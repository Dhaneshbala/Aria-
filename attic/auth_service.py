"""Authentication: users, sessions (hashed at rest), roles, local-owner boot.

Local-first compatibility
-------------------------
ARIA stays a single-owner local app by default: with ARIA_MULTIUSER unset,
`require_user` resolves to the auto-created local OWNER — meaning today's
flows keep working with no login. Set ARIA_MULTIUSER=1 (a shared server) to
require real accounts: every private/AI endpoint needs a Bearer session token
and data is isolated per user (see services/userctx.py).

Security properties
-------------------
* passwords: scrypt (stdlib OpenSSL), per-user random salt, server-side pepper
  from ARIA_AUTH_PEPPER (optional but recommended in production).
* sessions: 32-byte urlsafe token shown ONCE; only its SHA-256 is stored;
  expiry (ARIA_SESSION_TTL_H, default 24h) + explicit revocation (logout).
* roles: user | admin | test. Admin endpoints must check role server-side.
* IDs are opaque `u_<uuid4-hex12>` — never derivable from usernames.
"""

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import uuid

from models import store

# ── Roles & plans ────────────────────────────────────────────────────────────
ADMIN = "admin"
USER = "user"
TEST = "test"


class AuthError(Exception):
    """Raised with a machine-readable reason; routers map to 401/403/4xx."""

    def __init__(self, message: str, status: int = 401):
        super().__init__(message)
        self.status = status


def _pepper() -> str:
    return os.environ.get("ARIA_AUTH_PEPPER", "")


def _hash_password(password: str, salt: str) -> str:
    # scrypt: memory-hard; n=2**14 r=8 p=1 is the OWASP floor for interactive
    pw = (password + _pepper()).encode()
    dk = hashlib.scrypt(pw, salt=salt.encode(), n=2**14, r=8, p=1, dklen=32)
    return dk.hex()


# ── Users ────────────────────────────────────────────────────────────────────


def create_user(
    username: str,
    password: str,
    role: str = USER,
    plan: str = "free",
    suspended: bool = False,
) -> sqlite3.Row:
    username = (username or "").strip().lower()
    if not username or len(username) > 60:
        raise AuthError("username must be 1-60 chars", 400)
    if len(password) < 8:
        raise AuthError("password must be at least 8 characters", 400)
    salt = secrets.token_hex(16)
    uid = f"u_{uuid.uuid4().hex[:12]}"
    with store.write_tx() as conn:
        try:
            conn.execute(
                "INSERT INTO users(id, username, password_hash, salt, role, plan,"
                " suspended, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    uid,
                    username,
                    _hash_password(password, salt),
                    salt,
                    role if role in (ADMIN, USER, TEST) else USER,
                    plan if plan in ("free", "premium", "test") else "free",
                    1 if suspended else 0,
                    time.time(),
                ),
            )
        except sqlite3.IntegrityError:
            raise AuthError("username already taken", 409) from None
        row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return row


def get_user_by_username(username: str):
    lookup = (username or "").strip().lower()
    conn = store.get_conn()
    return conn.execute("SELECT * FROM users WHERE username=?", (lookup,)).fetchone()


def get_user(uid: str):
    conn = store.get_conn()
    return conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()


def verify_login(username: str, password: str):
    """Return the user row on success; raise AuthError otherwise.

    message() is deliberately vague on which factor failed."""
    row = get_user_by_username(username)
    # Always run a hash to keep timing flat for missing users.
    if row is None:
        _hash_password(password or "", secrets.token_hex(16))
        raise AuthError("invalid username or password", 401)
    if row["suspended"]:
        raise AuthError("account suspended", 403)
    if not hmac.compare_digest(
        _hash_password(password or "", row["salt"]), row["password_hash"]
    ):
        raise AuthError("invalid username or password", 401)
    return row


def count_users() -> int:
    conn = store.get_conn()
    return int(conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"])


def bootstrap_owner() -> "sqlite3.Row":
    """Create the implicit local OWNER (admin) once, no username/password.

    Used in single-user local mode: anything that needs an identity gets the
    owner. In multi-user mode the owner is just a normal admin account."""
    conn = store.get_conn()
    row = conn.execute("SELECT * FROM users ORDER BY created_at LIMIT 1").fetchone()
    if row:
        return row
    uid = f"u_{uuid.uuid4().hex[:12]}"
    salt = secrets.token_hex(16)
    with store.write_tx() as connx:
        connx.execute(
            "INSERT INTO users(id, username, password_hash, salt, role, plan,"
            " suspended, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                uid,
                "local-owner",
                _hash_password(_random_dev_password(), salt),
                salt,
                ADMIN,
                "free",
                0,
                time.time(),
            ),
        )
        row = connx.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return row


def _random_dev_password() -> str:
    return secrets.token_urlsafe(24)  # unusable login (hash never shown)


# ── Sessions ────────────────────────────────────────────────────────────────


def _ttl_seconds() -> float:
    try:
        return float(os.environ.get("ARIA_SESSION_TTL_H", "24")) * 3600
    except Exception:
        return 86400.0


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode()).hexdigest()
    ttl = _ttl_seconds()
    with store.write_tx() as conn:
        conn.execute(
            "INSERT INTO sessions(token_hash, user_id, created_at, expires_at)"
            " VALUES (?,?,?,?)",
            (digest, user_id, time.time(), time.time() + ttl),
        )
    return token


def resolve_session(token: str) -> "sqlite3.Row | None":
    """Bearer token → active user row, or None. Sheds expired/revoked rows."""
    if not token:
        return None
    digest = hashlib.sha256(token.encode()).hexdigest()
    conn = store.get_conn()
    row = conn.execute(
        "SELECT s.user_id, s.expires_at, s.revoked, u.* FROM sessions s"
        " JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?",
        (digest,),
    ).fetchone()
    if row is None or row["revoked"] or row["expires_at"] < time.time():
        return None
    if row["suspended"]:
        raise AuthError("account suspended", 403)
    return row


def revoke_session(token: str) -> bool:
    digest = hashlib.sha256(token.encode()).hexdigest()
    with store.write_tx() as conn:
        cur = conn.execute(
            "UPDATE sessions SET revoked=1 WHERE token_hash=?", (digest,)
        )
        return cur.rowcount > 0


def purge_expired_sessions() -> int:
    with store.write_tx() as conn:
        cur = conn.execute("DELETE FROM sessions WHERE expires_at < ?", (time.time(),))
        return cur.rowcount


def set_profile(uid: str, profile: dict) -> None:
    clean = {
        k: v
        for k, v in (profile or {}).items()
        if k in ("student_name", "student_age", "student_grade", "grade")
        and isinstance(v, (str, int))
    }
    if len(str(clean)) > 2000:
        raise AuthError("profile too large", 400)
    with store.write_tx() as conn:
        conn.execute(
            "UPDATE users SET profile_json=? WHERE id=?",
            (json.dumps(clean), uid),
        )


def get_profile(uid: str) -> dict:
    row = get_user(uid)
    if not row:
        return {}
    try:
        return json.loads(row["profile_json"] or "{}")
    except Exception:
        return {}


def set_plan(uid: str, plan: str, sourced: str = "admin") -> None:
    with store.write_tx() as conn:
        conn.execute(
            "UPDATE users SET plan=?, plan_sourced=? WHERE id=?",
            (plan if plan in ("free", "premium", "test") else "free", sourced, uid),
        )


def find_test_usernames() -> list[str]:
    conn = store.get_conn()
    return [
        r["username"]
        for r in conn.execute("SELECT username FROM users WHERE role='test'")
    ]
