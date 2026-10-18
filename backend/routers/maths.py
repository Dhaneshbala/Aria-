"""Maths Accelerator API — selective-level practice sets + mastery."""

from fastapi import APIRouter
from pydantic import BaseModel

from services import maths_accelerator_service as svc

router = APIRouter(prefix="/api/maths", tags=["maths"])


class GenerateRequest(BaseModel):
    topic_id: str = "quadratics"
    tier: str = "selective"
    count: int = 5


class SubmitRequest(BaseModel):
    topic_id: str = "quadratics"
    tier: str = "selective"
    correct: int = 0
    total: int = 1
    mistakes: list[dict] = []
    # Anti-spoofing: when set (normal UI flow today), the set was registered
    # server-side at generate time and scoring is clamped to it.
    session_id: str | None = None
    marks: list[bool] = []


@router.get("/topics")
async def topics():
    return {"topics": svc.list_topics(), "tiers": svc.TIERS}


@router.post("/generate")
async def generate(req: GenerateRequest):
    return await svc.generate_set(req.topic_id, req.tier, req.count)


@router.post("/submit")
async def submit(req: SubmitRequest):
    try:
        if req.session_id:
            # Session-anchored scoring: client-supplied correct/total ignored,
            # attempts derived from the registered set + per-question marks.
            result = svc.record_session_result(req.session_id, req.marks)
        else:
            # Legacy callers (scripts/tests). Can't be verified server-side
            # — kept clamped only. New code should always pass session_id.
            result = svc.record_attempt(
                req.topic_id, req.tier, req.correct, req.total, req.mistakes
            )
    except ValueError as e:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=str(e)) from e
    # Auto-file maths mistakes in the mistake book
    try:
        from services import mistake_service

        for m in req.mistakes or []:
            if isinstance(m, dict) and not m.get("correct", True):
                mistake_service.record(
                    question=m.get("q") or m.get("question", ""),
                    correct_answer=m.get("answer", ""),
                    subject="maths",
                    topic=req.topic_id,
                    source="maths",
                )
    except Exception:
        pass
    return result


@router.get("/mastery")
async def mastery():
    return {"mastery": svc.get_mastery()}
