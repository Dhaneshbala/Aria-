"""
Idle Learner — DISABLED by default per user request (was auto-creating
random flashcards for weak/curriculum topics).

Set ARIA_IDLE_LEARNER=1 to re-enable. When disabled, start_idle_learner()
is a no-op and _should_learn() always returns False, so no background
flashcards/quizzes are ever generated. Manual flashcard creation still works.
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

IDLE_THRESHOLD_SEC = int(os.environ.get("ARIA_IDLE_THRESHOLD_SEC", "300"))  # 5 min idle
COOLDOWN_SEC = int(os.environ.get("ARIA_IDLE_COOLDOWN_SEC", "3600"))  # 1h between learns
MAX_WEAK_TOPICS = 2
COMPREHENSIVE_PER_CYCLE = 1  # one comprehensive topic per idle cycle to avoid overload

DATA_DIR = Path.home() / ".aria_data"
COMPREHENSIVE_PROGRESS = DATA_DIR / "comprehensive_progress.json"

_last_learn_ts = 0.0
_learner_task: asyncio.Task | None = None

def _idle_learner_enabled() -> bool:
    return os.environ.get("ARIA_IDLE_LEARNER", "0").lower() in ("1", "true", "yes", "on")

def _should_learn(last_activity_ts: float) -> bool:
    if not _idle_learner_enabled():
        return False
    now = time.time()
    global _last_learn_ts
    if now - last_activity_ts < IDLE_THRESHOLD_SEC:
        return False
    if now - _last_learn_ts < COOLDOWN_SEC:
        return False
    # Skip during pytest
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return True

def _get_all_highschool_topics() -> list[str]:
    """All topics needed for A-grade: NSW S4-S6 (Years 7-12) across all KLAs."""
    try:
        from services.nsw_curriculum_service import NSW_KLAS
        topics = []
        for kla_key, kla_data in NSW_KLAS.items():
            for stage in ["S4", "S5", "S6"]:
                for content in kla_data.get("content", {}).get(stage, []):
                    # Keep full descriptor as topic: "Mathematics S4: Number and Algebra..."
                    topics.append(f"{kla_data['name']} {stage}: {content}")
                # Also add individual outcomes as topics for thoroughness (first 3 per stage to avoid explosion)
                for outcome in kla_data.get("stages", {}).get(stage, [])[:2]:
                    topics.append(f"{kla_data['name']} {stage} outcome {outcome}")
        # Deduplicate, keep order, limit to high-school core for sanity (~120 topics)
        seen = set()
        uniq = []
        for t in topics:
            if t not in seen:
                seen.add(t)
                uniq.append(t)
        return uniq[:150]  # cap for M4
    except Exception:
        return []

def _load_comprehensive_progress() -> dict:
    if COMPREHENSIVE_PROGRESS.exists():
        try:
            return json.loads(COMPREHENSIVE_PROGRESS.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"covered": [], "total": 0, "last_topic": None}

def _save_comprehensive_progress(progress: dict):
    try:
        COMPREHENSIVE_PROGRESS.parent.mkdir(parents=True, exist_ok=True)
        COMPREHENSIVE_PROGRESS.write_text(json.dumps(progress, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.debug("Comprehensive progress save failed: %s", e)

def _get_next_uncovered_topic() -> str | None:
    all_topics = _get_all_highschool_topics()
    prog = _load_comprehensive_progress()
    covered = set(prog.get("covered", []))
    for t in all_topics:
        if t not in covered:
            return t
    # All covered — cycle again from start (spaced repetition for A)
    return all_topics[0] if all_topics else None

def _mark_comprehensive_covered(topic: str):
    prog = _load_comprehensive_progress()
    covered = prog.get("covered", [])
    if topic not in covered:
        covered.append(topic)
        prog["covered"] = covered
        prog["total"] = len(_get_all_highschool_topics())
        prog["last_topic"] = topic
        prog["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_comprehensive_progress(prog)

async def _learn_once():
    """One idle learning cycle — weak topics -> flashcards/quiz."""
    if not _idle_learner_enabled():
        return
    global _last_learn_ts
    _last_learn_ts = time.time()
    try:
        from services.memory_service import MemoryService
        from services.study_service import StudyService
        from models.database import MODELS

        mem = MemoryService()
        profile = await mem.get_profile()
        weak = profile.get("weak_areas", []) or []
        # fallback: derive weak from subjects if weak_areas empty but accuracy low
        if not weak:
            subjects = profile.get("subjects", {})
            for subj, stats in subjects.items():
                if stats.get("total", 0) >= 3 and stats.get("correct", 0) / max(1, stats["total"]) < 0.6:
                    weak.append(subj)
        weak = weak[:MAX_WEAK_TOPICS]
        if not weak:
            logger.info("Idle learner: no weak topics — will do comprehensive A-grade sweep")

        svc = StudyService()
        model = MODELS.get("main", "gemma4:e4b-mlx")
        for topic in weak:
            # Check still idle before each topic (abort if user returned)
            if time.time() - get_last_activity() < IDLE_THRESHOLD_SEC:
                logger.info("Idle learner: user returned, aborting topic %r", topic)
                break
            logger.info("Idle learner: generating flashcards+quiz for weak topic %r", topic)
            try:
                # Flashcards warm RAG + spaced repetition cache
                cards = await svc.generate_flashcards(topic, num_cards=3, model=model)
                # Store to spaced repetition for future due reviews
                if cards:
                    try:
                        from services.advanced_study_service import AdvancedStudyIntelligence
                        adv = AdvancedStudyIntelligence()
                        await adv.add_flashcards_bulk(cards, subject=topic)
                    except Exception as e:
                        logger.debug("Idle learner: bulk add failed for %r: %s", topic, e)
            except Exception as e:
                logger.debug("Idle learner flashcards failed for %r: %s", topic, e)
            try:
                # Quiz warms verified cache
                await svc.generate_quiz(topic, level="medium", num_questions=3, model=model)
            except Exception as e:
                logger.debug("Idle learner quiz failed for %r: %s", topic, e)
            # small pause to yield to any incoming chat
            await asyncio.sleep(2)

        logger.info("Idle learner: weak-topic cycle done for %r", weak)

        # ── Comprehensive A-grade: ensure ALL high school units covered ──
        # After weak topics, systematically cover every NSW S4-S6 topic so
        # student has material for every unit needed for an A.
        for _ in range(COMPREHENSIVE_PER_CYCLE):
            if time.time() - get_last_activity() < IDLE_THRESHOLD_SEC:
                logger.info("Idle learner: user returned, skipping comprehensive")
                break
            next_topic = _get_next_uncovered_topic()
            if not next_topic:
                break
            logger.info("Idle learner: comprehensive A-grade topic %r", next_topic)
            try:
                cards = await svc.generate_flashcards(next_topic, num_cards=3, model=model)
                if cards:
                    try:
                        from services.advanced_study_service import AdvancedStudyIntelligence
                        adv = AdvancedStudyIntelligence()
                        await adv.add_flashcards_bulk(cards, subject=next_topic)
                    except Exception as e:
                        logger.debug("Comprehensive bulk add failed for %r: %s", next_topic, e)
            except Exception as e:
                logger.debug("Comprehensive flashcards failed for %r: %s", next_topic, e)
            try:
                await svc.generate_quiz(next_topic, level="medium", num_questions=3, model=model)
            except Exception as e:
                logger.debug("Comprehensive quiz failed for %r: %s", next_topic, e)
            _mark_comprehensive_covered(next_topic)
            await asyncio.sleep(2)

        prog = _load_comprehensive_progress()
        logger.info("Idle learner: comprehensive progress %d/%d", len(prog.get("covered", [])), prog.get("total") or len(_get_all_highschool_topics()))
    except Exception as e:
        logger.warning("Idle learner cycle failed: %s", e)

# Activity tracker — updated by middleware in main.py
_last_activity = time.time()

def bump_activity():
    global _last_activity
    _last_activity = time.time()

def get_last_activity() -> float:
    return _last_activity

async def _loop():
    logger.info("Idle learner started: threshold=%ds cooldown=%ds", IDLE_THRESHOLD_SEC, COOLDOWN_SEC)
    while True:
        try:
            await asyncio.sleep(60)  # check every minute
            if _should_learn(get_last_activity()):
                await _learn_once()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug("Idle learner loop error: %s", e)
            await asyncio.sleep(60)

def start_idle_learner():
    if not _idle_learner_enabled():
        logger.info("Idle learner disabled (ARIA_IDLE_LEARNER!=1) — no auto flashcards")
        return
    global _learner_task
    if _learner_task and not _learner_task.done():
        return
    try:
        loop = asyncio.get_running_loop()
        _learner_task = loop.create_task(_loop())
        logger.info("Idle learner task created")
    except RuntimeError:
        # No running loop (e.g., during import in tests) — will start on startup event
        pass

def stop_idle_learner():
    global _learner_task
    if _learner_task and not _learner_task.done():
        _learner_task.cancel()
