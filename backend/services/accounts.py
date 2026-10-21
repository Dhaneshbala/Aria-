"""Accounts core — users, sessions, roles (Section 13 Stage 1).

SQLite at DATA_DIR/app.db. Passwords: hashlib.scrypt (stdlib), stored as
``scrypt$n$r$p$salt_hex$hash_hex``. Sessions: opaque ``ses_…`` tokens,
only their SHA-256 lives server-side.

Two modes, selected by env ``ARIA_AUTH_MODE``:
- ``local``    (default) — today's single-user behaviour: every request
  is attributed to the built-in ``local-owner`` account; nothing is
  required of the user. The family Mac keeps working exactly as now.
- ``accounts`` — real registration/login. New accounts are students;
  admin/superadmin exist only via `python -m tools.superadmin` or this
  module's bootstrap (never through any API input).

Roles: student < admin < superadmin, enforced in services/gate.py.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()

_ROLES = ("student", "admin", "superadmin")
_MIN_PASSWORD = 10
_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")

DEFAULT_LOCAL_USER = "local-owner"


def auth_mode() -> str:
    return os.environ.get("ARIA_AUTH_MODE", "local").strip().lower() or "local"


def accounts_enabled() -> bool:
    return auth_mode() == "accounts"


def open_registration() -> bool:
    """Accounts mode: is public self-signup allowed? Default on for the
    pilot; set ARIA_OPEN_REGISTRATION=0 to close it (CLI/superadmin can
    still add people is future work — closing signup is the safety valve)."""
    return os.environ.get("ARIA_OPEN_REGISTRATION", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


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
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  display_name TEXT,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'student',
  status TEXT NOT NULL DEFAULT 'active',   -- active | suspended | deleted
  plan TEXT NOT NULL DEFAULT 'free',       -- free | premium
  created_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token_hash TEXT NOT NULL UNIQUE,
  user_id INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  last_used_at TEXT NOT NULL,
  admin_unlocked_until TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
"""

_SESSION_DAYS = 7.0  # session lifetime in days


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _init_schema() -> None:
    with closing(_cx()) as conn, conn:
        conn.executescript(_SCHEMA)


# ---------------------------------------------------------------- hashing


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    n, r, p = 2**14, 8, 1
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=32
    )
    return f"scrypt${n}${r}${p}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, hash_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=32,
        )
        return secrets.compare_digest(digest.hex(), hash_hex)
    except Exception:
        return False


def validate_username(username: str) -> str | None:
    if not _USERNAME_RE.match(username):
        return (
            "3–32 chars: lowercase letters, digits, . _ - (starts with letter/digit)."
        )
    return None


def validate_password(password: str) -> str | None:
    if len(password) < _MIN_PASSWORD:
        return f"At least {_MIN_PASSWORD} characters."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
        return "Must contain letters and digits."
    return None


# ------------------------------------------------------------------ users


def _default_local_user() -> dict[str, Any]:
    """The built-in single-user account everything is attributed to in
    local mode. Created lazily, never logged into, no credentials."""
    with _LOCK, closing(_cx()) as conn, conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (DEFAULT_LOCAL_USER,)
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO users (username, display_name, password_hash,"
                " role, status, plan, created_at, last_seen_at)"
                " VALUES (?, 'Owner', ?, 'superadmin', 'active', 'premium',"
                " ?, ?)",
                (
                    DEFAULT_LOCAL_USER,
                    hash_password(secrets.token_hex(24)),  # unusable pw
                    _iso(_now()),
                    _iso(_now()),
                ),
            )
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (DEFAULT_LOCAL_USER,)
            ).fetchone()
        return dict(row)


def ensure_local_user() -> dict[str, Any]:
    return _default_local_user()


def create_user(
    username: str,
    password: str,
    display_name: str | None = None,
    role: str = "student",
) -> dict[str, Any]:
    msg = validate_username(username) or validate_password(password)
    if msg:
        raise ValueError(msg)
    if role not in _ROLES:
        raise ValueError("Unknown role.")
    with _LOCK, closing(_cx()) as conn, conn:
        try:
            conn.execute(
                "INSERT INTO users (username, display_name, password_hash,"
                " role, status, plan, created_at, last_seen_at)"
                " VALUES (?, ?, ?, ?, 'active', 'free', ?, ?)",
                (
                    username,
                    display_name or username,
                    hash_password(password),
                    role,
                    _iso(_now()),
                    _iso(_now()),
                ),
            )
        except sqlite3.IntegrityError as e:
            raise ValueError("That username is already taken.") from e
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
    return dict(row)


def get_user_by_username(username: str) -> dict[str, Any] | None:
    with closing(_cx()) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
    return dict(row) if row is not None else None


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with closing(_cx()) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row is not None else None


