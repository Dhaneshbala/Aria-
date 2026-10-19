"""ARIA Gateway — Cloud Boost proxy (Phase 0 of docs/BUSINESS.md).

    user's ARIA ──▶ THIS GATEWAY (holds ONE Anthropic key server-side)
                       │ validate gw_ token → caps left? → meter usage → Claude
                       └ per-token daily/monthly cost caps, spend ledger,
                         instant kill switch

Every dollar is checked here, BEFORE Anthropic sees the request. Run:

    GATEWAY_ADMIN_TOKEN=... ANTHROPIC_API_KEY=... \
        uvicorn --app-dir deploy gateway.main:app --port 8088

See deploy/gateway/README.md.
"""

from __future__ import annotations

import json
import logging
import secrets
from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from gateway.config import GatewayConfig, estimate_cost
from gateway.store import GatewayStore

log = logging.getLogger("aria_gateway")
APP_VERSION = "0.1.0"


def _bearer(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return None


def _err(status: int, type_: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"type": type_, "message": message}},
    )


def _observe_sse(line: str, acc: dict[str, int]) -> None:
    """Pull usage numbers out of one SSE data line (None-safe).

    message_start carries the final input-side usage; message_delta
    carries the cumulative output_tokens at end-turn.
    """
    if not line.startswith("data:"):
        return
    try:
        data = json.loads(line[5:].strip())
    except Exception:
        return
    if not isinstance(data, dict):
        return
    kind = data.get("type")
    if kind == "message_start":
        usage = (data.get("message") or {}).get("usage") or {}
        for key in (
            "input_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
            "output_tokens",
        ):
            value = usage.get(key)
            if isinstance(value, int) and value >= 0:
                acc[key] = max(acc.get(key, 0), value)
    elif kind == "message_delta":
        usage = data.get("usage") or {}
        value = usage.get("output_tokens")
        if isinstance(value, int) and value >= 0:
            acc["output_tokens"] = max(acc.get("output_tokens", 0), value)


