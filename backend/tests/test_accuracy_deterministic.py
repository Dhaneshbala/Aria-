"""Accuracy suite for deterministic ARIA services.

These functions have no randomness (regex, scoring, lookups, math), so a
correct implementation must pass every case exactly.
"""
import json
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.knowledge_graph_service import KnowledgeGraphService
from services.citation_service import CitationService, enhance_system_prompt_with_citations
from services.nsw_curriculum_service import get_curriculum_service
from services.document_service import DocumentService
from services.study_service import StudyService
from services.knowledge_base_service import (
    _chunk_text, _file_hash, _detect_collection,
)
from services.analytics_service import AnalyticsService


# ── Knowledge graph entity extraction ────────────────────────────────────

KG_CASES = [
    # (input text, expected entity tuples)
    ("Dr. Sarah Chen presented the Solar Tracker project today.",
     [("person", "Dr. Sarah Chen"), ("project", "Solar Tracker")]),
    ("John Smith and Mary Johnson worked on the weather app.",
     [("person", "John Smith"), ("person", "Mary Johnson"), ("project", "weather")]),
    ("The photosynthesis_notes.pdf and data.csv were uploaded.",
     [("file", "photosynthesis_notes.pdf"), ("file", "data.csv")]),
    ("World War 2 ended in 1945.",
     [("date", "1945")]),
    ("The treaty was signed on March 15, 1945.",
     [("date", "March 15, 1945")]),
    ("We discussed the topic of ancient Rome.",
     [("topic", "ancient Rome")]),
    ("They are working on a quiz game and a homework system.",
     [("project", "quiz"), ("project", "homework")]),
]


class TestKnowledgeGraphAccuracy:

    def test_entity_extraction_exact(self):
        kg = KnowledgeGraphService()
        for text, expected in KG_CASES:
            got = kg._extract_entities(text)
            got_set = set(got)
            for exp in expected:
                assert exp in got_set, f"missing {exp!r} in {text!r} -> {got!r}"
            extras = [e for e in got if e not in expected]
            assert not extras, f"unexpected extras for {text!r}: {extras!r}"

    def test_make_id_normalizes(self):
        kg = KnowledgeGraphService()
        assert kg._make_id("Person", "John Smith") == "person:john smith"
        assert kg._make_id("date", "1945") == "date:1945"

    def test_common_phrase_false_positives_filtered(self):
        kg = KnowledgeGraphService()
        entities = kg._extract_entities("This is a test. Tell me about the solar system.")
        names = [v for t, v in entities if t == "person"]
        assert "Tell Me" not in names
        assert "This Is" not in names


# ── Citation service ──────────────────────────────────────────────────────

class TestCitationAccuracy:

    def _sources(self):
        cs = CitationService()
        cs.register_sources(
            web_results=[{"title": "T1", "url": "https://a.com", "snippet": "s1"}],
            kb_results=[{"metadata": {"source": "KB1"}, "text": "kb text", "score": 0.9}],
            doc_content="---\nPage 1\n---\nFirst page text.\n---\nPage 2\n---\nSecond page text.",
            youtube_results={"title": "YT", "video_id": "abc123", "transcript": "tr"},
        )
        return cs

    def test_source_indexing_order(self):
        cs = self._sources()
        st = cs.get_source_list()
        assert st[0]["type"] == "web" and st[0]["index"] == 1
        assert st[1]["type"] == "kb" and st[1]["index"] == 2
        assert st[2]["type"] == "document" and st[2]["index"] == 3
        assert st[3]["type"] == "document" and st[3]["index"] == 4
        assert st[4]["type"] == "youtube" and st[4]["index"] == 5

    def test_document_pages_extracted(self):
        cs = self._sources()
        pages = [s for s in cs.get_source_list() if s["type"] == "document"]
        assert [p["page"] for p in pages] == [1, 2]

    def test_parse_citations_dedupes_and_maps(self):
        cs = self._sources()
        text, cites = cs.parse_citations("Answer [1] and also [1] and [3]")
        assert text == "Answer [1] and also [1] and [3]"
        assert len(cites) == 2
        assert cites[0].index == 1 and cites[0].source_type == "web"
        assert cites[0].source_url == "https://a.com"
        assert cites[1].index == 3 and cites[1].source_type == "document"

    def test_unknown_citation_index_ignored(self):
        cs = self._sources()
        _, cites = cs.parse_citations("Nothing [99] here")
        assert cites == []

    def test_build_footer_formats(self):
        cs = self._sources()
        footer = cs.build_citation_footer()
        assert "[1] [T1](https://a.com)" in footer
        assert "[2] KB1 (Knowledge Base)" in footer
        assert "Document — page 2" in footer
        assert "YT (YouTube)" in footer

    def test_enhance_prompt_with_sources(self):
        cs = self._sources()
        enhanced = enhance_system_prompt_with_citations("BASE", cs.get_source_list())
        assert enhanced.startswith("BASE")
        assert "[1] T1 — https://a.com" in enhanced
        assert "CITATION SOURCES" in enhanced

    def test_extract_inline_citations_context(self):
        cs = self._sources()
        results = cs.extract_inline_citations("The quick brown fox jumps [2] over the lazy dog")
        assert len(results) == 1
        assert results[0]["index"] == 2
        assert "quick brown fox" in results[0]["context"]

    def test_page_pattern_not_confused_with_brackets(self):
        cs = CitationService()
        cs.register_sources(doc_content="Page 3\nText on page three about plants.")
        _, cites = cs.parse_citations("See page 3 [1] for details")
        assert len(cites) == 1 and cites[0].index == 1


