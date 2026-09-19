"""
Advanced Study Intelligence — NSW Curriculum-aware features.
Extends the base StudyIntelligence with:
  • Exam Readiness Score (NESA-style assessment prediction)
  • Spaced Repetition Engine (SM-2 algorithm)
  • Learning Style Detector
  • Knowledge Gap Finder (maps against NSW syllabus)
"""
import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from services.ollama_service import OllamaService
try:
    from models.database import MODELS
except Exception:
    MODELS = {"main": "gemma4:e4b-mlx", "embedding": "mxbai-embed-large"}
from services.memory_service import MemoryService
from services.nsw_curriculum_service import NSWCurriculumService, NSW_KLAS, NSW_STAGES

logger = logging.getLogger(__name__)

ollama = OllamaService()
memory_svc = MemoryService()
curriculum = NSWCurriculumService()

# Spaced Repetition file
DATA_DIR = __import__('pathlib').Path(__import__('os').environ.get("ARIA_DATA_DIR", __import__('pathlib').Path.home() / ".aria_data"))
SR_FILE = DATA_DIR / "spaced_repetition.json"
LEARNING_STYLE_FILE = DATA_DIR / "learning_style.json"
KNOWLEDGE_MAP_FILE = DATA_DIR / "knowledge_map.json"


import threading
import tempfile
import os
_JSON_LOCKS: dict[str, threading.RLock] = {}
_JSON_LOCKS_LOCK = threading.Lock()

def _lock_for(path) -> threading.RLock:
    key = str(path)
    with _JSON_LOCKS_LOCK:
        if key not in _JSON_LOCKS:
            _JSON_LOCKS[key] = threading.RLock()
        return _JSON_LOCKS[key]

def _load_json(path, default):
    with _lock_for(path):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return default


