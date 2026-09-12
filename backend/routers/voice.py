from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import Response
from services.voice_service import VoiceService

router = APIRouter(prefix="/api/voice", tags=["voice"])
voice_svc = VoiceService()


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...), language: Optional[str] = Form(default=None)):
    data = await audio.read()
    result = await voice_svc.transcribe(data, audio.content_type or "audio/webm", language)
    # Backward compat: old frontend expects {"transcript": str}
    if isinstance(result, dict):
        return {"transcript": result.get("text", ""), "language": result.get("language", "en"),
                "language_prob": result.get("language_prob", 0.0), "model": result.get("model", "small")}
    return {"transcript": result}


@router.get("/languages")
async def languages():
    """All speech languages ARIA understands (Whisper 99)."""
    from services.voice_service import WHISPER_LANGS
    return {"languages": [{"code": k, "name": v} for k, v in sorted(WHISPER_LANGS.items(), key=lambda x: x[1])]}


@router.post("/synthesize")
async def synthesize(data: dict):
    text = data.get("text", "")
    audio_bytes = await voice_svc.synthesize(text)
    if audio_bytes:
        return Response(content=audio_bytes, media_type="audio/mp4")
    return {"error": "TTS not available"}
