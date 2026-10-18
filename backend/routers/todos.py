"""Todos / Assignment Inbox — solo student organization."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.todo_service import (
    add_todo,
    cushion,
    delete_todo,
    list_todos,
    parse_due_date,
    parse_estimate,
    parse_priority,
    update_todo,
)

router = APIRouter(prefix="/api/todos", tags=["todos"])


class TodoCreate(BaseModel):
    subject: str = "General"
    task: str
    due_date: str | None = None
    estimated_mins: int = 30
    priority: str = "medium"


class TodoUpdate(BaseModel):
    subject: str | None = None
    task: str | None = None
    due_date: str | None = None
    estimated_mins: int | None = None
    priority: str | None = None
    completed: bool | None = None


@router.get("")
async def get_todos():
    return {"todos": list_todos(), "cushion": cushion()}


@router.post("")
async def create_todo(req: TodoCreate):
    # Try to parse due date from task if not explicitly provided
    due = req.due_date or parse_due_date(req.task)
    est = req.estimated_mins
    # If task contains "45m" and estimate is default 30, try parse
    if est == 30:
        parsed_est = parse_estimate(req.task)
        if parsed_est:
            est = parsed_est
    prio = req.priority
    if prio == "medium":
        parsed_prio = parse_priority(req.task)
        if parsed_prio:
            prio = parsed_prio
    todo = add_todo(req.subject, req.task, due, est, prio)
    return todo


@router.patch("/{todo_id}")
async def patch_todo(todo_id: str, req: TodoUpdate):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    todo = update_todo(todo_id, updates)
    if not todo:
        raise HTTPException(404, "Todo not found")
    return todo


@router.delete("/{todo_id}")
async def remove_todo(todo_id: str):
    ok = delete_todo(todo_id)
    if not ok:
        raise HTTPException(404, "Todo not found")
    return {"deleted": True}


@router.get("/cushion")
async def get_cushion():
    return cushion()


@router.post("/from-chat")
async def create_from_chat(data: dict):
    """Create todo from chat-parsed text: {text: "add maths HW due Fri 45m"}"""
    text = data.get("text", "") or data.get("message", "")
    if not text.strip():
        raise HTTPException(400, "text required")
    # Simple parsing: subject is first word before task, or "General"
    # Try to extract subject: look for known subjects
    import re

    subjects = [
        "maths",
        "mathematics",
        "english",
        "science",
        "biology",
        "chemistry",
        "physics",
        "history",
        "geography",
        "pdhpe",
        "technology",
        "art",
        "music",
        "commerce",
        "economics",
    ]
    subject = "General"
    task = text
    # Remove leading "add" / "todo"
    task = re.sub(r"^\s*(add|create|new)\s+(todo\s+)?", "", task, flags=re.IGNORECASE)
    # Try to find subject at start
    for subj in subjects:
        if re.match(rf"^{subj}\b", task, re.IGNORECASE):
            subject = subj.capitalize()
            task = re.sub(rf"^{subj}\b\s*[:\-]?\s*", "", task, flags=re.IGNORECASE)
            break
    # Parse due, estimate, priority from remaining text
    due = parse_due_date(text)
    est = parse_estimate(text) or 30
    prio = parse_priority(text) or "medium"
    # Clean task: remove due/estimate fragments for display
    # Keep original for now, just store as task
    todo = add_todo(subject, task.strip() or text, due, est, prio)
    return todo
