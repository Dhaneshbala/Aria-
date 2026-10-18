from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response

from services.voice_service import VoiceService

router = APIRouter(prefix="/api/voice", tags=["voice"])
voice_svc = VoiceService()

MAX_AUDIO_SIZE = 25 * 1024 * 1024  # 25 MB — whisper can't handle hours-long audio
MAX_SYNTH_CHARS = 2000  # TTS queue/clarity cap — long docs should use audio overview


@router.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...), language: str | None = Form(default=None)
):
    data = await audio.read(MAX_AUDIO_SIZE + 1)
    if len(data) > MAX_AUDIO_SIZE:
        raise HTTPException(413, "Audio too large (max 25MB)")
    if not data:
        raise HTTPException(400, "Empty audio file")
    result = await voice_svc.transcribe(
        data, audio.content_type or "audio/webm", language
    )
    # Backward compat: old frontend expects {"transcript": str}
    if isinstance(result, dict):
        return {
            "transcript": result.get("text", ""),
            "language": result.get("language", "en"),
            "language_prob": result.get("language_prob", 0.0),
            "model": result.get("model", "small"),
        }
    return {"transcript": result}


@router.get("/languages")
async def languages():
    """All speech languages ARIA understands (Whisper 99)."""
    from services.voice_service import WHISPER_LANGS

    return {
        "languages": [
            {"code": k, "name": v}
            for k, v in sorted(WHISPER_LANGS.items(), key=lambda x: x[1])
        ]
    }


@router.post("/synthesize")
async def synthesize(data: dict):
    text = data.get("text", "")
    if not isinstance(text, str) or not text.strip():
        return JSONResponse(status_code=400, content={"error": "text is required"})
    if len(text) > MAX_SYNTH_CHARS:
        return JSONResponse(
            status_code=413,
            content={"error": f"Text too long (max {MAX_SYNTH_CHARS} chars)"},
        )
    audio_bytes = await voice_svc.synthesize(text)
    if audio_bytes:
        return Response(content=audio_bytes, media_type="audio/mp4")
    return {"error": "TTS not available"}
