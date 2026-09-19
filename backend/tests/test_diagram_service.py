"""Unit tests for services.diagram_service — pure heuristic paths + mocked LLM refine.

No live Ollama needed: the refine path patches services.ollama_service.OllamaService.
"""
import json
from unittest.mock import patch

from services.diagram_service import (
    DiagramService,
    _dedupe,
    _fallback_spec,
    _sanitize_spec,
    _smart_title,
    _split_items,
    detect_visual_type,
    suggest_visuals,
)


class TestDetectVisualType:
    def test_venn_is_reachable(self):
        assert detect_visual_type("Draw a Venn diagram for multiples of 2 and 3") == "venn"

    def test_venn_overlap_words(self):
        assert detect_visual_type("What do cats and dogs have in common? overlap") == "venn"

    def test_comparison_vs(self):
        assert detect_visual_type("Compare cats vs dogs") == "comparison"

    def test_no_false_positive_year7(self):
        # "Year 7 maths" must NOT become a timeline
        assert detect_visual_type("Year 7 maths fractions homework") == "flowchart"

    def test_no_false_positive_about(self):
        assert detect_visual_type("Explain photosynthesis") == "flowchart"

    def test_cycle(self):
        assert detect_visual_type("Show the water cycle") == "cycle"

    def test_timeline(self):
        assert detect_visual_type("Timeline of WW2 battles") == "timeline"

    def test_pie(self):
        assert detect_visual_type("pie chart of oceans, 71 percent water") == "pie"

    def test_mindmap(self):
        assert detect_visual_type("make a mind map of cells") == "mindmap"

    def test_steps(self):
        assert detect_visual_type("First do this, then do that, finally serve") == "steps"

    def test_short_token_boundaries(self):
        # "pie" inside "piece" must not trigger pie charts
        assert detect_visual_type("Explain this piece of code") != "pie"

    def test_fallback_is_flowchart(self):
        assert detect_visual_type("Photosynthesis and chlorophyll facts") == "flowchart"


class TestSmartTitle:
    def test_acronyms_preserved(self):
        assert _smart_title("please draw a diagram of WW2 battles") == "WW2 Battles"
        assert _smart_title("make a mind map about DNA replication") == "DNA Replication"

    def test_trailing_please_stripped(self):
        assert _smart_title("WW2 timeline please") == "WW2 Timeline"

    def test_diagram_prefix_stripped(self):
        assert _smart_title("draw a diagram of photosynthesis") == "Photosynthesis"

    def test_empty_prompt_gives_overview(self):
        assert _smart_title("   ") == "Overview"


class TestSplitItems:
    def test_bullets_split(self):
        items = _split_items("Evaporation\nCondensation\nPrecipitation\nCollection")
        assert len(items) >= 4

    def test_duplicates_removed(self):
        items = _split_items("Rain\nRain\nrain\nSnow")
        lowered = [i.lower() for i in items]
        assert len(lowered) == len(set(lowered))

    def test_sentences_split(self):
        items = _split_items("The sun heats water. Vapor rises high. Clouds form slowly. Rain falls down.")
        assert len(items) >= 3

    def test_dedupe_case_insensitive(self):
        assert _dedupe(["Rain", "rain", " Snow "]) == ["Rain", "Snow"]


class TestFallbackSpec:
    def test_shape_and_bounds(self):
        spec = _fallback_spec("Evaporation. Condensation. Precipitation. Collection.")
        assert spec["visual_type"] == "flowchart"
        assert 3 <= len(spec["nodes"]) <= 8
        for node in spec["nodes"]:
            assert node["id"] and node["label"]
            assert len(node["label"]) <= 48

    def test_no_key_point_filler(self):
        spec = _fallback_spec("the water cycle")
        assert len(spec["nodes"]) >= 3
        assert not any("Key point" in n["label"] for n in spec["nodes"])

    def test_flowchart_has_chain_edges(self):
        spec = _fallback_spec("One. Two. Three. Four.", "flowchart")
        ids = [n["id"] for n in spec["nodes"]]
        assert len(spec["edges"]) == len(ids) - 1
        assert spec["edges"][0] == {"from": ids[0], "to": ids[1], "label": ""}

    def test_cycle_edges_loop(self):
        spec = _fallback_spec("One. Two. Three.", "cycle")
        assert spec["edges"][-1]["to"] == spec["nodes"][0]["id"]

    def test_mindmap_has_no_edges(self):
        spec = _fallback_spec("Cells. Nucleus. Membrane.", "mindmap")
        assert spec["edges"] == []

    def test_bad_type_falls_back(self):
        spec = _fallback_spec("One. Two. Three.", "not-a-type")
        assert spec["visual_type"] == "flowchart"


