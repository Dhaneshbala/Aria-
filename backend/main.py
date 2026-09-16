"""ARIA Backend — FastAPI main entry point."""
import logging
from pathlib import Path

import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
except ImportError:
    Limiter = None  # type: ignore

from models.database import DATA_DIR
from routers import (
    chat_router, study_router, docs_router,
    research_router, voice_router, admin_router, agent_router,
    v2_router, kb_router, intelligence_router,
    imagegen_router, diagram_router, maths_router,
)
from routers.notebooks import router as notebooks_router
from routers.backup import router as backup_router
from routers.system import router as system_router
from routers.todos import router as todos_router

# Log to console AND to aria.log (used by the "send logs" support flow)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log_file = DATA_DIR / "aria.log"
try:
    from logging.handlers import RotatingFileHandler
    _file_handler = RotatingFileHandler(log_file, maxBytes=2*1024*1024, backupCount=5, encoding="utf-8")
    _file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logging.getLogger().addHandler(_file_handler)
except Exception:
    try:
        _file_handler = logging.FileHandler(log_file, encoding="utf-8")
        _file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logging.getLogger().addHandler(_file_handler)
    except Exception:
        pass  # log file is best-effort

app = FastAPI(title="ARIA — AI Study Assistant", version="2.1.0")

# Rate limiting — protects local Ollama from abuse / tight loops
if Limiter:
    limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    from fastapi.responses import PlainTextResponse
    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return PlainTextResponse(f"Rate limited: {exc.detail}", status_code=429)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ARIA_CORS_ORIGINS", "http://localhost:5173,http://localhost:4173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:4173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "microphone=(self)"
    return resp

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    import uuid
    # bump idle learner activity on any request
    try:
        from services.idle_learner_service import bump_activity
        bump_activity()
    except Exception:
        pass
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
    # structured log: method path id
    logging.getLogger("aria.request").info("%s %s id=%s", request.method, request.url.path, req_id)
    resp = await call_next(request)
    resp.headers["X-Request-ID"] = req_id
    return resp

@app.on_event("startup")
async def _start_idle_learner():
    try:
        from services.idle_learner_service import start_idle_learner
        start_idle_learner()
    except Exception as e:
        logging.getLogger(__name__).debug("Idle learner not started: %s", e)
    # Warm up nomic-embed-text so first chat doesn't timeout (12s cold start → 0.1s warm)
    try:
        import asyncio as _aio
        from services.ollama_service import OllamaService
        from models.database import MODELS as _M
        async def _warm_nomic():
            try:
                await _aio.wait_for(OllamaService().embed(_M.get("embedding", "nomic-embed-text"), "warmup ok"), timeout=65)
                logging.getLogger(__name__).info("nomic warmup ok")
            except Exception as e:
                logging.getLogger(__name__).debug("nomic warmup failed: %s", e)
        _aio.create_task(_warm_nomic())
    except Exception:
        pass

@app.on_event("shutdown")
async def _stop_idle_learner():
    try:
        from services.idle_learner_service import stop_idle_learner
        stop_idle_learner()
    except Exception:
        pass


@app.middleware("http")
async def friendly_errors(request: Request, call_next):
    """Convert unhandled exceptions into friendly JSON + record a crash."""
    try:
        return await call_next(request)
    except Exception as e:
        logging.getLogger(__name__).exception("Unhandled error on %s %s",
                                               request.method, request.url.path)
        try:
            from services.telemetry_service import record_crash
            record_crash("backend", e)
        except Exception:
            pass
        return JSONResponse(
            status_code=500,
            content={
                "detail": {
                    "type": "friendly",
                    "message": "Something went wrong on ARIA's side. "
                               "Your data is safe — please try again.",
                    "hint": "If this keeps happening, use Settings → Send logs to support.",
                }
            },
        )


for router in [
    chat_router, study_router, docs_router,
    research_router, voice_router, admin_router, agent_router,
    v2_router, kb_router, intelligence_router,
    notebooks_router,
    backup_router, system_router, todos_router,
    imagegen_router, diagram_router, maths_router,
]:
    app.include_router(router)


@app.get("/api/health")
async def health():
    import shutil
    du = shutil.disk_usage(DATA_DIR)
    free_gb = round(du.free / (1024**3), 1)
    try:
        from services.ollama_service import OllamaService
        ollama_ok = (await OllamaService().health()).get("ok", False)
    except Exception:
        ollama_ok = False
    return {
        "status": "ok",
        "version": "2.1.0",
        "ollama": ollama_ok,
        "disk_free_gb": free_gb,
        "data_dir": str(DATA_DIR),
    }


if __name__ == "__main__":
    import uvicorn
    # Localhost only — never expose ARIA (which can run file/terminal
    # operations) to the local network.
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