def authenticate(username: str, password: str) -> dict[str, Any] | None:
    user = get_user_by_username(username)
    if user is None or user["status"] != "active":
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def set_last_seen(user_id: int) -> None:
    with _LOCK, closing(_cx()) as conn, conn:
        conn.execute(
            "UPDATE users SET last_seen_at = ? WHERE id = ?",
            (_iso(_now()), user_id),
        )


def update_user(user_id: int, updates: dict[str, Any]) -> dict[str, Any]:
    """Whitelisted admin edits. Every field gets its own prepared
    statement — no constructed SQL (the string-building pattern bandit
    flags as B608 can't exist here by construction)."""
    if "status" in updates and updates["status"] not in (
        "active",
        "suspended",
        "deleted",
    ):
        raise ValueError("Bad status.")
    if "plan" in updates and updates["plan"] not in ("free", "premium"):
        raise ValueError("Bad plan.")
    if "role" in updates and updates["role"] not in _ROLES:
        raise ValueError("Bad role.")
    if not updates:
        raise ValueError("Nothing to update.")
    with _LOCK, closing(_cx()) as conn, conn:
        if "status" in updates:
            conn.execute(
                "UPDATE users SET status = ? WHERE id = ?",
                (updates["status"], user_id),
            )
        if "plan" in updates:
            conn.execute(
                "UPDATE users SET plan = ? WHERE id = ?",
                (updates["plan"], user_id),
            )
        if "role" in updates:
            conn.execute(
                "UPDATE users SET role = ? WHERE id = ?",
                (updates["role"], user_id),
            )
        if "display_name" in updates:
            dn = str(updates["display_name"]).strip()[:64]
            if dn:
                conn.execute(
                    "UPDATE users SET display_name = ? WHERE id = ?",
                    (dn, user_id),
                )
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise ValueError("No such user.")
    return dict(row)


def change_password(user_id: int, old: str, new: str) -> None:
    user = get_user_by_id(user_id)
    if user is None or not verify_password(old, user["password_hash"]):
        raise ValueError("Current password is incorrect.")
    msg = validate_password(new)
    if msg:
        raise ValueError(msg)
    with _LOCK, closing(_cx()) as conn, conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(new), user_id),
        )
        # Password change revokes every other session.
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def soft_delete_user(user_id: int) -> None:
    """Account deletion per spec: user is unusable, sessions revoked, and
    the account's partitioned feature files are purged immediately
    (DATA_DIR/users/<username> — never the base legacy stores, never the
    built-in local account)."""
    user = get_user_by_id(user_id)
    if user is None:
        raise ValueError("No such user.")
    if user["username"] == DEFAULT_LOCAL_USER:
        raise ValueError("The built-in local account cannot be deleted.")
    update_user(user_id, {"status": "deleted"})
    revoke_sessions(user_id)
    try:
        from services.scoping import purge_account_files

        purge_account_files(user["username"])
    except Exception:
        logger.warning(
            "Purging files for deleted user %s failed.", user_id, exc_info=True
        )


# --------------------------------------------------------------- sessions


def create_session(user_id: int, days: float = _SESSION_DAYS) -> str:
    raw = "ses_" + secrets.token_hex(24)
    with _LOCK, closing(_cx()) as conn, conn:
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at,"
            " expires_at, last_used_at) VALUES (?, ?, ?, ?, ?)",
            (
                hashlib.sha256(raw.encode()).hexdigest(),
                user_id,
                _iso(_now()),
                _iso(_now() + timedelta(days=days)),
                _iso(_now()),
            ),
        )
    return raw


