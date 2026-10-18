"""
Config store for ARIA.
Defaults are tuned for MacBook Air M4 16GB / 100GB storage.

Model strategy (16 GB unified memory):
  qwen3.5:9b       → main generation model — chat, reasoning, coding,
                       math, vision/multimodal, tool calling, planning.
                       Single model handles all generation tasks to avoid
                       loading multiple large models simultaneously.
                       Runs on Metal GPU via Ollama on Apple Silicon (nvfp4, 256K ctx, ~19-25 tok/s vs 9-12 on Gemma)
  nomic-embed-text    → embedding model — ONLY for memory/RAG retrieval.
                       Tiny, fast, never used for generation.

   Total disk:  ~7.9 GB for qwen3.5 + 274 MB for nomic
  RAM pattern: only ONE generation model loaded at a time.
               Leaves headroom for Chrome, Canva, Word, PDFs, VS Code.

Image generation: Pollinations.ai (free, no install, uses internet not GPU).
Stable Diffusion: NOT recommended — needs 4+ GB extra RAM and 10+ GB disk.

Legacy Qwen/Llama/Gemma3 keys are kept for migration but map to qwen3.5:9b.
"""

import json
import os
import tempfile
import threading
from pathlib import Path


# ── Clean model routing (task requirement) ──────────────────────────────────
# Env overrides allow Docker/CI without code change
def _env_model(primary: str, fallbacks: list[str], default: str) -> str:
    for key in [primary] + fallbacks:
        if os.environ.get(key):
            return os.environ[key]
    return default


MODELS = {
    "main": _env_model(
        "ARIA_MAIN_MODEL", ["MODELS_MAIN", "REASONING_MODEL"], "qwen3.5:9b"
    ),
    "embedding": _env_model(
        "ARIA_EMBED_MODEL", ["MODELS_EMBEDDING", "EMBEDDING_MODEL"], "nomic-embed-text"
    ),
}
_raw_ollama = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_URL = _raw_ollama.rstrip("/")
if OLLAMA_URL.endswith(("/api/generate", "/api/chat")):
    OLLAMA_URL = OLLAMA_URL.rsplit("/api", 1)[0]

