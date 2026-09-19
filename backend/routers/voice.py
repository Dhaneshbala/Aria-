from typing import Optional
import asyncio
import json
import logging
import threading
from fastapi import APIRouter, UploadFile, File, Form, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from services.voice_service import VoiceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])
voice_svc = VoiceService()

# Day 46: rate-limit the CPU-heavy endpoints (house pattern from chat.py).
# No-op where slowapi isn't installed; synthesize gets a generous budget
# because one spoken answer fans out to many sentence requests.
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    _voice_limiter = Limiter(key_func=get_remote_address)
    _limit_transcribe = _voice_limiter.limit("30/minute")
    _limit_synthesize = _voice_limiter.limit("120/minute")
    _limit_chunk = _voice_limiter.limit("240/minute")
except Exception:
    _voice_limiter = None
    _limit_transcribe = _limit_synthesize = _limit_chunk = lambda f: f  # no-op

# Day 24: cap single audio uploads. 25 MB ≈ 25+ min of Opus voice notes —
# far above the 45 s tutor cap — while blocking OOM-via-upload.
MAX_AUDIO_BYTES = 25 * 1024 * 1024

# Day 43: cap concurrent voice streams. Each session can pin a worker thread
# in whisper transcription, and HTTP rate limiting (slowapi) doesn't cover
# websockets — so bound it here. Single-user Macs never notice; a 5th tab
# gets a polite "busy, retry" close instead of starving the first four.
# Plain counter (not a Semaphore): test portals and reloads run separate
# event loops, but the process — and its worker threads — is shared.
MAX_WS_SESSIONS = 4
_WS_ACTIVE = 0
_WS_LOCK = threading.Lock()


def _ws_try_enter() -> bool:
    global _WS_ACTIVE
    with _WS_LOCK:
        if _WS_ACTIVE >= MAX_WS_SESSIONS:
            return False
        _WS_ACTIVE += 1
        return True


def _ws_exit() -> None:
    global _WS_ACTIVE
    with _WS_LOCK:
        _WS_ACTIVE = max(0, _WS_ACTIVE - 1)

# Day 7: realtime voice counters (no user content — sizes and hits only).
# Exposed via /stream-info so Admin/diagnostics can show TTFA-relevant stats.
_VOICE_STATS = {"ws_sessions": 0, "ws_partials": 0, "ws_finals": 0, "tts_hits": 0, "tts_misses": 0}
_VOICE_STATS_LOCK = threading.Lock()


def _voice_stat(name: str, delta: int = 1) -> None:
    with _VOICE_STATS_LOCK:
        _VOICE_STATS[name] = _VOICE_STATS.get(name, 0) + delta


def _voice_stats_snapshot() -> dict:
    with _VOICE_STATS_LOCK:
        return dict(_VOICE_STATS)


class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    language: Optional[str] = Field(default=None, max_length=10)


class ChunkRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    max_chars: int = Field(default=350, ge=80, le=1000)


@router.post("/transcribe")
@_limit_transcribe
async def transcribe(request: Request, audio: UploadFile = File(...), language: Optional[str] = Form(default=None, max_length=10)):
    data = await audio.read()
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, f"Audio too large. Maximum size: {MAX_AUDIO_BYTES // (1024*1024)} MB")
    if not data:
        return {"transcript": "", "language": "en", "language_prob": 0.0, "model": "none"}
    result = await voice_svc.transcribe(data, audio.content_type or "audio/webm", language)
    # Backward compat: old frontend expects {"transcript": str}
    if isinstance(result, dict):
        return {"transcript": result.get("text", ""), "language": result.get("language", "en"),
                "language_prob": result.get("language_prob", 0.0), "model": result.get("model", "small")}
    return {"transcript": result}


@router.get("/languages")
async def languages():
    """All speech languages ARIA understands (Whisper 99).

    Day 22: each entry flags whether spoken replies are available in that
    language (`tts_voice` set + installed on this Mac), so the UI can show
    "voice reply" vs "text-only" per language.
    """
    from services.voice_service import WHISPER_LANGS, _pick_tts_voice
    return {"languages": [
        {"code": k, "name": v, "tts_voice": _pick_tts_voice(k), "tts": _pick_tts_voice(k) is not None}
        for k, v in sorted(WHISPER_LANGS.items(), key=lambda x: x[1])
    ]}


