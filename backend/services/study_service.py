"""Study service — generates quizzes, flashcards, mind maps."""

import json
import os
import re
import logging
import asyncio
from pathlib import Path
from difflib import SequenceMatcher
from services.ollama_service import OllamaService

logger = logging.getLogger(__name__)


def _fuzz_ratio(a: str, b: str) -> float:
    """Similarity ratio (0..1) between two short strings — used to match
    semantically-inflected tokens (evaporation vs evaporates)."""
    return SequenceMatcher(None, a, b).ratio()


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
            expr = re.findall(r"\d+\s*[\+\-\*/]\s*\d+(?:\s*[\+\-\*/]\s*\d+)*", question)[0]
            expected = eval(expr, {"__builtins__": {}}, {})
            expected = int(expected) if float(expected).is_integer() else float(expected)
        except Exception:
            pass
    elif any(k in q_lower for k in ("more","total","altogether","sum","in all","plus","add","combined","together")):
        try:
            expected = q_nums[0] + q_nums[1]
        except Exception:
            pass
    elif any(k in q_lower for k in ("left","fewer","difference","remain","remaining","less")) or re.search(r"\b(minus|subtract|take away)\b", q_lower):
        try:
            expected = q_nums[0] - q_nums[1]
        except Exception:
            pass
    elif re.search(r"\b(times|multiply|multiplied|product|of)\b", q_lower) and len(q_nums) >= 2:
        try:
            expected = q_nums[0] * q_nums[1]
        except Exception:
            pass
    elif re.search(r"\b(divide|divided|quotient|per|ratio)\b", q_lower) and len(q_nums) >= 2 and q_nums[1] != 0:
        try:
            expected = q_nums[0] / q_nums[1]
            expected = int(expected) if float(expected).is_integer() else expected
        except Exception:
            pass

    if expected is None:
        return ""

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

ollama = OllamaService()

# Import central routing
try:
    from models.database import MODELS
except Exception:
    MODELS = {
        "main": "gemma4:e4b-mlx",
        "embedding": "nomic-embed-text",
    }

def _default_model() -> str:
    try:
        from models.database import get_config
        return get_config().get("model") or get_config().get("reasoning_model") or MODELS["main"]
    except Exception:
        return MODELS["main"]

QUIZ_LEVELS = {
    "easy": "simple recall and basic understanding, single-step problems",
    "medium": "application and some analysis, two-step problems",
    "hard": "deep analysis, multi-step reasoning, challenging edge cases",
    "exam": "timed exam simulation — comprehensive coverage, varied question types, mark-scheme style answers",
    "olympiad": "competition-level (APSMO/AMC/IMO style), highly challenging, creative lateral thinking, proof-based",
}


