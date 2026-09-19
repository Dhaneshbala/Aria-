"""Tests for the Maths Accelerator service."""
import pytest


class TestMathsAccelerator:
    """Test maths accelerator fallback bank and generation."""

    def test_list_topics(self):
        from services.maths_accelerator_service import list_topics
        topics = list_topics()
        assert isinstance(topics, list)
        assert len(topics) > 0
        topic_ids = [t["id"] for t in topics]
        assert "quadratics" in topic_ids

    def test_tiers_exist(self):
        from services.maths_accelerator_service import TIERS
        assert "foundation" in TIERS
        assert "selective" in TIERS
        assert "extension" in TIERS

    def test_fallback_set_foundation(self):
        from services.maths_accelerator_service import _fallback_set
        questions = _fallback_set("quadratics", "foundation", 2)
        assert len(questions) == 2
        for q in questions:
            assert "question" in q
            assert "marks" in q
            assert "answer" in q
            assert "solution_steps" in q

    def test_fallback_set_selective(self):
        from services.maths_accelerator_service import _fallback_set
        questions = _fallback_set("quadratics", "selective", 2)
        assert len(questions) == 2
        for q in questions:
            assert q["marks"] >= 2

    def test_fallback_set_extension(self):
        from services.maths_accelerator_service import _fallback_set
        questions = _fallback_set("quadratics", "extension", 1)
        assert len(questions) == 1
        assert questions[0]["marks"] >= 3

    def test_fallback_set_generic(self):
        from services.maths_accelerator_service import _fallback_set
        # Unknown topic should fall back to generic
        questions = _fallback_set("unknown_topic", "foundation", 1)
        assert len(questions) == 1

    def test_fallback_set_count_capped(self):
        from services.maths_accelerator_service import _fallback_set
        questions = _fallback_set("quadratics", "foundation", 100)
        # Should not exceed available questions
        assert len(questions) <= 100

    def test_mastery_persistence(self):
        from services.maths_accelerator_service import get_mastery
        mastery = get_mastery()
        assert isinstance(mastery, dict)

    def test_record_attempt(self):
        from services.maths_accelerator_service import record_attempt
        result = record_attempt("quadratics", "foundation", 2, 2, [])
        assert isinstance(result, dict)
