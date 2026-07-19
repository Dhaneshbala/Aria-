from fastapi import APIRouter
from pydantic import BaseModel
from services.study_service import StudyService
from models.database import get_config

router = APIRouter(prefix="/api/study", tags=["study"])
study_svc = StudyService()


class StudyRequest(BaseModel):
    topic: str
    level: str = "medium"
    count: int = 5
    days: int = 7


class EssayRequest(BaseModel):
    essay: str
    topic: str = ""


@router.post("/quiz")
async def generate_quiz(req: StudyRequest):
    config = get_config()
    model = config.get("reasoning_model", "qwen3:8b")
    questions = await study_svc.generate_quiz(req.topic, req.level, req.count, model)
    return {"questions": questions}


@router.post("/flashcards")
async def generate_flashcards(req: StudyRequest):
    config = get_config()
    model = config.get("reasoning_model", "qwen3:8b")
    cards = await study_svc.generate_flashcards(req.topic, req.count, model)
    return {"cards": cards}


@router.post("/mindmap")
async def generate_mindmap(req: StudyRequest):
    config = get_config()
    model = config.get("reasoning_model", "qwen3:8b")
    mindmap = await study_svc.generate_mindmap(req.topic, model)
    return {"mindmap": mindmap}


@router.post("/study-plan")
async def generate_study_plan(req: StudyRequest):
    config = get_config()
    model = config.get("reasoning_model", "qwen3:8b")
    plan = await study_svc.generate_study_plan(req.topic, req.days, model)
    return {"plan": plan}


@router.post("/summary")
async def generate_summary(req: StudyRequest):
    config = get_config()
    model = config.get("reasoning_model", "qwen3:8b")
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


@router.post("/notes")
async def generate_notes(req: StudyRequest):
    config = get_config()
    model = config.get("reasoning_model", "qwen3:8b")
    notes = await study_svc.generate_notes(req.topic, model=model)
    return {"notes": notes}


@router.post("/exam")
async def generate_exam(req: StudyRequest):
    config = get_config()
    model = config.get("reasoning_model", "qwen3:8b")
    questions = await study_svc.generate_exam_questions(req.topic, req.count, model)
    return {"questions": questions, "mode": "exam"}

@router.post("/pptx")
async def generate_pptx(req: StudyRequest):
    config = get_config()
    model  = config.get("pptx_model", "qwen3:8b")
    pptx_bytes = await study_svc.generate_pptx(req.topic, req.count or 10, model)
    return Response(
        content=pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Disposition": f'attachment; filename="ARIA-{req.topic}.pptx"',
            "Content-Length": str(len(pptx_bytes)),
        }
    )


@router.post("/essay-feedback")
async def essay_feedback(req: EssayRequest):
    config = get_config()
    model = config.get("reasoning_model", "qwen3:8b")
    feedback = await study_svc.generate_essay_feedback(req.essay, req.topic, model)
    return {"feedback": feedback}


@router.post("/formula")
async def formula_reference(req: StudyRequest):
    config = get_config()
    model = config.get("reasoning_model", "qwen3:8b")
    reference = await study_svc.generate_formula_reference(req.topic, model)
    return {"reference": reference}


@router.post("/timeline")
async def timeline(req: StudyRequest):
    config = get_config()
    model = config.get("reasoning_model", "qwen3:8b")
    timeline_text = await study_svc.generate_timeline(req.topic, model)
    return {"timeline": timeline_text}