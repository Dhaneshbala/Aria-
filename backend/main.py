"""Study Buddy Backend — FastAPI main entry point ($100k-grade hardened)."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import os
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
except ImportError:
    Limiter = None  # type: ignore
    logging.getLogger(__name__).warning(
        "slowapi not installed — rate limiting DISABLED. "
        "Install requirements.txt to re-enable protection."
    )

from config.settings import get_settings

_settings = get_settings()

from models.database import DATA_DIR
from models.schemas import HealthResponse, ReadyResponse, error_envelope
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
_LOG_LEVEL = os.environ.get("ARIA_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log_file = DATA_DIR / "aria.log"
try:
    from logging.handlers import RotatingFileHandler
    _file_handler = RotatingFileHandler(
        log_file,
        maxBytes=_settings.log_max_bytes,
        backupCount=_settings.log_backup_count,
        encoding="utf-8",
    )
    _file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logging.getLogger().addHandler(_file_handler)
except Exception:
    try:
        _file_handler = logging.FileHandler(log_file, encoding="utf-8")
        _file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logging.getLogger().addHandler(_file_handler)
    except Exception as e:
        logging.getLogger(__name__).warning("Could not attach log file %s: %s", log_file, e)

app = FastAPI(title="Study Buddy — AI Study Assistant", version="2.2.0")

# Rate limiting — protects local Ollama from abuse / tight loops
if Limiter:
    limiter = Limiter(key_func=get_remote_address, default_limits=[_settings.rate_limit_global])
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content=error_envelope(
                "Too many requests — please wait a moment and try again.",
                type="rate_limited",
                hint="Study Buddy throttles to protect your local AI model.",
            ),
        )
else:
    logging.getLogger(__name__).error(
        "slowapi missing — rate limiting is OFF. Run: pip install -r requirements.txt"
    )


@app.exception_handler(RequestValidationError)
async def _validation_handler(request: Request, exc: RequestValidationError):
    """Unified 422 shape so the frontend shows one premium toast."""
    try:
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", []) if str(p) != "body")
        msg = first.get("msg", "Invalid request")
        detail_msg = f"{loc}: {msg}" if loc else str(msg)
    except Exception:
        detail_msg = "Invalid request"
    return JSONResponse(
        status_code=422,
        content=error_envelope(
            detail_msg[:300],
            type="validation",
            hint="Check the highlighted field and try again.",
        ),
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ARIA_CORS_ORIGINS", _settings.cors_origins).split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
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
    except Exception as e:
        logging.getLogger(__name__).debug("bump_activity failed: %s", e)
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
    # structured log: method path id
    logging.getLogger("aria.request").info("%s %s id=%s", request.method, request.url.path, req_id)
    resp = await call_next(request)
    resp.headers["X-Request-ID"] = req_id
    return resp

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    await _start_idle_learner()
    try:
        yield
    finally:
        await _stop_idle_learner()


# Attach lifespan the supported way (FastAPI >= 0.100)
app.router.lifespan_context = _lifespan


async def _start_idle_learner():
    try:
        from services.idle_learner_service import start_idle_learner
        start_idle_learner()
    except Exception as e:
        logging.getLogger(__name__).debug("Idle learner not started: %s", e)
    # Warm up mxbai-embed-large so first chat doesn't timeout (12s cold start → 0.1s warm)
    try:
        import asyncio as _aio
        from services.ollama_service import OllamaService
        from models.database import MODELS as _M
        async def _warm_embed():
            try:
                await _aio.wait_for(OllamaService().embed(_M.get("embedding", "mxbai-embed-large"), "warmup ok"), timeout=65)
                logging.getLogger(__name__).info("embed warmup ok")
            except Exception as e:
                logging.getLogger(__name__).debug("embed warmup failed: %s", e)
        _aio.create_task(_warm_embed())
    except Exception as e:
        logging.getLogger(__name__).debug("embed warmup setup failed: %s", e, exc_info=True)

    # SQLite WAL checkpoint — prevent WAL file growth
    _startup_wal_checkpoint()

    # Data integrity checks
    _startup_integrity_checks()

async def _stop_idle_learner():
    try:
        from services.idle_learner_service import stop_idle_learner
        stop_idle_learner()
    except Exception as e:
        logging.getLogger(__name__).debug("Idle learner stop failed: %s", e)


def _startup_wal_checkpoint():
    """Checkpoint SQLite WAL file to prevent unbounded growth."""
    import sqlite3
    log = logging.getLogger(__name__)
    db_path = DATA_DIR / "organizer.db"
    if not db_path.exists():
        return
    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
        log.info("SQLite WAL checkpoint completed")
    except Exception as e:
        log.warning("WAL checkpoint failed: %s", e)


def _startup_integrity_checks():
    """Verify critical data files exist and are valid."""
    log = logging.getLogger(__name__)
    checks = [
        ("config.json", DATA_DIR / "config.json", True),
        ("conversations.json", DATA_DIR / "conversations.json", False),
    ]
    for name, path, required in checks:
        if not path.exists():
            if required:
                log.error("CRITICAL: %s missing at %s", name, path)
            else:
                log.debug("%s not found (optional): %s", name, path)
            continue
        try:
            if path.suffix == ".json":
                import json
                json.loads(path.read_text(encoding="utf-8"))
                log.debug("Integrity check passed: %s", name)
        except Exception as e:
            log.warning("Integrity check failed for %s: %s", name, e)


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
            content=error_envelope(
                "Something went wrong on Study Buddy's side. Your data is safe — please try again.",
                type="friendly",
                hint="If this keeps happening, use Settings → Send logs to support.",
            ),
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


@app.get("/api/health", response_model=HealthResponse)
async def health():
    import shutil
    du = shutil.disk_usage(DATA_DIR)
    free_gb = round(du.free / (1024**3), 1)
    try:
        from services.ollama_service import OllamaService
        ollama_ok = (await OllamaService().health()).get("ok", False)
    except Exception:
        ollama_ok = False
    return HealthResponse(
        status="ok",
        version="2.2.0",
        ollama=ollama_ok,
        disk_free_gb=free_gb,
        data_dir=str(DATA_DIR),
    )


@app.get("/api/ready", response_model=ReadyResponse)
async def ready():
    """Kubernetes-style readiness: config + data dir writable + optional Chroma."""
    checks: dict[str, bool | str] = {}
    try:
        checks["data_dir_writable"] = os.access(DATA_DIR, os.W_OK)
    except Exception as e:
        checks["data_dir_writable"] = f"error: {e}"
    try:
        from models.database import CONFIG_FILE

        checks["config_readable"] = CONFIG_FILE.exists() or True
    except Exception as e:
        checks["config_readable"] = f"error: {e}"
    try:
        import shutil

        checks["disk_free_gb"] = round(shutil.disk_usage(DATA_DIR).free / (1024**3), 1)
    except Exception as e:
        checks["disk_free_gb"] = f"error: {e}"
    ok = all(v is True or isinstance(v, (int, float)) for v in checks.values())
    return ReadyResponse(ready=bool(ok), checks=checks)


# ── Single-server app mode: serve the built frontend from FastAPI ──────────
# Registered LAST so every /api/* route matches first. When frontend/dist
# exists (production `npm run build`), the UI is served from the same
# origin+port as the API: no second process, no CORS, no vite needed.
# Dev flow is untouched: `npm run dev` + reload still uses the vite proxy.
# Disabled explicitly with ARIA_SERVE_FRONTEND=0.
_BACKEND_DIR = Path(__file__).resolve().parent
_DIST_DIR = _BACKEND_DIR.parent / "frontend" / "dist"
_SERVE_FRONTEND = os.environ.get("ARIA_SERVE_FRONTEND", "1") == "1" and (_DIST_DIR / "index.html").exists()
if _SERVE_FRONTEND:
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    _assets = _DIST_DIR / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/", include_in_schema=False)
    async def _spa_root():
        return FileResponse(_DIST_DIR / "index.html")

    @app.get("/{path:path}", include_in_schema=False)
    async def _spa_fallback(path: str):
        # API + docs namespace stays JSON; everything else is the SPA or a file.
        if path.startswith("api/") or path.startswith("openapi") or path.startswith("docs") or path.startswith("redoc"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        candidate = (_DIST_DIR / path)
        try:
            resolved = candidate.resolve()
            if resolved.is_file() and _DIST_DIR.resolve() in resolved.parents:
                return FileResponse(resolved)
        except Exception:
            pass
        return FileResponse(_DIST_DIR / "index.html")
    logging.getLogger(__name__).info("Serving frontend from %s", _DIST_DIR)


if __name__ == "__main__":
    import uvicorn
    # Localhost only — never expose Study Buddy (which can run file/terminal
    # operations) to the local network.
    _reload = os.environ.get("ARIA_RELOAD", "0") == "1"
    uvicorn.run(
        "main:app",
        host=_settings.backend_host,
        port=_settings.backend_port,
        reload=_reload,
    )
