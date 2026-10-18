"""Syllabus tracker: NSW outcomes with student progress."""

from fastapi.testclient import TestClient

import main
from services import syllabus_service

client = TestClient(main.app)


def test_overview_shape():
    r = client.get("/api/v2/syllabus/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["stage"]
    assert isinstance(body["subjects"], list) and body["subjects"]
    first = body["subjects"][0]
    for key in ("kla", "name", "total", "confident", "learning", "pct"):
        assert key in first


def test_outcomes_merge_status():
    r = client.get("/api/v2/syllabus/outcomes?kla=mathematics&stage=S5")
    assert r.status_code == 200
    outcomes = r.json()["outcomes"]
    assert outcomes and all(
        {"code", "status"} <= set(o)
        and o["status"] in ("none", "learning", "confident")
        for o in outcomes
    )


def test_progress_roundtrip():
    r = client.post(
        "/api/v2/syllabus/progress",
        json={
            "kla": "mathematics",
            "stage": "S5",
            "code": "MA5-1WM",
            "status": "learning",
        },
    )
    assert r.status_code == 200 and r.json()["ok"] is True
    r = client.get("/api/v2/syllabus/outcomes?kla=mathematics&stage=S5")
    match = [o for o in r.json()["outcomes"] if o["code"] == "MA5-1WM"]
    assert match and match[0]["status"] == "learning"
    # reset for isolation
    syllabus_service.set_status("mathematics", "S5", "MA5-1WM", "none")


def test_progress_rejects_bad_status():
    r = client.post(
        "/api/v2/syllabus/progress",
        json={
            "kla": "mathematics",
            "stage": "S5",
            "code": "MA5-1WM",
            "status": "expert",
        },
    )
    assert r.status_code == 400
