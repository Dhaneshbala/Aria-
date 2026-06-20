"""
Config store for ARIA.
Defaults are tuned for MacBook Air M4 16GB / 100GB storage.

Model choices explained:
  qwen3:8b        → 5.2 GB disk, ~8 GB RAM — best reasoning quality that fits
                    comfortably in 16 GB alongside macOS + browser.
                    Runs on Metal GPU via Ollama on Apple Silicon.

  qwen2.5vl:3b    → 2.2 GB disk, ~4 GB RAM — vision model for images/worksheets.
                    Loaded only when an image is attached (not always in RAM).
                    3b is sufficient for reading worksheets and diagrams.

  llama3.2:3b     → 2.0 GB disk, ~3 GB RAM — fast fallback if qwen3:8b is slow.

  Total disk:  ~9.4 GB  (well within 100 GB free)
  RAM pattern: only ONE model loaded at a time by Ollama.
               qwen3:8b alone = 8 GB. macOS takes ~5 GB. Leaves 3 GB buffer.

Image generation: Pollinations.ai (free, no install, uses internet not GPU).
Stable Diffusion: NOT recommended — needs 4+ GB extra RAM and 10+ GB disk.
"""
import json
from pathlib import Path

DATA_DIR = Path.home() / ".aria_data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = DATA_DIR / "config.json"

DEFAULT_CONFIG = {
    # ── AI Models (M4 MacBook Air 16GB optimised) ──────────────────────────
     "reasoning_model":   "qwen3:8b",        # 5.2 GB — best quality for this machine
     "vision_model":      "qwen2.5vl:3b",    # 2.2 GB — reads images & worksheets
     "fallback_model":    "llama3.2:3b",  
     "coding_model":    "qwen2.5-coder:7b",
     "pptx_model":      "qwen3:8b",   # 2.0 GB — fast fallback

    # ── Document processing ────────────────────────────────────────────────
    "doc_context_chars": 8000,              # chars of doc to pass to model per query

    # ── Features ───────────────────────────────────────────────────────────
    "web_search_enabled": True,
    "voice_enabled":      True,
    "memory_enabled":     True,
    "image_gen_enabled":  True,             # Uses Pollinations.ai (free, no GPU)

    # ── Image generation ───────────────────────────────────────────────────
    "image_gen_backend":  "pollinations",   # "pollinations" (recommended) or "sd"
    "pollinations_model": "flux",           # "flux" (quality) or "turbo" (faster)
    "sd_url":             "http://127.0.0.1:7860",
    "sd_enabled":         False,            # Stable Diffusion NOT recommended on 16 GB

    # ── Student ────────────────────────────────────────────────────────────
    "student_name": "Student",
    "student_age":  13,
}


def get_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            saved = json.loads(CONFIG_FILE.read_text())
            return {**DEFAULT_CONFIG, **saved}
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(updates: dict) -> dict:
    merged = {**get_config(), **updates}
    CONFIG_FILE.write_text(json.dumps(merged, indent=2))
    return merged
