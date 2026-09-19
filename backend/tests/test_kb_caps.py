"""Feature 5 slice 1: KB upload caps (hermetic — validation only)."""
from fastapi.testclient import TestClient
from main import app

client = TestClient(app, raise_server_exceptions=False)


def test_kb_upload_rejects_empty():
    r = client.post("/api/kb/upload", files={"file": ("a.txt", b"", "text/plain")})
    assert r.status_code == 400


def test_kb_upload_multiple_rejects_11_files():
    files = [("files", (f"a{i}.txt", b"hello", "text/plain")) for i in range(11)]
    r = client.post("/api/kb/upload-multiple", files=files)
    assert r.status_code == 400


def test_kb_search_caps_n():
    r = client.get("/api/kb/search", params={"q": "x", "n": 100})
    assert r.status_code == 422
