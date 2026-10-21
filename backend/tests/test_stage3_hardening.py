"""Section 13 Stage-2.5 hardening tests — the post-QA fixes.

Covers the five QA findings fixed in this round:
1. Chat-context memory isolation: `retrieve()` never feeds another
   student's saved memories into the model context (accounts mode), and
   the orchestrator passes the scoped user.
2. The static `ARIA_API_TOKEN` gate yields to session tokens in accounts
   mode instead of bricking remote sign-in.
3. `/api/auth/admin/unlock` is brute-force limited like /login.
4. Account deletion purges the account's per-user files; the built-in
   local account cannot be deleted or mutated.
5. Credit-ledger idempotency: a retried admin grant with the same
   idempotency key cannot grant twice.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.test_accounts_rbac import (
    bearer,
    client,
    login,
    make_user,
    unlocked_admin,
)

DATA_DIR = Path(os.environ["ARIA_DATA_DIR"])


def _suffix() -> str:
    import uuid

    return uuid.uuid4().hex[:6]


def accounts_mode(monkeypatch) -> None:
    monkeypatch.setenv("ARIA_AUTH_MODE", "accounts")


# ─────────────────────────── 1. chat-context memory isolation


class _FakeGlobalCollection:
    """Mimics chroma where-filtering honestly: `where` must admit a doc or
    it is not returned. Captures every query's where-clause."""

    from typing import ClassVar

    DOCS: ClassVar[dict[str, str]] = {
        "cid_a": "ALICE-ONLY-vectors",
        "cid_b": "BOB-SECRET-vectors-stolen-if-seen",
    }

    def __init__(self) -> None:
        self.execute_where: list[Any] = []

    def count(self) -> int:
        return len(self.DOCS)

    def query(self, query_texts, n_results, where: Any = None):
        self.execute_where.append(where)
        admit = self.DOCS
        if isinstance(where, dict):
            spec = where.get("conversation_id", {})
            if isinstance(spec, dict) and "$in" in spec:
                admit = {cid: d for cid, d in self.DOCS.items() if cid in spec["$in"]}
            elif isinstance(spec, str):
                admit = {c: d for c, d in self.DOCS.items() if c == spec}
        docs = list(admit.values())[: max(n_results, 1)]
        metas = [{"conversation_id": c} for c in list(admit)[: max(n_results, 1)]]
        return {"documents": [docs], "metadatas": [metas]}


def _write_conversations() -> None:
    (DATA_DIR / "conversations.json").write_text(
        json.dumps(
            {
                "cid_a": [
                    {
                        "user": "algebra question",
                        "ai": "alice's private aside",
                        "timestamp": "2026-10-21T00:00:00Z",
                    }
                ],
                "cid_b": [
                    {
                        "user": "bob's diary entry",
                        "ai": "bob's private aside",
                        "timestamp": "2026-10-21T00:00:00Z",
                    }
                ],
            }
        )
    )
    (DATA_DIR / "conversation_owners.json").write_text(
        json.dumps({"cid_a": "tq_alice", "cid_b": "tq_bob"})
    )


def _scoped_service(monkeypatch) -> tuple[Any, _FakeGlobalCollection]:
    from services.memory_service import MemoryService

    accounts_mode(monkeypatch)
    _write_conversations()
    svc = MemoryService()
    fake = _FakeGlobalCollection()
    svc._chroma_available = True
    svc._global_collection = fake
    svc._collection = None  # per-cid semantic path unused in this test
    return svc, fake


def test_retrieve_filters_global_memory_to_owned_conversations(monkeypatch):
    svc, fake = _scoped_service(monkeypatch)
    out = asyncio.run(svc.retrieve("cid_a", "algebra question", k=3, user="tq_alice"))
    assert out and all("BOB-SECRET" not in s for s in out)
    # The wall must be at QUERY time: chroma only ever saw alice's cids.
    assert len(fake.execute_where) == 1
    spec = fake.execute_where[0]["conversation_id"]
    assert spec["$in"] == ["cid_a"]


