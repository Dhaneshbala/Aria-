"""Diagram service — Napkin AI-style visual generation for ARIA.

Napkin flow replicated locally (private, M4-friendly):
  text ──▶ detect visual type ──▶ heuristic spec (instant) ──▶ frontend renders SVG
                                       │
                                       └─▶ background LLM refinement (optional, caches result)

Speed: heuristic-first gives instant diagram. LLM refines labels/icons in background.
Quality: heuristic now extracts smarter nodes with sub-descriptions and context-aware icons.

Spec shape:
  {
    "visual_type": "flowchart|mindmap|cycle|timeline|steps|comparison|pyramid|venn|pie|bar",
    "title": "Water Cycle",
    "nodes": [{"id": "n1", "label": "Evaporation", "sub": "Sun heats water", "icon": "☀️"}],
    "edges": [{"from": "n1", "to": "n2", "label": ""}],
  }
Rules: 3-8 nodes, label ≤ 48 chars, sub ≤ 80 chars.
"""

import json
import logging
import re
import asyncio

logger = logging.getLogger(__name__)

VISUAL_TYPES = [
    "flowchart", "mindmap", "cycle", "timeline", "steps",
    "comparison", "pyramid", "venn", "pie", "bar",
]

# ── Auto-detect: prompt keywords → best visual type (Napkin's auto-pick) ──
_TYPE_HINTS = [
    ({"venn", "overlap", "both", "neither", "compare", "contrast", "vs", "versus"}, "comparison"),
    ({"timeline", "history", "chronolog", "evolution", "year", "century", "ww2", "war"}, "timeline"),
    ({"cycle", "water cycle", "carbon cycle", "circulat", "loop", "recycl"}, "cycle"),
    ({"process", "steps", "procedure", "how to", "method", "stage"}, "steps"),
    ({"flowchart", "flow", "decision", "if ", "workflow", "algorithm"}, "flowchart"),
    ({"pyramid", "hierarchy", "levels of", "maslow", "food chain"}, "pyramid"),
    ({"pie", "percent", "share", "proportion", "distribution"}, "pie"),
    ({"bar", "statistics", "stats", "compare numbers", "chart"}, "bar"),
    ({"mindmap", "mind map", "branches", "concept map", "overview", "about"}, "mindmap"),
]

_ICON_HINTS = [
    ({"sun", "solar", "evaporat"}, "☀️"), ({"water", "rain", "ocean", "river"}, "💧"),
    ({"plant", "photo", "leaf"}, "🌱"), ({"cell", "blood", "body", "heart"}, "🧬"),
    ({"war", "battle", "army", "history"}, "⚔️"), ({"space", "planet", "star"}, "🪐"),
    ({"money", "econom", "trade"}, "💰"), ({"code", "program", "comput"}, "💻"),
    ({"food", "eat", "nutri"}, "🍎"), ({"energy", "power", "electric"}, "⚡"),
    ({"earth", "climate", "carbon"}, "🌍"), ({"animal", "species"}, "🐾"),
    ({"math", "number", "fraction", "angle"}, "📐"), ({"music", "sound"}, "🎵"),
    ({"book", "essay", "writ"}, "📚"), ({"sport", "game"}, "⚽"),
    ({"heart", "love", "emotion"}, "❤️"), ({"brain", "think", "cognitive"}, "🧠"),
    ({"time", "clock", "schedule"}, "⏰"), ({"home", "house", "building"}, "🏠"),
    ({"car", "transport", "travel"}, "🚗"), ({"fire", "heat", "burn"}, "🔥"),
    ({"wind", "air", "breeze"}, "💨"), ({"mountain", "rock", "geology"}, "🏔️"),
    ({"ocean", "sea", "marine"}, "🌊"), ({"star", "night", "sky"}, "⭐"),
]

# ── Smart sub-descriptions for common topics ──
_SUB_HINTS = [
    ({"evaporat", "vapor"}, "Sun heats water, turning it to vapor"),
    ({"condens", "cloud"}, "Vapor cools and forms clouds"),
    ({"precipit", "rain", "snow"}, "Water falls as rain or snow"),
    ({"collect", "runoff", "river"}, "Water flows into rivers and lakes"),
    ({"absorb", "root", "uptake"}, "Plants absorb water through roots"),
    ({"transpir", "release"}, "Plants release water vapor through leaves"),
    ({"photosyn", "light"}, "Plants use sunlight to make food"),
    ({"respir", "breathe"}, "Living things breathe in oxygen"),
    ({"decompos", "break down"}, "Dead matter breaks down into soil"),
    ({"produc", "output"}, "What gets created or made"),
    ({"consum", "input", "use"}, "What gets used or eaten"),
    ({"energy", "power"}, "The force that makes things happen"),
    ({"transfer", "move"}, "Things moving from one place to another"),
    ({"store", "keep"}, "Where things are kept or saved"),
    ({"control", "regulate"}, "What manages or controls the process"),
    ({"feedback", "loop"}, "The output feeds back into the input"),
]


