"""Prometheus metrics — request counts + latency for the always-on box.

Cardinality-safe: path labels collapse IDs (`/chat/conversations/<uuid>`
→ `/chat/conversations/{id}`) so series stay bounded.
"""

import re
import time

from prometheus_client import Counter, Histogram

REQUESTS = Counter(
    "aria_http_requests_total",
    "HTTP requests by method, route and status.",
    ["method", "route", "status"],
)
LATENCY = Histogram(
    "aria_http_request_seconds",
    "HTTP request latency by route.",
    ["route"],
)

_ID_PATTERNS = [
    (re.compile(r"/[0-9a-fA-F-]{8,}"), "/{id}"),
    (re.compile(r"/\d+"), "/{id}"),
]


def normalize_route(path: str) -> str:
    for rx, repl in _ID_PATTERNS:
        path = rx.sub(repl, path)
    return path or "/"


class MetricsMiddleware:
    """Pure-ASGI middleware (no FastAPI dependency at import time)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        route = normalize_route(scope.get("path", "/"))
        method = scope.get("method", "GET")
        start = time.perf_counter()
        status = 500

        async def send_wrapper(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            LATENCY.labels(route=route).observe(time.perf_counter() - start)
            REQUESTS.labels(method=method, route=route, status=status).inc()
