"""Help & feedback (Section 13 A: report issues / send feedback)."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()


def _db_path() -> Path:
    from models.database import DATA_DIR

    return DATA_DIR / "app.db"


def _cx() -> sqlite3.Connection:
    Path(_db_path()).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_db_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS feedback ("
    " id INTEGER PRIMARY KEY AUTOINCREMENT,"
    " ts TEXT NOT NULL,"
    " user_id INTEGER,"
    " user_name TEXT NOT NULL,"
    " kind TEXT NOT NULL,"  # issue | feedback
    " message TEXT NOT NULL,"
    " status TEXT NOT NULL DEFAULT 'open')"
)


def _init_schema() -> None:
    with closing(_cx()) as conn, conn:
        conn.executescript(_SCHEMA)


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def submit(user: dict[str, Any], kind: str, message: str) -> dict[str, Any]:
    """Public and private content stay private: the message is stored
    once and surfaced only to admins — this is a feature, not a leak."""
    if kind not in ("issue", "feedback"):
        kind = "feedback"
    msg = str(message).strip()[:4000]
    if len(msg) < 5:
        raise ValueError("Message too short.")
    with _LOCK, closing(_cx()) as conn, conn:
        conn.execute(
            "INSERT INTO feedback (ts, user_id, user_name, kind, message)"
            " VALUES (?, ?, ?, ?, ?)",
            (_now_iso(), user["id"], user["username"], kind, msg),
        )
        row = conn.execute(
            "SELECT id FROM feedback ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return {"id": row["id"], "kind": kind, "stored": True}


def list_feedback(limit: int = 100, open_only: bool = False) -> list[dict]:
    sql = "SELECT id, ts, user_id, user_name, kind, message, status FROM feedback"
    if open_only:
        sql += " WHERE status = 'open'"
    sql += " ORDER BY id DESC LIMIT ?"
    with closing(_cx()) as conn:
        rows = conn.execute(sql, (min(max(limit, 1), 500),)).fetchall()
    return [dict(r) for r in rows]
    return [dict(r) for r in rows]