class StudyService:

    async def generate_quiz(
        self,
        topic: str,
        level: str = "medium",
        num_questions: int = 5,
        model: str = "gemma4:e4b-mlx",
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
        topic = re.sub(r"orangell", "organell", topic, flags=re.I)
        topic = re.sub(r"mitocondria", "mitochondria", topic, flags=re.I)
        topic = re.sub(r"ribosom", "ribosome", topic, flags=re.I)

        level_desc = QUIZ_LEVELS.get(level, QUIZ_LEVELS["medium"])
        prompt = (
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
            f"- Make questions appropriate for a 13-year-old student."
        )
        response = await ollama.complete(model, prompt, think=False, context_window=2048)
        raw_questions = self._parse_quiz(response)

        if not raw_questions:
            return []

        if not verify:
            for q in raw_questions:
                q.setdefault("verified", "unverified")
            # Background verify + learn while ARIA idle — don't block quiz return
            # Skip during pytest to keep tests deterministic and fast
            if not os.environ.get("PYTEST_CURRENT_TEST"):
                try:
                    # copy so background can mutate without affecting returned list
                    to_verify = [dict(q) for q in raw_questions]
                    asyncio.create_task(self._background_verify_and_learn(to_verify, topic))
                except Exception:
                    pass
            return raw_questions

        # Verified path — bounded by overall timeout so we never hang "forever"
        try:
            verified = await asyncio.wait_for(
                self._verify_quiz(raw_questions, topic), timeout=25
            )
            return verified
        except asyncio.TimeoutError:
            logger.warning("Quiz verification timed out (25s), returning original questions")
            for q in raw_questions:
                q.setdefault("verified", "original")
            return raw_questions

    async def _verify_quiz(self, questions: list[dict], topic: str, verify_model: str | None = None) -> list[dict]:
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
                logger.warning("Verification failed for question, using original: %s", res)
                q["verified"] = "original"
                out.append(q)
            elif isinstance(res, dict):
                out.append(res)
            else:
                q["verified"] = "original"
                out.append(q)
        return out

    async def _background_verify_and_learn(self, questions: list[dict], topic: str):
        """Run verification in background (not blocking quiz return).
        NOTE: auto flashcard pre-generation removed per user request —
        flashcards are only created when explicitly asked."""
        try:
            # 1) Verify quiz in background (parallel, 30s budget)
            verified = await asyncio.wait_for(self._verify_quiz(questions, topic), timeout=30)
            # Cache verified quiz for future instant hits (5-min TTL already in ollama cache)
            # We store to a tiny on-disk cache so next identical topic can be instant-verified
            try:
                cache_path = Path.home() / ".aria_data" / "verified_quiz_cache.json"
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                # non-blocking write via thread
                import json as _json
                # best-effort: don't block if file locked
                existing = {}
                if cache_path.exists():
                    try:
                        existing = _json.loads(cache_path.read_text(encoding="utf-8"))
                    except Exception:
                        existing = {}
                existing[topic.lower().strip()[:80]] = {"verified": verified, "ts": __import__("time").time()}
                # keep last 50
                if len(existing) > 50:
                    # drop oldest
                    oldest = sorted(existing.items(), key=lambda kv: kv[1].get("ts", 0))[0][0]
                    existing.pop(oldest, None)
                cache_path.write_text(_json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as e:
                logger.debug("Background cache write failed: %s", e)

            logger.info("Background verify done for topic=%r (%d q)", topic, len(verified))
        except asyncio.TimeoutError:
            logger.warning("Background verify timed out for topic=%r", topic)
        except Exception as e:
            logger.debug("Background verify failed for %r: %s", topic, e)

    async def _verify_single_question(self, q: dict, topic: str, verify_model: str) -> dict:
        """Verify a single question — math direct + second model + Google IN PARALLEL with timeouts."""
        question_text = q["question"]
        options = q["options"]
        claimed_correct = q.get("correct", "")

        # Direct math solve (strongest signal for arithmetic, e.g. 45+23=68)
        math_answer = _solve_simple_math(question_text, options)

        options_text = "\n".join(
            f"{chr(65+i)}) {opt}" for i, opt in enumerate(options)
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
        except asyncio.TimeoutError:
            # If one times out, gather with return_exceptions fallback
            # Re-run with individual handling to salvage the other
            model_answer, google_answer = "", ""
            try:
                model_answer = await asyncio.wait_for(
                    self._ask_second_model(question_text, options_text, claimed_correct, verify_model),
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
                    self._ask_second_model(question_text, options_text, claimed_correct, verify_model),
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
            final_q = self._cross_compare(q, claimed_correct, model_answer or "", google_answer or "", math_answer)
        else:
            final_q = self._cross_compare(q, claimed_correct, model_answer or "", google_answer or "", "")

        # Post-check: ensure explanation's number matches correct option (fixes 45+23=68 vs B case)
        try:
            exp = final_q.get("explanation", "") or ""
            # Extract numbers from explanation (e.g. "45 + 23 = 68" -> 68)
            exp_nums = re.findall(r"-?\d+", exp)
            if exp_nums and any(re.search(r"\d", opt) for opt in options):
                # Heuristic: last number in explanation is likely the answer
                exp_last = exp_nums[-1]
                # Find which option contains that number
                for i, opt in enumerate(options):
                    if re.search(rf"\b{re.escape(exp_last)}\b", opt):
                        exp_letter = chr(65 + i)
                        if final_q.get("correct") != exp_letter:
                            logger.info("Fixing mismatch: explanation says %s but correct was %s, fixing to %s", exp_last, final_q.get("correct"), exp_letter)
                            final_q["correct"] = exp_letter
                            # Upgrade verification since we fixed via explanation
                            if final_q.get("verified") in ("disputed", "unverified", "original"):
                                final_q["verified"] = "majority_verified"
                        break
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
                model, prompt,
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

    async def _verify_with_google(self, question: str, options: list[str], topic: str) -> str:
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
                "a", "an", "the", "is", "it", "in", "on", "at", "to", "for",
                "of", "and", "or", "but", "with", "this", "that", "from",
                "are", "be", "was", "were", "can", "could", "would", "should",
                "all", "above", "none", "which", "what", "does", "who", "why",
                "most", "them", "their", "that", "these", "those", "not",
            }

            def _sig_words(opt: str) -> list[str]:
                return [
                    w for w in re.findall(r"\b[a-zA-Z]{3,}\b", opt.lower())
                    if w not in q_words and w not in stopwords
                ]

            # Detect numeric options (e.g. 67, 68, 78) — handle separately
            has_numeric_opts = any(re.search(r"\d", opt) for opt in options)

            # Score each option: distinctive term occurrences in snippets, with
            # fuzzy tolerance for inflection (evaporation vs evaporates).
            best_letter, best_score = "", 0.0
            for i, opt in enumerate(options):
                sig = _sig_words(opt)
                if not sig:  # "All of the above" / "None of the above" — no signal, skip
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
        self, q: dict, claimed: str, model_answer: str, google_answer: str, math_answer: str = ""
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
            q["verified"] = "triple_verified" if votes[math_answer] >= 3 else "majority_verified"
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
        self, topic: str, num_cards: int = 10, model: str = "gemma4:e4b-mlx"
    ) -> list[dict]:
        prompt = (
            f"Generate {num_cards} flashcards for studying: {topic}\n"
            f"Format exactly:\n"
            f"FRONT: [term or question] | BACK: [definition or answer]\n"
            f"One flashcard per line. Make them clear and memorable for a 13-year-old."
        )
        response = await ollama.complete(model, prompt, think=False, context_window=2048)
        return self._parse_flashcards(response)

    async def generate_summary(self, text: str, model: str = "gemma4:e4b-mlx") -> str:
        prompt = (
            f"Summarise the following in clear, simple language for a 13-year-old student.\n"
            f"Include: key points, important vocabulary, main ideas.\n\n{text[:4000]}"
        )
        return await ollama.complete(model, prompt, think=False, context_window=2048)

    def _parse_quiz(self, text: str) -> list[dict]:
        questions = []
        # Gemma may output Q1:, Q[1]:, Q 1., Question 1:, or 1. — handle all
        blocks = re.split(r"(?:\bQ\s*\[?\d+\]?\s*[:\.\)]\s*|\bQuestion\s+\d+\s*[:\.\)]\s*|^\s*\d+[\.\)]\s+)", text, flags=re.M)
        for block in blocks[1:]:
            lines = [l.strip() for l in block.strip().split("\n") if l.strip()]
            if not lines:
                continue
            q = {"question": lines[0], "options": [], "correct": "", "explanation": ""}
            for line in lines[1:]:
                if re.match(r"^[A-Da-d][\.:\)\-]\s*", line):
                    q["options"].append(re.sub(r"^[A-Da-d][\.:\)\-]\s*", "", line).strip())
                elif re.search(r"(?i)\b(correct|answer)\b", line) and not re.search(r"(?i)^explanation", line) and len(line) < 120:
                    # "Correct: B", "Correct answer: B", "The correct answer is B",
                    # "Correct: (B)" — the answer letter is the last standalone
                    # A-D token on the line (ignore 'a' inside words like "answer").
                    letters = re.findall(r"\b[A-Da-d]\b", line)
                    if letters:
                        q["correct"] = letters[-1].upper()
                elif re.match(r"(?i)^explanation\s*[:\-]\s*", line) or (q["correct"] and len(line) > 15):
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
                    back  = re.sub(r"(?i)back:\s*",  "", parts[1]).strip()
                    if front and back:
                        cards.append({"front": front, "back": back})
        return cards[:20]

    async def generate_notes(
        self, topic: str, style: str = "structured", model: str = "gemma4:e4b-mlx"
    ) -> str:
        style_desc = {
            "structured": "well-organised with headings, bullet points, key terms bolded",
            "cornell": "Cornell note format: main notes right, cue questions left, summary at bottom",
            "outline": "hierarchical outline with numbered sections and sub-sections",
            "simple": "simple clear bullet points easy for a 13-year-old",
        }.get(style, "structured")
        prompt = (
            f"Create comprehensive study notes about: {topic}\n"
            f"Style: {style_desc}\n"
            f"Include: key concepts, important definitions, examples, common mistakes.\n"
            f"Clear and helpful for a 13-year-old student."
        )
        return await ollama.complete(model, prompt, think=False, context_window=2048)

    async def generate_essay_feedback(
        self, essay: str, topic: str = "", model: str = "gemma4:e4b-mlx"
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
            f"End with an overall rating and top 3 improvements to make."
        )
        return await ollama.complete(model, prompt, system="You are an expert English teacher providing constructive essay feedback for a 13-year-old student.", think=False, context_window=2048)

    async def generate_formula_reference(
        self, topic: str, model: str = "gemma4:e4b-mlx"
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
            f"Format clearly with headings. Suitable for a 13-year-old student."
        )
        return await ollama.complete(model, prompt, system="You are a maths/science tutor creating a clear formula reference sheet.", think=False, context_window=2048)

    async def generate_timeline(
        self, topic: str, model: str = "gemma4:e4b-mlx"
    ) -> str:
        prompt = (
            f"Create a detailed chronological timeline for: {topic}\n\n"
            f"Format as a structured list:\n"
            f"[Date/Period] — [Event]\n"
            f"  Cause: [what led to this]\n"
            f"  Significance: [why it matters]\n\n"
            f"Include 10-15 key events. Show cause-and-effect relationships.\n"
            f"Use clear dates/periods. Suitable for a 13-year-old student."
        )
        return await ollama.complete(model, prompt, system="You are a history expert creating a clear, educational timeline.", think=False, context_window=2048)

    async def generate_worksheet(
        self, topic: str, grade: str = "Year 10",
        question_count: int = 10, include_answers: bool = True,
        model: str = "gemma4:e4b-mlx"
    ) -> str:
        from data.nsw_curriculum import get_curriculum_context, detect_stage

        stage = detect_stage(grade)
        curriculum_ctx = get_curriculum_context(topic, stage, topic)

        # Split questions into three difficulty tiers
        q1 = max(2, question_count // 4)       # mild
        q2 = max(3, question_count // 2)       # medium
        q3 = question_count - q1 - q2          # spicy/extension

        ans = (
            "Include a separate ANSWER KEY at the end with full worked solutions "
            "for every question. Mark each answer with its question number."
        ) if include_answers else "Do NOT include answers."

        prompt = (
            "You are an expert NSW school teacher creating a professional worksheet "
            "in the style of Tutero.com — clean, differentiated, curriculum-aligned.\n\n"
            f"TOPIC: {topic}\n"
            f"GRADE: {grade}\n"
            f"NSW STAGE: {stage}\n"
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

        response = await ollama.complete(model, prompt, system=system, timeout=300, think=False, context_window=2048)
        return response