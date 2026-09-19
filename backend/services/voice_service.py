"""Voice service — Whisper STT + local TTS (multilingual)."""
import asyncio
import logging
import os
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


# ── Realtime voice helpers (Day 1 of streaming tutor) ─────────────────────────
# Pure functions — no model deps, safe to unit test. Frontend mirrors this
# logic in frontend/src/services/voiceQueue.js (keep the two in sync).

import re as _re

_CLEAN_PATTERNS = [
    (r"```[\s\S]*?```", " [diagram shown on screen]. "),
    (r"`([^`]+)`", r"\1"),
    (r"\$\$[\s\S]*?\$\$", " [equation shown on screen]. "),
    (r"\$([^$]+)\$", r"\1"),
    (r"^#{1,6}\s+", ""),
    (r"\*\*([^*]+)\*\*", r"\1"),
    (r"\[([^\]]+)\]\([^)]+\)", r"\1"),
    (r"^[\s]*[-*]\s+", ""),
]


# ── Day 8: maths verbalization ──────────────────────────────────────────────────
# Tutors must *say* equations ("x squared plus three"), not spell symbols.
# Conservative by design: only unambiguous patterns are rewritten so prose,
# dates, and URLs survive untouched. Runs BEFORE markdown stripping.

_MATH_WORDS = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
    "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
}

_LATEX_OPS = [
    (r"\\times", " times "),
    (r"\\div", " divided by "),
    (r"\\pm", " plus or minus "),
    (r"\\neq", " is not equal to "),
    (r"\\leq?", " is less than or equal to "),
    (r"\\geq?", " is greater than or equal to "),
    (r"\\cdot", " times "),
]


def verbalize_math(text: str | None) -> str:
    """Rewrite unambiguous maths notation into speakable words."""
    if not text:
        return ""
    out = text
    # \frac{a}{b} → "a over b" (loop for nesting, capped)
    for _ in range(3):
        new = _re.sub(r"\\d?frac\{([^{}]+)\}\{([^{}]+)\}", r"\1 over \2", out)
        if new == out:
            break
        out = new
    # \sqrt{x} → "square root of x"
    out = _re.sub(r"\\sqrt\{([^{}]+)\}", r"square root of \1", out)
    for pat, repl in _LATEX_OPS:
        out = _re.sub(pat, repl, out)
    # Powers: x^2 → "x squared", x^3 → "x cubed", x^n → "x to the power n"
    def _pow(m: "_re.Match") -> str:
        base, exp = m.group(1), m.group(2).strip("{} ")
        if exp == "2":
            return f"{base} squared"
        if exp == "3":
            return f"{base} cubed"
        return f"{base} to the power {exp}"

    out = _re.sub(r"([A-Za-z0-9\)\]])\s*\^\s*(\{?[A-Za-z0-9]+\}?)", _pow, out)
    # Unicode superscripts / symbols (unambiguous — rare in prose)
    out = out.replace("²", " squared").replace("³", " cubed")
    out = _re.sub(r"√\s*([A-Za-z0-9\(]+)", r"square root of \1", out)
    out = out.replace("×", " times ").replace("÷", " divided by ")
    out = out.replace("±", " plus or minus ").replace("≠", " is not equal to ")
    out = out.replace("≤", " is less than or equal to ").replace("≥", " is greater than or equal to ")
    # Spaced equals: "a = b" → "a equals b" (bare "=" in URLs/code untouched)
    out = _re.sub(r"\s=\s", " equals ", out)
    # Common spoken fractions; other single-digit fractions → "a over b"
    out = _re.sub(r"\b1\s*/\s*2\b", "one half", out)
    out = _re.sub(r"\b1\s*/\s*4\b", "one quarter", out)
    out = _re.sub(r"\b3\s*/\s*4\b", "three quarters", out)
    out = _re.sub(r"\b([0-9])\s*/\s*([0-9])\b", lambda m: f"{_MATH_WORDS[m.group(1)]} over {_MATH_WORDS[m.group(2)]}", out)
    # Percent: "50%" → "50 percent"
    out = _re.sub(r"(\d)\s*%", r"\1 percent", out)
    out = _re.sub(r"\s{2,}", " ", out)
    return out


