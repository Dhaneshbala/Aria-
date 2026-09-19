"""Chat-core slice 2: prompt-budget enforcement (hermetic, no models/network)."""
from services.prompt_builder import (
    MAX_PROMPT_CHARS,
    _build_system_prompt,
    enforce_prompt_budget,
)


def _big_search(n=5, snippet_len=400):
    return [{"title": f"T{i}", "snippet": "s" * snippet_len, "url": f"https://x/{i}"} for i in range(n)]


def test_small_prompts_untouched():
    p1 = _build_system_prompt(["chat"], None, None, None, "", None, {})
    p2 = _build_system_prompt(["chat"], None, None, None, "", None, {}, max_chars=20000)
    assert p1 == p2
    assert len(p1) < MAX_PROMPT_CHARS


def test_worst_case_capped_to_budget():
    big_doc = "x" * 15000
    big_mem = "m" * 5000
    big_kb = "k" * 5000
    search = _big_search()
    yt = {"title": "YT", "transcript": "y" * 3000}
    cc = _big_search(n=4, snippet_len=300)
    p = _build_system_prompt(
        ["explain", "web_search"], search, "v" * 2000, big_doc, big_mem,
        yt, {}, cross_check=cc, kb_context=big_kb, max_chars=20000,
    )
    assert len(p) <= 20000 + 8000  # base (~7k) + budget headroom for chrome
    # Doc (highest priority) must survive at least partially
    assert "xxxx" in p


def test_priority_cross_check_cut_first():
    fit = enforce_prompt_budget(
        memory_context="m" * 2000,
        kb_context="k" * 2500,
        vision_text="v" * 3000,
        doc_text="d" * 12000,
        search_results=_big_search(),
        youtube_results={"title": "YT", "transcript": "y" * 2000},
        cross_check=_big_search(n=4, snippet_len=300),
        max_chars=20000,
        base_chars=7000,
    )
    assert fit["truncated"] is True
    # cross-check budget should be zeroed before doc is touched
    assert fit["budgets"]["cross_check"] == 0
    assert len(fit["doc_text"]) > 5000


def test_fits_without_truncation_flag():
    fit = enforce_prompt_budget(memory_context="hi", max_chars=20000)
    assert fit["truncated"] is False
    assert fit["memory_context"] == "hi"


def test_custom_max_chars_respected():
    p = _build_system_prompt(["chat"], None, None, "d" * 50000, "", None, {}, max_chars=9000)
    assert len(p) <= 9000 + 8000
