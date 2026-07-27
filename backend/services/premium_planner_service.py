"""Premium AI Study Planner — intelligent scheduling system."""
import json
import os
import uuid
import re
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3:8b"
_session = requests.Session()

DATA_DIR = Path.home() / ".aria_data"
PLANNER_DIR = DATA_DIR / "premium_planner"
PLANNER_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_OPTIONS = {
    "num_gpu": 99, "num_thread": 4, "num_batch": 512,
    "num_predict": 2000, "temperature": 0.2, "top_k": 20,
    "top_p": 0.8, "num_ctx": 4096,
}


def _ask(prompt: str) -> str:
    resp = _session.post(OLLAMA_URL, json={"model": MODEL, "prompt": prompt, "stream": False, "options": OLLAMA_OPTIONS}, timeout=300)
    resp.raise_for_status()
    return resp.json().get("response", "")


def _time_to_min(t: str) -> int:
    h, m = map(int, t.split(":"))
    return h * 60 + m


def _min_to_time(m: int) -> str:
    return f"{m // 60 % 24:02d}:{m % 60:02d}"


# ═══════════════════════════════════════════════════════════════════
# DATA LAYER
# ═══════════════════════════════════════════════════════════════════

class PremiumPlannerDB:
    def __init__(self):
        self._tables = ["courses", "assignments", "exams", "availability",
                        "study_sessions", "notifications", "analytics", "settings"]
        self._data = {}
        self._load()

    def _path(self, table: str) -> Path:
        return PLANNER_DIR / f"{table}.json"

    def _load(self):
        for t in self._tables:
            p = self._path(t)
            if p.exists():
                try:
                    self._data[t] = json.loads(p.read_text())
                except Exception:
                    self._data[t] = []
            else:
                self._data[t] = []
                self._save(t)

    def _save(self, table: str):
        self._path(table).write_text(json.dumps(self._data[table], indent=2, default=str))

    # ── Courses ────────────────────────────────────────────────────
    def get_courses(self):
        return self._data["courses"]

    def add_course(self, course: dict) -> dict:
        c = {"id": str(uuid.uuid4())[:8], "color": self._next_color(), **course}
        self._data["courses"].append(c)
        self._save("courses")
        return c

    def _next_color(self) -> str:
        colors = ["#7c6af7", "#06b6d4", "#10b981", "#f59e0b", "#f472b6", "#fb923c", "#22d3ee", "#34d399"]
        used = [c.get("color") for c in self._data["courses"]]
        for col in colors:
            if col not in used:
                return col
        return colors[0]

    # ── Assignments ────────────────────────────────────────────────
    def get_assignments(self, course_id: str = None):
        if course_id:
            return [a for a in self._data["assignments"] if a.get("course_id") == course_id]
        return self._data["assignments"]

    def add_assignment(self, assignment: dict) -> dict:
        a = {"id": str(uuid.uuid4())[:8], "completed": False, "created_at": datetime.now().isoformat(), **assignment}
        self._data["assignments"].append(a)
        self._save("assignments")
        return a

    def update_assignment(self, assignment_id: str, updates: dict):
        for a in self._data["assignments"]:
            if a["id"] == assignment_id:
                a.update(updates)
                self._save("assignments")
                return a
        return None

    def delete_assignment(self, assignment_id: str):
        self._data["assignments"] = [a for a in self._data["assignments"] if a["id"] != assignment_id]
        self._save("assignments")

    # ── Exams ──────────────────────────────────────────────────────
    def get_exams(self):
        return self._data["exams"]

    def add_exam(self, exam: dict) -> dict:
        e = {"id": str(uuid.uuid4())[:8], **exam}
        self._data["exams"].append(e)
        self._save("exams")
        return e

    # ── Availability (weekly template) ──────────────────────────────
    def get_availability(self):
        return self._data["availability"]

    def set_availability(self, blocks: list):
        self._data["availability"] = blocks
        self._save("availability")

    # ── Study Sessions ─────────────────────────────────────────────
    def get_study_sessions(self, date_from: str = None, date_to: str = None):
        sessions = self._data["study_sessions"]
        if date_from:
            sessions = [s for s in sessions if s.get("date", "") >= date_from]
        if date_to:
            sessions = [s for s in sessions if s.get("date", "") <= date_to]
        return sorted(sessions, key=lambda s: (s.get("date", ""), s.get("start_time", "")))

    def add_study_session(self, session: dict) -> dict:
        s = {"id": str(uuid.uuid4())[:8], "completed": False, "locked": False, **session}
        self._data["study_sessions"].append(s)
        self._save("study_sessions")
        return s

    def update_session(self, session_id: str, updates: dict):
        for s in self._data["study_sessions"]:
            if s["id"] == session_id:
                s.update(updates)
                self._save("study_sessions")
                return s
        return None

    def delete_session(self, session_id: str):
        self._data["study_sessions"] = [s for s in self._data["study_sessions"] if s["id"] != session_id]
        self._save("study_sessions")

    # ── Notifications ──────────────────────────────────────────────
    def get_notifications(self):
        return sorted(self._data["notifications"], key=lambda n: n.get("created_at", ""), reverse=True)

    def add_notification(self, notification: dict):
        n = {"id": str(uuid.uuid4())[:8], "read": False, "created_at": datetime.now().isoformat(), **notification}
        self._data["notifications"].append(n)
        self._save("notifications")

    def mark_notification_read(self, notification_id: str):
        for n in self._data["notifications"]:
            if n["id"] == notification_id:
                n["read"] = True
                self._save("notifications")
                break

    # ── Analytics ──────────────────────────────────────────────────
    def get_analytics(self):
        return self._data["analytics"]

    def save_analytics(self, analytics: dict):
        self._data["analytics"].append({**analytics, "recorded_at": datetime.now().isoformat()})
        self._save("analytics")

    # ── Settings ───────────────────────────────────────────────────
    def get_settings(self):
        if not self._data["settings"]:
            return {"min_study_block": 25, "school_start": "08:30", "school_end": "15:00",
                    "sleep_start": "22:00", "sleep_end": "07:00", "pomodoro_focus": 25,
                    "pomodoro_break": 5, "generated_today": ""}
        return self._data["settings"][-1]

    def save_settings(self, settings: dict):
        self._data["settings"].append(settings)
        self._save("settings")