class TestSanitizeSpec:
    def test_dedupes_labels(self):
        data = {
            "visual_type": "flowchart", "title": "T",
            "nodes": [{"label": "Evaporation"}, {"label": "evaporation"}, {"label": "Rain"}, {"label": "Snow"}],
            "edges": [],
        }
        spec = _sanitize_spec(data, "water cycle", "flowchart")
        assert [n["label"] for n in spec["nodes"]] == ["Evaporation", "Rain", "Snow"]

    def test_too_few_nodes_falls_back_to_heuristic(self):
        data = {"visual_type": "flowchart", "title": "T", "nodes": [{"label": "Only"}], "edges": []}
        spec = _sanitize_spec(data, "Evaporation. Condensation. Rain.", "flowchart")
        assert len(spec["nodes"]) >= 3

    def test_bad_visual_type_uses_hint(self):
        data = {"visual_type": "nonsense", "title": "T",
                "nodes": [{"label": "A"}, {"label": "B"}, {"label": "C"}], "edges": []}
        spec = _sanitize_spec(data, "topic", "timeline")
        assert spec["visual_type"] == "timeline"

    def test_icon_falls_back_when_missing(self):
        data = {"visual_type": "flowchart", "title": "T",
                "nodes": [{"label": "Evaporation"}, {"label": "Condensation"}, {"label": "Rain"}],
                "edges": []}
        spec = _sanitize_spec(data, "water cycle", "flowchart")
        assert all(n["icon"] for n in spec["nodes"])

    def test_edges_only_keep_valid_ids(self):
        data = {"visual_type": "flowchart", "title": "T",
                "nodes": [{"label": "A"}, {"label": "B"}, {"label": "C"}],
                "edges": [{"from": "n1", "to": "n2", "label": ""}, {"from": "n1", "to": "n99"}]}
        spec = _sanitize_spec(data, "topic", "flowchart")
        assert spec["edges"] == [{"from": "n1", "to": "n2", "label": ""}]


class TestSuggestVisuals:
    def test_three_options_first_recommended(self):
        opts = suggest_visuals("Draw a Venn diagram of cats and dogs")
        assert len(opts) == 3
        assert opts[0]["type"] == "venn"
        assert opts[0]["recommended"] is True
        assert all(not o["recommended"] for o in opts[1:])


class _StubOllama:
    """OllamaService stub accepting DiagramService's kwargs."""

    def __init__(self, payload=None, calls=None):
        self._payload = payload
        self.calls = calls if calls is not None else []

    async def complete(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class TestGenerate:
    async def test_empty_prompt_errors(self):
        res = await DiagramService().generate("   ")
        assert "error" in res

    async def test_bad_visual_type_is_detected_not_crash(self):
        res = await DiagramService().generate("Evaporation. Condensation. Rain.", visual_type="nope")
        assert res["spec"]["visual_type"] == "flowchart"

    async def test_llm_refine_path_used_when_valid(self):
        payload = json.dumps({
            "visual_type": "steps", "title": "Water Steps",
            "nodes": [
                {"id": "n1", "label": "Evaporate", "sub": "Sun heats", "icon": "☀️"},
                {"id": "n2", "label": "Condense", "sub": "Clouds form", "icon": "☁️"},
                {"id": "n3", "label": "Rain", "sub": "Falls down", "icon": "🌧️"},
                {"id": "n4", "label": "Collect", "sub": "Rivers fill", "icon": "💧"},
            ],
            "edges": [{"from": "n1", "to": "n2", "label": ""}],
        })
        DiagramService._refine_cache.clear()
        with patch("services.ollama_service.OllamaService", return_value=_StubOllama(payload)):
            res = await DiagramService().generate("Evaporation. Condensation. Rain. Collect.", visual_type="steps")
        assert res["spec"]["title"] == "Water Steps"
        assert len(res["spec"]["nodes"]) == 4
        assert "fallback" not in res

    async def test_llm_garbage_falls_back_to_heuristic(self):
        DiagramService._refine_cache.clear()
        with patch("services.ollama_service.OllamaService", return_value=_StubOllama("not json at all")):
            res = await DiagramService().generate("Evaporation. Condensation. Rain.")
        assert len(res["spec"]["nodes"]) >= 3
        assert res.get("fallback") is True

    async def test_refine_cache_skips_second_llm_call(self):
        payload = json.dumps({
            "visual_type": "flowchart", "title": "Cached",
            "nodes": [{"label": "A1"}, {"label": "B2"}, {"label": "C3"}],
            "edges": [],
        })
        DiagramService._refine_cache.clear()
        calls: list = []
        with patch("services.ollama_service.OllamaService", return_value=_StubOllama(payload, calls)):
            first = await DiagramService().generate("Alpha. Beta. Gamma.")
            second = await DiagramService().generate("Alpha. Beta. Gamma.")
        assert first["spec"]["title"] == "Cached"
        assert second.get("cached") is True
        assert len(calls) == 1

    async def test_suggest_returns_preview(self):
        res = await DiagramService().suggest("the water cycle")
        assert len(res["options"]) == 3
        assert len(res["preview"]["nodes"]) >= 3