def test_retrieve_refuses_foreign_conversation_entirely(monkeypatch):
    svc, fake = _scoped_service(monkeypatch)
    out = asyncio.run(svc.retrieve("cid_b", "diary", k=3, user="tq_alice"))
    assert out == []
    assert fake.execute_where == []  # never even queried


def test_retrieve_with_no_owned_conversations_is_empty(monkeypatch):
    svc, fake = _scoped_service(monkeypatch)
    from services.memory_service import OWNERS_FILE

    OWNERS_FILE.write_text(json.dumps({"cid_a": "someone-else"}))
    out = asyncio.run(svc.retrieve("cid_a", "anything", k=3, user="tq_bob"))
    assert out == []
    # Never queried at all: a user who owns nothing is refused up front
    # (the foreign-cid guard short-circuits before any chroma call).
    assert fake.execute_where == []


def test_retrieve_local_mode_keeps_unscoped_context(monkeypatch):
    monkeypatch.setenv("ARIA_AUTH_MODE", "local")
    monkeypatch.delenv("ARIA_AUTH_MODE", raising=False)
    _write_conversations()
    from services.memory_service import MemoryService

    svc = MemoryService()
    fake = _FakeGlobalCollection()
    svc._chroma_available = True
    svc._global_collection = fake
    svc._collection = None
    out = asyncio.run(svc.retrieve("cid_a", "diary", k=3, user=None))
    assert any("BOB-SECRET" in s for s in out)  # single-owner machine: still all
    assert fake.execute_where == [None]


def test_orchestrator_memory_fetch_passes_the_scope(monkeypatch):
    """The orchestrator seam must hand the gate's user to retrieve()."""
    import inspect

    from services import orchestrator

    src = inspect.getsource(orchestrator)
    assert "user=scoped_user()" in src, (
        "orchestrator must pass the request scope into retrieve()"
    )


# ─────────────────────────── 2. static token gate yields to accounts


def test_session_token_survives_static_token_gate(monkeypatch):
    accounts_mode(monkeypatch)
    username = f"tq_remote_{_suffix()}"
    make_user(username, password="SturdyPass123")
    from config.settings import settings as settings_obj

    monkeypatch.setattr(settings_obj, "aria_api_token", "topsecret")
    from main import app

    me = login(client(), username)
    remote = TestClient(app, client=("203.0.113.9", 1234))
    r = remote.get("/api/auth/me", headers=bearer(me["token"]))
    assert r.status_code == 200, r.text
    assert r.json()["username"] == username
    # Still no anonymous access: the accounts gate answers, not the static one.
    anon = remote.get("/api/todos")
    assert anon.status_code == 401
    assert "Sign in required" in anon.json()["error"]["message"]


# ─────────────────────────── 3. step-up brute force


def test_admin_unlock_is_rate_limited(monkeypatch):
    accounts_mode(monkeypatch)
    username = f"tq_sup_{_suffix()}"
    make_user(username, role="superadmin")
    c = client()
    token = login(c, username)["token"]
    headers = bearer(token)
    statuses = []
    for _ in range(12):
        r = c.post(
            "/api/auth/admin/unlock",
            json={"username": username, "password": "BadPass9999"},
            headers=headers,
        )
        statuses.append(r.status_code)
        if r.status_code == 429:
            break
    assert statuses[-1] == 429  # never loops without 429
    assert statuses.count(401) == 10  # exactly the budget, then the wall


# ─────────────────────────── 4. deletion purge + built-in account guard


