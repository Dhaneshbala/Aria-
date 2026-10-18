"""Mistake book API — record wrong answers, drill them to mastery."""

from fastapi import APIRouter
from pydantic import BaseModel

from services import mistake_service as mistakes

router = APIRouter(prefix="/api/v2/mistakes", tags=["mistakes"])


class RecordRequest(BaseModel):
    question: str = ""
    correct_answer: str = ""
    given_answer: str = ""
    subject: str = "general"
    topic: str = ""
    source: str = "quiz"


class ReviewRequest(BaseModel):
    correct: bool = False


@router.post("")
async def record_mistake(req: RecordRequest):
    item = mistakes.record(
        question=req.question,
        correct_answer=req.correct_answer,
        given_answer=req.given_answer,
        subject=req.subject,
        topic=req.topic,
        source=req.source,
    )
    if item is None:
        return {"recorded": False}
    return {"recorded": True, "mistake": item}


@router.get("/due")
async def due_mistakes(limit: int = 20):
    return {"mistakes": mistakes.due(limit), "stats": mistakes.stats()}


@router.post("/{item_id}/review")
async def review_mistake(item_id: str, req: ReviewRequest):
    item = mistakes.review(item_id, req.correct)
    if item is None:
        return {"error": "mistake not found or already mastered"}
    return {"mistake": item, "stats": mistakes.stats()}


@router.get("/stats")
async def mistake_stats():
    return mistakes.stats()
