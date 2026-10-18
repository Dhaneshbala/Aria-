"""Thin-router coverage — system/backup/voice endpoints, no model needed."""

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def test_system_logs_shape():
    r = client.get("/api/system/logs?lines=5")
    assert r.status_code == 200
    body = r.json()
    assert "content" in body and "lines" in body
    assert body["lines"] <= 5


def test_system_storage_shape():
    r = client.get("/api/system/storage")
    assert r.status_code == 200
    for key in ("data_dir", "disk_free_gb", "disk_total_gb"):
        assert key in r.json()


def test_system_metrics_exposes_aria_series():
    r = client.get("/api/system/metrics")
    assert r.status_code == 200
    assert "aria_http_requests_total" in r.text


def test_backup_lifecycle():
    created = client.post("/api/backup/create", params={"include_uploads": False})
    assert created.status_code == 200
    listed = client.get("/api/backup/list")
    assert listed.status_code == 200
    names = [b["filename"] for b in listed.json().get("backups", [])]
    assert names, "expected at least the backup just created"
    dl = client.get(f"/api/backup/download/{names[0]}")
    assert dl.status_code == 200
    assert len(dl.content) > 1000
    rm = client.delete(f"/api/backup/delete/{names[0]}")
    assert rm.status_code in (200, 404)


def test_backup_rejects_traversal():
    r = client.get("/api/backup/download/..%2F..%2Fconfig.json")
    assert r.status_code in (400, 403, 404)


def test_voice_languages():
    r = client.get("/api/voice/languages")
    assert r.status_code == 200
    langs = r.json().get("languages", [])
    assert len(langs) > 50
    assert all("code" in entry and "name" in entry for entry in langs[:5])


def test_voice_synthesize_caps():
    r = client.post("/api/voice/synthesize", json={"text": ""})
    assert r.status_code == 400
    r = client.post("/api/voice/synthesize", json={"text": "x" * 2001})
    assert r.status_code == 413