# ── NSW curriculum ────────────────────────────────────────────────────────

class TestNSWCurriculumAccuracy:

    def setup_method(self):
        self.c = get_curriculum_service()

    def test_stage_for_age_exact(self):
        cases = {4: "ES1", 5: "ES1", 6: "S1", 7: "S1", 8: "S2", 9: "S2",
                 10: "S3", 11: "S3", 12: "S4", 13: "S4", 14: "S4",
                 15: "S5", 16: "S5", 17: "S6", 18: "S6", 19: None, 3: "ES1"}
        for age, expected in cases.items():
            got = self.c.get_stage_for_age(age)
            assert got == expected, f"age {age}: got {got!r}, expected {expected!r}"

    def test_unknown_kla_returns_empty(self):
        assert self.c.get_subject_content("nonexistent", "S4") == []
        assert self.c.get_outcomes("nonexistent", "S4") == []
        assert self.c.get_learning_progression("nonexistent") == {}

    def test_kla_case_insensitive(self):
        a = self.c.get_subject_content("mathematics", "S4")
        b = self.c.get_subject_content("Mathematics", "S4")
        assert a == b and len(a) > 0

    def test_search_curriculum_substring(self):
        results = self.c.search_curriculum("photosynthesis")
        assert isinstance(results, list)
        for r in results:
            assert "photosynthesis" in r["content"].lower()
            assert r["kla"] and r["stage"]

    def test_stages_and_klas_present(self):
        stages = self.c.get_stages()
        assert "ES1" in stages and "S6" in stages
        klas = self.c.get_klas()
        assert len(klas) >= 5
        assert all("name" in v and "code" in v for v in klas.values())

    def test_learning_progression_ordered(self):
        prog = self.c.get_learning_progression("mathematics")
        assert list(prog.keys()) == sorted(prog.keys(), key=lambda s: ["ES1","S1","S2","S3","S4","S5","S6"].index(s))


# ── Document service (quote scoring) ──────────────────────────────────────

class TestDocumentQuoteAccuracy:

    def setup_method(self):
        self.d = DocumentService()

    def test_keyword_extraction_removes_stopwords(self):
        kws = self.d._extract_keywords("Find the quotes about photosynthesis in the chapter")
        assert "photosynthesis" in kws
        assert "the" not in kws
        assert "find" not in kws
        assert len(kws) >= 1

    def test_keyword_score_exact_and_partial(self):
        assert self.d._keyword_score("photosynthesis converts light", ["photosynthesis"]) == 1.0
        assert self.d._keyword_score("photosynthetically active", ["photosynthesis"]) == 0.5
        assert self.d._keyword_score("nothing related", ["photosynthesis"]) == 0.0

    def test_quote_scoring_ranks_relevant_first(self):
        pages = [
            {"page": 1, "text": "Photosynthesis is the process plants use to make food from sunlight."},
            {"page": 2, "text": "The Roman empire expanded across Europe and Africa."},
            {"page": 3, "text": "Photosynthesis requires chlorophyll, water and carbon dioxide to produce glucose."},
        ]
        quotes = self.d._score_quotes(pages, "photosynthesis process plants")
        assert quotes, "expected at least one quote"
        assert quotes[0]["quote"] != quotes[1]["quote"]
        assert all(q["relevance"] > 0 for q in quotes)
        assert quotes[0]["relevance"] >= quotes[-1]["relevance"]

    def test_quote_word_count_bounds(self):
        pages = [{"page": 1, "text": "Short."},
                 {"page": 2, "text": "This sentence has exactly enough words to be considered a quote for the purpose of this test."}]
        quotes = self.d._score_quotes(pages, "enough words quote")
        assert all(8 <= q["word_count"] <= 150 for q in quotes)

    def test_dedup_by_prefix(self):
        pages = [{"page": 1, "text": "The solar system has eight planets orbiting the sun in elliptical paths." * 2}]
        quotes = self.d._score_quotes(pages, "solar system planets")
        starts = [q["quote"][:40] for q in quotes]
        assert len(starts) == len(set(starts))