_db = PremiumPlannerDB()


# ═══════════════════════════════════════════════════════════════════
# SYLLABUS PARSING (AI)
# ═══════════════════════════════════════════════════════════════════

def parse_syllabus(text: str) -> dict:
    today = datetime.today().strftime("%A %d %B %Y")
    prompt = f"""You are an academic scheduler. Today is {today}.

Extract all courses, assignments, exams, and recurring classes from this syllabus.
Output ONLY valid JSON with this structure:
{{
  "courses": [{{"name": "...", "lecturer": "", "schedule": "Mon 10:00-11:00", "color": "#7c6af7"}}],
  "assignments": [{{"title": "...", "course": "...", "due_date": "YYYY-MM-DD", "estimated_hours": 5, "type": "essay|problem_set|reading|project|presentation"}}],
  "exams": [{{"subject": "...", "date": "YYYY-MM-DD", "topics": "...", "weight": 30}}],
  "summary": "..."
}}

SYLLABUS:
{text[:4000]}"""
    raw = _ask(prompt)
    clean = raw.strip().strip("```json").strip("```").strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        return {"courses": [], "assignments": [], "exams": [], "summary": "Could not parse syllabus automatically."}


# ═══════════════════════════════════════════════════════════════════
# TIME BLOCKING ENGINE
# ═══════════════════════════════════════════════════════════════════

