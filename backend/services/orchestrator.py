"""
Study Buddy Orchestrator — The Brain (refactored)
──────────────────────────────────────────
Thin coordinator that imports from focused modules.
The orchestrate() function is the main pipeline that ties everything together.

Decomposed modules:
  • intent_detector.py  — INTENT_PATTERNS, detect_intents(), detect_message_language()
  • model_selector.py   — choose_models(), _main_model()
  • prompt_builder.py   — _build_system_prompt()
  • post_processor.py   — _generate_extras, _verify_answer, _verify_math_via_code,
                           _self_check_critic, _generate_suggestions, _parse_methods,
                           _parse_quiz, _parse_flashcards, _sse
"""

import asyncio
import json
import re
import logging
import time as _time
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

# ── Re-export from focused modules (backward compatibility) ──────────────────
from services.intent_detector import (
    INTENT_PATTERNS,
    detect_intents,
    detect_message_language,
)
from services.model_selector import (
    choose_models,
    _main_model,
    MODELS,
)
from services.prompt_builder import _build_system_prompt
from services.post_processor import (
    _sse,
    _generate_extras,
    _verify_answer,
    _verify_math_via_code,
    _self_check_critic,
    _generate_suggestions,
    _parse_methods,
    # Re-export parsers from post_processor (which imports from study_service)
    _parse_quiz,
    _parse_flashcards,
)

# ── Services ──────────────────────────────────────────────────────────────────

from services.ollama_service import OllamaService
from services.image_service import ImageService
from services.research_service import ResearchService
from services.study_service import StudyService
from services.youtube_service import YouTubeService
from services.document_service import DocumentService
from services.citation_service import CitationService

ollama       = OllamaService()
image_svc    = ImageService()
research_svc = ResearchService()
study_svc    = StudyService()
youtube_svc  = YouTubeService()
doc_svc      = DocumentService()
citation_svc = CitationService()

try:
    from services.memory_service import MemoryService
    memory_svc = MemoryService()
except Exception:
    memory_svc = None
try:
    from services.knowledge_base_service import KnowledgeBaseService
    kb_svc = KnowledgeBaseService()
except Exception:
    kb_svc = None


# Day 5: voice-optimized answers. Spoken replies must be short, plain-text,
# and sentence-chunked so TTS can start on sentence 1. No markdown tables,
# code fences, or latex — the voice cleaner strips them anyway, so don't emit
# them in the first place.
VOICE_MODE_SUFFIX = (
    "\n\nIMPORTANT: You are in VOICE TUTOR MODE. The student hears your answer out loud.\n"
    "1. Keep it short: 1-3 sentences per idea, max ~120 words unless asked for more.\n"
    "2. Plain speakable text only: no markdown, tables, code fences, latex, or URLs.\n"
    "3. One idea per sentence so speech chunks cleanly on . ! ? boundaries.\n"
    "4. Read formulas aloud ('x squared plus three') instead of writing symbols.\n"
    "5. Match the student's language and script — if they speak Tamil, answer in Tamil.\n"
    "6. No greetings or filler openers — start directly with the answer so the\n"
    "   first spoken sentence carries content, not 'Hello!'.\n"
    "7. End with one quick spoken check question.\n"
)


# ── Main orchestrator ─────────────────────────────────────────────────────────

