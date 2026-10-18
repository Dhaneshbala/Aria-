"""Mistake book: record wrong answers, drill to 3-in-a-row mastery."""

from fastapi.testclient import TestClient

import main
from services import mistake_service

client = TestClient(main.app)


def test_record_and_dedupe():
    first = mistake_service.record(
        question="What is 7 x 8?",
        correct_answer="56",
        given_answer="54",
        subject="maths",
        topic="multiplication",
        source="quiz",
    )
    assert first and first["times_missed"] == 1
    again = mistake_service.record(
        question="  what IS 7 x  8? ",
        correct_answer="56",
        subject="maths",
    )
    assert again["id"] == first["id"]
    assert again["times_missed"] == 2


def test_review_retires_at_three_streak():
    item = mistake_service.record(question="Capital of Mars?", correct_answer="-")
    for _ in range(2):
        out = mistake_service.review(item["id"], True)
        assert out["mastered"] is False
    out = mistake_service.review(item["id"], True)
    assert out["mastered"] is True
    assert out["id"] not in [i["id"] for i in mistake_service.due()]


def test_miss_resets_streak():
    item = mistake_service.record(question="2+2x2?", correct_answer="6")
    mistake_service.review(item["id"], True)
    out = mistake_service.review(item["id"], False)
    assert out["streak"] == 0 and out["mastered"] is False


def test_empty_question_rejected():
    assert mistake_service.record(question="   ") is None
    assert mistake_service.review("nope", True) is None


def test_endpoints_roundtrip():
    r = client.post(
        "/api/v2/mistakes",
        json={"question": "H2O?", "correct_answer": "water", "subject": "science"},
    )
    assert r.status_code == 200 and r.json()["recorded"] is True
    mid = r.json()["mistake"]["id"]

    r = client.get("/api/v2/mistakes/due?limit=5")
    assert r.status_code == 200
    assert any(m["id"] == mid for m in r.json()["mistakes"])

    r = client.post(f"/api/v2/mistakes/{mid}/review", json={"correct": True})
    assert r.status_code == 200

    r = client.get("/api/v2/mistakes/stats")
    assert r.status_code == 200 and r.json()["total"] >= 1


def test_quiz_check_autofiles_mistake():
    before = mistake_service.stats()["total"]
    r = client.post(
        "/api/study/quiz/check",
        json={
            "subject": "science",
            "correct": False,
            "question": "What is H2O?",
            "correct_answer": "water",
            "given_answer": "fire",
            "topic": "chemistry",
        },
    )
    assert r.status_code == 200
    assert mistake_service.stats()["total"] == before + 1


def test_quiz_check_correct_records_nothing():
    before = mistake_service.stats()["total"]
    r = client.post(
        "/api/study/quiz/check",
        json={"subject": "science", "correct": True, "question": "What is H2O?"},
    )
    assert r.status_code == 200
    assert mistake_service.stats()["total"] == before