def detect_available_slots(availability: list, date_from: str, date_to: str) -> list:
    """Find all available time slots between availability blocks."""
    slots = []
    current = datetime.strptime(date_from, "%Y-%m-%d")
    end = datetime.strptime(date_to, "%Y-%m-%d")
    while current <= end:
        day_name = current.strftime("%A")
        day_blocks = [b for b in availability if b.get("day") == day_name]
        day_blocks.sort(key=lambda b: b.get("start", "00:00"))

        # Fill gaps between blocks as available
        prev_end = "00:00"
        for block in day_blocks:
            block_start = block.get("start", "00:00")
            if block_start > prev_end:
                free_min = _time_to_min(block_start) - _time_to_min(prev_end)
                if free_min >= 15:
                    slots.append({
                        "date": current.strftime("%Y-%m-%d"),
                        "day": day_name,
                        "start": prev_end,
                        "end": block_start,
                        "duration_min": free_min,
                        "type": "available",
                    })
            # Update prev_end if this block ends later
            block_end = block.get("end", "00:00")
            if block_end > prev_end:
                prev_end = block_end

        # After last block until 23:00
        remaining = _time_to_min("23:00") - _time_to_min(prev_end)
        if remaining >= 15:
            slots.append({
                "date": current.strftime("%Y-%m-%d"),
                "day": day_name,
                "start": prev_end,
                "end": "23:00",
                "duration_min": remaining,
                "type": "available",
            })
        current += timedelta(days=1)
    return slots


def generate_time_blocks(
    assignments: list,
    exams: list,
    availability: list,
    settings: dict,
) -> list:
    """AI generates time-blocked study sessions from assignments and availability."""
    today = datetime.today().strftime("%A %d %B %Y")
    min_block = settings.get("min_study_block", 25)

    prompt = f"""You are an expert study scheduler. Today is {today}.

Create a detailed study schedule that turns every assignment deadline into DO dates.
Rules:
- Break each assignment into multiple {min_block}-min sessions spread across available days
- Never schedule during busy blocks
- Prioritise: exams > urgent assignments > long-term assignments
- Leave at least 1 free block per day
- Don't schedule after 21:00
- Spread work evenly — don't overload any single day

ASSIGNMENTS:
{json.dumps(assignments, indent=2)}

EXAMS:
{json.dumps(exams, indent=2)}

AVAILABLE TIME SLOTS (free study time):
{json.dumps(availability, indent=2)}

Output ONLY a JSON array of study sessions:
[
  {{
    "date": "YYYY-MM-DD",
    "start_time": "HH:MM",
    "end_time": "HH:MM",
    "course": "Course Name",
    "assignment": "Assignment Title",
    "task": "Specific task description",
    "duration_min": {min_block},
    "type": "study|review|exam_prep"
  }}
]"""

    raw = _ask(prompt)
    clean = raw.strip().strip("```json").strip("```").strip()
    try:
        sessions = json.loads(clean)
    except json.JSONDecodeError:
        sessions = []

    # Persist sessions
    saved = []
    for s in sessions:
        saved.append(_db.add_study_session(s))
    return saved


# ═══════════════════════════════════════════════════════════════════
# SMART RESCHEDULING
# ═══════════════════════════════════════════════════════════════════