@router.post("/synthesize")
@_limit_synthesize
async def synthesize(request: Request, data: SynthesizeRequest):
    from services.voice_service import tts_cache_get, tts_cache_put, tts_engine, _pick_tts_voice, _piper_stem
    text = data.text[:3500]
    lang = (data.language or None)
    engine, mime = tts_engine(lang)
    # X-Voice keeps its historic meaning (spoken voice name); X-Engine is new.
    voice_label = (_piper_stem(lang) if engine.startswith("piper") else None) or _pick_tts_voice(lang) or "default"
    headers = {"X-Voice": voice_label, "X-Engine": engine.split(":")[0]}
    hit = tts_cache_get(text, lang, engine)
    if hit:
        _voice_stat("tts_hits")
        try:
            from services.telemetry_service import record_event
            record_event("voice_tts", cached=True, chars=len(text))
        except Exception:
            pass
        return Response(content=hit, media_type=mime, headers={**headers, "X-Cache": "HIT"})
    audio_bytes, mime = await voice_svc.synthesize_audio(text, lang)
    if audio_bytes:
        tts_cache_put(text, audio_bytes, lang, engine)
        _voice_stat("tts_misses")
        try:
            from services.telemetry_service import record_event
            record_event("voice_tts", cached=False, chars=len(text))
        except Exception:
            pass
        return Response(content=audio_bytes, media_type=mime, headers={**headers, "X-Cache": "MISS"})
    return {"error": "TTS not available"}


@router.post("/chunk")
@_limit_chunk
async def chunk_text(request: Request, data: ChunkRequest):
    """Split long LLM output into TTS-friendly sentence chunks.

    Day 1 of realtime tutor: frontend calls this (or mirrors it locally)
    so it can start speaking sentence 1 while the LLM still streams the rest.
    Pure function — no model load, safe to call at high frequency.
    """
    from services.voice_service import chunk_for_speech
    chunks = chunk_for_speech(data.text, max_chars=data.max_chars)
    return {"chunks": chunks, "count": len(chunks)}


@router.get("/stream-info")
async def stream_info():
    """Feature-detection for realtime voice clients."""
    from services.voice_service import (
        tts_cache_stats, TTS_VOICES, PIPER_VOICES, installed_say_voices, tts_engine,
    )
    installed = installed_say_voices()
    if installed is None:
        installed_codes = sorted(TTS_VOICES.keys())  # unknown host — assume mapped set
    else:
        from services.voice_service import _pick_tts_voice
        installed_codes = sorted(c for c in TTS_VOICES if _pick_tts_voice(c) is not None)
    return {
        "streaming": True,
        "ws_transcribe": "/api/voice/ws-transcribe",
        "chunk_endpoint": "/api/voice/chunk",
        "max_chunk_chars": 350,
        "protocol": "ws-binary-audio",
        "tts_cache": tts_cache_stats(),
        "tts_voices": sorted(TTS_VOICES.keys()),
        "tts_voices_installed": installed_codes,
        "tts_engines": {code: tts_engine(code)[0].split(":")[0] for code in sorted(set(TTS_VOICES) | set(PIPER_VOICES))},
        "stats": _voice_stats_snapshot(),
        "ws_idle_timeout_s": 300,
        "ws_max_session_s": 900,
        "hint": "Realtime voice: WS partial-STT + sentence TTS + per-language voices. See backend/docs/voice_api.md.",
    }


@router.websocket("/ws-transcribe")
async def ws_transcribe(ws: WebSocket):
    """Streaming STT: binary audio in, {vad, partial, final} JSON out.

    Client protocol:
      - optional text: {"type":"config","language":"ta","mime":"audio/webm"}
      - binary: raw audio chunks (MediaRecorder timeslices)
      - text: {"type":"flush"} → transcribe buffer, emit final, keep open
      - text: {"type":"reset"} → clear buffer
      - close → session ends (unflushed audio is discarded; REST is truth)
    Server emits: ready, vad (per chunk), partial (throttled), final, error.
    REST /transcribe remains source of truth for accuracy; WS is for latency.
    Day 4: idle (5min) + absolute (15min) session caps so dead tabs can't
    pin a worker thread running whisper transcribes forever.
    Day 43: max 4 concurrent streams (counter, not semaphore — test portals
    and reloads run separate event loops but share the process).
    """
    await ws.accept()
    if not _ws_try_enter():
        try:
            await ws.send_json({"type": "error", "code": "busy",
                                "message": "Too many live voice streams — close one and retry."})
            await ws.close(code=1013)
        except Exception:
            pass
        return
    try:
        await _ws_session(ws)
    finally:
        _ws_exit()


