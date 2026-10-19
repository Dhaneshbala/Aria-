"""Regression tests for the document router (/api/docs/*), no Ollama needed.

Untrusted-content fencing assertions: document content must reach the LLM
prompt inside a nonce-fenced <untrusted kind="document"> block, with
UNTRUSTED RULES in the system prompt (regression for prompt injection).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ollama_service import OllamaService


def _client():
    from fastapi.testclient import TestClient

    import main

    return TestClient(main.app)


TXT_SAMPLE = (
    "Photosynthesis in plants.\n\n"
    "Plants convert sunlight into chemical energy via chloroplasts. "
    "Chlorophyll absorbs red and blue light and reflects green light.\n\n"
    "Two stages: light-dependent reactions and the Calvin cycle. "
    "Water and carbon dioxide become glucose and oxygen.\n\n"
) * 3


def _sse(text):
    return [ln[6:] for ln in text.splitlines() if ln.startswith("data: ")]


@pytest.fixture
def c():
    return _client()


class TestUpload:
    def test_upload_txt_fields(self, c):
        r = c.post(
            "/api/docs/upload", files={"file": ("cells.txt", TXT_SAMPLE.encode())}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["filename"] == "cells.txt"
        assert body["pages"] >= 1
        assert body["words"] > 10
        assert "Photosynthesis" in body["preview"]
        assert body["truncated"] is False
        # text is the capped full text; short doc stays fully included
        assert "Calvin cycle" in body["text"]

    def test_upload_oversize_rejected_413(self, c):
        big = b"x" * (50 * 1024 * 1024 + 1)
        r = c.post("/api/docs/upload", files={"file": ("big.txt", big)})
        assert r.status_code == 413
        assert "too large" in r.json()["detail"].lower()


@pytest.fixture
def stream_capture(monkeypatch):
    """Replace OllamaService.stream with a deterministic async generator.

    Records (model, system, message) per call so tests can assert the
    untrusted fence reached the prompt.
    """
    calls = []

    async def _stream(self, model, system, message, **kwargs):
        calls.append({"model": model, "system": system, "message": message})
        for chunk in ("SUMMARY ", "CHUNK "):
            yield chunk

    monkeypatch.setattr(OllamaService, "stream", _stream)
    return calls


class TestSummarise:
    def test_stream_shape_and_done(self, c, stream_capture):
        r = c.post(
            "/api/docs/summarise", files={"file": ("cells.txt", TXT_SAMPLE.encode())}
        )
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        parts = _sse(r.text)
        assert parts[-1] == "[DONE]"
        assert any("SUMMARY" in p for p in parts)

    def test_untrusted_fencing_in_prompt(self, c, stream_capture):
        r = c.post(
            "/api/docs/summarise", files={"file": ("cells.txt", TXT_SAMPLE.encode())}
        )
        assert r.status_code == 200
        assert stream_capture, "OllamaService.stream must have been called"
        call = stream_capture[0]
        assert "<untrusted" in call["message"]
        assert "</untrusted>" in call["message"]
        assert "UNTRUSTED CONTENT RULES" in call["system"]

    def test_style_and_focus_in_prompt(self, c, stream_capture):
        r = c.post(
            "/api/docs/summarise",
            files={"file": ("cells.txt", TXT_SAMPLE.encode())},
            data={"style": "detailed", "focus": "chlorophyll"},
        )
        assert r.status_code == 200
        call = stream_capture[0]
        assert "chlorophyll" in call["message"]


class TestAsk:
    def test_ask_streams_and_fences(self, c, stream_capture):
        r = c.post(
            "/api/docs/ask",
            files={"file": ("cells.txt", TXT_SAMPLE.encode())},
            data={"question": "What do chloroplasts do?"},
        )
        assert r.status_code == 200
        parts = _sse(r.text)
        assert parts[-1] == "[DONE]"
        call = stream_capture[0]
        assert "<untrusted" in call["message"]
        assert "What do chloroplasts do?" in call["message"]
        assert 'kind="document"' in call["message"]


class TestKeyPoints:
    def test_key_points_shape(self, c, monkeypatch):
        async def _complete(self, model, prompt, system="", **kwargs):
            return "1. Photosynthesis happens in chloroplasts. (Page 1)"

        monkeypatch.setattr(OllamaService, "complete", _complete)
        r = c.post(
            "/api/docs/key-points", files={"file": ("cells.txt", TXT_SAMPLE.encode())}
        )
        assert r.status_code == 200
        body = r.json()
        assert "Photosynthesis happens" in body["key_points"]
        assert body["pages"] >= 1


class TestQuotes:
    def test_quotes_shape(self, c):
        r = c.post(
            "/api/docs/quotes",
            files={"file": ("cells.txt", TXT_SAMPLE.encode())},
            data={"theme": "photosynthesis", "min_relevance": "0.0"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["theme"] == "photosynthesis"
        assert isinstance(body["quotes"], list)
        for q in body["quotes"]:
            assert {"quote", "page", "relevance"} <= set(q.keys())
        assert body["total_found"] == len(body["quotes"])
