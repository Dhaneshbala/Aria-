"""
Gamification — Streaks, Achievements, Challenge Mode, Leaderboard.
"""
import json
import logging
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path.home() / ".aria_data"
ACHIEVEMENTS_FILE = DATA_DIR / "achievements.json"
GAMIFICATION_FILE = DATA_DIR / "gamification.json"
PROFILE_FILE = DATA_DIR / "study_profile.json"


def _load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return default


def _save_json(path, data):
    path.write_text(json.dumps(data, indent=2))


ACHIEVEMENT_DEFS = [
    {"id": "first_quiz", "name": "First Steps", "desc": "Complete your first quiz", "icon": "🎯", "category": "milestone"},
    {"id": "quiz_10", "name": "Quiz Master", "desc": "Complete 10 quizzes", "icon": "🏆", "category": "milestone"},
    {"id": "quiz_50", "name": "Quiz Legend", "desc": "Complete 50 quizzes", "icon": "👑", "category": "milestone"},
    {"id": "flashcard_50", "name": "Card Collector", "desc": "Review 50 flashcards", "icon": "🃏", "category": "milestone"},
    {"id": "flashcard_100", "name": "Card Champion", "desc": "Review 100 flashcards", "icon": "🎰", "category": "milestone"},
    {"id": "streak_3", "name": "Three Day Streak", "desc": "Study 3 days in a row", "icon": "🔥", "category": "streak"},
    {"id": "streak_7", "name": "Week Warrior", "desc": "Study 7 days in a row", "icon": "⚡", "category": "streak"},
    {"id": "streak_14", "name": "Fortnight Fighter", "desc": "Study 14 days in a row", "icon": "💪", "category": "streak"},
    {"id": "streak_30", "name": "Monthly Master", "desc": "Study 30 days in a row", "icon": "🌟", "category": "streak"},
    {"id": "perfect_quiz", "name": "Perfect Score", "desc": "Get 100% on a quiz", "icon": "💯", "category": "achievement"},
    {"id": "all_subjects", "name": "Well Rounded", "desc": "Study 5 different subjects", "icon": "🎓", "category": "achievement"},
    {"id": "early_bird", "name": "Early Bird", "desc": "Study before 8am", "icon": "🌅", "category": "special"},
    {"id": "night_owl", "name": "Night Owl", "desc": "Study after 10pm", "icon": "🦉", "category": "special"},
    {"id": "speed_demon", "name": "Speed Demon", "desc": "Complete a quiz in under 2 minutes", "icon": "⏱️", "category": "special"},
    {"id": "night_before", "name": "Crammer", "desc": "Study the night before something", "icon": "📚", "category": "special"},
    {"id": "pdf_reader", "name": "Bookworm", "desc": "Upload and analyse 5 documents", "icon": "🐛", "category": "milestone"},
    {"id": "video_learner", "name": "Visual Learner", "desc": "Analyse 3 YouTube videos", "icon": "🎬", "category": "milestone"},
    {"id": "code_ninja", "name": "Code Ninja", "desc": "Use coding features 10 times", "icon": "🥷", "category": "milestone"},
    {"id": "mindmap_master", "name": "Mind Mapper", "desc": "Create 5 mind maps", "icon": "🗺️", "category": "milestone"},
    {"id": "presentation_pro", "name": "Presentation Pro", "desc": "Generate 3 PowerPoint presentations", "icon": "📊", "category": "milestone"},
]


