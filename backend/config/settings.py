"""Centralized, validated settings for ARIA.

Usage:
    from config import get_settings
    cfg = get_settings()
    print(cfg.ollama_url)
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class AriaSettings(BaseSettings):
    """All tuneable constants in one place.  Defaults suit a MacBook Air M4 16 GB."""

    # ── Network ────────────────────────────────────────────────────────────
    ollama_url: str = Field(
        default="http://localhost:11434",
        description="Base URL for the Ollama server",
    )
    backend_host: str = Field(default="127.0.0.1", description="Bind address")
    backend_port: int = Field(default=8000, ge=1024, le=65535, description="Bind port")
    frontend_port: int = Field(default=5173, ge=1024, le=65535, description="Vite dev port")

    # ── CORS ───────────────────────────────────────────────────────────────
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:4173,http://localhost:3000,"
                "http://127.0.0.1:5173,http://127.0.0.1:4173",
        description="Comma-separated allowed origins",
    )

    # ── Rate limiting ──────────────────────────────────────────────────────
    rate_limit_global: str = Field(default="120/minute", description="Default rate limit")
    rate_limit_chat: str = Field(default="30/minute", description="Chat endpoint rate limit")

    # ── Upload limits (bytes) ──────────────────────────────────────────────
    max_image_bytes: int = Field(default=20 * 1024 * 1024, ge=0, description="Max image upload")
    max_doc_bytes: int = Field(default=50 * 1024 * 1024, ge=0, description="Max document upload")
    max_message_chars: int = Field(default=8000, ge=1, description="Max chat message length")
    max_upload_files: int = Field(default=10, ge=1, le=50, description="Max simultaneous file uploads")

    # ── Chat / LLM ────────────────────────────────────────────────────────
    default_context_chars: int = Field(default=8000, ge=500, description="Doc context per query")
    max_context_chars: int = Field(default=15000, ge=1000, description="Absolute max doc context")
    max_prompt_chars: int = Field(default=20000, ge=5000, description="Absolute max system-prompt chars (base + all contexts)")
    ollama_timeout_secs: float = Field(default=120.0, gt=0, description="LLM request timeout")
    embed_timeout_secs: float = Field(default=65.0, gt=0, description="Embedding timeout")
    llm_max_tokens: int = Field(default=2048, ge=64, le=32768, description="Max tokens per generation")

    # ── Backup ─────────────────────────────────────────────────────────────
    max_backups: int = Field(default=10, ge=1, le=100, description="Backup retention count")
    max_restore_bytes: int = Field(default=500 * 1024 * 1024, ge=0, description="Max restore zip size")

    # ── Logging ────────────────────────────────────────────────────────────
    log_max_bytes: int = Field(default=2 * 1024 * 1024, ge=0, description="Log file rotation size")
    log_backup_count: int = Field(default=5, ge=0, description="Log file backup count")

    # ── Database ───────────────────────────────────────────────────────────
    db_wal_checkpoint_interval: int = Field(
        default=1000, ge=100,
        description="WAL checkpoint every N pages",
    )

    # ── Paths ──────────────────────────────────────────────────────────────
    data_dir: Path = Field(
        default_factory=lambda: Path(os.environ.get("ARIA_DATA_DIR", Path.home() / ".aria_data")),
        description="ARIA data directory",
    )

    # ── Student ────────────────────────────────────────────────────────────
    student_age: int = Field(default=13, ge=5, le=18, description="Target student age")

    @field_validator("ollama_url")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator("ollama_url")
    @classmethod
    def _strip_api_suffix(cls, v: str) -> str:
        if v.endswith("/api/generate") or v.endswith("/api/chat"):
            return v.rsplit("/api", 1)[0]
        return v

    model_config = {"env_prefix": "ARIA_", "env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache(maxsize=1)
def get_settings() -> AriaSettings:
    """Singleton settings instance.  Cached after first call."""
    return AriaSettings()
