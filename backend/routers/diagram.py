"""Diagram router — Napkin AI-style visuals (inline in chat, no separate page)."""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from services.diagram_service import DiagramService

router = APIRouter(prefix="/api/diagram", tags=["diagram"])
svc = DiagramService()


class DiagramRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    visual_type: str | None = Field(default=None, max_length=50)
    max_tokens: int = Field(default=700, ge=100, le=2000)


class SuggestRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)


@router.post("/generate")
async def generate_diagram(req: DiagramRequest):
    prompt = (req.prompt or "").strip()[:1200]
    if not prompt:
        return {"error": "Prompt cannot be empty"}
    return await svc.generate(
        prompt,
        visual_type=req.visual_type,
        max_tokens=max(100, min(req.max_tokens, 1200)),
    )


@router.post("/suggest")
async def suggest_diagram(req: SuggestRequest):
    """Napkin-style: 3 visual options + preview spec for the top pick."""
    prompt = (req.prompt or "").strip()[:1200]
    if not prompt:
        return {"error": "Prompt cannot be empty"}
    return await svc.suggest(prompt)


@router.get("/status")
async def diagram_status():
    try:
        from services.ollama_service import OllamaService
        from models.database import MODELS, get_config
        cfg = get_config()
        model = cfg.get("model") or cfg.get("reasoning_model") or MODELS["main"]
        health = await OllamaService().health()
        return {"ok": True, "model": model, "ollama": health.get("ok", False),
                "mode": "spec-json (no LoRA needed)"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}
