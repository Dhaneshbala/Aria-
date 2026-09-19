"""Day 1-2 realtime voice: chunking, VAD, WS partial-STT."""

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_clean_for_speech_strips_markdown():
    from services.voice_service import clean_for_speech

    out = clean_for_speech("**Hello** `code` [link](http://x)\n\nWorld")
    assert "Hello" in out
    assert "**" not in out
    assert "http" not in out


def test_chunk_for_speech_splits_sentences():
    from services.voice_service import chunk_for_speech

    text = "Hello world. This is sentence two! Is this sentence three? Yes."
    chunks = chunk_for_speech(text, max_chars=40)
    assert len(chunks) >= 2
    assert "".join(chunks).replace(" ", "").startswith("Helloworld")
    for c in chunks:
        assert len(c) <= 40


def test_chunk_for_speech_empty():
    from services.voice_service import chunk_for_speech

    assert chunk_for_speech("") == []
    assert chunk_for_speech("   ") == []


def test_chunk_endpoint():
    from main import app

    client = TestClient(app)
    r = client.post(
        "/api/voice/chunk",
        json={
            "text": "Hello world, this is a long first sentence. Here is a second long sentence for testing. And a third one here.",
            "max_chars": 80,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 2
    assert len(data["chunks"]) == data["count"]


def test_stream_info():
    from main import app

    client = TestClient(app)
    r = client.get("/api/voice/stream-info")
    assert r.status_code == 200
    data = r.json()
    assert "chunk_endpoint" in data
    assert data["ws_transcribe"] == "/api/voice/ws-transcribe"
    assert data["ws_idle_timeout_s"] == 300
    assert data["ws_max_session_s"] == 900
    assert "entries" in data["tts_cache"]
    assert "ws_sessions" in data["stats"]


def test_audio_energy_silence_vs_loud():
    from services.voice_service import audio_energy, is_speech

    assert audio_energy(b"") == 0.0
    assert audio_energy(None) == 0.0
    assert audio_energy(b"\x00" * 1000) == 0.0
    assert not is_speech(b"\x00" * 1000)
    loud = bytes([0, 127] * 500)
    assert audio_energy(loud) > 0.02
    assert is_speech(loud)


def test_streaming_buffer_policy():
    from services.voice_service import StreamingBuffer

    buf = StreamingBuffer(max_bytes=100)
    assert len(buf) == 0
    buf.add(b"a" * 50, False)
    assert len(buf) == 50
    assert not buf.should_partial(min_bytes=60)
    buf.add(b"b" * 50, True)
    assert len(buf) == 100
    buf.add(b"c", True)  # over limit
    assert buf.over_limit
    buf.reset()
    assert len(buf) == 0 and not buf.over_limit


def test_ws_ready_vad_flush_flow():
    from main import app

    canned = {
        "text": "hello world",
        "language": "en",
        "language_prob": 0.9,
        "model": "small",
    }
    with patch("routers.voice.voice_svc") as mock_svc:
        mock_svc._transcribe_sync.return_value = canned
        client = TestClient(app)
        with client.websocket_connect("/api/voice/ws-transcribe") as ws:
            ready = ws.receive_json()
            assert ready["type"] == "ready"
            ws.send_json({"type": "config", "language": "en"})
            cfg = ws.receive_json()
            assert cfg["type"] == "ready"
            ws.send_bytes(bytes([0, 100] * 1000))
            vad = ws.receive_json()
            assert vad["type"] == "vad"
            assert "energy" in vad and "bytes" in vad
            ws.send_json({"type": "flush"})
            final = ws.receive_json()
            assert final["type"] == "final"
            assert final["transcript"] == "hello world"
            # connection stays open for another turn
            ws.send_json({"type": "reset"})
            rst = ws.receive_json()
            assert rst.get("ok") is True


def test_ws_bad_control():
    from main import app

    client = TestClient(app)
    with client.websocket_connect("/api/voice/ws-transcribe") as ws:
        ws.receive_json()  # ready
        ws.send_text("not-json{{{")
        err = ws.receive_json()
        assert err["type"] == "error"


def test_tts_cache_put_get():
    import uuid

    from services.voice_service import tts_cache_get, tts_cache_put, tts_cache_stats

    key = f"cache-test-{uuid.uuid4().hex}"
    assert tts_cache_get(key) is None
    tts_cache_put(key, b"fake-audio-bytes")
    assert tts_cache_get(key) == b"fake-audio-bytes"
    assert tts_cache_stats()["entries"] >= 1


def test_synthesize_cache_hit_miss():
    import uuid
    from unittest.mock import AsyncMock

    from main import app

    text = f"Cache me {uuid.uuid4().hex}"
    with patch("routers.voice.voice_svc") as mock_svc:
        mock_svc.synthesize_audio = AsyncMock(
            return_value=(b"cached-audio-bytes", "audio/mp4")
        )
        client = TestClient(app)
        r1 = client.post("/api/voice/synthesize", json={"text": text})
        assert r1.status_code == 200
        assert r1.headers.get("X-Cache") == "MISS"
        r2 = client.post("/api/voice/synthesize", json={"text": text})
        assert r2.status_code == 200
        assert r2.headers.get("X-Cache") == "HIT"
        assert r2.content == b"cached-audio-bytes"
        assert mock_svc.synthesize_audio.await_count == 1


def test_voice_mode_suffix_is_speakable():
    from services.orchestrator import VOICE_MODE_SUFFIX

    assert "VOICE TUTOR MODE" in VOICE_MODE_SUFFIX
    assert "no markdown" in VOICE_MODE_SUFFIX.lower()
    assert ". ! ?" in VOICE_MODE_SUFFIX
    assert "student's language" in VOICE_MODE_SUFFIX
    assert "No greetings" in VOICE_MODE_SUFFIX


async def test_orchestrate_voice_mode_adds_suffix(monkeypatch):
    import services.orchestrator as orch

    captured = {}

    class CapOllama:
        async def stream(self, model, system, message, context_window=8192, **kw):
            captured["system"] = system
            captured["think"] = kw.get("think")
            yield "Hi there."

    class NoopCitation:
        def register_sources(self, **kw):
            pass

        def parse_citations(self, text):
            return [], []

        def get_source_list(self):
            return []

    class EmptyResearch:
        async def search(self, *a, **k):
            return []

    monkeypatch.setattr(orch, "ollama", CapOllama())
    monkeypatch.setattr(orch, "memory_svc", None)
    monkeypatch.setattr(orch, "kb_svc", None)
    monkeypatch.setattr(orch, "research_svc", EmptyResearch())
    monkeypatch.setattr(orch, "citation_svc", NoopCitation())
    cfg = {
        "web_search_enabled": False,
        "memory_enabled": False,
        "knowledge_base_enabled": False,
    }
    events = [
        c
        async for c in orch.orchestrate("hello", "voice-test", config=cfg, mode="voice")
    ]
    assert events[-1].endswith('"done"}\n\n')
    assert "VOICE TUTOR MODE" in captured.get("system", "")
    # Day 40: voice never streams reasoning preambles (measured: think is the
    # whole TTFA budget on-device, and preambles can't be spoken anyway)
    assert captured.get("think") is False


async def test_orchestrate_math_still_thinks_in_normal_mode(monkeypatch):
    import services.orchestrator as orch

    captured = {}

    class CapOllama:
        async def stream(self, model, system, message, context_window=8192, **kw):
            captured["think"] = kw.get("think")
            yield "4"

    class NoopCitation:
        def register_sources(self, **kw):
            pass

        def parse_citations(self, text):
            return [], []

        def get_source_list(self):
            return []

    class EmptyResearch:
        async def search(self, *a, **k):
            return []

    monkeypatch.setattr(orch, "ollama", CapOllama())
    monkeypatch.setattr(orch, "memory_svc", None)
    monkeypatch.setattr(orch, "kb_svc", None)
    monkeypatch.setattr(orch, "research_svc", EmptyResearch())
    monkeypatch.setattr(orch, "citation_svc", NoopCitation())
    cfg = {
        "web_search_enabled": False,
        "memory_enabled": False,
        "knowledge_base_enabled": False,
    }
    [
        c
        async for c in orch.orchestrate(
            "solve 2+2", "voice-test-2", config=cfg, mode="normal"
        )
    ]
    assert captured.get("think") is True


def test_voice_stats_count_sessions_and_tts():
    from unittest.mock import AsyncMock

    from main import app

    client = TestClient(app)
    before = client.get("/api/voice/stream-info").json()["stats"]
    with client.websocket_connect("/api/voice/ws-transcribe") as ws:
        ws.receive_json()  # ready
        ws.send_json({"type": "flush"})  # empty final, no model needed
        final = ws.receive_json()
        assert final["type"] == "final"
    with patch("routers.voice.voice_svc") as mock_svc:
        import uuid

        mock_svc.synthesize_audio = AsyncMock(
            return_value=(b"stats-audio", "audio/mp4")
        )
        client.post("/api/voice/synthesize", json={"text": f"stats-{uuid.uuid4().hex}"})
    after = client.get("/api/voice/stream-info").json()["stats"]
    assert after["ws_sessions"] >= before["ws_sessions"] + 1
    assert after["ws_finals"] >= before["ws_finals"] + 1
    assert after["tts_misses"] >= before["tts_misses"] + 1


def test_verbalize_math_powers():
    from services.voice_service import verbalize_math

    assert verbalize_math("x^2 + y^3") == "x squared + y cubed"
    assert "to the power 4" in verbalize_math("x^4")
    assert "squared" in verbalize_math("x²")


def test_verbalize_math_roots_fractions_symbols():
    from services.voice_service import verbalize_math

    assert verbalize_math(r"\sqrt{16}") == "square root of 16"
    assert verbalize_math(r"\frac{1}{2}") == "1 over 2"
    assert verbalize_math("√9") == "square root of 9"
    assert verbalize_math("3 × 4") == "3 times 4"
    assert verbalize_math("10 ÷ 2") == "10 divided by 2"
    assert verbalize_math("a = b") == "a equals b"
    assert verbalize_math("1/2") == "one half"
    assert verbalize_math("50%") == "50 percent"


def test_verbalize_math_leaves_prose_alone():
    from services.voice_service import verbalize_math

    assert verbalize_math("https://example.com/a=b") == "https://example.com/a=b"
    assert verbalize_math("Due on 2026/09/17") == "Due on 2026/09/17"
    assert verbalize_math("") == ""


def test_clean_for_speech_verbalizes_equations():
    from services.voice_service import clean_for_speech

    out = clean_for_speech("Solve $x^2 + 3 = 7$.")
    assert "squared" in out
    assert "equals" in out
    assert "$" not in out


def test_pick_tts_voice_mapping():
    from services import voice_service

    with patch.object(voice_service, "installed_say_voices", return_value=None):
        assert voice_service._pick_tts_voice("ta") == "Vani"
        assert voice_service._pick_tts_voice("ta-IN") == "Vani"
        assert voice_service._pick_tts_voice("hi") == "Lekha"
        assert voice_service._pick_tts_voice("te") == "Geeta"
        assert voice_service._pick_tts_voice("ar") == "Majed"
        assert voice_service._pick_tts_voice("zh") == "Tingting"
        assert voice_service._pick_tts_voice("zh-TW") == "Meijia"
        assert voice_service._pick_tts_voice("zh-HK") == "Sinji"
        assert voice_service._pick_tts_voice("fr") == "Thomas"
        assert voice_service._pick_tts_voice("en") is None
        assert voice_service._pick_tts_voice("en-US") is None
        assert voice_service._pick_tts_voice("xx") is None
        assert voice_service._pick_tts_voice(None) is None
        assert voice_service._pick_tts_voice("auto") is None


def test_pick_tts_voice_skips_missing():
    from services import voice_service

    with patch.object(
        voice_service, "installed_say_voices", return_value=frozenset({"Samantha"})
    ):
        assert voice_service._pick_tts_voice("ta") is None
    with patch.object(
        voice_service,
        "installed_say_voices",
        return_value=frozenset({"Samantha", "Vani"}),
    ):
        assert voice_service._pick_tts_voice("ta") == "Vani"


def test_parse_say_voices():
    from services.voice_service import _parse_say_voices

    sample = "Vani                ta_IN    # Hello!\nThomas              fr_FR    # Bonjour!\n"
    assert _parse_say_voices(sample) == frozenset({"Vani", "Thomas"})
    assert _parse_say_voices("") == frozenset()


def test_synthesize_splits_cache_by_language():
    import uuid
    from unittest.mock import AsyncMock

    from main import app
    from services import voice_service

    text = f"Lang split {uuid.uuid4().hex}"
    with (
        patch("routers.voice.voice_svc") as mock_svc,
        patch.object(voice_service, "installed_say_voices", return_value=None),
    ):
        mock_svc.synthesize_audio = AsyncMock(return_value=(b"lang-audio", "audio/mp4"))
        client = TestClient(app)
        r1 = client.post("/api/voice/synthesize", json={"text": text, "language": "ta"})
        assert r1.headers.get("X-Cache") == "MISS"
        assert r1.headers.get("X-Voice") == "Vani"
        r2 = client.post("/api/voice/synthesize", json={"text": text, "language": "ta"})
        assert r2.headers.get("X-Cache") == "HIT"
        r3 = client.post("/api/voice/synthesize", json={"text": text, "language": "hi"})
        assert r3.headers.get("X-Cache") == "MISS"
        assert r3.headers.get("X-Voice") == "Lekha"
        assert mock_svc.synthesize_audio.await_count == 2


def test_stream_info_lists_tts_voices():
    from main import app

    client = TestClient(app)
    info = client.get("/api/voice/stream-info").json()
    assert "ta" in info["tts_voices"] and "hi" in info["tts_voices"]
    assert "tts_voices_installed" in info
    assert isinstance(info["tts_voices_installed"], list)
    engines = info["tts_engines"]
    assert engines["ta"] == "say"  # no Piper voice file in test DATA_DIR
    assert set(engines) >= {"en", "hi", "te", "ta"}


def test_piper_stem_mapping():
    from services.voice_service import _piper_stem

    assert _piper_stem("en") == "en_US-lessac-medium"
    assert _piper_stem(None) == "en_US-lessac-medium"
    assert _piper_stem("hi-IN") == "hi_IN-pratham-medium"
    assert _piper_stem("te") == "te_IN-maya-medium"
    assert _piper_stem("bn") == "bn_BD-google-medium"
    assert _piper_stem("ml") == "ml_IN-meera-medium"
    assert _piper_stem("mr") == "mr_IN-google-medium"
    assert _piper_stem("ur") == "ur_PK-aegis_female-medium"
    assert _piper_stem("ta") is None
    assert _piper_stem("fr") is None


def test_tts_engine_falls_back_without_files():
    import os
    from pathlib import Path

    from services import voice_service

    assert os.environ.get("ARIA_DATA_DIR", "") != str(Path.home() / ".aria_data")
    assert voice_service.tts_engine("en") == ("say", "audio/mp4")
    assert voice_service.tts_engine("ta") == ("say", "audio/mp4")


def test_tts_engine_prefers_piper_when_ready(monkeypatch, tmp_path):
    from services import voice_service

    stem = "en_US-lessac-medium"
    (tmp_path / "piper").mkdir(exist_ok=True)
    (tmp_path / "piper" / f"{stem}.onnx").write_bytes(b"fake")
    monkeypatch.setenv("ARIA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(voice_service, "piper_available", lambda: True)
    assert voice_service.tts_engine("en") == (f"piper:{stem}", "audio/wav")
    # Tamil has no Piper voice even with files present
    assert voice_service.tts_engine("ta") == ("say", "audio/mp4")


def test_synthesize_audio_empty_short_circuits():
    import asyncio
    from unittest.mock import patch as _patch

    from services.voice_service import VoiceService

    svc = VoiceService()
    with _patch("services.voice_service.subprocess") as mock_sp:
        data, mime = asyncio.run(svc.synthesize_audio("   ", "en"))
        assert data == b""
        mock_sp.run.assert_not_called()


def test_synthesize_compat_returns_bytes():
    import asyncio
    from unittest.mock import AsyncMock
    from unittest.mock import patch as _patch

    from services.voice_service import VoiceService

    svc = VoiceService()
    with _patch.object(
        VoiceService,
        "synthesize_audio",
        AsyncMock(return_value=(b"wav-bytes", "audio/wav")),
    ):
        assert asyncio.run(svc.synthesize("hi", "en")) == b"wav-bytes"


def test_ws_rapid_chunks_all_get_vad():
    from main import app

    canned = {"text": "rapid", "language": "en", "language_prob": 0.9, "model": "small"}
    with patch("routers.voice.voice_svc") as mock_svc:
        mock_svc._transcribe_sync.return_value = canned
        client = TestClient(app)
        with client.websocket_connect("/api/voice/ws-transcribe") as ws:
            ws.receive_json()  # ready
            for _ in range(5):
                ws.send_bytes(bytes([0, 100] * 500))
            vads = [ws.receive_json() for _ in range(5)]
            assert all(v["type"] == "vad" for v in vads)
            ws.send_json({"type": "flush"})
            final = ws.receive_json()
            assert final["type"] == "final"
            assert final["transcript"] == "rapid"


def test_chat_router_passes_voice_mode_through():
    from main import app

    captured = {}

    async def _fake_orchestrate(**kwargs):
        captured.update(kwargs)
        yield 'data: {"type": "done"}\n\n'

    with patch("routers.chat.orchestrate", side_effect=_fake_orchestrate):
        client = TestClient(app)
        r = client.post("/api/chat", data={"message": "hello", "mode": "voice"})
        assert r.status_code == 200
        assert captured.get("mode") == "voice"


def test_chat_router_coerces_unknown_mode():
    from main import app

    captured = {}

    async def _fake_orchestrate(**kwargs):
        captured.update(kwargs)
        yield 'data: {"type": "done"}\n\n'

    with patch("routers.chat.orchestrate", side_effect=_fake_orchestrate):
        client = TestClient(app)
        r = client.post("/api/chat", data={"message": "hello", "mode": "klingon"})
        assert r.status_code == 200
        assert captured.get("mode") == "normal"


def test_ws_rejects_oversized_chunk_but_stays_open():
    from main import app

    canned = {
        "text": "still here",
        "language": "en",
        "language_prob": 0.9,
        "model": "small",
    }
    with patch("routers.voice.voice_svc") as mock_svc:
        mock_svc._transcribe_sync.return_value = canned
        client = TestClient(app)
        with client.websocket_connect("/api/voice/ws-transcribe") as ws:
            ws.receive_json()  # ready
            ws.send_bytes(b"\x01" * (1024 * 1024 + 1))
            err = ws.receive_json()
            assert err["type"] == "error"
            assert err["code"] == "chunk_too_large"
            ws.send_bytes(bytes([0, 100] * 500))
            vad = ws.receive_json()
            assert vad["type"] == "vad"
            ws.send_json({"type": "flush"})
            final = ws.receive_json()
            assert final["type"] == "final"
            assert final["transcript"] == "still here"


def test_ws_fifth_session_gets_busy():
    import contextlib

    import routers.voice as voice_router
    from main import app

    assert voice_router._WS_ACTIVE == 0  # no leaked slots from other tests
    client = TestClient(app)
    with contextlib.ExitStack() as stack:
        conns = [
            stack.enter_context(client.websocket_connect("/api/voice/ws-transcribe"))
            for _ in range(4)
        ]
        for c in conns:
            assert c.receive_json()["type"] == "ready"
        with client.websocket_connect("/api/voice/ws-transcribe") as busy:
            msg = busy.receive_json()
            assert msg["type"] == "error"
            assert msg["code"] == "busy"
    assert voice_router._WS_ACTIVE == 0  # all slots released


def test_ws_connect_warms_whisper_in_background():
    import time as _time

    from main import app
    from services import voice_service

    with patch.object(voice_service, "_get_model") as mock_get:
        client = TestClient(app)
        with client.websocket_connect("/api/voice/ws-transcribe"):
            deadline = _time.monotonic() + 5.0
            while _time.monotonic() < deadline:
                if mock_get.called:
                    break
                _time.sleep(0.05)
        assert mock_get.called


def test_ws_rejects_non_object_control_and_long_mime():
    from main import app

    client = TestClient(app)
    with client.websocket_connect("/api/voice/ws-transcribe") as ws:
        ws.receive_json()  # ready
        ws.send_text("[1, 2, 3]")
        err = ws.receive_json()
        assert err["type"] == "error"
        assert err["code"] == "bad_json"
        ws.send_json({"type": "config", "mime": "x" * 100})
        ready = ws.receive_json()
        assert ready["type"] == "ready"
        assert ready["mime"] == "audio/webm"  # over-long mime ignored
        ws.send_json({"type": "flush"})
        assert ws.receive_json()["type"] == "final"  # still open


def test_transcribe_rejects_empty_and_oversized():
    from unittest.mock import AsyncMock

    from main import app

    client = TestClient(app)
    with patch("routers.voice.voice_svc") as mock_svc:
        mock_svc.transcribe = AsyncMock(
            return_value={
                "text": "hi",
                "language": "en",
                "language_prob": 1.0,
                "model": "small",
            }
        )
        r = client.post(
            "/api/voice/transcribe", files={"audio": ("empty.webm", b"", "audio/webm")}
        )
        assert r.status_code == 200
        assert r.json()["transcript"] == ""
        mock_svc.transcribe.assert_not_called()
    with patch("routers.voice.voice_svc") as mock_svc:
        mock_svc.transcribe = AsyncMock()
        big = b"\x01" * (26 * 1024 * 1024)
        r = client.post(
            "/api/voice/transcribe", files={"audio": ("big.webm", big, "audio/webm")}
        )
        assert r.status_code == 413
        mock_svc.transcribe.assert_not_called()


def test_languages_flag_tts_availability():
    from main import app
    from services import voice_service

    client = TestClient(app)
    with patch.object(voice_service, "installed_say_voices", return_value=None):
        r = client.get("/api/voice/languages")
    assert r.status_code == 200
    langs = {e["code"]: e for e in r.json()["languages"]}
    assert langs["ta"]["tts"] is True
    assert langs["ta"]["tts_voice"] == "Vani"
    assert langs["en"]["tts"] is False
    assert langs["en"]["tts_voice"] is None
    assert langs["ta"]["name"]  # backward-compat fields intact


def test_tts_sync_skips_empty_without_subprocess():
    from unittest.mock import patch as _patch

    from services.voice_service import VoiceService

    svc = VoiceService()
    with _patch("services.voice_service.subprocess") as mock_sp:
        assert svc._tts_sync("") == b""
        assert svc._tts_sync("   ") == b""
        mock_sp.run.assert_not_called()


def test_tts_concurrency_capped_at_two():
    import asyncio
    import threading
    import time

    from services.voice_service import VoiceService

    svc = VoiceService()
    active = 0
    peak = 0
    lock = threading.Lock()

    def _slow(text, voice=None):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return b"audio"

    svc._tts_sync = _slow  # type: ignore[method-assign]

    async def _go():
        return await asyncio.gather(*[svc.synthesize(f"day15-{i}") for i in range(4)])

    results = asyncio.run(_go())
    assert results == [b"audio"] * 4
    assert peak <= 2


def test_piper_cache_evicts_oldest(monkeypatch, tmp_path):
    import sys
    import types
    from pathlib import Path

    from services import voice_service

    (tmp_path / "piper").mkdir(exist_ok=True)
    for stem in ("v1", "v2", "v3", "v4"):
        (tmp_path / "piper" / f"{stem}.onnx").write_bytes(b"fake")
    monkeypatch.setenv("ARIA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(voice_service, "_PIPER_CACHE", {})
    monkeypatch.setattr(voice_service, "_PIPER_CACHE_MAX", 3)

    made = []

    class _FakeVoice:
        def __init__(self, stem):
            self.stem = stem
            made.append(stem)

    fake_piper = types.ModuleType("piper")
    fake_piper.PiperVoice = type(
        "P", (), {"load": staticmethod(lambda p: _FakeVoice(Path(p).stem))}
    )
    monkeypatch.setitem(sys.modules, "piper", fake_piper)

    a = voice_service._piper_voice("v1")
    voice_service._piper_voice("v2")
    voice_service._piper_voice("v3")
    assert voice_service._piper_voice("v1") is a  # refresh, still cached
    voice_service._piper_voice("v4")  # evicts v2 (oldest untouched)
    assert set(voice_service._PIPER_CACHE) == {"v1", "v3", "v4"}
    assert len(made) == 4  # v1 served from cache on re-hit
