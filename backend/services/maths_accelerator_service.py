"""
Maths Accelerator — selective-level maths for North Sydney Boys standard.

Tiers:
  • foundation — Stage 5.2 consolidation (speed + accuracy)
  • selective  — Stage 5.3 exam style (multi-step, NESA verbs, traps)
  • extension  — early Extension 1 bridge (proof-flavoured, harder)

Each generated question carries:
  question, marks, solution_steps[], trap, shortcut, answer

Works offline: if the LLM is unavailable, deterministic fallback sets
are returned so the UI + tests never break.
"""
import json
import logging
import os
import re
import threading
import tempfile
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("ARIA_DATA_DIR", Path.home() / ".aria_data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
MASTERY_FILE = DATA_DIR / "maths_mastery.json"

_LOCK = threading.RLock()


def _load_mastery() -> dict:
    with _LOCK:
        if MASTERY_FILE.exists():
            try:
                data = json.loads(MASTERY_FILE.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
        return {}


def _save_mastery(data: dict) -> None:
    with _LOCK:
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(DATA_DIR), prefix=".maths_mastery.tmp."
        )
        try:
            with open(tmp_fd, "w", encoding="utf-8") as f:
                f.write(json.dumps(data, indent=2, ensure_ascii=False))
                f.flush()
                os.fsync(f.fileno())
            Path(tmp_path).replace(MASTERY_FILE)
        finally:
            p = Path(tmp_path)
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass


TIERS = {
    "foundation": {
        "name": "Foundation",
        "desc": "Stage 5.2 — speed + accuracy, single method",
        "marks_hint": "1-2 marks each",
    },
    "selective": {
        "name": "Selective",
        "desc": "Stage 5.3 exam style — multi-step + traps",
        "marks_hint": "2-4 marks each",
    },
    "extension": {
        "name": "Extension",
        "desc": "Early Ext 1 bridge — prove it, generalise it",
        "marks_hint": "3-5 marks each",
    },
}

# NSW Stage 4/5.3 topic map — what a selective student actually faces.
MATHS_TOPICS = [
    {
        "id": "quadratics",
        "name": "Quadratics",
        "stage": "Stage 5.3",
        "outcomes": ["MA5-7NA", "MA5-8NA"],
        "prereq": "Expanding & factorising",
        "focus": "Factorise, complete square, quadratic formula, discriminant, worded max/min",
    },
    {
        "id": "surds_indices",
        "name": "Surds & Indices",
        "stage": "Stage 5.3",
        "outcomes": ["MA5-5NA", "MA5-6NA"],
        "prereq": "Index laws (integer)",
        "focus": "Simplify surds, rationalise denominator, fractional/negative indices",
    },
    {
        "id": "simultaneous",
        "name": "Simultaneous Equations",
        "stage": "Stage 5.3",
        "outcomes": ["MA5-7NA"],
        "prereq": "Linear graphs",
        "focus": "Elimination/substitution, linear+non-linear pairs, worded problems",
    },
    {
        "id": "inequalities",
        "name": "Inequalities & Regions",
        "stage": "Stage 5.3",
        "outcomes": ["MA5-8NA"],
        "prereq": "Solving linear equations",
        "focus": "Solve + graph, compound regions, sign-flip traps",
    },
    {
        "id": "functions_graphs",
        "name": "Functions & Graphs",
        "stage": "Stage 5.3",
        "outcomes": ["MA5-9NA"],
        "prereq": "Linear + quadratic graphs",
        "focus": "Parabola shifts, intercepts, axis of symmetry, sketch from equation",
    },
    {
        "id": "trig_advanced",
        "name": "Advanced Trigonometry",
        "stage": "Stage 5.3",
        "outcomes": ["MA5-6MG"],
        "prereq": "SOHCAHTOA, Pythagoras",
        "focus": "Exact values, sine/cosine rule, bearings, 3D-ish worded drops",
    },
    {
        "id": "polynomials_intro",
        "name": "Polynomials (Intro)",
        "stage": "Ext bridge",
        "outcomes": ["MA-S1"],
        "prereq": "Quadratics factorised",
        "focus": "Cubic factor by grouping, remainder/factor theorem taste",
    },
    {
        "id": "logarithms_intro",
        "name": "Logarithms (Intro)",
        "stage": "Ext bridge",
        "outcomes": ["MA-S2"],
        "prereq": "Indices fluent",
        "focus": "Log = undo exponent, basic laws, solve 2^x = 24 style",
    },
    {
        "id": "circle_geometry",
        "name": "Circle Geometry Proofs",
        "stage": "Stage 5.3",
        "outcomes": ["MA5-3MG"],
        "prereq": "Angle facts",
        "focus": "Angle in semicircle, cyclic quads, give-a-reason proofs",
    },
    {
        "id": "probability_advanced",
        "name": "Advanced Probability",
        "stage": "Stage 5.3",
        "outcomes": ["MA5-4SP"],
        "prereq": "Tree diagrams",
        "focus": "With/without replacement, Venn + conditional taste, expected value",
    },
]


def list_topics() -> list[dict]:
    return MATHS_TOPICS


def get_topic(topic_id: str) -> dict | None:
    return next((t for t in MATHS_TOPICS if t["id"] == topic_id), None)


# ── Offline fallback bank (deterministic, exam-sharp) ────────────────────────

_FALLBACK: dict[str, dict[str, list[dict]]] = {
    "quadratics": {
        "foundation": [
            {
                "question": "Factorise fully: $x^2 + 7x + 12$",
                "marks": 2,
                "solution_steps": [
                    "Find two numbers that multiply to 12 and add to 7 → 3 and 4",
                    "Write as $(x+3)(x+4)$",
                    "Quick check: expand to confirm $x^2+7x+12$",
                ],
                "trap": "Sign trap: +12 with +7 means BOTH signs positive — not (x-3)(x-4).",
                "shortcut": "For $x^2+bx+c$, list factor pairs of c first, then match b.",
                "answer": "$(x+3)(x+4)$",
            },
            {
                "question": "Solve: $x^2 - 5x + 6 = 0$",
                "marks": 2,
                "solution_steps": [
                    "Factorise: find numbers multiplying to 6, adding to -5 → -2, -3",
                    "$(x-2)(x-3) = 0$",
                    "$x = 2$ or $x = 3$",
                ],
                "trap": "Don't divide by x — factorise, don't cancel roots away.",
                "shortcut": "Sum/product check: roots sum to 5, product 6.",
                "answer": "$x=2$ or $x=3$",
            },
        ],
        "selective": [
            {
                "question": "The product of two consecutive positive integers is 132. Form a quadratic equation and find the integers. [3 marks]",
                "marks": 3,
                "solution_steps": [
                    "Let integers be $n$ and $n+1$: $n(n+1) = 132$",
                    "$n^2 + n - 132 = 0$ → factorise: $(n+12)(n-11) = 0$",
                    "$n = 11$ (positive) → integers 11 and 12. Check: $11 \\times 12 = 132$ ✓",
                ],
                "trap": "Reject $n=-12$ explicitly — question says positive. Selective markers dock for unexplained rejection.",
                "shortcut": "$\\sqrt{132} \\approx 11.5$ — answer sits either side, saves trial time.",
                "answer": "11 and 12",
            },
            {
                "question": "For $kx^2 - 4x + 1 = 0$ to have no real roots, find the range of $k$. Justify with the discriminant. [3 marks]",
                "marks": 3,
                "solution_steps": [
                    "Discriminant $\\Delta = b^2-4ac = 16 - 4k$",
                    "No real roots ⟺ $\\Delta < 0$: $16 - 4k < 0$",
                    "$k > 4$. (If $k=0$ it's linear — state assumption $k \\ne 0$.)",
                ],
                "trap": "Forgetting $k \\ne 0$: at $k=0$ it's not even quadratic. Mention it for full marks.",
                "shortcut": "Memorise: $\\Delta>0$ two roots, $=0$ one, $<0$ none — write the chain every time.",
                "answer": "$k > 4$",
            },
        ],
        "extension": [
            {
                "question": "Prove that $x^2 + 4x + 7 > 0$ for all real $x$, and find its minimum value. [4 marks]",
                "marks": 4,
                "solution_steps": [
                    "Complete the square: $x^2+4x+7 = (x+2)^2 + 3$",
                    "Since $(x+2)^2 \\ge 0$, expression $\\ge 3 > 0$ for all real $x$ ∎",
                    "Minimum 3 at $x = -2$.",
                ],
                "trap": "Discriminant-only argument ($\\Delta<0$) proves positivity but not the minimum — complete the square for both.",
                "shortcut": "Vertex form $a(x-h)^2+k$ reads the minimum straight off: $(-2, 3)$.",
                "answer": "Min 3 at $x=-2$, always positive",
            },
        ],
    },
}

_GENERIC_FALLBACK = {
    "foundation": [
        {
            "question": "State the key definition for this topic in one sentence, then give one worked example.",
            "marks": 2,
            "solution_steps": ["Define the core idea", "Work one basic example with every step", "Check by substitution"],
            "trap": "Rushing step 1 — selective markers award method marks for setup lines.",
            "shortcut": "Write the formula first, then substitute — never do mental substitution in exams.",
            "answer": "See worked example",
        },
    ],
    "selective": [
        {
            "question": "Exam-style multi-step problem: set up equations from words, solve, then verify against the question conditions. [3 marks]",
            "marks": 3,
            "solution_steps": ["Define variables + write equations", "Solve with full working", "Verify + reject extraneous answers with a reason"],
            "trap": "Unrejected extraneous answer = lost mark. Always state why you discard.",
            "shortcut": "Estimate the answer size first — catches algebra slips early.",
            "answer": "See full solution",
        },
    ],
    "extension": [
        {
            "question": "Prove-or-generalise task: solve the specific case, then state and justify the general rule. [4 marks]",
            "marks": 4,
            "solution_steps": ["Solve the numeric case", "Spot the pattern / conjecture", "Prove it (factorise, complete square, or contradiction)"],
            "trap": "Example ≠ proof. One verified case earns at most 1 of 4 without general reasoning.",
            "shortcut": "Try small numbers to guess the pattern, then prove backwards from the answer.",
            "answer": "See proof",
        },
    ],
}


def _fallback_set(topic_id: str, tier: str, count: int) -> list[dict]:
    bank = _FALLBACK.get(topic_id, {}).get(tier) or _GENERIC_FALLBACK.get(tier, [])
    out = []
    i = 0
    while len(out) < count and bank:
        base = dict(bank[i % len(bank)])
        q = dict(base)
        if len(out) > 0:
            q = dict(q)
            q["question"] = f"(v{len(out)+1}) {q['question']}"
        out.append(q)
        i += 1
    return out[:count]


# ── LLM generation ───────────────────────────────────────────────────────────

_TIER_STYLE = {
    "foundation": "Stage 5.2 consolidation: single-method, fluency, 1-2 marks. NSW syllabus, 13-14 y.o. reading level.",
    "selective": "Stage 5.3 selective-exam style: multi-step, NESA verbs (solve, justify, show), one deliberate trap per question, 2-4 marks with [n marks] shown.",
    "extension": "Early Extension 1 bridge: prove/generalise/derive, one question should need insight beyond routine method, 3-5 marks.",
}


def _build_prompt(topic: dict, tier: str, count: int) -> str:
    style = _TIER_STYLE.get(tier, _TIER_STYLE["selective"])
    return (
        f"You are a senior NSW selective-school maths teacher writing a practice set.\n"
        f"TOPIC: {topic['name']} ({topic['stage']}). Focus: {topic['focus']}\n"
        f"TIER: {tier} — {style}\n"
        f"COUNT: {count} questions.\n\n"
        f"STRICT FORMAT per question (repeat exactly):\n"
        f"Q[N]: <question text, use LaTeX $...$ for maths, end with [n marks]>\n"
        f"Marks: <integer>\n"
        f"Solution: <step 1> | <step 2> | <step 3>\n"
        f"Trap: <one exam trap + how to avoid it>\n"
        f"Shortcut: <fast selective-school method or check>\n"
        f"Answer: <final boxed answer>\n\n"
        f"RULES: Australian curriculum. Every step shown, no skipped algebra. "
        f"Vary numbers so answers differ. No citations, no URLs."
    )


def _parse_set(text: str) -> list[dict]:
    blocks = re.split(r"(?m)^Q\s*\[?\d+\]?\s*[:\.\)]\s*", text)
    out = []
    for block in blocks[1:]:
        lines = [ln.strip() for ln in block.strip().split("\n") if ln.strip()]
        if not lines:
            continue
        q: dict = {
            "question": lines[0],
            "marks": 2,
            "solution_steps": [],
            "trap": "",
            "shortcut": "",
            "answer": "",
        }
        for line in lines[1:]:
            m = re.match(r"(?i)^marks\s*[:\-]\s*\[?(\d+)\]?", line)
            if m:
                try:
                    q["marks"] = max(1, min(6, int(m.group(1))))
                except Exception:
                    pass
                continue
            m = re.match(r"(?i)^solution\s*[:\-]\s*(.+)", line)
            if m:
                q["solution_steps"] = [s.strip() for s in m.group(1).split("|") if s.strip()][:8]
                continue
            m = re.match(r"(?i)^trap\s*[:\-]\s*(.+)", line)
            if m:
                q["trap"] = m.group(1).strip()
                continue
            m = re.match(r"(?i)^shortcut\s*[:\-]\s*(.+)", line)
            if m:
                q["shortcut"] = m.group(1).strip()
                continue
            m = re.match(r"(?i)^answer\s*[:\-]\s*(.+)", line)
            if m:
                q["answer"] = m.group(1).strip()
                continue
        if len(q["question"]) >= 8 and q["answer"]:
            if not q["solution_steps"]:
                q["solution_steps"] = ["See answer — show full working for method marks."]
            out.append(q)
    return out


async def generate_set(
    topic_id: str,
    tier: str = "selective",
    count: int = 5,
    model: str | None = None,
) -> dict:
    topic = get_topic(topic_id)
    if not topic:
        raise ValueError(f"Unknown topic: {topic_id}")
    tier = tier if tier in TIERS else "selective"
    count = max(1, min(10, int(count or 5)))

    if model is None:
        try:
            from models.database import get_config, MODELS

            cfg = get_config()
            model = cfg.get("model") or cfg.get("reasoning_model") or MODELS["main"]
        except Exception:
            model = "gemma4:e4b-mlx"

    try:
        from services.ollama_service import OllamaService

        raw = await OllamaService().complete(
            model,
            _build_prompt(topic, tier, count),
            system="You are a senior NSW selective-school maths teacher. Output ONLY the formatted questions.",
            think=False,
            context_window=2048,
            max_tokens=2200,
            timeout=120,
        )
        parsed = _parse_set(raw or "")
        if len(parsed) >= max(1, count // 2):
            # Top up with fallback variants if LLM short-delivered
            while len(parsed) < count:
                parsed.extend(_fallback_set(topic_id, tier, 1))
            return {
                "topic_id": topic_id,
                "topic": topic["name"],
                "tier": tier,
                "questions": parsed[:count],
                "source": "llm",
            }
        logger.warning("Maths LLM under-delivered (%d), using fallback", len(parsed))
    except Exception as e:
        logger.warning("Maths generation failed, fallback: %s", e)

    return {
        "topic_id": topic_id,
        "topic": topic["name"],
        "tier": tier,
        "questions": _fallback_set(topic_id, tier, count),
        "source": "fallback",
    }


# ── Mastery ──────────────────────────────────────────────────────────────────

def record_attempt(
    topic_id: str,
    tier: str,
    correct: int,
    total: int,
    mistakes: list[dict] | None = None,
) -> dict:
    data = _load_mastery()
    entry = data.get(topic_id, {"attempts": 0, "correct": 0, "by_tier": {}, "mistakes": []})
    total = max(1, int(total or 1))
    correct = max(0, min(total, int(correct or 0)))
    entry["attempts"] = int(entry.get("attempts", 0)) + total
    entry["correct"] = int(entry.get("correct", 0)) + correct
    by_tier = entry.setdefault("by_tier", {})
    t = by_tier.get(tier, {"attempts": 0, "correct": 0})
    t["attempts"] = int(t.get("attempts", 0)) + total
    t["correct"] = int(t.get("correct", 0)) + correct
    by_tier[tier] = t
    if mistakes:
        ml = entry.setdefault("mistakes", [])
        for m in mistakes[:10]:
            ml.append({**m, "ts": datetime.now(timezone.utc).isoformat()})
        entry["mistakes"] = ml[-30:]
    entry["accuracy"] = round(entry["correct"] / entry["attempts"] * 100) if entry["attempts"] else 0
    data[topic_id] = entry
    _save_mastery(data)
    return {"topic_id": topic_id, **entry}


def get_mastery() -> dict:
    data = _load_mastery()
    out = {}
    for t in MATHS_TOPICS:
        e = data.get(t["id"], {"attempts": 0, "correct": 0, "accuracy": 0, "by_tier": {}})
        out[t["id"]] = {
            "name": t["name"],
            "stage": t["stage"],
            "attempts": e.get("attempts", 0),
            "correct": e.get("correct", 0),
            "accuracy": e.get("accuracy", 0),
            "by_tier": e.get("by_tier", {}),
        }
    return out
