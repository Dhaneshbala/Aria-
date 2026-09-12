"""Tests for the orchestrator: intent routing, model selection, streaming flow.

The intent router (detect_intents) is ARIA's front door — every message is
classified here, so these tests pin down the exact expected behaviour and
guard against regressions. The full orchestrate() flow is tested with
fakes for every service so no network/model is needed.
"""
import json

import pytest

import services.orchestrator as orch
from services.orchestrator import (
    _build_system_prompt,
    _generate_suggestions,
    _sse,
    choose_models,
    detect_intents,
    detect_message_language,
    orchestrate,
)


# ═══════════════════════ 1. Intent routing ══════════════════════════════════

def test_intents_default_to_chat():
    assert detect_intents("Hello there!") == ["chat"]
    assert detect_intents("") == ["chat"]


def test_intent_quiz():
    assert "quiz" in detect_intents("quiz me on World War 2")
    assert "quiz" in detect_intents("give me practice questions on fractions")
    assert "quiz" in detect_intents("olympiad question on geometry")


def test_intent_flashcards():
    assert "flashcard" in detect_intents("make flashcards for science")
    assert "flashcard" in detect_intents("create flash cards for the water cycle")
    assert "flashcard" in detect_intents("memorize these key terms")


def test_intent_mindmap_routes_to_diagram():
    # Standalone mindmap generator removed — mind-map requests use the
    # chat diagram generator (which supports a mindmap visual type).
    assert "diagram" in detect_intents("make a mind map of the water cycle")
    assert "diagram" in detect_intents("create a concept map about cells")
    assert "diagram" in detect_intents("visualise photosynthesis as a branch diagram")
    assert "mindmap" not in detect_intents("make a mind map of the water cycle")


def test_intent_exam_sim():
    assert "exam_sim" in detect_intents("create an exam simulation on algebra")
    assert "exam_sim" in detect_intents("mock exam for photosythesis")


def test_intent_audio_overview():
    assert "audio_overview" in detect_intents("give me an audio overview of photosynthesis")
    assert "audio_overview" in detect_intents("create audio guide for WW2")


def test_intent_study_intel():
    assert "study_intel" in detect_intents("what are my weak topics")
    assert "study_intel" in detect_intents("what should I study next")


def test_intent_math():
    assert "math" in detect_intents("solve 3x + 5 = 20")
    assert "math" in detect_intents("what is the area of a triangle with base 8 and height 5")
    assert "math" in detect_intents("calculate 2 + 2 * 3")


def test_intent_explain():
    assert "explain" in detect_intents("explain photosynthesis")
    assert "explain" in detect_intents("what is a black hole")
    assert "explain" in detect_intents("how does a battery work")


def test_intent_summary():
    assert "summary" in detect_intents("summarise the key points of the chapter")
    assert "summary" in detect_intents("give me a tldr of this topic")


def test_intent_coding():
    assert "coding" in detect_intents("debug this python code")
    assert "coding" in detect_intents("write a function in javascript")
    assert "coding" in detect_intents("what does this html do")


def test_intent_web_search():
    assert "web_search" in detect_intents("search for the latest discoveries about black holes")
    assert "web_search" in detect_intents("what happened in the news today")


def test_intent_youtube_url():
    assert "youtube" in detect_intents("https://www.youtube.com/watch?v=abc123 explain it")


def test_intent_translate():
    assert "translate" in detect_intents("translate bonjour to english")
    assert "translate" in detect_intents("traducir esta frase al ingles")


def test_intent_image_added_with_image():
    assert "image_analysis" in detect_intents("what does this say", has_image=True)


def test_intent_doc_chat_added_with_doc():
    assert "doc_chat" in detect_intents("what are the quotes about diversity", has_doc=True)


def test_intent_worksheet_solver():
    assert "worksheet_solver" in detect_intents("help me with question 3 on the worksheet")
    assert "worksheet_solver" in detect_intents("solve this homework")


def test_intent_essay_feedback():
    assert "essay_feedback" in detect_intents("review my essay please")
    assert "essay_feedback" in detect_intents("improve this essay")


def test_intent_quote_extraction():
    assert "quote_extraction" in detect_intents("find quotes about diversity in this pdf")


