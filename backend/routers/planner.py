"""
AI Study Planner router — homework scheduling, assessment analysis, ICS export.
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import json

router = APIRouter(prefix="/api/planner", tags=["planner"])

_planner = None


def _svc():
    global _planner
    if _planner is None:
        from services.ai_planner_service import (
            analyze_assessment, refine_plan, build_homework_schedule,
            create_ics_content, create_ics_from_schedule, extract_text_from_file,
        )
        _planner = {
            "analyze": analyze_assessment,
            "refine": refine_plan,
            "build_schedule": build_homework_schedule,
            "ics": create_ics_content,
            "ics_schedule": create_ics_from_schedule,
            "extract": extract_text_from_file,
        }
    return _planner


class HomeworkItem(BaseModel):
    subject: str
    task: str
    due_date: str
    estimated_minutes: int = 30
    priority: str = "medium"  # low, medium, high


class TestItem(BaseModel):
    subject: str
    date: str
    topics: str = ""


class FullScheduleRequest(BaseModel):
    homework: list[HomeworkItem] = []
    tests: list[TestItem] = []
    school_start: str = "08:30"
    school_end: str = "15:00"
    study_len: int = 45
    activities: list[str] = []
    sleep_time: str = "22:00"
    days_ahead: int = 14


class RefineRequest(BaseModel):
    plan: list
    feedback: str


# ── Assessment analysis (upload PDF) ────────────────────────────────────────────

@router.post("/analyse")
async def analyse_assessment(
    file: UploadFile = File(...),
    school_start: str = Form(default="08:30"),
    school_end: str = Form(default="15:00"),
    study_len: str = Form(default="45"),
):
    allowed = {".pdf", ".png", ".jpg", ".jpeg"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed:
        raise HTTPException(400, f"Unsupported file type: {ext}. Use PDF, PNG, or JPG.")

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 20MB)")

    path = os.path.join("uploads", file.filename or "upload.pdf")
    os.makedirs("uploads", exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)

    try:
        text = _svc()["extract"](path)
    except Exception as e:
        raise HTTPException(400, f"Failed to read file: {e}")
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

    if not text.strip():
        raise HTTPException(400, "Could not extract text from file.")

    try:
        raw = _svc()["analyze"](text, school_start, school_end, study_len)
    except RuntimeError as e:
        raise HTTPException(503, str(e))

    try:
        clean = raw.strip().strip("```json").strip("```").strip()
        tasks = json.loads(clean)
    except json.JSONDecodeError:
        raise HTTPException(500, detail={"error": "AI returned invalid JSON", "raw": raw})

    ics_content = _svc()["ics"](tasks)
    return {"status": "success", "study_plan": tasks, "ics": ics_content}


# ── Full homework schedule ──────────────────────────────────────────────────────

@router.post("/schedule")
async def full_schedule(req: FullScheduleRequest):
    homework = [h.model_dump() for h in req.homework]
    tests = [t.model_dump() for t in req.tests]

    try:
        schedule = _svc()["build_schedule"](
            homework=homework,
            tests=tests,
            school_start=req.school_start,
            school_end=req.school_end,
            study_len=req.study_len,
            activities=req.activities,
            sleep_time=req.sleep_time,
            days_ahead=req.days_ahead,
        )
    except (ValueError, KeyError) as e:
        raise HTTPException(400, f"Invalid input: {e}")

    ics_content = _svc()["ics_schedule"](schedule)
    return {"status": "success", "schedule": schedule, "ics": ics_content}


# ── Refine plan ─────────────────────────────────────────────────────────────────

@router.post("/refine")
async def refine(req: RefineRequest):
    if not req.plan or not isinstance(req.plan, list):
        raise HTTPException(400, "plan must be a non-empty list")
    if not req.feedback:
        raise HTTPException(400, "feedback is required")

    try:
        raw = _svc()["refine"](req.plan, req.feedback)
    except RuntimeError as e:
        raise HTTPException(503, str(e))

    try:
        clean = raw.strip().strip("```json").strip("```").strip()
        updated = json.loads(clean)
    except json.JSONDecodeError:
        raise HTTPException(500, detail={"error": "AI returned invalid JSON", "raw": raw})

    ics_content = _svc()["ics"](updated)
    return {"status": "success", "study_plan": updated, "ics": ics_content}


# ── Quick add homework to existing schedule ─────────────────────────────────────

class QuickAddRequest(BaseModel):
    schedule: list
    subject: str
    task: str
    due_date: str
    estimated_minutes: int = 30
    priority: str = "medium"
    study_len: int = 45


@router.post("/add-homework")
async def add_homework(req: QuickAddRequest):
    if not req.schedule:
        raise HTTPException(400, "schedule is required")
    if not req.subject or not req.task or not req.due_date:
        raise HTTPException(400, "subject, task, and due_date are required")

    from services.ai_planner_service import add_homework_to_schedule
    updated = add_homework_to_schedule(
        schedule=req.schedule,
        homework_item={
            "subject": req.subject,
            "task": req.task,
            "due_date": req.due_date,
            "estimated_minutes": req.estimated_minutes,
            "priority": req.priority,
        },
        study_len=req.study_len,
    )

    ics_content = _svc()["ics_schedule"](updated)
    return {"status": "success", "schedule": updated, "ics": ics_content}
