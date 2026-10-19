"""SQLite store: hashed tokens, usage ledger, kill switch.

Design notes (pilot scale, 5-10 users):
- Tokens are stored as SHA-256 hashes; the raw value is shown exactly
  once at creation and never persisted.
- Spend is recomputed from the ledger on every check (SUM over indexed
  day/month columns) — no counters to drift.
- A burst of parallel requests can overshoot a cap slightly before the
  next check sees the spend; the max_tokens clamp bounds that overshoot.
  The Anthropic-side spending limit is the hard backstop.
- One sqlite file per gateway; WAL mode for concurrent read/write.
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tokens (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token_hash TEXT NOT NULL UNIQUE,
  label TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 1,
  daily_cap_usd REAL NOT NULL,
  monthly_cap_usd REAL NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token_id INTEGER NOT NULL REFERENCES tokens(id),
  ts TEXT NOT NULL,
  model TEXT NOT NULL,
  input_tokens INTEGER NOT NULL DEFAULT 0,
  cache_write_tokens INTEGER NOT NULL DEFAULT 0,
  cache_read_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  cost_usd REAL NOT NULL DEFAULT 0,
  day TEXT NOT NULL,
  month TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_token_day ON usage(token_id, day);
CREATE INDEX IF NOT EXISTS idx_usage_token_month ON usage(token_id, month);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""

_UPDATABLE = {"is_active", "daily_cap_usd", "monthly_cap_usd", "label"}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class GatewayStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self.init_schema()

    def _cx(self) -> sqlite3.Connection:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def init_schema(self) -> None:
        with closing(self._cx()) as conn, conn:
            conn.executescript(_SCHEMA)

    # --- tokens ---------------------------------------------------------

    def create_token(
        self,
        label: str,
        daily_cap_usd: float,
        monthly_cap_usd: float,
    ) -> dict[str, Any]:
        """Create a token. The raw value is returned once, never stored."""
        raw = "gw_" + secrets.token_hex(16)
        with closing(self._cx()) as conn, conn:
            cur = conn.execute(
                "INSERT INTO tokens (token_hash, label, is_active,"
                " daily_cap_usd, monthly_cap_usd, created_at)"
                " VALUES (?, ?, 1, ?, ?, ?)",
                (
                    _hash_token(raw),
                    label,
                    daily_cap_usd,
                    monthly_cap_usd,
                    _utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                ),
            )
            token_id = cur.lastrowid
        return {
            "id": token_id,
            "token": raw,
            "label": label,
            "is_active": 1,
            "daily_cap_usd": daily_cap_usd,
            "monthly_cap_usd": monthly_cap_usd,
        }

    def get_by_raw(self, raw: str) -> dict[str, Any] | None:
        with closing(self._cx()) as conn:
            row = conn.execute(
                "SELECT * FROM tokens WHERE token_hash = ?",
                (_hash_token(raw),),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_tokens(self, day: str, month: str) -> list[dict[str, Any]]:
        with closing(self._cx()) as conn:
            rows = conn.execute(
                "SELECT t.id, t.label, t.is_active, t.daily_cap_usd,"
                " t.monthly_cap_usd, t.created_at,"
                " COALESCE((SELECT SUM(u.cost_usd) FROM usage u"
                "   WHERE u.token_id = t.id AND u.day = ?), 0)"
                "   AS spend_today_usd,"
                " COALESCE((SELECT SUM(u.cost_usd) FROM usage u"
                "   WHERE u.token_id = t.id AND u.month = ?), 0)"
                "   AS spend_month_usd"
                " FROM tokens t ORDER BY t.id",
                (day, month),
            ).fetchall()
        return [dict(r) for r in rows]

    def update_token(
        self, token_id: int, updates: dict[str, Any]
    ) -> dict[str, Any] | None:
        fields = {k: v for k, v in updates.items() if k in _UPDATABLE}
        if not fields:
            return None
        sets = ", ".join(f"{k} = ?" for k in fields)
        with closing(self._cx()) as conn, conn:
            cur = conn.execute(
                f"UPDATE tokens SET {sets} WHERE id = ?",
                (*fields.values(), token_id),
            )
            if cur.rowcount == 0:
                return None
            row = conn.execute(
                "SELECT * FROM tokens WHERE id = ?", (token_id,)
            ).fetchone()
        return dict(row) if row is not None else None

    # --- usage ----------------------------------------------------------

    def record_usage(
        self,
        token_id: int,
        model: str,
        input_tokens: int,
        cache_write_tokens: int,
        cache_read_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ) -> None:
        now = _utcnow()
        with closing(self._cx()) as conn, conn:
            conn.execute(
                "INSERT INTO usage (token_id, ts, model, input_tokens,"
                " cache_write_tokens, cache_read_tokens, output_tokens,"
                " cost_usd, day, month)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    token_id,
                    now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    model,
                    int(input_tokens),
                    int(cache_write_tokens),
                    int(cache_read_tokens),
                    int(output_tokens),
                    float(cost_usd),
                    now.strftime("%Y-%m-%d"),
                    now.strftime("%Y-%m"),
                ),
            )

    def spend_for(self, token_id: int) -> dict[str, Any]:
        now = _utcnow()
        day = now.strftime("%Y-%m-%d")
        month = now.strftime("%Y-%m")
        with closing(self._cx()) as conn:
            row = conn.execute(
                "SELECT"
                " COALESCE(SUM(CASE WHEN day = ? THEN cost_usd END), 0) AS today_usd,"
                " COALESCE(SUM(CASE WHEN month = ? THEN cost_usd END), 0) AS month_usd,"
                " COALESCE(SUM(CASE WHEN day = ? THEN input_tokens END), 0)"
                "   AS today_input,"
                " COALESCE(SUM(CASE WHEN day = ? THEN output_tokens END), 0)"
                "   AS today_output"
                " FROM usage WHERE token_id = ?",
                (day, month, day, day, token_id),
            ).fetchone()
        data = dict(row) if row is not None else {}
        return {"day": day, "month": month, **data}

    def totals(self) -> dict[str, Any]:
        """Ledger totals for today and this month, across all tokens."""
        now = _utcnow()
        day = now.strftime("%Y-%m-%d")
        month = now.strftime("%Y-%m")
        with closing(self._cx()) as conn:
            row = conn.execute(
                "SELECT"
                " COALESCE(SUM(CASE WHEN day = ? THEN cost_usd END), 0) AS today_usd,"
                " COALESCE(SUM(CASE WHEN month = ? THEN cost_usd END), 0) AS month_usd,"
                " COALESCE(SUM(CASE WHEN day = ? THEN input_tokens END), 0) AS today_input,"
                " COALESCE(SUM(CASE WHEN day = ? THEN output_tokens END), 0) AS today_output"
                " FROM usage",
                (day, month, day, day),
            ).fetchone()
        data = dict(row) if row is not None else {}
        return {"day": day, "month": month, **data}

    def daily_breakdown(self, days: int = 30) -> list[dict[str, Any]]:
        since = (_utcnow() - timedelta(days=max(days, 1) - 1)).strftime("%Y-%m-%d")
        with closing(self._cx()) as conn:
            rows = conn.execute(
                "SELECT day, SUM(cost_usd) AS cost_usd, SUM(input_tokens)"
                " AS input_tokens, SUM(output_tokens) AS output_tokens"
                " FROM usage WHERE day >= ? GROUP BY day ORDER BY day",
                (since,),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- settings (kill switch) ------------------------------------------

    def get_setting(self, key: str) -> str | None:
        with closing(self._cx()) as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row is not None else None

    def set_setting(self, key: str, value: str) -> None:
        with closing(self._cx()) as conn, conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
