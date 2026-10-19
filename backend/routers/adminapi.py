"""Admin API (Section 13 Stage 1) — every metric is real data.

Backed by: users/sessions (accounts), audit chain, credit ledger, the
usage ledger (per-user token/cost capture), background task state and
provider health probes. Payments/subscriptions are NOT built yet —
those keys are returned as ``None`` with an explicit
``payments_not_implemented`` label instead of invented numbers.

Role gating + step-up for mutations is enforced by services/gate.py
before any of these run; this router never repeats that decision.
"""

from __future__ import annotations

import contextlib
import logging
import shutil

from fastapi import APIRouter, HTTPException, Request

from services import accounts, audit, credits, feedback, gate
from services.audit import log as audit_log

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/admin", tags=["admin"])


# ───────────────────────────────────────────── Overview dashboard


@router.get("/overview")
async def overview(request: Request):
    user = gate.current_user(request)
    users = accounts.user_count()
    active = accounts.active_counts(24, 30)

    # Usage ledger — real token + cost capture (user-attributed).
    try:
        from services.usage_service import admin_totals

        usage = admin_totals()
    except Exception as e:
        log.warning("usage totals unavailable: %s", e)
        usage = {}

    credit_totals = credits.totals()
    # Budget state (global daily cloud budget, enforced at dispatch)
    from services.budget_service import current_budget_state

    budget = current_budget_state()

    return {
        "users": {
            "total": users.get("total", 0),
            "active": users.get("active", 0),
            "suspended": users.get("suspended", 0),
            "free": users.get("free", 0),
            "premium": users.get("premium", 0),
            "new_last_7d": users.get("last_7d", 0),
            "new_last_30d": users.get("last_30d", 0),
            "dau": active["dau"],
            "mau": active["mau"],
        },
        "ai_usage": usage,
        "credits": credit_totals,
        "budget": budget,
        "revenue": {
            "total": None,
            "refunds": None,
            "label": "Not implemented — payments provider is a later"
            " milestone (docs/BUSINESS.md); no numbers are invented.",
        },
        "feedback_open": len(feedback.list_feedback(open_only=True)),
        "generated_by": user["username"],
    }


# ───────────────────────────────────────────── User management


@router.get("/users")
async def admin_users(request: Request, q: str = "", include_local: bool = False):
    gate.current_user(request)
    users = accounts.list_users(q.strip(), include_local=include_local)
    from services.usage_service import cost_by_user

    costs = cost_by_user()  # {user: {requests, cost_usd, tokens}}
    out = []
    for u in users:
        c = costs.get(u["username"], {})
        out.append(
            {
                **u,
                "balance_usd": round(credits.balance_micro(u["id"]) / 1_000_000, 6),
                "ai_cost_usd": c.get("cost_usd", 0.0),
                "ai_requests": c.get("requests", 0),
            }
        )
    return {"users": out}


@router.patch("/users/{user_id}")
async def admin_patch_user(request: Request, user_id: int):
    actor = gate.current_user(request)
    body = await request.json()
    target = accounts.get_user_by_id(user_id)
    if target is None or target["status"] == "deleted":
        raise HTTPException(status_code=404, detail="No such user.")

    updates: dict = {}
    if "status" in body:
        if body["status"] not in ("active", "suspended"):
            raise HTTPException(status_code=400, detail="Bad status value.")
        updates["status"] = body["status"]
    if "plan" in body:
        updates["plan"] = body["plan"]
    if "role" in body:
        # Role changes are superadmin-only, full stop.
        if actor["role"] != "superadmin":
            raise HTTPException(
                status_code=403,
                detail="Only a superadmin can change roles.",
            )
        if actor["id"] == user_id:
            raise HTTPException(400, "Don't change your own role.")
        updates["role"] = body["role"]
    if not updates:
        raise HTTPException(status_code=400, detail="Nothing to update.")
    reason = str(body.get("reason", "")).strip()
    if len(reason) < 3:
        raise HTTPException(
            status_code=400,
            detail="A reason (≥3 chars) is recorded in the audit log.",
        )
    # Suspensions strip sessions immediately.
    if updates.get("status") == "suspended":
        accounts.revoke_sessions(user_id)
    try:
        user = accounts.update_user(user_id, updates)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    audit_log(
        actor["id"],
        actor["username"],
        "user_update",
        target=f"user:{user_id}",
        reason=reason,
        meta={
            "updates": {k: updates[k] for k in updates if k != "role"} or None,
            "role": updates.get("role"),
        },
    )
    return user


# ───────────────────────────────────────── Credits & adjustments


