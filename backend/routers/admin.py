"""Admin router — config, health, model management, memory."""

import datetime
import logging
import re

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from models.database import get_config, save_config
from services.memory_service import MemoryService
from services.ollama_service import OllamaService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])
ollama = OllamaService()
mem_svc = MemoryService()

# Model names go to `ollama pull` — restrict to safe chars so arbitrary
# strings (shell metachars, flags, paths) never reach the subprocess.
_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}$")


def _valid_model_name(name: str) -> bool:
    return bool(name) and bool(_MODEL_RE.match(name))


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
    h = await ollama.health()
    config = get_config()
    ok = h if isinstance(h, bool) else h.get("ok", False)
    models = h.get("models", []) if isinstance(h, dict) else []
    # Check Pollinations (free FLUX diffusion backend)
    pollinations_ok = True
    try:
        import asyncio as _aio

        from services.imagegen_service import ImageGenService

        # 4s timeout so health doesn't hang
        status = await _aio.wait_for(ImageGenService().is_available(), timeout=4)
        pollinations_ok = bool(status.get("pollinations", False))
    except Exception:
        pollinations_ok = False
    return {
        "ollama": ok,
        "installed_models": models,
        "model": config.get("model") or config.get("reasoning_model"),
        "reasoning_model": config.get("reasoning_model"),
        "vision_model": config.get("vision_model"),
        "fallback_model": config.get("fallback_model"),
        "embedding_model": config.get("embedding_model"),
        "main_model": config.get("model") or config.get("reasoning_model"),
        "pollinations": pollinations_ok,
        "image_gen_enabled": config.get("image_gen_enabled", True),
        "status": "ok" if ok else "degraded",
    }


@router.post("/models/pull")
async def pull_model(data: dict):
    """Stream model download progress."""
    model_name = data.get("model", "")
    if not model_name:
        return {"error": "model name required"}
    if not _valid_model_name(model_name):
        return {"error": "invalid model name"}

    async def stream_pull():
        async for status in ollama.pull_model(model_name):
            yield f"data: {status}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream_pull(), media_type="text/event-stream")


@router.post("/models/unload")
async def unload_model(data: dict):
    """Unload a model from RAM to free memory."""
    model_name = data.get("model", "")
    if not _valid_model_name(model_name):
        return {"error": "invalid model name"}
    await ollama.unload_model(model_name)
    return {"unloaded": True}


@router.get("/profile")
async def get_profile():
    return await mem_svc.get_profile()


@router.delete("/memory/all")
async def clear_all_memory():
    import datetime
    import shutil

    from models.database import DATA_DIR

    for fname in ["conversations.json", "study_profile.json", "titles.json"]:
        p = DATA_DIR / fname
        if p.exists():
            # Backup before wipe so old chats are recoverable
            ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            try:
                shutil.copy2(p, DATA_DIR / f"{fname}.bak-{ts}")
            except Exception:
                pass
            p.unlink()
    return {"cleared": True}


@router.get("/export/{conversation_id}")
async def export_conversation(conversation_id: str):
    turns = await mem_svc.get_conversation(conversation_id)
    return {
        "conversation_id": conversation_id,
        "turns": turns,
        "exported_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }


# ── Telemetry (opt-in, local only) ───────────────────────────────────────────


@router.get("/telemetry")
async def get_telemetry():
    """View the local telemetry summary + recent events."""
    from services.telemetry_service import get_events, summary

    return {**summary(), "recent": get_events(50)}


@router.post("/telemetry/toggle")
async def toggle_telemetry(data: dict):
    """Turn anonymous usage counters on/off (config flag)."""
    enabled = bool(data.get("enabled"))
    return save_config({"telemetry_enabled": enabled})


@router.delete("/telemetry")
async def clear_telemetry():
    """Wipe all recorded telemetry events."""
    from services.telemetry_service import clear

    clear()
    return {"cleared": True}
