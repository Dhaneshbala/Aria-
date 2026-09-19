"""Maths Accelerator API — selective-level practice sets + mastery."""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from services import maths_accelerator_service as svc

router = APIRouter(prefix="/api/maths", tags=["maths"])


class GenerateRequest(BaseModel):
    topic_id: str = Field(default="quadratics", max_length=100)
    tier: str = Field(default="selective", pattern="^(foundation|selective|extension)$")
    count: int = Field(default=5, ge=1, le=20)


class SubmitRequest(BaseModel):
    topic_id: str = Field(default="quadratics", max_length=100)
    tier: str = Field(default="selective", pattern="^(foundation|selective|extension)$")
    correct: int = Field(default=0, ge=0)
    total: int = Field(default=1, ge=1)
    mistakes: list[dict] = Field(default_factory=list, max_length=50)


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