def resolve_session(raw: str) -> dict[str, Any] | None:
    """→ {user…} for a live session, else None. Stamps activity."""
    if not raw:
        return None
    now_iso = _iso(_now())
    with _LOCK, closing(_cx()) as conn:
        row = conn.execute(
            "SELECT s.id AS sid, s.expires_at, s.admin_unlocked_until,"
            " u.*, u.id AS user_id FROM sessions s JOIN users u"
            " ON u.id = s.user_id"
            " WHERE s.token_hash = ?",
            (hashlib.sha256(raw.encode()).hexdigest(),),
        ).fetchone()
        if row is None:
            return None
        data = dict(row)
        if data["expires_at"] <= now_iso or data["status"] != "active":
            return None
        # Stamp session + user activity (throttled: ≥60s apart)
        try:
            stale = (
                data["last_used_at"]
                and _now()
                - datetime.strptime(data["last_used_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=UTC
                )
            ).total_seconds() > 60
        except Exception:
            stale = True
        if stale:
            with conn:
                conn.execute(
                    "UPDATE sessions SET last_used_at = ? WHERE id = ?",
                    (now_iso, data["sid"]),
                )
                conn.execute(
                    "UPDATE users SET last_seen_at = ? WHERE id = ?",
                    (now_iso, data["user_id"]),
                )
    return data


def admin_unlock(raw: str, minutes: float = 15) -> None:
    """Step-up: after this, admin *mutating* actions are permitted for
    ``minutes`` — fresh recent verification for privileged ops."""
    with _LOCK, closing(_cx()) as conn, conn:
        conn.execute(
            "UPDATE sessions SET admin_unlocked_until = ? WHERE token_hash = ?",
            (
                _iso(_now() + timedelta(minutes=minutes)),
                hashlib.sha256(raw.encode()).hexdigest(),
            ),
        )


def admin_unlocked(data: dict[str, Any]) -> bool:
    until = data.get("admin_unlocked_until")
    if not until:
        return False
    try:
        return (
            datetime.strptime(until, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC) > _now()
        )
    except Exception:
        return False


def revoke_sessions(user_id: int) -> None:
    with _LOCK, closing(_cx()) as conn, conn:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def revoke_self(raw: str) -> None:
    with _LOCK, closing(_cx()) as conn, conn:
        conn.execute(
            "DELETE FROM sessions WHERE token_hash = ?",
            (hashlib.sha256(raw.encode()).hexdigest(),),
        )


# -------------------------------------------------------- admin queries


def user_count() -> dict[str, Any]:
    with closing(_cx()) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS total,"
            " SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active,"
            " SUM(CASE WHEN status = 'suspended' THEN 1 ELSE 0 END)"
            "   AS suspended,"
            " SUM(CASE WHEN plan = 'premium' THEN 1 ELSE 0 END) AS premium,"
            " SUM(CASE WHEN plan = 'free' THEN 1 ELSE 0 END) AS free,"
            " SUM(CASE WHEN created_at >= ? THEN 1 ELSE 0 END) AS last_7d,"
            " SUM(CASE WHEN created_at >= ? THEN 1 ELSE 0 END) AS last_30d"
            " FROM users WHERE username != ?",
            (
                _iso(_now() - timedelta(days=7)),
                _iso(_now() - timedelta(days=30)),
                DEFAULT_LOCAL_USER,
            ),
        ).fetchone()
    return dict(row) if row else {}


def active_counts(day_window: float, month_window: float) -> dict[str, int]:
    with closing(_cx()) as conn:
        row = conn.execute(
            "SELECT SUM(CASE WHEN last_seen_at >= ? THEN 1 ELSE 0 END) AS dau,"
            " SUM(CASE WHEN last_seen_at >= ? THEN 1 ELSE 0 END) AS mau"
            " FROM users WHERE username != ?",
            (
                _iso(_now() - timedelta(hours=day_window)),
                _iso(_now() - timedelta(days=month_window)),
                DEFAULT_LOCAL_USER,
            ),
        ).fetchone()
    data = dict(row) if row else {}
    return {"dau": data.get("dau", 0) or 0, "mau": data.get("mau", 0) or 0}


def list_users(query: str = "", include_local: bool = False) -> list[dict[str, Any]]:
    """Minimal PII for admin support views: never passwords/tokens, never
    private content."""
    sql = (
        "SELECT id, username, display_name, role, status, plan,"
        " created_at, last_seen_at FROM users"
    )
    params: list[Any] = []
    where = []
    if not include_local:
        where.append("username != ?")
        params.append(DEFAULT_LOCAL_USER)
    if query:
        where.append("(username LIKE ? OR display_name LIKE ?)")
        like = f"%{query}%"
        params.extend([like, like])
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id"
    with closing(_cx()) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# ------------------------------------------------------ login hardening

_login_fails: dict[str, tuple[int, float]] = {}


def check_login_allowed(key: str) -> bool:
    fails, first = _login_fails.get(key, (0, 0.0))
    return not (fails >= 10 and time.time() - first < 600)


def record_login_result(key: str, ok: bool) -> None:
    if ok:
        _login_fails.pop(key, None)
        return
    fails, first = _login_fails.get(key, (0, 0.0))
    if time.time() - first > 600:
        fails, first = 0, time.time()
    _login_fails[key] = (fails + 1, first)


def bootstrap_superadmin(
    username: str, password: str, display_name: str | None = None
) -> dict[str, Any]:
    """Secure initial-admin path: CLI only (`python -m tools.superadmin`).
    Idempotent — promotes an existing account if it exists."""
    existing = get_user_by_username(username)
    if existing is not None:
        return update_user(existing["id"], {"role": "superadmin", "status": "active"})
    return create_user(username, password, display_name, role="superadmin")