def test_intent_geography():
    assert "geography" in detect_intents("what is the capital city of France")
    assert "geography" in detect_intents("explain how rivers erode the land")


def test_intent_formula():
    assert "formula" in detect_intents("what is the formula for area of a circle")


def test_intent_timeline():
    assert "timeline" in detect_intents("make a timeline of world war 2")


def test_intent_image_gen():
    assert "image_gen" in detect_intents("draw the solar system")
    assert "image_gen" in detect_intents("generate an image of a volcano")


def test_intent_multiple_intents():
    intents = detect_intents("quiz me on fractions and make flashcards")
    assert "quiz" in intents and "flashcard" in intents


def test_intent_no_false_positive_math():
    # "equation" in a biology context must not trigger maths
    intents = detect_intents("explain the equation for photosynthesis")
    assert "math" not in intents
    assert "explain" in intents


# ═══════════════════════ 2. Language detection ═══════════════════════════════

def test_language_detection():
    assert detect_message_language("안녕하세요") == "Korean"
    assert detect_message_language("こんにちは") == "Japanese"
    assert detect_message_language("你好") == "Chinese"
    assert detect_message_language("مرحبا") == "Arabic"
    assert detect_message_language("नमस्ते") == "Hindi"
    assert detect_message_language("vanakkam வணக்கம்") == "Tamil"
    assert detect_message_language("привет") == "Russian"
    assert detect_message_language("por favor ayúdame") == "Spanish"
    assert detect_message_language("bonjour merci") == "French"
    assert detect_message_language("danke schön bitte") == "German"
    assert detect_message_language("grazie per favore") == "Italian"


def test_language_detection_english_is_none():
    assert detect_message_language("hello how are you") is None
    assert detect_message_language("") is None


# ═══════════════════════ 3. Model selection ═════════════════════════════════

CONFIG = {
    "model": "gemma4:e4b-mlx",
    "reasoning_model": "gemma4:e4b-mlx",
    "vision_model": "gemma4:e4b-mlx",
    "coding_model": "gemma4:e4b-mlx",
    "fallback_model": "gemma4:e4b-mlx",
}

# Legacy config — should still route but migrate to gemma for vision
LEGACY_CONFIG = {
    "reasoning_model": "qwen3:8b",
    "vision_model": "qwen2.5vl:3b",
    "coding_model": "qwen2.5-coder:7b",
    "fallback_model": "llama3.2:3b",
}


def test_choose_models_plain_chat():
    # New single-model routing: all generation uses gemma
    assert choose_models(["chat"], CONFIG) == {"reasoning": "gemma4:e4b-mlx", "fallback": "gemma4:e4b-mlx"}
    # Legacy config still returns legacy if explicitly set, but coding now maps to main
    assert choose_models(["chat"], LEGACY_CONFIG) == {"reasoning": "qwen3:8b", "fallback": "qwen3:8b"}


def test_choose_models_coding_uses_coder():
    # Single model: coding uses same main model (no separate coder needed)
    assert choose_models(["coding"], CONFIG) == {"reasoning": "gemma4:e4b-mlx", "fallback": "gemma4:e4b-mlx"}
    # Legacy coding_model is now mapped to main (gemma strategy)
    assert choose_models(["coding"], LEGACY_CONFIG) == {"reasoning": "qwen3:8b", "fallback": "qwen3:8b"}


def test_choose_models_vision():
    # Gemma is multimodal — vision points to same main model
    m = choose_models(["image_analysis", "explain"], CONFIG)
    assert m["vision"] == "gemma4:e4b-mlx"
    assert m["reasoning"] == "gemma4:e4b-mlx"
    # Legacy vision model is migrated to legacy main (or gemma if main is gemma)
    m2 = choose_models(["image_analysis", "explain"], LEGACY_CONFIG)
    assert m2["vision"] == "qwen3:8b"  # migrated to legacy main
    assert m2["reasoning"] == "qwen3:8b"


def test_choose_models_quiz():
    assert choose_models(["quiz"], CONFIG) == {"reasoning": "gemma4:e4b-mlx", "fallback": "gemma4:e4b-mlx"}


