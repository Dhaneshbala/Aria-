"""
Intelligence router — Knowledge Graph, Memory Timeline, Semantic Search,
Context Compression, Smart Cleanup, Background Agents, AI Superpowers,
Study Intelligence, Coding Intelligence.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])

# Lazy-load services
_kg_svc = None
_mem_svc = None
_bg_svc = None
_superpowers = None
_study_intel = None
_coding_intel = None


def _get_kg():
    global _kg_svc
    if _kg_svc is None:
        from services.knowledge_graph_service import KnowledgeGraphService
        _kg_svc = KnowledgeGraphService()
    return _kg_svc


def _get_mem():
    global _mem_svc
    if _mem_svc is None:
        from services.memory_service import MemoryService
        _mem_svc = MemoryService()
    return _mem_svc


def _get_bg():
    global _bg_svc
    if _bg_svc is None:
        from services.background_agent_service import BackgroundAgentService
        _bg_svc = BackgroundAgentService()
    return _bg_svc


def _get_superpowers():
    global _superpowers
    if _superpowers is None:
        from services.ai_superpowers_service import AISuperpowers
        _superpowers = AISuperpowers()
    return _superpowers


def _get_study_intel():
    global _study_intel
    if _study_intel is None:
        from services.study_intelligence_service import StudyIntelligence
        _study_intel = StudyIntelligence()
    return _study_intel


def _get_coding_intel():
    global _coding_intel
    if _coding_intel is None:
        from services.coding_intelligence_service import CodingIntelligence
        _coding_intel = CodingIntelligence()
    return _coding_intel


# ═══════════════════════════════════════════════════════════════════════════════
# Knowledge Graph
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/knowledge-graph")
async def get_knowledge_graph():
    return _get_kg().get_all()


@router.get("/knowledge-graph/graph")
async def get_knowledge_graph_data(max_nodes: int = 200):
    return _get_kg().get_graph_data(max_nodes)


@router.get("/knowledge-graph/stats")
async def get_knowledge_graph_stats():
    return _get_kg().get_stats()


@router.get("/knowledge-graph/search")
async def search_knowledge_graph(q: str = ""):
    if not q.strip():
        return []
    return _get_kg().search(q)


@router.get("/knowledge-graph/node/{node_id}/connections")
async def get_node_connections(node_id: str):
    return _get_kg().get_connections(node_id)


@router.get("/knowledge-graph/type/{node_type}")
async def get_nodes_by_type(node_type: str):
    return _get_kg().get_nodes_by_type(node_type)


@router.delete("/knowledge-graph")
async def clear_knowledge_graph():
    await _get_kg().clear()
    return {"cleared": True}


# ═══════════════════════════════════════════════════════════════════════════════
# Memory Intelligence
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/memory/timeline")
async def get_memory_timeline(days: int = 30):
    return await _get_mem().get_timeline(days)


@router.get("/memory/search")
async def global_memory_search(q: str = "", limit: int = 20):
    if not q.strip():
        return []
    return await _get_mem().search_global(q, limit)


@router.post("/memory/compress")
async def compress_memory(older_than_days: int = 7):
    return await _get_mem().compress_old_conversations(older_than_days)


@router.post("/memory/cleanup")
async def cleanup_memory(max_age_days: int = 90):
    return await _get_mem().cleanup_old_memory(max_age_days)


# ═══════════════════════════════════════════════════════════════════════════════
# Background Agents
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/agents/summarise-folder")
async def summarise_folder(folder_path: str):
    return await _get_bg().summarise_folder(folder_path)


@router.post("/agents/auto-research")
async def auto_research(topic: str, depth: int = 3):
    return await _get_bg().auto_research(topic, depth)


@router.get("/agents/tasks")
async def get_tasks(status: Optional[str] = None):
    return _get_bg().get_tasks(status)


@router.delete("/agents/tasks/completed")
async def clear_completed_tasks():
    return {"cleared": _get_bg().clear_completed()}


# ═══════════════════════════════════════════════════════════════════════════════
# AI Superpowers
# ═══════════════════════════════════════════════════════════════════════════════

class PromptOptimiseRequest(BaseModel):
    prompt: str

class CritiqueRequest(BaseModel):
    response: str
    question: str

class ConfidenceRequest(BaseModel):
    response: str
    question: str

class HallucinationRequest(BaseModel):
    response: str
    context: str

class ReflectionRequest(BaseModel):
    response: str
    question: str

class DebateRequest(BaseModel):
    question: str
    models: Optional[list[str]] = None


@router.post("/superpowers/optimise-prompt")
async def optimise_prompt(req: PromptOptimiseRequest):
    result = await _get_superpowers().optimise_prompt(req.prompt)
    return {"original": req.prompt, "optimised": result}


@router.post("/superpowers/self-critique")
async def self_critique(req: CritiqueRequest):
    return await _get_superpowers().self_critique(req.response, req.question)


@router.post("/superpowers/confidence")
async def confidence_score(req: ConfidenceRequest):
    return await _get_superpowers().confidence_score(req.response, req.question)


@router.post("/superpowers/hallucination-check")
async def hallucination_check(req: HallucinationRequest):
    return await _get_superpowers().hallucination_detector(req.response, req.context)


@router.post("/superpowers/reflect")
async def reflect(req: ReflectionRequest):
    improved = await _get_superpowers().reflection_mode(req.response, req.question)
    return {"original": req.response, "improved": improved}


@router.post("/superpowers/debate")
async def multi_agent_debate(req: DebateRequest):
    return await _get_superpowers().multi_agent_debate(req.question, req.models)


# ═══════════════════════════════════════════════════════════════════════════════
# Study Intelligence
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/study/weak-topics")
async def get_weak_topics():
    return await _get_study_intel().identify_weak_topics()


@router.get("/study/suggest-next")
async def suggest_next_topic():
    return await _get_study_intel().suggest_next_topic()


@router.get("/study/revision-needs")
async def get_revision_needs():
    return await _get_study_intel().predict_revision_needs()


@router.get("/study/formulas")
async def get_learned_formulas():
    return await _get_study_intel().get_learned_formulas()


@router.get("/study/curriculum/{subject}")
async def get_curriculum(subject: str):
    context = await _get_study_intel().get_curriculum_context(subject)
    return {"subject": subject, "curriculum": context}


@router.get("/study/adaptive")
async def get_adaptive_recommendations():
    return await _get_mem().get_adaptive_recommendations()


# ═══════════════════════════════════════════════════════════════════════════════
# Coding Intelligence
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/coding/understand")
async def understand_project(path: str):
    return await _get_coding_intel().understand_project(path)


@router.get("/coding/architecture")
async def view_architecture(path: str):
    return await _get_coding_intel().view_architecture(path)


@router.get("/coding/dependencies")
async def analyse_dependencies(path: str):
    return await _get_coding_intel().analyse_dependencies(path)


@router.get("/coding/dead-code")
async def find_dead_code(path: str):
    return await _get_coding_intel().find_dead_code(path)


@router.get("/coding/security")
async def scan_security(path: str):
    return await _get_coding_intel().scan_security(path)


@router.get("/coding/changelog")
async def generate_changelog(path: str):
    result = await _get_coding_intel().generate_changelog(path)
    return {"changelog": result}


@router.get("/coding/explain")
async def explain_structure(path: str):
    result = await _get_coding_intel().explain_structure(path)
    return {"explanation": result}


@router.get("/coding/performance")
async def analyse_performance(path: str):
    result = await _get_coding_intel().analyse_performance(path)
    return {"analysis": result}
