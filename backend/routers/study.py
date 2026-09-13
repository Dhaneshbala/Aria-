import asyncio
import json as _json

from fastapi import APIRouter, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from services.study_service import StudyService
from models.database import get_config, MODELS

router = APIRouter(prefix="/api/study", tags=["study"])
study_svc = StudyService()


class StudyRequest(BaseModel):
    topic: str
    level: str = "medium"
    count: int = 5
    days: int = 7
    verify: bool = True  # cross-check (second model + Google) — on by default, as requested


# ── Response schemas (the contract the frontend depends on) ──────────────────

class QuizQuestion(BaseModel):
    question: str = "Question text"
    options: list[str] = "Exactly 4 options, indexed A) B) C) D)"
    correct: str = "Answer letter ('A'-'D'); may be '' when verification could not run"
    explanation: str = "Brief explanation of the correct answer"
    verified: str = "verification status: triple_verified | majority_verified | disputed | original | no_data | unverified"


class QuizResponse(BaseModel):
    """Response of POST /quiz — timed exam simulations run through the
    chat brain (exam_sim) instead of a separate endpoint.

    The frontend must render questions by this shape only.
    """
    questions: list[QuizQuestion]
    mode: str | None = None


class FlashcardsResponse(BaseModel):
    cards: list[dict]


class SummaryResponse(BaseModel):
    summary: str


@router.post("/quiz", response_model=QuizResponse)
async def generate_quiz(req: StudyRequest):
    config = get_config()
    model = config.get("model", config.get("reasoning_model", MODELS["main"]))
    # verify flag: request body takes precedence; config/env also honoured.
    # Default is True (verified) as requested — no auto-quit.
    if req.verify is False:
        verify = False
    elif req.verify is True:
        verify = True
    else:
        verify = config.get("quiz_verify", True)
    questions = await study_svc.generate_quiz(req.topic, req.level, req.count, model, verify=verify)
    return {"questions": questions}


@router.post("/quiz/stream")
async def stream_quiz(req: StudyRequest, request: Request):
    """SSE quiz stream — each verified question arrives as it's done.

    Events: {"type":"total","total":n}, {"type":"question","question":{...}},
    {"type":"progress","done":d,"total":n}, {"type":"error",...},
    {"type":"done","questions":[...]}. Same verification as POST /quiz.
    """
    config = get_config()
    model = config.get("model", config.get("reasoning_model", MODELS["main"]))

    def _sse(obj: dict) -> str:
        return f"data: {_json.dumps(obj, ensure_ascii=False)}\n\n"

    async def event_stream():
        questions: list = []
        try:
            async for kind, *payload in study_svc.generate_quiz_stream(
                req.topic, req.level, req.count, model
            ):
                if await request.is_disconnected():
                    break
                if kind == "total":
                    yield _sse({"type": "total", "total": payload[0]})
                elif kind == "question":
                    questions.append(payload[0])
                    yield _sse({"type": "question", "question": payload[0]})
                elif kind == "progress":
                    yield _sse({"type": "progress", "done": payload[0], "total": payload[1]})
                elif kind == "error":
                    yield _sse({"type": "error", "content": str(payload[0])[:300]})
            yield _sse({"type": "done", "questions": questions})
        except asyncio.CancelledError:
            raise
        except Exception as e:
            yield _sse({"type": "error", "content": str(e)[:200]})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/flashcards")
async def generate_flashcards(req: StudyRequest):
    config = get_config()
    model = config.get("model", config.get("reasoning_model", MODELS["main"]))
    cards = await study_svc.generate_flashcards(req.topic, req.count, model)
    return {"cards": cards}


@router.post("/summary")
async def generate_summary(req: StudyRequest):
    config = get_config()
    model = config.get("model", config.get("reasoning_model", MODELS["main"]))
    summary = await study_svc.generate_summary(req.topic, model)
    return {"summary": summary}

@router.post("/quiz/check")
async def check_answer(data: dict):
    from services.memory_service import MemoryService
    mem = MemoryService()
    subject = data.get("subject", "general")
    correct = data.get("correct", False)
    profile = await mem.update_profile(subject, correct)
    return {"profile": profile}


