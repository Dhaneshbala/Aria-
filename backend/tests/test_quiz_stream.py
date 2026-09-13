"""Quiz streaming: questions arrive one-by-one as verified (no waiting for all).

Uses fakes for generation + verification — no model needed.
"""
import pytest

from services.study_service import StudyService

RAW = """Q1: 2+2?
A) 3
B) 4
C) 5
D) 6
Correct: B
Explanation: 2+2=4
Q2: Capital of France?
A) Paris
B) Rome
C) Madrid
D) Berlin
Correct: A
Explanation: Paris is the capital.
"""


@pytest.fixture
def svc(monkeypatch):
    s = StudyService()

    async def fake_complete(model, prompt, **kw):
        assert "SPECIFICALLY about" in prompt  # shared builder format
        return RAW

    async def fake_verify(self, q, topic, model):
        q = dict(q)
        q["verified"] = "majority_verified"
        return q

    monkeypatch.setattr("services.study_service.ollama.complete", fake_complete)
    monkeypatch.setattr(StudyService, "_verify_single_question", fake_verify)
    return s


async def test_stream_yields_each_question_with_progress(svc):
    events = []
    async for ev in svc.generate_quiz_stream("general", "easy", 2, model="m"):
        events.append(ev)
    kinds = [k for k, *_ in events]
    assert kinds[0] == "total"
    assert kinds.count("question") == 2
    assert ("progress", 2, 2) in [(k, *p) for k, *p in events if k == "progress"]
    qs = [p[0] for k, *p in events if k == "question"]
    assert all(q.get("verified") == "majority_verified" for q in qs)
    assert all(len(q.get("options", [])) >= 4 for q in qs)


async def test_stream_empty_generation_yields_error(svc, monkeypatch):
    async def blank(model, prompt, **kw):
        return "no questions here, just prose"

    monkeypatch.setattr("services.study_service.ollama.complete", blank)
    events = [ev async for ev in svc.generate_quiz_stream("x", "easy", 2, model="m")]
    assert events and events[0][0] == "error"


async def test_shared_prompt_builder_matches_generate_quiz_format():
    p = StudyService._build_quiz_prompt("Fractions", "easy", 3)
    assert "SPECIFICALLY about: Fractions" in p
    assert "Q[N]: [question text]" in p
    assert "Correct: [letter]" in p
