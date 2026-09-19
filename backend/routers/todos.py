"""Todos / Assignment Inbox — solo student organization."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from services.todo_service import list_todos, add_todo, update_todo, delete_todo, cushion, parse_due_date, parse_estimate, parse_priority

router = APIRouter(prefix="/api/todos", tags=["todos"])

class TodoCreate(BaseModel):
    subject: str = Field(default="General", max_length=100)
    task: str = Field(..., min_length=1, max_length=1000)
    due_date: Optional[str] = Field(default=None, max_length=50)
    estimated_mins: int = Field(default=30, ge=1, le=1440)
    priority: str = Field(default="medium", pattern="^(low|medium|high|urgent)$")

class TodoUpdate(BaseModel):
    subject: Optional[str] = Field(default=None, max_length=100)
    task: Optional[str] = Field(default=None, max_length=1000)
    due_date: Optional[str] = Field(default=None, max_length=50)
    estimated_mins: Optional[int] = Field(default=None, ge=1, le=1440)
    priority: Optional[str] = Field(default=None, pattern="^(low|medium|high|urgent)$")
    completed: Optional[bool] = None

class TodoFromChatRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)

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
async def create_from_chat(data: TodoFromChatRequest):
    """Create todo from chat-parsed text: {text: "add maths HW due Fri 45m"}"""
    text = data.text
    if not text.strip():
        raise HTTPException(400, "text required")
    # Simple parsing: subject is first word before task, or "General"
    # Try to extract subject: look for known subjects
    import re
    subjects = ["maths", "mathematics", "english", "science", "biology", "chemistry", "physics", "history", "geography", "pdhpe", "technology", "art", "music", "commerce", "economics"]
    subject = "General"
    task = text
    # Remove leading "add" / "todo"
    task = re.sub(r"^\s*(add|create|new)\s+(todo\s+)?", "", task, flags=re.I)
    # Try to find subject at start
    for subj in subjects:
        if re.match(rf"^{subj}\b", task, re.I):
            subject = subj.capitalize()
            task = re.sub(rf"^{subj}\b\s*[:\-]?\s*", "", task, flags=re.I)
            break
    # Parse due, estimate, priority from remaining text
    due = parse_due_date(text)
    est = parse_estimate(text) or 30
    prio = parse_priority(text) or "medium"
    # Clean task: remove due/estimate fragments for display
    # Keep original for now, just store as task
    todo = add_todo(subject, task.strip() or text, due, est, prio)
    return todo
