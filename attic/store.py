"""SQLite store for ARIA multi-user: users, sessions, credit ledger, payments.

Why SQLite here
---------------
ARIA already stores everything in DATA_DIR (JSON files + ChromaDB). This adds
a REAL transactional store for the data that money depends on (balances,
reservations, payments) while keeping the app dependency-light (stdlib
sqlite3, no server to host). WAL + `BEGIN IMMEDIATE` give serialized writers
and crash safety for the latency profile of one small deployment.

Postgres path: the schema below is plain SQL that also runs on Postgres
(`AUTOINCREMENT` is the only SQLite-ism — see docs/MULTIUSER_BILLING.md for
the documented migration to `BIGSERIAL`). To move: `sqlite3 ... .dump` or
run the documented migration, then switch `ARIA_STORE_DSN` to a
`postgresql://` URL handled by the same SQL (requires psycopg — deliberate
future step, not silently switched here).

Schema (see _MIGRATIONS):
  users(id PK, username UNIQUE, password_hash, salt, role, plan,
        allowance_expiry, profile_json, suspended, created_at)
  sessions(token_hash PK UNIQUE, user_id, created_at, expires_at, revoked)
  credit_grants(id PK, user_id, amount_cents, remaining_cents, type,
        reason, ref, expires_at, created_at)
  credit_transactions(id PK, user_id, amount_cents(±), type, reason, ref,
        idempotency_key UNIQUE, created_at)   — audit ledger, append-only
  credit_reservations(id PK, user_id, cents, request_id UNIQUE, provider,
        model, max_tokens, status(active|settled|released|expired),
        estimated_in_tokens, created_at, settled_at)
  usage_events(id PK, user_id, request_id, provider, model, prompt_tokens,
        completion_tokens, cost_micro_usd, estimated, ok, created_at)
  payment_events(event_id UNIQUE, provider, user_id, kind, amount_cents,
        currency, status, payload_json, created_at)
"""

import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from models.database import DATA_DIR

DB_PATH = DATA_DIR / "aria.sqlite3"

_MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
    CREATE TABLE IF NOT EXISTS users (
      id TEXT PRIMARY KEY,
      username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      salt TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'user',
      plan TEXT NOT NULL DEFAULT 'free',
      allowance_expiry TEXT,
      profile_json TEXT NOT NULL DEFAULT '{}',
      suspended INTEGER NOT NULL DEFAULT 0,
      created_at REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS sessions (
      token_hash TEXT PRIMARY KEY,
      user_id TEXT NOT NULL REFERENCES users(id),
      created_at REAL NOT NULL,
      expires_at REAL NOT NULL,
      revoked INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
    """,
    ),
    (
        2,
        """
    CREATE TABLE IF NOT EXISTS credit_grants (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id TEXT NOT NULL REFERENCES users(id),
      amount_cents INTEGER NOT NULL,
      remaining_cents INTEGER NOT NULL,
      type TEXT NOT NULL,
      reason TEXT NOT NULL,
      ref TEXT,
      expires_at REAL,
      created_at REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_grants_user ON credit_grants(user_id);
    CREATE TABLE IF NOT EXISTS credit_transactions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id TEXT NOT NULL REFERENCES users(id),
      amount_cents INTEGER NOT NULL,
      type TEXT NOT NULL,
      reason TEXT NOT NULL,
      ref TEXT,
      idempotency_key TEXT NOT NULL UNIQUE,
      created_at REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_txn_user ON credit_transactions(user_id);
    """,
    ),
    (
        3,
        """
    CREATE TABLE IF NOT EXISTS credit_reservations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id TEXT NOT NULL REFERENCES users(id),
      request_id TEXT NOT NULL UNIQUE,
      cents INTEGER NOT NULL,
      provider TEXT NOT NULL,
      model TEXT NOT NULL,
      max_tokens INTEGER NOT NULL,
      estimated_in_tokens INTEGER NOT NULL DEFAULT 0,
      status TEXT NOT NULL DEFAULT 'active',
      created_at REAL NOT NULL,
      settled_at REAL
    );
    CREATE INDEX IF NOT EXISTS idx_resv_user ON credit_reservations(user_id);
    CREATE TABLE IF NOT EXISTS usage_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id TEXT REFERENCES users(id),
      request_id TEXT,
      provider TEXT NOT NULL,
      model TEXT NOT NULL,
      prompt_tokens INTEGER NOT NULL DEFAULT 0,
      completion_tokens INTEGER NOT NULL DEFAULT 0,
      cost_micro_usd INTEGER NOT NULL DEFAULT 0,
      estimated INTEGER NOT NULL DEFAULT 0,
      ok INTEGER NOT NULL DEFAULT 1,
      created_at REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_usage_user ON usage_events(user_id);
    """,
    ),
    (
        4,
        """
    CREATE TABLE IF NOT EXISTS payment_events (
      event_id TEXT PRIMARY KEY,
      provider TEXT NOT NULL,
      user_id TEXT,
      kind TEXT NOT NULL,
      amount_cents INTEGER NOT NULL DEFAULT 0,
      currency TEXT NOT NULL DEFAULT 'usd',
      status TEXT NOT NULL,
      payload_json TEXT NOT NULL DEFAULT '{}',
      created_at REAL NOT NULL
    );
    """,
    ),
    (
        5,
        """
    ALTER TABLE users ADD COLUMN allowance_renewed_at REAL;
    ALTER TABLE users ADD COLUMN plan_sourced TEXT;
    """,
    ),
]

_conn: sqlite3.Connection | None = None
_init_lock = threading.Lock()
_initialized = False


def _apply_migrations(conn: sqlite3.Connection) -> None:
    with conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version INTEGER PRIMARY KEY, applied_at REAL NOT NULL)"
        )
        applied = {
            row[0] for row in conn.execute("SELECT version FROM schema_migrations")
        }
        for version, sql in _MIGRATIONS:
            if version in applied:
                continue
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (version, time.time()),
            )


def get_conn() -> sqlite3.Connection:
    """Module connection (WAL + busy timeout). NOT created at import time so
    tests that relocate ARIA_DATA_DIR first can still control the path."""
    global _conn, _initialized
    with _init_lock:
        if _conn is None or not _initialized:
            Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
            c = sqlite3.connect(str(DB_PATH), timeout=30.0)
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            c.execute("PRAGMA foreign_keys=ON")
            c.row_factory = sqlite3.Row
            _apply_migrations(c)
            _conn = c
            _initialized = True
    return _conn


def reset_for_tests(db_path: Path | None = None) -> None:
    """Point the store at another file (tests isolate ARIA_DATA_DIR)."""
    global _conn, _initialized, DB_PATH
    with _init_lock:
        DB_PATH = db_path or (DATA_DIR / "aria.sqlite3")
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
        _conn = None
        _initialized = False


@contextmanager
def write_tx():
    """Serialized writer: BEGIN IMMEDIATE + busy wait; commits or rolls back.

    Use for EVERY balance/state mutation so concurrent requests cannot
    interleave a check-then-spend (TOCTOU)."""
    conn = get_conn()
    for attempt in range(5):
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except Exception:
                conn.rollback()
                raise
            conn.commit()
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < 4:
                time.sleep(0.05 * (attempt + 1))
                continue
            raise
