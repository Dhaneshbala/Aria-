"""Request gate (Section 13 Stage 1): sessions → roles → data attribution.

``ARIA_AUTH_MODE``:
- ``local`` (default): unchanged single-user behaviour. Zero auth needed;
  everything is attributed to the built-in ``local-owner`` account.
- ``accounts``: every /api call needs `Authorization: Bearer ses_…`.
  Opening paths: /api/health, /api/auth/register, /api/auth/login.
  ``/api/admin*`` and ``/api/v2/admin*`` additionally require the
  admin/superadmin role, and **mutating** admin calls require a fresh
  step-up (``POST /api/auth/admin/unlock``, 15-minute window).

Pure-ASGI middleware (BaseHTTPMiddleware would run handlers in a separate
task and lose the user ContextVar). It stamps:
- ``scope["state"]["user"]`` / ``scope["state"]["session_token"]`` —
  readable by handlers as ``request.state.user`` (same shared dict), and
- ``services.request_scope`` ContextVar — read by usage/credit seams.

The frontend may hide controls by role; this middleware independently
enforces every permission server-side, for every request.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from services import accounts, credits, request_scope
from services.audit import log as audit_log

logger = logging.getLogger(__name__)

_OPEN_PREFIXES = ("/api/health", "/api/auth/register", "/api/auth/login")
_ADMIN_PREFIXES = ("/api/admin", "/api/v2/admin")


def _err(status: int, type_: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status, content={"error": {"type": type_, "message": message}}
    )


def _bearer_token(scope: Scope) -> str:
    for name, value in scope.get("headers") or []:
        if name == b"authorization":
            raw = value.decode("latin-1").strip()
            if raw.lower().startswith("bearer "):
                return raw[7:].strip()
    return ""


def init() -> None:
    """Create all Stage-1 tables once; run the legacy-data migration for
    accounts mode."""
    accounts._init_schema()
    credits._init_schema()
    from services import audit, feedback
    from services.budget_service import _init_schema as _budget_schema

    audit._init_schema()
    feedback._init_schema()
    _budget_schema()
    accounts.ensure_local_user()
    if accounts.accounts_enabled():
        _migrate_legacy_conversations()


def current_user(request: Any) -> dict[str, Any]:
    """The resolved user for this request (accounts or local mode)."""
    user = getattr(request.state, "user", None)
    return user if isinstance(user, dict) else accounts.ensure_local_user()


def _migrate_legacy_conversations() -> None:
    """Assign pre-accounts conversations to the first admin so old chats
    stay visible to the operator and hidden from students. Idempotent."""
    try:
        from services.memory_service import assign_legacy_conversations

        assign_legacy_conversations()
    except Exception as e:  # pragma: no cover — migration is best-effort
        logger.warning("Legacy conversation migration failed: %s", e)


class GateMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        state = scope.setdefault("state", {})

        if not accounts.accounts_enabled():
            user = accounts.ensure_local_user()
            state["user"] = user
            state["session_token"] = ""
            request_scope.set_user(user["username"])
            await self.app(scope, receive, send)
            return

        if not path.startswith("/api") or any(
            path.startswith(p) for p in _OPEN_PREFIXES
        ):
            await self.app(scope, receive, send)
            return

        token = _bearer_token(scope)
        data = accounts.resolve_session(token)
        if data is None:
            await _err(
                401,
                "invalid_session",
                "Sign in required. Send Authorization: Bearer <session token>.",
            )(scope, receive, send)
            return
        if accounts.admin_unlocked(data):
            data["admin_unlocked"] = True

        role = data.get("role", "student")
        state["user"] = data
        state["session_token"] = token
        request_scope.set_user(data["username"])

        is_admin_path = any(path.startswith(p) for p in _ADMIN_PREFIXES)
        mutating = scope.get("method", "GET").upper() not in (
            "GET",
            "HEAD",
            "OPTIONS",
        )
        if is_admin_path and role not in ("admin", "superadmin"):
            audit_log(
                data["id"],
                data["username"],
                "admin_path_denied",
                target=path,
                outcome="denied",
            )
            await _err(
                403,
                "forbidden",
                "Administrator role required for this endpoint.",
            )(scope, receive, send)
            return
        if is_admin_path and mutating and not data.get("admin_unlocked"):
            await _err(
                403,
                "admin_locked",
                "Re-verify your password within the last 15 minutes to run"
                " admin changes (POST /api/auth/admin/unlock).",
            )(scope, receive, send)
            return

        async def send_wrapped(message: Any) -> None:
            # 13D: student data must never land in shared caches.
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                headers.append((b"cache-control", b"private, no-store"))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapped)


def install(app) -> None:
    """Init schema/migrations, then register the gate."""
    init()
    app.add_middleware(GateMiddleware)
