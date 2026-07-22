"""
Extended Intelligence router — Analytics, Gamification, Automation, Utilities,
NSW Curriculum, Advanced Study Intelligence.
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/v2", tags=["v2"])

# Lazy-load services
_analytics = None
_gamification = None
_automation = None
_utilities = None
_curriculum = None
_advanced_study = None


def _svc(name):
    global _analytics, _gamification, _automation, _utilities, _curriculum, _advanced_study
    if name == "analytics":
        if _analytics is None:
            from services.analytics_service import AnalyticsService
            _analytics = AnalyticsService()
        return _analytics
    if name == "gamification":
        if _gamification is None:
            from services.gamification_service import GamificationService
            _gamification = GamificationService()
        return _gamification
    if name == "automation":
        if _automation is None:
            from services.automation_service import AutomationService
            _automation = AutomationService()
        return _automation
    if name == "utilities":
        if _utilities is None:
            from services.utility_tools_service import UtilityToolsService
            _utilities = UtilityToolsService()
        return _utilities
    if name == "curriculum":
        if _curriculum is None:
            from services.nsw_curriculum_service import NSWCurriculumService
            _curriculum = NSWCurriculumService()
        return _curriculum
    if name == "advanced_study":
        if _advanced_study is None:
            from services.advanced_study_service import AdvancedStudyIntelligence
            _advanced_study = AdvancedStudyIntelligence()
        return _advanced_study


# ═══════════════════════════════════════════════════════════════════════════════
# Analytics Dashboard
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/analytics/heatmap")
async def get_heatmap(months: int = 6):
    return _svc("analytics").get_heatmap(months)


@router.get("/analytics/trends")
async def get_trends(days: int = 30):
    return _svc("analytics").get_trends(days)


@router.get("/analytics/predicted-grades")
async def get_predicted_grades():
    return _svc("analytics").get_predicted_grades()


@router.get("/analytics/focus-score")
async def get_focus_score():
    return _svc("analytics").get_focus_score()


@router.get("/analytics/weekly-summary")
async def get_weekly_summary():
    return _svc("analytics").get_weekly_summary()


# ═══════════════════════════════════════════════════════════════════════════════
# Gamification
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/game/progress")
async def get_game_progress():
    return _svc("gamification").get_progress()


@router.get("/game/challenge")
async def get_challenge():
    return _svc("gamification").get_challenge()


@router.get("/game/leaderboard")
async def get_leaderboard():
    return _svc("gamification").get_leaderboard()


# ═══════════════════════════════════════════════════════════════════════════════
# Automation
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/auto/flashcards-from-pdf")
async def auto_flashcards(file: UploadFile = File(...), count: int = Form(default=10)):
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 50MB)")
    return await _svc("automation").auto_flashcards_from_pdf(content, file.filename or "document", count)


@router.post("/auto/quiz-from-notes")
async def auto_quiz(file: UploadFile = File(...), count: int = Form(default=5)):
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 50MB)")
    return await _svc("automation").quiz_from_notes(content, file.filename or "notes", count)


@router.post("/auto/summarise-paper")
async def summarise_paper(file: UploadFile = File(...)):
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 50MB)")
    return await _svc("automation").summarise_paper_pipeline(content, file.filename or "paper")


# ═══════════════════════════════════════════════════════════════════════════════
# Utility Tools
# ═══════════════════════════════════════════════════════════════════════════════

class SummariseRequest(BaseModel):
    text: str
    level: str = "paragraph"

class CitationRequest(BaseModel):
    source: dict
    style: str = "apa"

class ConvertRequest(BaseModel):
    value: float
    from_unit: str
    to_unit: str

class PlotRequest(BaseModel):
    expression: str
    x_min: float = -10
    x_max: float = 10

class VoiceToCardsRequest(BaseModel):
    transcript: str
    count: int = 5


@router.post("/util/summarise")
async def summarise(req: SummariseRequest):
    return await _svc("utilities").smart_summarise(req.text, req.level)


@router.post("/util/citation")
async def citation(req: CitationRequest):
    result = _svc("utilities").generate_citation(req.source, req.style)
    return {"citation": result, "style": req.style}


@router.post("/util/convert")
async def convert(req: ConvertRequest):
    return _svc("utilities").convert_unit(req.value, req.from_unit, req.to_unit)


@router.post("/util/plot")
async def plot(req: PlotRequest):
    return _svc("utilities").plot_function(req.expression, req.x_min, req.x_max)


@router.post("/util/voice-to-cards")
async def voice_to_cards(req: VoiceToCardsRequest):
    return await _svc("utilities").voice_to_flashcards(req.transcript, req.count)


# ═══════════════════════════════════════════════════════════════════════════════
# NSW Curriculum
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/curriculum/stages")
async def get_stages():
    return _svc("curriculum").get_stages()


@router.get("/curriculum/klas")
async def get_klas():
    return _svc("curriculum").get_klas()


@router.get("/curriculum/subject/{kla}/stage/{stage}")
async def get_subject_content(kla: str, stage: str):
    return {
        "kla": kla,
        "stage": stage,
        "outcomes": _svc("curriculum").get_outcomes(kla, stage),
        "content": _svc("curriculum").get_subject_content(kla, stage),
    }


@router.get("/curriculum/hsc")
async def get_hsc_subjects():
    return _svc("curriculum").get_hsc_subjects()


@router.get("/curriculum/search")
async def search_curriculum(q: str = ""):
    if not q.strip():
        return []
    return _svc("curriculum").search_curriculum(q)


@router.get("/curriculum/age/{age}")
async def get_curriculum_for_age(age: int):
    from services.advanced_study_service import AdvancedStudyIntelligence
    return AdvancedStudyIntelligence().get_curriculum_for_age(age)


@router.get("/curriculum/progression/{kla}")
async def get_progression(kla: str):
    return _svc("curriculum").get_learning_progression(kla)


# ═══════════════════════════════════════════════════════════════════════════════
# Advanced Study Intelligence (NSW-aware)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/study/exam-readiness/{subject}")
async def exam_readiness(subject: str, days: int = 14):
    return await _svc("advanced_study").calculate_exam_readiness(subject, days)


@router.get("/study/knowledge-gaps/{subject}")
async def knowledge_gaps(subject: str):
    return await _svc("advanced_study").find_knowledge_gaps(subject)


@router.post("/study/gap-plan")
async def gap_study_plan(subject: str, days: int = 7):
    return await _svc("advanced_study").generate_gap_study_plan(subject, days)


@router.get("/study/learning-style")
async def learning_style():
    return await _svc("advanced_study").detect_learning_style()


@router.get("/study/due-cards")
async def due_cards(subject: str | None = None, limit: int = 20):
    return await _svc("advanced_study").get_due_cards(subject, limit)


@router.get("/study/sr-stats")
async def sr_stats():
    return await _svc("advanced_study").get_sr_stats()


class AddCardRequest(BaseModel):
    front: str
    back: str
    subject: str = "general"

class ReviewCardRequest(BaseModel):
    card_id: str
    quality: int  # 0-5

@router.post("/study/add-card")
async def add_card(req: AddCardRequest):
    return await _svc("advanced_study").add_flashcard(req.front, req.back, req.subject)


@router.post("/study/review-card")
async def review_card(req: ReviewCardRequest):
    return await _svc("advanced_study").review_flashcard(req.card_id, req.quality)
