"""Section 13 Stage 2 acceptance tests — per-user store isolation.

Covers the Stage 2 acceptance criteria: every remaining feature store is
partitioned per account in accounts mode (todos, mistakes, exam plans,
maths mastery + generation sessions, notebooks, knowledge base, prompt
caches), legacy stores move to the real (non-local) first admin on first
accounts-mode boot, operator surfaces (system, backups, agent) are
admin-only with step-up on mutations, cross-account maths sessions are
meaningless, the gateway seam routes cloud traffic through the Cloud
Boost gateway when configured, and the manual ``payment`` ledger kind
records verified top-ups. Local mode keeps the historic base paths.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import respx
from httpx import Response as HttpxResponse

from tests.test_accounts_rbac import (  # shared Stage-1 helpers/conventions
    ACCOUNTS,
    bearer,
    client,
    login,
    make_user,
    register,
    set_envs,
    unlocked_admin,
)

DATA_DIR = Path(os.environ["ARIA_DATA_DIR"])
LOCAL = {"ARIA_AUTH_MODE": "local"}

GATEWAY = "http://gateway.test"
GATEWAY_MESSAGES = f"{GATEWAY}/v1/messages"


def accounts_mode(monkeypatch) -> None:
    set_envs(monkeypatch, ACCOUNTS)


def local_mode(monkeypatch) -> None:
    set_envs(monkeypatch, LOCAL)
    monkeypatch.delenv("ARIA_AUTH_MODE", raising=False)


def hdr_for(username: str) -> dict:
    c = client()
    token = login(c, username)["token"]
    return bearer(token)


def first_non_local_admin() -> str:
    admin = first_non_local_admin_if_any()
    assert admin, "no non-local admin exists to own migrated stores"
    return admin


def first_non_local_admin_if_any() -> str | None:
    from services.accounts import DEFAULT_LOCAL_USER, list_users

    for u in list_users(include_local=True):
        if (
            u["role"] in ("admin", "superadmin")
            and u["status"] == "active"
            and u["username"] != DEFAULT_LOCAL_USER
        ):
            return u["username"]
    return None


# ─────────────────────────────────── 1. flat stores partitioned per user


def test_todos_are_partitioned_per_account(monkeypatch):
    accounts_mode(monkeypatch)
    register(client(), "tde_alice")
    register(client(), "tde_bob")
    alice, bobs = hdr_for("tde_alice"), hdr_for("tde_bob")
    c = client()

    r = c.post(
        "/api/todos",
        json={
            "task": "Alice's secret homework",
            "subject": "maths",
            "due_date": "2026-10-25",
        },
        headers=alice,
    )
    assert r.status_code == 200, r.text
    todo_id = r.json()["id"]

    assert all(
        t["id"] != todo_id for t in c.get("/api/todos", headers=bobs).json()["todos"]
    )
    assert (DATA_DIR / "users" / "tde_alice" / "todos.json").exists()
    assert not (DATA_DIR / "users" / "tde_bob" / "todos.json").exists()

    # Bob cannot complete or delete Alice's todo.
    assert (
        c.patch(
            f"/api/todos/{todo_id}", json={"completed": True}, headers=bobs
        ).status_code
        == 404
    )
    assert c.delete(f"/api/todos/{todo_id}", headers=bobs).status_code == 404
    # Alice still has it.
    assert any(
        t["id"] == todo_id for t in c.get("/api/todos", headers=alice).json()["todos"]
    )


def test_local_mode_todos_still_use_the_base_file(monkeypatch):
    local_mode(monkeypatch)
    c = client()
    before = c.get("/api/todos").json()["todos"]
    r = c.post("/api/todos", json={"task": "local-mode todo", "subject": "english"})
    assert r.status_code == 200, r.text
    after = c.get("/api/todos").json()["todos"]
    assert len(after) == len(before) + 1
    # Base path — no users/ partition is used in local mode.
    assert (DATA_DIR / "todos.json").exists()
    assert not (DATA_DIR / "users" / "tde_bob" / "todos.json").exists()


def test_mistakes_are_partitioned_per_account(monkeypatch):
    accounts_mode(monkeypatch)
    register(client(), "tde_mia")
    register(client(), "tde_liam")
    mia, liam = hdr_for("tde_mia"), hdr_for("tde_liam")
    c = client()

    r = c.post(
        "/api/v2/mistakes",
        json={
            "question": "7 × 8 = ?",
            "correct_answer": "56",
            "given_answer": "54",
            "subject": "maths",
        },
        headers=mia,
    )
    assert r.status_code == 200, r.text
    item_id = r.json()["mistake"]["id"]

    due = c.get("/api/v2/mistakes/due", headers=liam)
    assert due.status_code == 200
    ids = [m["id"] for m in due.json()["mistakes"]]
    assert item_id not in ids
    # Liam reviewing Mia's (unseen-for-him) item finds nothing to retire.
    rev = c.post(
        f"/api/v2/mistakes/{item_id}/review", json={"correct": True}, headers=liam
    )
    assert rev.json().get("error") or rev.status_code in (404, 400)


def test_exam_plans_are_partitioned_per_account(monkeypatch):
    accounts_mode(monkeypatch)
    register(client(), "tde_exa")
    register(client(), "tde_exb")
    exa, exb = hdr_for("tde_exa"), hdr_for("tde_exb")
    c = client()

    r = c.post(
        "/api/study/exam-plan",
        json={"exam_date": "2026-11-20", "subjects": ["Maths", "Science"]},
        headers=exa,
    )
    assert r.status_code == 200, r.text
    plan_id = r.json().get("plan", {}).get("id") or r.json().get("id")

    plans_b = c.get("/api/study/exam-plans", headers=exb)
    assert plans_b.status_code == 200
    assert plan_id not in json.dumps(plans_b.json())


# ─────────────────────────────────── 2. legacy migration to first admin


def test_legacy_stores_move_to_the_non_local_first_admin(monkeypatch):
    from services.scoping import migrate_legacy_stores

    accounts_mode(monkeypatch)
    if not first_non_local_admin_if_any():
        make_user("tde_admin", role="superadmin")
    admin_username = first_non_local_admin()
    seed = DATA_DIR / "todos.json"
    seed.write_text(
        json.dumps([{"id": "legacy-1", "text": "operator's legacy todo"}]),
        encoding="utf-8",
    )

    moved = migrate_legacy_stores()
    assert moved >= 1

    dst = DATA_DIR / "users" / admin_username / "todos.json"
    assert dst.exists()
    assert not seed.exists()
    assert json.loads(dst.read_text())[0]["text"] == "operator's legacy todo"
    # The built-in local-mode account must never capture legacy data.
    assert not (DATA_DIR / "users" / "local-owner" / "todos.json").exists()

    # Idempotent: a second run moves nothing.
    assert migrate_legacy_stores() == 0
    assert not any((DATA_DIR / name).exists() for name in ("todos.json",))


# ─────────────────────────────────── 3. notebooks are partitioned


def test_notebooks_are_partitioned_per_account(monkeypatch):
    accounts_mode(monkeypatch)
    register(client(), "tde_nb_a")
    register(client(), "tde_nb_b")
    nba, nbb = hdr_for("tde_nb_a"), hdr_for("tde_nb_b")
    c = client()

    r = c.post("/api/notebooks", json={"name": "Alice's notebook"}, headers=nba)
    assert r.status_code == 200, r.text
    nb_id = r.json().get("id") or r.json().get("notebook", {}).get("id")

    names_b = c.get("/api/notebooks", headers=nbb).json()
    if isinstance(names_b, dict):
        names_b = names_b.get("notebooks", [])
    assert all(n.get("id") != nb_id for n in names_b)

    assert c.get(f"/api/notebooks/{nb_id}", headers=nbb).status_code in (404, 403)
    assert c.get(f"/api/notebooks/{nb_id}", headers=nba).status_code == 200


# ─────────────────────────────────── 4. maths generation sessions


def test_maths_sessions_are_account_scoped(monkeypatch):
    accounts_mode(monkeypatch)
    register(client(), "tde_math_a")
    register(client(), "tde_math_b")

    from services.ollama_service import OllamaService

    async def _boom(_self, *_args, **_kwargs):
        raise RuntimeError("no LLM in tests")

    monkeypatch.setattr(OllamaService, "complete", _boom)

    c = client()
    r = c.post(
        "/api/maths/generate",
        json={"topic_id": "quadratics", "tier": "selective"},
        headers=hdr_for("tde_math_a"),
    )
    assert r.status_code == 200, r.text
    sid = r.json().get("session_id")
    assert sid, r.json()

    rb = c.post(
        "/api/maths/submit",
        json={"session_id": sid, "marks": [True] * 10},
        headers=hdr_for("tde_math_b"),
    )
    # Another account's session simply does not exist for them.
    assert rb.status_code in (400, 403), rb.text


# ─────────────────────────────────── 5. operator surfaces locked down


def test_operator_surfaces_require_an_admin(monkeypatch):
    accounts_mode(monkeypatch)
    register(client(), "tde_stu")
    make_user("tde_op_admin", role="superadmin")
    op = hdr_for("tde_op_admin")
    c = client()

    for method, path in [
        ("get", "/api/system/diagnostics"),
        ("get", "/api/agent/anything"),
    ]:
        r = getattr(c, method)(path, headers=hdr_for("tde_stu"))
        assert r.status_code == 403, (path, r.status_code, r.text)

    r = c.get("/api/system/diagnostics", headers=op)
    assert r.status_code == 200, r.text

    # Mutating operator calls need a fresh step-up, even for admins.
    r = c.post("/api/system/restart-ollama", headers=op)
    assert r.status_code == 403
    assert r.json()["error"]["type"] == "admin_locked"


def test_backup_endpoints_are_admin_only(monkeypatch):
    accounts_mode(monkeypatch)
    register(client(), "tde_bkp_stu")
    make_user("tde_bkp_admin", role="superadmin")
    op = hdr_for("tde_bkp_admin")
    c = client()

    assert c.get("/api/backup/list", headers=hdr_for("tde_bkp_stu")).status_code == 403
    r = c.get("/api/backup/list", headers=op)
    assert r.status_code == 200, r.text


# ─────────────────────────────────── 6. knowledge base isolation


def test_kb_documents_are_partitioned_per_account(monkeypatch):
    from services.ollama_service import OllamaService

    async def _embed_fake(self, _model, text):
        v = float(sum(ord(ch) for ch in text) % 97) / 97.0
        return [v, 1.0 - v, 0.5]

    async def _embed_batch_fake(self, _model, texts):
        return [await _embed_fake(self, _model, t) for t in texts]

    monkeypatch.setattr(OllamaService, "embed", _embed_fake)
    monkeypatch.setattr(OllamaService, "embed_batch", _embed_batch_fake)

    accounts_mode(monkeypatch)
    register(client(), "tde_kb_a")
    register(client(), "tde_kb_b")
    kba, kbb = hdr_for("tde_kb_a"), hdr_for("tde_kb_b")
    c = client()

    up = c.post(
        "/api/kb/upload",
        files={
            "file": ("secret_notes.txt", b"Photosynthesis happens in chloroplasts.")
        },
        data={"collection": "user_docs"},
        headers=kba,
    )
    assert up.status_code == 200, up.text

    docs_a = c.get("/api/kb/documents", headers=kba).json()
    doc_list = docs_a if isinstance(docs_a, list) else docs_a.get("documents", [])
    assert any("secret_notes" in str(d.get("title", "")).lower() for d in doc_list)

    docs_b = c.get("/api/kb/documents", headers=kbb)
    if docs_b.status_code == 200:
        body = docs_b.json()
        bl = body if isinstance(body, list) else body.get("documents", [])
        assert all("secret_notes" not in str(d.get("title", "")).lower() for d in bl)

    file_hash = doc_list[0]["file_hash"]
    assert c.delete(f"/api/kb/documents/{file_hash}", headers=kbb).status_code in (
        403,
        404,
    )
    # Alice can still delete her own document.
    assert c.delete(f"/api/kb/documents/{file_hash}", headers=kba).status_code in (
        200,
        404,
    )


# ─────────────────────────────────── 7. payment ledger kind


def test_payment_kind_records_verified_money(monkeypatch):
    accounts_mode(monkeypatch)
    admin = unlocked_admin("tde_pay_admin")
    pay_user = register(client(), "tde_pay_user")
    ah = bearer(admin["token"])
    c = client()
    uid = pay_user["id"]

    from services import credits

    before = credits.balance_micro(uid)
    r = c.post(
        f"/api/v2/admin/credits/{uid}",
        json={
            "delta_dollars": 5.0,
            "kind": "payment",
            "reason": "bank transfer verified",
        },
        headers=ah,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "payment"
    assert abs(body["delta_usd"] - 5.0) < 1e-6
    assert credits.balance_micro(uid) == before + 5_000_000

    le = c.get("/api/v2/admin/credits/ledger?limit=10", headers=ah)
    entries = le.json().get("entries", [])
    assert any(e.get("kind") == "payment" for e in entries)

    # A negative "payment" is nonsense — payments only record money in.
    r2 = c.post(
        f"/api/v2/admin/credits/{uid}",
        json={"delta_dollars": -1.0, "kind": "payment", "reason": "negative payment"},
        headers=ah,
    )
    assert r2.status_code == 400
    assert "positive" in r2.json()["detail"]


# ─────────────────────────────────── 8. gateway seam


@respx.mock
def test_gateway_routes_through_the_cloud_boost_gateway(monkeypatch):
    accounts_mode(monkeypatch)
    user = register(client(), "tde_gw_user")

    from config.settings import settings
    from services import credits, request_scope

    monkeypatch.setattr(settings, "aria_gateway_url", GATEWAY)
    monkeypatch.setattr(settings, "aria_gateway_token", "gw_test_token")
    monkeypatch.setattr(settings, "aria_cloud_consent", True)
    monkeypatch.setattr(settings, "anthropic_api_key", "")

    credits.apply(user["id"], 10_000_000, "grant", "gateway test credit")

    captured = {}

    def _handler(request):
        captured["auth"] = request.headers.get("authorization")
        captured["x_api_key"] = request.headers.get("x-api-key")
        return HttpxResponse(
            200,
            json={
                "id": "msg_test",
                "role": "assistant",
                "content": [{"type": "text", "text": "Hello!"}],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

    respx.post(GATEWAY_MESSAGES).mock(side_effect=_handler)

    import asyncio

    from services.ai_providers import AnthropicProvider

    request_scope.set_user(user["username"])

    async def _run():
        return await AnthropicProvider().complete(
            "claude-haiku-4-5", "You are a test.", "Hi", 32
        )

    out = asyncio.run(_run())
    assert "Hello!" in str(out)
    assert captured["auth"] == "Bearer gw_test_token"
    assert captured["x_api_key"] is None  # no real credential in the backend

    # Usage attributed to the calling account, and the wallet paid.
    from services.usage_service import user_summary

    summary = user_summary(user["username"], days=1)
    assert summary.get("totals", {}).get("requests", 0) >= 1
    by_provider = json.dumps(summary)
    assert "anthropic" in by_provider
    assert credits.balance_micro(user["id"]) < 10_000_000


def test_gateway_without_consent_stays_disabled(monkeypatch):
    from config.settings import settings
    from services.ai_providers import AnthropicProvider, ProviderDisabledError

    monkeypatch.setattr(settings, "aria_gateway_url", GATEWAY)
    monkeypatch.setattr(settings, "aria_gateway_token", "gw_test")
    monkeypatch.setattr(settings, "aria_cloud_consent", False)

    with pytest.raises(ProviderDisabledError):
        AnthropicProvider()._require_enabled()


def test_direct_key_still_works_without_gateway(monkeypatch):
    from config.settings import settings
    from services.ai_providers import AnthropicProvider

    monkeypatch.setattr(settings, "aria_gateway_url", "")
    monkeypatch.setattr(settings, "aria_cloud_consent", True)

    p = AnthropicProvider(api_key="sk-test")
    assert p._base == "https://api.anthropic.com"
    assert p._headers()["x-api-key"] == "sk-test"


# ─────────────────────────────────── 9. prompt-cache namespacing


def test_cache_keys_are_namespaced_per_user(monkeypatch):
    from services import request_scope
    from services.ollama_service import _ns
    from services.scoping import accounts_mode as am

    accounts_mode(monkeypatch)
    request_scope.set_user("tde_cache_a")
    assert _ns() == "u:tde_cache_a:"
    request_scope.set_user("tde_cache_b")
    assert _ns() == "u:tde_cache_b:"

    local_mode(monkeypatch)
    request_scope.set_user(None)
    assert not am()
    assert _ns() == ""  # local mode keeps the historic shared keys
