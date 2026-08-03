from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import Response
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


@router.post("/assessment-plan")
async def assessment_plan(
    file: UploadFile = File(...),
    days_available: int = Form(default=7),
):
    from services.document_service import DocumentService
    doc_svc = DocumentService()
    data = await file.read()
    pages = await doc_svc.extract_pages(data, file.filename or "notification.pdf")
    full_text = "\n\n".join(f"[Page {p['page']}]\n{p['text']}" for p in pages)
    if not full_text.strip():
        full_text = f"[Filename: {file.filename}] — no text could be extracted from this PDF."
    config = get_config()
    model = config.get("reasoning_model", "qwen3:8b")
    result = await study_svc.generate_assessment_study_plan(full_text, days_available, model)
    return result


class WorksheetRequest(BaseModel):
    topic: str
    grade: str = "Year 8"
    subject: str = ""
    question_count: int = 10
    include_answers: bool = True
    difficulty: str = "mixed"


@router.post("/worksheet")
async def generate_worksheet(req: WorksheetRequest):
    config = get_config()
    model = config.get("reasoning_model", "qwen3:8b")

    # Auto-detect subject from topic if not provided
    topic = req.topic
    subject = req.subject or topic.split()[0] if topic else "General"

    # Map common course codes to subjects
    code_map = {
        'ENGD': 'English', 'MAT4': 'Mathematics', 'SCID': 'Science',
        'HSIED': 'HSIE', 'RELD': 'Religion', 'HRC3': 'History',
        'TEC2': 'Technology', 'VAR2': 'Visual Arts', 'MUSD': 'Music',
        'PDE2': 'PDHPE',
    }
    for code, sub in code_map.items():
        if code in topic.upper():
            subject = sub
            break

    worksheet = await study_svc.generate_worksheet(
        topic, req.grade, req.question_count, req.include_answers, model
    )
    return {"worksheet": worksheet, "subject": subject, "grade": req.grade}


@router.post("/check-handwriting")
async def check_handwriting(
    image: UploadFile = File(...),
    question: str = Form(default=""),
    model_answer: str = Form(default=""),
):
    """
    Check a handwritten answer photo against an expected answer.
    Vision model reads the handwriting, then the reasoning model grades it.
    """
    from services.image_service import ImageService
    from services.ollama_service import OllamaService
    from services.voice_service import VoiceService

    config = get_config()
    vision_model = config.get("vision_model", "qwen2.5vl:3b")
    reasoning_model = config.get("reasoning_model", "qwen3:8b")

    image_data = await image.read()
    mime = image.content_type or "image/jpeg"

    image_svc = ImageService()
    llm = OllamaService()
    tts = VoiceService()

    try:
        # 1) Read the handwriting with the vision model
        vision_text = await image_svc.analyse(image_data, mime, vision_model)
        await llm.unload_model(vision_model)
    except Exception as e:
        return {"error": f"Vision failed: {e}"}

    prompt = (
        "A Year 7 student wrote a handwritten answer, which was transcribed below.\n\n"
        f"QUESTION: {question}\n\n"
        f"HANDWRITTEN ANSWER (transcribed):\n{vision_text[:1500]}\n\n"
    )
    if model_answer:
        prompt += f"EXPECTED ANSWER:\n{model_answer[:1500]}\n\n"

    prompt += (
        "Grade the student's answer out of 10 like a fair Year 7 teacher.\n"
        "Consider: accuracy, completeness, and understanding.\n"
        "Then write a short friendly note with 2-3 specific tips to improve.\n"
        "Return JSON: {\"score\": 0-10, \"summary\": \"1-2 sentence summary\", "
        "\"tips\": [\"tip1\", \"tip2\", \"tip3\"]}"
    )

    try:
        raw = await llm.complete(reasoning_model, prompt,
            "You are a kind, encouraging Year 7 teacher who grades handwriting.")
        import re, json
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(m.group()) if m else {}
        score = max(0, min(10, int(data.get("score", 5))))
        summary = str(data.get("summary", ""))[:400]
        tips = [str(t)[:200] for t in data.get("tips", [])[:3]]
    except Exception as e:
        return {"error": f"Grading failed: {e}"}

    return {
        "score": score,
        "summary": summary,
        "tips": tips,
        "transcribed": vision_text[:800],
        "feedback": (
            f"Score: {score}/10\n\n{summary}\n\n"
            + "\n".join(f"• {t}" for t in tips)
        ),
    }