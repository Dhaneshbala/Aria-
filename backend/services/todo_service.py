"""
Todo / Assignment Inbox — solo student organization.

Stores personal todos in ~/.aria_data/todos.json with atomic writes + RLock.
Used by chat brain ("add maths HW due Fri") and Dashboard ring.
"""
import json
import os
import re
import threading
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(os.environ.get("ARIA_DATA_DIR", Path.home() / ".aria_data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
TODO_FILE = DATA_DIR / "todos.json"

_LOCK = threading.RLock()

def _load() -> list[dict]:
    with _LOCK:
        if TODO_FILE.exists():
            try:
                return json.loads(TODO_FILE.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

def _save(todos: list[dict]):
    with _LOCK:
        text = json.dumps(todos, indent=2, ensure_ascii=False)
        fd, tmp = tempfile.mkstemp(dir=str(TODO_FILE.parent), prefix=".todos.tmp.")
        try:
            with open(fd, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            Path(tmp).replace(TODO_FILE)
        finally:
            p = Path(tmp)
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

def list_todos() -> list[dict]:
    todos = _load()
    # sort: incomplete first, then due date, then priority — handle None due_date
    def sort_key(t):
        prio = {"high": 0, "medium": 1, "low": 2}.get(t.get("priority", "medium"), 1)
        due = t.get("due_date") or "9999-12-31"
        # ensure due is str for comparison
        if not isinstance(due, str):
            due = str(due)
        completed = 1 if t.get("completed") else 0
        return (completed, due, prio)
    return sorted(todos, key=sort_key)

def add_todo(subject: str, task: str, due_date: str | None = None, estimated_mins: int = 30, priority: str = "medium") -> dict:
    todos = _load()
    todo = {
        "id": str(uuid.uuid4())[:8],
        "subject": subject.strip() or "General",
        "task": task.strip() or "Untitled",
        "due_date": due_date,
        "estimated_mins": max(5, min(240, int(estimated_mins))),
        "priority": priority if priority in ("low", "medium", "high") else "medium",
        "completed": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    todos.append(todo)
    _save(todos)
    return todo

def update_todo(todo_id: str, updates: dict) -> dict | None:
    todos = _load()
    for t in todos:
        if t["id"] == todo_id:
            # only allow safe fields
            for k in ("subject", "task", "due_date", "estimated_mins", "priority", "completed"):
                if k in updates:
                    if k == "estimated_mins":
                        t[k] = max(5, min(240, int(updates[k])))
                    else:
                        t[k] = updates[k]
            _save(todos)
            return t
    return None

def delete_todo(todo_id: str) -> bool:
    todos = _load()
    before = len(todos)
    todos = [t for t in todos if t["id"] != todo_id]
    if len(todos) != before:
        _save(todos)
        return True
    return False

def parse_due_date(text: str) -> str | None:
    """Parse 'due Fri', 'due 2026-09-10', 'due tomorrow', 'due in 3 days' -> YYYY-MM-DD or None."""
    text_lower = text.lower()
    today = datetime.now().date()
    # Explicit YYYY-MM-DD
    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if m:
        try:
            datetime.strptime(m.group(1), "%Y-%m-%d")
            return m.group(1)
        except Exception:
            pass
    # Tomorrow / today
    if re.search(r"\btomorrow\b", text_lower):
        return (today + timedelta(days=1)).isoformat()
    if re.search(r"\btoday\b", text_lower):
        return today.isoformat()
    # In N days
    m = re.search(r"in\s+(\d+)\s+days?", text_lower)
    if m:
        try:
            n = int(m.group(1))
            return (today + timedelta(days=n)).isoformat()
        except Exception:
            pass
    # Weekday: Mon, Tue, Fri, etc.
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for i, wd in enumerate(weekdays):
        if re.search(rf"\b{wd[:3]}\b", text_lower) or re.search(rf"\b{wd}\b", text_lower):
            # Find next occurrence of that weekday
            today_wd = today.weekday()  # 0 Mon
            target_wd = i
            delta = (target_wd - today_wd) % 7
            if delta == 0:
                delta = 7  # next week if today is same weekday and no time context
            # If text says "due Fri" and today is Fri, assume today
            if re.search(rf"\bdue\s+{wd[:3]}", text_lower) and delta == 7:
                # Check if user meant today — if no other context, use today
                pass
            return (today + timedelta(days=delta)).isoformat()
    # Next week
    if re.search(r"\bnext week\b", text_lower):
        return (today + timedelta(days=7)).isoformat()
    return None

def parse_estimate(text: str) -> int | None:
    m = re.search(r"(\d+)\s*(?:min|mins|minutes|m)\b", text.lower())
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass
    # "45m" without space
    m = re.search(r"(\d+)\s*m\b", text.lower())
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass
    return None

def parse_priority(text: str) -> str | None:
    tl = text.lower()
    if re.search(r"\bhigh\b|\b urg", tl):
        return "high"
    if re.search(r"\blow\b", tl):
        return "low"
    if re.search(r"\bmedium\b|\bmid\b", tl):
        return "medium"
    return None

def cushion(todos: list[dict] | None = None) -> dict:
    """Simple overload check: total estimated mins vs. available study time.
    For solo use, assume 90 mins available per weekday, 180 on weekends.
    """
    if todos is None:
        todos = [t for t in _load() if not t.get("completed")]
    total_mins = sum(t.get("estimated_mins", 30) for t in todos)
    # Available: next 7 days
    today = datetime.now().date()
    available = 0
    for i in range(7):
        d = today + timedelta(days=i)
        is_weekend = d.weekday() >= 5
        available += 180 if is_weekend else 90
    # Overload if total > available, busy if > 70% of available
    if total_mins > available:
        status = "overloaded"
    elif total_mins > available * 0.7:
        status = "busy"
    else:
        status = "on_track"
    return {
        "total_mins": total_mins,
        "available_mins": available,
        "overload": total_mins - available if total_mins > available else 0,
        "status": status,
        "count": len(todos),
    }
