"""Tamper-evident audit log (Section 13 Stage 1).

Append-only, hash-chained: each row stores the hash of its predecessor,
so deleting or editing history breaks verification. Records admin
logins/step-ups, role changes, suspensions, credit grants and budget
changes — actor, target, reason, outcome. NEVER records passwords,
tokens, secret values or raw student content.

Verify with ``verify_chain()`` (exposed on the admin API as a flag).
"""

from __future__ import annotations

import hashlib
import json
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
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  actor_id INTEGER,
  actor_name TEXT NOT NULL,
  action TEXT NOT NULL,
  target TEXT,
  reason TEXT,
  outcome TEXT NOT NULL,
  meta TEXT,
  prev_hash TEXT NOT NULL,
  entry_hash TEXT NOT NULL UNIQUE
);
"""


def _init_schema() -> None:
    with closing(_cx()) as conn, conn:
        conn.executescript(_SCHEMA)


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _entry_hash(payload: dict[str, Any], prev_hash: str) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prev_hash + canonical).encode("utf-8")).hexdigest()


def log(
    actor_id: int | None,
    actor_name: str,
    action: str,
    target: str | None = None,
    reason: str | None = None,
    outcome: str = "ok",
    meta: dict[str, Any] | None = None,
) -> None:
    """Append one audit entry, keeping the chain intact."""
    with _LOCK, closing(_cx()) as conn, conn:
        row = conn.execute(
            "SELECT entry_hash FROM audit_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        prev_hash = row["entry_hash"] if row else ""
        ts = _now_iso()
        payload = {
            "ts": ts,
            "actor_id": actor_id,
            "actor": actor_name,
            "action": action,
            "target": target,
            "reason": reason,
            "outcome": outcome,
            "meta": meta or {},
        }
        entry_hash = _entry_hash(payload, prev_hash)
        conn.execute(
            "INSERT INTO audit_log (ts, actor_id, actor_name, action,"
            " target, reason, outcome, meta, prev_hash, entry_hash)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ts,
                actor_id,
                actor_name,
                action,
                target,
                reason,
                outcome,
                json.dumps(meta or {}),
                prev_hash,
                entry_hash,
            ),
        )


def list_entries(limit: int = 200, action: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM audit_log"
    params: list[Any] = []
    if action:
        sql += " WHERE action = ?"
        params.append(action)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(min(max(limit, 1), 1000))
    with closing(_cx()) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def verify_chain() -> bool:
    """Walk the whole log: every row must hash from the previous row's
    entry_hash. Any edit/deletion breaks this → False."""
    with closing(_cx()) as conn:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
    prev = ""
    for row in rows:
        data = dict(row)
        payload = {
            "ts": data["ts"],
            "actor_id": data["actor_id"],
            "actor": data["actor_name"],
            "action": data["action"],
            "target": data["target"],
            "reason": data["reason"],
            "outcome": data["outcome"],
            "meta": json.loads(data["meta"] or "{}"),
        }
        if data["prev_hash"] != prev:
            return False
        if _entry_hash(payload, prev) != data["entry_hash"]:
            return False
        prev = data["entry_hash"]
    return True
