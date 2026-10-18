"""ARIA Backend — FastAPI main entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

try:
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
except ImportError:
    RateLimitExceeded = None  # type: ignore
    SlowAPIMiddleware = None  # type: ignore

from config.settings import settings
from models.database import DATA_DIR
from routers import (
    admin_router,
    agent_router,
    chat_router,
    diagram_router,
    docs_router,
    imagegen_router,
    intelligence_router,
    kb_router,
    maths_router,
    mistakes_router,
    research_router,
    study_router,
    syllabus_router,
    v2_router,
    voice_router,
)
from routers.backup import router as backup_router
from routers.notebooks import router as notebooks_router
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

    _file_handler = RotatingFileHandler(
        log_file, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    _file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logging.getLogger().addHandler(_file_handler)
except Exception as e:
    logging.getLogger(__name__).debug("Rotating log handler failed: %s", e)
    try:
        _file_handler = logging.FileHandler(log_file, encoding="utf-8")
        _file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logging.getLogger().addHandler(_file_handler)
    except Exception as e2:
        logging.getLogger(__name__).debug("Log file disabled: %s", e2)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Fail-loud: bound off-localhost with no server password = open API.
    try:
        if (
            settings.aria_host not in ("127.0.0.1", "localhost", "::1")
            and not settings.aria_api_token
        ):
            logging.getLogger(__name__).warning(
                "ARIA bound to %s with NO ARIA_API_TOKEN — the API is open "
                "to the network. Set ARIA_API_TOKEN or bind 127.0.0.1.",
                settings.aria_host,
            )
    except Exception:
        pass
    # startup: idle learner + warm nomic-embed-text (12s cold → 0.1s warm)
    try:
        from services.idle_learner_service import start_idle_learner

        start_idle_learner()
    except Exception as e:
        logging.getLogger(__name__).debug("Idle learner not started: %s", e)
    try:
        import asyncio as _aio

        from models.database import MODELS as _M
        from services.ollama_service import OllamaService

        async def _warm_nomic():
            try:
                await _aio.wait_for(
                    OllamaService().embed(
                        _M.get("embedding", "nomic-embed-text"), "warmup ok"
                    ),
                    timeout=65,
                )
                logging.getLogger(__name__).info("nomic warmup ok")
            except Exception as e:
                logging.getLogger(__name__).debug("nomic warmup failed: %s", e)

        _aio.create_task(_warm_nomic())
    except Exception as e:
        logging.getLogger(__name__).debug("Warmup scheduling failed: %s", e)
    yield
    # shutdown
    try:
        from services.idle_learner_service import stop_idle_learner

        stop_idle_learner()
    except Exception as e:
        logging.getLogger(__name__).debug("Idle learner stop failed: %s", e)


app = FastAPI(title="ARIA — AI Study Assistant", version="2.1.0", lifespan=_lifespan)

# Rate limiting — protects local Ollama from abuse / tight loops.
# Shared Limiter lives in services/rate_limit.py so routers (chat) enforce
# against the SAME instance instead of raising their own disjoint state.
from services.rate_limit import limiter as _shared_limiter

if _shared_limiter:
    limiter = _shared_limiter
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    from fastapi.responses import PlainTextResponse

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return PlainTextResponse(f"Rate limited: {exc.detail}", status_code=429)


@app.middleware("http")
async def api_token_gate(request: Request, call_next):
    """Server-password gate for shared hosting.

    Off by default (empty token = today's localhost behaviour, tests
    unaffected). When ARIA_API_TOKEN is set, remote /api callers need
    `Authorization: Bearer <token>`; loopback + /api/health stay open.

    Registered BEFORE CORS (CORS wraps this) so 401 responses still carry
    CORS headers and the browser shows a clean message instead of an opaque
    network error.
    """
    if (
        settings.aria_api_token
        and request.url.path.startswith("/api")
        and request.url.path != "/api/health"
    ):
        from routers.agent import _is_loopback_host

        client = request.client
        host = client.host if client else ""
        authed = request.headers.get("authorization", "") == (
            f"Bearer {settings.aria_api_token}"
        )
        if not _is_loopback_host(host) and not authed:
            return JSONResponse(
                status_code=401,
                content={"detail": "unauthorized: server password required"},
            )
    return await call_next(request)


@app.middleware("http")
async def friendly_errors(request: Request, call_next):
    """Convert unhandled exceptions into friendly JSON + record a crash."""
    try:
        return await call_next(request)
    except Exception as e:
        logging.getLogger(__name__).exception(
            "Unhandled error on %s %s", request.method, request.url.path
        )
        try:
            from services.telemetry_service import record_crash

            record_crash("backend", e)
        except Exception as e2:
            logging.getLogger(__name__).debug("record_crash failed: %s", e2)
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


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
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
    except Exception as e:
        logging.getLogger(__name__).debug("bump_activity failed: %s", e)
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
    # structured log: method path id
    logging.getLogger("aria.request").info(
        "%s %s id=%s", request.method, request.url.path, req_id
    )
    resp = await call_next(request)
    resp.headers["X-Request-ID"] = req_id
    return resp


# Prometheus metrics (pure-ASGI, runs outside the middleware stack above)
try:
    from services.metrics import MetricsMiddleware

    app.add_middleware(MetricsMiddleware)
except Exception as e:
    logging.getLogger(__name__).debug("Metrics disabled: %s", e)


for router in [
    chat_router,
    study_router,
    docs_router,
    research_router,
    voice_router,
    admin_router,
    agent_router,
    v2_router,
    kb_router,
    intelligence_router,
    notebooks_router,
    backup_router,
    system_router,
    todos_router,
    imagegen_router,
    diagram_router,
    maths_router,
    mistakes_router,
    syllabus_router,
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
    except Exception as e:
        logging.getLogger(__name__).debug("Health ollama check failed: %s", e)
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

    # Localhost only by default — never expose ARIA (which can run file/terminal
    # operations) to the local network. Override with ARIA_HOST/ARIA_PORT env.
    # workdir is backend/, so app lives at main:app (not backend.main:app).
    uvicorn.run(
        "main:app", host=settings.aria_host, port=settings.aria_port, reload=True
    )
