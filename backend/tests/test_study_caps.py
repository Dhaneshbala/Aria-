"""Feature 2 slice 1: study request caps (hermetic — validation only, no models)."""
from fastapi.testclient import TestClient

from main import app

client = TestClient(app, raise_server_exceptions=False)


def test_quiz_rejects_count_100():
    r = client.post("/api/study/quiz", json={"topic": "fractions", "level": "medium", "count": 100})
    assert r.status_code == 422


def test_quiz_rejects_empty_topic():
    r = client.post("/api/study/quiz", json={"topic": "", "level": "medium", "count": 5})
    assert r.status_code == 422


def test_quiz_rejects_topic_over_300():
    r = client.post("/api/study/quiz", json={"topic": "x" * 301, "level": "medium", "count": 5})
    assert r.status_code == 422


def test_quiz_rejects_bad_level():
    r = client.post("/api/study/quiz", json={"topic": "fractions", "level": "insane", "count": 5})
    assert r.status_code == 422


def test_quiz_stream_rejects_count_0():
    r = client.post("/api/study/quiz/stream", json={"topic": "fractions", "level": "medium", "count": 0})
    # Validation happens before streaming — 422, never touches the model.
    assert r.status_code == 422


def test_flashcards_rejects_count_100():
    r = client.post("/api/study/flashcards", json={"topic": "cells", "count": 100})
    assert r.status_code == 422


def test_parse_notification_rejects_empty():
    r = client.post("/api/study/exam-plan/parse-notification", files={"file": ("n.txt", b"", "text/plain")})
    assert r.status_code == 400
