"""Tests for the AI usage ledger and provider abstraction.

Covers: routing (explicit anthropic: prefix), the consent gate (cloud off by
default), provider-reported token recording, cost estimation from config
pricing, daily rollup + retention, and the strict-TLS kill switch for search.
No real API or Ollama calls — httpx/requests are faked at the client layer.
"""

import asyncio
import json
from typing import ClassVar

import pytest
import requests as _requests

import services.ollama_service as oll_mod
import services.research_service as research_mod
from config.settings import settings
from services import ai_providers
from services.ai_providers import (
    AnthropicProvider,
    ProviderDisabledError,
    resolve_provider,
)
from services.ollama_service import OllamaService
from services.usage_service import (
    LEDGER_PATH,
    _load,
    get_summary,
    record_usage,
)


def _reset_ledger():
    LEDGER_PATH.unlink(missing_ok=True)


# ── resolve_provider ─────────────────────────────────────────────────────────


def test_plain_model_routes_to_ollama():
    assert resolve_provider("qwen3.5:9b") == ("ollama", "qwen3.5:9b")


def test_anthropic_prefix_routes_to_anthropic():
    assert resolve_provider("anthropic:claude-haiku-5-5") == (
        "anthropic",
        "claude-haiku-5-5",
    )


# ── Consent gate (cloud off by default) ──────────────────────────────────────


