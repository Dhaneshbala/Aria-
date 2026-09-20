"""Diagram service — Napkin AI-style visual generation for Study Buddy.

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
    "comparison", "pyramid", "venn", "pie", "bar", "geometry",
]

# ── Auto-detect: prompt keywords → best visual type (Napkin's auto-pick) ──
# NOTE: order matters — explicit types first. "venn" previously mapped to
# "comparison" so Venn was unreachable; bare words like "about"/"year"/"if "
# caused false positives ("Year 7 maths" → timeline). Use word boundaries.
_TYPE_HINTS = [
    ({"venn"}, "venn"),
    ({"pie", "percent", "percentage", "share of", "proportion", "distribution"}, "pie"),
    ({"bar chart", "bar graph", "histogram", "compare numbers", "statistics", "stats"}, "bar"),
    ({"timeline", "chronolog", "evolution", "century", "ww2", "world war"}, "timeline"),
    ({"cycle", "water cycle", "carbon cycle", "circulat", "loop", "recycl"}, "cycle"),
    ({"pyramid", "hierarchy", "levels of", "maslow", "food chain"}, "pyramid"),
    ({"flowchart", "flow chart", "workflow", "algorithm", "decision tree"}, "flowchart"),
    ({"process", "procedure", "how to", "method", "stage"}, "steps"),
    ({"mind map", "mindmap", "concept map", "branch diagram", "topic map", "branches"}, "mindmap"),
    ({"compare", "contrast", "versus", "pros and cons", "advantages and disadvantages"}, "comparison"),
    ({"angle", "vertex", "ray", "complement", "supplement", "straight line", "protract", "geometry", "parallel", "perpendicular", "triangle", "polygon", "quadrilateral"}, "geometry"),
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
        for k in keywords:
            # Multi-word / distinctive hints: substring is fine.
            # Short tokens (<=3 chars): require word boundaries to avoid
            # matching inside other words ("vs" in "versus" is ok, but
            # "pie" in "piece" is not).
            if len(k) <= 3:
                if re.search(rf"\b{re.escape(k)}\b", p):
                    return vtype
            elif k in p:
                return vtype
    if re.search(r"\bvs\b|versus|pros\s*.?\s*cons|advantages?\s*.{0,20}disadvantages?", p):
        return "comparison"
    if re.search(r"\b(flow|decision|if\s+.*\sthen)\b", p) and re.search(r"\b(then|else|step|next)\b", p):
        return "flowchart"
    if re.search(r"\b(1[.)]|first\b.{0,20}\bthen\b|\bthen\b.{0,20}\bnext\b|\bfinally\b)", p):
        return "steps"
    if re.search(r"\b(overlap|both|neither|shared|in common)\b", p):
        return "venn"
    if re.search(r"\b(history of|evolution of|timeline of)\b", p):
        return "timeline"
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


def _smart_title(prompt: str) -> str:
    """Title-case without mangling acronyms (WW2, DNA, NSW stay uppercase)."""
    first_line = prompt.strip().split("\n")[0][:60]
    cleaned = re.sub(
        r"^(please\s+)?(draw|generate|create|make|show|give|explain|visualise|visualize)\b[^a-zA-Z]*",
        "", first_line, flags=re.I,
    ).strip()
    cleaned = re.sub(r"^(me\s+)?(an?\s+)?(diagram|flowchart|chart|graph|map|figure|mind\s*map|timeline|poster)\s+(of|for|showing|that shows|about)?\s*", "", cleaned, flags=re.I).strip()
    cleaned = re.sub(r"\s+(please|thanks|thank you)[.!]?\s*$", "", cleaned, flags=re.I).strip()
    if not cleaned:
        return "Overview"
    words = cleaned.split()
    out = [w if (w.isupper() and len(w) <= 5) or re.fullmatch(r"[A-Za-z]*\d+[A-Za-z]*", w) else w.capitalize() for w in words]
    return _short(" ".join(out), 60) or "Overview"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        key = re.sub(r"\s+", " ", it.strip().lower())
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(it.strip())
    return out


def _split_items(prompt: str) -> list[str]:
    """Split prompt into candidate node labels: bullets → sentences → clauses."""
    lines = [l.strip(" •-*0123456789.)\t ") for l in re.split(r"[\n;]", prompt) if l.strip()]
    items: list[str] = []
    for ln in lines:
        parts = re.split(r"\s*[•·]\s*|\s{2,}", ln)
        items.extend(p.strip() for p in parts if p.strip())
    items = _dedupe(items)
    if len(items) < 3:
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", prompt) if len(s.strip()) > 8]
        items = _dedupe(items + sents)
    if len(items) < 3:
        clauses = [p.strip() for p in re.split(r",\s*|\s+and\s+", prompt) if len(p.strip()) > 3]
        items = _dedupe(items + clauses)
    # Last resort: split the longest item on " — "/" : " rather than filler text
    if len(items) < 3 and items:
        longest = max(items, key=len)
        for part in re.split(r"\s+[—–:]\s+|\s+—\s+", longest):
            if len(items) >= 3:
                break
            if len(part.strip()) > 3 and part.strip() not in items:
                items.append(part.strip())
    return [i[:70] for i in items if i][:6]


def _geometry_spec(prompt: str) -> dict:
    """Parse angle/geometry prompt into a Napkin geometry spec.

    Extracts ray names and angle values from the prompt.
    Examples:
      "angle AOB = 60°" → rays OA, OB with 60° between them
      "angles 60°, 45°, 75° on a straight line" → 4 rays with those angles
      "complementary angles 30° and 60°" → 3 rays with 30° and 60°
    """
    p = prompt.lower()
    title = _short(re.sub(
        r"^(please\s+)?(draw|show|give|make|create|explain)\s+(me\s+)?(an?\s+)?",
        "", prompt, flags=re.I
    ).strip().title() or "Angles", 60)

    # Extract angle values (e.g. 60°, 45 degrees, 30 deg)
    angle_vals = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*(?:°|deg|degree)", p)]
    # Also try bare numbers after "angle" or before "and"
    if len(angle_vals) < 2:
        angle_vals += [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\b", p)
                       if 1 <= float(x) <= 359 and float(x) not in angle_vals]

    # Extract ray/point names (e.g. OA, OB, PQR, XYZ)
    ray_names = re.findall(r"\b([A-Z]{2,3})\b", prompt)
    # Filter to likely ray names (2-3 uppercase letters, not common words)
    _skip = {"THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN", "HER", "WAS",
             "ONE", "OUR", "OUT", "HAS", "HIS", "HOW", "MAN", "NEW", "NOW", "OLD", "SEE",
             "WAY", "WHO", "DID", "GET", "LET", "SAY", "SHE", "TOO", "USE", "MATH", "THIS",
             "THAT", "WITH", "HAVE", "FROM", "THEY", "BEEN", "WILL", "WHAT", "WHEN", "YOUR",
             "YEAR", "MAKE", "LIKE", "LONG", "LOOK", "MANY", "MOST", "OVER", "SUCH", "TAKE",
             "THAN", "THEM", "THEN", "ALSO", "INTO", "JUST", "SHALL"}
    ray_names = [r for r in ray_names if r not in _skip and len(r) <= 3]

    # Determine vertex label
    vertex = "V"
    if ray_names:
        # Try to find a single-letter vertex (e.g. "angle PQR" → vertex Q)
        for name in ray_names:
            if len(name) == 3:
                vertex = name[1]
                break
        # Or use first point name as vertex
        if vertex == "V" and ray_names:
            vertex = ray_names[0][0] if len(ray_names[0]) >= 2 else ray_names[0]

    # Build ray labels
    if len(ray_names) >= 2 and all(len(r) >= 2 for r in ray_names[:4]):
        # Use the extracted names (e.g. OA, OB, OC)
        ray_labels = ray_names[:min(len(angle_vals) + 1, 5)]
    else:
        # Generate generic ray names from vertex
        ray_labels = [f"{vertex}{chr(65 + i)}" for i in range(max(len(angle_vals), 2))]

    # Ensure we have enough angle values
    while len(angle_vals) < len(ray_labels) - 1:
        # Fill with equal divisions of 180° or 360°
        is_straight = any(w in p for w in ["straight", "line", "180"])
        is_full = any(w in p for w in ["around", "point", "full", "360"])
        total = 180 if is_straight else (360 if is_full else 180)
        remaining = total - sum(angle_vals)
        n_missing = len(ray_labels) - 1 - len(angle_vals)
        if n_missing > 0 and remaining > 0:
            each = remaining / n_missing
            angle_vals.extend([round(each, 1)] * n_missing)
        else:
            angle_vals.append(30)

    # Build nodes (one per ray)
    nodes = []
    for i, label in enumerate(ray_labels[:6]):
        deg = angle_vals[i] if i < len(angle_vals) else 30
        nodes.append({
            "id": f"n{i+1}",
            "label": label,
            "angle": deg,
            "angleLabel": f"{int(deg) if deg == int(deg) else deg}°",
            "vertexLabel": vertex if i == 0 else "",
            "sub": "",
            "icon": "📐" if i == 0 else "",
        })

    return {"visual_type": "geometry", "title": title, "nodes": nodes, "edges": []}


def _fallback_spec(prompt: str, visual_type: str | None = None) -> dict:
    """Smart heuristic spec builder — works with zero model (offline-safe).

    Extracts meaningful nodes with sub-descriptions and context-aware icons.
    Never emits "Key point N" filler: short prompts fall back to splitting the
    prompt itself into clauses so every node carries real content.
    """
    vtype = visual_type or detect_visual_type(prompt)
    if vtype not in VISUAL_TYPES:
        vtype = "flowchart"

    # ── Geometry: parse rays + angles from prompt ──
    if vtype == "geometry":
        return _geometry_spec(prompt)

    items = _split_items(prompt)
    if not items:
        # Single short topic, e.g. "the water cycle" — use the topic as the
        # centre node plus generic-but-honest stage labels derived from it.
        topic = _smart_title(prompt)
        items = [topic, f"{topic} — how it starts", f"{topic} — key parts"]
    while len(items) < 3:
        # Duplicate-free padding from the prompt's own keywords, not filler.
        keywords = [w for w in re.findall(r"[A-Za-z]{4,}", prompt) if len(w) > 4]
        extra = keywords[len(items) % max(len(keywords), 1)] if keywords else prompt[:24]
        candidate = f"{extra.strip().capitalize()} — key idea"
        if candidate not in items:
            items.append(candidate)
        else:
            break
    title = _smart_title(prompt)
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
    if vtype in ("comparison", "venn", "pie", "bar", "pyramid", "mindmap", "timeline", "geometry"):
        return []
    return [{"from": ids[i], "to": ids[i + 1], "label": ""} for i in range(len(ids) - 1)]


def _sanitize_spec(data: dict, prompt: str, fallback_type: str) -> dict:
    """Clamp LLM output to the safe spec shape (Napkin: 3-8 short nodes)."""
    vtype = str(data.get("visual_type", fallback_type or "")).lower().strip()
    if vtype not in VISUAL_TYPES:
        vtype = detect_visual_type(prompt) if not fallback_type else fallback_type
    title = _short(str(data.get("title", "") or _smart_title(prompt)), 60) or "Overview"
    raw_nodes = data.get("nodes") or []
    nodes: list[dict] = []
    seen_labels: set[str] = set()
    for nd in raw_nodes[:8]:
        if isinstance(nd, str):
            nd = {"label": nd}
        if not isinstance(nd, dict):
            continue
        label = _short(str(nd.get("label", "")), 48)
        if not label:
            continue
        key = label.strip().lower()
        if key in seen_labels:
            continue
        seen_labels.add(key)
        icon_raw = str(nd.get("icon", "")).strip()
        # Grapheme-safe: keep up to ~8 chars so compound emoji (🏔️, ❤️)
        # aren't sliced mid-sequence; fall back to context icon.
        icon = icon_raw[:8] if icon_raw else _icon_for(label, prompt)
        nodes.append({
            "id": f"n{len(nodes)+1}",
            "label": label,
            "sub": _short(str(nd.get("sub", "")), 80),
            "icon": icon or _icon_for(label, prompt),
            # Preserve geometry-specific fields
            **({} if vtype != "geometry" else {
                "angle": nd.get("angle", 30),
                "angleLabel": str(nd.get("angleLabel", "")),
                "vertexLabel": str(nd.get("vertexLabel", "")),
            }),
        })
    if len(nodes) < (2 if vtype == "geometry" else 3):
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

    # Tiny in-memory cache: identical prompts skip the LLM round-trip.
    _refine_cache: dict[tuple[str, str], dict] = {}
    _REFINE_CACHE_MAX = 50
    LLM_TIMEOUT_SECS = 12.0

    async def generate(self, prompt: str, visual_type: str | None = None,
                       model: str | None = None, max_tokens: int = 500) -> dict:
        """Returns {"type": "napkin", "spec": {...}} — or {"error": ...}.

        Instant: returns heuristic spec immediately.
        Then: tries LLM refinement (12s budget — local gemma needs >5s).
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

        # Cache hit: skip the LLM entirely
        cache_key = (prompt[:300].lower(), hint)
        cached = self._refine_cache.get(cache_key)
        if cached and len(cached.get("nodes", [])) >= 3:
            return {"type": "napkin", "spec": cached, "cached": True}

        # Try LLM refinement with timeout (don't block the user long)
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
                    max_tokens=max(250, min(max_tokens, 700)),
                    think=False, json_mode=True, context_window=4096,
                ),
                timeout=self.LLM_TIMEOUT_SECS,
            )
            data = json.loads(_strip_fences(raw))
            refined_spec = _sanitize_spec(data, prompt, hint)
            if len(refined_spec.get("nodes", [])) >= len(instant_spec.get("nodes", [])):
                self._cache_refine(cache_key, refined_spec)
                return {"type": "napkin", "spec": refined_spec}
            return {"type": "napkin", "spec": instant_spec, "refined": False}
        except asyncio.TimeoutError:
            logger.info("Diagram LLM timed out (%.0fs) — using heuristic", self.LLM_TIMEOUT_SECS)
            return {"type": "napkin", "spec": instant_spec, "fallback": True}
        except Exception as e:
            logger.info("Diagram LLM refinement skipped (%s) — using heuristic", e)
            return {"type": "napkin", "spec": instant_spec, "fallback": True}

    @classmethod
    def _cache_refine(cls, key: tuple[str, str], spec: dict) -> None:
        if len(cls._refine_cache) >= cls._REFINE_CACHE_MAX:
            cls._refine_cache.pop(next(iter(cls._refine_cache)))
        cls._refine_cache[key] = spec

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