def clean_for_speech(text: str | None, max_chars: int = 3500) -> str:
    """Strip markdown/code/latex into speakable plain text (maths verbalized)."""
    if not text:
        return ""
    out = verbalize_math(text)
    for pat, repl in _CLEAN_PATTERNS:
        out = _re.sub(pat, repl, out, flags=_re.MULTILINE)
    out = _re.sub(r"\n{2,}", ". ", out)
    out = _re.sub(r"\n", " ", out)
    out = _re.sub(r"\s{2,}", " ", out).strip()
    return out[:max_chars]


def chunk_for_speech(text: str, max_chars: int = 350) -> list[str]:
    """Split speakable text into TTS-friendly sentence chunks.

    - Cleans markdown first via clean_for_speech()
    - Splits on sentence boundaries (. ! ? + newlines)
    - Merges tiny fragments so we don't spam the TTS endpoint
    - Hard-caps each chunk at max_chars (word-boundary split)
    """
    cleaned = clean_for_speech(text)
    if not cleaned:
        return []
    # Split keeping delimiters so "Hello. World" -> ["Hello.", "World"]
    parts = _re.split(r"(?<=[.!?])\s+|\n+", cleaned)
    chunks: list[str] = []
    buf = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Very long single sentence → word-boundary split
        while len(part) > max_chars:
            cut = part.rfind(" ", 0, max_chars)
            if cut <= 0:
                cut = max_chars
            piece = part[:cut].strip()
            if buf:
                if len(buf) + 1 + len(piece) <= max_chars:
                    buf = f"{buf} {piece}"
                else:
                    chunks.append(buf)
                    buf = piece
            else:
                chunks.append(piece)
            part = part[cut:].strip()
        if not part:
            continue
        if not buf:
            buf = part
        elif len(buf) + 1 + len(part) <= max_chars:
            buf = f"{buf} {part}"
        else:
            # Keep questions/exclamations responsive: flush immediately
            chunks.append(buf)
            buf = part
    if buf:
        chunks.append(buf)
    return chunks


# ── Day 2: streaming VAD helpers ──────────────────────────────────────────────
# Dependency-free heuristics for WebSocket partial-STT. Compressed chunks
# (webm/opus) can't be decoded without ffmpeg, so energy is approximate and
# used only for UI feedback + flush hints — never for gating transcription.

