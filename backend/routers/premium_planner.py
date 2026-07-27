"""Premium Planner router — AI-powered scheduling system."""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import json

router = APIRouter(prefix="/api/premium-planner", tags=["premium-planner"])

_svc = None
def svc():
    global _svc
    if _svc is None:
        from services.premium_planner_service import (
            PremiumPlannerDB, parse_syllabus, detect_available_slots,
            generate_time_blocks, reschedule_session, reschedule_missed_sessions,
            calculate_workload, generate_daily_plan, ai_study_assistant,
            generate_exam_revision, get_analytics_data,
        )
        _svc = {
            "db": PremiumPlannerDB(),
            "parse_syllabus": parse_syllabus,
            "detect_slots": detect_available_slots,
            "generate_blocks": generate_time_blocks,
            "reschedule": reschedule_session,
            "reschedule_missed": reschedule_missed_sessions,
            "workload": calculate_workload,
            "daily_plan": generate_daily_plan,
            "ai_assist": ai_study_assistant,
            "exam_revision": generate_exam_revision,
            "analytics": get_analytics_data,
        }
    return _svc


# ── Syllabus Upload ──────────────────────────────────────────────────────────

@router.post("/upload-syllabus")
async def upload_syllabus(file: UploadFile = File(...)):
    allowed = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".md", ".docx"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    content = await file.read()
    path = os.path.join("uploads", file.filename or "syllabus.pdf")
    os.makedirs("uploads", exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)

    try:
        from services.ai_planner_service import extract_text_from_file
        text = extract_text_from_file(path, max_chars=5000)
    except Exception as e:
        raise HTTPException(400, f"Failed to read: {e}")
    finally:
        try: os.remove(path)
        except: pass

    if not text.strip():
        raise HTTPException(400, "Could not extract text from file.")

    result = svc()["parse_syllabus"](text + "\n\nExtract courses, assignments, exams.")

    # Auto-import courses and assignments
    db = svc()["db"]
    for course in result.get("courses", []):
        db.add_course(course)
    for assignment in result.get("assignments", []):
        db.add_assignment(assignment)
    for exam in result.get("exams", []):
        db.add_exam(exam)

    return {"status": "success", "data": result}


# ── Courses ──────────────────────────────────────────────────────────────────

@router.get("/courses")
async def list_courses():
    return {"courses": svc()["db"].get_courses()}


class CourseCreate(BaseModel):
    name: str
    schedule: str = ""
    lecturer: str = ""


@router.post("/courses")
async def create_course(course: CourseCreate):
    return svc()["db"].add_course(course.model_dump())


# ── Assignments ──────────────────────────────────────────────────────────────

@router.get("/assignments")
async def list_assignments(course_id: str = None):
    return {"assignments": svc()["db"].get_assignments(course_id)}


class AssignmentCreate(BaseModel):
    course_id: str
    title: str
    due_date: str
    estimated_hours: float = 1
    type: str = "assignment"


@router.post("/assignments")
async def create_assignment(a: AssignmentCreate):
    return svc()["db"].add_assignment(a.model_dump())


@router.post("/assignments/{assignment_id}/toggle")
async def toggle_assignment(assignment_id: str):
    db = svc()["db"]
    for a in db.get_assignments():
        if a["id"] == assignment_id:
            return db.update_assignment(assignment_id, {"completed": not a.get("completed")})
    raise HTTPException(404, "Assignment not found")


@router.delete("/assignments/{assignment_id}")
async def delete_assignment(assignment_id: str):
    svc()["db"].delete_assignment(assignment_id)
    return {"status": "deleted"}


# ── Exams ────────────────────────────────────────────────────────────────────

@router.get("/exams")
async def list_exams():
    return {"exams": svc()["db"].get_exams()}


class ExamCreate(BaseModel):
    subject: str
    date: str
    topics: str = ""
    weight: float = 0


@router.post("/exams")
async def create_exam(e: ExamCreate):
    return svc()["db"].add_exam(e.model_dump())