def test_account_delete_purges_files(monkeypatch):
    accounts_mode(monkeypatch)
    username = f"tq_gone_{_suffix()}"
    me = login(client(), username) if make_user(username) else None
    assert me is not None
    c = client()
    r = c.post(
        "/api/todos",
        json={"task": "something to purge", "subject": "maths"},
        headers=bearer(me["token"]),
    )
    assert r.status_code in (200, 201), r.text
    user_dir = DATA_DIR / "users" / username
    if not user_dir.exists():  # deletion from a previous run: recreate a file
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "todos.json").write_text("[]")
    out = c.request(
        "DELETE",
        "/api/auth/me",
        data=json.dumps({"password": "SturdyPass123"}),
        headers={**bearer(me["token"]), "Content-Type": "application/json"},
    )
    assert out.status_code == 200, out.text
    assert not user_dir.exists()


def test_builtin_local_account_is_undeletable(monkeypatch):
    accounts_mode(monkeypatch)
    admin = unlocked_admin("tq_super", password="SturdyPass123")
    from services import accounts

    local = accounts.get_user_by_username("local-owner")
    assert local is not None
    c = client()
    # Direct owner deletion attempt is refused…
    r = c.request(
        "DELETE",
        "/api/auth/me",
        data=json.dumps({"password": "anything"}),
        headers={
            **bearer(accounts.create_session(local["id"])),
            "Content-Type": "application/json",
        },
    )
    assert r.status_code in (400, 401, 403)
    # …and admin mutability is refused too.
    r2 = c.patch(
        f"{AADMIN}/users/{local['id']}",
        json={"status": "deleted"},
        headers=bearer(admin["token"]),
    )
    assert r2.status_code == 400
    assert "built-in" in r2.json()["detail"]


# ─────────────────────────── 5. ledger idempotency


AADMIN = "/api/v2/admin"


def test_admin_grant_idempotency_key_cannot_double_grant(monkeypatch):
    accounts_mode(monkeypatch)
    admin = unlocked_admin("tq_granter", password="SturdyPass123")
    student = make_user(f"tq_student_{_suffix()}")
    c = client()
    body = {
        "delta_dollars": 1.25,
        "kind": "grant",
        "reason": "pilot stake",
        "idempotency_key": f"topup:receipt-{_suffix()}",
    }
    r1 = c.post(
        f"{AADMIN}/credits/{student['id']}", json=body, headers=bearer(admin["token"])
    )
    assert r1.status_code == 200, r1.text
    r2 = c.post(
        f"{AADMIN}/credits/{student['id']}",
        json=body,
        headers=bearer(admin["token"]),
    )  # operator/browser retry of the SAME request
    assert r2.status_code == 200
    assert r2.json()["duplicate"] is True
    first, second = r1.json(), r2.json()
    assert first["balance_micro"] == second["balance_micro"]
    w = c.get("/api/auth/me/wallet", headers=bearer_student(student)).json()
    # 10 purchases-worth of retries must still equal one 1.25 grant.
    assert w["balance_usd"] == pytest.approx(1.25)


def test_idempotency_keys_are_biased_per_user(monkeypatch):
    accounts_mode(monkeypatch)
    admin = unlocked_admin("tq_broker", password="SturdyPass123")
    a = make_user(f"tq_a_{_suffix()}")
    b = make_user(f"tq_b_{_suffix()}")
    c = client()
    key = {"idempotency_key": f"stripe:evt_{_suffix()}"}
    r1 = c.post(
        f"{AADMIN}/credits/{a['id']}",
        json={**key, "delta_dollars": 5, "kind": "grant", "reason": "bank xfer"},
        headers=bearer(admin["token"]),
    )
    assert r1.status_code == 200
    r2 = c.post(
        f"{AADMIN}/credits/{b['id']}",
        json={**key, "delta_dollars": 5, "kind": "grant", "reason": "bank xfer"},
        headers=bearer(admin["token"]),
    )
    assert r2.status_code == 400  # key bound to its first user
    assert b["id"] != a["id"]


def bearer_student(me: dict) -> dict:
    c = client()
    tok = login(c, me["username"])["token"]
    return bearer(tok)
