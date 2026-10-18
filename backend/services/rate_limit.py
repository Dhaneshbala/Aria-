"""Shared rate limiter — one Limiter instance for the whole app.

SlowAPI state is kept on the Limiter object itself; creating a second one in
routers/chat.py gave the 30/min chat cap and the 120/min app cap disjoint
state (a client could chat far past 30/min while the unused app counter sat
idle). Import `limiter` here everywhere.
"""

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
except Exception:  # pragma: no cover - slowapi is an optional dependency
    limiter = None


def chat_limit(fn=None):
    """Apply the 30/minute chat decorator (no-op when slowapi is absent)."""
    if limiter is None:
        return fn if fn else (lambda f: f)

    def _wrap(f):
        return limiter.limit("30/minute")(f)

    return _wrap(fn) if fn else _wrap