def detect_visual_type(prompt: str) -> str:
    p = prompt.lower()
    for keywords, vtype in _TYPE_HINTS:
        if any(k in p for k in keywords):
            return vtype
    if re.search(r"\bvs\b|versus|pros.?cons|advantages?.*disadvantages?", p):
        return "comparison"
    if re.search(r"\b(1[.)]|first|then|next|finally)\b", p):
        return "steps"
    return "flowchart"


def _icon_for(label: str, prompt: str = "") -> str:
    text = f"{label} {prompt}".lower()
    for keywords, icon in _ICON_HINTS:
        if any(k in text for k in keywords):
            return icon
    return "📌"


def _sub_for(label: str) -> str:
    text = label.lower()
    for keywords, sub in _SUB_HINTS:
        if any(k in text for k in keywords):
            return sub
    return ""


def suggest_visuals(prompt: str) -> list[dict]:
    primary = detect_visual_type(prompt)
    alternates = {
        "flowchart": ["steps", "mindmap"],
        "steps": ["flowchart", "timeline"],
        "timeline": ["steps", "mindmap"],
        "cycle": ["flowchart", "steps"],
        "mindmap": ["flowchart", "comparison"],
        "comparison": ["venn", "mindmap"],
        "pyramid": ["steps", "mindmap"],
        "venn": ["comparison", "mindmap"],
        "pie": ["bar", "comparison"],
        "bar": ["pie", "comparison"],
    }
    picks = [primary] + alternates.get(primary, ["mindmap", "steps"])
    labels = {
        "flowchart": "Flow — shows order & decisions",
        "mindmap": "Mind map — big picture branches",
        "cycle": "Cycle — loops back to the start",
        "timeline": "Timeline — events in time order",
        "steps": "Steps — numbered sequence",
        "comparison": "Compare — side by side",
        "pyramid": "Pyramid — hierarchy levels",
        "venn": "Venn — overlaps & shared traits",
        "pie": "Pie — shares of a whole",
        "bar": "Bars — compare sizes",
    }
    return [{"type": t, "label": labels.get(t, t), "recommended": i == 0} for i, t in enumerate(picks[:3])]


def _fallback_spec(prompt: str, visual_type: str | None = None) -> dict:
    """Smart heuristic spec builder — works with zero model (offline-safe).

    Now extracts meaningful nodes with sub-descriptions and context-aware icons.
    """
    vtype = visual_type or detect_visual_type(prompt)
    if vtype not in VISUAL_TYPES:
        vtype = "flowchart"
    # Try bullets / numbered lines first, then sentences, then phrases
    lines = [l.strip(" •-*0123456789.)\t ") for l in re.split(r"[\n;]", prompt) if l.strip()]
    items: list[str] = []
    for ln in lines:
        parts = re.split(r"\s*[•·]\s*|\s{2,}", ln)
        items.extend(p.strip() for p in parts if p.strip())
    if len(items) < 3:
        items = [s.strip() for s in re.split(r"(?<=[.!?])\s+", prompt) if len(s.strip()) > 8]
    if len(items) < 3:
        items = [p.strip() for p in re.split(r",\s*", prompt) if len(p.strip()) > 3]
    items = [i[:70] for i in items if i][:6]
    while len(items) < 3:
        items.append(f"Key point {len(items) + 1}")
    title_bits = prompt.strip().split("\n")[0][:60]
    title = re.sub(r"^(please\s+)?(draw|generate|create|make|show|give|explain)\b[^a-zA-Z]*", "", title_bits, flags=re.I).strip().title() or "Overview"
    nodes = [
        {
            "id": f"n{i+1}",
            "label": _short(label, 48),
            "sub": _sub_for(label) or "",
            "icon": _icon_for(label, prompt),
        }
        for i, label in enumerate(items[:6])
    ]
    edges = _chain_edges(nodes, vtype)
    return {"visual_type": vtype, "title": _short(title, 60), "nodes": nodes, "edges": edges}


def _short(text: str, n: int) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _chain_edges(nodes: list[dict], vtype: str) -> list[dict]:
    ids = [nd["id"] for nd in nodes]
    if vtype == "cycle":
        return [{"from": ids[i], "to": ids[(i + 1) % len(ids)], "label": ""} for i in range(len(ids))]
    if vtype in ("comparison", "venn", "pie", "bar", "pyramid", "mindmap", "timeline"):
        return []
    return [{"from": ids[i], "to": ids[i + 1], "label": ""} for i in range(len(ids) - 1)]