# ── Availability ─────────────────────────────────────────────────────────────

@router.get("/availability")
async def get_availability():
    return {"availability": svc()["db"].get_availability()}


class AvailabilityBlock(BaseModel):
    day: str
    start: str
    end: str
    label: str = "Busy"


@router.post("/availability")
async def set_availability(blocks: list[AvailabilityBlock]):
    svc()["db"].set_availability([b.model_dump() for b in blocks])
    return {"status": "saved", "count": len(blocks)}


# ── Study Sessions ───────────────────────────────────────────────────────────

@router.get("/sessions")
async def get_sessions(date_from: str = None, date_to: str = None):
    return {"sessions": svc()["db"].get_study_sessions(date_from, date_to)}


@router.post("/sessions/{session_id}/toggle")
async def toggle_session(session_id: str):
    db = svc()["db"]
    s = None
    for sess in db.get_study_sessions():
        if sess["id"] == session_id:
            s = sess
            break
    if not s:
        raise HTTPException(404)
    return db.update_session(session_id, {"completed": not s.get("completed")})


@router.post("/sessions/{session_id}/lock")
async def lock_session(session_id: str):
    db = svc()["db"]
    s = None
    for sess in db.get_study_sessions():
        if sess["id"] == session_id:
            s = sess
            break
    if not s:
        raise HTTPException(404)
    return db.update_session(session_id, {"locked": not s.get("locked")})


@router.post("/sessions/move")
async def move_session(session_id: str = Form(...), date: str = Form(...), start_time: str = Form(...)):
    db = svc()["db"]
    return db.update_session(session_id, {"date": date, "start_time": start_time})


@router.post("/reschedule/{session_id}")
async def reschedule(session_id: str):
    availability = svc()["db"].get_availability()
    result = svc()["reschedule"](session_id, availability)
    if result:
        return {"status": "rescheduled", "session": result}
    raise HTTPException(400, "Could not reschedule - no available slots")


@router.post("/reschedule-missed")
async def reschedule_missed():
    availability = svc()["db"].get_availability()
    result = svc()["reschedule_missed"](availability)
    return {"rescheduled": result, "count": len(result)}


# ── AI Time Blocking ─────────────────────────────────────────────────────────

@router.post("/generate-blocks")
async def generate_blocks():
    db = svc()["db"]
    assignments = db.get_assignments()
    exams = db.get_exams()
    availability = db.get_availability()
    settings = db.get_settings()
    result = svc()["generate_blocks"](assignments, exams, availability, settings)
    return {"sessions": result, "count": len(result)}


# ── Workload ─────────────────────────────────────────────────────────────────

@router.get("/workload")
async def workload():
    return svc()["workload"]()


# ── Daily Plan ───────────────────────────────────────────────────────────────

@router.get("/daily-plan")
async def daily_plan():
    return svc()["daily_plan"]()


# ── AI Assistant ─────────────────────────────────────────────────────────────

class AIAssistRequest(BaseModel):
    session_id: str
    query: str


@router.post("/ai-assist")
async def ai_assist(req: AIAssistRequest):
    result = svc()["ai_assist"](req.session_id, req.query)
    return {"response": result}


# ── Exam Revision ────────────────────────────────────────────────────────────

@router.post("/exam-revision/{exam_id}")
async def exam_revision(exam_id: str):
    availability = svc()["db"].get_availability()
    result = svc()["exam_revision"](exam_id, availability)
    return {"sessions": result, "count": len(result)}


# ── Analytics ────────────────────────────────────────────────────────────────

@router.get("/analytics")
async def analytics():
    return svc()["analytics"]()


# ── Notifications ────────────────────────────────────────────────────────────

@router.get("/notifications")
async def get_notifications():
    return {"notifications": svc()["db"].get_notifications()}


@router.post("/notifications/{notification_id}/read")
async def mark_read(notification_id: str):
    svc()["db"].mark_notification_read(notification_id)
    return {"status": "read"}