DATA_DIR = Path(os.environ.get("ARIA_DATA_DIR", Path.home() / ".aria_data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = DATA_DIR / "config.json"
_CONFIG_LOCK = threading.RLock()
try:
    from filelock import FileLock as _FileLock

    _CONFIG_FILE_LOCK = _FileLock(str(CONFIG_FILE) + ".lock", timeout=5)
except Exception:
    _CONFIG_FILE_LOCK = None  # fallback to threading lock only

DEFAULT_CONFIG = {
    # ── AI Models (16 GB optimised — single generation model + embedding) ──
    # Primary routing — use MODELS["main"] for all generation:
    "model": MODELS["main"],  # alias used by new code
    "reasoning_model": MODELS["main"],  # legacy key → maps to main
    "vision_model": MODELS["main"],  # qwen3.5 is multimodal, handles vision
    "fallback_model": MODELS["main"],  # no separate fallback needed
    "coding_model": MODELS["main"],  # gemma handles coding too
    "fast_model": MODELS["main"],  # single model, no separate fast
    "pptx_model": MODELS["main"],
    "organizer_model": "",  # "" = use main model
    "embedding_model": MODELS["embedding"],  # nomic-embed-text ONLY for embeddings
    # ── Document processing ────────────────────────────────────────────────
    "doc_context_chars": 8000,  # chars of doc to pass to model per query
    # ── Features ───────────────────────────────────────────────────────────
    "web_search_enabled": True,
    # Speed default (Option 1): local KB/memory first; web only for explicit
    # search, freshness queries, or factual fallback. Legacy saved configs with
    # google_first=True keep the factual fallback via _needs_web_search().
    "google_first": False,  # Google supplements local knowledge
    "personal_info_ask_first": False,
    "knowledge_base_enabled": True,  # RAG via nomic-embed-text
    "memory_enabled": True,  # ChromaDB memory via nomic-embed-text
    "voice_enabled": True,
    "image_gen_enabled": True,  # Uses Pollinations.ai (free, no GPU)
    # ── Privacy ────────────────────────────────────────────────────────────
    # Opt-in anonymous usage counters (chat counts, crash types). Never
    # leaves the machine — view/clear in Admin → Privacy.
    "telemetry_enabled": False,
    # ── Image generation ───────────────────────────────────────────────────
    "image_gen_backend": "pollinations",  # "pollinations" (recommended) or "sd"
    "pollinations_model": "flux",  # "flux" (quality) or "turbo" (faster)
    "sd_url": "http://127.0.0.1:7860",
    "sd_enabled": False,  # Stable Diffusion NOT recommended on 16 GB
    # ── Student ────────────────────────────────────────────────────────────
    # student_grade is the source of truth for grade-locking ("Year 7").
    # student_age is kept in sync (age = year + 6) for legacy code.
    "student_name": "Student",
    "student_age": 13,
    "student_grade": "Year 7",
}


# ── Grade helpers (single source of truth for grade-locking) ──────────────
GRADE_YEARS = [f"Year {n}" for n in range(1, 13)]

GRADE_TO_STAGE = {
    "Year 1": "S1",
    "Year 2": "S1",
    "Year 3": "S2",
    "Year 4": "S2",
    "Year 5": "S3",
    "Year 6": "S3",
    "Year 7": "S4",
    "Year 8": "S4",
    "Year 9": "S5",
    "Year 10": "S5",
    "Year 11": "S6",
    "Year 12": "S6",
}


def parse_grade_year(grade: str | None) -> int | None:
    """Extract the year number from 'Year 7' / 'year7' / '7' → 7. None if invalid."""
    import re as _re

    if grade is None:
        return None
    if isinstance(grade, int):
        return grade if 1 <= grade <= 12 else None
    m = _re.search(r"\d{1,2}", str(grade))
    if not m:
        return None
    year = int(m.group())
    return year if 1 <= year <= 12 else None


def grade_to_age(grade: str | None) -> int | None:
    """NSW approximation: Year N ≈ age N+6 (Year 7 ≈ 13)."""
    year = parse_grade_year(grade)
    return year + 6 if year else None


def age_to_grade(age: int | None) -> str | None:
    """NSW approximation: age A ≈ Year A-6, clamped to 1..12."""
    try:
        year = int(age) - 6
    except (TypeError, ValueError):
        return None
    return f"Year {max(1, min(12, year))}"


def get_student_grade(config: dict | None) -> str:
    """Canonical student grade — always returns a valid 'Year N' string.

    Prefers config['student_grade']; falls back to deriving from
    config['student_age']; defaults to 'Year 7'.
    """
    config = config or {}
    year = parse_grade_year(config.get("student_grade"))
    if year:
        return f"Year {year}"
    try:
        age_year = int(config.get("student_age", 13)) - 6
        return f"Year {max(1, min(12, age_year))}"
    except (TypeError, ValueError):
        return "Year 7"


_LEGACY_MODELS = {
    "gemma3:12b",
    "qwen3:8b",
    "qwen3:4b",
    "qwen2.5vl:3b",
    "qwen2.5:3b",
    "qwen2.5-coder:7b",
    "llama3.2:3b",
    "llama3.2:1b",
    "gemma4:e4b-mlx",
    "gemma4:12b-mlx",
}


def _migrate_legacy_models(cfg: dict) -> dict:
    """Replace legacy Qwen/Llama/Gemma3 defaults with qwen3.5:9b if user
    never customised them. Prevents old saved config from forcing unused
    models. Also migrates gemma4:e4b-mlx → qwen3.5:9b."""
    for key in (
        "model",
        "reasoning_model",
        "vision_model",
        "fallback_model",
        "coding_model",
        "fast_model",
        "pptx_model",
        "organizer_model",
    ):
        val = cfg.get(key, "")
        if val in _LEGACY_MODELS:
            # Only migrate empty organizer_model is "" already correct
            if key == "organizer_model" and val == "":
                continue
            cfg[key] = MODELS["main"]
    # Ensure embedding stays nomic
    if cfg.get("embedding_model") in _LEGACY_MODELS or not cfg.get("embedding_model"):
        cfg["embedding_model"] = MODELS["embedding"]
    return cfg


def _migrate_student_grade(cfg: dict) -> dict:
    """Backfill student_grade from student_age for configs saved before
    grade-locking existed. Never overwrites an explicit grade."""
    if not parse_grade_year(cfg.get("student_grade")):
        derived = age_to_grade(cfg.get("student_age", 13))
        cfg["student_grade"] = derived or "Year 7"
    # Keep age in sync with the grade (grade is source of truth).
    synced = grade_to_age(cfg.get("student_grade"))
    if synced:
        cfg["student_age"] = synced
    return cfg


def _atomic_write(path: Path, data: str):
    """Atomic write via tmp+rename to avoid torn files on crash."""
    tmp = None
    try:
        fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent), prefix=f".{path.name}.tmp."
        )
        tmp = Path(tmp_path)
        with open(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(path)
    finally:
        if tmp and tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def get_config() -> dict:
    # Use FileLock for cross-process safety when available, fallback to thread lock
    lock_ctx = _CONFIG_FILE_LOCK if _CONFIG_FILE_LOCK else _CONFIG_LOCK
    # FileLock doesn't support nested with _CONFIG_LOCK, so use it exclusively when present
    ctx = lock_ctx if _CONFIG_FILE_LOCK else _CONFIG_LOCK
    with ctx:
        if CONFIG_FILE.exists():
            try:
                saved = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                merged = {**DEFAULT_CONFIG, **saved}
                merged = _migrate_legacy_models(merged)
                merged = _migrate_student_grade(merged)
                # Auto-fix if file still has legacy values — persist migration
                if any(
                    saved.get(k) in _LEGACY_MODELS for k in saved if k in DEFAULT_CONFIG
                ):
                    try:
                        _atomic_write(CONFIG_FILE, json.dumps(merged, indent=2))
                    except Exception:
                        pass
                return merged
            except Exception:
                pass
        return DEFAULT_CONFIG.copy()


ALLOWED_CONFIG_KEYS = {
    "model",
    "reasoning_model",
    "vision_model",
    "fallback_model",
    "coding_model",
    "fast_model",
    "pptx_model",
    "organizer_model",
    "embedding_model",
    "doc_context_chars",
    "web_search_enabled",
    "google_first",
    "personal_info_ask_first",
    "knowledge_base_enabled",
    "memory_enabled",
    "voice_enabled",
    "image_gen_enabled",
    "telemetry_enabled",
    "image_gen_backend",
    "pollinations_model",
    "sd_url",
    "sd_enabled",
    "student_name",
    "student_age",
    "student_grade",
    "subjects",
}

_MODEL_KEYS = {
    "model",
    "reasoning_model",
    "vision_model",
    "fallback_model",
    "coding_model",
    "fast_model",
    "pptx_model",
    "organizer_model",
    "embedding_model",
    "pollinations_model",
    "image_gen_backend",
    "sd_url",
}


def save_config(updates: dict) -> dict:
    lock_ctx = _CONFIG_FILE_LOCK if _CONFIG_FILE_LOCK else _CONFIG_LOCK
    ctx = lock_ctx if _CONFIG_FILE_LOCK else _CONFIG_LOCK
    with ctx:
        filtered: dict = {}
        for k, v in (updates or {}).items():
            if k not in ALLOWED_CONFIG_KEYS:
                continue
            if k == "doc_context_chars":
                try:
                    iv = int(v)
                except Exception:
                    continue
                if iv < 500 or iv > 50000:
                    continue
                filtered[k] = iv
                continue
            if k in _MODEL_KEYS and isinstance(v, str) and len(v) > 100:
                continue
            filtered[k] = v
        merged = {**get_config(), **filtered}
        # Grade is source of truth: a grade change re-syncs age automatically.
        if "student_grade" in filtered:
            year = parse_grade_year(filtered.get("student_grade"))
            if year:
                merged["student_grade"] = f"Year {year}"
                synced = grade_to_age(merged["student_grade"])
                if synced:
                    merged["student_age"] = synced
        merged = _migrate_student_grade(merged)
        _atomic_write(CONFIG_FILE, json.dumps(merged, indent=2))
        return merged
