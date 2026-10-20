"""Per-user store partitioning (Section 13 Stage 2).

Every feature store that Stage 1 left shared (todos, mistakes, spaced
repetition, exam plans, maths mastery, gamification, study profile,
knowledge graph, background tasks, knowledge base, notebooks, prompt
caches) is partitioned by the *account* the request runs under:

- ``local`` mode (default): every path resolves exactly as before —
  ``DATA_DIR/<name>`` — so existing data, tests and snapshots are
  untouched and the family keeps its single-owner behaviour.
- ``accounts`` mode: stores live under ``DATA_DIR/users/<username>/``.
  Requests always run with a session (the gate guarantees the user
  ContextVar), so services resolve their files inside their own calls.

Legacy data migration: the first time accounts mode starts,
:meth:`migrate_legacy_stores` moves the existing base files/directories
into the first admin's user directory — one ``os.replace``-style move
per store, idempotent,missing-file-safe. Nothing is copied twice and
nothing is deleted.

The frontend may hide controls by role; these paths are the real wall —
there is no API that can read another account's store files.
"""

from __future__ import annotations

import logging
from pathlib import Path

from services.request_scope import current_username

logger = logging.getLogger(__name__)

USER_STORES = (
    "todos.json",
    "mistakes.json",
    "spaced_repetition.json",
    "exam_plans.json",
    "maths_mastery.json",
    "gamification.json",
    "study_profile.json",
    "learning_style.json",
    "knowledge_graph.json",
    "background_tasks.json",
)
# Whole-directory stores (moved, not renamed — chroma/notebooks live inside).
USER_STORE_DIRS = ("knowledge_base", "notebooks")
USER_CACHE_FILES = ("cache.json", "embed_cache.json")


def data_dir() -> Path:
    from models.database import DATA_DIR

    return DATA_DIR


def accounts_mode() -> bool:
    from services.accounts import auth_mode

    return auth_mode() == "accounts"


def scoped_user() -> str | None:
    """The partitioning username for THIS call, or None in local mode.

    Accounts mode always has a username after the gate (tests set it
    directly); ``local-owner`` is the reserved local-mode account and
    never partitions accounts-mode stores on its own name.
    """
    if not accounts_mode():
        return None
    return current_username()


def user_root(username: str) -> Path:
    """Root directory of one account's stage-2 stores."""
    return data_dir() / "users" / username


def store_path(name: str, username: str | None = None) -> Path:
    """Per-user path for a single-file store (mkdir as needed).

    Local mode → ``DATA_DIR/<name>`` (unchanged). Accounts mode →
    ``DATA_DIR/users/<username>/<name>``.
    """
    user = username if username is not None else scoped_user()
    base = data_dir()
    if user is None:
        return base / name
    p = user_root(user) / name
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def store_dir(name: str, username: str | None = None) -> Path:
    """Per-user directory store (kb, notebooks) — same rules as store_path."""
    user = username if username is not None else scoped_user()
    base = data_dir()
    if user is None:
        return base / name
    p = user_root(user) / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def migrate_legacy_stores() -> int:
    """Move pre-accounts stores into the first admin's user directory.

    Files (todos.json, ...) and directories (knowledge_base/,
    notebooks/) move under ``users/<first-admin>/`` when the destination
    does not already exist. Idempotent: after the move the source is
    gone, later runs are no-ops.
    """
    moved = 0
    from services.accounts import DEFAULT_LOCAL_USER, list_users

    admin = next(
        (
            u["username"]
            for u in list_users(include_local=True)
            if u["role"] in ("admin", "superadmin")
            and u["status"] == "active"
            and u["username"] != DEFAULT_LOCAL_USER
        ),
        None,
    )
    if admin is None:
        logger.info("No admin yet — legacy store migration deferred.")
        return 0

    root = user_root(admin)
    root.mkdir(parents=True, exist_ok=True)
    for name in (*USER_STORES, *USER_CACHE_FILES):
        src = data_dir() / name
        dst = root / name
        if src.exists() and not dst.exists():
            src.replace(dst)
            moved += 1
    for name in USER_STORE_DIRS:
        src = data_dir() / name
        dst = root / name
        if src.exists() and not dst.exists():
            src.rename(dst)  # atomic within one filesystem
            moved += 1
    if moved:
        logger.info("Migrated %d legacy stores to users/%s/", moved, admin)
    return moved