async def orchestrate(
    message: str,
    conversation_id: str,
    image_data: bytes | None = None,
    image_mime: str | None = None,
    doc_text: str | None = None,
    config: dict | None = None,
    mode: str = "normal",
) -> AsyncGenerator[str, None]:
    """Main orchestration pipeline. Streams SSE events for the chat response."""
    config    = config or {}
    # Feature-1 quality program: stage timings. Monotonic marks at pipeline
    # boundaries, emitted as one additive `timings` event before `done`
    # (frontends ignore unknown types). Zero behavior change otherwise.
    _t0 = _time.monotonic()
    _marks: dict = {}

    def _mark(name: str) -> None:
        _marks[name] = round((_time.monotonic() - _t0) * 1000)

    has_image = image_data is not None
    has_doc   = doc_text is not None
    # Polish: empty message + image → default to handwriting/grading request
    if has_image and not message.strip():
        message = "Please analyse this image and check my handwritten answer, grade it out of 10 with tips."

    intents = detect_intents(message, has_image, has_doc)
    # Worksheet generator takes precedence over solver (generate vs solve)
    if "worksheet_generator" in intents and "worksheet_solver" in intents:
        if re.search(r"\b(generate|create|make|build|design)\b", message, re.I):
            intents = [i for i in intents if i != "worksheet_solver"]
        else:
            intents = [i for i in intents if i != "worksheet_generator"]
    # Diagram specialist beats raster image gen for diagrams (vector > photo)
    if "diagram" in intents and "image_gen" in intents:
        intents = [i for i in intents if i != "image_gen"]
    models  = choose_models(intents, config)
    is_hard = any(i in intents for i in {"math","formula","coding","geography","history","science","worksheet_solver"})
    if "explain" in intents and any(i in intents for i in {"math","formula","coding","geography","history","science"}):
        is_hard = True

    logger.info("Orchestrating: intents=%s, models=%s, mode=%s", intents, models, mode)
    yield _sse({"type": "intent", "content": intents})
    yield _sse({"type": "progress", "step": "intent", "status": "done", "pct": 10, "label": "Understanding request"})
    _mark("intent")
    try:
        from services.telemetry_service import record_event
        record_event("orchestrate", intents=",".join(intents[:5]), mode=mode)
    except Exception:
        pass

    # ── Step 1: Memory & KB retrieval (fast) — used to skip search ──
    memory_context = ""
    kb_context = ""
    kb_results = []
    search_results = None
    youtube_results = None
    cross_check = None

    if config.get("memory_enabled") and memory_svc is not None:
        try:
            mem_k = 5 if is_hard else 3
            memories = await asyncio.wait_for(
                memory_svc.retrieve(conversation_id, message, k=mem_k), timeout=12
            )
            if memories:
                memory_context = "\n".join(memories[:6 if is_hard else 4])
        except Exception:
            pass
    if config.get("knowledge_base_enabled") and kb_svc is not None:
        try:
            kb_n = 6 if is_hard else 4
            if any(i in intents for i in {"math","formula","worksheet_solver","explain"}):
                kb_cols = ["math","education_au","general","science"]
            elif "geography" in intents:
                kb_cols = ["geography","education_au","general"]
            elif "history" in intents:
                kb_cols = ["history","education_au","general"]
            elif "coding" in intents or "code" in intents:
                kb_cols = ["coding","general"]
            else:
                kb_cols = None
            kb_results = await asyncio.wait_for(
                kb_svc.search(message, collections=kb_cols, n_results=kb_n), timeout=12
            )
            if kb_results:
                kb_context = "\n".join(r["text"][:500] for r in kb_results[:5 if is_hard else 3])
        except Exception:
            pass

    has_kb_or_memory = bool(memory_context) or bool(kb_context)

    # ── Step 2: Parallel lightweight tasks — Google only if needed ──
    parallel = {}
    cross_check_intents = {"explain", "math", "formula", "timeline", "summary", "worksheet_solver", "notes", "geography", "coding", "history", "science", "study_intel"}
    needs_cross_check = bool(cross_check_intents & set(intents))

    web_enabled = config.get("web_search_enabled", True)
    google_first = config.get("google_first", True)

    needs_search = web_enabled and ("web_search" in intents or not has_kb_or_memory)

    google_intents = {"explain", "chat", "summary", "math", "geography", "formula", "timeline", "notes", "coding", "history", "science", "worksheet_solver", "doc_chat", "study_intel", "translate", "socratic", "roleplay"}
    if needs_search:
        if "web_search" in intents:
            parallel["search"] = research_svc.search(message, max_results=6 if is_hard else 5)
        elif google_first and any(i in intents for i in google_intents):
            parallel["search"] = research_svc.search(message, max_results=6 if is_hard else 5)
        if needs_cross_check and "search" not in parallel:
            parallel["cross_check"] = research_svc.search(message, max_results=5)
    elif needs_cross_check and not has_kb_or_memory:
        parallel["cross_check"] = research_svc.search(message, max_results=5)
    if "youtube" in intents:
        urls = re.findall(r"https?://(?:www\.)?(?:youtube\.com|youtu\.be)\S+", message)
        if urls:
            parallel["youtube"] = youtube_svc.process(urls[0])

    search_results  = None
    youtube_results = None
    cross_check     = None

    if parallel:
        for key in parallel:
            label = {"search":"Searching Google","cross_check":"Cross-checking","youtube":"Fetching YouTube"}.get(key, key)
            yield _sse({"type": "progress", "step": key, "status": "running", "pct": 20, "label": label})
        results = await asyncio.gather(*parallel.values(), return_exceptions=True)
        for key, result in zip(parallel.keys(), results):
            if isinstance(result, Exception):
                yield _sse({"type": "progress", "step": key, "status": "error", "pct": 30, "label": str(result)[:60]})
                continue
            if key == "search":
                search_results = result
                yield _sse({"type": "progress", "step": key, "status": "done", "pct": 35, "label": f"Found {len(search_results or [])} results"})
                yield _sse({"type": "tool", "tool": "web_search", "content": (search_results or [])[:3]})
            elif key == "cross_check":
                cross_check = result
                yield _sse({"type": "progress", "step": key, "status": "done", "pct": 40, "label": "Cross-check ready"})
            elif key == "youtube":
                youtube_results = result
                yield _sse({"type": "progress", "step": key, "status": "done", "pct": 40, "label": "YouTube ready"})
                yield _sse({"type": "tool", "tool": "youtube", "content": youtube_results})
        yield _sse({"type": "progress", "step": "search_done", "status": "done", "pct": 45, "label": "Search complete"})
    _mark("retrieval")

    # ── Step 3: Vision ──
    vision_text = None
    if "image_analysis" in intents and image_data:
        vision_model = models.get("vision", _main_model(config))
        yield _sse({"type": "progress", "step": "vision", "status": "running", "pct": 50, "label": f"Reading image with {vision_model}"})
        yield _sse({"type": "status", "content": f"Reading image with {vision_model}..."})
        try:
            vision_text = await image_svc.analyse(
                image_data, image_mime or "image/jpeg", vision_model
            )
            yield _sse({"type": "progress", "step": "vision", "status": "done", "pct": 65, "label": "Image read"})
            yield _sse({"type": "tool", "tool": "vision", "content": vision_text})
            main_m = _main_model(config)
            if vision_model != main_m:
                await ollama.unload_model(vision_model)
        except Exception as e:
            vision_text = f"[Vision model unavailable — using OCR: {e}]"
            yield _sse({"type": "progress", "step": "vision", "status": "error", "pct": 60, "label": "Vision fallback to OCR"})
            yield _sse({"type": "status", "content": "Vision unavailable, falling back to OCR..."})
    _mark("vision")

    # ── Step 3b: Study Intel enrichment ──
    if "study_intel" in intents and memory_svc is not None:
        try:
            profile = await memory_svc.get_profile()
            subjects = profile.get("subjects", {})
            weak_lines = []
            for subj, stats in subjects.items():
                total = stats.get("total", 0)
                correct = stats.get("correct", 0)
                if total >= 3:
                    acc = correct / total if total else 0
                    if acc < 0.6:
                        weak_lines.append(f"{subj}: {int(acc*100)}% ({correct}/{total})")
            if weak_lines:
                memory_context += "\n━━ STUDY INTEL (from profile) ━━\nWeak topics: " + "; ".join(weak_lines[:5])
                if profile.get("last_active"):
                    memory_context += f"\nLast active: {profile.get('last_active')}"
        except Exception as e:
            logger.debug("Study intel enrichment failed: %s", e)

    # ── Step 4: Build master system prompt ──
    citation_svc.register_sources(
        web_results=search_results,
        kb_results=kb_results if 'kb_results' in dir() else None,
        doc_content=doc_text,
        youtube_results=youtube_results,
        cross_check=cross_check,
    )

    system_prompt = _build_system_prompt(
        intents, search_results, vision_text,
        doc_text, memory_context, youtube_results, config, cross_check, kb_context,
        max_chars=(config.get("max_prompt_chars", 20000) if isinstance(config, dict) else 20000),
    )
    try:
        logger.info("Prompt ready: %d chars (intents=%s)", len(system_prompt), intents[:5])
    except Exception:
        pass

    # ── Step 4b: Detect language and inject context ──
    detected_lang = detect_message_language(message)
    if detected_lang:
        system_prompt += (
            f"\nThe user is writing in {detected_lang}. "
            f"Respond in {detected_lang} for this entire conversation.\n"
        )

    # ── Step 4c: Apply mode adjustments ──
    if mode == "think":
        system_prompt += (
            "\n\nIMPORTANT: You are in THINK MODE. Take your time to reason deeply.\n"
            "Show your thinking process step by step before giving the final answer.\n"
            "Consider multiple approaches. Check your work. Be thorough.\n"
        )
    elif mode == "fast":
        system_prompt += (
            "\n\nIMPORTANT: You are in FAST MODE. Give a quick, concise answer.\n"
            "Be brief — just the key facts or answer, no lengthy explanations.\n"
        )
    elif mode == "socratic":
        system_prompt += (
            "\n\nIMPORTANT: You are in SOCRATIC TUTORING MODE.\n"
            "NEVER give direct answers. Instead, guide the student with questions:\n"
            "1. Start by asking what they already know about the topic.\n"
            "2. Ask guiding questions that lead them toward the answer.\n"
            "3. If they get stuck, give a small hint (not the answer).\n"
            "4. Only after 2-3 failed attempts, provide the answer WITH explanation.\n"
            "5. After revealing the answer, ask: 'Does that make sense? What would you try differently next time?'\n"
            "6. Celebrate their reasoning process, not just correct answers.\n"
            "Example: Instead of 'The answer is 42', ask 'What do you think the first step should be?'\n"
        )
    elif mode == "hype":
        system_prompt += (
            "\n\nIMPORTANT: You are in HYPE TUTOR MODE — maximum energy, zero boredom.\n"
            "Explain like a hype-man who genuinely wants the student to WIN:\n"
            "1. Bring the energy: punchy lines, caps for key moments, a fire emoji here and there — but never more hype than substance.\n"
            "2. Every fact earns its place: intuition first, then ONE killer worked example with every step shown.\n"
            "3. Translate everything into MARKS: 'here's why this exact step is free marks on the exam'.\n"
            "4. Call out the trap: one common mistake, framed as 'don't you dare lose marks here'.\n"
            "5. End with a 1-line dare: one check question for the student to attempt right now.\n"
            "NEVER sacrifice correctness for vibes: every formula, date and calculation stays exact. No made-up facts, no skipping algebra.\n"
        )
    elif mode == "voice":
        system_prompt += VOICE_MODE_SUFFIX

    # ── Step 5: Study tool handling (cheatsheet, worksheet, todos) ──
    reasoning_model = models.get("reasoning", _main_model(config))
    fallback_model  = models.get("fallback", reasoning_model)
    full_response   = ""
    is_hard = any(i in intents for i in {"math","formula","coding","geography","history","science","worksheet_solver","explain"})
    if mode == "think":
        context_window = 16384
    elif any(i in intents for i in {"quiz","flashcard","worksheet_generator","cheatsheet","exam_sim","audio_overview","study_intel"}):
        context_window = 8192
    elif is_hard:
        context_window = 12288
    else:
        context_window = 8192
    if doc_text and len(doc_text) > 4000:
        context_window = 16384
    worksheet_handled = False

    if "cheatsheet" in intents and "worksheet_generator" not in intents:
        try:
            m = re.search(r"cheat[\s\-]?sheet\s*(?:on|for|about)?\s*[:\-]?\s*(.+)", message, re.I)
            cs_topic = (m.group(1).strip() if m else message.strip())[:150]
            cs_topic = re.sub(r"^(a|an|the)\s+", "", cs_topic, flags=re.I)
            cs_topic = re.sub(r"\b(generate|create|make|build|give me|please)\b", "", cs_topic, flags=re.I).strip(" -:") or message.strip()[:80]
            yield _sse({"type": "status", "content": f"Building one-page cheat sheet on {cs_topic}..."})
            cs_model = models.get("reasoning", _main_model(config))
            sheet_md = await study_svc.generate_cheatsheet(cs_topic, "", cs_model)
            chunk_size = 60
            for i in range(0, len(sheet_md), chunk_size):
                yield _sse({"type": "text", "content": sheet_md[i:i+chunk_size]})
                await asyncio.sleep(0.01)
            yield _sse({"type": "extras", "content": {"cheatsheet": sheet_md}})
            yield _sse({"type": "tool", "tool": "cheatsheet", "content": {"topic": cs_topic}})
            full_response = sheet_md
            worksheet_handled = True
        except Exception as e:
            logger.warning(f"Cheatsheet generation failed, falling back to chat: {e}")

    if "worksheet_generator" in intents:
        try:
            m = re.search(r"worksheet\s*(?:on|for|about)?\s*[:\-]?\s*(.+)", message, re.I)
            topic = (m.group(1).strip() if m else message.strip())[:120]
            topic = re.sub(r"^(a|an|the)\s+", "", topic, flags=re.I)
            topic = re.sub(r"\b(generate|create|make|build)\b", "", topic, flags=re.I).strip(" -:") or message.strip()[:80]
            gm = re.search(r"(year|grade|yr)\s*(\d{1,2})", message, re.I)
            grade = f"Year {gm.group(2)}" if gm else "Year 8"
            qm = re.search(r"(\d+)\s*(questions|qs)", message, re.I)
            qcount = int(qm.group(1)) if qm else 10
            qcount = max(5, min(20, qcount))

            yield _sse({"type": "status", "content": f"Generating worksheet on {topic} ({grade})..."})
            ws_model = models.get("reasoning", _main_model(config))
            worksheet_md = await study_svc.generate_worksheet(topic, grade, qcount, True, ws_model)

            chunk_size = 60
            for i in range(0, len(worksheet_md), chunk_size):
                chunk = worksheet_md[i:i+chunk_size]
                yield _sse({"type": "text", "content": chunk})
                await asyncio.sleep(0.01)

            yield _sse({"type": "extras", "content": {"worksheet": worksheet_md}})
            yield _sse({"type": "tool", "tool": "worksheet", "content": {"topic": topic, "grade": grade, "count": qcount}})

            full_response = worksheet_md
            worksheet_handled = True
        except Exception as e:
            logger.warning(f"Worksheet generation failed, falling back to chat: {e}")

    # ── Step 5a: Todo handling ──
    todo_handled = False
    if "todo" in intents and not worksheet_handled:
        try:
            from services.todo_service import add_todo, parse_due_date, parse_estimate, parse_priority
            import re as _re
            raw = message.strip()
            task_text = _re.sub(r"^\s*(add|create|new)\s+(todo\s+)?", "", raw, flags=_re.I)
            subjects = ["maths","mathematics","english","science","biology","chemistry","physics","history","geography","pdhpe","technology","art","music","commerce","economics"]
            subject = "General"
            for subj in subjects:
                if _re.match(rf"^{subj}\b", task_text, _re.I):
                    subject = subj.capitalize()
                    task_text = _re.sub(rf"^{subj}\b\s*[:\-]?\s*", "", task_text, flags=_re.I)
                    break
            due = parse_due_date(message)
            est = parse_estimate(message) or 30
            prio = parse_priority(message) or "medium"
            todo = add_todo(subject, task_text.strip() or raw, due, est, prio)
            yield _sse({"type": "tool", "tool": "todo", "content": todo})
            msg = f"Added ✅ **{todo['subject']}**: {todo['task']}"
            if todo['due_date']:
                msg += f" (due {todo['due_date']}, {todo['estimated_mins']}m, {todo['priority']})"
            yield _sse({"type": "text", "content": msg})
            full_response = msg
            todo_handled = True
        except Exception as e:
            logger.warning(f"Todo creation failed: {e}")

    if "list_todos" in intents and not todo_handled and not worksheet_handled:
        try:
            from services.todo_service import list_todos
            todos = list_todos()
            yield _sse({"type": "tool", "tool": "todos", "content": todos[:5]})
            if todos:
                text = "Your todos:\n" + "\n".join(f"- **{t['subject']}**: {t['task']} (due {t.get('due_date','—')}, {t['estimated_mins']}m, {t['priority']}) {'✓' if t.get('completed') else ''}" for t in todos[:5])
                if len(todos) > 5:
                    text += f"\n...and {len(todos)-5} more"
            else:
                text = "You have no todos — all caught up! 🎉"
            yield _sse({"type": "text", "content": text})
            full_response = text
            todo_handled = True
        except Exception as e:
            logger.warning(f"List todos failed: {e}")

    # ── Step 5b: Stream reasoning model ──
    reasoning_model = models.get("reasoning", _main_model(config))
    fallback_model  = models.get("fallback", reasoning_model)
    if not worksheet_handled and not todo_handled:
        yield _sse({"type": "progress", "step": "reasoning", "status": "running", "pct": 75, "label": f"Thinking with {reasoning_model}"})
        yield _sse({"type": "status", "content": f"Thinking with {reasoning_model}..."})
        _mark("prompt_ready")

        hard_intents = {"math", "formula", "coding", "geography", "history", "science", "worksheet_solver", "explain"}
        # Day 40: voice answers must start fast — reasoning preambles cost
        # ~10 s TTFT on-device and can't be spoken anyway. Measured live:
        # TTFS 10.0 s with think vs TTS 0.8 s; think is the whole budget.
        stream_think = (mode == "think" or any(i in intents for i in hard_intents)) and mode != "voice"
        for attempt, model_name in enumerate([reasoning_model, fallback_model]):
            try:
                async for token in ollama.stream(model_name, system_prompt, message, context_window=context_window, think=stream_think):
                    if "ttft" not in _marks:
                        _mark("ttft")
                    full_response += token
                    yield _sse({"type": "text", "content": token})
                yield _sse({"type": "progress", "step": "reasoning", "status": "done", "pct": 95, "label": "Answer complete"})
                _mark("llm_done")
                break
            except Exception as e:
                if attempt == 0:
                    yield _sse({"type": "status",
                        "content": f"{model_name} unavailable, trying {fallback_model}..."})
                    continue
                try:
                    from services.telemetry_service import record_crash
                    record_crash("ollama", e)
                except Exception:
                    pass
                yield _sse({"type": "error",
                    "content": (
                        "Study Buddy's AI engine isn't responding.\n\n"
                        "Click the status dot in the top bar to retry, or run:\n"
                        f"  ollama pull {reasoning_model}\n\n"
                        "then restart Study Buddy. Your chats are safe."
                    )})
                yield _sse({"type": "done"})
                return

    # ── Step 6: Parse citations ──
    _, parsed_citations = citation_svc.parse_citations(full_response)
    source_list = citation_svc.get_source_list()
    if source_list:
        yield _sse({"type": "sources", "content": source_list})
    if parsed_citations:
        yield _sse({"type": "citations", "content": [c.to_dict() for c in parsed_citations]})

    yield _sse({"type": "progress", "step": "extras", "status": "running", "pct": 97, "label": "Building extras"})

    # ── Step 6b: Structured extras + reliability checks (parallel) ──
    extras_task = asyncio.create_task(
        _generate_extras(intents, message, full_response, reasoning_model, config)
    )
    verify_task = None
    if needs_cross_check and cross_check and len(full_response) > 100:
        verify_task = asyncio.create_task(
            _verify_answer(message, full_response, cross_check)
        )
    suggest_task = None
    if len(full_response) > 150 and "translate" not in intents:
        suggest_task = asyncio.create_task(
            _generate_suggestions(message, full_response)
        )
    math_verify_task = None
    if any(i in intents for i in {"math", "formula"}):
        math_verify_task = asyncio.create_task(_verify_math_via_code(message, full_response))
    self_check_task = None
    if len(full_response) > 200:
        self_check_task = asyncio.create_task(_self_check_critic(message, full_response, reasoning_model))

    extras = await extras_task
    if extras:
        yield _sse({"type": "extras", "content": extras})

    if verify_task:
        verification = await verify_task
        if verification:
            yield _sse({"type": "verification", "content": verification})

    if math_verify_task:
        math_ver = await math_verify_task
        if math_ver:
            yield _sse({"type": "verification", "content": math_ver})

    if self_check_task:
        critic = await self_check_task
        if critic and not critic.get("ok"):
            yield _sse({"type": "verification", "content": {"verified": False, "notes": critic.get("notes","Self-check flagged potential error")}})

    if suggest_task:
        suggestions = await suggest_task
        if suggestions:
            yield _sse({"type": "suggestions", "content": suggestions})

    yield _sse({"type": "progress", "step": "extras", "status": "done", "pct": 99, "label": "Extras ready"})

    # ── Step 6c: Cross-check sources ──
    if cross_check:
        yield _sse({"type": "tool", "tool": "cross_check", "content": cross_check[:4]})

    # ── Step 6d: Image generation ──
    if "image_gen" in intents and config.get("image_gen_enabled", True):
        yield _sse({"type": "progress", "step": "image", "status": "running", "pct": 92, "label": "Generating image with FLUX diffusion"})
        try:
            from services.imagegen_service import ImageGenService
            img_svc = ImageGenService()
            poll_model = config.get("pollinations_model", "flux")
            clean = re.sub(
                r"^\s*(please\s+)?(draw|generate|create|paint|make|sketch|illustrate)\s+(an?\s+)?(image|picture|illustration|diagram|poster|drawing|artwork)?\s*(of|showing|about)?\s*",
                "", message, flags=re.I
            ).strip()
            prompt = clean if len(clean) >= 3 else message.strip()
            prompt = prompt[:400]
            result = await img_svc.generate(prompt, model=poll_model, width=512, height=512)
            img_url = result.get("image") if isinstance(result, dict) else None
            if img_url:
                yield _sse({"type": "image", "content": img_url})
                yield _sse({"type": "progress", "step": "image", "status": "done", "pct": 96, "label": "Image ready"})
                yield _sse({"type": "tool", "tool": "image_gen", "content": {"prompt": prompt, "model": poll_model}})
            else:
                err = result.get("error", "Image generation failed") if isinstance(result, dict) else "Image generation failed"
                yield _sse({"type": "progress", "step": "image", "status": "error", "pct": 95, "label": err[:80]})
        except Exception as e:
            logger.warning("Image generation failed: %s", e)
            yield _sse({"type": "progress", "step": "image", "status": "error", "pct": 95, "label": f"Image gen error: {str(e)[:60]}"})

    # ── Step 6e: Diagram generation ──
    _refers_to_attached = has_image and re.search(
        r"\b(this|that|the)\s+(diagram|image|photo|picture|figure|chart)\b", message, re.I
    ) and not re.search(
        r"\b(draw|generate|create|make)\b.{0,20}\b(another|new|second|also|own)\b", message, re.I
    )
    if "diagram" in intents and not _refers_to_attached:
        yield _sse({"type": "progress", "step": "diagram", "status": "running", "pct": 92, "label": "Designing visual"})
        try:
            from services.diagram_service import DiagramService, detect_visual_type
            diag_svc = DiagramService()
            clean = re.sub(
                r"^\s*(please\s+)?(draw|generate|create|make|sketch|show|give)\s+(me\s+)?(an?\s+)?(diagram|flowchart|chart|graph|map|figure|illustration|picture)?\s*(of|for|showing|that shows|about)?\s*",
                "", message, flags=re.I
            ).strip()
            prompt = (clean if len(clean) >= 3 else message.strip())[:400]
            visual_hint = detect_visual_type(message)
            result = await diag_svc.generate(prompt, visual_type=visual_hint)
            if isinstance(result, dict) and result.get("type") == "napkin" and "spec" in result:
                yield _sse({"type": "diagram", "content": result})
                yield _sse({"type": "progress", "step": "diagram", "status": "done", "pct": 96, "label": "Visual ready — edit it inline"})
                yield _sse({"type": "tool", "tool": "diagram", "content": {"prompt": prompt, "kind": result["spec"].get("visual_type")}})
            else:
                err = result.get("error", "Diagram failed") if isinstance(result, dict) else "Diagram failed"
                yield _sse({"type": "progress", "step": "diagram", "status": "error", "pct": 95, "label": err[:80]})
        except Exception as e:
            logger.warning("Diagram generation failed: %s", e)
            yield _sse({"type": "progress", "step": "diagram", "status": "error", "pct": 95, "label": f"Diagram error: {str(e)[:60]}"})

    # ── Auto-generate geometry diagrams for math angle topics ──
    if "diagram" not in intents and "math" in intents:
        _geom_kw = re.search(
            r"\b(angle|vertex|ray|complement|supplement|protract|parallel|perpendicular|straight line|around a point)\b",
            message, re.I
        )
        if _geom_kw and not _refers_to_attached:
            try:
                from services.diagram_service import DiagramService
                diag_svc = DiagramService()
                result = await diag_svc.generate(message[:400], visual_type="geometry")
                if isinstance(result, dict) and result.get("type") == "napkin" and "spec" in result:
                    yield _sse({"type": "diagram", "content": result})
            except Exception:
                pass  # Non-critical — don't block the response

    # ── Step 7: Persist memory ──
    if config.get("memory_enabled") and memory_svc is not None and full_response:
        try:
            await memory_svc.save(conversation_id, message, full_response)
            try:
                title = await memory_svc.get_title(conversation_id)
                if title:
                    yield _sse({"type": "title", "content": title, "conversation_id": conversation_id})
                try:
                    from models.database import DATA_DIR as _DD
                    import json as _js
                    _cj = _DD / "conversations.json"
                    if _cj.exists():
                        _data = _js.loads(_cj.read_text(encoding="utf-8"))
                        _turns = _data.get(conversation_id, [])
                        if len(_turns) >= 3:
                            import asyncio as _aio
                            try:
                                new_title = await _aio.wait_for(
                                    memory_svc.regenerate_title(conversation_id, use_llm=True), timeout=4
                                )
                                if new_title and new_title != title:
                                    yield _sse({"type": "title", "content": new_title, "conversation_id": conversation_id})
                            except _aio.TimeoutError:
                                pass
                except Exception:
                    pass
            except Exception:
                pass
        except Exception as e:
            logger.debug("Memory save failed: %s", e)

    # ── Step 8: Check gamification achievements ──
    try:
        from services.gamification_service import GamificationService
        from services.memory_service import MemoryService as _MS
        game_svc = GamificationService()
        mem_tmp = _MS()
        profile = await mem_tmp.get_profile()
        convs = await mem_tmp.get_conversations()
        new_achievements = game_svc.check_and_award_achievements(profile, convs)
        if new_achievements:
            progress = game_svc.get_progress()
            yield _sse({"type": "achievement", "content": {
                "new": new_achievements,
                "xp": progress.get("xp", 0),
                "level": progress.get("level", 1),
            }})
    except Exception as e:
        logger.debug("Gamification check failed: %s", e)

    yield _sse({"type": "progress", "step": "done", "status": "done", "pct": 100, "label": "Done"})
    _mark("total")
    yield _sse({"type": "timings", "content": dict(_marks)})
    yield _sse({"type": "done"})
