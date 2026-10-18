"""Syllabus tracker API — NSW outcomes + student progress."""

from fastapi import APIRouter
from pydantic import BaseModel

from services import syllabus_service as syllabus

router = APIRouter(prefix="/api/v2/syllabus", tags=["syllabus"])


class ProgressRequest(BaseModel):
    kla: str = ""
    stage: str = ""
    code: str = ""
    status: str = "none"


@router.get("/overview")
async def syllabus_overview(stage: str | None = None):
    return syllabus.overview(stage)


@router.get("/outcomes")
async def syllabus_outcomes(kla: str, stage: str):
    return {
        "kla": kla,
        "stage": stage,
        "outcomes": syllabus.outcomes_with_status(kla, stage),
    }


@router.post("/progress")
async def set_progress(req: ProgressRequest):
    result = syllabus.set_status(req.kla, req.stage, req.code, req.status)
    if "error" in result:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=400, content=result)
    return result