async def _ws_session(ws: WebSocket) -> None:
    """Body of a voice stream once a concurrency slot is held."""
    from services.voice_service import StreamingBuffer, audio_energy, is_speech
    import time as _time

    WS_IDLE_TIMEOUT_S = 300.0
    WS_MAX_SESSION_S = 900.0

    buf = StreamingBuffer()
    language: str | None = None
    mime = "audio/webm"
    session_start = _time.monotonic()
    partial_inflight = False
    _voice_stat("ws_sessions")
    # Day 30: warm whisper in the background on connect (measured 4.8 s cold
    # load vs 2.3 s warm). Only voice users pay the ~875 MB — never at boot.
    try:
        _warm_loop = asyncio.get_running_loop()

        def _warm() -> None:
            try:
                from services.voice_service import _get_model
                _get_model("small")
            except Exception as e:
                logger.debug("whisper warmup failed: %s", e)

        _warm_loop.run_in_executor(None, _warm)
    except Exception:
        pass
    await ws.send_json({"type": "ready", "protocol": "ws-binary-audio", "mime": mime})

    async def _transcribe_current() -> dict:
        data = buf.bytes()
        loop = asyncio.get_running_loop()

        def _sync() -> dict:
            try:
                return voice_svc._transcribe_sync(data, mime, language)
            except Exception as e:
                logger.warning("ws-transcribe model error: %s", e)
                return {"text": "", "language": "en", "language_prob": 0.0, "model": "error"}

        return await loop.run_in_executor(None, _sync)

    try:
        while True:
            if _time.monotonic() - session_start > WS_MAX_SESSION_S:
                try:
                    await ws.send_json({"type": "error", "code": "session_expired", "message": "Voice stream session exceeded 15 minutes — please reconnect."})
                except Exception:
                    pass
                break
            try:
                msg = await asyncio.wait_for(ws.receive(), timeout=WS_IDLE_TIMEOUT_S)
            except asyncio.TimeoutError:
                try:
                    await ws.send_json({"type": "error", "code": "idle_timeout", "message": "Voice stream idle for 5 minutes — closing."})
                except Exception:
                    pass
                break
            if msg.get("bytes") is not None:
                chunk: bytes = msg["bytes"] or b""
                if not chunk:
                    continue
                if len(chunk) > 1024 * 1024:
                    await ws.send_json({"type": "error", "code": "chunk_too_large", "message": "Single audio chunk exceeded 1MB — send smaller timeslices."})
                    continue
                energy = audio_energy(chunk)
                speech = is_speech(chunk)
                total = buf.add(chunk, speech)
                if buf.over_limit:
                    await ws.send_json({"type": "error", "code": "too_large", "message": "Audio buffer exceeded 8MB — send flush or reset."})
                    continue
                await ws.send_json({"type": "vad", "speech": speech, "energy": round(energy, 4), "bytes": total})
                # Throttled partial: prefix transcript without clearing buffer.
                # Day 12: skip when a partial is already being transcribed so a
                # chatty client can't stack whisper jobs and pin the M4 CPU.
                if buf.should_partial() and total > 0 and not partial_inflight:
                    partial_inflight = True
                    try:
                        res = await _transcribe_current()
                        _voice_stat("ws_partials")
                        await ws.send_json({
                            "type": "partial",
                            "text": (res.get("text", "") or "")[:500],
                            "language": res.get("language", "en"),
                            "bytes": total,
                        })
                    except Exception as e:
                        logger.debug("partial transcribe failed: %s", e)
                    finally:
                        partial_inflight = False
            elif msg.get("text") is not None:
                try:
                    ctl = json.loads(msg["text"])
                    if not isinstance(ctl, dict):
                        raise ValueError("control must be an object")
                except Exception:
                    await ws.send_json({"type": "error", "code": "bad_json", "message": "Control must be a JSON object."})
                    continue
                ctype = str(ctl.get("type") or "").lower()[:20]
                if ctype == "config":
                    language = (ctl.get("language") or None)
                    if isinstance(language, str) and len(language) > 10:
                        language = language[:10]
                    raw_mime = ctl.get("mime")
                    if isinstance(raw_mime, str) and raw_mime and len(raw_mime) <= 40:
                        mime = raw_mime
                    await ws.send_json({"type": "ready", "protocol": "ws-binary-audio", "mime": mime, "language": language})
                elif ctype == "reset":
                    buf.reset()
                    await ws.send_json({"type": "reset", "ok": True})
                elif ctype in ("flush", "final", "stop"):
                    if len(buf) == 0:
                        _voice_stat("ws_finals")
                        await ws.send_json({"type": "final", "transcript": "", "text": "", "language": "en", "bytes": 0})
                    else:
                        try:
                            res = await _transcribe_current()
                            text = res.get("text", "") or ""
                            _voice_stat("ws_finals")
                            await ws.send_json({
                                "type": "final",
                                "transcript": text,
                                "text": text,
                                "language": res.get("language", "en"),
                                "language_prob": res.get("language_prob", 0.0),
                                "model": res.get("model", "small"),
                                "bytes": len(buf),
                            })
                        except Exception as e:
                            logger.warning("final transcribe failed: %s", e)
                            await ws.send_json({"type": "error", "code": "transcribe_failed", "message": str(e)[:200]})
                    buf.reset()
                else:
                    await ws.send_json({"type": "error", "code": "unknown_type", "message": f"Unknown control '{ctype}'. Use config/flush/reset."})
            elif msg.get("type") == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("ws-transcribe closed: %s", e)
    finally:
        try:
            await ws.close()
        except Exception:
            pass