def test_choose_models_no_intent_is_empty():
    # New behaviour: empty intents still returns a default reasoning model (gemma)
    # so orchestrator never has zero models
    assert choose_models([], CONFIG) == {"reasoning": "gemma4:e4b-mlx", "fallback": "gemma4:e4b-mlx"}


# ═══════════════════════ 4. Streaming flow (all fakes) ══════════════════════

class FakeStream:
    """Streams a fixed token sequence then finishes."""

    def __init__(self, tokens, errors=None):
        self._tokens = tokens
        self._errors = errors or []

    async def __call__(self, model, system, message, context_window=4096, **kwargs):
        for i, t in enumerate(self._tokens):
            if i in self._errors:
                raise RuntimeError("ollama down")
            yield t


class FakeOllama:
    def __init__(self, tokens=("Hello", " world")):
        self.stream = FakeStream(tokens)
        self.complete_calls = 0

    async def complete(self, model, prompt, system="", max_tokens=2048,
                       timeout=300.0, think=None, json_mode=False, context_window=4096):
        self.complete_calls += 1
        return '{"verified": true, "notes": "ok"}' if "fact" in prompt else ""

    async def unload_model(self, model):
        return True


class FakeMemory:
    async def retrieve(self, conversation_id, query, k=4):
        return []

    async def save(self, conversation_id, user_msg, ai_msg):
        return None

    async def get_profile(self):
        return {"subjects": {}, "last_active": None}


class FakeKB:
    async def search(self, message, n_results=5):
        return []


class FakeResearch:
    async def search(self, message, max_results=4):
        return []


class FakeYouTube:
    async def process(self, url):
        return {"title": "Test", "transcript": "hello"}


class FakeStudy:
    async def generate_quiz(self, topic, level, count, model):
        return None


class FakeCitation:
    def __init__(self):
        self.sources = []

    def register_sources(self, **kw):
        self.sources.append(kw)

    def parse_citations(self, text):
        return [], []

    def get_source_list(self):
        return []


@pytest.fixture
def fakes(monkeypatch):
    fake = {
        "ollama": FakeOllama(),
        "memory_svc": FakeMemory(),
        "kb_svc": FakeKB(),
        "research_svc": FakeResearch(),
        "youtube_svc": FakeYouTube(),
        "study_svc": FakeStudy(),
        "citation_svc": FakeCitation(),
    }
    for name, obj in fake.items():
        monkeypatch.setattr(orch, name, obj)
    return fake


def _collect(agen):
    return [json.loads(c[6:]) for c in agen]


async def test_orchestrate_plain_chat_flow(fakes):
    events = _collect([c async for c in orchestrate("hello", "c1", config={})])
    types = [e["type"] for e in events]
    assert types[0] == "intent"
    assert "text" in types
    assert "done" in types
    assert "error" not in types
    assert types.count("text") == 2  # "Hello" + " world"


async def test_orchestrate_emits_intents_event(fakes):
    events = _collect([c async for c in orchestrate("quiz me on maths", "c1", config={})])
    intent_ev = events[0]
    assert "quiz" in intent_ev["content"]


