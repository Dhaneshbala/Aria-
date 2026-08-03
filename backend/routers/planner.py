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


# ── Syllabus upload (Shovel-style PDF import) ─────────────────────────────────

@router.post("/upload-syllabus")
async def upload_syllabus(
    file: UploadFile = File(...),
    school_start: str = Form(default="08:30"),
    school_end: str = Form(default="15:00"),
    study_len: str = Form(default="45"),
):
    allowed = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".md"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 20MB)")

    path = os.path.join("uploads", file.filename or "syllabus.pdf")
    os.makedirs("uploads", exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)

    try:
        text = _svc()["extract"](path, max_chars=5000)
    except Exception as e:
        raise HTTPException(400, f"Failed to read file: {e}")
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

    if not text.strip():
        raise HTTPException(400, "Could not extract text from file.")

    from services.ai_planner_service import parse_syllabus
    try:
        raw = parse_syllabus(text)
    except RuntimeError as e:
        raise HTTPException(503, str(e))

    try:
        clean = raw.strip().strip("```json").strip("```").strip()
        data = json.loads(clean)
    except json.JSONDecodeError:
        raise HTTPException(500, detail={"error": "AI returned invalid JSON", "raw": raw})

    return {"status": "success", "data": data}


# ── ICS calendar import ────────────────────────────────────────────────────────

class ImportICSRequest(BaseModel):
    timezone_offset: int = 10  # hours ahead of UTC (default AEST = +10)


@router.post("/import-ics")
async def import_ics(
    file: UploadFile = File(...),
    timezone_offset: str = Form(default="10"),
):
    """Import a .ics file (from Compass/Google Calendar export) into ARIA events.
    Converts UTC times to local time using the given offset (default +10 for AEST)."""
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 10MB)")

    try:
        utc_offset_hours = int(timezone_offset)
    except (ValueError, TypeError):
        utc_offset_hours = 10

    text = content.decode("utf-8", errors="replace")

    # Split into event blocks — handles both proper newlines and single-line files
    # First normalize \r\n to \n, then split on BEGIN:VEVENT / END:VEVENT
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Also insert newlines before known iCal property names so single-line files work
    import re
    text = re.sub(r'\s+(DTSTART|DTEND|SUMMARY|LOCATION|DESCRIPTION|CATEGORIES|UID|STATUS|CLASS|TRANSP|SEQUENCE|DTSTAMP|CREATED|LAST-MODIFIED)\s*:', r'\n\1:', text)

    events = []
    # Split on VEVENT boundaries
    parts = text.split("BEGIN:VEVENT")
    for part in parts[1:]:  # skip everything before first BEGIN:VEVENT
        block = part.split("END:VEVENT")[0]
        current = {}
        for line in block.split("\n"):
            line = line.strip()
            if not line or ":" not in line:
                continue
            key, _, val = line.partition(":")
            key = key.strip()
            if key == "SUMMARY":
                current["label"] = val.strip()
            elif key == "DTSTART":
                current["raw_start"] = val.strip()
            elif key == "DTEND":
                current["raw_end"] = val.strip()
            elif key == "DESCRIPTION":
                current["description"] = val.strip()
            elif key == "LOCATION":
                current["location"] = val.strip()
            elif key == "CATEGORIES":
                current["categories"] = val.strip()
        if current.get("raw_start"):
            events.append(current)

    # Parse raw DTSTART/DTEND into dayIdx + start/end times
    import datetime
    import re

    day_idx_map = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 0}  # Mon=1..Sat=6, Sun=0

    def parse_ical_dt(raw: str) -> datetime.datetime | None:
        """Parse iCal datetime, handling Z suffix (UTC) and raw format."""
        raw = raw.strip()
        if len(raw) < 15:
            return None
        is_utc = raw.endswith("Z")
        # Extract just the datetime part: YYYYMMDDTHHMMSS
        dt_str = raw[:15]
        try:
            dt = datetime.datetime.strptime(dt_str, "%Y%m%dT%H%M%S")
        except ValueError:
            return None
        if is_utc:
            # Convert UTC to local time
            dt = dt + datetime.timedelta(hours=utc_offset_hours)
        return dt

    parsed = []
    seen_keys = set()
    for ev in events:
        dt = parse_ical_dt(ev.get("raw_start", ""))
        if dt is None:
            continue

        dt_end = parse_ical_dt(ev.get("raw_end", ""))
        if dt_end is None:
            dt_end = dt + datetime.timedelta(hours=1)

        wd = dt.weekday()
        day_idx = day_idx_map.get(wd, 0)

        start_h, start_m = dt.hour, dt.minute
        end_h, end_m = dt_end.hour, dt_end.minute
        start_str = f"{start_h:02d}:{start_m:02d}"
        end_str = f"{end_h:02d}:{end_m:02d}"

        label = ev.get("label", "Untitled")
        location = ev.get("location", "")
        description = ev.get("description", "")
        color = _label_to_color(label, ev.get("categories", ""))

        date_str_val = dt.strftime("%Y-%m-%d")
        dedup_key = f"{date_str_val}|{start_str}|{end_str}|{label}"
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        uid = f"ical-{dt.strftime('%Y%m%dT%H%M')}-{hash(label) & 0xFFFF:04x}"

        parsed.append({
            "id": uid,
            "date": dt.strftime("%Y-%m-%d"),
            "dayIdx": day_idx,
            "start": start_str,
            "end": end_str,
            "label": label,
            "color": color,
            "type": "imported",
            "completed": False,
            "location": location,
            "description": description,
        })

    return {"status": "success", "events": parsed, "count": len(parsed)}


