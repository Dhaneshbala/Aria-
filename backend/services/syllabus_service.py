"""Syllabus tracker — NSW outcomes with per-student progress.

Curriculum content comes from NSWCurriculumService (read-only); this module
stores only the student's status per outcome: none | learning | confident.
"""

import json
import logging
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

STATUSES = ("none", "learning", "confident")

# Module-level lock: status writes come from the UI and chat flows; without
# it concurrent updates race (last-writer-wins) and progress rows vanish.
_LOCK = threading.RLock()


def _data_file() -> Path:
    from models.database import DATA_DIR

    return DATA_DIR / "syllabus_progress.json"


def _load() -> dict:
    try:
        p = _data_file()
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception as e:
        logger.debug("Syllabus progress load failed: %s", e)
    return {"progress": {}}


def _save(data: dict) -> None:
    try:
        p = _data_file()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
    except Exception as e:
        logger.debug("Syllabus progress save failed: %s", e)


def _key(kla: str, stage: str, code: str) -> str:
    return f"{kla}:{stage}:{code}"


def student_stage() -> str:
    """Stage for the configured student grade (defaults S4)."""
    try:
        from models.database import get_config
        from services.nsw_curriculum_service import get_curriculum_service

        grade = get_config().get("student_grade", "Year 7")
        stage = get_curriculum_service().get_stage_for_grade(grade)
        if stage:
            return stage
    except Exception as e:
        logger.debug("Stage lookup failed: %s", e)
    return "S4"


def set_status(kla: str, stage: str, code: str, status: str) -> dict:
    if status not in STATUSES:
        return {"error": f"status must be one of {STATUSES}"}
    if not (kla and stage and code):
        return {"error": "kla, stage and code are required"}
    with _LOCK:
        data = _load()
        data["progress"][_key(kla, stage, code)] = {
            "status": status,
            "updated_at": time.time(),
        }
        _save(data)
    return {"ok": True}


def outcomes_with_status(kla: str, stage: str) -> list[dict]:
    """Curriculum outcomes merged with saved statuses."""
    from services.nsw_curriculum_service import get_curriculum_service

    svc = get_curriculum_service()
    codes = svc.get_outcomes(kla, stage) or []
    saved = _load()["progress"]
    return [
        {
            "code": code,
            "status": saved.get(_key(kla, stage, code), {}).get("status", "none"),
        }
        for code in codes
    ]


def overview(stage: str | None = None) -> dict:
    """Per-KLA coverage for a stage (defaults to the student's)."""
    from services.nsw_curriculum_service import get_curriculum_service

    svc = get_curriculum_service()
    stage = stage or student_stage()
    klas = svc.get_klas() or {}
    saved = _load()["progress"]
    subjects = []
    for kla in sorted(klas):
        codes = svc.get_outcomes(kla, stage) or []
        counts = {"none": 0, "learning": 0, "confident": 0}
        for code in codes:
            st = saved.get(_key(kla, stage, code), {}).get("status", "none")
            counts[st if st in counts else "none"] += 1
        total = len(codes)
        subjects.append(
            {
                "kla": kla,
                "name": klas[kla].get("name", kla)
                if isinstance(klas[kla], dict)
                else str(klas[kla]),
                "stage": stage,
                "total": total,
                "confident": counts["confident"],
                "learning": counts["learning"],
                "pct": round(100 * counts["confident"] / total) if total else 0,
            }
        )
    return {"stage": stage, "subjects": subjects}