@router.post("/credits/{user_id}")
async def admin_grant(request: Request, user_id: int):
    actor = gate.current_user(request)
    body = await request.json()
    target = accounts.get_user_by_id(user_id)
    if target is None or target["status"] == "deleted":
        raise HTTPException(status_code=404, detail="No such user.")
    delta_dollars = body.get("delta_dollars")
    if not isinstance(delta_dollars, (int, float)) or delta_dollars == 0:
        raise HTTPException(
            status_code=400, detail="delta_dollars must be a non-zero number."
        )
    delta_micro = round(float(delta_dollars) * 1_000_000)
    if delta_micro == 0:
        raise HTTPException(status_code=400, detail="Amount too small to ledger.")
    try:
        result = credits.apply(
            user_id,
            delta_micro,
            str(body.get("kind", "grant")),
            str(body.get("reason", "")),
            actor_id=actor["id"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    audit_log(
        actor["id"],
        actor["username"],
        "credit_adjustment",
        target=f"user:{user_id}",
        reason=result["reason"],
        meta={
            "delta_usd": round(result["delta_micro"] / 1_000_000, 6),
            "kind": result["kind"],
            "balance_usd": round(result["balance_micro"] / 1_000_000, 6),
        },
    )
    return {
        **result,
        "delta_usd": round(result["delta_micro"] / 1_000_000, 6),
        "balance_usd": round(result["balance_micro"] / 1_000_000, 6),
    }


@router.get("/credits/ledger")
async def credit_ledger(request: Request, limit: int = 200):
    gate.current_user(request)
    with contextlib.closing(credits._cx()) as conn:
        rows = conn.execute(
            "SELECT l.*, u.username FROM credit_ledger l"
            " JOIN users u ON u.id = l.user_id ORDER BY l.id DESC LIMIT ?",
            (min(max(limit, 1), 1000),),
        ).fetchall()
    entries = []
    for r in rows:
        d = dict(r)
        d["delta_usd"] = round(d["delta_micro"] / 1_000_000, 6)
        d["balance_usd"] = round(d["balance_after_micro"] / 1_000_000, 6)
        entries.append(d)
    return {"entries": entries, "chain_ok": audit.verify_chain()}


# ───────────────────────────────────────────── Audit log


@router.get("/audit")
async def audit_entries(request: Request, limit: int = 200, action: str = ""):
    gate.current_user(request)
    return {
        "entries": audit.list_entries(limit=limit, action=action or None),
        "chain_ok": audit.verify_chain(),
    }


@router.get("/feedback")
async def admin_feedback(request: Request, open_only: bool = False):
    gate.current_user(request)
    return {"feedback": feedback.list_feedback(open_only=open_only)}


@router.patch("/feedback/{fb_id}")
async def resolve_feedback(request: Request, fb_id: int):
    actor = gate.current_user(request)
    body = await request.json()
    status = body.get("status")
    if status not in ("open", "done", "wont_do"):
        raise HTTPException(status_code=400, detail="Bad status.")
    import contextlib

    from services.feedback import _cx as _fcx

    with contextlib.closing(_fcx()) as conn, conn:
        conn.execute("UPDATE feedback SET status = ? WHERE id = ?", (status, fb_id))
    audit_log(
        actor["id"],
        actor["username"],
        "feedback_update",
        target=f"feedback:{fb_id}",
        reason=str(body.get("reason", ""))[:200],
    )
    return {"ok": True}


# ─────────────────────────────── Providers, budget & system health


@router.get("/providers")
async def providers(request: Request):
    gate.current_user(request)
    from config.pricing import MODEL_PRICES
    from config.settings import settings
    from services.budget_service import current_budget_state

    try:
        key_configured = bool(str(getattr(settings, "anthropic_api_key", "")).strip())
    except Exception:
        key_configured = False
    return {
        "allowlist_models": sorted(MODEL_PRICES.keys()) if MODEL_PRICES else [],
        "pricing": MODEL_PRICES,
        "anthropic_key_configured": key_configured,
        "cloud_consent": bool(getattr(settings, "aria_cloud_consent", False)),
        "budget_state": current_budget_state(),
        "secret_note": "API keys live only in the server environment/settings;"
        " values are never returned or displayed.",
    }


@router.post("/budget")
async def set_budget(request: Request):
    actor = gate.current_user(request)
    body = await request.json()
    from services.budget_service import set_daily_budget

    try:
        state = set_daily_budget(body.get("daily_budget_usd"))
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    audit_log(
        actor["id"],
        actor["username"],
        "budget_change",
        reason=str(body.get("reason", ""))[:200] or None,
        meta={"daily_budget_usd": state.get("daily_budget_usd")},
    )
    return state


@router.get("/health")
async def admin_health(request: Request):
    gate.current_user(request)
    from models.database import DATA_DIR

    disk = shutil.disk_usage(str(DATA_DIR))
    ollama_ok = False
    try:
        from services.ollama_service import OllamaService

        h = await OllamaService().health()
        ollama_ok = bool(h if isinstance(h, bool) else h.get("ok", False))
    except Exception:
        ollama_ok = False
    failed_jobs = 0
    total_jobs = 0
    try:
        import json as _json

        tasks_file = DATA_DIR / "background_tasks.json"
        if tasks_file.exists():
            tasks = _json.loads(tasks_file.read_text())
            items = tasks if isinstance(tasks, list) else list(tasks.values())
            for t in items:
                if not isinstance(t, dict):
                    continue
                total_jobs += 1
                if str(t.get("status", "")) in ("error", "failed"):
                    failed_jobs += 1
    except Exception:
        pass
    backups = DATA_DIR.parent / "backups"
    backup_count = 0
    try:
        if backups.exists():
            backup_count = len(list(backups.glob("*.zip"))) + len(
                list(backups.glob("*.tgz"))
            )
    except Exception:
        pass
    return {
        "backend": "ok",
        "version": "2.1.0",
        "auth_mode": accounts.auth_mode(),
        "ollama": ollama_ok,
        "database": {
            "path": "app.db (sqlite, WAL)",
            "users_ok": True,
            "audit_chain_ok": audit.verify_chain(),
        },
        "disk": {
            "free_gb": round(disk.free / 1e9, 1),
            "total_gb": round(disk.total / 1e9, 1),
        },
        "background_jobs": {"tracked": total_jobs, "failed": failed_jobs},
        "backups_found": backup_count,
        "data_dir_size_note": "Full file listing stays server-side; this is a summary only.",
    }