def _save_json(path, data):
    lock = _lock_for(path)
    with lock:
        text = json.dumps(data, indent=2, ensure_ascii=False)
        # atomic write
        fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.tmp.")
        try:
            with open(fd, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            Path(tmp_path).replace(path)
        finally:
            p = Path(tmp_path)
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass


class AdvancedStudyIntelligence:

    # ═══════════════════════════════════════════════════════════════════════════
    # Exam Readiness Score
    # ═══════════════════════════════════════════════════════════════════════════

    async def calculate_exam_readiness(self, subject: str, days_until_exam: int = 14) -> dict:
        """Calculate how ready a student is for an exam, using NSW curriculum mapping."""
        profile = await memory_svc.get_profile()
        subjects = profile.get("subjects", {})

        # Map subject to NSW curriculum
        kla = self._subject_to_kla(subject)
        stage = curriculum.get_stage_for_age(13)  # Default for student
        outcomes = curriculum.get_outcomes(kla, stage) if kla else []
        content = curriculum.get_subject_content(kla, stage) if kla else []

        # Calculate accuracy for this subject
        subj_stats = subjects.get(subject, {})
        total = subj_stats.get("total", 0)
        correct = subj_stats.get("correct", 0)
        accuracy = correct / total if total > 0 else 0

        # Estimate readiness based on multiple factors
        factors = {}

        # 1. Accuracy score (40% weight)
        factors["accuracy"] = {
            "score": round(accuracy * 100),
            "weight": 0.4,
            "detail": f"{correct}/{total} correct ({accuracy:.0%})",
        }

        # 2. Volume of practice (25% weight)
        practice_score = min(total / 30, 1.0)  # Max at 30 questions
        factors["practice_volume"] = {
            "score": round(practice_score * 100),
            "weight": 0.25,
            "detail": f"{total} questions attempted",
        }

        # 3. Consistency (20% weight)
        last_active = profile.get("last_active")
        if last_active:
            try:
                la = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
                days_since = (datetime.now(timezone.utc) - la).days
                consistency = max(0, 1 - (days_since / 7))  # Decay over 7 days
            except Exception:
                consistency = 0.5
        else:
            consistency = 0
        factors["consistency"] = {
            "score": round(consistency * 100),
            "weight": 0.20,
            "detail": f"Last active {last_active[:10] if last_active else 'never'}",
        }

        # 4. Curriculum coverage (15% weight) — heuristic: if student has practiced subject, count ~ half outcomes as touched
        if total >= 3 and accuracy >= 0.5:
            # estimate coverage by volume + accuracy: 3 quizzes ~20%, 15 quizzes ~50%, 30 ~75%
            coverage = min(0.75, 0.2 + (total / 30) * 0.55 + accuracy * 0.15)
            covered_outcomes = round(coverage * len(outcomes))
        elif total > 0:
            coverage = 0.15
            covered_outcomes = max(1, round(coverage * len(outcomes))) if outcomes else 0
        else:
            coverage = 0.0
            covered_outcomes = 0
        factors["curriculum_coverage"] = {
            "score": round(coverage * 100),
            "weight": 0.15,
            "detail": f"~{covered_outcomes}/{len(outcomes)} outcomes covered" if outcomes else "No NSW curriculum data",
        }

        # Calculate weighted readiness score
        readiness_score = sum(
            f["score"] * f["weight"] for f in factors.values()
        )

        # Predicted grade (NESA-style)
        if readiness_score >= 90:
            predicted_band = "Band 6 (90+)"
        elif readiness_score >= 80:
            predicted_band = "Band 5 (80-89)"
        elif readiness_score >= 70:
            predicted_band = "Band 4 (70-79)"
        elif readiness_score >= 60:
            predicted_band = "Band 3 (60-69)"
        elif readiness_score >= 50:
            predicted_band = "Band 2 (50-59)"
        else:
            predicted_band = "Band 1 (<50)"

        # Days recommendation
        if readiness_score >= 80:
            study_days = max(1, days_until_exam // 3)
        elif readiness_score >= 60:
            study_days = max(2, days_until_exam // 2)
        else:
            study_days = days_until_exam

        return {
            "subject": subject,
            "readiness_score": round(readiness_score),
            "factors": factors,
            "predicted_band": predicted_band,
            "days_until_exam": days_until_exam,
            "recommended_study_days": study_days,
            "nsw_curriculum": {
                "kla": kla,
                "stage": stage,
                "outcomes_count": len(outcomes),
                "content_areas": content[:5],
            },
        }

    def _subject_to_kla(self, subject: str) -> str | None:
        """Map a subject name to a NSW KLA key."""
        subject_lower = subject.lower()
        mapping = {
            "english": "english", "maths": "mathematics", "math": "mathematics",
            "mathematics": "mathematics", "science": "science", "biology": "science",
            "chemistry": "science", "physics": "science", "history": "history",
            "geography": "geography", "pdhpe": "pdhpe", "health": "pdhpe",
            "pe": "pdhpe", "ict": "technologies", "technology": "technologies",
            "art": "creative_arts", "music": "creative_arts", "drama": "creative_arts",
        }
        return mapping.get(subject_lower)

    # ═══════════════════════════════════════════════════════════════════════════
    # Spaced Repetition Engine (SM-2 Algorithm)
    # ═══════════════════════════════════════════════════════════════════════════

    async def add_flashcard(self, front: str, back: str, subject: str = "general") -> dict:
        """Add a flashcard to the spaced repetition system."""
        import uuid as _uuid
        cards = _load_json(SR_FILE, [])
        card = {
            "id": f"card_{_uuid.uuid4().hex[:12]}",
            "front": front,
            "back": back,
            "subject": subject,
            "ease_factor": 2.5,
            "interval": 1,
            "repetitions": 0,
            "next_review": datetime.now(timezone.utc).isoformat(),
            "last_review": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        cards.append(card)
        _save_json(SR_FILE, cards)
        return card

    async def review_flashcard(self, card_id: str, quality: int) -> dict:
        """
        Update flashcard using SM-2 algorithm.
        quality: 0-5 (0=complete blackout, 5=perfect response)
        """
        cards = _load_json(SR_FILE, [])
        for card in cards:
            if card["id"] == card_id:
                # SM-2 algorithm
                if quality >= 3:
                    # Correct response
                    if card["repetitions"] == 0:
                        card["interval"] = 1
                    elif card["repetitions"] == 1:
                        card["interval"] = 6
                    else:
                        card["interval"] = round(card["interval"] * card["ease_factor"])
                    card["repetitions"] += 1
                else:
                    # Incorrect — reset
                    card["repetitions"] = 0
                    card["interval"] = 1

                # Update ease factor
                card["ease_factor"] = max(
                    1.3,
                    card["ease_factor"] + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
                )

                # Calculate next review
                next_review = datetime.now(timezone.utc) + timedelta(days=card["interval"])
                card["next_review"] = next_review.isoformat()
                card["last_review"] = datetime.now(timezone.utc).isoformat()

                # Record review in history (for streak tracking)
                history = card.setdefault("review_history", [])
                history.append({
                    "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "quality": quality,
                })
                if len(history) > 200:
                    card["review_history"] = history[-200:]

                _save_json(SR_FILE, cards)
                return card

        return {"error": "Card not found"}

    async def get_due_cards(self, subject: str | None = None, limit: int = 20) -> list[dict]:
        """Get cards due for review."""
        cards = _load_json(SR_FILE, [])
        now = datetime.now(timezone.utc)
        due = []
        for card in cards:
            if subject and card.get("subject") != subject:
                continue
            try:
                next_rev = datetime.fromisoformat(card["next_review"].replace("Z", "+00:00"))
                if next_rev <= now:
                    due.append(card)
            except Exception:
                due.append(card)

        # Sort by overdue-ness (most overdue first)
        due.sort(key=lambda c: c.get("next_review", ""))
        return due[:limit]

    async def get_sr_stats(self) -> dict:
        """Get spaced repetition statistics."""
        cards = _load_json(SR_FILE, [])
        now = datetime.now(timezone.utc)

        due = 0
        learning = 0
        mastered = 0
        review_days = set()
        for card in cards:
            try:
                next_rev = datetime.fromisoformat(card["next_review"].replace("Z", "+00:00"))
                if next_rev <= now:
                    due += 1
                elif card["repetitions"] >= 5:
                    mastered += 1
                else:
                    learning += 1
            except Exception:
                due += 1
            for entry in card.get("review_history", []):
                review_days.add(entry.get("date", ""))

        # Streak: consecutive days (ending today or yesterday) with a review
        streak = 0
        d = datetime.now(timezone.utc).date()
        if d.strftime("%Y-%m-%d") not in review_days:
            d -= timedelta(days=1)
        while d.strftime("%Y-%m-%d") in review_days:
            streak += 1
            d -= timedelta(days=1)

        return {
            "total_cards": len(cards),
            "due_today": due,
            "learning": learning,
            "mastered": mastered,
            "review_streak": streak,
        }

    async def delete_flashcard(self, card_id: str) -> dict:
        """Delete a flashcard by ID."""
        cards = _load_json(SR_FILE, [])
        before = len(cards)
        cards = [c for c in cards if c["id"] != card_id]
        if len(cards) < before:
            _save_json(SR_FILE, cards)
            return {"status": "deleted", "id": card_id}
        return {"error": "Card not found"}

    async def add_flashcards_bulk(self, flashcards: list[dict], subject: str = "general") -> list[dict]:
        """Add multiple flashcards at once (e.g. from generated flashcard set)."""
        import uuid as _uuid
        cards = _load_json(SR_FILE, [])
        existing_ids = {c.get("id") for c in cards}
        added = []
        for fc in flashcards[:200]:
            front = str(fc.get("front", "")).strip()
            back = str(fc.get("back", "")).strip()
            if not front or not back:
                continue  # skip empties — previously stored blank cards
            cid = f"card_{_uuid.uuid4().hex[:12]}"
            while cid in existing_ids:
                cid = f"card_{_uuid.uuid4().hex[:12]}"
            existing_ids.add(cid)
            card = {
                "id": cid,
                "front": front,
                "back": back,
                "subject": subject,
                "ease_factor": 2.5,
                "interval": 1,
                "repetitions": 0,
                "next_review": datetime.now(timezone.utc).isoformat(),
                "last_review": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            cards.append(card)
            added.append(card)
        _save_json(SR_FILE, cards)
        return added

    async def get_all_cards(self, subject: str | None = None) -> list[dict]:
        """Get all flashcards (not just due ones)."""
        cards = _load_json(SR_FILE, [])
        if subject:
            cards = [c for c in cards if c.get("subject") == subject]
        return cards

    # ═══════════════════════════════════════════════════════════════════════════
    # Learning Style Detector
    # ═══════════════════════════════════════════════════════════════════════════

    async def detect_learning_style(self) -> dict:
        """Analyse student's interaction patterns to detect learning style."""
        profile = await memory_svc.get_profile()
        convs_data = _load_json(DATA_DIR / "conversations.json", {})

        # Analyse patterns
        visual_count = 0      # Image uploads, mind maps, diagrams
        reading_count = 0     # Long text questions, summaries
        practice_count = 0    # Quiz attempts, worksheet solving
        social_count = 0      # Questions about others, collaboration

        for cid, turns in convs_data.items():
            for turn in turns:
                user_msg = turn.get("user", "").lower()
                if any(w in user_msg for w in ["image", "diagram", "picture", "visual", "mind map", "chart"]):
                    visual_count += 1
                if any(w in user_msg for w in ["explain", "what is", "tell me", "read", "notes", "summary"]):
                    reading_count += 1
                if any(w in user_msg for w in ["quiz", "test", "practice", "solve", "worksheet", "calculate"]):
                    practice_count += 1
                if any(w in user_msg for w in ["how do", "method", "approach", "compare", "debate"]):
                    social_count += 1

        total = max(visual_count + reading_count + practice_count + social_count, 1)
        styles = {
            "visual": {"count": visual_count, "percentage": round(visual_count / total * 100)},
            "reading": {"count": reading_count, "percentage": round(reading_count / total * 100)},
            "practice": {"count": practice_count, "percentage": round(practice_count / total * 100)},
            "social": {"count": social_count, "percentage": round(social_count / total * 100)},
        }

        # Determine dominant style
        dominant = max(styles, key=lambda k: styles[k]["count"])
        style_descriptions = {
            "visual": "You learn best through images, diagrams, and visual representations. Aria will create more mind maps and visual aids for you.",
            "reading": "You learn best through reading and written explanations. Aria will provide detailed written notes and summaries.",
            "practice": "You learn best by doing — practice problems and hands-on work. Aria will generate more quizzes and practice questions.",
            "social": "You learn best through discussion and understanding different approaches. Aria will use Socratic questioning and compare methods.",
        }

        result = {
            "dominant_style": dominant,
            "description": style_descriptions.get(dominant, ""),
            "styles": styles,
            "recommendation": f"Based on your {total} interactions, Aria recommends a {dominant}-focused approach.",
        }

        # Save
        _save_json(LEARNING_STYLE_FILE, result)
        return result

    # ═══════════════════════════════════════════════════════════════════════════
    # Knowledge Gap Finder (NSW Curriculum)
    # ═══════════════════════════════════════════════════════════════════════════

    async def find_knowledge_gaps(self, subject: str) -> dict:
        """Compare what the student knows vs. NSW curriculum requirements."""
        profile = await memory_svc.get_profile()
        subjects = profile.get("subjects", {})
        kla = self._subject_to_kla(subject)
        stage = curriculum.get_stage_for_age(13)

        if not kla:
            return {
                "subject": subject,
                "error": f"Unknown subject: {subject}. Try: English, Mathematics, Science, History, Geography",
            }

        content = curriculum.get_subject_content(kla, stage)
        outcomes = curriculum.get_outcomes(kla, stage)
        subj_stats = subjects.get(subject, {})
        accuracy = subj_stats.get("correct", 0) / max(subj_stats.get("total", 0), 1)

        # Analyse gaps based on quiz/flashcard history
        gaps = []
        covered = []
        for item in content:
            # Simple heuristic: check if any quiz/flashcard related to this content exists
            related_quizzes = subj_stats.get("total", 0)
            if related_quizzes > 0 and accuracy >= 0.6:
                covered.append({"topic": item, "status": "covered"})
            else:
                gaps.append({"topic": item, "status": "gap", "priority": "high"})

        return {
            "subject": subject,
            "kla": kla,
            "stage": stage,
            "stage_name": curriculum.get_stages().get(stage, {}).get("name", ""),
            "total_outcomes": len(outcomes),
            "outcomes": outcomes[:10],
            "content_areas": content,
            "covered": covered,
            "gaps": gaps,
            "coverage_percentage": round(len(covered) / max(len(content), 1) * 100),
            "recommendation": f"You've covered {len(covered)}/{len(content)} content areas. Focus on the gaps above." if gaps else "Great coverage! Keep practising to maintain mastery.",
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # NSW Curriculum Helpers
    # ═══════════════════════════════════════════════════════════════════════════

    def get_curriculum_for_age(self, age: int) -> dict:
        """Get all subjects and outcomes for a given age."""
        stage = curriculum.get_stage_for_age(age)
        if not stage:
            return {"error": "Age out of range (4-18)"}

        subjects = {}
        for kla_key, kla_data in NSW_KLAS.items():
            outcomes = kla_data.get("stages", {}).get(stage, [])
            content = kla_data.get("content", {}).get(stage, [])
            if outcomes or content:
                subjects[kla_key] = {
                    "name": kla_data["name"],
                    "outcomes": outcomes,
                    "content": content,
                }

        return {
            "age": age,
            "stage": stage,
            "stage_name": NSW_STAGES[stage]["name"],
            "subjects": subjects,
        }

    def search_curriculum(self, query: str) -> list[dict]:
        return curriculum.search_curriculum(query)