async def test_orchestrate_uses_fallback_when_primary_fails(fakes):
    # Primary model stream raises, fallback works
    def _bad_stream(model, system, message, context_window=4096, **kwargs):
        raise RuntimeError("down")

    async def _good_stream(model, system, message, context_window=4096, **kwargs):
        yield "recovered"

    fake_ollama = fakes["ollama"]
    fake_ollama.stream = _bad_stream
    # Second attempt (fallback) succeeds
    calls = {"n": 0}

    async def _flaky_stream(model, system, message, context_window=4096, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("down")
        yield "recovered"

    fake_ollama.stream = _flaky_stream
    events = _collect([c async for c in orchestrate("hello", "c1", config={})])
    assert events[-1]["type"] == "done"
    assert "recovered" in [e.get("content", "") for e in events if e["type"] == "text"]
    assert "error" not in [e["type"] for e in events]


async def test_orchestrate_emits_friendly_error_when_all_models_fail(fakes):
    def _fail_stream(model, system, message, context_window=4096, **kwargs):
        async def _gen():
            raise RuntimeError("ollama is down")
            yield  # pragma: no cover
        return _gen()

    fakes["ollama"].stream = _fail_stream
    events = _collect([c async for c in orchestrate("hello", "c1", config={})])
    types = [e["type"] for e in events]
    assert "error" in types
    assert types[-1] == "done"
    error_text = next(e["content"] for e in events if e["type"] == "error")
    assert "AI engine" in error_text


async def test_orchestrate_saves_memory(fakes, monkeypatch):
    saved = []

    class Mem:
        async def retrieve(self, *a, **k):
            return []

        async def save(self, cid, user, ai):
            saved.append((cid, user, ai))

    monkeypatch.setattr(orch, "memory_svc", Mem())
    events = _collect([c async for c in orchestrate("hello", "c1", config={"memory_enabled": True})])
    assert saved and saved[0][0] == "c1"
    assert saved[0][1] == "hello"
    assert saved[0][2] == "Hello world"


async def test_orchestrate_skips_extras_when_response_short(fakes):
    fakes["ollama"] = FakeOllama(tokens=("hi",))
    events = _collect([c async for c in orchestrate("hello", "c1", config={})])
    kinds = [e["type"] for e in events]
    assert "extras" not in kinds
    assert "suggestions" not in kinds


async def test_orchestrate_image_flow(fakes, monkeypatch):
    seen = {}

    class Img:
        async def analyse(self, data, mime, model):
            seen["model"] = model
            return "DESCRIPTION: a worksheet about fractions"

    monkeypatch.setattr(orch, "image_svc", Img())
    events = _collect([c async for c in
                       orchestrate("answer this", "c1", image_data=b"x", image_mime="image/png",
                                   config={})])
    types = [e["type"] for e in events]
    assert "image_analysis" in events[0]["content"]
    assert seen["model"] == "gemma4:e4b-mlx"
    assert "tool" in types


# ═══════════════════════ 5. System prompt building ══════════════════════════

def test_build_system_prompt_contains_student_name():
    p = _build_system_prompt(["chat"], None, None, None, "", None,
                             {"student_name": "Amy", "student_age": 12})
    assert "Amy" in p


def test_build_system_prompt_quiz_mode():
    p = _build_system_prompt(["quiz"], None, None, None, "", None, {})
    assert "QUIZ MODE" in p


def test_build_system_prompt_math_mode():
    p = _build_system_prompt(["math"], None, None, None, "", None, {})
    assert "MATHS MODE" in p


def test_build_system_prompt_think_mode():
    p = _build_system_prompt(["chat"], None, None, None, "", None, {})
    # mode adjustments are appended by orchestrate(), not the builder
    assert "THINK MODE" not in p


def test_build_system_prompt_doc_text():
    p = _build_system_prompt(["doc_chat"], None, None, "Chapter text here", "", None, {})
    assert "Chapter text here" in p


def test_build_system_prompt_web_results():
    results = [{"title": "T1", "snippet": "S1"}]
    p = _build_system_prompt(["web_search"], results, None, None, "", None, {})
    assert "T1" in p


# ═══════════════════════ 6. Parsers & helpers ═══════════════════════════════

def test_sse_format():
    assert _sse({"type": "done"}) == 'data: {"type": "done"}\n\n'


async def test_generate_suggestions_parses_numbered_lines():
    async def _fake_complete(model, prompt, system="", max_tokens=2048, timeout=300.0,
                             think=None, json_mode=False, context_window=4096):
        return "1. What happens next?\n2. Why is the sky blue?\n3. Can you show me an example?"

    import services.orchestrator as o
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(o.ollama, "complete", _fake_complete)
    try:
        sugg = await _generate_suggestions("q", "a")
        assert sugg is not None and len(sugg) == 3
        assert all(not s[0].isdigit() for s in sugg)  # numbering stripped
    finally:
        monkeypatch.undo()


async def test_generate_suggestions_fails_gracefully():
    async def _boom(model, prompt, system="", max_tokens=2048, timeout=300.0,
                    think=None, json_mode=False, context_window=4096):
        raise RuntimeError("nope")

    import services.orchestrator as o
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(o.ollama, "complete", _boom)
    try:
        assert await _generate_suggestions("q", "a") is None
    finally:
        monkeypatch.undo()
