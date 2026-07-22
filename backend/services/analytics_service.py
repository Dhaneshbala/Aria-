"""
Analytics Dashboard — Study activity analytics with heatmap, trends, predicted grades, focus score.
"""
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path.home() / ".aria_data"
CONVERSATIONS_FILE = DATA_DIR / "conversations.json"
PROFILE_FILE = DATA_DIR / "study_profile.json"
ANALYTICS_FILE = DATA_DIR / "analytics.json"


def _load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return default


def _save_json(path, data):
    path.write_text(json.dumps(data, indent=2))


class AnalyticsService:

    def get_heatmap(self, months: int = 6) -> dict:
        """Generate GitHub-style study activity heatmap data."""
        convs = _load_json(CONVERSATIONS_FILE, {})
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=months * 30)

        # Count activity per day
        daily = defaultdict(int)
        for cid, turns in convs.items():
            for turn in turns:
                try:
                    ts = turn.get("timestamp", "")
                    if ts:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        if dt >= cutoff:
                            day = dt.strftime("%Y-%m-%d")
                            daily[day] += 1
                except Exception:
                    continue

        # Fill in missing days with 0
        heatmap = []
        current = cutoff
        while current <= now:
            day = current.strftime("%Y-%m-%d")
            heatmap.append({
                "date": day,
                "count": daily.get(day, 0),
                "day_of_week": current.strftime("%a"),
            })
            current += timedelta(days=1)

        max_count = max((h["count"] for h in heatmap), default=1) or 1
        for h in heatmap:
            h["level"] = min(4, int(h["count"] / max_count * 4)) if h["count"] > 0 else 0

        return {
            "heatmap": heatmap,
            "total_days_active": sum(1 for h in heatmap if h["count"] > 0),
            "total_interactions": sum(h["count"] for h in heatmap),
            "max_daily": max_count,
            "current_streak": self._calculate_streak(daily),
        }

    def get_trends(self, days: int = 30) -> dict:
        """Performance trends over time."""
        profile = _load_json(PROFILE_FILE, {})
        convs = _load_json(CONVERSATIONS_FILE, {})
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=days)

        # Daily activity counts
        daily_activity = defaultdict(int)
        daily_questions = defaultdict(lambda: {"correct": 0, "total": 0})

        for cid, turns in convs.items():
            for turn in turns:
                try:
                    ts = turn.get("timestamp", "")
                    if ts:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        if dt >= cutoff:
                            day = dt.strftime("%Y-%m-%d")
                            daily_activity[day] += 1
                except Exception:
                    continue

        # Subject performance over time
        subjects = profile.get("subjects", {})
        subject_trends = {}
        for subj, stats in subjects.items():
            total = stats.get("total", 0)
            correct = stats.get("correct", 0)
            accuracy = correct / total if total > 0 else 0
            subject_trends[subj] = {
                "accuracy": round(accuracy * 100),
                "total": total,
                "correct": correct,
                "trend": "improving" if accuracy >= 0.7 else "needs_work",
            }

        return {
            "daily_activity": dict(daily_activity),
            "subject_trends": subject_trends,
            "period_days": days,
        }

    def get_predicted_grades(self) -> dict:
        """Predict grades based on current performance trajectory."""
        profile = _load_json(PROFILE_FILE, {})
        subjects = profile.get("subjects", {})
        predictions = {}

        for subj, stats in subjects.items():
            total = stats.get("total", 0)
            correct = stats.get("correct", 0)
            accuracy = correct / total if total > 0 else 0

            if total < 5:
                band = "Insufficient data"
                band_num = None
            elif accuracy >= 0.9:
                band = "Band 6 (90+)"
                band_num = 6
            elif accuracy >= 0.8:
                band = "Band 5 (80-89)"
                band_num = 5
            elif accuracy >= 0.7:
                band = "Band 4 (70-79)"
                band_num = 4
            elif accuracy >= 0.6:
                band = "Band 3 (60-69)"
                band_num = 3
            elif accuracy >= 0.5:
                band = "Band 2 (50-59)"
                band_num = 2
            else:
                band = "Band 1 (<50)"
                band_num = 1

            predictions[subj] = {
                "accuracy": round(accuracy * 100),
                "questions_attempted": total,
                "predicted_band": band,
                "band_number": band_num,
                "confidence": "high" if total >= 20 else "medium" if total >= 10 else "low",
            }

        return predictions

    def get_focus_score(self) -> dict:
        """Measure study session quality."""
        convs = _load_json(CONVERSATIONS_FILE, {})
        profile = _load_json(PROFILE_FILE, {})
        now = datetime.now(timezone.utc)

        # Analyse last 7 days
        cutoff = now - timedelta(days=7)
        subjects_seen = set()
        total_turns = 0
        unique_days = set()

        for cid, turns in convs.items():
            for turn in turns:
                try:
                    ts = turn.get("timestamp", "")
                    if ts:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        if dt >= cutoff:
                            total_turns += 1
                            unique_days.add(dt.strftime("%Y-%m-%d"))
                            # Detect subject from message
                            msg = turn.get("user", "").lower()
                            for subj in ["math", "science", "english", "history", "geography"]:
                                if subj in msg:
                                    subjects_seen.add(subj)
                except Exception:
                    continue

        # Focus metrics
        variety_score = min(len(subjects_seen) / 3, 1.0) * 100  # Max at 3 subjects
        consistency_score = min(len(unique_days) / 5, 1.0) * 100  # Max at 5 days
        volume_score = min(total_turns / 20, 1.0) * 100  # Max at 20 turns

        focus_score = (variety_score * 0.3 + consistency_score * 0.4 + volume_score * 0.3)

        return {
            "focus_score": round(focus_score),
            "variety_score": round(variety_score),
            "consistency_score": round(consistency_score),
            "volume_score": round(volume_score),
            "subjects_practiced": list(subjects_seen),
            "days_active_this_week": len(unique_days),
            "total_interactions_week": total_turns,
            "assessment": "Excellent" if focus_score >= 80 else "Good" if focus_score >= 60 else "Needs improvement" if focus_score >= 40 else "Low activity",
        }

    def get_weekly_summary(self) -> dict:
        """Generate a weekly learning summary."""
        profile = _load_json(PROFILE_FILE, {})
        subjects = profile.get("subjects", {})

        total_q = profile.get("total_questions", 0)
        total_correct = profile.get("correct_answers", 0)
        accuracy = total_correct / total_q if total_q > 0 else 0

        subjects_summary = []
        for subj, stats in subjects.items():
            t = stats.get("total", 0)
            c = stats.get("correct", 0)
            subjects_summary.append({
                "subject": subj,
                "questions": t,
                "correct": c,
                "accuracy": round(c / t * 100) if t > 0 else 0,
            })

        return {
            "total_questions": total_q,
            "total_correct": total_correct,
            "overall_accuracy": round(accuracy * 100),
            "subjects": sorted(subjects_summary, key=lambda x: x["questions"], reverse=True),
            "strong_areas": profile.get("strong_areas", []),
            "weak_areas": profile.get("weak_areas", []),
        }

    def _calculate_streak(self, daily: dict) -> int:
        """Calculate current consecutive study days."""
        now = datetime.now(timezone.utc)
        streak = 0
        current = now
        while True:
            day = current.strftime("%Y-%m-%d")
            if daily.get(day, 0) > 0:
                streak += 1
                current -= timedelta(days=1)
            else:
                break
            if streak > 365:
                break
        return streak