def reschedule_session(
    session_id: str,
    availability: list,
) -> Optional[dict]:
    """Find the next best time for a missed/cancelled session."""
    session = None
    for s in _db.get_study_sessions():
        if s["id"] == session_id:
            session = s
            break
    if not session:
        return None

    session_date = session.get("date", "")
    duration = session.get("duration_min", 45)

    # Find available slots after the original date
    available = detect_available_slots(
        availability,
        session_date,
        (datetime.strptime(session_date, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d"),
    )

    # Find first slot that fits the duration
    for slot in available:
        if slot["duration_min"] >= duration:
            new_start = slot["start"]
            new_end = _min_to_time(_time_to_min(new_start) + duration)
            updated = _db.update_session(session_id, {
                "date": slot["date"],
                "start_time": new_start,
                "end_time": new_end,
                "rescheduled": True,
                "original_date": session_date,
            })
            _db.add_notification({
                "type": "rescheduled",
                "message": f"Session '{session.get('assignment', 'Study')}' rescheduled to {slot['date']} at {new_start}",
            })
            return updated

    _db.add_notification({
        "type": "warning",
        "message": f"No available slot found to reschedule '{session.get('assignment', 'Study')}' within 7 days",
    })
    return None


def reschedule_missed_sessions(availability: list) -> list:
    """Auto-reschedule all incomplete past sessions."""
    today = datetime.today().strftime("%Y-%m-%d")
    missed = [s for s in _db.get_study_sessions() if s.get("date", "") < today and not s.get("completed") and not s.get("rescheduled")]
    rescheduled = []
    for s in missed:
        new = reschedule_session(s["id"], availability)
        if new:
            rescheduled.append(new)
    return rescheduled


# ═══════════════════════════════════════════════════════════════════
# WORKLOAD PREDICTOR
# ═══════════════════════════════════════════════════════════════════

def calculate_workload() -> dict:
    """Calculate workload statistics for the current week."""
    today = datetime.today()
    week_start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
    week_end = (today + timedelta(days=6 - today.weekday())).strftime("%Y-%m-%d")

    # Hours remaining (assignments not completed)
    assignments = _db.get_assignments()
    remaining_hours = sum(a.get("estimated_hours", 1) for a in assignments if not a.get("completed"))

    # Hours already studied this week
    sessions = _db.get_study_sessions(week_start, week_end)
    studied_min = sum(s.get("duration_min", 0) for s in sessions if s.get("completed"))
    studied_hours = round(studied_min / 60, 1)

    # Available hours this week (from availability)
    availability = _db.get_availability()
    available_slots = detect_available_slots(availability, week_start, week_end)
    available_hours = round(sum(a["duration_min"] for a in available_slots) / 60, 1)

    # Remaining sessions this week
    remaining_sessions = sum(1 for s in sessions if not s.get("completed"))

    # Risk level
    if remaining_hours > available_hours * 1.5:
        risk = "overloaded"
    elif remaining_hours > available_hours:
        risk = "busy"
    else:
        risk = "on_track"

    return {
        "remaining_hours": remaining_hours,
        "studied_hours": studied_hours,
        "available_hours": available_hours,
        "remaining_sessions": remaining_sessions,
        "completion_rate": round(
            (sum(1 for s in sessions if s.get("completed")) / max(1, len(sessions))) * 100
        ),
        "risk": risk,
        "week_start": week_start,
        "week_end": week_end,
    }


# ═══════════════════════════════════════════════════════════════════
# DAILY STUDY PLAN
# ═══════════════════════════════════════════════════════════════════

def generate_daily_plan() -> dict:
    """Generate today's study plan with priorities and recommendations."""
    today = datetime.today().strftime("%Y-%m-%d")
    day_name = datetime.today().strftime("%A")

    today_sessions = [s for s in _db.get_study_sessions(today, today) if not s.get("completed")]
    assignments = _db.get_assignments()
    exams = _db.get_exams()

    # Find urgent items
    urgent = [a for a in assignments if not a.get("completed") and a.get("due_date", "") == today]

    priority_courses = []
    for exam in exams:
        if exam.get("date", "") >= today:
            priority_courses.append(exam.get("subject", ""))

    plan = {
        "date": today,
        "day": day_name,
        "sessions": today_sessions,
        "urgent_items": urgent,
        "total_study_min": sum(s.get("duration_min", 0) for s in today_sessions),
        "priority_courses": list(set(priority_courses)),
        "recommended_breaks": max(1, len(today_sessions) // 2),
    }

    # AI recommendations
    workload = calculate_workload()
    recs = []
    if workload["risk"] == "overloaded":
        recs.append("Reduce workload today — focus on high-priority items only")
        recs.append("Move low-priority assignments to next week")
    elif workload["risk"] == "busy":
        recs.append("Start with the most urgent task first")
        recs.append("Consider a longer study block for deep work")
    else:
        recs.append("You're on track — maintain your current pace")
        if len(today_sessions) <= 2:
            recs.append("Add a review session for upcoming exams")

    if priority_courses:
        recs.append(f"Prioritise revision for: {', '.join(priority_courses[:3])}")

    plan["recommendations"] = recs
    return plan


# ═══════════════════════════════════════════════════════════════════
# AI STUDY ASSISTANT
# ═══════════════════════════════════════════════════════════════════

def ai_study_assistant(session_id: str, query: str) -> str:
    """Answer AI questions about a specific study session."""
    session = None
    for s in _db.get_study_sessions():
        if s["id"] == session_id:
            session = s
            break

    if not session:
        return "Session not found."

    course = session.get("course", "Unknown")
    assignment = session.get("assignment", "Unknown")
    task = session.get("task", "")

    prompt = f"""You are an AI study assistant helping a student with their current study session.

COURSE: {course}
ASSIGNMENT: {assignment}
TASK: {task}

Student asks: {query}

Provide a helpful, detailed response. If they ask for explanation, explain clearly.
If they ask for flashcards or quiz, generate them. If they ask for summary, summarise."""

    return _ask(prompt)


# ═══════════════════════════════════════════════════════════════════
# EXAM REVISION SCHEDULE
# ═══════════════════════════════════════════════════════════════════

def generate_exam_revision(exam_id: str, availability: list) -> list:
    """Generate a spaced repetition revision schedule for an exam."""
    exam = None
    for e in _db.get_exams():
        if e["id"] == exam_id:
            exam = e
            break
    if not exam:
        return []

    today = datetime.today()
    exam_date = datetime.strptime(exam["date"], "%Y-%m-%d")
    days_until = (exam_date - today).days

    if days_until <= 0:
        return []

    prompt = f"""You are an exam revision scheduler.

EXAM: {exam.get("subject", "Unknown")}
TOPICS: {exam.get("topics", "All topics")}
DAYS UNTIL EXAM: {days_until}

Create a revision schedule using spaced repetition:
- First 30%: Learn/understand core concepts
- Next 40%: Practice with questions
- Next 20%: Review weak areas
- Last 10%: Final review

Available study slots:
{json.dumps(availability[:20], indent=2)}

Output ONLY a JSON array:
[{{"date": "YYYY-MM-DD", "start_time": "HH:MM", "end_time": "HH:MM", "phase": "Learn|Practice|Review|Final", "topic": "...", "activity": "..."}}]
Max 2 sessions per day."""
    raw = _ask(prompt)
    clean = raw.strip().strip("```json").strip("```").strip()
    try:
        sessions = json.loads(clean)
    except json.JSONDecodeError:
        sessions = []

    # Mark sessions as exam prep
    for s in sessions:
        s["course"] = exam.get("subject", "Unknown")
        s["assignment"] = f"Revision: {exam.get('subject', 'Unknown')}"
        s["type"] = "exam_prep"
        s["exam_id"] = exam_id
        _db.add_study_session(s)

    return sessions


# ═══════════════════════════════════════════════════════════════════
# STUDY ANALYTICS
# ═══════════════════════════════════════════════════════════════════

def get_analytics_data() -> dict:
    """Get comprehensive analytics for the dashboard."""
    today = datetime.today()
    month_start = today.replace(day=1).strftime("%Y-%m-%d")
    month_end = (today.replace(day=28) + timedelta(days=7)).strftime("%Y-%m-%d")

    sessions = _db.get_study_sessions(month_start, month_end)
    assignments = _db.get_assignments()

    completed_sessions = [s for s in sessions if s.get("completed")]
    total_min = sum(s.get("duration_min", 0) for s in completed_sessions)

    # Per-subject breakdown
    subjects = {}
    for s in completed_sessions:
        course = s.get("course", "Unknown")
        if course not in subjects:
            subjects[course] = {"minutes": 0, "sessions": 0}
        subjects[course]["minutes"] += s.get("duration_min", 0)
        subjects[course]["sessions"] += 1

    # Streak
    streak = 0
    check = today
    while True:
        day_str = check.strftime("%Y-%m-%d")
        day_sessions = [s for s in sessions if s.get("date") == day_str and s.get("completed")]
        if day_sessions:
            streak += 1
            check -= timedelta(days=1)
        else:
            break

    # Completion rate
    total = len(assignments)
    done = sum(1 for a in assignments if a.get("completed"))
    completion_rate = round((done / max(1, total)) * 100)

    workload = calculate_workload()

    return {
        "total_minutes": total_min,
        "total_hours": round(total_min / 60, 1),
        "total_sessions": len(completed_sessions),
        "streak": streak,
        "completion_rate": completion_rate,
        "subjects": subjects,
        "workload": workload,
        "month": today.strftime("%B %Y"),
    }