@router.post("/quiz/adaptive-difficulty")
async def adaptive_difficulty(data: dict):
    """Real-time difficulty adjustment based on rolling accuracy.
    POST {"current_difficulty": "easy|medium|hard", "correct": true/false, "history": [true,false,true,true]}
    Returns {"suggested_difficulty": "easy|medium|hard", "reason": "..."}
    """
    current = data.get("current_difficulty", "medium")
    history = data.get("history", [])  # last N answers as booleans
    if not history:
        return {"suggested_difficulty": current, "reason": "No history yet"}

    # Rolling accuracy over last 5 questions
    recent = history[-5:]
    accuracy = sum(1 for x in recent if x) / len(recent)
    total = len(history)
    total_correct = sum(1 for x in history if x)
    total_accuracy = total_correct / total if total else 0

    suggested = current
    reason = ""

    if current == "easy":
        if accuracy >= 0.8 and total >= 3:
            suggested = "medium"
            reason = f"Great job! {accuracy:.0%} correct in last {len(recent)} — level up to medium"
        else:
            reason = f"Keep practicing — {accuracy:.0%} recent accuracy"
    elif current == "medium":
        if accuracy >= 0.8 and total >= 4:
            suggested = "hard"
            reason = f"Impressive! {accuracy:.0%} correct — you're ready for harder questions"
        elif accuracy <= 0.4 and total >= 3:
            suggested = "easy"
            reason = f"Let's slow down — {accuracy:.0%} recent accuracy, building foundations"
        else:
            reason = f"Steady progress — {accuracy:.0%} recent accuracy"
    elif current == "hard":
        if accuracy <= 0.4 and total >= 3:
            suggested = "medium"
            reason = f"Let's review — {accuracy:.0%} recent accuracy, reinforcing concepts"
        elif accuracy >= 0.8:
            reason = f"Excellent! {accuracy:.0%} at hard level — keep pushing!"
        else:
            reason = f"Challenging but good — {accuracy:.0%} recent accuracy"

    return {
        "suggested_difficulty": suggested,
        "reason": reason,
        "recent_accuracy": round(accuracy, 2),
        "total_accuracy": round(total_accuracy, 2),
        "questions_answered": total,
    }


@router.post("/notes")
async def generate_notes(req: StudyRequest):
    config = get_config()
    model = config.get("model", config.get("reasoning_model", MODELS["main"]))
    notes = await study_svc.generate_notes(req.topic, style=req.level, model=model)
    return {"notes": notes}


class CheatsheetRequest(BaseModel):
    topic: str
    subject: str = ""


@router.post("/cheatsheet")
async def generate_cheatsheet(req: CheatsheetRequest):
    from fastapi import HTTPException
    topic = (req.topic or "").strip()
    if not topic:
        raise HTTPException(400, "Topic cannot be empty")
    if len(topic) > 300:
        raise HTTPException(400, "Topic too long (max 300 chars)")
    config = get_config()
    model = config.get("model", config.get("reasoning_model", MODELS["main"]))
    sheet = await study_svc.generate_cheatsheet(topic[:300], (req.subject or "")[:80], model)
    return {"topic": topic, "subject": req.subject or "", "cheatsheet": sheet}


# ── Exam countdown plans ────────────────────────────────────────────────────

class ExamPlanRequest(BaseModel):
    exam_name: str = "Exam"
    exam_date: str = ""  # YYYY-MM-DD
    subjects: list[str] = []
    mins_per_day: int = 45
    assessment_text: str | None = None
    assessment_topics: list[str] | None = None
    assessment_summary: str | None = None


@router.post("/exam-plan")
async def create_exam_plan(req: ExamPlanRequest):
    from fastapi import HTTPException
    from services.exam_plan_service import create_plan
    try:
        return await create_plan(
            req.exam_name, req.exam_date, req.subjects, req.mins_per_day,
            assessment_text=req.assessment_text,
            assessment_topics=req.assessment_topics,
            assessment_summary=req.assessment_summary,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/exam-plan/parse-notification")
async def parse_exam_notification(file: UploadFile = File(...)):
    """Upload an assessment notification (PDF/DOCX/TXT/image) so ARIA knows
    what the assessment is about. Returns extracted text + parsed fields
    (exam_name, exam_date, subjects, topics, summary) to prefill the plan form."""
    from fastapi import HTTPException
    from services.document_service import DocumentService
    from services.exam_plan_service import parse_notification
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")
    fname = file.filename or "notification"
    ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
    try:
        if ext in ("png", "jpg", "jpeg", "webp", "heic", "bmp"):
            from services.image_service import ImageService
            from models.database import get_config, MODELS
            cfg = get_config()
            model = cfg.get("model", cfg.get("reasoning_model", MODELS["main"]))
            mime = file.content_type or "image/jpeg"
            text = await ImageService().analyse(data, mime, model)
        else:
            text = await DocumentService().extract_text(data, fname)
    except Exception as e:
        raise HTTPException(400, f"Could not read file: {e}")
    text = (text or "").strip()
    if not text:
        raise HTTPException(400, "No text found in file — try a clearer photo or PDF")
    parsed = await parse_notification(text)
    return {
        "filename": fname,
        "text_preview": text[:1500],
        "assessment_text": text[:4000],
        **parsed,
    }


@router.get("/exam-plans")
async def get_exam_plans():
    from services.exam_plan_service import list_plans
    return list_plans()


@router.delete("/exam-plans/{plan_id}")
async def remove_exam_plan(plan_id: str):
    from fastapi import HTTPException
    from services.exam_plan_service import delete_plan
    if not delete_plan(plan_id):
        raise HTTPException(404, "Plan not found")
    return {"deleted": True}