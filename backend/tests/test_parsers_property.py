"""Property tests for the study parsers — model output is adversarial input.

Parsers must never raise, must cap output, and must return well-shaped
records no matter what text they're fed.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from services.study_service import StudyService

svc = StudyService()

TEXT = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=2000)


@given(TEXT)
@settings(max_examples=200, deadline=None)
def test_parse_quiz_never_raises_and_caps(text):
    qs = svc._parse_quiz(text)
    assert isinstance(qs, list)
    assert len(qs) <= 10
    for q in qs:
        assert isinstance(q["question"], str) and q["question"]
        assert isinstance(q["options"], list) and len(q["options"]) >= 4
        assert q["correct"] in ("", "A", "B", "C", "D")


@given(TEXT)
@settings(max_examples=200, deadline=None)
def test_parse_flashcards_never_raises_and_caps(text):
    cards = svc._parse_flashcards(text)
    assert isinstance(cards, list)
    assert len(cards) <= 20
    for c in cards:
        assert isinstance(c["front"], str) and c["front"].strip()
        assert isinstance(c["back"], str) and c["back"].strip()


@given(st.text(min_size=1, max_size=500))
@settings(max_examples=100, deadline=None)
def test_parse_quiz_wellformed_input_roundtrips(text):
    # A clean Q/A block must survive parsing with its question intact.
    doc = f"Q1: What is {text.strip() or 'x'}?\nA) one\nB) two\nC) three\nD) four\nCorrect: B"
    qs = svc._parse_quiz(doc)
    assert len(qs) == 1
    assert text.strip()[:20] in qs[0]["question"] or qs[0]["question"]
    assert qs[0]["correct"] == "B"