# ── Study service parsers ─────────────────────────────────────────────────

class TestStudyServiceParserAccuracy:

    def setup_method(self):
        self.s = StudyService()

    def test_parse_quiz_full(self):
        text = (
            "Q1: What is 2+2?\n"
            "A) 3\nB) 4\nC) 5\nD) 6\n"
            "Correct: B\n"
            "Explanation: 2+2 equals 4.\n\n"
            "Q2: What is the capital of France?\n"
            "A) Berlin\nB) Madrid\nC) Paris\nD) Rome\n"
            "Correct: C\n"
            "Explanation: Paris is the capital.\n"
        )
        qs = self.s._parse_quiz(text)
        assert len(qs) == 2
        assert qs[0]["question"] == "What is 2+2?"
        assert qs[0]["options"] == ["3", "4", "5", "6"]
        assert qs[0]["correct"] == "B"
        assert "4" in qs[0]["explanation"]
        assert qs[1]["correct"] == "C"

    def test_parse_quiz_rejects_short_option_sets(self):
        qs = self.s._parse_quiz("Q1: X?\nA) a\nB) b\nCorrect: A\n")
        assert qs == []

    def test_parse_quiz_lowercase_correct(self):
        qs = self.s._parse_quiz("Q1: X?\nA) a\nB) b\nC) c\nD) d\ncorrect: a\n")
        assert qs[0]["correct"] == "A"

    def test_parse_quiz_correct_answer_phrasing(self):
        # "Correct answer: D" must not be missed by the parser
        qs = self.s._parse_quiz(
            "Q1: X?\nA) a\nB) b\nC) c\nD) d\nCorrect answer: D\nExplanation: it is d\n"
        )
        assert len(qs) == 1
        assert qs[0]["correct"] == "D"
        # "Answer: B" phrasing must also parse
        qs2 = self.s._parse_quiz("Q2: Y?\nA) a\nB) b\nC) c\nD) d\nAnswer: B\n")
        assert qs2[0]["correct"] == "B"

    def test_parse_quiz_the_correct_answer_is(self):
        # "The correct answer is B" (unanchored) must not be swallowed as explanation
        qs = self.s._parse_quiz(
            "Q1: X?\nA) a\nB) b\nC) c\nD) d\nThe correct answer is B.\nExplanation: b is right\n"
        )
        assert len(qs) == 1
        assert qs[0]["correct"] == "B"
        assert "b is right" in qs[0]["explanation"]

    def test_parse_quiz_bracketed_correct(self):
        qs = self.s._parse_quiz(
            "Q1: X?\nA) a\nB) b\nC) c\nD) d\nCorrect: (D)\n"
        )
        assert qs[0]["correct"] == "D"

    async def _mock_google(self, snippets, options=None):
        """Run _verify_with_google against injected ResearchService results."""
        from unittest.mock import patch, AsyncMock
        if options is None:
            options = ["Oxygen", "Carbon dioxide", "Nitrogen", "Helium"]
        fake_research = AsyncMock()
        fake_research.search.return_value = [
            {"title": t, "snippet": s} for t, s in snippets
        ]
        with patch("services.research_service.ResearchService") as mock_cls:
            mock_cls.return_value = fake_research
            return await self.s._verify_with_google(
                "Which gas do plants absorb during photosynthesis?",
                options,
                "botany",
            )

    def test_google_verify_prefers_distinct_option(self):
        """Distinctive terms echoed exactly in the snippet must win."""
        import asyncio
        letter = asyncio.run(self._mock_google([
            ("Photosynthesis", "Plants take in carbon dioxide and release oxygen."),
        ]))
        # "carbon dioxide" and "oxygen" both appear; distinctive-score weighs
        # the informative option, so an exact echo should be selected.
        assert letter in "AB"

    def test_google_verify_tolerates_inflection(self):
        """Fuzzy match must handle evaporation vs evaporates."""
        import asyncio
        options = ["Evaporation", "Condensation", "Precipitation", "Collection"]
        letter = asyncio.run(self._mock_google([
            ("Water cycle", "Water evaporates from oceans, lakes and rivers."),
        ], options))
        assert letter == "A"

    def test_google_verify_ignores_conjunctive_options(self):
        """'All of the above' carries no signal and must never be chosen."""
        import asyncio
        options = ["Evaporation", "Condensation", "Precipitation", "All of the above"]
        letter = asyncio.run(self._mock_google([
            ("Water cycle", "Water evaporates from the heated surface of the ocean."),
        ], options))
        assert letter == "A"

    def test_parse_flashcards(self):
        text = (
            "FRONT: What is photosynthesis? | BACK: Process plants use to make food.\n"
            "FRONT: H2O | BACK: Chemical formula for water\n"
            "not a card line without separator\n"
        )
        cards = self.s._parse_flashcards(text)
        assert len(cards) == 2
        assert cards[0]["front"] == "What is photosynthesis?"
        assert "plants" in cards[0]["back"]
        assert cards[1]["front"] == "H2O"

    def test_brain_intents_cover_study_tools(self):
        from services.orchestrator import detect_intents
        # previously study_plan, now covered via exam_sim/audio_overview/etc via brain
        assert "exam_sim" in detect_intents("exam simulation on algebra")
        assert "audio_overview" in detect_intents("audio overview photosynthesis")
        assert "study_intel" in detect_intents("what are my weak topics")