def audio_energy(audio_bytes: bytes | None) -> float:
    """Rough 0..1 loudness estimate for an audio chunk.

    Interprets bytes as signed 8-bit PCM and returns RMS. Silence ≈ 0.0,
    normal speech ≈ 0.05–0.3, loud ≈ 0.5+. Empty → 0.0.
    """
    if not audio_bytes:
        return 0.0
    try:
        import numpy as _np
        arr = _np.frombuffer(audio_bytes, dtype=_np.int8).astype(_np.float32) / 128.0
        if arr.size == 0:
            return 0.0
        # Downsample huge chunks for speed
        if arr.size > 32000:
            arr = arr[:: arr.size // 32000]
        rms = float(_np.sqrt(_np.mean(arr * arr)))
        return max(0.0, min(1.0, rms))
    except Exception:
        return 0.0


def is_speech(audio_bytes: bytes | None, threshold: float = 0.02) -> bool:
    """Heuristic voice-activity flag for a single chunk."""
    return audio_energy(audio_bytes) >= threshold


class StreamingBuffer:
    """Accumulates binary audio chunks for one WS session.

    Tracks total bytes, chunk count, last-speech time, and flush policy so
    the router stays thin. No model deps — safe to unit test.
    """

    def __init__(self, max_bytes: int = 8 * 1024 * 1024):
        self._buf = bytearray()
        self.chunks = 0
        self.max_bytes = max_bytes
        self.over_limit = False
        try:
            import time as _time
            self._now = _time.monotonic
        except Exception:  # pragma: no cover
            import time as _time
            self._now = _time.time
        self.started_at = self._now()
        self.last_partial_at = 0.0
        self.last_speech_at = 0.0

    def add(self, data: bytes, speech: bool) -> int:
        if self.over_limit:
            return len(self._buf)
        if len(self._buf) + len(data) > self.max_bytes:
            self.over_limit = True
            return len(self._buf)
        self._buf += data
        self.chunks += 1
        if speech:
            self.last_speech_at = self._now()
        return len(self._buf)

    def __len__(self) -> int:
        return len(self._buf)

    def bytes(self) -> bytes:
        return bytes(self._buf)

    def should_partial(self, min_bytes: int = 30 * 1024, min_gap_s: float = 8.0) -> bool:
        if len(self._buf) < min_bytes:
            return False
        now = self._now()
        if now - self.last_partial_at < min_gap_s:
            return False
        self.last_partial_at = now
        return True

    def reset(self) -> None:
        self._buf = bytearray()
        self.chunks = 0
        self.over_limit = False
        self.last_partial_at = 0.0


# ── Day 3: TTS response cache ───────────────────────────────────────────────────
# `say`/pyttsx3 cost ~0.5-2s per sentence and tutors repeat phrases
# ("Well done!", "Try again"). Small LRU avoids re-synthesis. Pure stdlib.

import hashlib as _hashlib
import threading as _threading
from collections import OrderedDict as _OrderedDict

_TTS_CACHE: "_OrderedDict[str, bytes]" = _OrderedDict()
_TTS_CACHE_BYTES = 0
_TTS_CACHE_MAX_ENTRIES = 50
_TTS_CACHE_MAX_BYTES = 20 * 1024 * 1024
_TTS_CACHE_LOCK = _threading.Lock()


# ── Day 9: language-matched TTS voices ──────────────────────────────────────────
# STT already covers 99 languages, but replies always used the default English
# voice. Map each language to a macOS `say` voice (verified via `say -v '?'`
# on the target Mac). Unknown/absent voices → default voice, never an error.

TTS_VOICES = {
    "ta": "Vani", "hi": "Lekha", "te": "Geeta", "kn": "Soumya", "bn": "Piya",
    "ar": "Majed", "zh": "Tingting", "ja": "Kyoko", "ko": "Yuna",
    "fr": "Thomas", "de": "Anna", "es": "Mónica", "ms": "Amira",
    "th": "Kanya", "vi": "Linh", "id": "Damayanti", "nl": "Xander",
    "ru": "Milena", "pt": "Luciana",
}

_TTS_VOICE_REGION_OVERRIDE = {
    "zh-hk": "Sinji",
    "zh-tw": "Meijia",
}

# Day 10: not every Mac has every voice installed (voices are downloadable in
# System Settings). Probe once via `say -v '?'` and skip the named-voice
# attempt when the voice is absent — saves a failed subprocess spawn per
# uncached sentence. None = unknown (non-macOS?) → attempt + fallback path.
_INSTALLED_SAY_VOICES: frozenset | None | str = "unprobed"


def _parse_say_voices(output: str) -> frozenset:
    """Parse `say -v '?'` output into a set of voice names."""
    names = set()
    for line in (output or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Format: "Name   locale   # comment" — name may contain spaces/parens.
        # Locale looks like xx or xx_YY; find its start to split the name.
        m = _re.search(r"\s([a-z]{2,3}(?:_[A-Z]{2,3})?)\s+#", line)
        if m:
            names.add(line[: m.start()].strip())
        else:
            # Compact voices (Eddy/Flo/...) list locale in parens instead
            m2 = _re.match(r"(.+?)\s*\(", line)
            if m2:
                names.add(m2.group(1).strip())
    return frozenset(n for n in names if n)


def installed_say_voices() -> frozenset | None:
    """Cached set of installed `say` voices, or None if unknowable."""
    global _INSTALLED_SAY_VOICES
    if _INSTALLED_SAY_VOICES != "unprobed":
        return _INSTALLED_SAY_VOICES  # type: ignore[return-value]
    try:
        proc = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=15)
        if proc.returncode == 0 and proc.stdout.strip():
            _INSTALLED_SAY_VOICES = _parse_say_voices(proc.stdout)
        else:
            _INSTALLED_SAY_VOICES = None
    except Exception:
        _INSTALLED_SAY_VOICES = None
    return _INSTALLED_SAY_VOICES  # type: ignore[return-value]


def _pick_tts_voice(language: str | None) -> str | None:
    """Best-effort macOS voice for a BCP-47 tag. None → default voice."""
    if not language or not isinstance(language, str):
        return None
    tag = language.strip().lower().replace("_", "-")
    if not tag or tag == "auto":
        return None
    if tag in _TTS_VOICE_REGION_OVERRIDE:
        voice: str | None = _TTS_VOICE_REGION_OVERRIDE[tag]
    else:
        code = _normalize_lang(tag)
        if not code or code == "en":
            return None  # English → system default (Samantha), unchanged behaviour
        voice = TTS_VOICES.get(code)
    if voice is None:
        return None
    installed = installed_say_voices()
    if installed is not None and voice not in installed:
        logger.info("TTS voice '%s' not installed — using default voice", voice)
        return None
    return voice


def _tts_cache_key(text: str, language: str | None = None, engine: str = "") -> str:
    lang = (language or "").strip().lower()[:10]
    return _hashlib.sha256(f"{lang}\0{engine}\0{text.strip()}".encode("utf-8")).hexdigest()


def tts_cache_get(text: str, language: str | None = None, engine: str = "") -> bytes | None:
    key = _tts_cache_key(text, language, engine)
    with _TTS_CACHE_LOCK:
        data = _TTS_CACHE.get(key)
        if data is not None:
            _TTS_CACHE.move_to_end(key)
        return data


def tts_cache_put(text: str, data: bytes, language: str | None = None, engine: str = "") -> None:
    global _TTS_CACHE_BYTES
    if not data:
        return
    if len(data) > 2 * 1024 * 1024:  # don't cache huge outliers
        return
    key = _tts_cache_key(text, language, engine)
    with _TTS_CACHE_LOCK:
        old = _TTS_CACHE.pop(key, None)
        if old is not None:
            _TTS_CACHE_BYTES -= len(old)
        _TTS_CACHE[key] = data
        _TTS_CACHE_BYTES += len(data)
        while len(_TTS_CACHE) > _TTS_CACHE_MAX_ENTRIES or _TTS_CACHE_BYTES > _TTS_CACHE_MAX_BYTES:
            _k, _v = _TTS_CACHE.popitem(last=False)
            _TTS_CACHE_BYTES -= len(_v)


def tts_cache_stats() -> dict:
    with _TTS_CACHE_LOCK:
        return {
            "entries": len(_TTS_CACHE),
            "bytes": _TTS_CACHE_BYTES,
            "max_entries": _TTS_CACHE_MAX_ENTRIES,
            "max_bytes": _TTS_CACHE_MAX_BYTES,
        }


# ── Day 32: Piper neural TTS (engine #1 for mapped languages) ─────────────────
# Local ONNX voices (~65 MB each) in $ARIA_DATA_DIR/piper. Measured on this
# Mac: en 0.54 s / hi 0.14 s per medium sentence vs `say` ~1.0-1.3 s — and the
# quality is consistent across machines. Languages without a Piper voice
# (ta, kn, …) keep using macOS `say`. Nothing here raises: missing package,
# missing files, or synthesis errors all fall through to the next engine.

PIPER_VOICES = {
    "en": "en_US-lessac-medium",
    "hi": "hi_IN-pratham-medium",
    "te": "te_IN-maya-medium",
    "bn": "bn_BD-google-medium",
    "ml": "ml_IN-meera-medium",
    "mr": "mr_IN-google-medium",
    "ur": "ur_PK-aegis_female-medium",
}

_PIPER_CACHE: dict = {}
_PIPER_CACHE_MAX = 3  # ~65 MB per voice; cap resident set ≈200 MB on 16 GB Macs


def _piper_dir() -> Path:
    return Path(os.environ.get("ARIA_DATA_DIR", Path.home() / ".aria_data")) / "piper"


def piper_available() -> bool:
    try:
        import piper  # noqa: F401
        return True
    except ImportError:
        return False


def _piper_stem(language: str | None) -> str | None:
    """Model stem for a language (None language → English default reply)."""
    code = _normalize_lang(language) if language else "en"
    return PIPER_VOICES.get(code or "en")


def _piper_voice(stem: str):
    """Lazily loaded + cached Piper voice (~65 MB resident each, max 3)."""
    if stem in _PIPER_CACHE:
        _PIPER_CACHE[stem] = _PIPER_CACHE.pop(stem)  # refresh LRU order
        return _PIPER_CACHE[stem]
    from piper import PiperVoice
    model = _piper_dir() / f"{stem}.onnx"
    if not model.exists():
        return None
    voice = PiperVoice.load(str(model))
    _PIPER_CACHE[stem] = voice
    while len(_PIPER_CACHE) > _PIPER_CACHE_MAX:
        _PIPER_CACHE.pop(next(iter(_PIPER_CACHE)))  # evict oldest; reloads are ~0.45 s
    return voice


def _piper_wav(text: str, stem: str) -> bytes | None:
    """Synthesize to WAV bytes. None on any failure (caller falls through)."""
    import io
    import wave
    voice = _piper_voice(stem)
    if voice is None:
        return None
    pcm = b"".join(c.audio_int16_bytes for c in voice.synthesize(text))
    if not pcm:
        return None
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(voice.config.sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


def tts_engine(language: str | None) -> tuple[str, str]:
    """Pick (engine_tag, mime) for a reply language without synthesizing.

    engine_tag feeds the TTS cache key so Piper WAVs and `say` M4As for the
    same text never collide.
    """
    stem = _piper_stem(language)
    if stem is not None and piper_available() and (_piper_dir() / f"{stem}.onnx").exists():
        return f"piper:{stem}", "audio/wav"
    return "say", "audio/mp4"


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


# Day 15: cap parallel `say` processes. Playback + prefetch can overlap, and
# each `say` is CPU-heavy next to gemma + whisper on a 16 GB Mac. At most 2
# syntheses run at once; the rest wait (no drops, no errors). One semaphore
# per event loop (tests + reloads create fresh loops).
_TTS_SEMAPHORES: dict = {}


def _tts_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    sem = _TTS_SEMAPHORES.get(loop)
    if sem is None:
        sem = asyncio.Semaphore(2)
        _TTS_SEMAPHORES[loop] = sem
    return sem


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

    async def synthesize(self, text: str, language: str | None = None) -> bytes:
        """Text-to-speech — returns audio bytes (backward-compat wrapper)."""
        data, _mime = await self.synthesize_audio(text, language)
        return data

    async def synthesize_audio(self, text: str, language: str | None = None) -> tuple[bytes, str]:
        """Text-to-speech — returns (audio bytes, mime).

        Engine order: Piper neural (mapped languages, files present) →
        macOS `say` → pyttsx3 → b"".
        """
        loop = asyncio.get_running_loop()
        async with _tts_semaphore():
            return await loop.run_in_executor(None, self._synthesize_sync, text, language)

    def _synthesize_sync(self, text: str, language: str | None) -> tuple[bytes, str]:
        if not (text or "").strip():
            return b"", "audio/mp4"
        stem = _piper_stem(language)
        if stem is not None and piper_available():
            try:
                wav = _piper_wav(text, stem)
                if wav:
                    return wav, "audio/wav"
            except Exception as e:
                logger.debug("piper TTS failed, falling back to say: %s", e)
        data = self._tts_sync(text, _pick_tts_voice(language))
        return data, "audio/mp4"

    def _tts_sync(self, text: str, voice: str | None = None) -> bytes:
        # Day 18: never spawn a subprocess for empty input (queue drift can
        # enqueue blank sentences; fail fast instead of a 2 s `say` no-op).
        if not (text or "").strip():
            return b""
        # 1) macOS built-in `say` — zero deps, natural voices
        for attempt_voice in ([voice] if voice else []) + [None]:
            try:
                out = Path(tempfile.gettempdir()) / f"aria_tts_{abs(hash((text, attempt_voice)))}.m4a"
                cmd = ["say", "-o", str(out), "--data-format=aac", "--file-format=m4af"]
                if attempt_voice:
                    cmd += ["-v", attempt_voice]
                cmd.append(text)
                result = subprocess.run(cmd, capture_output=True, timeout=120)
                if result.returncode == 0 and out.exists() and out.stat().st_size > 0:
                    data = out.read_bytes()
                    out.unlink(missing_ok=True)
                    return data
                # Non-zero with a named voice → voice missing on this Mac; retry default
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
