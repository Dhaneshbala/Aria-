"""
Study Intelligence — Adaptive learning features.
Includes: Difficulty Adjustment, Adaptive Learning, Revision Predictor,
School Curriculum Mode, and Formula Memory.
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from services.ollama_service import OllamaService
from services.memory_service import MemoryService

logger = logging.getLogger(__name__)

ollama = OllamaService()
memory_svc = MemoryService()


class StudyIntelligence:

    # ── Difficulty Adjustment ─────────────────────────────────────────────────

    async def get_difficulty(self, topic: str, model: str = "qwen3:8b") -> str:
        """Determine appropriate difficulty level based on student profile."""
        profile = await memory_svc.get_profile()
        subjects = profile.get("subjects", {})

        # Check if topic matches a known subject
        for subj, stats in subjects.items():
            if subj.lower() in topic.lower() or topic.lower() in subj.lower():
                total = stats.get("total", 0)
                correct = stats.get("correct", 0)
                if total >= 3:
                    accuracy = correct / total
                    if accuracy >= 0.8:
                        return "hard"
                    elif accuracy >= 0.5:
                        return "medium"
                    else:
                        return "easy"

        # Default to medium for unknown topics
        return "medium"

    async def adjust_explanation(self, explanation: str, difficulty: str, model: str = "qwen3:8b") -> str:
        """Adjust explanation complexity based on difficulty level."""
        if difficulty == "medium":
            return explanation

        system = (
            f"You are adjusting an explanation for a student who needs a {'simpler' if difficulty == 'easy' else 'more advanced'} version.\n"
            f"{'Use simpler language, more analogies, and break down complex ideas.' if difficulty == 'easy' else 'Go deeper, use technical terms, include more complex examples.'}\n"
            "Return ONLY the adjusted explanation."
        )
        try:
            result = await ollama.complete(model, explanation[:2000], system=system, max_tokens=2000)
            return result.strip() if result.strip() else explanation
        except Exception:
            return explanation

    # ── Adaptive Learning ─────────────────────────────────────────────────────

    async def identify_weak_topics(self) -> list[dict]:
        """Analyse study profile to identify weak areas that need attention."""
        profile = await memory_svc.get_profile()
        subjects = profile.get("subjects", {})
        weak_topics = []

        for subj, stats in subjects.items():
            total = stats.get("total", 0)
            correct = stats.get("correct", 0)
            if total >= 3:
                accuracy = correct / total
                if accuracy < 0.5:
                    weak_topics.append({
                        "topic": subj,
                        "accuracy": accuracy,
                        "attempts": total,
                        "priority": "high" if accuracy < 0.3 else "medium",
                        "recommendation": f"Focus on {subj} — you're getting {accuracy:.0%} correct after {total} attempts.",
                    })

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        weak_topics.sort(key=lambda x: priority_order.get(x["priority"], 2))
        return weak_topics

    async def suggest_next_topic(self) -> dict:
        """Suggest what the student should study next based on their profile."""
        weak = await self.identify_weak_topics()

        if weak:
            return {
                "suggestion": weak[0]["topic"],
                "reason": weak[0]["recommendation"],
                "priority": weak[0]["priority"],
            }

        profile = await memory_svc.get_profile()
        strong = profile.get("strong_areas", [])
        if strong:
            return {
                "suggestion": strong[0],
                "reason": f"You're strong in {strong[0]}! Try advanced topics or a new subject.",
                "priority": "low",
            }

        return {
            "suggestion": "Start with any topic you're curious about!",
            "reason": "No performance data yet. Try a quiz or flashcards to build your profile.",
            "priority": "info",
        }

    # ── Revision Predictor ────────────────────────────────────────────────────

    async def predict_revision_needs(self) -> list[dict]:
        """Use spaced repetition logic to predict what needs revision."""
        profile = await memory_svc.get_profile()
        subjects = profile.get("subjects", {})
        revision_list = []

        # Simple spaced repetition: items needing review based on accuracy and recency
        for subj, stats in subjects.items():
            total = stats.get("total", 0)
            correct = stats.get("correct", 0)
            if total >= 3:
                accuracy = correct / total
                # Lower accuracy = more urgent revision
                if accuracy < 0.7:
                    urgency = "high" if accuracy < 0.5 else "medium"
                    next_review = "now" if accuracy < 0.4 else "this week"
                    revision_list.append({
                        "topic": subj,
                        "accuracy": accuracy,
                        "attempts": total,
                        "urgency": urgency,
                        "next_review": next_review,
                        "suggestion": f"Review {subj} {next_review} — accuracy is {accuracy:.0%}",
                    })

        revision_list.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x["urgency"], 2))
        return revision_list

    # ── School Curriculum Mode ────────────────────────────────────────────────

    async def get_curriculum_context(self, subject: str, model: str = "qwen3:8b") -> str:
        """Generate context about what's typically covered in this subject."""
        system = (
            "You are an education expert who knows school curricula.\n"
            f"For the subject '{subject}', provide:\n"
            "1. Key topics typically covered in middle school (age 12-15)\n"
            "2. Important concepts to master\n"
            "3. Common exam topics\n"
            "4. Progressive difficulty levels\n"
            "Be concise. Return as a structured list."
        )
        try:
            result = await ollama.complete(model, f"What is covered in {subject} at school?", system=system, max_tokens=600)
            return result
        except Exception:
            return f"Curriculum information for {subject} is not available."

    # ── Formula Memory ────────────────────────────────────────────────────────

    async def get_learned_formulas(self) -> list[dict]:
        """Retrieve formulas the student has been taught (from conversation history)."""
        # Search conversations for formula-related content
        results = await memory_svc.search_global("formula equation theorem", limit=10)
        formulas = []
        for r in results:
            text = r.get("text", "")
            # Extract formula-like patterns
            import re
            formula_patterns = [
                r'[A-Za-z]+\s*=\s*[^,\n]+',  # x = ...
                r'[A-Z]\s*=\s*[^,\n]+',  # Single letter = ...
                r'\b(?:area|volume|speed|force|energy|power)\s*=\s*[^,\n]+',
            ]
            for pat in formula_patterns:
                for m in re.finditer(pat, text, re.I):
                    formula = m.group().strip()
                    if len(formula) > 5 and len(formula) < 100:
                        formulas.append({
                            "formula": formula,
                            "source": r.get("conversation_id", "unknown"),
                            "timestamp": r.get("timestamp", ""),
                        })

        # Deduplicate
        seen = set()
        unique = []
        for f in formulas:
            key = f["formula"].lower()
            if key not in seen:
                seen.add(key)
                unique.append(f)
        return unique[:20]