def create_app(config: GatewayConfig | None = None) -> FastAPI:
    cfg = config or GatewayConfig.from_env()
    if not cfg.admin_token:
        log.warning("No GATEWAY_ADMIN_TOKEN configured: /admin/* is disabled.")
    store = GatewayStore(cfg.db_path)
    store.set_setting("kill_switch", store.get_setting("kill_switch") or "0")

    app = FastAPI(
        title="ARIA Gateway",
        version=APP_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    def killed() -> bool:
        return (store.get_setting("kill_switch") or "0") == "1"

    def check_token(
        request: Request,
    ) -> tuple[dict[str, Any] | None, JSONResponse | None]:
        raw = _bearer(request)
        if not raw:
            return None, _err(
                401,
                "invalid_token",
                "Authorization: Bearer gw_… required",
            )
        row = store.get_by_raw(raw)
        if row is None:
            return None, _err(401, "invalid_token", "Unknown token")
        if not row["is_active"]:
            return None, _err(403, "token_disabled", "Token revoked")
        return row, None

    def check_admin(request: Request) -> JSONResponse | None:
        expected = cfg.admin_token
        given = _bearer(request) or ""
        if expected is None:
            return _err(403, "admin_disabled", "GATEWAY_ADMIN_TOKEN is not set")
        if not secrets.compare_digest(given, expected):
            return _err(401, "invalid_admin_token", "Invalid admin token")
        return None

    # --- public ---------------------------------------------------------

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse(
            content={
                "ok": True,
                "service": "aria-gateway",
                "version": APP_VERSION,
                "kill_switch": killed(),
                "models": cfg.model_allowlist,
            }
        )

    @app.get("/v1/usage")
    async def usage(request: Request) -> JSONResponse:
        row, denial = check_token(request)
        if denial is not None:
            return denial
        spend = store.spend_for(row["id"])
        return JSONResponse(
            content={
                "token_id": row["id"],
                "label": row["label"],
                "day": spend["day"],
                "month": spend["month"],
                "spend_today_usd": spend["today_usd"],
                "daily_cap_usd": row["daily_cap_usd"],
                "spend_month_usd": spend["month_usd"],
                "monthly_cap_usd": row["monthly_cap_usd"],
                "kill_switch": killed(),
            }
        )

    @app.post("/v1/messages")
    async def messages(request: Request) -> Response:
        if killed():
            return _err(
                503,
                "kill_switch_on",
                "Gateway kill switch is on; cloud answers are disabled.",
            )
        row, denial = check_token(request)
        if denial is not None:
            return denial
        if not cfg.anthropic_api_key:
            return _err(
                503,
                "misconfigured",
                "Gateway has no ANTHROPIC_API_KEY set.",
            )

        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > cfg.max_body_bytes:
            return _err(413, "request_too_large", "Body too large.")

        try:
            body = json.loads((await request.body()) or b"null")
        except Exception:
            return _err(400, "invalid_request", "Body must be a JSON object.")
        if not isinstance(body, dict):
            return _err(400, "invalid_request", "Body must be a JSON object.")

        model = body.get("model")
        msgs = body.get("messages")
        max_tokens = body.get("max_tokens")
        if not isinstance(model, str) or model not in cfg.model_allowlist:
            return _err(
                400,
                "model_not_allowed",
                f"Allowed models: {', '.join(cfg.model_allowlist)}",
            )
        if not isinstance(msgs, list) or not msgs:
            return _err(400, "invalid_request", "messages must be a list.")
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            return _err(400, "invalid_request", "max_tokens must be positive.")
        if max_tokens > cfg.max_tokens_limit:
            return _err(
                400,
                "max_tokens_too_large",
                f"Gateway limit is {cfg.max_tokens_limit}.",
            )

        spend = store.spend_for(row["id"])
        if spend["today_usd"] >= row["daily_cap_usd"]:
            return _err(
                429,
                "daily_cap_exceeded",
                f"Daily cap ${row['daily_cap_usd']:.2f} reached; resets"
                f" {spend['day']}+1d UTC.",
            )
        if spend["month_usd"] >= row["monthly_cap_usd"]:
            return _err(
                429,
                "monthly_cap_exceeded",
                f"Monthly cap ${row['monthly_cap_usd']:.2f} reached"
                f" this month ({spend['month']}).",
            )

        upstream = cfg.upstream_base_url.rstrip("/") + "/v1/messages"
        headers = {
            "x-api-key": cfg.anthropic_api_key,
            "anthropic-version": cfg.anthropic_version,
        }
        timeout = httpx.Timeout(180.0, connect=10.0)
        try:
            if body.get("stream"):
                return await _proxy_stream(
                    cfg, store, row, body, model, upstream, headers, timeout
                )
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(upstream, json=body, headers=headers)
        except httpx.RequestError:
            log.warning("Anthropic unreachable (%s)", model)
            return _err(502, "upstream_unavailable", "Could not reach Anthropic.")

        if resp.status_code >= 400:
            # Errors cost nothing — pass the upstream verdict through.
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                media_type=resp.headers.get("content-type", "application/json"),
            )

        try:
            data = resp.json()
        except Exception:
            log.warning("Non-JSON 2xx from Anthropic; metering skipped.")
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                media_type=resp.headers.get("content-type", "application/json"),
            )
        usage = data.get("usage") or {}
        cost = estimate_cost(
            model,
            int(usage.get("input_tokens") or 0),
            int(usage.get("cache_creation_input_tokens") or 0),
            int(usage.get("cache_read_input_tokens") or 0),
            int(usage.get("output_tokens") or 0),
        )
        if cost is None:
            log.warning(
                "No usable usage block for model %s; metering skipped.",
                model,
            )
        else:
            store.record_usage(
                row["id"],
                model,
                int(usage.get("input_tokens") or 0),
                int(usage.get("cache_creation_input_tokens") or 0),
                int(usage.get("cache_read_input_tokens") or 0),
                int(usage.get("output_tokens") or 0),
                cost,
            )
        return JSONResponse(content=data)

    async def _proxy_stream(
        cfg: GatewayConfig,
        store: GatewayStore,
        row: dict[str, Any],
        body: dict[str, Any],
        model: str,
        upstream: str,
        headers: dict[str, str],
        timeout: httpx.Timeout,
    ) -> Response:
        client = httpx.AsyncClient(timeout=timeout)
        try:
            req = client.build_request("POST", upstream, json=body, headers=headers)
            resp = await client.send(req, stream=True)
        except httpx.RequestError:
            await client.aclose()
            return _err(502, "upstream_unavailable", "Could not reach Anthropic.")

        if resp.status_code >= 400:
            content = await resp.aread()
            await resp.aclose()
            await client.aclose()
            return Response(
                content=content,
                status_code=resp.status_code,
                media_type=resp.headers.get("content-type", "application/json"),
            )

        acc: dict[str, int] = {}
        buf = ""

        async def gen() -> AsyncIterator[str]:
            nonlocal buf
            try:
                async for chunk in resp.aiter_text():
                    buf += chunk
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        _observe_sse(line, acc)
                    yield chunk
            finally:
                # Runs on completion OR client disconnect: meter whatever
                # the stream reported before it ended.
                await resp.aclose()
                await client.aclose()
                cost = estimate_cost(
                    model,
                    acc.get("input_tokens", 0),
                    acc.get("cache_creation_input_tokens", 0),
                    acc.get("cache_read_input_tokens", 0),
                    acc.get("output_tokens", 0),
                )
                if cost is not None:
                    store.record_usage(
                        row["id"],
                        model,
                        acc.get("input_tokens", 0),
                        acc.get("cache_creation_input_tokens", 0),
                        acc.get("cache_read_input_tokens", 0),
                        acc.get("output_tokens", 0),
                        cost,
                    )

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={"cache-control": "no-cache"},
        )

    # --- admin ----------------------------------------------------------

    @app.get("/admin/kill")
    async def admin_kill_get(request: Request) -> Response:
        if denial := check_admin(request):
            return denial
        return JSONResponse(content={"kill_switch": killed()})

    @app.post("/admin/kill")
    async def admin_kill_post(request: Request) -> Response:
        if denial := check_admin(request):
            return denial
        try:
            body = json.loads((await request.body()) or b"null")
        except Exception:
            return _err(400, "invalid_request", "Body must be JSON.")
        if not isinstance(body, dict) or not isinstance(body.get("on"), bool):
            return _err(400, "invalid_request", 'Body: {"on": true|false}.')
        store.set_setting("kill_switch", "1" if body["on"] else "0")
        log.warning("Kill switch set to %s", body["on"])
        return JSONResponse(content={"kill_switch": killed()})

    @app.post("/admin/tokens")
    async def admin_create_token(request: Request) -> Response:
        if denial := check_admin(request):
            return denial
        try:
            body = json.loads((await request.body()) or b"null")
        except Exception:
            return _err(400, "invalid_request", "Body must be JSON.")
        if not isinstance(body, dict) or not str(body.get("label") or "").strip():
            return _err(400, "invalid_request", "label is required.")
        daily = body.get("daily_cap_usd", cfg.default_daily_cap_usd)
        monthly = body.get("monthly_cap_usd", cfg.default_monthly_cap_usd)
        if (
            not isinstance(daily, (int, float))
            or daily <= 0
            or (not isinstance(monthly, (int, float)) or monthly <= 0)
        ):
            return _err(
                400,
                "invalid_request",
                "Caps must be positive numbers (USD).",
            )
        created = store.create_token(
            str(body["label"]).strip(), float(daily), float(monthly)
        )
        log.info("Token %s created (label=%s)", created["id"], created["label"])
        return JSONResponse(status_code=201, content=created)

    @app.get("/admin/tokens")
    async def admin_list_tokens(request: Request) -> Response:
        if denial := check_admin(request):
            return denial
        now_spend = store.totals()
        tokens = store.list_tokens(now_spend["day"], now_spend["month"])
        return JSONResponse(
            content={
                "tokens": tokens,
                "day": now_spend["day"],
                "month": now_spend["month"],
            }
        )

    @app.patch("/admin/tokens/{token_id}")
    async def admin_patch_token(request: Request, token_id: int) -> Response:
        if denial := check_admin(request):
            return denial
        try:
            body = json.loads((await request.body()) or b"null")
        except Exception:
            return _err(400, "invalid_request", "Body must be JSON.")
        if not isinstance(body, dict):
            return _err(400, "invalid_request", "Body must be a JSON object.")
        updates: dict[str, Any] = {}
        if "is_active" in body:
            if not isinstance(body["is_active"], bool):
                return _err(400, "invalid_request", "is_active must be a boolean.")
            updates["is_active"] = 1 if body["is_active"] else 0
        for key in ("daily_cap_usd", "monthly_cap_usd"):
            if key in body:
                if not isinstance(body[key], (int, float)) or body[key] <= 0:
                    return _err(400, "invalid_request", f"{key} must be positive.")
                updates[key] = float(body[key])
        if "label" in body:
            if not str(body.get("label") or "").strip():
                return _err(400, "invalid_request", "label cannot be empty.")
            updates["label"] = str(body["label"]).strip()
        if not updates:
            return _err(400, "invalid_request", "Nothing to update.")
        row = store.update_token(token_id, updates)
        if row is None:
            return _err(404, "token_not_found", "No such token.")
        return JSONResponse(content=row)

    @app.get("/admin/usage")
    async def admin_usage(request: Request) -> Response:
        if denial := check_admin(request):
            return denial
        totals = store.totals()
        tokens = store.list_tokens(totals["day"], totals["month"])
        return JSONResponse(
            content={
                "day": totals["day"],
                "month": totals["month"],
                "today_usd": totals["today_usd"],
                "month_usd": totals["month_usd"],
                "today_input_tokens": totals["today_input"],
                "today_output_tokens": totals["today_output"],
                "tokens": tokens,
                "daily": store.daily_breakdown(30),
            }
        )

    return app


app = create_app()  # uvicorn --app-dir deploy gateway.main:app
