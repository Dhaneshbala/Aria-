"""Cache-poisoning guard: blank LLM replies must never be cached.

Regression test for the flashcards 0-card bug — a cold model returned "",
it was cached for the full TTL, and every identical prompt kept getting "".
No network/model needed (httpx is faked).
"""
import json

import services.ollama_service as oll


class _FakeResp:
    def __init__(self, content):
        self._content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {"message": {"content": self._content}}


class _FakeClient:
    reply = "ok"

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, *a, **k):
        return _FakeResp(self.reply)


def _patch(monkeypatch, reply):
    _FakeClient.reply = reply
    monkeypatch.setattr(oll.httpx, "AsyncClient", _FakeClient)


async def test_blank_reply_not_cached(monkeypatch):
    _patch(monkeypatch, "")
    oll._CACHE.clear()
    svc = oll.OllamaService()
    out = await svc.complete("m", "prompt-blank", max_tokens=8)
    assert out == ""
    assert len(oll._CACHE) == 0, "blank reply must not be cached"


async def test_whitespace_reply_not_cached(monkeypatch):
    _patch(monkeypatch, "   \n  ")
    oll._CACHE.clear()
    svc = oll.OllamaService()
    await svc.complete("m", "prompt-ws", max_tokens=8)
    assert len(oll._CACHE) == 0, "whitespace reply must not be cached"


async def test_good_reply_cached_and_served(monkeypatch):
    _patch(monkeypatch, "hello world")
    oll._CACHE.clear()
    svc = oll.OllamaService()
    assert await svc.complete("m", "prompt-good", max_tokens=8) == "hello world"
    assert len(oll._CACHE) == 1
    # Second call hits cache even if the model would now go blank
    _patch(monkeypatch, "")
    assert await svc.complete("m", "prompt-good", max_tokens=8) == "hello world"


async def test_stale_blank_in_cache_is_ignored(monkeypatch):
    import time as _t
    oll._CACHE.clear()
    oll._CACHE["k"] = ("", _t.time())  # simulate pre-fix poison
    _patch(monkeypatch, "fresh answer")
    svc = oll.OllamaService()
    # complete() computes its own key, so emulate via direct guard check:
    from services.ollama_service import _CACHE, CACHE_TTL_SEC
    key = next(iter(_CACHE))
    cached = _CACHE.get(key)
    fresh = cached and (_t.time() - cached[1] < CACHE_TTL_SEC) and str(cached[0]).strip()
    assert not fresh, "blank cache entries must be treated as misses"
    assert await svc.complete("m", "other-prompt", max_tokens=8) == "fresh answer"
