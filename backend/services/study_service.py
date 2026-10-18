"""Study service — generates quizzes, flashcards, mind maps."""

import asyncio
import logging
import os
import re
from difflib import SequenceMatcher

from services.ollama_service import OllamaService

logger = logging.getLogger(__name__)


def _fuzz_ratio(a: str, b: str) -> float:
    """Similarity ratio (0..1) between two short strings — used to match
    semantically-inflected tokens (evaporation vs evaporates)."""
    return SequenceMatcher(None, a, b).ratio()


def _safe_arith_eval(expr: str):
    """AST-based safe evaluator for simple arithmetic. Raises on unsafe input."""
    import ast as _ast
    import operator as _op

    if len(expr) > 100:
        raise ValueError("expression too long")
    tree = _ast.parse(expr, mode="eval")
    _allowed = (
        _ast.Expression,
        _ast.BinOp,
        _ast.UnaryOp,
        _ast.Constant,
        _ast.Add,
        _ast.Sub,
        _ast.Mult,
        _ast.Div,
        _ast.Mod,
        _ast.Pow,
        _ast.UAdd,
        _ast.USub,
        _ast.Load,
    )
    for node in _ast.walk(tree):
        if not isinstance(node, _allowed):
            raise ValueError(f"disallowed: {type(node).__name__}")  # noqa: TRY004 — ValueError is the contract surfaced to the student for invalid formulas
        if isinstance(node, _ast.Constant) and not isinstance(node.value, (int, float)):
            raise ValueError("only numbers allowed")  # noqa: TRY004
    # Guard pow explosion: base abs <= 1e6, exponent <= 100
    for node in _ast.walk(tree):
        import ast as _a2

        if isinstance(node, _a2.BinOp) and isinstance(node.op, _a2.Pow):
            try:
                exp = _a2.literal_eval(node.right)
                base = _a2.literal_eval(node.left)
                if abs(float(exp)) > 100 or abs(float(base)) > 1e6:
                    raise ValueError("pow out of bounds")
            except ValueError:
                raise
            except Exception:
                raise ValueError("non-constant pow")
    _ops = {
        _ast.Add: _op.add,
        _ast.Sub: _op.sub,
        _ast.Mult: _op.mul,
        _ast.Div: _op.truediv,
        _ast.Mod: _op.mod,
        _ast.Pow: _op.pow,
        _ast.UAdd: _op.pos,
        _ast.USub: _op.neg,
    }

    def _ev(n):
        import ast as _a3

        if isinstance(n, _a3.Expression):
            return _ev(n.body)
        if isinstance(n, _a3.Constant):
            return n.value
        if isinstance(n, _a3.BinOp):
            return _ops[type(n.op)](_ev(n.left), _ev(n.right))
        if isinstance(n, _a3.UnaryOp):
            return _ops[type(n.op)](_ev(n.operand))
        raise ValueError("disallowed node")

    return _ev(tree)


def _solve_simple_math(question: str, options: list[str]) -> str:
    """Directly solve simple arithmetic (45+23, '45 and 23 more total') -> letter.
    Returns 'A'-'D' or '' if not a simple math question or can't solve."""
    q_lower = question.lower()
    # Extract numbers from question (integers)
    q_nums = list(map(int, re.findall(r"\b\d+\b", question)))
    if len(q_nums) < 2 or len(options) < 2:
        return ""
    expected = None
    # Direct operator in question — any + - * / (not just +)
    if re.search(r"\d+\s*[\+\-\*/]\s*\d+", question):
        try:
            expr = re.findall(
                r"\d+\s*[\+\-\*/]\s*\d+(?:\s*[\+\-\*/]\s*\d+)*", question
            )[0]
            expected = _safe_arith_eval(expr)
            expected = (
                int(expected) if float(expected).is_integer() else float(expected)
            )
        except Exception:
            pass
    elif any(
        k in q_lower
        for k in (
            "more",
            "total",
            "altogether",
            "sum",
            "in all",
            "plus",
            "add",
            "combined",
            "together",
        )
    ):
        try:
            expected = q_nums[0] + q_nums[1]
        except Exception:
            pass
    elif any(
        k in q_lower
        for k in ("left", "fewer", "difference", "remain", "remaining", "less")
    ) or re.search(r"\b(minus|subtract|take away)\b", q_lower):
        try:
            expected = q_nums[0] - q_nums[1]
        except Exception:
            pass
    elif (
        re.search(r"\b(times|multiply|multiplied|product|of)\b", q_lower)
        and len(q_nums) >= 2
    ):
        try:
            expected = q_nums[0] * q_nums[1]
        except Exception:
            pass
    elif (
        re.search(r"\b(divide|divided|quotient|per|ratio)\b", q_lower)
        and len(q_nums) >= 2
        and q_nums[1] != 0
    ):
        try:
            expected = q_nums[0] / q_nums[1]
            expected = int(expected) if float(expected).is_integer() else expected
        except Exception:
            pass

    if expected is None:
        return _solve_equation_with_sympy(question, options)

    # Map expected numeric string to option letter (support float like 2.5)
    for i, opt in enumerate(options):
        m = re.search(r"-?\d+(?:\.\d+)?", opt.replace(",", ""))
        if m:
            try:
                if float(m.group()) == float(expected):
                    return chr(65 + i)
            except Exception:
                continue
    return ""


