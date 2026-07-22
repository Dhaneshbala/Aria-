"""
AI Study Planner — full homework-aware scheduling.
Takes all your homework, tests, and commitments and builds a custom daily timetable.
"""
import os
import re
import json
import uuid
import requests
from datetime import datetime, timedelta


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:3b"
_session = requests.Session()

OLLAMA_OPTIONS = {
    "num_gpu": 99,
    "num_thread": 4,
    "num_batch": 512,
    "num_predict": 1500,
    "temperature": 0.2,
    "top_k": 20,
    "top_p": 0.8,
    "num_ctx": 4096,
}


def _ask_ollama(prompt: str) -> str:
    resp = _session.post(
        OLLAMA_URL,
        json={"model": MODEL, "prompt": prompt, "stream": False, "options": OLLAMA_OPTIONS},
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json().get("response", "")


# ── PDF / Image text extraction ─────────────────────────────────────────────────

def extract_text_from_file(file_path: str, max_chars: int = 3000) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        text = _extract_native_pdf(file_path)
    elif ext in (".png", ".jpg", ".jpeg"):
        text = _extract_image(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text).strip()
    return text[:max_chars] if len(text) > max_chars else text


def _extract_native_pdf(path: str) -> str:
    try:
        import fitz
        doc = fitz.open(path)
        text = "\n".join(page.get_text("text") for page in doc)
        doc.close()
        if len(text.strip()) > 100:
            return text
    except Exception:
        pass
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            text = "\n".join(t or "" for p in pdf.pages if (t := p.extract_text()))
        return text
    except Exception:
        raise RuntimeError("No PDF library available")


def _extract_image(path: str) -> str:
    from PIL import Image
    import pytesseract
    return pytesseract.image_to_string(Image.open(path), config="--psm 6 --oem 1")


# ── Assessment analysis (upload PDF) ────────────────────────────────────────────

def analyze_assessment(text: str, school_start="08:30", school_end="15:00", study_len="45") -> str:
    text = text.strip()[:2000]
    today = datetime.today()
    prompt = f"""You are an expert student study coach. Today is {today.strftime("%A %d %B %Y")}.

ASSESSMENT NOTIFICATION:
{text}

Create a day-by-day study plan. Rules:
- Extract subject, date, every topic/concept listed
- Split topics evenly across available days (1-2 topics per day)
- Each day: specific task telling the student EXACTLY what to do
- Phase structure: first 30% LEARN, middle 40% PRACTISE, next 20% REVISE, last day FINAL REVIEW
- Never schedule during school hours ({school_start}–{school_end})
- Each session {study_len} minutes
- Weekends: up to 2 sessions if test is close

OUTPUT: ONLY a valid JSON array. Each object:
  day, date (YYYY-MM-DD), subject, topic, task, phase, duration"""

    return _ask_ollama(prompt)


# ── Full homework schedule ──────────────────────────────────────────────────────

def build_homework_schedule(
    homework: list,
    tests: list,
    school_start: str = "08:30",
    school_end: str = "15:00",
    study_len: int = 45,
    activities: list = None,
    sleep_time: str = "22:00",
    days_ahead: int = 14,
) -> list:
    """
    Build a complete daily timetable for all homework + tests.
    
    homework: [{subject, task, due_date, estimated_minutes, priority}]
    tests: [{subject, date, topics}]
    activities: ["Monday Soccer", "Wednesday Music"]
    """
    today = datetime.today()
    schedule = []

    for day_offset in range(days_ahead):
        current_date = today + timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")
        day_name = current_date.strftime("%A")
        is_weekend = current_date.weekday() >= 5

        # Collect what's due on this day
        due_today = [h for h in homework if h.get("due_date") == date_str]
        test_today = [t for t in tests if t.get("date") == date_str]

        # Collect what should be worked on today (due soon, high priority)
        work_today = []
        for h in homework:
            if not h.get("due_date"):
                continue
            try:
                due = datetime.strptime(h["due_date"], "%Y-%m-%d")
            except ValueError:
                continue
            days_until = (due - current_date).days
            if 0 <= days_until <= 7:
                priority = h.get("priority", "medium")
                est = h.get("estimated_minutes", 30)
                work_today.append({**h, "days_until_due": days_until, "urgency": _urgency(days_until, priority)})

        # Sort by urgency (most urgent first)
        work_today.sort(key=lambda x: -x["urgency"])

        # Also add test prep
        for t in tests:
            if not t.get("date"):
                continue
            try:
                due = datetime.strptime(t["date"], "%Y-%m-%d")
            except ValueError:
                continue
            days_until = (due - current_date).days
            if 0 <= days_until <= 10:
                topics = [x.strip() for x in t.get("topics", "General revision").split(",")]
                work_today.append({
                    "subject": t["subject"],
                    "task": f"Test prep: {', '.join(topics[:3])}",
                    "due_date": t["date"],
                    "estimated_minutes": 45,
                    "priority": "high",
                    "days_until_due": days_until,
                    "urgency": _urgency(days_until, "high") + 5,
                    "is_test": True,
                })

        work_today.sort(key=lambda x: -x["urgency"])

        # Build time slots
        slots = []
        if is_weekend:
            wake = "09:00"
            slots.append({"time": f"{wake} – 09:30", "task": "Morning routine", "type": "break", "date": date_str})
            study_start = "09:30"
        else:
            slots.append({"time": f"{school_start} – {school_end}", "task": "School", "type": "school", "date": date_str})
            study_start = _add_minutes(school_end, 60)  # 1hr after school
            slots.append({"time": f"{_add_minutes(school_end, 15)} – {_add_minutes(school_end, 45)}", "task": "Afternoon break / snack", "type": "break", "date": date_str})

        # Activity slots
        for act in (activities or []):
            if day_name.lower() in act.lower():
                act_time = "16:00" if not is_weekend else "10:00"
                slots.append({"time": f"{act_time} – {_add_minutes(act_time, 60)}", "task": act, "type": "activity", "date": date_str})

        # Study / homework slots
        current_time = study_start
        remaining_before_dinner = _minutes_between(current_time, "18:00") if not is_weekend else 360
        remaining_after_dinner = _minutes_between("19:00", sleep_time)
        total_available = remaining_before_dinner + remaining_after_dinner

        # Calculate how many sessions fit
        break_between = 10
        session_with_break = study_len + break_between
        max_sessions = min(len(work_today), total_available // session_with_break)

        sessions_used = 0
        for item in work_today[:max_sessions]:
            if sessions_used < (remaining_before_dinner // session_with_break):
                # Afternoon slot
                if sessions_used == 0 and not is_weekend:
                    current_time = study_start
                elif sessions_used > 0:
                    current_time = _add_minutes(current_time, session_with_break)
            else:
                # Evening slot
                if sessions_used == (remaining_before_dinner // session_with_break) and not is_weekend:
                    current_time = "19:00"
                elif sessions_used > 0:
                    current_time = _add_minutes(current_time, session_with_break)

            end_time = _add_minutes(current_time, study_len)
            phase = _get_phase(item.get("days_until_due", 7), item.get("priority", "medium"))
            task_label = item["task"]
            if item.get("is_test"):
                task_label = f"TEST PREP: {item['task']}"

            slots.append({
                "time": f"{current_time} – {end_time}",
                "task": task_label,
                "subject": item["subject"],
                "type": "study",
                "date": date_str,
                "duration": f"{study_len} min",
                "phase": phase,
                "due_date": item.get("due_date", ""),
                "priority": item.get("priority", "medium"),
            })
            sessions_used += 1
            current_time = end_time

        # Free time
        if not is_weekend:
            free_start = _add_minutes(school_end, max_sessions * session_with_break + 60)
            if free_start < "18:00":
                slots.append({"time": f"{free_start} – {_add_minutes(free_start, 90)}", "task": "Free time / hobbies", "type": "free", "date": date_str})

        # Evening wind-down
        wind_start = _add_minutes(sleep_time, -30)
        slots.append({"time": f"{wind_start} – {sleep_time}", "task": "Wind down / prep for tomorrow", "type": "break", "date": date_str})

        # Summary
        total_study = sessions_used * study_len
        total_homework = sum(h.get("estimated_minutes", 30) for h in homework if h.get("due_date") == date_str)
        overdue = [h for h in homework if h.get("due_date") and h["due_date"] < date_str and not h.get("completed")]

        schedule.append({
            "day": day_name,
            "date": date_str,
            "is_weekend": is_weekend,
            "slots": slots,
            "summary": {
                "study_minutes": total_study,
                "tasks_scheduled": sessions_used,
                "due_today": len(due_today),
                "overdue": len(overdue),
            },
        })

    return schedule


def _urgency(days_until: int, priority: str) -> float:
    """Higher = more urgent."""
    base = max(0, 10 - days_until)
    mult = {"high": 3, "medium": 2, "low": 1}.get(priority, 2)
    return base * mult


def _get_phase(days_until: int, priority: str) -> str:
    if days_until <= 1:
        return "Final Review"
    if days_until <= 3:
        return "Revise"
    if days_until <= 5:
        return "Practise"
    return "Learn"


def _add_minutes(time_str: str, mins: int) -> str:
    h, m = map(int, time_str.split(':'))
    total = h * 60 + m + mins
    return f"{total // 60 % 24:02d}:{total % 60:02d}"


def _minutes_between(start: str, end: str) -> int:
    sh, sm = map(int, start.split(':'))
    eh, em = map(int, end.split(':'))
    return (eh * 60 + em) - (sh * 60 + sm)


# ── Refine plan ─────────────────────────────────────────────────────────────────

def refine_plan(current_plan: list, feedback: str) -> str:
    today = datetime.today()
    prompt = f"""You are a student study coach. Today is {today.strftime("%A %d %B %Y")}.

Current study plan:
{json.dumps(current_plan, indent=2)}

Student says: "{feedback}"

Update the plan. Keep same JSON structure: day, date, subject, topic, task, phase, duration.
Be specific. Output ONLY the updated JSON array."""

    return _ask_ollama(prompt)


# ── ICS export ──────────────────────────────────────────────────────────────────

def create_ics_content(tasks: list, timezone: str = "Australia/Sydney") -> str:
    ics = "BEGIN:VCALENDAR\nVERSION:2.0\nCALSCALE:GREGORIAN\nPRODID:-//ARIA Study Planner//EN\n"
    for task in tasks:
        date_str = task.get("date", "")
        subject = task.get("subject", "")
        topic = task.get("topic", "")
        task_text = task.get("task", "Study session")
        phase = task.get("phase", "")
        duration_str = task.get("duration", "45 min")
        start_time = task.get("time", "16:00")

        # Extract start time from "HH:MM – HH:MM" format
        if "–" in start_time:
            start_time = start_time.split("–")[0].strip()

        try:
            duration_mins = int(''.join(filter(str.isdigit, duration_str)))
        except Exception:
            duration_mins = 45
        if not date_str:
            continue
        try:
            dt_start = datetime.strptime(f"{date_str} {start_time}", "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        dt_end = dt_start + timedelta(minutes=duration_mins)
        summary = f"{subject} — {topic}" if topic and subject else (topic or f"{subject} — {task_text[:50]}")
        desc_parts = []
        if phase:
            desc_parts.append(f"Phase: {phase}")
        if topic:
            desc_parts.append(f"Topic: {topic}")
        desc_parts.append(f"Task: {task_text}")
        desc_parts.append(f"Duration: {duration_str}")
        description = "\\n".join(desc_parts)
        ics += f"""BEGIN:VEVENT
UID:{uuid.uuid4()}@aria-study-planner
SUMMARY:{summary}
DTSTART;TZID={timezone}:{dt_start.strftime("%Y%m%dT%H%M%S")}
DTEND;TZID={timezone}:{dt_end.strftime("%Y%m%dT%H%M%S")}
DESCRIPTION:{description}
END:VEVENT\n"""
    ics += "END:VCALENDAR"
    return ics


def create_ics_from_schedule(schedule: list, timezone: str = "Australia/Sydney") -> str:
    """Convert full schedule into ICS — only study/work slots."""
    study_tasks = []
    for day in schedule:
        for slot in day.get("slots", []):
            if slot.get("type") == "study":
                study_tasks.append({
                    "date": slot.get("date", day.get("date", "")),
                    "subject": slot.get("subject", ""),
                    "task": slot.get("task", ""),
                    "phase": slot.get("phase", ""),
                    "duration": slot.get("duration", "45 min"),
                    "time": slot.get("time", "16:00"),
                })
    return create_ics_content(study_tasks, timezone)


# ── Quick add homework to existing schedule ─────────────────────────────────────

def add_homework_to_schedule(schedule: list, homework_item: dict, study_len: int = 45) -> list:
    """
    Insert a new homework item into an existing schedule.
    Finds the best available slot (before due date, fitting into free time).
    """
    subject = homework_item.get("subject", "")
    task = homework_item.get("task", "")
    due_date = homework_item.get("due_date", "")
    priority = homework_item.get("priority", "medium")
    est_minutes = homework_item.get("estimated_minutes", 30)

    if not due_date or not schedule:
        return schedule

    # Calculate how many sessions needed
    num_sessions = max(1, est_minutes // study_len)

    # Find days before due date that have space
    added = 0
    for day in schedule:
        if added >= num_sessions:
            break
        day_date = day.get("date", "")
        if day_date > due_date:
            continue
        if day_date == due_date:
            # Can still add on due day (morning/afternoon)
            pass

        # Find free slots on this day
        existing_studies = sum(1 for s in day.get("slots", []) if s.get("type") == "study")
        max_per_day = 4 if not day.get("is_weekend") else 6

        if existing_studies < max_per_day:
            # Find where to insert — after last study slot or after school
            slots = day.get("slots", [])
            last_study_end = None
            for s in slots:
                if s.get("type") == "study":
                    t = s.get("time", "")
                    if "–" in t:
                        last_study_end = t.split("–")[1].strip()

            if last_study_end:
                start_time = _add_minutes(last_study_end, 10)
            elif day.get("is_weekend"):
                start_time = "10:00" if existing_studies == 0 else _add_minutes("10:00", existing_studies * (study_len + 10))
            else:
                start_time = _add_minutes("15:00", 60 + existing_studies * (study_len + 10))

            end_time = _add_minutes(start_time, study_len)

            phase = _get_phase(
                max(0, (datetime.strptime(due_date, "%Y-%m-%d") - datetime.strptime(day_date, "%Y-%m-%d")).days),
                priority,
            )

            new_slot = {
                "time": f"{start_time} – {end_time}",
                "task": task,
                "subject": subject,
                "type": "study",
                "date": day_date,
                "duration": f"{study_len} min",
                "phase": phase,
                "due_date": due_date,
                "priority": priority,
            }

            # Insert before the last break/wind-down slot
            insert_idx = len(slots)
            for i in range(len(slots) - 1, -1, -1):
                if slots[i].get("type") in ("break", "free"):
                    insert_idx = i
                else:
                    break
            slots.insert(insert_idx, new_slot)
            day["slots"] = slots
            day["summary"]["tasks_scheduled"] = existing_studies + 1
            day["summary"]["study_minutes"] = day["summary"].get("study_minutes", 0) + study_len
            added += 1

    return schedule
