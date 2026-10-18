"""Maths practice sessions — server-anchored scoring (anti-spoofing).

Before this fix, POST /api/maths/submit trusted the client's correct/total
numbers outright: any script could POST correct=total=1000 and top the
mastery board. /generate now registers the set server-side and /submit
scores only against that registered set.
"""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import maths_accelerator_service as mas


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """Force the deterministic fallback path in every test here (no Ollama)."""
    from services.ollama_service import OllamaService

    async def _boom(self, *args, **kwargs):
        raise RuntimeError("offline test")

    monkeypatch.setattr(OllamaService, "complete", _boom)


def test_generate_registers_session(monkeypatch):
    data = _run(mas.generate_set("quadratics", "selective", 3))
    assert data["source"] == "fallback"
    assert data["session_id"]
    sess = mas.get_session(data["session_id"])
    assert sess is not None
    assert sess["count"] == len(data["questions"]) == 3
    assert sess["topic_id"] == "quadratics"
    assert sess["tier"] == "selective"


def test_record_session_result_scores_registered_set(monkeypatch):
    data = _run(mas.generate_set("quadratics", "selective", 4))
    before = mas.get_mastery().get("quadratics", {"attempts": 0, "correct": 0})

    res = mas.record_session_result(data["session_id"], [True, False, True, True])

    after = mas.get_mastery()["quadratics"]
    assert after["attempts"] - before["attempts"] == 4
    assert after["correct"] - before["correct"] == 3
    assert res["correct"] == 3


def test_record_pads_and_trims_marks_to_real_set(monkeypatch):
    data = _run(mas.generate_set("quadratics", "foundation", 3))
    before = mas.get_mastery()["quadratics"]
    # Lie outright: 50 marks claimed for a 3-question set → clamped to 3.
    mas.record_session_result(data["session_id"], [True] * 50)
    after = mas.get_mastery()["quadratics"]
    # Only the three real set questions were counted, no more.
    assert after["attempts"] - before["attempts"] == 3
    assert after["correct"] - before["correct"] == 3


def test_unknown_session_rejected():
    with pytest.raises(ValueError, match="Unknown or expired"):
        mas.record_session_result("not-a-real-session", [True])


def test_submit_router_session_scores_and_unknown_400():
    from fastapi.testclient import TestClient

    import main

    client = TestClient(main.app)
    gen = client.post(
        "/api/maths/generate",
        json={"topic_id": "quadratics", "tier": "selective", "count": 3},
    )
    assert gen.status_code == 200
    body = gen.json()
    sid = body.get("session_id")
    assert sid, "generate must return a session id"

    ok = client.post(
        "/api/maths/submit",
        json={
            "session_id": sid,
            "marks": [True, True, False],
            "correct": 999,
            "total": 999,
            "mistakes": [],
        },
    )
    assert ok.status_code == 200
    scored = ok.json()
    assert isinstance(scored["attempts"], int) and scored["attempts"] > 0
    assert 0 <= scored["correct"] <= scored["attempts"]
    expected_acc = (
        round(scored["correct"] / scored["attempts"] * 100) if scored["attempts"] else 0
    )
    assert scored["accuracy"] == expected_acc

    bad = client.post(
        "/api/maths/submit",
        json={"session_id": "bogus", "marks": [True], "mistakes": []},
    )
    assert bad.status_code == 400
    assert "Unknown or expired" in bad.json()["detail"]


def test_mastery_accuracy_consistency():
    """attempt rows always satisfy correct <= attempts (clamp guarantee)."""
    mastery = mas.get_mastery()
    for entry in mastery.values():
        assert entry["attempts"] >= entry["correct"]
