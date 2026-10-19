"""Per-request scope — who is making this request, service-side.

A ContextVar the gate middleware sets for every request (accounts mode:
the session user's username; local mode: 'local-owner'). Usage
attribution and credit deduction read this instead of threading user
objects through every service signature — no behaviour change for the
existing routers.
"""

from __future__ import annotations

import contextvars

_USER: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "aria_user", default=None
)


def set_user(username: str | None) -> None:
    _USER.set(username)


def current_username() -> str:
    return _USER.get() or "local-owner"
