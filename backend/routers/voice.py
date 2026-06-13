from fastapi import APIRouter, UploadFile, File
from fastapi.responses import Response
from ..services.voice_service import VoiceService

router = APIRouter(prefix="/api/voice", tags=["voice"])
voice_svc = VoiceService()


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    data = await audio.read()
    text = await voice_svc.transcribe(data, audio.content_type or "audio/webm")
    return {"transcript": text}


@router.post("/synthesize")
async def synthesize(data: dict):
    text = data.get("text", "")
    audio_bytes = await voice_svc.synthesize(text)
    if audio_bytes:
        return Response(content=audio_bytes, media_type="audio/mpeg")
    return {"error": "TTS not available"}
