"""Regression tests for /api/voice/* — no whisper, no TTS audio generated.

Covers: transcription shapes (dict + legacy str results), size/empty guards,
language list shape, synthesis guards and audio transport.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.voice_service import VoiceService


def _client():
    from fastapi.testclient import TestClient

    import main

    return TestClient(main.app)


def _mock_transcribe(monkeypatch, result):
    async def _t(self, data, content_type="audio/webm", language=None):
        return result

    monkeypatch.setattr(VoiceService, "transcribe", _t)


def _mock_synthesize(monkeypatch, result):
    async def _s(self, text):
        return result

    monkeypatch.setattr(VoiceService, "synthesize", _s)


class TestLanguages:
    def test_languages_shape(self):
        r = _client().get("/api/voice/languages")
        assert r.status_code == 200
        langs = r.json()["languages"]
        assert len(langs) > 50  # whisper supports ~99
        codes = {item["code"] for item in langs}
        assert {"en", "zh", "ar", "hi", "es"} <= codes
        names = [item["name"] for item in langs]
        assert names == sorted(names)  # sorted by name per the router


class TestTranscribe:
    def test_dict_result_shape(self, monkeypatch):
        _mock_transcribe(
            monkeypatch,
            {
                "text": "hello there",
                "language": "en",
                "language_prob": 0.98,
                "model": "small",
            },
        )
        r = _client().post(
            "/api/voice/transcribe", files={"audio": ("a.webm", b"RIFFDATA")}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["transcript"] == "hello there"
        assert body["language"] == "en"
        assert body["model"] == "small"
        assert body["language_prob"] == pytest.approx(0.98)

    def test_legacy_str_result(self, monkeypatch):
        _mock_transcribe(monkeypatch, "plain text result")
        r = _client().post(
            "/api/voice/transcribe", files={"audio": ("a.webm", b"RIFFDATA")}
        )
        assert r.status_code == 200
        assert r.json() == {"transcript": "plain text result"}

    def test_empty_audio_rejected(self):
        r = _client().post("/api/voice/transcribe", files={"audio": ("a.webm", b"")})
        assert r.status_code == 400
        assert "empty" in r.json()["detail"].lower()

    def test_oversize_audio_rejected(self):
        big = b"x" * (25 * 1024 * 1024 + 1)
        r = _client().post("/api/voice/transcribe", files={"audio": ("a.webm", big)})
        assert r.status_code == 413


class TestSynthesize:
    def test_audio_bytes_served(self, monkeypatch):
        _mock_synthesize(monkeypatch, b"AAC_PAYLOAD")
        r = _client().post("/api/voice/synthesize", json={"text": "Read me aloud."})
        assert r.status_code == 200
        assert r.headers["content-type"] == "audio/mp4"
        assert r.content == b"AAC_PAYLOAD"

    def test_not_available_message(self, monkeypatch):
        _mock_synthesize(monkeypatch, b"")
        r = _client().post("/api/voice/synthesize", json={"text": "hello"})
        assert r.status_code == 200
        assert "TTS not available" in r.json()["error"]

    def test_blank_text_rejected(self):
        r = _client().post("/api/voice/synthesize", json={"text": "   "})
        assert r.status_code == 400

    def test_oversize_text_rejected(self):
        r = _client().post("/api/voice/synthesize", json={"text": "a" * 2001})
        assert r.status_code == 413
        assert "max 2000" in r.json()["error"]