def _math_run_before(text: str, eq_pos: int) -> str:
    """Maximal math expression immediately before '=' (scans backwards).

    Stops at English words: a lowercase letter counts as part of a word when
    its neighbour inside the text is also a letter (e.g. 'when', 'If'), while
    variable letters bounded by digits/operators/space ('2x + 5') are kept.
    """
    allowed = set("0123456789.+-*/^()")
    out: list[str] = []
    i = eq_pos - 1
    while i >= 0:
        c = text[i]
        if c == " ":
            out.append(c)
            i -= 1
            continue
        if c in allowed:
            out.append(c)
            i -= 1
            continue
        if c.isalpha() and c.islower():
            nxt = text[i + 1] if i + 1 < len(text) else ""
            prev = text[i - 1] if i >= 1 else ""
            # Part of a multi-letter word ('when', 'If', 'solve') — stop.
            if nxt.isalpha() or prev.isalpha():
                break
            out.append(c)
            i -= 1
            continue
        break
    repaired = "".join(reversed(out)).strip()
    # Trim any leading space-isolated variable that lost its operator
    # (e.g. 'x 2x + 5' → keep '2x + 5' only when a word boundary occurred).
    return repaired


def _math_run_after(text: str, eq_pos: int) -> str:
    """Maximal math expression immediately after '=' (scans forwards)."""
    allowed = set("0123456789.+-*/^()")
    out: list[str] = []
    i = eq_pos + 1
    while i < len(text):
        c = text[i]
        if c == " ":
            # Only keep spaces sandwiched between math characters.
            if (
                out
                and i + 1 < len(text)
                and (text[i + 1] in allowed or text[i + 1].isalpha())
            ):
                out.append(c)
            i += 1
            continue
        if c in allowed:
            out.append(c)
            i += 1
            continue
        if c.isalpha() and c.islower():
            nxt = text[i + 1] if i + 1 < len(text) else ""
            # Part of a word ('what', 'more') — stop; single trailing var is ok.
            if nxt.isalpha():
                break
            out.append(c)
            i += 1
            continue
        break
    return "".join(out).strip()


def _solve_equation_with_sympy(question: str, options: list[str]) -> str:
    """Deterministic solve for algebraic questions the arithmetic evaluator
    cannot head: linear equations ("Solve for x: 2x + 5 = 13") and percent
    questions ("What is 15% of 80").

    Uses sympy (optional dependency) for symbolic solving; percent questions
    fall back to plain float math. Never raises — returns "" when no reliable
    answer can be computed, so verification behaves as if there were no
    math signal. This prevents LLM-only maths answers where possible
    (competitors like Intu AI run a full CAS; this is a pragmatic subset).
    """
    if not question or len(options) < 2:
        return ""

    try:
        # Percent: "15% of 80"
        pct = re.search(r"(\d+(?:\.\d+)?)\s*%", question)
        of = re.search(r"%\s*of\s*(\d+(?:\.\d+)?)", question)
        if pct and of:
            expected = float(pct.group(1)) / 100.0 * float(of.group(1))
            return _match_number_to_options(expected, options)
        # Simple percent-of without the word 'of': "15% off 80"? ambiguous — skip.
    except Exception:
        pass

    # Symbolic equations need sympy; bail out quickly otherwise.
    try:
        import sympy  # type: ignore[import-untyped]
        from sympy.parsing.sympy_parser import (
            convert_xor,
            implicit_multiplication_application,
            parse_expr,
            standard_transformations,
        )
    except Exception:
        return ""

    # Pull the equation-looking substring out of the question text.
    eq_match = re.search(
        r"[0-9a-zA-Z.x⁄+\-*/()^=\s]{2,80}=[0-9a-zA-Z.+\-*/()^x\s]{1,60}", question
    )
    if not eq_match:
        return ""
    matched = eq_match.group(0)
    eq_pos = matched.index("=")
    left = _math_run_before(matched, eq_pos)
    right = _math_run_after(matched, eq_pos)
    if not left or not right:
        return ""
    equation_text = f"{left}={right}"

    # Single-letter variables: standalone ("x") or as a coefficient ("2x",
    # "3y"). coefficient-letter patterns have no \b on the letter, so we use
    # a lookaround for math-context neighbours instead.
    vars_in_eq = sorted(
        set(
            re.findall(
                r"\b[a-z]\b|(?<=[0-9.\s()+\-*/^])[a-z](?=[0-9.\s()+\-*/^=]|$)",
                equation_text,
            )
        )
    )
    if not vars_in_eq:
        return ""
    if len(vars_in_eq) > 1:
        return ""  # simultaneous equations are out of scope — don't guess

    var = sympy.Symbol(vars_in_eq[0])
    try:
        transformations = standard_transformations + (
            implicit_multiplication_application,
            convert_xor,
        )
        side = re.split(r"=", equation_text)
        if len(side) != 2:
            return ""
        lhs = parse_expr(side[0], transformations=transformations)
        rhs = parse_expr(side[1], transformations=transformations)
        solutions = sympy.solve(sympy.Eq(lhs, rhs), var, dict=False)
        if not solutions:
            return ""
        # A polynomial may have several roots (e.g. x²-16=0 → ±4). Only accept
        # a letter when EXACTLY ONE root matches the options — otherwise the
        # "verification" would be guessing.
        matched_letters = []
        for sol in solutions:
            val = sympy.N(sol, 12)
            if not val.is_number:
                continue
            letter = _match_number_to_options(float(val), options)
            if letter and letter not in matched_letters:
                matched_letters.append(letter)
        if len(matched_letters) == 1:
            return matched_letters[0]
        return ""
    except Exception:
        return ""