def _label_to_color(label: str, categories: str = "") -> str:
    """Map event label/categories to a color."""
    _COLORS = ['#7c6af7', '#4ade80', '#f472b6', '#06b6d4', '#f59e0b', '#ef4444', '#3b82f6', '#a78bfa']
    text = (label + " " + categories).lower()
    color_map = [
        (["math", "calculus", "algebra", "geometry"], "#7c6af7"),
        (["science", "biology", "chemistry", "physics"], "#4ade80"),
        (["english", "writing", "essay", "literature"], "#f472b6"),
        (["history", "social", "geography"], "#06b6d4"),
        (["art", "music", "design"], "#a78bfa"),
        (["sport", "gym", "workout", "exercise"], "#06b6d4"),
        (["lunch", "breakfast", "dinner", "meal", "food"], "#f59e0b"),
        (["sleep", "bed"], "#6366f1"),
        (["work", "job", "shift"], "#ef4444"),
        (["class", "lecture", "tutorial", "lab"], "#7c6af7"),
    ]
    for keywords, color in color_map:
        if any(kw in text for kw in keywords):
            return color
    # Hash label to get consistent color
    return _COLORS[hash(label) % len(_COLORS)]


# ── ICS calendar export ────────────────────────────────────────────────────────

class ExportICSRequest(BaseModel):
    events: list[dict] = []
    calname: str = "ARIA Study Plan"


@router.post("/export-ics")
async def export_ics(req: ExportICSRequest):
    import datetime
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//ARIA//Study Planner//EN",
        f"X-WR-CALNAME:{req.calname}",
    ]
    today = datetime.date.today()
    for ev in req.events:
        day_idx = ev.get("dayIdx", 0)
        start = ev.get("start", "09:00")
        end = ev.get("end", "10:00")
        label = ev.get("label", "Study")
        color = ev.get("color", "#7c6af7")
        # Find next occurrence of this weekday
        days_ahead = (day_idx - today.weekday()) % 7
        if days_ahead == 0:
            s_h, s_m = (int(x) for x in start.split(":"))
            now_m = datetime.datetime.now().hour * 60 + datetime.datetime.now().minute
            if s_h * 60 + s_m <= now_m:
                days_ahead = 7
        ev_date = today + datetime.timedelta(days=days_ahead)
        dt_start = ev_date.strftime("%Y%m%d") + "T" + start.replace(":", "") + "00"
        dt_end = ev_date.strftime("%Y%m%d") + "T" + end.replace(":", "") + "00"
        uid = f"{ev_date.isoformat()}-{label.replace(' ', '-')}-{hash(label) & 0xFFFF:04x}"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTART:{dt_start}",
            f"DTEND:{dt_end}",
            f"SUMMARY:{label}",
            f"CATEGORIES:{ev.get('type', 'course')}",
            f"COLOR:{color}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    ics_body = "\r\n".join(lines)
    from fastapi.responses import Response
    return Response(
        content=ics_body,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="aria_schedule.ics"'},
    )


