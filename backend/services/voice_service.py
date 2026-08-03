"""Voice service — Whisper STT + local TTS."""
import asyncio
import subprocess
import tempfile
from pathlib import Path


class VoiceService:

    async def transcribe(self, audio_data: bytes, mime_type: str = "audio/webm") -> str:
        """Speech-to-text using faster-whisper or whisper.cpp."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._transcribe_sync, audio_data, mime_type)

    def _transcribe_sync(self, audio_data: bytes, mime_type: str) -> str:
        ext = ".webm" if "webm" in mime_type else ".wav"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            f.write(audio_data)
            tmp_path = f.name
        try:
            # Try faster-whisper first
            try:
                from faster_whisper import WhisperModel
                model = WhisperModel("base", device="cpu", compute_type="int8")
                segments, _ = model.transcribe(tmp_path)
                return " ".join(s.text for s in segments)
            except ImportError:
                pass
            # Try openai-whisper
            try:
                import whisper
                model = whisper.load_model("base")
                result = model.transcribe(tmp_path)
                return result["text"]
            except ImportError:
                pass
            return "Voice transcription not available. Please install faster-whisper: pip install faster-whisper"
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def synthesize(self, text: str) -> bytes:
        """Text-to-speech — returns audio bytes (m4a on macOS, mp3 fallback)."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._tts_sync, text)

    def _tts_sync(self, text: str) -> bytes:
        # 1) macOS built-in `say` — zero deps, natural voices
        try:
            out = Path(tempfile.gettempdir()) / f"aria_tts_{abs(hash(text))}.m4a"
            cmd = [
                "say", "-o", str(out), "--data-format=aac", "--file-format=m4af", text,
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0 and out.exists() and out.stat().st_size > 0:
                data = out.read_bytes()
                out.unlink(missing_ok=True)
                return data
        except Exception:
            pass
        # 2) pyttsx3 fallback (mp3)
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 150)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                tmp = f.name
            engine.save_to_file(text, tmp)
            engine.runAndWait()
            with open(tmp, "rb") as f:
                data = f.read()
            Path(tmp).unlink(missing_ok=True)
            return data
        except Exception:
            return b""