def _match_number_to_options(expected: float, options: list[str]) -> str:
    """Match a computed number to the first option whose first number equals it."""
    for i, opt in enumerate(options):
        m = re.search(r"-?\d+(?:\.\d+)?", opt.replace(",", ""))
        if m:
            try:
                if abs(float(m.group()) - expected) < 1e-6:
                    return chr(65 + i)
            except Exception:
                continue
    return ""


def _dedupe_questions(questions: list[dict], threshold: float = 0.80) -> list[dict]:
    """Drop duplicate quizzes questions.

    LLMs frequently emit near-identical questions in one batch (same stem
    re-worded, or verbatim repeats). Duplicate questions make quizzes feel
    broken and double-count mistakes in profile stats.

    Exact normalised matches always collapse; near-duplicates collapse above
    the similarity threshold. Order is preserved (first occurrence wins).
    """
    kept: list[dict] = []

    def _norm(s: str) -> str:
        return re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).strip()

    exact_seen: set[str] = set()
    kept_norms: list[str] = []
    for q in questions:
        norm = _norm(q.get("question", ""))
        if not norm:
            kept.append(q)  # keep malformed rows; parsers/tests rely on passthrough
            continue
        if norm in exact_seen:
            continue
        if any(
            SequenceMatcher(None, norm, prev).ratio() >= threshold
            for prev in kept_norms
        ):
            continue
        exact_seen.add(norm)
        kept_norms.append(norm)
        kept.append(q)
    if len(kept) < len(questions):
        logger.info(
            "Quiz dedupe: removed %d duplicate question(s)", len(questions) - len(kept)
        )
    return kept


ollama = OllamaService()

# Import central routing
try:
    from models.database import MODELS
except Exception:
    MODELS = {
        "main": "gemma3:12b",
        "embedding": "nomic-embed-text",
    }


def _default_model() -> str:
    try:
        from models.database import get_config

        return (
            get_config().get("model")
            or get_config().get("reasoning_model")
            or MODELS["main"]
        )
    except Exception:
        return MODELS["main"]


QUIZ_LEVELS = {
    "easy": "simple recall and basic understanding, single-step problems",
    "medium": "application and some analysis, two-step problems",
    "hard": "deep analysis, multi-step reasoning, challenging edge cases",
    "exam": "timed exam simulation — comprehensive coverage, varied question types, mark-scheme style answers",
    "olympiad": "competition-level (APSMO/AMC/IMO style), highly challenging, creative lateral thinking, proof-based",
}


def _grade_lock_line() -> str:
    """Grade-lock snippet for every study generator prompt.

    Reads the student's Settings grade so quizzes, flashcards, notes, etc.
    are always built ONLY for their year — never younger or older content.
    """
    try:
        from models.database import get_config, get_student_grade
        from services.nsw_curriculum_service import NSW_STAGES, NSWCurriculumService

        grade = get_student_grade(get_config())
        stage = NSWCurriculumService().get_stage_for_grade(grade) or ""
        stage_name = NSW_STAGES.get(stage, {}).get("name", stage) if stage else ""
        stage_txt = f" ({stage_name})" if stage_name else ""
        return (
            f"GRADE LOCK: The student is in {grade}{stage_txt}, NSW syllabus. "
            f"Generate ONLY {grade}-level content using {grade} outcomes. "
            f"Never include content from younger years or older years."
        )
    except Exception:
        return (
            "GRADE LOCK: Generate only age-appropriate Year 7 level content. "
            "Never include content from younger years or older years."
        )