# ── Cushion calculation ───────────────────────────────────────────────────────

class CushionRequest(BaseModel):
    schedule: list
    homework: list = []
    tests: list = []


@router.post("/cushion")
async def cushion(req: CushionRequest):
    from services.ai_planner_service import calculate_cushion
    result = calculate_cushion(req.schedule, req.homework, req.tests)
    return result


# ── Free slots detection ──────────────────────────────────────────────────────

@router.post("/free-slots")
async def free_slots(req: CushionRequest):
    from services.ai_planner_service import detect_free_slots
    slots = detect_free_slots(req.schedule)
    return {"free_slots": slots, "count": len(slots)}


# ── Study streak ──────────────────────────────────────────────────────────────

@router.post("/streak")
async def streak(req: CushionRequest):
    from services.ai_planner_service import get_study_streak
    result = get_study_streak(req.schedule)
    return result


# ── Event & Task persistence ─────────────────────────────────────────────────

_PLANNER_FILE = os.path.expanduser("~/.aria_data/planner_data.json")


@router.get("/events")
async def load_events():
    """Load saved planner events and tasks."""
    if not os.path.exists(_PLANNER_FILE):
        return {"events": [], "tasks": [], "count": 0}
    try:
        with open(_PLANNER_FILE, "r") as f:
            data = json.load(f)
        return {"events": data.get("events", []), "tasks": data.get("tasks", []), "count": len(data.get("events", []))}
    except Exception:
        return {"events": [], "tasks": [], "count": 0}


class SaveDataRequest(BaseModel):
    events: list[dict] = []
    tasks: list[dict] = []


@router.post("/events")
async def save_events(req: SaveDataRequest):
    """Save planner events and tasks to disk."""
    os.makedirs(os.path.dirname(_PLANNER_FILE), exist_ok=True)
    with open(_PLANNER_FILE, "w") as f:
        json.dump({"events": req.events, "tasks": req.tasks}, f, indent=2)
    return {"status": "saved", "count": len(req.events), "tasks": len(req.tasks)}


# ── Smart notifications ───────────────────────────────────────────────────────

@router.get("/notifications")
async def notifications():
    """Check for things the student should know: upcoming tests, due flashcards."""
    import datetime

    now = datetime.datetime.now()
    today = now.strftime("%Y-%m-%d")

    notices = []

    # 1. Upcoming tests from saved planner tasks (type 'test' or label contains test)
    if os.path.exists(_PLANNER_FILE):
        try:
            with open(_PLANNER_FILE, "r") as f:
                data = json.load(f)

            def is_test_item(item):
                return (
                    item.get("type") == "test"
                    or "test" in (item.get("name", "") or "").lower()
                    or "exam" in (item.get("name", "") or "").lower()
                    or "test" in (item.get("title", "") or "").lower()
                    or "exam" in (item.get("title", "") or "").lower()
                )

            def due_str(item):
                return item.get("dueDate") or item.get("date") or ""

            # Tasks and events both count
            for task in list(data.get("tasks", [])) + list(data.get("events", [])):
                due = due_str(task)
                if not due or not is_test_item(task):
                    continue
                try:
                    d = datetime.datetime.strptime(due, "%Y-%m-%d")
                    days = (d - now).days
                    if 0 <= days <= 3:
                        name = task.get("name") or task.get("title") or "Test"
                        notices.append({
                            "type": "test",
                            "title": f"{name} in {days}d" if days else f"{name} today!",
                            "body": f"Due {due}. Plan revision sessions now.",
                            "severity": "high" if days <= 1 else "medium",
                        })
                except Exception:
                    pass
        except Exception:
            pass

    # 2. Due flashcards from spaced repetition
    try:
        from services.advanced_study_service import AdvancedStudyIntelligence
        svc = AdvancedStudyIntelligence()
        stats = await svc.get_sr_stats()
        if stats.get("due_today", 0) > 0:
            notices.append({
                "type": "flashcards",
                "title": f"{stats['due_today']} flashcards due today",
                "body": "Quick review session — 5 minutes keeps the streak alive!",
                "severity": "low",
            })
    except Exception:
        pass

    return {"notifications": notices, "count": len(notices)}
