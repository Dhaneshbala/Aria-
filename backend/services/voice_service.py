"""Voice service — Whisper STT + local TTS (multilingual)."""
import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Cache models — reloading on every request was slow + broke language detection.
# small (244M, fast) for everyday use, large-v3-turbo (809M, near-large accuracy)
# as fallback for low-confidence / low-resource languages. Both fit M4 16GB with int8.
_WHISPER_MODELS: dict = {}

# Full Whisper language set (99) — code -> name, for hint normalization + UI list
WHISPER_LANGS = {
    "en": "English", "ta": "Tamil", "hi": "Hindi", "te": "Telugu", "kn": "Kannada",
    "ml": "Malayalam", "mr": "Marathi", "gu": "Gujarati", "pa": "Punjabi", "bn": "Bengali",
    "ur": "Urdu", "ar": "Arabic", "fa": "Persian", "tr": "Turkish", "fr": "French",
    "de": "German", "es": "Spanish", "pt": "Portuguese", "it": "Italian", "nl": "Dutch",
    "ru": "Russian", "uk": "Ukrainian", "pl": "Polish", "zh": "Chinese", "ja": "Japanese",
    "ko": "Korean", "vi": "Vietnamese", "th": "Thai", "id": "Indonesian", "ms": "Malay",
    "tl": "Tagalog", "sw": "Swahili", "am": "Amharic", "he": "Hebrew", "el": "Greek",
    "hu": "Hungarian", "cs": "Czech", "sk": "Slovak", "ro": "Romanian", "bg": "Bulgarian",
    "hr": "Croatian", "sr": "Serbian", "da": "Danish", "fi": "Finnish", "sv": "Swedish",
    "no": "Norwegian", "af": "Afrikaans", "az": "Azerbaijani", "be": "Belarusian",
    "bs": "Bosnian", "et": "Estonian", "ka": "Georgian", "hy": "Armenian", "kk": "Kazakh",
    "ky": "Kyrgyz", "lt": "Lithuanian", "lv": "Latvian", "mk": "Macedonian", "mn": "Mongolian",
    "my": "Burmese", "ne": "Nepali", "ps": "Pashto", "si": "Sinhala", "sl": "Slovenian",
    "sq": "Albanian", "tg": "Tajik", "uz": "Uzbek", "yo": "Yoruba", "zu": "Zulu",
    "ca": "Catalan", "cy": "Welsh", "eu": "Basque", "gl": "Galician", "ht": "Haitian",
    "haw": "Hawaiian", "jw": "Javanese", "km": "Khmer", "la": "Latin", "lb": "Luxembourgish",
    "lo": "Lao", "mi": "Maori", "mt": "Maltese", "oc": "Occitan", "sa": "Sanskrit",
    "sd": "Sindhi", "so": "Somali", "su": "Sundanese", "tk": "Turkmen", "tt": "Tatar",
    "ug": "Uyghur", "yi": "Yiddish", "yo": "Yoruba",
}

_NAME_TO_CODE = {v.lower(): k for k, v in WHISPER_LANGS.items()}
_NAME_TO_CODE.update({
    "tamil": "ta", "tamilnadu": "ta", "hindi": "hi", "korean": "ko",
    "chinese": "zh", "mandarin": "zh", "cantonese": "yue",
})


def _normalize_lang(language: str | None) -> str | None:
    if not language:
        return None
    s = language.strip().lower().split("-")[0].split("_")[0]
    if s in WHISPER_LANGS:
        return s
    if s in _NAME_TO_CODE:
        return _NAME_TO_CODE[s]
    return None


def _get_model(name: str = "small"):
    """Cached singleton per model name."""
    if name in _WHISPER_MODELS:
        return _WHISPER_MODELS[name]
    from faster_whisper import WhisperModel
    try:
        _WHISPER_MODELS[name] = WhisperModel(name, device="cpu", compute_type="int8")
    except Exception as e:
        logger.warning("Could not load whisper '%s' (%s), falling back to small", name, e)
        if name != "small":
            return _get_model("small")
        _WHISPER_MODELS[name] = WhisperModel("base", device="cpu", compute_type="int8")
    return _WHISPER_MODELS[name]


class VoiceService:

    async def transcribe(self, audio_data: bytes, mime_type: str = "audio/webm", language: str | None = None) -> dict:
        """Speech-to-text, multilingual. Returns {text, language, language_prob}.
        language: optional BCP-47 hint from browser (e.g. 'ta', 'ta-IN', 'hi')."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._transcribe_sync, audio_data, mime_type, language)

    def _transcribe_sync(self, audio_data: bytes, mime_type: str, language: str | None = None) -> dict:
        ext = ".webm" if "webm" in mime_type else ".wav"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            f.write(audio_data)
            tmp_path = f.name
        try:
            try:
                model = _get_model("small")
            except ImportError:
                return {"text": "Voice transcription not available. Please install faster-whisper: pip install faster-whisper",
                        "language": "en", "language_prob": 0.0, "model": "none"}
            hint = _normalize_lang(language)

            def _run(m, lang_override=None):
                # Pass 1: detect (multilingual, VAD on). Never translate — that rewrites Tamil into English.
                try:
                    _, info = m.transcribe(tmp_path, task="transcribe", beam_size=5,
                                           vad_filter=True, multilingual=True)
                    detected = (getattr(info, "language", None) or "").lower()
                    prob = float(getattr(info, "language_probability", 0.0) or 0.0)
                except Exception as e:
                    logger.warning("Whisper language detect failed: %s", e)
                    detected, prob = "", 0.0
                # Explicit user choice always wins; else trust detection >=0.6, else browser hint
                if lang_override:
                    use_lang = lang_override
                else:
                    use_lang = detected if (detected and prob >= 0.6) else (hint or detected or None)
                kwargs: dict = dict(task="transcribe", beam_size=5, vad_filter=True, multilingual=True,
                                    condition_on_previous_text=False)
                if use_lang:
                    kwargs["language"] = use_lang
                segments, info2 = m.transcribe(tmp_path, **kwargs)
                text = " ".join(s.text for s in segments).strip()
                final_lang = (getattr(info2, "language", None) or use_lang or detected or "en").lower()
                final_prob = float(getattr(info2, "language_probability", prob) or prob or 0.0)
                return text, final_lang, final_prob, use_lang

            # If user explicitly picked a language, force it on the fast model first
            text, final_lang, final_prob, use_lang = _run(model, lang_override=hint if hint and language and language.strip().lower() not in ("auto", "") else None)
            model_used = "small"

            # Cascade: if unsure (<0.7), empty, or very short — retry with large-v3-turbo (much better for all 99 langs)
            needs_big = (not text) or (final_prob < 0.7 and len(text.split()) < 4)
            if needs_big:
                try:
                    big = _get_model("large-v3-turbo")
                    t2, l2, p2, _ = _run(big, lang_override=hint if hint else None)
                    # Prefer big if it produced text with higher confidence
                    if t2 and (p2 > final_prob or not text):
                        text, final_lang, final_prob = t2, l2, p2
                        model_used = "large-v3-turbo"
                except Exception as e:
                    logger.warning("large-v3-turbo fallback failed (will download ~1.6GB on first use): %s", e)

            if not text:
                return {"text": "", "language": final_lang, "language_prob": round(final_prob, 3), "model": model_used}
            return {"text": text, "language": final_lang, "language_prob": round(final_prob, 3), "model": model_used}
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
