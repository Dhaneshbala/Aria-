"""Authentication endpoints (Section 13 Stage 1).

Registration/login/logout/profile. New accounts are always students —
there is no API input anywhere that can set a role; that exists only in
the CLI bootstrap and superadmin-only admin endpoints.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from services import accounts, credits, gate
from services.audit import log as audit_log

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _me_payload(user: dict) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "role": user["role"],
        "plan": user["plan"],
        "status": user["status"],
        "auth_mode": accounts.auth_mode(),
    }


@router.post("/register")
async def register(request: Request):
    if accounts.accounts_enabled() and not accounts.open_registration():
        raise HTTPException(
            status_code=403,
            detail="Registration is closed. Ask an administrator for an account.",
        )
    body = await request.json()
    username = str(body.get("username", "")).strip().lower()
    password = str(body.get("password", ""))
    display = str(body.get("display_name", "")).strip()[:64] or None
    try:
        user = accounts.create_user(username, password, display)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    credits.ensure_wallet(user["id"])
    audit_log(
        user["id"],
        user["username"],
        "register",
        outcome="ok",
        target=f"user:{user['id']}",
    )
    token = accounts.create_session(user["id"])
    return {**_me_payload(user), "token": token}


@router.post("/login")
async def login(request: Request):
    body = await request.json()
    username = str(body.get("username", "")).strip().lower()
    password = str(body.get("password", ""))
    ip = request.client.host if request.client else "?"
    key = f"{username}|{ip}"
    if not accounts.check_login_allowed(key):
        raise HTTPException(
            status_code=429, detail="Too many failed attempts; wait 10 minutes."
        )
    user = accounts.authenticate(username, password)
    if user is None:
        accounts.record_login_result(key, False)
        audit_log(None, username, "login", outcome="failed", meta={"ip": ip})
        raise HTTPException(status_code=401, detail="Wrong username or password.")
    accounts.record_login_result(key, True)
    accounts.set_last_seen(user["id"])
    token = accounts.create_session(user["id"])
    audit_log(user["id"], user["username"], "login", outcome="ok", meta={"ip": ip})
    return {**_me_payload(user), "token": token}


@router.post("/admin/unlock")
async def admin_unlock(request: Request):
    """Step-up: re-verify password to enable admin *mutations* for 15 min."""
    if not accounts.accounts_enabled():
        raise HTTPException(status_code=404, detail="Not applicable in local mode.")
    current = gate.current_user(request)
    body = await request.json()
    user = accounts.authenticate(
        str(body.get("username", "")), str(body.get("password", ""))
    )
    if user is None or user["id"] != current["id"]:
        raise HTTPException(status_code=401, detail="Re-verification failed.")
    if user["role"] not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Only admin accounts can unlock.")
    token = getattr(request.state, "session_token", "")
    if not token:
        raise HTTPException(status_code=401, detail="No session token provided.")
    accounts.admin_unlock(token)
    audit_log(user["id"], user["username"], "admin_unlock", outcome="ok")
    return {"unlocked": True, "window_minutes": 15}


@router.post("/logout")
async def logout(request: Request):
    token = getattr(request.state, "session_token", None)
    if token:
        accounts.revoke_self(token)
    return {"ok": True}


@router.get("/me")
async def me(request: Request):
    return _me_payload(gate.current_user(request))


@router.patch("/me")
async def update_me(request: Request):
    user = gate.current_user(request)
    body = await request.json()
    currentUser = accounts.get_user_by_id(user["id"])
    if currentUser is None or currentUser["status"] != "active":
        raise HTTPException(status_code=403, detail="Account unavailable.")
    updates = {}
    if "display_name" in body:
        updates["display_name"] = str(body["display_name"]).strip()[:64]
    if "password" in body:
        cur = str(body.get("current_password", ""))
        if not cur:
            raise HTTPException(
                status_code=400, detail="Provide current_password to change it."
            )
        try:
            accounts.change_password(
                user["id"], str(body.get("current_password", "")), str(body["password"])
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        audit_log(user["id"], user["username"], "password_change", outcome="ok")
    if updates:
        try:
            user = accounts.update_user(user["id"], updates)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        audit_log(
            user["id"], user["username"], "profile_update", target=str(user["id"])
        )
    return _me_payload(user)


@router.delete("/me")
async def delete_me(request: Request):
    """Account deletion (Section 13A). Re-verifies the password first —
    a stolen unlocked tab must not be able to nuke the account. Stage 1
    deactivates + revokes sessions; owned feature-file purge is Stage 2
    and is reported honestly here."""
    user = gate.current_user(request)
    if accounts.auth_mode() != "accounts":
        raise HTTPException(status_code=404, detail="Not applicable in local mode.")
    body = await request.json()
    current = accounts.get_user_by_id(user["id"])
    if current is None or not accounts.verify_password(
        str(body.get("password", "")), current["password_hash"]
    ):
        raise HTTPException(status_code=401, detail="Password re-check failed.")
    accounts.soft_delete_user(user["id"])
    audit_log(user["id"], user["username"], "account_deleted", target=str(user["id"]))
    return {
        "deleted": True,
        "note": "Feature files (notes/todos etc.) are purged in Stage 2; chat history was already personal.",
    }


@router.get("/me/wallet")
async def wallet(request: Request):
    user = gate.current_user(request)
    credits.ensure_wallet(user["id"])
    bal = credits.balance_micro(user["id"])
    history = [
        {
            **h,
            "delta_usd": round(h["delta_micro"] / 1_000_000, 6),
            "balance_usd": round(h["balance_after_micro"] / 1_000_000, 6),
        }
        for h in credits.history(user["id"], limit=50)
    ]
    return {
        "balance_usd": round(bal / 1_000_000, 6),
        "history": history,
        "payments_note": "Card purchases are not connected yet (docs/BUSINESS.md"
        " milestone). Admin-entered payments — money you verified outside"
        " ARIA, e.g. a bank transfer — appear as ledger entries here.",
    }
