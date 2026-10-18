"""Token gate: ARIA_API_TOKEN set => remote /api needs Bearer; loopback open."""

import pytest
from fastapi.testclient import TestClient

import main as main_module
from config.settings import settings as settings_obj


@pytest.fixture()
def app_token(monkeypatch):
    # Gate reads the flag per-request, so no reload needed.
    monkeypatch.setattr(settings_obj, "aria_api_token", "secret-123")
    return main_module.app


def test_loopback_exempt_with_token_set(app_token):
    c = TestClient(app_token)
    r = c.get("/api/todos")
    assert r.status_code in (200, 500)  # never 401 from loopback
    assert r.status_code != 401


def test_health_open_with_token_set(app_token):
    c = TestClient(app_token, client=("203.0.113.9", 1234))
    r = c.get("/api/health")
    assert r.status_code == 200


def test_remote_needs_bearer(app_token):
    c = TestClient(app_token, client=("203.0.113.9", 1234))
    r = c.get("/api/todos")
    assert r.status_code == 401
    assert "password" in r.json()["detail"]


def test_remote_bearer_ok(app_token):
    c = TestClient(app_token, client=("203.0.113.9", 1234))
    r = c.get("/api/todos", headers={"Authorization": "Bearer secret-123"})
    assert r.status_code in (200, 500)
    assert r.status_code != 401


def test_no_token_no_gate():
    import main as m

    c = TestClient(m.app, client=("203.0.113.9", 1234))
    # default settings have empty token (unless env sets one — skip then)
    if m.settings.aria_api_token:
        pytest.skip("ARIA_API_TOKEN set in env; gate covered above")
    r = c.get("/api/todos")
    assert r.status_code != 401