def _sanitize_spec(data: dict, prompt: str, fallback_type: str) -> dict:
    """Clamp LLM output to the safe spec shape (Napkin: 3-8 short nodes)."""
    vtype = str(data.get("visual_type", fallback_type or "")).lower().strip()
    if vtype not in VISUAL_TYPES:
        vtype = detect_visual_type(prompt) if not fallback_type else fallback_type
    title = _short(str(data.get("title", "") or prompt[:50]), 60) or "Overview"
    raw_nodes = data.get("nodes") or []
    nodes: list[dict] = []
    for i, nd in enumerate(raw_nodes[:8]):
        if isinstance(nd, str):
            nd = {"label": nd}
        if not isinstance(nd, dict):
            continue
        label = _short(str(nd.get("label", "")), 48)
        if not label:
            continue
        nodes.append({
            "id": f"n{i+1}",
            "label": label,
            "sub": _short(str(nd.get("sub", "")), 80),
            "icon": str(nd.get("icon", ""))[:4] or _icon_for(label, prompt),
        })
    if len(nodes) < 3:
        return _fallback_spec(prompt, vtype)
    ids = {nd["id"] for nd in nodes}
    edges: list[dict] = []
    for e in (data.get("edges") or [])[:10]:
        if isinstance(e, dict) and e.get("from") in ids and e.get("to") in ids:
            edges.append({"from": e["from"], "to": e["to"], "label": _short(str(e.get("label", "")), 24)})
    if not edges and vtype in ("flowchart", "steps", "cycle"):
        edges = _chain_edges(nodes, vtype)
    return {"visual_type": vtype, "title": title, "nodes": nodes, "edges": edges}


_SPEC_SYSTEM = (
    "You turn study text into a Napkin AI-style visual diagram spec. "
    "Reply with ONLY valid JSON, no markdown, no commentary.\n"
    'Schema: {"visual_type": "flowchart|mindmap|cycle|timeline|steps|comparison|pyramid|venn|pie|bar", '
    '"title": "short title", '
    '"nodes": [{"id": "n1", "label": "short label max 7 words", "sub": "one-line detail or empty", "icon": "one emoji"}], '
    '"edges": [{"from": "n1", "to": "n2", "label": ""}]}\n'
    "Rules: 4-6 nodes (min 3, max 8). Labels short and kid-friendly (13-year-old). "
    "flowchart/steps/cycle need chain edges; mindmap/timeline/comparison/pyramid/venn/pie/bar use []. "
    "comparison needs exactly 2 big nodes plus up to 4 point nodes. venn needs 2-3 nodes. "
    "pie/bar: append numbers in labels when known (e.g. 'Oceans 71%'). One emoji icon per node."
)


class DiagramService:
    """Napkin-style diagrams via the main local model (no LoRA, no GPU cost).

    Speed strategy: heuristic-first (instant), LLM refines in background (optional).
    """

    async def generate(self, prompt: str, visual_type: str | None = None,
                       model: str | None = None, max_tokens: int = 300) -> dict:
        """Returns {"type": "napkin", "spec": {...}} — or {"error": ...}.

        Instant: returns heuristic spec immediately.
        Then: tries LLM refinement (faster with reduced params).
        """
        prompt = (prompt or "").strip()[:1200]
        if not prompt:
            return {"error": "Prompt cannot be empty"}
        want = (visual_type or "").lower().strip() or None
        if want and want not in VISUAL_TYPES:
            want = None
        hint = want or detect_visual_type(prompt)

        # Instant: heuristic spec
        instant_spec = _fallback_spec(prompt, hint)

        # Try LLM refinement with timeout (5s max — don't block the user)
        try:
            from services.ollama_service import OllamaService
            from models.database import get_config, MODELS
            cfg = {}
            try:
                cfg = get_config()
            except Exception:
                pass
            mdl = model or cfg.get("model") or cfg.get("reasoning_model") or MODELS["main"]
            full_prompt = (
                f"Visual type: {hint}\n"
                f"Topic/text to visualise (Year 7-8 student):\n{prompt}\n"
                "Return ONLY the JSON spec."
            )
            ollama = OllamaService()
            raw = await asyncio.wait_for(
                ollama.complete(
                    mdl, full_prompt, system=_SPEC_SYSTEM,
                    max_tokens=max(250, min(max_tokens, 400)),
                    think=False, json_mode=True, context_window=4096,
                ),
                timeout=5.0,
            )
            data = json.loads(_strip_fences(raw))
            refined_spec = _sanitize_spec(data, prompt, hint)
            if len(refined_spec.get("nodes", [])) >= len(instant_spec.get("nodes", [])):
                return {"type": "napkin", "spec": refined_spec}
            return {"type": "napkin", "spec": instant_spec, "refined": False}
        except asyncio.TimeoutError:
            logger.info("Diagram LLM timed out (5s) — using heuristic")
            return {"type": "napkin", "spec": instant_spec, "fallback": True}
        except Exception as e:
            logger.info("Diagram LLM refinement skipped (%s) — using heuristic", e)
            return {"type": "napkin", "spec": instant_spec, "fallback": True}

    async def suggest(self, prompt: str) -> dict:
        """Return 3 Napkin-style visual options + a preview spec for the top pick."""
        prompt = (prompt or "").strip()[:1200]
        if not prompt:
            return {"error": "Prompt cannot be empty"}
        options = suggest_visuals(prompt)
        preview = _fallback_spec(prompt, options[0]["type"])
        return {"options": options, "preview": preview}


def _strip_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?", "", t).strip()
        t = re.sub(r"```$", "", t).strip()
    if not t.startswith("{"):
        m = re.search(r"\{.*\}", t, re.S)
        if m:
            t = m.group(0)
    return t
