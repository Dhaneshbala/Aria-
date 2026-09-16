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


@router.get("/topics")
async def topics():
    return {"topics": svc.list_topics(), "tiers": svc.TIERS}


@router.post("/generate")
async def generate(req: GenerateRequest):
    return await svc.generate_set(req.topic_id, req.tier, req.count)


@router.post("/submit")
async def submit(req: SubmitRequest):
    return svc.record_attempt(req.topic_id, req.tier, req.correct, req.total, req.mistakes)


@router.get("/mastery")
async def mastery():
    return {"mastery": svc.get_mastery()}
