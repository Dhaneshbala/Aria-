"""Feature 7 slice 1: imagegen validation pinned (hermetic)."""
from fastapi.testclient import TestClient
from main import app

client = TestClient(app, raise_server_exceptions=False)


def test_imagegen_rejects_empty_prompt():
    r = client.post("/api/imagegen/generate", json={"prompt": ""})
    assert r.status_code == 422


def test_imagegen_rejects_huge_dimensions():
    r = client.post("/api/imagegen/generate", json={"prompt": "a cat", "width": 9999, "height": 9999})
    assert r.status_code == 422
