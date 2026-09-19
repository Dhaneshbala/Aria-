"""
Config store for ARIA.
Defaults are tuned for MacBook Air M4 16GB / 100GB storage.

Model strategy (16 GB unified memory):
  gemma4:e4b-mlx      → main generation model — chat, reasoning, coding,
                       math, vision/multimodal, tool calling, planning.
                       Single model handles all generation tasks to avoid
                       loading multiple large models simultaneously.
                       Runs on Metal GPU via Ollama/MLX on Apple Silicon.
  mxbai-embed-large   → embedding model — ONLY for memory/RAG retrieval.
                       Fast, 1024-dim vectors, never used for generation.

  Total disk:  ~5-6 GB for gemma4 + 670 MB for mxbai
  RAM pattern: only ONE generation model (gemma) loaded at a time.
               Leaves headroom for Chrome, Canva, Word, PDFs, VS Code.

Image generation: Pollinations.ai (free, no install, uses internet not GPU).
Stable Diffusion: NOT recommended — needs 4+ GB extra RAM and 10+ GB disk.

Legacy Qwen/Llama keys are kept for migration but map to gemma4:e4b-mlx.
"""

import json
import os
import threading
import tempfile
from pathlib import Path

try:
    # Canonical typed config — single source of truth for paths/URLs/limits.
    # Falls back to env parsing if config package is unavailable (tests/zip).
    from config.settings import get_settings as _get_settings

    _SETTINGS = _get_settings()
    DATA_DIR = Path(_SETTINGS.data_dir)
    OLLAMA_URL = str(_SETTINGS.ollama_url).rstrip("/")
    _MAIN_DEFAULT = os.environ.get("ARIA_MAIN_MODEL") or os.environ.get("MODELS_MAIN") or "gemma4:e4b-mlx"
    _EMBED_DEFAULT = os.environ.get("ARIA_EMBED_MODEL") or os.environ.get("MODELS_EMBEDDING") or "mxbai-embed-large"
    MODELS = {"main": _MAIN_DEFAULT, "embedding": _EMBED_DEFAULT}
except Exception:
    # ── Fallback: env-only routing (no pydantic available) ──────────────
    def _env_model(primary: str, fallbacks: list[str], default: str) -> str:
        for key in [primary] + fallbacks:
            if os.environ.get(key):
                return os.environ[key]  # type: ignore[return-value]
        return default

    MODELS = {
        "main": _env_model("ARIA_MAIN_MODEL", ["MODELS_MAIN", "REASONING_MODEL"], "gemma4:e4b-mlx"),
        "embedding": _env_model("ARIA_EMBED_MODEL", ["MODELS_EMBEDDING", "EMBEDDING_MODEL"], "mxbai-embed-large"),
    }
    _raw_ollama = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_URL = _raw_ollama.rstrip("/")
    if OLLAMA_URL.endswith("/api/generate") or OLLAMA_URL.endswith("/api/chat"):
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
     "model":             MODELS["main"],      # alias used by new code
     "reasoning_model":   MODELS["main"],      # legacy key → maps to main
     "vision_model":      MODELS["main"],      # gemma4 is multimodal, handles vision
     "fallback_model":    MODELS["main"],      # no separate fallback needed
     "coding_model":      MODELS["main"],      # gemma handles coding too
     "fast_model":        MODELS["main"],      # single model, no separate fast
     "pptx_model":        MODELS["main"],
     "organizer_model":   "",                  # "" = use main model
     "embedding_model":   MODELS["embedding"], # mxbai-embed-large ONLY for embeddings

    # ── Document processing ────────────────────────────────────────────────
    "doc_context_chars": 8000,              # chars of doc to pass to model per query
    "max_prompt_chars": 20000,             # absolute max system-prompt chars (base + contexts)

    # ── Features ───────────────────────────────────────────────────────────
    "web_search_enabled": True,
    "google_first":       True,             # Google supplements local knowledge
    "personal_info_ask_first": False,
    "knowledge_base_enabled": True,         # RAG via mxbai-embed-large
    "memory_enabled":     True,             # ChromaDB memory via mxbai-embed-large
    "voice_enabled":      True,
    "image_gen_enabled":  True,             # Uses Pollinations.ai (free, no GPU)

    # ── Privacy ────────────────────────────────────────────────────────────
    # Opt-in anonymous usage counters (chat counts, crash types). Never
    # leaves the machine — view/clear in Admin → Privacy.
    "telemetry_enabled": False,

    # ── Image generation ───────────────────────────────────────────────────
    "image_gen_backend":  "pollinations",   # "pollinations" (recommended) or "sd"
    "pollinations_model": "flux",           # "flux" (quality) or "turbo" (faster)
    "sd_url":             "http://127.0.0.1:7860",
    "sd_enabled":         False,            # Stable Diffusion NOT recommended on 16 GB

    # ── Student ────────────────────────────────────────────────────────────
    "student_name": "Student",
    "student_age":  13,
}


_LEGACY_MODELS = {
    "qwen3:8b", "qwen3:4b", "qwen2.5vl:3b", "qwen2.5:3b",
    "qwen2.5-coder:7b", "llama3.2:3b", "llama3.2:1b",
}

def _migrate_legacy_models(cfg: dict) -> dict:
    """Replace legacy Qwen/Llama defaults with gemma4:e4b-mlx if user never
    customised them. Prevents old saved config from forcing unused models."""
    for key in ("model", "reasoning_model", "vision_model", "fallback_model",
                "coding_model", "fast_model", "pptx_model", "organizer_model"):
        val = cfg.get(key, "")
        if val in _LEGACY_MODELS:
            # Only migrate empty organizer_model is "" already correct
            if key == "organizer_model" and val == "":
                continue
            cfg[key] = MODELS["main"]
    # Ensure embedding stays mxbai
    if cfg.get("embedding_model") in _LEGACY_MODELS or not cfg.get("embedding_model"):
        cfg["embedding_model"] = MODELS["embedding"]
    return cfg


def _atomic_write(path: Path, data: str):
    """Atomic write via tmp+rename to avoid torn files on crash."""
    tmp = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.tmp.")
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
                # Auto-fix if file still has legacy values — persist migration
                if any(saved.get(k) in _LEGACY_MODELS for k in saved if k in DEFAULT_CONFIG):
                    try:
                        _atomic_write(CONFIG_FILE, json.dumps(merged, indent=2))
                    except Exception:
                        pass
                return merged
            except Exception:
                pass
        return DEFAULT_CONFIG.copy()


def save_config(updates: dict) -> dict:
    lock_ctx = _CONFIG_FILE_LOCK if _CONFIG_FILE_LOCK else _CONFIG_LOCK
    ctx = lock_ctx if _CONFIG_FILE_LOCK else _CONFIG_LOCK
    with ctx:
        merged = {**get_config(), **updates}
        _atomic_write(CONFIG_FILE, json.dumps(merged, indent=2))
        return merged
