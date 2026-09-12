"""
Exam countdown planner — exam date in, day-by-day study plan out.

Rule-based (no LLM call — instant, deterministic, testable):
  - Weak topics from the study profile go first and repeat twice.
  - Remaining days rotate through the exam subjects.
  - Final day is always light review (20 mins, low priority).
  - Every study day becomes a real todo (due that date) so Dashboard,
    todos and cushion all stay in sync.

Plans live in ~/.aria_data/exam_plans.json. Deleting a plan also
removes its still-incomplete todos.
"""
import json
import os
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(os.environ.get("ARIA_DATA_DIR", Path.home() / ".aria_data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
PLANS_FILE = DATA_DIR / "exam_plans.json"

_LOCK = threading.RLock()


def _load() -> list[dict]:
    with _LOCK:
        if PLANS_FILE.exists():
            try:
                data = json.loads(PLANS_FILE.read_text(encoding="utf-8"))
                return data if isinstance(data, list) else []
            except Exception:
                return []
        return []


def _save(plans: list[dict]) -> None:
    with _LOCK:
        PLANS_FILE.write_text(json.dumps(plans, indent=2, ensure_ascii=False),
                              encoding="utf-8")


async def _weak_topics(limit: int = 5) -> list[str]:
    """Weak areas from the study profile (best-effort, never crashes)."""
    try:
        from services.memory_service import MemoryService
        profile = await MemoryService().get_profile()
        weak = profile.get("weak_areas", []) or []
        return [str(w) for w in weak[:limit] if str(w).strip()]
    except Exception:
        return []


def build_schedule(exam_date: date, subjects: list[str], weak: list[str],
                   assessment_topics: list[str] | None = None) -> list[dict]:
    """Pure function: dates + focus topics. Easy to unit test.

    Returns [{date: ISO, focus: str, weak_hit: bool}] for each study day
    from today up to (not including) the exam day, plus a light-review
    final entry for the day before the exam.

    Priority queue: assessment-notification topics first (×2), then each
    weak topic twice, then subjects round-robin.
    """
    today = date.today()
    days_left = max(0, (exam_date - today).days)
    subjects = [s.strip() for s in subjects if s.strip()] or ["General"]
    weak = [w.strip() for w in weak if w.strip()]
    assessment_topics = [t.strip() for t in (assessment_topics or []) if t.strip()]

    if days_left == 0:
        return [{"date": today.isoformat(), "focus": f"Light review: {subjects[0]}",
                 "weak_hit": False, "light": True}]

    # Study days exclude the exam day itself
    study_dates = [today + timedelta(days=i) for i in range(days_left)]
    # Priority queue: assessment topics (×2) → weak topics (×2) → subjects round-robin
    queue = assessment_topics * 2 + weak * 2 + subjects
    schedule: list[dict] = []
    for i, day in enumerate(study_dates):
        # Final study day = light review of the first subject
        if i == len(study_dates) - 1 and len(study_dates) > 1:
            schedule.append({"date": day.isoformat(),
                             "focus": f"Light review: {subjects[0]} — sleep early",
                             "weak_hit": False, "light": True})
            continue
        focus = queue[i % len(queue)]
        schedule.append({"date": day.isoformat(), "focus": focus,
                         "weak_hit": focus in weak, "light": False})
    return schedule


async def create_plan(exam_name: str, exam_date_str: str,
                      subjects: list[str], mins_per_day: int = 45,
                      assessment_text: str | None = None,
                      assessment_topics: list[str] | None = None,
                      assessment_summary: str | None = None) -> dict:
    """Create a plan + todos. Raises ValueError on bad input.

    assessment_text: raw text extracted from an assessment notification
      (stored truncated so chat/ARIA can see what the assessment is about).
    assessment_topics: specific topics parsed from the notification — these
      go first in the schedule, ahead of weak topics.
    assessment_summary: short human-readable summary of the notification.
    """
    from services.todo_service import add_todo

    exam_name = (exam_name or "").strip() or "Exam"
    try:
        exam_date = datetime.strptime(exam_date_str, "%Y-%m-%d").date()
    except Exception:
        raise ValueError("exam_date must be YYYY-MM-DD")
    if exam_date < date.today():
        raise ValueError("exam_date is in the past")
    if (exam_date - date.today()).days > 365:
        raise ValueError("exam_date is more than a year away")
    mins = max(15, min(180, int(mins_per_day or 45)))
    subjects = [s.strip() for s in (subjects or []) if s.strip()] or ["General"]
    assessment_topics = [t.strip() for t in (assessment_topics or []) if t.strip()][:12]
    assessment_text = (assessment_text or "").strip()[:4000]
    assessment_summary = (assessment_summary or "").strip()[:1000]

    weak = await _weak_topics()
    schedule = build_schedule(exam_date, subjects, weak, assessment_topics)

    days = []
    for entry in schedule:
        light = entry.get("light", False)
        todo = add_todo(
            subjects[0] if len(subjects) == 1 else "General",
            f"{exam_name}: {entry['focus']}",
            due_date=entry["date"],
            estimated_mins=20 if light else mins,
            priority="low" if light else ("high" if entry["weak_hit"] else "medium"),
        )
        days.append({**entry, "minutes": 20 if light else mins,
                     "todo_id": todo["id"], "completed": False})

    plan = {
        "id": str(uuid.uuid4())[:8],
        "exam_name": exam_name,
        "exam_date": exam_date.isoformat(),
        "days_left": max(0, (exam_date - date.today()).days),
        "subjects": subjects,
        "weak_topics": weak,
        "mins_per_day": mins,
        "days": days,
        "assessment_topics": assessment_topics,
        "assessment_summary": assessment_summary,
        "assessment_text": assessment_text,
        "has_notification": bool(assessment_text or assessment_summary or assessment_topics),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    plans = _load()
    plans.append(plan)
    _save(plans)
    return plan


def _heuristic_parse(text: str) -> dict:
    """Fast rule-based parse of an assessment notification (no LLM)."""
    import re
    t = text or ""
    # Subjects: look for known school subjects
    known = ["Mathematics", "Maths", "English", "Science", "Biology", "Chemistry",
             "Physics", "History", "Geography", "PDHPE", "Technology", "Art",
             "Music", "Commerce", "Economics", "Languages", "Religion", "Drama"]
    subjects = [s for s in known if re.search(rf"\b{re.escape(s)}\b", t, re.I)]
    # Dates: YYYY-MM-DD or D/M/YYYY or "15 March" style
    exam_date = None
    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", t)
    if m:
        exam_date = m.group(1)
    else:
        m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", t)
        if m:
            try:
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if y < 100:
                    y += 2000
                exam_date = date(y, mo, d).isoformat()
            except Exception:
                pass
    # Topics: lines after "topics", "outcomes", "content", "covers" keywords
    topics: list[str] = []
    for kw in ("topics", "outcomes", "content", "covers", "sections", "syllabus"):
        m = re.search(rf"{kw}\s*[:\-]?\s*(.{{10,400}})", t, re.I | re.S)
        if m:
            chunk = m.group(1)
            # split on bullets / commas / newlines
            parts = re.split(r"[\n•\-\*]+|,|;", chunk)
            for p in parts:
                p = re.sub(r"\s+", " ", p).strip(" .-:()")
                if 3 < len(p) < 80 and len(topics) < 12:
                    # skip boilerplate
                    if not re.search(r"(assessment|notification|student|school|teacher|signature|mark|exam date)", p, re.I):
                        topics.append(p)
            if topics:
                break
    # Exam name: first non-empty line, or "X Assessment"
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    exam_name = ""
    for ln in lines[:5]:
        if len(ln) < 80 and re.search(r"(assess|exam|test|task|task|quiz)", ln, re.I):
            exam_name = ln[:60]
            break
    if not exam_name and lines:
        exam_name = lines[0][:60]
    summary = " ".join(t.split())[:600]
    return {
        "exam_name": exam_name or "",
        "exam_date": exam_date or "",
        "subjects": subjects[:4],
        "topics": topics[:12],
        "summary": summary,
    }


async def parse_notification(text: str) -> dict:
    """Parse an assessment notification into plan fields.

    Tries the local LLM for a clean extraction, falls back to the
    heuristic parser so it never crashes and works offline-ish.
    Always returns {exam_name, exam_date, subjects, topics, summary}.
    """
    text = (text or "").strip()
    if not text:
        return {"exam_name": "", "exam_date": "", "subjects": [], "topics": [], "summary": ""}
    fallback = _heuristic_parse(text)
    try:
        from services.ollama_service import OllamaService
        from models.database import get_config, MODELS
        import json as _json
        cfg = get_config()
        model = cfg.get("model") or cfg.get("reasoning_model") or MODELS["main"]
        prompt = (
            "Extract assessment details from this school assessment notification.\n"
            "Return ONLY valid JSON: "
            '{"exam_name": "...", "exam_date": "YYYY-MM-DD or empty", '
            '"subjects": ["..."], "topics": ["topic1", ...up to 10], '
            '"summary": "2-3 sentence summary of what the assessment is about"}\n\n'
            f"NOTIFICATION:\n{text[:3000]}"
        )
        raw = await OllamaService().complete(
            model, prompt,
            system="You output ONLY JSON. No explanation, no markdown.",
            think=False, context_window=2048, max_tokens=600, timeout=60)
        # pull first {...} block
        m = __import__("re").search(r"\{.*\}", raw, __import__("re").S)
        if m:
            data = _json.loads(m.group(0))
            out = {
                "exam_name": str(data.get("exam_name") or fallback["exam_name"])[:60],
                "exam_date": str(data.get("exam_date") or fallback["exam_date"])[:10],
                "subjects": [str(s)[:30] for s in (data.get("subjects") or fallback["subjects"])][:4],
                "topics": [str(s)[:80] for s in (data.get("topics") or fallback["topics"])][:12],
                "summary": str(data.get("summary") or fallback["summary"])[:1000],
            }
            if out["topics"] or out["subjects"] or out["exam_name"]:
                return out
    except Exception:
        pass
    return fallback


def list_plans() -> list[dict]:
    """All plans with fresh days_left + per-day completion synced from todos."""
    from services.todo_service import list_todos
    todos = {t["id"]: t for t in list_todos()}
    plans = _load()
    today = date.today()
    changed = False
    for plan in plans:
        try:
            plan["days_left"] = max(0, (date.fromisoformat(plan["exam_date"]) - today).days)
        except Exception:
            plan["days_left"] = 0
        for day in plan.get("days", []):
            t = todos.get(day.get("todo_id", ""))
            done = bool(t and t.get("completed"))
            if day.get("completed") != done:
                day["completed"] = done
                changed = True
    if changed:
        _save(plans)
    return sorted(plans, key=lambda p: p.get("exam_date", ""))


def delete_plan(plan_id: str) -> bool:
    """Delete a plan + its still-incomplete todos. Returns True if found."""
    from services.todo_service import delete_todo, list_todos
    plans = _load()
    target = next((p for p in plans if p.get("id") == plan_id), None)
    if target is None:
        return False
    done_ids = {t["id"] for t in list_todos() if t.get("completed")}
    for day in target.get("days", []):
        tid = day.get("todo_id")
        if tid and tid not in done_ids:
            try:
                delete_todo(tid)
            except Exception:
                pass
    _save([p for p in plans if p.get("id") != plan_id])
    return True
