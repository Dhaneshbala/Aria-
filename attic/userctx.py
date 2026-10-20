"""Per-request user context + per-user data isolation.

`require_user` (see routers/auth.py) is the security boundary: the user id
ALWAYS comes from a verified session token (or the implicit local owner).
Any user id supplied by the frontend in a form field, header or query param
is ignored; downstream code reads `current_uid()` and `data_dir()`.

Per-user storage:

    DATA_DIR/                      → global: config.json, aria.sqlite3
    DATA_DIR/users/<uid>/          → per user:
        conversations.json, titles.json, study_profile.json,
        maths_mastery.json, chromadb/, knowledge_base/, uploads/ ...

Single-user local mode keeps writing straight into DATA_DIR (is_multiuser()
== False), so nothing moves until a shared deployment flips
ARIA_MULTIUSER=1. On first request in multi-user mode, pre-existing single-
user files are moved into the OWNER's directory (rename, never delete).
"""

import contextvars
import os
import threading
from pathlib import Path

from models.database import DATA_DIR
from services import auth_service

_uid_var: contextvars.ContextVar[str] = contextvars.ContextVar("aria_uid", default="")

_lock = threading.RLock()
_migrated = False


def is_multiuser() -> bool:
    return os.environ.get("ARIA_MULTIUSER", "").strip().lower() in ("1", "true", "yes")


def current_uid() -> str:
    return _uid_var.get() or ""


def set_current_uid(uid: str) -> None:
    _uid_var.set(uid)


def data_dir(uid: str | None = None) -> Path:
    """Per-user data directory (contextvar wins when uid arg omitted)."""
    if uid is None:
        uid = current_uid()
    if uid and is_multiuser():
        d = DATA_DIR / "users" / uid
        d.mkdir(parents=True, exist_ok=True)
        return d
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def chroma_dir(uid: str | None = None) -> Path:
    """ChromaDB path prefix for vector stores (memory + KB)."""
    if uid is None:
        uid = current_uid()
    if uid and is_multiuser():
        return data_dir(uid) / "chromadb"
    return DATA_DIR / "chromadb"


def migrate_legacy_files() -> None:
    """One-time: hand pre-existing single-user files to the OWNER.

    Uses rename (same volume) and deliberately never deletes anything."""
    global _migrated
    if _migrated or not is_multiuser():
        return
    with _lock:
        if _migrated:
            return
        try:
            owner = auth_service.get_user_by_username("local-owner") or (
                auth_service.bootstrap_owner()
            )
        except Exception:
            return
        uid = owner["id"]
        d = data_dir(uid)
        for fname in (
            "conversations.json",
            "titles.json",
            "study_profile.json",
            "maths_mastery.json",
        ):
            src = DATA_DIR / fname
            dst = d / fname
            try:
                if src.exists() and not dst.exists():
                    src.rename(dst)
            except Exception:
                pass  # keep the file rather than destroy it
        _migrated = True