class StudyService:
    @staticmethod
    def _build_quiz_prompt(topic: str, level: str, num_questions: int) -> str:
        """Shared prompt builder so generate_quiz and generate_quiz_stream
        ask for byte-identical formats (same parser downstream)."""
        # Typo correction for common biology terms (e.g. organelles)
        topic = re.sub(r"orangell", "organell", topic, flags=re.IGNORECASE)
        topic = re.sub(r"mitocondria", "mitochondria", topic, flags=re.IGNORECASE)
        topic = re.sub(r"ribosom", "ribosome", topic, flags=re.IGNORECASE)

        level_desc = QUIZ_LEVELS.get(level, QUIZ_LEVELS["medium"])
        return (
            f"Generate {num_questions} multiple-choice quiz questions SPECIFICALLY about: {topic}\n"
            f"CRITICAL: Every question MUST be directly about {topic}. Do NOT generate unrelated math if topic is biology, or vice versa.\n"
            f"Difficulty: {level_desc}\n"
            f"For each question:\n"
            f"Q[N]: [question text]\n"
            f"A) [option]\nB) [option]\nC) [option]\nD) [option]\n"
            f"Correct: [letter]\n"
            f"Explanation: [brief explanation showing the calculation or reasoning that proves the correct answer]\n\n"
            f"STRICT RULES:\n"
            f"- Double-check: the letter in 'Correct:' MUST point to the option that actually contains the correct answer\n"
            f"- For math, verify the arithmetic before marking: e.g. 45+23=68, so Correct must be the letter with 68\n"
            f"- Explanation must match the correct answer's value\n"
            f"- Do NOT invent citations, URLs, page numbers or sources — no [1], no http — quiz is closed-book\n"
            f"- If you include a number in Explanation, it MUST equal the number in the Correct option\n"
            f"- {_grade_lock_line()}"
        )

    async def generate_quiz_stream(
        self,
        topic: str,
        level: str = "medium",
        num_questions: int = 5,
        model: str = "gemma3:12b",
        timeout: float = 120,
    ):
        """Streaming quiz: yields ('total', n), then ('question', q) +
        ('progress', done, total) as EACH question finishes verification
        (asyncio.as_completed — no waiting for the slowest one).

        Timed-out leftovers are yielded unverified so the stream always
        terminates with a full set. Powers POST /study/quiz/stream.
        """
        prompt = self._build_quiz_prompt(topic, level, num_questions)
        try:
            response = await ollama.complete(
                model, prompt, think=False, context_window=2048
            )
        except Exception as e:
            yield ("error", f"Generation failed: {e}")
            return
        raw_questions = self._parse_quiz(response)
        if not raw_questions:
            yield ("error", "No questions generated — try a different topic.")
            return
        raw_questions = _dedupe_questions(raw_questions)
        if not raw_questions:
            yield ("error", "No questions generated — try a different topic.")
            return

        total = len(raw_questions)
        yield ("total", total)
        verify_model = _default_model()
        owners = {
            asyncio.ensure_future(
                self._verify_single_question(q, topic, verify_model)
            ): q
            for q in raw_questions
        }
        pending = set(owners)
        done_n = 0
        deadline = asyncio.get_running_loop().time() + timeout

        def _unverified(raw):
            q = dict(raw) if isinstance(raw, dict) else {}
            q.setdefault("question", "")
            q.setdefault("options", [])
            q.setdefault("correct", "")
            q.setdefault("explanation", "")
            q.setdefault("verified", "unverified")
            return q

        try:
            while pending:
                wait_for = max(0.1, deadline - asyncio.get_running_loop().time())
                done_set, pending = await asyncio.wait(
                    pending,
                    timeout=wait_for,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if not done_set:
                    break  # overall budget spent — fall through to leftovers
                for task in done_set:
                    raw = owners.pop(task, None)
                    done_n += 1
                    try:
                        q = task.result()
                    except Exception as e:
                        logger.warning("Stream verify failed, using raw: %s", e)
                        q = None
                    if not isinstance(q, dict) or not q.get("options"):
                        q = _unverified(raw)
                    yield ("question", q)
                    yield ("progress", done_n, total)
            # Leftovers (timed out): yield raw so the set is complete
            for task in list(pending):
                task.cancel()
                raw = owners.pop(task, None)
                done_n += 1
                yield ("question", _unverified(raw))
                yield ("progress", done_n, total)
        except asyncio.CancelledError:
            for task in pending:
                task.cancel()
            raise

    async def generate_quiz(
        self,
        topic: str,
        level: str = "medium",
        num_questions: int = 5,
        model: str = "gemma3:12b",
        verify: bool | None = None,
    ) -> list[dict]:
        """Generate quiz — VERIFIED by default (as requested).

        Verification (second model + Google) runs in parallel so 5q
        verifies in ~8-12s (not 60s sequential). Use verify=False for
        instant unverified mode, or ARIA_QUIZ_VERIFY=0 to default-off.
        """
        if verify is None:
            env = os.environ.get("ARIA_QUIZ_VERIFY", "1").lower()
            verify = env not in ("0", "false", "no", "off")

        # Typo correction for common biology terms (e.g. organelles)
        topic = re.sub(r"orangell", "organell", topic, flags=re.IGNORECASE)
        topic = re.sub(r"mitocondria", "mitochondria", topic, flags=re.IGNORECASE)
        topic = re.sub(r"ribosom", "ribosome", topic, flags=re.IGNORECASE)
        prompt = self._build_quiz_prompt(topic, level, num_questions)

        response = await ollama.complete(
            model, prompt, think=False, context_window=2048
        )
        raw_questions = self._parse_quiz(response)

        if not raw_questions:
            return []

        raw_questions = _dedupe_questions(raw_questions)
        if not raw_questions:
            return []

        if not verify:
            for q in raw_questions:
                q.setdefault("verified", "unverified")
            return raw_questions

        # Verified path — bounded by overall timeout so we never hang "forever"
        try:
            verified = await asyncio.wait_for(
                self._verify_quiz(raw_questions, topic), timeout=25
            )
            return verified
        except TimeoutError:
            logger.warning(
                "Quiz verification timed out (25s), returning original questions"
            )
            for q in raw_questions:
                q.setdefault("verified", "original")
            return raw_questions

    async def _verify_quiz(
        self, questions: list[dict], topic: str, verify_model: str | None = None
    ) -> list[dict]:
        """Verify all quiz questions IN PARALLEL (was sequential — the main slowdown).

        Memory optimisation: reuses single gemma model, no second large model.
        Concurrency is bounded by OllamaService's MAX_CONCURRENT_CALLS (2) semaphore,
        so parallel gather still queues safely without OOM.
        """
        if verify_model is None:
            verify_model = _default_model()

        tasks = [
            self._verify_single_question(q, topic, verify_model) for q in questions
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        out: list[dict] = []
        for q, res in zip(questions, results):
            if isinstance(res, Exception):
                logger.warning(
                    "Verification failed for question, using original: %s", res
                )
                q["verified"] = "original"
                out.append(q)
            elif isinstance(res, dict):
                out.append(res)
            else:
                q["verified"] = "original"
                out.append(q)
        return out

    async def _verify_single_question(
        self, q: dict, topic: str, verify_model: str
    ) -> dict:
        """Verify a single question — math direct + second model + Google IN PARALLEL with timeouts."""
        question_text = q["question"]
        options = q["options"]
        claimed_correct = q.get("correct", "")

        # Direct math solve (strongest signal for arithmetic, e.g. 45+23=68)
        math_answer = _solve_simple_math(question_text, options)

        options_text = "\n".join(
            f"{chr(65 + i)}) {opt}" for i, opt in enumerate(options)
        )

        # Run model + Google concurrently, each with its own timeout
        model_coro = self._ask_second_model(
            question_text, options_text, claimed_correct, verify_model
        )
        google_coro = self._verify_with_google(question_text, options, topic)

        try:
            model_answer, google_answer = await asyncio.gather(
                asyncio.wait_for(model_coro, timeout=12),
                asyncio.wait_for(google_coro, timeout=8),
            )
        except TimeoutError:
            # If one times out, gather with return_exceptions fallback
            # Re-run with individual handling to salvage the other
            model_answer, google_answer = "", ""
            try:
                model_answer = await asyncio.wait_for(
                    self._ask_second_model(
                        question_text, options_text, claimed_correct, verify_model
                    ),
                    timeout=6,
                )
            except Exception:
                pass
            try:
                google_answer = await asyncio.wait_for(
                    self._verify_with_google(question_text, options, topic), timeout=5
                )
            except Exception:
                pass
        except Exception:
            model_answer, google_answer = "", ""
            # try individually with short timeouts
            try:
                model_answer = await asyncio.wait_for(
                    self._ask_second_model(
                        question_text, options_text, claimed_correct, verify_model
                    ),
                    timeout=6,
                )
            except Exception:
                pass
            try:
                google_answer = await asyncio.wait_for(
                    self._verify_with_google(question_text, options, topic), timeout=5
                )
            except Exception:
                pass

        # Cross-compare all signals (handles empty strings gracefully) — math has highest weight
        if isinstance(model_answer, Exception):
            model_answer = ""
        if isinstance(google_answer, Exception):
            google_answer = ""
        if math_answer and math_answer in "ABCD":
            # Math direct solve is deterministic — trust it over model/Google if it disagrees
            # Still run cross-compare but with math as strong vote (count double)
            final_q = self._cross_compare(
                q, claimed_correct, model_answer or "", google_answer or "", math_answer
            )
        else:
            final_q = self._cross_compare(
                q, claimed_correct, model_answer or "", google_answer or "", ""
            )

        # Post-check: if the explanation's closing number contradicts the chosen
        # key, that is a disagreement worth surfacing — NOT a licence to rewrite
        # the answer key. Rewriting caused corruption on non-numeric questions
        # (e.g. explanation mentioning "step 3" flipped the key to option C).
        # Rules:
        #  * Only the deterministic math solver may change the key, and only
        #    when the explanation confirms the same value.
        #  * Any other contradiction downgrades the question to "disputed".
        try:
            exp = final_q.get("explanation", "") or ""
            exp_nums = re.findall(r"-?\d+(?:\.\d+)?", exp.replace(",", ""))
            if exp_nums and any(re.search(r"\d", opt) for opt in options):
                exp_last = exp_nums[-1]
                exp_letter = _match_number_to_options(float(exp_last), options)
                if exp_letter and final_q.get("correct") != exp_letter:
                    if math_answer and math_answer == exp_letter:
                        # Deterministic math + explanation agree against the key — fix it.
                        logger.info(
                            "Fixing key via deterministic math: explanation and solver say %s, key was %s",
                            exp_letter,
                            final_q.get("correct"),
                        )
                        final_q["correct"] = exp_letter
                        final_q["verified"] = "math_corrected"
                    else:
                        # Contradiction without deterministic confirmation — flag, never rewrite.
                        if final_q.get("verified") in (
                            "triple_verified",
                            "majority_verified",
                            "math_corrected",
                            "original",
                        ):
                            final_q["verified"] = "disputed"
        except Exception:
            pass
        return final_q

    async def _ask_second_model(
        self, question: str, options_text: str, claimed: str, model: str
    ) -> str:
        """Ask a second model to pick the correct answer — fast timeout."""
        prompt = (
            f"Answer this multiple-choice question. Reply with ONLY the letter (A, B, C, or D).\n\n"
            f"Question: {question}\n"
            f"{options_text}\n\n"
            f"Your answer (just the letter):"
        )
        try:
            response = await ollama.complete(
                model,
                prompt,
                system="You are a factual assistant. Answer only with the correct letter.",
                timeout=12,
                context_window=2048,
                max_tokens=16,
            )
            # Extract letter from response
            m = re.search(r"([A-Da-d])", response.strip())
            if m:
                return m.group(1).upper()
        except Exception as e:
            logger.warning("Second model verification failed: %s", e)
        return ""

    async def _verify_with_google(
        self, question: str, options: list[str], topic: str
    ) -> str:
        """Search Google to fact-check the answer — capped to 2 results for speed."""
        try:
            from services.research_service import ResearchService

            research = ResearchService()

            # Build a search query from the question — truncate to keep Google fast
            search_query = f"{topic} {question[:120]}"
            results = await research.search(search_query, max_results=2)

            if not results:
                return ""

            # Combine search snippets into a token set + vocabulary
            hit_text = " ".join(
                f"{r.get('title', '')} {r.get('snippet', '')}" for r in results
            ).lower()
            vocab = re.findall(r"\b[a-zA-Z]{3,}\b", hit_text)
            vocab_nums = set(re.findall(r"\b\d+\b", hit_text))

            # Option words that add information beyond the question itself —
            # generic/stop words and words already in the question are noise.
            q_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", question.lower()))
            stopwords = {
                "a",
                "an",
                "the",
                "is",
                "it",
                "in",
                "on",
                "at",
                "to",
                "for",
                "of",
                "and",
                "or",
                "but",
                "with",
                "this",
                "that",
                "from",
                "are",
                "be",
                "was",
                "were",
                "can",
                "could",
                "would",
                "should",
                "all",
                "above",
                "none",
                "which",
                "what",
                "does",
                "who",
                "why",
                "most",
                "them",
                "their",
                "these",
                "those",
                "not",
            }

            def _sig_words(opt: str) -> list[str]:
                return [
                    w
                    for w in re.findall(r"\b[a-zA-Z]{3,}\b", opt.lower())
                    if w not in q_words and w not in stopwords
                ]

            # Detect numeric options (e.g. 67, 68, 78) — handle separately
            has_numeric_opts = any(re.search(r"\d", opt) for opt in options)

            # Score each option: distinctive term occurrences in snippets, with
            # fuzzy tolerance for inflection (evaporation vs evaporates).
            best_letter, best_score = "", 0.0
            for i, opt in enumerate(options):
                sig = _sig_words(opt)
                if (
                    not sig
                ):  # "All of the above" / "None of the above" — no signal, skip
                    continue
                score = 0.0
                for w in sig:
                    exact = sum(1 for t in vocab if t == w)
                    if exact:
                        score += 2.0 * exact
                        continue
                    # fuzzy: allow inflection (evaporation/evaporates) but block atom/atomic false positive
                    for t in vocab:
                        if abs(len(t) - len(w)) <= 1 and _fuzz_ratio(t, w) >= 0.72:
                            score += 1.0
                            break
                # Reward options whose whole phrase is echoed in snippets
                if len(sig) >= 2 and all(t in hit_text for t in sig):
                    score += 1.5
                # Numeric bonus: if option contains a number that appears in snippet
                if has_numeric_opts:
                    nums = re.findall(r"\b\d+\b", opt)
                    for num in nums:
                        if num in vocab_nums:
                            score += 2.0
                        # Also check hit_text directly for numbers in context
                        if num in hit_text:
                            score += 1.0
                if score > best_score:
                    best_score, best_letter = score, chr(65 + i)

            return best_letter if best_score > 0 else ""
        except Exception as e:
            logger.warning("Google verification failed: %s", e)
            return ""

    def _cross_compare(
        self,
        q: dict,
        claimed: str,
        model_answer: str,
        google_answer: str,
        math_answer: str = "",
    ) -> dict:
        """Compare claimed, model, google, and math-direct answers. Pick the best."""
        # Math direct is deterministic — single vote, anchor logic handles priority without double-weight inflation
        answers = [claimed, model_answer, google_answer]
        if math_answer and math_answer in "ABCD":
            answers.append(math_answer)
        valid = [a for a in answers if a in "ABCD"]

        if not valid:
            q["verified"] = "no_data"
            return q

        # Count votes
        from collections import Counter

        votes = Counter(valid)
        majority_answer, majority_count = votes.most_common(1)[0]

        # Math anchor: if math says X and at least one other agrees, trust math
        if math_answer and math_answer in "ABCD" and votes[math_answer] >= 2:
            q["correct"] = math_answer
            q["verified"] = (
                "triple_verified" if votes[math_answer] >= 3 else "majority_verified"
            )
            return q
        # Math alone (uncorroborated but deterministic) — correct arithmetic error, mark separately
        if math_answer and math_answer in "ABCD" and claimed != math_answer:
            q["correct"] = math_answer
            q["verified"] = "math_corrected"
            return q

        if majority_count >= 2:
            # At least 2 agree
            q["correct"] = majority_answer
            if majority_count >= 3:
                q["verified"] = "triple_verified"
            else:
                q["verified"] = "majority_verified"
        else:
            # All disagree — use the original claimed answer but flag it
            q["verified"] = "disputed"

        return q

    async def generate_flashcards(
        self, topic: str, num_cards: int = 10, model: str = "gemma3:12b"
    ) -> list[dict]:
        prompt = (
            f"Generate {num_cards} flashcards for studying: {topic}\n"
            f"Format exactly:\n"
            f"FRONT: [term or question] | BACK: [definition or answer]\n"
            f"One flashcard per line. {_grade_lock_line()}"
        )
        response = await ollama.complete(
            model, prompt, think=False, context_window=2048
        )
        return self._parse_flashcards(response)

    async def generate_summary(self, text: str, model: str = "gemma3:12b") -> str:
        prompt = (
            f"Summarise the following in clear, simple language.\n"
            f"{_grade_lock_line()}\n"
            f"Include: key points, important vocabulary, main ideas.\n\n{text[:4000]}"
        )
        return await ollama.complete(model, prompt, think=False, context_window=2048)

    def _parse_quiz(self, text: str) -> list[dict]:
        questions = []
        # Gemma may output Q1:, Q[1]:, Q 1., Question 1:, or 1. — handle all
        blocks = re.split(
            r"(?:\bQ\s*\[?\d+\]?\s*[:\.\)]\s*|\bQuestion\s+\d+\s*[:\.\)]\s*|^\s*\d+[\.\)]\s+)",
            text,
            flags=re.MULTILINE,
        )
        for block in blocks[1:]:
            lines = [l.strip() for l in block.strip().split("\n") if l.strip()]
            if not lines:
                continue
            q = {"question": lines[0], "options": [], "correct": "", "explanation": ""}
            for line in lines[1:]:
                if re.match(r"^[A-Da-d][\.:\)\-]\s*", line):
                    q["options"].append(
                        re.sub(r"^[A-Da-d][\.:\)\-]\s*", "", line).strip()
                    )
                elif (
                    re.search(r"(?i)\b(correct|answer)\b", line)
                    and not re.search(r"(?i)^explanation", line)
                    and len(line) < 120
                ):
                    # "Correct: B", "Correct answer: B", "The correct answer is B",
                    # "Correct: (B)" — the answer letter is the last standalone
                    # A-D token on the line (ignore 'a' inside words like "answer").
                    letters = re.findall(r"\b[A-Da-d]\b", line)
                    if letters:
                        q["correct"] = letters[-1].upper()
                elif re.match(r"(?i)^explanation\s*[:\-]\s*", line) or (
                    q["correct"] and len(line) > 15
                ):
                    q["explanation"] = (q["explanation"] + " " + line).strip()
            if len(q["options"]) >= 4:
                questions.append(q)
        return questions[:10]

    def _parse_flashcards(self, text: str) -> list[dict]:
        cards = []
        for line in text.split("\n"):
            if "|" in line and re.search(r"(?i)front:", line):
                parts = line.split("|", 1)
                if len(parts) == 2:
                    front = re.sub(r"(?i)front:\s*", "", parts[0]).strip()
                    back = re.sub(r"(?i)back:\s*", "", parts[1]).strip()
                    if front and back:
                        cards.append({"front": front, "back": back})
        return cards[:20]

    async def generate_notes(
        self, topic: str, style: str = "structured", model: str = "gemma3:12b"
    ) -> str:
        style_desc = {
            "structured": "well-organised with headings, bullet points, key terms bolded",
            "cornell": "Cornell note format: main notes right, cue questions left, summary at bottom",
            "outline": "hierarchical outline with numbered sections and sub-sections",
            "simple": f"simple clear bullet points. {_grade_lock_line()}",
        }.get(style, "structured")
        prompt = (
            f"Create comprehensive study notes about: {topic}\n"
            f"Style: {style_desc}\n"
            f"Include: key concepts, important definitions, examples, common mistakes.\n"
            f"{_grade_lock_line()}"
        )
        return await ollama.complete(model, prompt, think=False, context_window=2048)

    async def generate_essay_feedback(
        self, essay: str, topic: str = "", model: str = "gemma3:12b"
    ) -> str:
        prompt = (
            f"Analyse this essay and provide detailed feedback.\n"
            f"Topic: {topic or 'not specified'}\n\n"
            f"Essay:\n{essay[:4000]}\n\n"
            f"Provide feedback on:\n"
            f"1. Thesis strength and clarity\n"
            f"2. Argument structure and logical flow\n"
            f"3. Evidence quality and use of examples\n"
            f"4. Grammar, spelling, and punctuation\n"
            f"5. Vocabulary and expression\n"
            f"6. Introduction and conclusion effectiveness\n"
            f"7. Overall coherence\n\n"
            f"For each area give a rating (Needs Work/Good/Very Good/Excellent)\n"
            f"and specific suggestions with examples of how to improve.\n"
            f"End with an overall rating and top 3 improvements to make.\n"
            f"{_grade_lock_line()}"
        )
        return await ollama.complete(
            model,
            prompt,
            system="You are an expert English teacher providing constructive essay feedback.",
            think=False,
            context_window=2048,
        )

    async def generate_formula_reference(
        self, topic: str, model: str = "gemma3:12b"
    ) -> str:
        prompt = (
            f"Provide a comprehensive formula reference for: {topic}\n\n"
            f"For each formula include:\n"
            f"- Name of the formula\n"
            f"- The equation (use clear notation)\n"
            f"- What each variable/symbol means\n"
            f"- When to use it\n"
            f"- A worked example\n"
            f"- Common mistakes to avoid\n\n"
            f"Format clearly with headings. {_grade_lock_line()}"
        )
        return await ollama.complete(
            model,
            prompt,
            system="You are a maths/science tutor creating a clear formula reference sheet.",
            think=False,
            context_window=2048,
        )

    async def generate_timeline(self, topic: str, model: str = "gemma3:12b") -> str:
        prompt = (
            f"Create a detailed chronological timeline for: {topic}\n\n"
            f"Format as a structured list:\n"
            f"[Date/Period] — [Event]\n"
            f"  Cause: [what led to this]\n"
            f"  Significance: [why it matters]\n\n"
            f"Include 10-15 key events. Show cause-and-effect relationships.\n"
            f"Use clear dates/periods. {_grade_lock_line()}"
        )
        return await ollama.complete(
            model,
            prompt,
            system="You are a history expert creating a clear, educational timeline.",
            think=False,
            context_window=2048,
        )

    async def generate_cheatsheet(
        self, topic: str, subject: str = "", model: str = "gemma3:12b"
    ) -> str:
        """One printable page per topic: formulas, definitions, gotchas.
        Made for the morning bus ride — dense but scannable, fits ~1 page."""
        subj = f"Subject: {subject}\n" if subject else ""
        prompt = (
            "Create a ONE-PAGE cheat sheet a student can revise on the bus.\n"
            f"{subj}Topic: {topic}\n\n"
            "STRICT FORMAT (markdown, keep it tight — max ~450 words total):\n"
            "## <topic> — Cheat Sheet\n"
            "### 🔑 Key definitions (5-7 max)\n"
            "- **Term** — one-line definition\n"
            "### 📐 Must-know formulas\n"
            "- **Name**: `formula` — what each symbol means, when to use it\n"
            "### ⚠️ Gotchas (3-5 exam traps)\n"
            "- Trap → correct approach\n"
            "### ⚡ 60-second recall\n"
            "- 5 rapid-fire check questions (no answers — student self-tests)\n\n"
            "RULES:\n"
            "- Dense, no fluff, no intro paragraph.\n"
            "- Use LaTeX $...$ for math.\n"
            "- Australian curriculum examples where relevant.\n"
            f"- {_grade_lock_line()} Exam-sharp."
        )
        return await ollama.complete(
            model,
            prompt,
            system="You are ARIA, creating ultra-concise one-page exam cheat sheets.",
            think=False,
            context_window=2048,
        )

    async def generate_worksheet(
        self,
        topic: str,
        grade: str = "Year 10",
        question_count: int = 10,
        include_answers: bool = True,
        model: str = "gemma3:12b",
    ) -> str:
        from data.nsw_curriculum import detect_stage, get_curriculum_context

        stage = detect_stage(grade)
        curriculum_ctx = get_curriculum_context(topic, stage, topic)

        # Split questions into three difficulty tiers
        q1 = max(2, question_count // 4)  # mild
        q2 = max(3, question_count // 2)  # medium
        q3 = question_count - q1 - q2  # spicy/extension

        ans = (
            (
                "Include a separate ANSWER KEY at the end with full worked solutions "
                "for every question. Mark each answer with its question number."
            )
            if include_answers
            else "Do NOT include answers."
        )

        prompt = (
            "You are an expert NSW school teacher creating a professional worksheet "
            "in the style of Tutero.com — clean, differentiated, curriculum-aligned.\n\n"
            f"TOPIC: {topic}\n"
            f"GRADE: {grade}\n"
            f"NSW STAGE: {stage}\n"
            f"GRADE LOCK: All questions must be {grade}-level only. "
            f"Never include content from younger years or older years.\n"
            f"TOTAL QUESTIONS: {question_count} (split: {q1} mild + {q2} medium + {q3} spicy)\n\n"
            f"NSW CURRICULUM CONTEXT:\n{curriculum_ctx}\n\n"
            "=== WORKSHEET STRUCTURE (Tutero style) ===\n\n"
            "HEADER:\n"
            "- Worksheet title (clear, topic-specific)\n"
            "- Student Name: ____________\n"
            "- Date: ____________\n"
            "- Subject & Stage/Grade\n\n"
            "LEARNING INTENT:\n"
            "- One sentence: What students will learn\n"
            "- 3-4 Success Criteria as 'I can...' statements\n\n"
            "--- SECTION 1: MILD (Foundational) ---\n"
            f"Provide {q1} questions that check basic understanding.\n"
            "These are MCQ (4 options A-D) or simple one-line recall questions.\n"
            "Bloom's level: Remember, Understand.\n"
            "Include a THINKING TIME hint for the first question.\n\n"
            "--- SECTION 2: MEDIUM (Proficient) ---\n"
            f"Provide {q2} questions that apply knowledge.\n"
            "Mix of short answer (2-4 sentences), calculations, and short-problem questions.\n"
            "Bloom's level: Apply, Analyse.\n"
            "Use real-world Australian contexts where relevant.\n\n"
            "--- SECTION 3: SPICY (Extension) ---\n"
            f"Provide {q3} questions that challenge thinking.\n"
            "Extended response, essay-style, evaluate/create tasks, or complex multi-step problems.\n"
            "Bloom's level: Evaluate, Create.\n"
            "These are exit-point questions for students who finish early.\n\n"
            "MARKS:\n"
            "- Show [x marks] next to each question\n"
            f"- Total ~{question_count * 3} marks\n"
            "- MCQs: 1 mark, Short answer: 2-3 marks, Extended: 4-6 marks, Problems: 3-5 marks\n\n"
            "FORMATTING:\n"
            "- Use markdown: ## for section headers, numbered questions, bold for key terms\n"
            "- Leave clear space (blank lines) between questions for student answers\n"
            "- Clean, uncluttered layout\n\n"
            f"{ans}\n\n"
            "Now generate the complete worksheet."
        )

        system = (
            "You are a senior NSW teacher creating professional worksheets aligned to the "
            "NESA NSW Curriculum, modelled after Tutero.com's differentiated format. "
            "Worksheets must have three clear difficulty tiers: Mild, Medium, Spicy. "
            "Each tier signals to students where to start and where to stretch. "
            "Use Australian examples, clear language, and a clean layout. "
            "Every question must have a marks allocation."
        )

        response = await ollama.complete(
            model, prompt, system=system, timeout=300, think=False, context_window=2048
        )
        return response
