"""Global cloud budget (Section 13: application-wide spending limits).

Admin sets a global *daily* cloud budget in USD; the provider dispatch
path refuses cloud calls once today's estimated cloud spend has hit it.
Local Ollama stays free and unaffected — that's the BUSINESS.md rule
("local-first; cloud is premium"), and it means a student can always
keep studying offline even when the budget closes. The current budget
is stored in app.db settings; changing it is an audited admin action.
"""

from __future__ import annotations

import contextlib
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
    "CREATE TABLE IF NOT EXISTS settings ( key TEXT PRIMARY KEY, value TEXT NOT NULL)"
)


def _init_schema() -> None:
    with closing(_cx()) as conn, conn:
        conn.executescript(_SCHEMA)


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def get_daily_budget() -> float | None:
    with contextlib.closing(_cx()) as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = 'daily_budget_usd'"
        ).fetchone()
    if row is None or str(row["value"]).strip() == "":
        return None
    try:
        return float(row["value"])
    except (TypeError, ValueError):
        return None


def set_daily_budget(usd: Any) -> dict[str, Any]:
    """None clears the budget; 0 disables all cloud spend."""
    with _LOCK, contextlib.closing(_cx()) as conn, conn:
        if usd is None or usd == "":
            conn.execute(
                "INSERT INTO settings (key, value) VALUES"
                " ('daily_budget_usd', '')"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value"
            )
            return {"daily_budget_usd": None}
        value = float(usd)
        if value < 0 or value > 10_000:
            raise ValueError("Budget must be between 0 and 10000 USD.")
        conn.execute(
            "INSERT INTO settings (key, value) VALUES"
            " ('daily_budget_usd', ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(value),),
        )
    return {"daily_budget_usd": value}


def cloud_spent_today_usd() -> float:
    """Estimated cloud (non-Ollama) spend from the usage ledger — the same
    numbers the user-facing ledger records."""
    try:
        from services.usage_service import cloud_spend

        return cloud_spend(_today())
    except Exception:
        return 0.0


def cloud_spending_allowed() -> tuple[bool, str | None]:
    budget = get_daily_budget()
    if budget is None:
        return True, None
    spent = cloud_spent_today_usd()
    if spent >= budget:
        return (
            False,
            (
                "Global daily cloud budget "
                f"(${budget:.2f}) is spent for today."
                " Local models remain available."
            ),
        )
    return True, None


def current_budget_state() -> dict[str, Any]:
    budget = get_daily_budget()
    spent = cloud_spent_today_usd()
    if budget is None:
        return {
            "daily_budget_usd": None,
            "spent_today_usd": spent,
            "remaining_usd": None,
            "status": "unlimited",
        }
    remaining = max(0.0, round(budget - spent, 6))
    return {
        "daily_budget_usd": budget,
        "spent_today_usd": spent,
        "remaining_usd": remaining,
        "status": "exhausted" if remaining <= 0 else "active",
    }
