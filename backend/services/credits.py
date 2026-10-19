"""Credit wallet + append-only ledger (Section 13 Stage 1).

Amounts are stored as INTEGER MICRO-dollars (1_000_000 micro = $1):
chat-scale costs are fractions of a cent, so cents would round nearly
every deduction to zero. One balance row per user; every change appends
a ledger row in the same SQLite transaction, recording the resulting
balance. Admin grants require a reason and are audited at the router.
There is deliberately **no API that moves a balance without a ledger
row**.

Payment rails (Stripe / purchases / refunds) are NOT implemented in
Stage 1 — those are BUSINESS.md milestone 2/3 work and the UI says so.
What exists: admin grants, cloud-usage deductions and manual
adjustments, all ledgered with exact balances.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()

_KINDS = ("grant", "usage", "adjustment", "refund")
_MIN_REASON = 3


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
CREATE TABLE IF NOT EXISTS credit_balances (
  user_id INTEGER PRIMARY KEY REFERENCES users(id),
  balance_micro INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS credit_ledger (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  user_id INTEGER NOT NULL REFERENCES users(id),
  delta_micro INTEGER NOT NULL,
  kind TEXT NOT NULL,          -- grant | usage | adjustment | refund
  actor_id INTEGER,
  reason TEXT NOT NULL,
  balance_after_micro INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_credit_ledger_user
  ON credit_ledger(user_id, ts);
"""


def _init_schema() -> None:
    with closing(_cx()) as conn, conn:
        conn.executescript(_SCHEMA)


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_wallet(user_id: int) -> None:
    with _LOCK, closing(_cx()) as conn, conn:
        conn.execute(
            "INSERT OR IGNORE INTO credit_balances (user_id, balance_micro,"
            " updated_at) VALUES (?, 0, ?)",
            (user_id, _now_iso()),
        )


def balance_micro(user_id: int) -> int:
    ensure_wallet(user_id)
    with closing(_cx()) as conn:
        row = conn.execute(
            "SELECT balance_micro FROM credit_balances WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return int(row["balance_micro"]) if row else 0


def _apply(
    conn: sqlite3.Connection,
    user_id: int,
    delta_micro: int,
    kind: str,
    actor_id: int | None,
    reason: str,
) -> int:
    row = conn.execute(
        "SELECT balance_micro FROM credit_balances WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    current = int(row["balance_micro"]) if row else 0
    after = current + delta_micro
    if after < 0:
        raise ValueError("Balance would go negative; operation refused.")
    conn.execute(
        "INSERT INTO credit_ledger (ts, user_id, delta_micro, kind,"
        " actor_id, reason, balance_after_micro)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (_now_iso(), user_id, delta_micro, kind, actor_id, reason, after),
    )
    conn.execute(
        "INSERT INTO credit_balances (user_id, balance_micro, updated_at)"
        " VALUES (?, ?, ?)"
        " ON CONFLICT(user_id) DO UPDATE SET balance_micro ="
        " excluded.balance_micro, updated_at = excluded.updated_at",
        (user_id, after, _now_iso()),
    )
    return after


def apply(
    user_id: int,
    delta_micro: int,
    kind: str,
    reason: str,
    actor_id: int | None = None,
) -> dict[str, Any]:
    """The ONLY way a balance moves. Refuses and raises; always ledgers."""
    if kind not in _KINDS:
        raise ValueError("Bad ledger kind.")
    if (
        not isinstance(delta_micro, int)
        or isinstance(delta_micro, bool)
        or delta_micro == 0
    ):
        raise ValueError("Amount must be a non-zero integer (micro-dollars).")
    if len(str(reason).strip()) < _MIN_REASON:
        raise ValueError("A reason of at least 3 characters is required.")
    reason = str(reason).strip()[:500]
    with _LOCK, closing(_cx()) as conn, conn:
        after = _apply(conn, user_id, delta_micro, kind, actor_id, reason)
    return {
        "user_id": user_id,
        "delta_micro": delta_micro,
        "balance_micro": after,
        "kind": kind,
        "reason": reason,
    }


def history(user_id: int, limit: int = 100) -> list[dict[str, Any]]:
    with closing(_cx()) as conn:
        rows = conn.execute(
            "SELECT ts, delta_micro, kind, actor_id, reason,"
            " balance_after_micro FROM credit_ledger WHERE user_id = ?"
            " ORDER BY id DESC LIMIT ?",
            (user_id, min(max(limit, 1), 1000)),
        ).fetchall()
    return [dict(r) for r in rows]


def totals() -> dict[str, Any]:
    """Admin overview: outstanding balances + ledger activity (USD floats)."""
    with closing(_cx()) as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(balance_micro), 0) AS outstanding_micro"
            " FROM credit_balances"
        ).fetchone()
        grants = conn.execute(
            "SELECT COALESCE(SUM(delta_micro), 0) AS granted_micro,"
            " COUNT(*) AS n FROM credit_ledger WHERE kind = 'grant'"
        ).fetchone()
        usage = conn.execute(
            "SELECT COALESCE(SUM(-delta_micro), 0) AS spent_micro"
            " FROM credit_ledger WHERE kind = 'usage'"
        ).fetchone()
    m = lambda v: round((v or 0) / 1_000_000, 6)
    return {
        "outstanding_usd": m(row["outstanding_micro"] if row else 0),
        "granted_usd": m(grants["granted_micro"] if grants else 0),
        "usage_spent_usd": m(usage["spent_micro"] if usage else 0),
        "ledger_rows": int(grants["n"]) if grants else 0,
    }


def reserve_enough(user_id: int, min_micro: int = 1) -> bool:
    """Pre-dispatch gate: refuse cloud calls on an empty wallet."""
    return balance_micro(user_id) >= min_micro
