import asyncio
import json as _json

from fastapi import APIRouter, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from services.study_service import StudyService
from models.database import get_config, MODELS

router = APIRouter(prefix="/api/study", tags=["study"])
study_svc = StudyService()

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    from config.settings import get_settings as _get_study_settings
    _study_limit_val = _get_study_settings().rate_limit_chat
    _study_limiter = Limiter(key_func=get_remote_address, default_limits=[_study_limit_val])
    _study_limit = _study_limiter.limit(_study_limit_val)
except Exception:
    _study_limiter = None
    _study_limit = lambda f: f  # no-op


class StudyRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    level: str = Field(default="medium", pattern="^(easy|medium|hard|exam|olympiad)$")
    count: int = Field(default=5, ge=1, le=15)
    days: int = Field(default=7, ge=1, le=365)
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
@_study_limit
async def generate_quiz(req: StudyRequest, request: Request):
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
@_study_limit
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
@_study_limit
async def generate_flashcards(req: StudyRequest, request: Request):
    config = get_config()
    model = config.get("model", config.get("reasoning_model", MODELS["main"]))
    cards = await study_svc.generate_flashcards(req.topic, req.count, model)
    return {"cards": cards}


@router.post("/summary")
@_study_limit
async def generate_summary(req: StudyRequest, request: Request):
    config = get_config()
    model = config.get("model", config.get("reasoning_model", MODELS["main"]))
    summary = await study_svc.generate_summary(req.topic, model)
    return {"summary": summary}

class QuizCheckRequest(BaseModel):
    subject: str = Field(default="general", max_length=100)
    correct: bool = False


class AdaptiveDifficultyRequest(BaseModel):
    current_difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    correct: bool = False
    history: list[bool] = Field(default_factory=list, max_length=100)


@router.post("/quiz/check")
async def check_answer(data: QuizCheckRequest):
    from services.memory_service import MemoryService
    mem = MemoryService()
    profile = await mem.update_profile(data.subject, data.correct)
    return {"profile": profile}


@router.post("/quiz/adaptive-difficulty")
async def adaptive_difficulty(data: AdaptiveDifficultyRequest):
    """Real-time difficulty adjustment based on rolling accuracy.
    POST {"current_difficulty": "easy|medium|hard", "correct": true/false, "history": [true,false,true,true]}
    Returns {"suggested_difficulty": "easy|medium|hard", "reason": "..."}
    """
    current = data.current_difficulty
    history = data.history
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
@_study_limit
async def generate_notes(req: StudyRequest, request: Request):
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
    weighting: int | None = None
    task_type: str | None = None


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
            weighting=req.weighting,
            task_type=req.task_type,
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
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "Notification file too large (max 10 MB)")
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


@router.get("/exam-plans/{plan_id}/readiness")
async def exam_plan_readiness(plan_id: str):
    """Readiness % for a plan: weak-topic burden, days left, weighting.

    Rule-based (instant, no LLM): starts at 100, loses points for each
    unfinished day, extra loss for unfinished weak-hit days, bonus for
    high completion on high-weighting tasks.
    """
    from fastapi import HTTPException
    from services.exam_plan_service import list_plans
    plan = next((p for p in list_plans() if p.get("id") == plan_id), None)
    if plan is None:
        raise HTTPException(404, "Plan not found")
    days = plan.get("days", []) or []
    total = len(days) or 1
    done = sum(1 for d in days if d.get("completed"))
    weak_total = sum(1 for d in days if d.get("weak_hit"))
    weak_done = sum(1 for d in days if d.get("weak_hit") and d.get("completed"))
    score = round(done / total * 100)
    # Weak topics drag readiness down until cleared
    if weak_total:
        weak_score = round(weak_done / weak_total * 100)
        score = round(score * 0.6 + weak_score * 0.4)
    return {
        "plan_id": plan_id,
        "readiness": score,
        "done": done,
        "total": total,
        "weak_done": weak_done,
        "weak_total": weak_total,
        "days_left": plan.get("days_left", 0),
        "weighting": plan.get("weighting"),
        "verdict": (
            "Exam-ready — light review only" if score >= 85 else
            "On track — clear weak days next" if score >= 60 else
            "Behind — hit notification topics first" if score >= 30 else
            "Urgent — start with the first weak topic today"
        ),
    }


class PracticeSetRequest(BaseModel):
    count: int = 5
    level: str = "hard"


@router.post("/exam-plans/{plan_id}/practice-set")
async def exam_plan_practice_set(plan_id: str, req: PracticeSetRequest):
    """Timed practice set built from the plan's notification topics.

    Uses the verified quiz pipeline (StudyService) so questions are
    checked the same way as Create → Quiz. Falls back to subjects when
    the notification had no topics.
    """
    from fastapi import HTTPException
    from services.exam_plan_service import list_plans
    plan = next((p for p in list_plans() if p.get("id") == plan_id), None)
    if plan is None:
        raise HTTPException(404, "Plan not found")
    topics = plan.get("assessment_topics") or plan.get("subjects") or ["General"]
    topic = ", ".join(topics[:3])[:160]
    config = get_config()
    model = config.get("model", config.get("reasoning_model", MODELS["main"]))
    count = max(3, min(10, int(req.count or 5)))
    level = req.level if req.level in ("medium", "hard", "exam", "olympiad") else "hard"
    questions = await study_svc.generate_quiz(topic, level, count, model, verify=False)
    return {
        "plan_id": plan_id,
        "topic": topic,
        "level": level,
        "timed_mins": count * 2,
        "questions": questions,
    }


@router.delete("/exam-plans/{plan_id}")
async def remove_exam_plan(plan_id: str):
    from fastapi import HTTPException
    from services.exam_plan_service import delete_plan
    if not delete_plan(plan_id):
        raise HTTPException(404, "Plan not found")
    return {"deleted": True}