async def test_cloud_disabled_without_consent(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(settings, "aria_cloud_consent", False)
    provider = AnthropicProvider(api_key="test-key")
    with pytest.raises(ProviderDisabledError):
        await provider.complete("claude-haiku-5-5", "hi")
    with pytest.raises(ProviderDisabledError):
        [d async for d in provider.stream("claude-haiku-5-5", "sys", "msg")]


async def test_cloud_disabled_without_key(monkeypatch):
    monkeypatch.setattr(settings, "aria_cloud_consent", True)
    monkeypatch.setattr(settings, "anthropic_api_key", "", raising=False)
    provider = AnthropicProvider(api_key=None)
    with pytest.raises(ProviderDisabledError):
        await provider.complete("claude-haiku-5-5", "hi")


def test_cloud_enabled_with_key_and_consent(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(settings, "aria_cloud_consent", True)
    AnthropicProvider(api_key="test-key")._require_enabled()  # must not raise


# ── Usage ledger ─────────────────────────────────────────────────────────────


def test_record_and_summarise():
    _reset_ledger()
    record_usage(
        provider="ollama",
        model="qwen3.5:9b",
        prompt_tokens=10,
        completion_tokens=20,
        duration_ms=100,
    )
    record_usage(provider="ollama", model="qwen3.5:9b", ok=False)
    summary = get_summary(30)
    assert summary["totals"]["requests"] == 2
    assert summary["totals"]["failures"] == 1
    assert summary["totals"]["prompt_tokens"] == 10
    assert summary["totals"]["completion_tokens"] == 20
    # Ollama is free — cost must be 0
    assert summary["totals"]["estimated_cost_usd"] == 0.0


def test_anthropic_cost_from_config():
    _reset_ledger()
    record_usage(
        provider="anthropic",
        model="claude-haiku-5-5",
        prompt_tokens=1_000_000,
        completion_tokens=1_000_000,
    )
    summary = get_summary(1)
    # verified price: $0.10 in / $0.50 out → $0.60 for 1M+1M tokens
    assert summary["totals"]["estimated_cost_usd"] == pytest.approx(0.60, abs=0.001)


def test_negative_tokens_clamped():
    _reset_ledger()
    record_usage(provider="ollama", model="m", prompt_tokens=-5)
    assert get_summary(1)["totals"]["prompt_tokens"] >= 0


def test_retention_pruning():
    _reset_ledger()
    for _ in range(150):
        record_usage(provider="ollama", model="m")
    assert len(_load()["days"]) <= 91


def test_ledger_write_is_valid_json():
    _reset_ledger()
    record_usage(provider="ollama", model="m", prompt_tokens=1)
    with open(LEDGER_PATH, encoding="utf-8") as f:
        json.load(f)  # valid JSON despite concurrent writers (atomic tmp+replace)


def test_usage_endpoints_served():
    """The /api/v2/usage endpoints return a well-formed rollup."""
    record_usage(
        provider="ollama", model="qwen3.5:9b", prompt_tokens=4, completion_tokens=6
    )
    from fastapi.testclient import TestClient

    import main

    client = TestClient(main.app)
    r = client.get("/api/v2/usage/summary?days=1")
    assert r.status_code == 200
    body = r.json()
    assert body["totals"]["prompt_tokens"] >= 4
    assert body["totals"]["completion_tokens"] >= 6
    today = client.get("/api/v2/usage/today")
    assert today.status_code == 200
    assert "providers" in today.json()["usage"]


# ── Ollama usage capture (fake streaming client, idiom from test_ollama_cache)


class _FakeStreamResp:
    sse: ClassVar[list[str]] = []

    def raise_for_status(self):
        pass

    async def aiter_lines(self):
        for line in _FakeStreamResp.sse:
            yield line

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _FakeStreamClient:
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def stream(self, *a, **k):
        return _FakeStreamResp()


async def test_ollama_stream_records_final_usage(monkeypatch):
    _reset_ledger()
    _FakeStreamResp.sse = [
        json.dumps({"message": {"content": "Hi"}, "done": False}),
        json.dumps(
            {
                "message": {"content": "!"},
                "done": True,
                "prompt_eval_count": 12,
                "eval_count": 34,
            }
        ),
    ]
    monkeypatch.setattr(oll_mod.httpx, "AsyncClient", _FakeStreamClient)
    out = ""
    async for delta in OllamaService().stream("qwen3.5:9b", "sys", "msg"):
        out += delta
    assert out == "Hi!"
    summary = get_summary(1)
    assert summary["totals"]["prompt_tokens"] == 12
    assert summary["totals"]["completion_tokens"] == 34
    assert summary["totals"]["requests"] == 1


# ── Anthropic provider (fake client matching the async-with stream pattern) ──


class _SseResp:
    sse: ClassVar[list[str]] = []

    def raise_for_status(self):
        pass

    async def aiter_lines(self):
        for line in _SseResp.sse:
            yield line

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _FakeAnthropicStreamClient:
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def stream(self, *a, **k):
        return _SseResp()


class _FakeAnthropicPostClient:
    status: ClassVar[int] = 200
    body: ClassVar[dict] = {}
    n_posts: ClassVar[int] = 0

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, *a, **k):
        import httpx

        _FakeAnthropicPostClient.n_posts += 1
        s, body = _FakeAnthropicPostClient.status, _FakeAnthropicPostClient.body

        class _Resp:
            status_code = s

            def raise_for_status(self):
                if s >= 400:
                    raise httpx.HTTPStatusError(
                        f"HTTP {s}", request=None, response=None
                    )

            def json(self):
                return body

        return _Resp()


async def test_anthropic_stream_records_cloud_usage(monkeypatch):
    monkeypatch.setattr(settings, "aria_cloud_consent", True)
    monkeypatch.setattr(settings, "anthropic_api_key", "k", raising=False)
    _reset_ledger()
    _SseResp.sse = [
        'data: {"type":"message_start","message":{"usage":{"input_tokens":4}}}',
        'data: {"type":"content_block_delta","delta":{"text":"Hi"}}',
        'data: {"type":"content_block_delta","delta":{"text":" there"}}',
        'data: {"type":"message_delta","usage":{"output_tokens":9}}',
    ]
    monkeypatch.setattr(ai_providers.httpx, "AsyncClient", _FakeAnthropicStreamClient)
    deltas = [
        d
        async for d in AnthropicProvider(api_key="k").stream(
            "claude-haiku-5-5", "sys", "msg", max_tokens=64
        )
    ]
    assert "".join(deltas) == "Hi there"
    summary = get_summary(1)
    assert summary["totals"]["prompt_tokens"] == 4
    assert summary["totals"]["completion_tokens"] == 9


def test_anthropic_no_retry_after_final_error(monkeypatch):
    """429 retried at most once, then the error surfaces — no endless loops."""
    monkeypatch.setattr(settings, "aria_cloud_consent", True)
    monkeypatch.setattr(settings, "anthropic_api_key", "k", raising=False)
    _FakeAnthropicPostClient.n_posts = 0
    _FakeAnthropicPostClient.status = 429
    _FakeAnthropicPostClient.body = {"error": {"message": "rate limited"}}
    monkeypatch.setattr(
        ai_providers.httpx, "AsyncClient", lambda *a, **k: _FakeAnthropicPostClient()
    )
    monkeypatch.setattr(ai_providers.time, "sleep", lambda s: None)

    async def run():
        try:
            await AnthropicProvider(api_key="k").complete("claude-haiku-5-5", "hi")
            return False
        except ai_providers.httpx.HTTPError:
            return True

    failed = asyncio.run(run())
    assert failed
    assert _FakeAnthropicPostClient.n_posts == 2, "exactly one retry after 429"


# ── Strict TLS kill switch (research) ────────────────────────────────────────


class _FakeRequestsGet:
    """First call raises SSLError, second call is observed for verify=…"""

    def __init__(self):
        self.calls: list[dict] = []
        self.ssl_error: Exception | None = None

    def __call__(self, url, **kwargs):
        already_tried = bool(self.calls)
        self.calls.append(kwargs)
        if self.ssl_error and not already_tried:
            raise self.ssl_error
        return type("R", (), {"raise_for_status": lambda s: None, "status_code": 200})()


def test_search_strict_tls_disables_fallback(monkeypatch):
    fake = _FakeRequestsGet()
    fake.ssl_error = _requests.exceptions.SSLError("bad cert")
    settings.search_strict_tls = True
    try:
        monkeypatch.setattr(research_mod.requests, "get", fake)
        with pytest.raises(_requests.exceptions.SSLError):  # strict: fail loudly
            research_mod._get("https://example.com", timeout=1)
        assert len(fake.calls) == 1  # no second (insecure) attempt
    finally:
        settings.search_strict_tls = False


def test_search_tls_fallback_remains_by_default(monkeypatch):
    fake = _FakeRequestsGet()
    fake.ssl_error = _requests.exceptions.SSLError("bad cert")
    settings.search_strict_tls = False
    monkeypatch.setattr(research_mod.requests, "get", fake)
    resp = research_mod._get("https://example.com", timeout=1)  # fallback path
    assert resp is not None
    assert fake.calls[0]["verify"] is True  # first attempt verifies
    assert fake.calls[1]["verify"] is False  # logged downgrade for school proxies
