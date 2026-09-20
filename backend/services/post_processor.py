"""
Post-processing utilities for Study Buddy responses.
──────────────────────────────────────────────
Extracted from orchestrator.py for maintainability.
Includes: extras generation, answer verification, math code exec,
self-check critic, follow-up suggestions.
"""

import asyncio
import json
import re
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

from services.ollama_service import OllamaService

ollama = OllamaService()

# Single source of truth — import from database
try:
    from models.database import MODELS
except Exception:
    MODELS = {
        "main": "gemma4:e4b-mlx",
        "embedding": "mxbai-embed-large",
    }


def _sse(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


# ── Extras generator ──────────────────────────────────────────────────────────

async def _generate_extras(
    intents: list[str], message: str, response: str,
    model: str, config: dict
) -> dict:
    """Generate structured extras (quiz, flashcards, methods) from the response."""
    extras = {}

    if "quiz" in intents or "exam_mode" in intents or "exam_sim" in intents:
        q = _parse_quiz(response)
        if q:
            if "exam_sim" in intents:
                extras["exam_sim"] = q
            else:
                extras["quiz"] = q

    if "flashcard" in intents:
        fc = _parse_flashcards(response)
        if fc:
            extras["flashcards"] = fc

    if "multiple_methods" in intents or "math" in intents:
        meth = _parse_methods(response)
        if meth:
            extras["methods"] = meth

    return extras


# ── Answer verification (2nd-model cross-check) ───────────────────────────────

async def _verify_answer(
    question: str, answer: str, evidence: list[dict], model: str | None = None
) -> dict | None:
    """Check the answer's facts against web evidence. Uses main gemma model
    (no second large model needed — reuses same model to save RAM)."""
    if model is None:
        try:
            from models.database import get_config as _get_cfg
            model = _get_cfg().get("model") or _get_cfg().get("reasoning_model") or MODELS["main"]
        except Exception:
            model = MODELS["main"]
    try:
        evidence_text = "\n".join(
            f"[{i+1}] {r['title']}: {r['snippet'][:250]}"
            for i, r in enumerate(evidence[:4])
        )
        prompt = (
            "You are a careful fact-checker for a student's AI tutor answer.\n\n"
            f"QUESTION: {question[:400]}\n\n"
            f"AI ANSWER:\n{answer[:2000]}\n\n"
            f"WEB EVIDENCE:\n{evidence_text}\n\n"
            "Compare the answer's factual claims against the web evidence.\n"
            "If every claim is supported or not contradicted by the evidence, set verified to true.\n"
            "If any claim is wrong or contradicts the evidence, set verified to false and explain briefly.\n"
            'Reply with ONLY JSON: {"verified": true or false, "notes": "brief explanation or empty string"}'
        )
        raw = await ollama.complete(
            model, prompt, "You are a strict but fair fact-checker."
        )
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            return {
                "verified": bool(data.get("verified")),
                "notes": str(data.get("notes", ""))[:300],
            }
    except Exception as e:
        logger.warning("Answer verification failed: %s", e)
    return None


# ── Code exec verifier for math (free, local python3 + sympy) ────────────────

async def _verify_math_via_code(question: str, answer: str) -> dict | None:
    """Verify numeric answers via local python (sympy if available). No API, no RAM cost."""
    try:
        import re as _re, subprocess as _sp, json as _js, tempfile as _tf, textwrap as _tw
        nums = _re.findall(r"[-+]?\d*\.?\d+", answer)
        if not nums:
            return None
        exprs = _re.findall(r"[\d\.\s\+\-\*\/\(\)\^]+", question)
        code = textwrap.dedent("""
            import re, math, ast, operator
            try:
                import sympy
                has_sympy=True
            except: has_sympy=False
            q = '''{q}'''
            a = '''{a}'''
            def _safe_eval(expr):
                _ops = {ast.Add: operator.add, ast.Sub: operator.sub,
                        ast.Mult: operator.mul, ast.Div: operator.truediv,
                        ast.USub: operator.neg, ast.UAdd: operator.pos}
                def _ev(n):
                    if isinstance(n, ast.Expression): return _ev(n.body)
                    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)): return n.value
                    if isinstance(n, ast.BinOp) and type(n.op) in _ops: return _ops[type(n.op)](_ev(n.left), _ev(n.right))
                    if isinstance(n, ast.UnaryOp) and type(n.op) in _ops: return _ops[type(n.op)](_ev(n.operand))
                    raise ValueError("bad expr")
                return _ev(ast.parse(expr, mode="eval"))
            try:
                m=re.search(r'(\\d+\\s*[\\+\\-\\*\\/]\\s*\\d+[\\s\\+\\-\\*\\/\\d\\(\\)]*)', q)
                if m:
                    expr=m.group(1).replace('^','**')
                    expected=_safe_eval(expr)
                    if str(int(expected)) not in a and str(expected) not in a:
                        print(f"MISMATCH:{{expected}}")
                    else:
                        print("OK")
                else:
                    print("SKIP")
            except Exception as e:
                print(f"ERR:{{e}}")
        """).format(q=question.replace("'", "\\'")[:500], a=answer.replace("'", "\\'")[:500])
        proc = _sp.run(["python3", "-c", code], capture_output=True, timeout=3, text=True)
        out = (proc.stdout or "").strip()
        if out.startswith("MISMATCH:"):
            val = out.split(":", 1)[1].strip()
            return {"verified": False, "notes": f"Code exec check: expected {val} not found in answer — possible arithmetic error"}
        if out.startswith("OK"):
            return {"verified": True, "notes": "Code exec verified arithmetic"}
    except Exception as e:
        logger.debug("Math code verify failed: %s", e)
    return None


async def _self_check_critic(question: str, answer: str, model: str | None = None) -> dict | None:
    """Self-check critic using same gemma4 — asks model to find its own errors. Free, just latency."""
    if model is None:
        try:
            from models.database import get_config as _get_cfg
            model = _get_cfg().get("model") or _get_cfg().get("reasoning_model") or MODELS["main"]
        except Exception:
            model = MODELS["main"]
    try:
        prompt = (
            f"QUESTION: {question[:400]}\n\nANSWER:\n{answer[:2000]}\n\n"
            "You are a strict critic. Check the answer for any math, factual, or logical errors.\n"
            "If correct, reply {\"ok\": true, \"notes\": \"\"}.\n"
            "If error found, reply {\"ok\": false, \"notes\": \"1-sentence error description\"}.\n"
            "ONLY JSON."
        )
        raw = await ollama.complete(model, prompt, "You are a careful critic.", max_tokens=80, think=False)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            if not data.get("ok"):
                return {"ok": False, "notes": str(data.get("notes", "Self-check flagged"))[:200]}
            return {"ok": True, "notes": ""}
    except Exception as e:
        logger.debug("Self-check critic failed: %s", e)
    return None


# ── Follow-up suggestions (NotebookLM-style) ──────────────────────────────────

async def _generate_suggestions(
    question: str, answer: str, model: str | None = None
) -> list[str] | None:
    """Generate 3 short follow-up questions. Reuses main gemma model."""
    if model is None:
        try:
            from models.database import get_config as _get_cfg
            model = _get_cfg().get("model") or _get_cfg().get("reasoning_model") or MODELS["main"]
        except Exception:
            model = MODELS["main"]
    try:
        prompt = (
            "A Year 7 student just asked a question and received this answer.\n\n"
            f"QUESTION: {question[:300]}\n\n"
            f"ANSWER:\n{answer[:1200]}\n\n"
            "Suggest exactly 3 short follow-up questions the student would naturally ask next.\n"
            "They should dig deeper into the topic and be useful for studying.\n"
            "Number them 1., 2., 3. Each under 12 words. One per line."
        )
        raw = await ollama.complete(
            model, prompt, "You suggest useful follow-up study questions."
        )
        qs = []
        for line in raw.split("\n"):
            line = line.strip()
            if not line or "follow-up question" in line.lower() or line.lower().startswith("here are"):
                continue
            q = re.sub(r"^\d+[.)]\s*", "", line).strip()
            if 3 < len(q) < 120:
                qs.append(q)
        return qs[:3] or None
    except Exception as e:
        logger.warning("Suggestion generation failed: %s", e)
    return None


# ── Parsers ───────────────────────────────────────────────────────────────────
# Canonical implementations live in StudyService (study_service.py).
# Imported here so quiz/flashcard parsing never drifts out of sync.
from services.study_service import StudyService as _StudyService
_parser_svc = _StudyService()
_parse_quiz = _parser_svc._parse_quiz
_parse_flashcards = _parser_svc._parse_flashcards


def _parse_methods(text: str) -> list[dict] | None:
    """Parse 2-3 methods from response: Method 1: ... Method 2: ..."""
    blocks = re.split(r"\bMethod\s*(\d+)\s*[:\-]\s*", text, flags=re.I)
    # blocks[0] is preface, then id, content, id, content ...
    if len(blocks) < 3:
        return None
    methods = []
    for i in range(1, len(blocks) - 1, 2):
        try:
            mid = int(blocks[i])
        except Exception:
            continue
        content = blocks[i + 1].strip().split("\n\n")[0].strip()
        # also split comparison table if present
        content = re.split(r"\n\| Method", content)[0].strip()
        if content and len(content) > 10:
            methods.append({"method": mid, "content": content[:1200]})
    return methods[:3] if methods else None