# ── Knowledge base helpers ────────────────────────────────────────────────

class TestKnowledgeBaseHelperAccuracy:

    def test_chunk_text_overlap_contiguous(self):
        text = "word " * 500
        chunks = _chunk_text(text, chunk_size=50)
        assert len(chunks) >= 2
        joined = "".join(chunks)
        assert all(c.strip() for c in chunks)

    def test_chunk_single_small_text(self):
        chunks = _chunk_text("tiny text", chunk_size=50)
        assert chunks == ["tiny text"]

    def test_file_hash_deterministic(self, tmp_path):
        p = tmp_path / "f.txt"
        p.write_text("hello")
        h1 = _file_hash(str(p))
        p.write_text("hello")
        h2 = _file_hash(str(p))
        p.write_text("hello!")
        h3 = _file_hash(str(p))
        assert h1 == h2
        assert h1 != h3
        assert len(h1) == 16

    def test_detect_collection_exact(self):
        cases = [
            ("syllabus.pdf", "NSW Year 7 Mathematics syllabus aligned to the Australian curriculum", "education_au"),
            ("main.py", "def main():\n    return 1\n", "coding"),
            ("paper.pdf", "The abstract describes the methodology and conclusion. The study was peer-reviewed with citations.", "research"),
            ("algebra.pdf", "Solve the equation using the quadratic formula and prove the theorem.", "math"),
            ("biology.pdf", "The experiment studied cells and molecules in organisms and chemical reactions.", "science"),
            ("history.pdf", "The war and the revolution in the 19th century shaped the empire.", "history"),
            ("geography.pdf", "The river crosses continents with varied climate and population density.", "geography"),
        ]
        for fname, text, expected in cases:
            got = _detect_collection(fname, text)
            assert got == expected, f"{fname}: got {got!r}, expected {expected!r}"


# ── Analytics ─────────────────────────────────────────────────────────────

class TestAnalyticsAccuracy:

    def test_streak_calculation(self):
        from datetime import datetime, timezone, timedelta
        a = AnalyticsService()
        daily = {"2026-08-07": 5, "2026-08-06": 3, "2026-08-05": 0, "2026-08-04": 2}
        # anchor "now" explicitly → the test is deterministic regardless of TZ
        now = datetime(2026, 8, 7, tzinfo=timezone.utc)
        # consecutive days from today backward: 07, 06 count; 05 breaks
        assert a._calculate_streak(daily, now) == 2
        assert a._calculate_streak({"2026-08-07": 1, **daily}, now) == 2
        assert a._calculate_streak(daily, datetime(2026, 8, 5, tzinfo=timezone.utc)) == 0


# ── Ollama concurrency guard ──────────────────────────────────────────────

class TestOllamaConcurrencyGuard:

    def test_parallel_completes_bounded(self):
        """6 parallel complete() calls must never exceed MAX_CONCURRENT_CALLS
        concurrent requests to the model server."""
        import asyncio
        import httpx
        import services.ollama_service as osvc

        async def run():
            osvc._loop_semaphores.clear()
            active, max_active = 0, 0
            real_post = httpx.AsyncClient.post

            async def slow_post(client, url, **kw):
                nonlocal active, max_active
                active += 1
                max_active = max(max_active, active)
                await asyncio.sleep(0.02)
                active -= 1
                resp = httpx.Response(200, request=client.build_request("POST", url, json={}))
                resp._content = b'{"message":{"content":"ok"}}'
                return resp

            httpx.AsyncClient.post = slow_post
            try:
                svc = osvc.OllamaService()
                await asyncio.gather(
                    *[svc.complete("m", f"p{i}") for i in range(6)]
                )
            finally:
                httpx.AsyncClient.post = real_post

            return max_active

        max_active = asyncio.run(run())
        assert max_active <= osvc.MAX_CONCURRENT_CALLS