class GamificationService:

    def __init__(self):
        self._data = _load_json(GAMIFICATION_FILE, {
            "achievements": [],
            "xp": 0,
            "level": 1,
            "badges": [],
        })

    def check_and_award_achievements(self, profile: dict, convs: dict) -> list[dict]:
        """Check all achievement conditions and award new ones."""
        new_achievements = []
        existing = {a["id"] for a in self._data.get("achievements", [])}

        total_q = profile.get("total_questions", 0)
        total_correct = profile.get("correct_answers", 0)
        subjects = profile.get("subjects", {})

        # Count interactions
        total_turns = sum(len(turns) for turns in convs.values())
        subject_count = len(subjects)

        # Streak calculation
        daily = {}
        for cid, turns in convs.items():
            for turn in turns:
                try:
                    ts = turn.get("timestamp", "")
                    if ts:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        day = dt.strftime("%Y-%m-%d")
                        daily[day] = daily.get(day, 0) + 1
                except Exception:
                    continue
        streak = self._calc_streak(daily)

        # Time-based
        now = datetime.now(timezone.utc)
        hour = now.hour

        # Check each achievement
        checks = {
            "first_quiz": total_q >= 1,
            "quiz_10": total_q >= 10,
            "quiz_50": total_q >= 50,
            "flashcard_50": total_turns >= 50,
            "flashcard_100": total_turns >= 100,
            "streak_3": streak >= 3,
            "streak_7": streak >= 7,
            "streak_14": streak >= 14,
            "streak_30": streak >= 30,
            "perfect_quiz": total_correct > 0 and total_q > 0 and (total_correct / total_q) == 1.0,
            "all_subjects": subject_count >= 5,
            "early_bird": 5 <= hour < 8,
            "night_owl": hour >= 22,
        }

        for ach_id, condition in checks.items():
            if condition and ach_id not in existing:
                ach_def = next((a for a in ACHIEVEMENT_DEFS if a["id"] == ach_id), None)
                if ach_def:
                    new_achievements.append(ach_def)
                    self._data["achievements"].append({
                        **ach_def,
                        "earned_at": now.isoformat(),
                    })
                    self._data["xp"] = self._data.get("xp", 0) + 10
                    self._data["level"] = 1 + self._data["xp"] // 100

        if new_achievements:
            _save_json(GAMIFICATION_FILE, self._data)

        return new_achievements

    def get_progress(self) -> dict:
        """Get gamification progress."""
        total_ach = len(ACHIEVEMENT_DEFS)
        earned = len(self._data.get("achievements", []))

        return {
            "xp": self._data.get("xp", 0),
            "level": self._data.get("level", 1),
            "xp_to_next": 100 - (self._data.get("xp", 0) % 100),
            "achievements_earned": earned,
            "total_achievements": total_ach,
            "percentage": round(earned / total_ach * 100) if total_ach > 0 else 0,
            "achievements": self._data.get("achievements", []),
            "all_achievements": ACHIEVEMENT_DEFS,
        }

    def get_challenge(self) -> dict:
        """Generate a random challenge for the student."""
        profile = _load_json(PROFILE_FILE, {})
        subjects = profile.get("subjects", {})

        challenges = [
            {"id": "speed_quiz", "name": "Speed Round", "desc": "Complete 5 questions in under 3 minutes", "xp_reward": 20, "type": "timed"},
            {"id": "accuracy挑战", "name": "Accuracy Challenge", "desc": "Get 80%+ on a 10-question quiz", "xp_reward": 25, "type": "accuracy"},
            {"id": "subject_blend", "name": "Subject Blend", "desc": "Study 3 different subjects today", "xp_reward": 15, "type": "variety"},
            {"id": "flashcard_sprint", "name": "Flashcard Sprint", "desc": "Review 10 flashcards in a row without missing", "xp_reward": 30, "type": "streak"},
            {"id": "weekend_warrior", "name": "Weekend Warrior", "desc": "Study for 30+ minutes on a weekend", "xp_reward": 15, "type": "weekend"},
        ]

        # Pick a random challenge
        challenge = random.choice(challenges)
        challenge["expires"] = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        return challenge

    def get_leaderboard(self) -> dict:
        """Get personal leaderboard (subject performance ranking)."""
        profile = _load_json(PROFILE_FILE, {})
        subjects = profile.get("subjects", {})

        entries = []
        for subj, stats in subjects.items():
            total = stats.get("total", 0)
            correct = stats.get("correct", 0)
            accuracy = correct / total if total > 0 else 0
            entries.append({
                "subject": subj,
                "accuracy": round(accuracy * 100),
                "questions": total,
                "xp": total * 2 + correct * 3,
                "rank": "",  # Set below
            })

        entries.sort(key=lambda e: e["xp"], reverse=True)
        medals = ["🥇", "🥈", "🥉"]
        for i, entry in enumerate(entries):
            entry["rank"] = medals[i] if i < 3 else f"#{i+1}"

        return {
            "entries": entries,
            "total_xp": self._data.get("xp", 0),
            "level": self._data.get("level", 1),
        }

    def _calc_streak(self, daily: dict) -> int:
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
