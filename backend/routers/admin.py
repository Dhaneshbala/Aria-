"""Admin router — config, health, model management, memory."""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from models.database import get_config, save_config
from services.ollama_service import OllamaService
from services.imagegen_service import ImageGenService
from services.memory_service import MemoryService
import datetime
import logging

logger = logging.getLogger(__name__)

router  = APIRouter(prefix="/api/admin", tags=["admin"])
ollama  = OllamaService()
sd_svc  = ImageGenService()
mem_svc = MemoryService()


@router.get("/config")
async def get_config_endpoint():
    return get_config()


@router.post("/config")
async def update_config(data: dict):
    return save_config(data)


@router.get("/models")
async def list_models():
    """List installed Ollama models with size."""
    models = await ollama.list_models()
    return {"models": models}


@router.get("/health")

async def health_check():
    h      = await ollama.health()
    sd_ok  = await sd_svc.is_available()
    config = get_config()
    ok     = h if isinstance(h, bool) else h.get("ok", False)
    models = h.get("models", []) if isinstance(h, dict) else []
    return {
        "ollama":             ok,
        "stable_diffusion":   sd_ok,
        "installed_models":   models,
        "reasoning_model":    config.get("reasoning_model"),
        "vision_model":       config.get("vision_model"),
        "fallback_model":     config.get("fallback_model"),
        "status":             "ok" if ok else "degraded",
    }


@router.post("/models/pull")
async def pull_model(data: dict):
    """Stream model download progress."""
    model_name = data.get("model", "")
    if not model_name:
        return {"error": "model name required"}

    async def stream_pull():
        async for status in ollama.pull_model(model_name):
            yield f"data: {status}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream_pull(), media_type="text/event-stream")


@router.post("/models/unload")
async def unload_model(data: dict):
    """Unload a model from RAM to free memory."""
    await ollama.unload_model(data.get("model", ""))
    return {"unloaded": True}


@router.get("/profile")
async def get_profile():
    return await mem_svc.get_profile()


@router.delete("/memory/all")
async def clear_all_memory():
    from pathlib import Path
    import json
    from models.database import DATA_DIR
    for fname in ["conversations.json", "study_profile.json"]:
        p = DATA_DIR / fname
        if p.exists():
            p.unlink()
    return {"cleared": True}


@router.get("/export/{conversation_id}")
async def export_conversation(conversation_id: str):
    turns = await mem_svc.get_conversation(conversation_id)
    return {
        "conversation_id": conversation_id,
        "turns": turns,
        "exported_at": datetime.datetime.utcnow().isoformat(),
    }
