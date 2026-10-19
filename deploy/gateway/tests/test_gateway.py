"""Gateway e2e against a mocked Anthropic upstream (respx) — the Phase 0
gate in docs/BUSINESS.md: "Mock-e2e green, docs done".

No real API key, no network: respx intercepts every httpx call the app
makes, so the full request path is exercised — auth, kill switch,
allowlist, clamps, caps, metering math, SSE accounting, admin flows.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import respx
from fastapi.testclient import TestClient
from gateway.config import GatewayConfig
from gateway.main import create_app

SONNET = "claude-sonnet-5-5"
UPSTREAM = "https://api.anthropic.com/v1/messages"
ADMIN = {"Authorization": "Bearer admin-test"}

# A response worth $0.002306: (100 + 1.25*40 + 0.05*60)/1e6 * $2
# + 200/1e6 * $10.
RAW_USAGE = {
    "input_tokens": 100,
    "cache_creation_input_tokens": 40,
    "cache_read_input_tokens": 60,
    "output_tokens": 200,
}
UPSTREAM_BODY = {
    "id": "msg_01",
    "type": "message",
    "role": "assistant",
    "model": SONNET,
    "content": [{"type": "text", "text": "hi"}],
    "stop_reason": "end_turn",
    "usage": RAW_USAGE,
}

SSE_FULL = (
    "event: message_start\n"
    'data: {"type":"message_start","message":{"id":"msg_01","type":"message",'
    '"role":"assistant","model":"claude-sonnet-5-5","usage":'
    '{"input_tokens":100,"cache_creation_input_tokens":40,'
    '"cache_read_input_tokens":60,"output_tokens":1}}}\n'
    "\n"
    "event: content_block_delta\n"
    'data: {"type":"content_block_delta","delta":{"type":"text_delta",'
    '"text":"hello"}}\n'
    "\n"
    "event: message_delta\n"
    'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},'
    '"usage":{"output_tokens":42}}\n'
    "\n"
    "event: message_stop\n"
    'data: {"type":"message_stop"}\n'
    "\n"
)  # worth $0.000726 (output 42 instead of 200)

# Stream cut before message_delta: only input-side usage is known, and
# output stays at the message_start value (1).
SSE_TRUNCATED = SSE_FULL.split("event: content_block_delta")[0] + (
    'event: message_stop\ndata: {"type":"message_stop"}\n\n'
)


def make_config(tmp_path: Path, **over: object) -> GatewayConfig:
    defaults = {
        "admin_token": "admin-test",
        "anthropic_api_key": "sk-test-key",
        "db_path": str(tmp_path / "gw.sqlite3"),
        "model_allowlist": [SONNET],
        "default_daily_cap_usd": 1.0,
        "default_monthly_cap_usd": 10.0,
        "max_tokens_limit": 2048,
    }
    defaults.update(over)
    return GatewayConfig(**defaults)


def make_token(client: TestClient, **over: object) -> dict:
    resp = client.post("/admin/tokens", json={"label": "t", **over}, headers=ADMIN)
    assert resp.status_code == 201, resp.text
    return resp.json()


def user(raw_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw_token}"}


def chat_body(**over: object) -> dict:
    return {
        "model": SONNET,
        "max_tokens": 512,
        "messages": [{"role": "user", "content": "hi"}],
        **over,
    }


def mocked_upstream(
    body: dict = UPSTREAM_BODY, status_code: int = 200
) -> respx.MockRouter:
    """Intercept Anthropic calls with a fixed non-stream response."""
    router = respx.mock(assert_all_called=False)
    router.post(UPSTREAM).respond(json=body, status_code=status_code)
    return router


# ---------------------------------------------------------------- health


def test_health_is_public(tmp_path: Path) -> None:
    app = create_app(make_config(tmp_path))
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["models"] == [SONNET]


# ------------------------------------------------------------------ auth


def test_rejects_missing_and_unknown_tokens(tmp_path: Path) -> None:
    app = create_app(make_config(tmp_path))
    with mocked_upstream(), TestClient(app) as client:
        assert client.post("/v1/messages", json=chat_body()).status_code == 401
        assert (
            client.post(
                "/v1/messages", json=chat_body(), headers=user("gw_nope")
            ).status_code
            == 401
        )
        assert client.get("/v1/usage").status_code == 401


def test_disabled_token_is_refused(tmp_path: Path) -> None:
    app = create_app(make_config(tmp_path))
    with mocked_upstream(), TestClient(app) as client:
        tok = make_token(client)
        patched = client.patch(
            f"/admin/tokens/{tok['id']}",
            json={"is_active": False},
            headers=ADMIN,
        )
        assert patched.status_code == 200
        assert patched.json()["is_active"] == 0
        resp = client.post("/v1/messages", json=chat_body(), headers=user(tok["token"]))
        assert resp.status_code == 403
        assert resp.json()["error"]["type"] == "token_disabled"


# --------------------------------------------------- kill switch + config


def test_kill_switch_blocks_and_persists(tmp_path: Path) -> None:
    cfg = make_config(tmp_path)
    app = create_app(cfg)
    with TestClient(app) as client:
        tok = make_token(client)
        assert (
            client.post("/admin/kill", json={"on": True}, headers=ADMIN).status_code
            == 200
        )
        resp = client.post("/v1/messages", json=chat_body(), headers=user(tok["token"]))
        assert resp.status_code == 503
        assert resp.json()["error"]["type"] == "kill_switch_on"

    # Restart on the same database: the switch survives.
    app2 = create_app(make_config(tmp_path))
    with TestClient(app2) as client:
        tok = make_token(client)
        resp = client.post("/v1/messages", json=chat_body(), headers=user(tok["token"]))
        assert resp.status_code == 503
        assert (
            client.post("/admin/kill", json={"on": False}, headers=ADMIN).status_code
            == 200
        )


def test_no_api_key_is_misconfigured(tmp_path: Path) -> None:
    app = create_app(make_config(tmp_path, anthropic_api_key=None))
    with mocked_upstream(), TestClient(app) as client:
        tok = make_token(client)
        resp = client.post("/v1/messages", json=chat_body(), headers=user(tok["token"]))
        assert resp.status_code == 503
        assert resp.json()["error"]["type"] == "misconfigured"


def test_admin_is_gated(tmp_path: Path) -> None:
    app = create_app(make_config(tmp_path))
    with TestClient(app) as client:
        assert client.get("/admin/usage").status_code == 401
        assert (
            client.get(
                "/admin/usage", headers={"Authorization": "Bearer wrong"}
            ).status_code
            == 401
        )

    # And with no admin token configured at all, admin is disabled.
    app2 = create_app(make_config(tmp_path, admin_token=None))
    with TestClient(app2) as client:
        assert client.get("/admin/usage").status_code == 403


# ---------------------------------------------------- request validation


def test_model_outside_allowlist(tmp_path: Path) -> None:
    app = create_app(make_config(tmp_path))
    with mocked_upstream(), TestClient(app) as client:
        tok = make_token(client)
        resp = client.post(
            "/v1/messages",
            json=chat_body(model="claude-opus-5-5"),
            headers=user(tok["token"]),
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["type"] == "model_not_allowed"
        # No spend was recorded.
        usage = client.get("/v1/usage", headers=user(tok["token"])).json()
        assert usage["spend_today_usd"] == 0


def test_max_tokens_above_clamp(tmp_path: Path) -> None:
    app = create_app(make_config(tmp_path, max_tokens_limit=1000))
    with mocked_upstream(), TestClient(app) as client:
        tok = make_token(client)
        resp = client.post(
            "/v1/messages",
            json=chat_body(max_tokens=1001),
            headers=user(tok["token"]),
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["type"] == "max_tokens_too_large"


def test_oversized_body_rejected(tmp_path: Path) -> None:
    app = create_app(
        make_config(
            tmp_path,
            max_body_bytes=10,
        )
    )
    with mocked_upstream(), TestClient(app) as client:
        tok = make_token(client)
        resp = client.post("/v1/messages", json=chat_body(), headers=user(tok["token"]))
        assert resp.status_code == 413


# ---------------------------------------------------------------- metering


def test_ok_call_passes_through_and_bills_exact_cost(tmp_path: Path) -> None:
    app = create_app(make_config(tmp_path))
    with respx.mock(assert_all_called=False) as mock, TestClient(app) as client:
        route = mock.post(UPSTREAM).respond(json=UPSTREAM_BODY, status_code=200)
        tok = make_token(client)
        raw = tok["token"]
        resp = client.post("/v1/messages", json=chat_body(), headers=user(raw))
        assert resp.status_code == 200
        assert resp.json() == UPSTREAM_BODY  # verbatim passthrough

        # The upstream saw our key, not the user's gateway token, and the
        # model rides the pinned version header.
        sent = route.calls.last.request
        assert sent.headers["x-api-key"] == "sk-test-key"
        assert sent.headers["anthropic-version"] == "2023-06-01"

        usage = client.get("/v1/usage", headers=user(raw)).json()
        assert abs(usage["spend_today_usd"] - 0.002306) < 1e-9
        assert abs(usage["spend_month_usd"] - 0.002306) < 1e-9
        assert usage["daily_cap_usd"] == 1.0


def test_daily_cap_blocks_after_first_call(tmp_path: Path) -> None:
    app = create_app(make_config(tmp_path, default_daily_cap_usd=0.001))
    with mocked_upstream(), TestClient(app) as client:
        tok = make_token(client, daily_cap_usd=0.001)
        raw = tok["token"]
        # First call passes the pre-check, spends past the cap (bounded
        # overshoot by max_tokens clamp), second call is refused.
        assert (
            client.post("/v1/messages", json=chat_body(), headers=user(raw)).status_code
            == 200
        )
        resp = client.post("/v1/messages", json=chat_body(), headers=user(raw))
        assert resp.status_code == 429
        assert resp.json()["error"]["type"] == "daily_cap_exceeded"


def test_monthly_cap_blocks(tmp_path: Path) -> None:
    app = create_app(
        make_config(
            tmp_path,
            default_daily_cap_usd=100.0,
            default_monthly_cap_usd=0.001,
        )
    )
    with mocked_upstream(), TestClient(app) as client:
        tok = make_token(client, monthly_cap_usd=0.001)
        raw = tok["token"]
        assert (
            client.post("/v1/messages", json=chat_body(), headers=user(raw)).status_code
            == 200
        )
        resp = client.post("/v1/messages", json=chat_body(), headers=user(raw))
        assert resp.status_code == 429
        assert resp.json()["error"]["type"] == "monthly_cap_exceeded"


def test_upstream_error_passthrough_no_spend(tmp_path: Path) -> None:
    app = create_app(make_config(tmp_path))
    with (
        mocked_upstream(body={"error": "boom"}, status_code=500),
        TestClient(app) as client,
    ):
        tok = make_token(client)
        raw = tok["token"]
        resp = client.post("/v1/messages", json=chat_body(), headers=user(raw))
        assert resp.status_code == 500
        assert resp.json()["error"] == "boom"
        usage = client.get("/v1/usage", headers=user(raw)).json()
        assert usage["spend_today_usd"] == 0


def test_upstream_outage_is_a_502(tmp_path: Path) -> None:
    app = create_app(make_config(tmp_path))
    with respx.mock(assert_all_called=False) as mock, TestClient(app) as client:
        mock.post(UPSTREAM).mock(side_effect=httpx.ConnectError("down"))
        tok = make_token(client)
        resp = client.post("/v1/messages", json=chat_body(), headers=user(tok["token"]))
        assert resp.status_code == 502
        assert resp.json()["error"]["type"] == "upstream_unavailable"


# ------------------------------------------------------------- streaming


def test_stream_sse_passthrough_and_metering(tmp_path: Path) -> None:
    app = create_app(make_config(tmp_path))
    with respx.mock(assert_all_called=False) as mock, TestClient(app) as client:
        mock.post(UPSTREAM).respond(
            content=SSE_FULL.encode("utf-8"),
            headers={"content-type": "text/event-stream"},
        )
        tok = make_token(client)
        raw = tok["token"]
        with client.stream(
            "POST", "/v1/messages", json=chat_body(stream=True), headers=user(raw)
        ) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            streamed = "".join(resp.iter_text())
        assert streamed == SSE_FULL  # byte-faithful passthrough
        assert "message_stop" in streamed

        usage = client.get("/v1/usage", headers=user(raw)).json()
        # out 42 × $10/MTok → $0.00042; inputs $0.000306 → $0.000726 total.
        assert abs(usage["spend_today_usd"] - 0.000726) < 1e-9


def test_truncated_stream_bills_whatever_arrived(tmp_path: Path) -> None:
    app = create_app(make_config(tmp_path))
    with respx.mock(assert_all_called=False) as mock, TestClient(app) as client:
        mock.post(UPSTREAM).respond(
            content=SSE_TRUNCATED.encode("utf-8"),
            headers={"content-type": "text/event-stream"},
        )
        tok = make_token(client)
        raw = tok["token"]
        with client.stream(
            "POST", "/v1/messages", json=chat_body(stream=True), headers=user(raw)
        ) as resp:
            assert resp.status_code == 200
            "".join(resp.iter_text())

        usage = client.get("/v1/usage", headers=user(raw)).json()
        # Input side fully recorded; output stays at message_start's 1.
        # Inputs: (100 + 1.25*40 + 0.05*60) × $2/MTok = $0.000306,
        # plus 1 output token = $0.00001 → $0.000316.
        assert abs(usage["spend_today_usd"] - 0.000316) < 1e-9


# ------------------------------------------------------------------ admin


def test_admin_token_lifecycle_and_usage_overview(tmp_path: Path) -> None:
    app = create_app(make_config(tmp_path))
    with mocked_upstream(), TestClient(app) as client:
        tok = make_token(client, label="pilot-user")
        raw = tok["token"]
        assert raw.startswith("gw_") and len(raw) == 35

        # The list shows hashed tokens, never the raw value; per-token
        # spend is included.
        listing = client.get("/admin/tokens", headers=ADMIN).json()
        assert listing["tokens"][0]["id"] == tok["id"]
        assert raw not in json.dumps(listing)
        assert listing["tokens"][0]["spend_today_usd"] == 0

        assert (
            client.post("/v1/messages", json=chat_body(), headers=user(raw)).status_code
            == 200
        )

        overview = client.get("/admin/usage", headers=ADMIN).json()
        assert abs(overview["today_usd"] - 0.002306) < 1e-9
        assert abs(overview["tokens"][0]["spend_today_usd"] - 0.002306) < 1e-9
        days = overview["daily"]
        assert len(days) == 1
        assert abs(days[0]["cost_usd"] - 0.002306) < 1e-9


def test_admin_caps_and_label_updates(tmp_path: Path) -> None:
    app = create_app(make_config(tmp_path))
    with mocked_upstream(), TestClient(app) as client:
        tok = make_token(client)
        patched = client.patch(
            f"/admin/tokens/{tok['id']}",
            json={"daily_cap_usd": 2.5, "label": "renamed"},
            headers=ADMIN,
        )
        assert patched.status_code == 200
        assert patched.json()["daily_cap_usd"] == 2.5
        assert patched.json()["label"] == "renamed"

        bad = client.patch(
            f"/admin/tokens/{tok['id']}",
            json={"daily_cap_usd": -3},
            headers=ADMIN,
        )
        assert bad.status_code == 400
        missing = client.patch("/admin/tokens/999", json={"label": "x"}, headers=ADMIN)
        assert missing.status_code == 404
