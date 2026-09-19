"""Integration tests for API routers using FastAPI TestClient."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    import sys
    sys.path.insert(0, ".")
    from main import app
    return TestClient(app)


class TestHealthEndpoint:
    """Test /api/health endpoint."""

    def test_health_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "disk_free_gb" in data


class TestSystemDiagnostics:
    """Test /api/system/diagnostics endpoint."""

    def test_diagnostics_structure(self, client):
        resp = client.get("/api/system/diagnostics")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "checks" in data
        assert "backend" in data["checks"]


class TestMathsEndpoints:
    """Test /api/maths/ endpoints."""

    def test_topics(self, client):
        resp = client.get("/api/maths/topics")
        assert resp.status_code == 200
        data = resp.json()
        assert "topics" in data
        assert "tiers" in data
        assert len(data["topics"]) > 0

    def test_generate_rejects_invalid_tier(self, client):
        resp = client.post("/api/maths/generate", json={
            "topic_id": "quadratics",
            "tier": "invalid_tier",
            "count": 3,
        })
        assert resp.status_code == 422  # Pydantic validation error

    def test_generate_rejects_too_many(self, client):
        resp = client.post("/api/maths/generate", json={
            "topic_id": "quadratics",
            "tier": "foundation",
            "count": 100,  # over max
        })
        assert resp.status_code == 422

    def test_mastery(self, client):
        resp = client.get("/api/maths/mastery")
        assert resp.status_code == 200
        data = resp.json()
        assert "mastery" in data


class TestTodosEndpoints:
    """Test /api/todos/ endpoints."""

    def test_list_todos(self, client):
        resp = client.get("/api/todos")
        assert resp.status_code == 200
        data = resp.json()
        assert "todos" in data

    def test_create_todo(self, client):
        resp = client.post("/api/todos", json={
            "subject": "Maths",
            "task": "Complete worksheet 3",
            "due_date": "2026-09-20",
            "estimated_mins": 45,
            "priority": "high",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["subject"] == "Maths"
        assert data["task"] == "Complete worksheet 3"

    def test_create_todo_rejects_empty_task(self, client):
        resp = client.post("/api/todos", json={
            "task": "",
        })
        assert resp.status_code == 422

    def test_cushion(self, client):
        resp = client.get("/api/todos/cushion")
        assert resp.status_code == 200


class TestAdminEndpoints:
    """Test /api/admin/ endpoints."""

    def test_get_config(self, client):
        resp = client.get("/api/admin/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "model" in data

    def test_health_check(self, client):
        resp = client.get("/api/admin/health")
        assert resp.status_code == 200


class TestBackupEndpoints:
    """Test /api/backup/ endpoints."""

    def test_list_backups(self, client):
        resp = client.get("/api/backup/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "backups" in data
        assert "count" in data


class TestSecurityHeaders:
    """Test security headers middleware."""

    def test_nosniff_header(self, client):
        resp = client.get("/api/health")
        assert resp.headers.get("x-content-type-options") == "nosniff"

    def test_frame_deny(self, client):
        resp = client.get("/api/health")
        assert resp.headers.get("x-frame-options") == "DENY"

    def test_request_id(self, client):
        resp = client.get("/api/health")
        assert "x-request-id" in resp.headers
