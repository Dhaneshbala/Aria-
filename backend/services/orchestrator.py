"""
ARIA Orchestrator — The Brain
─────────────────────────────
Tuned for MacBook Air M4, 16 GB unified memory.

Model strategy (one loaded at a time to protect RAM):
  • qwen3:8b        → reasoning, chat, study tools  (5.2 GB, ~8 tok/s on M4)
  • qwen2.5vl:3b   → vision, image reading, OCR     (4.9 GB)
  • qwen2.5:3b     → fallback for simple questions  (2.0 GB, very fast)

Ollama auto-swaps models — only one sits in RAM at a time.
Vision model is called first (fast), then unloaded before reasoning runs.
"""

import asyncio
import json
import re
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

from services.ollama_service import OllamaService
from services.image_service import ImageService
from services.memory_service import MemoryService
from services.research_service import ResearchService
from services.study_service import StudyService
from services.youtube_service import YouTubeService
from services.document_service import DocumentService

ollama       = OllamaService()
image_svc    = ImageService()
memory_svc   = MemoryService()
research_svc = ResearchService()
study_svc    = StudyService()
youtube_svc  = YouTubeService()
doc_svc      = DocumentService()


# ── Intent detection ──────────────────────────────────────────────────────────

INTENT_PATTERNS = {
    "image_analysis": [
        r"\.(jpg|jpeg|png|gif|webp|bmp)$",
        r"\b(look at|read this|what.*image|what.*photo|what.*picture)\b",
        r"\b(worksheet|diagram|handwriting|ocr|scan|handwritten)\b",
    ],
    "quiz": [
        r"\b(quiz|test me|practice question|multiple.?choice|quizme)\b",
        r"\b(olympiad|apsmo|amc|competition question)\b",
    ],
    "exam_mode": [
        r"\b(exam mode|exam question|past paper|mark scheme|timed question)\b",
    ],
    "flashcard": [
        r"\b(flashcard|flash card|memoris|memoriz|key terms|study cards)\b",
    ],
    "mindmap": [
        r"\b(mind.?map|concept map|visualis|visualiz|branch diagram|topic map)\b",
    ],
    "study_plan": [
        r"\b(study plan|study schedule|revision plan|how.*study|prepare.*exam)\b",
    ],
    "notes": [
        r"\b(study notes|take notes|create notes|make notes|cornell|outline notes|notes on|notes about)\b",
    ],
    "worksheet_solver": [
        r"\b(solve.*worksheet|help.*worksheet|answer.*question|question \d+|problem \d+)\b",
        r"\b(homework help|help.*homework|do.*question|work.*through)\b",
    ],
    "quote_extraction": [
        r"\b(quote[s]?|passage[s]?|excerpt[s]?|extract.*text|text.*about)\b",
        r"\b(evidence|example[s]?.*from|find.*in.*pdf|lines.*about)\b",
        r"\b(essay|theme|diversity|acceptance|justice|identity|courage|friendship)\b.*\b(quote|passage|text|evidence)\b",
    ],
    "pdf_summarise": [
        r"\b(summarise.*pdf|summarize.*pdf|summarise.*document|summarize.*document)\b",
        r"\b(summarise.*file|what.*does.*pdf|overview.*document|what.*book.*about)\b",
    ],
    "youtube": [
        r"https?://(?:www\.)?(?:youtube\.com|youtu\.be)\S+",
        r"\b(youtube.*url|video.*url|watch.*video|transcript.*video)\b",
    ],
    "web_search": [
        r"\b(search|look up|find.*info|latest|current|news|today|recent)\b",
        r"\b(what happened|who is.*now|how many.*currently)\b",
    ],
    "image_gen": [
        r"\b(draw|generate.*image|create.*image|paint|illustrate|make.*picture|sketch)\b",
        r"\b(generate.*diagram|create.*poster|draw.*map)\b",
    ],
    "math": [
        r"\b(solve|calculate|equation|algebra|geometry|calculus|differentiate|integrate)\b",
        r"\b(area|volume|perimeter|gradient|probability|statistics|matrix|vector|fraction)\b",
        r"[\d]+\s*[\+\-\*\/\^]\s*[\d]",
    ],
    "summary": [
        r"\b(summarise|summarize|summary|tldr|brief overview|key points|main idea|overview)\b",
    ],
    "explain": [
        r"\b(explain|what is|how does|why does|tell me about|describe|what are|define)\b",
    ],
    "coding": [
        r"\b(code|coding|program|programming|function|class|method|debug|refactor)\b",
        r"\b(python|javascript|java|c\+\+|html|css|sql|react|node)\b",
        r"\b(git|github|commit|branch|merge|pull request|repository)\b",
        r"\b(docker|container|terminal|command line|bash|shell|script)\b",
        r"\b(explain.*code|what.*does.*code|how.*does.*code|write.*function)\b",
        r"\b(unit test|test|api|database|sql|regex)\b",
    ],
    "essay_feedback": [
        r"\b(essay feedback|review.*essay|grade.*essay|improve.*essay|mark.*essay)\b",
        r"\b(essay.*improve|essay.*better|essay.*grade|check.*essay)\b",
    ],
    "formula": [
        r"\b(formula|equation|theorem|proof|derivation)\b",
        r"\b(scientific|chemistry|physics|biology formula)\b",
    ],
    "timeline": [
        r"\b(timeline|chronological|historical.*order|sequence.*events)\b",
        r"\b(what happened.*when|order.*events|history.*of)\b",
    ],
    "doc_chat":         [],   # set by chat router when doc is attached
    "video_summarise":  [],   # set when youtube_results present
}


def detect_intents(message: str, has_image: bool = False, has_doc: bool = False) -> list[str]:
    msg = message.lower()
    intents = []
    if has_image:
        intents.append("image_analysis")
    if has_doc:
        intents.append("doc_chat")
    for intent, patterns in INTENT_PATTERNS.items():
        if any(re.search(p, msg, re.I) for p in patterns):
            if intent not in intents:
                intents.append(intent)
    if not intents:
        intents.append("chat")
    return intents


def choose_models(intents: list[str], config: dict) -> dict:
    """
    Return which model handles which role.
    On 16 GB M4: vision and reasoning swap — never both loaded simultaneously.
    """
    models = {}
    if "image_analysis" in intents:
        models["vision"] = config.get("vision_model", "qwen2.5vl:3b")
    # Everything else → reasoning model
    reasoning_intents = {
        "quiz", "exam_mode", "flashcard", "mindmap", "study_plan", "notes",
        "worksheet_solver", "quote_extraction", "pdf_summarise",
        "math", "explain", "chat", "summary", "doc_chat",
        "web_search", "youtube", "video_summarise", "code", "coding",
        "essay_feedback", "formula", "timeline",
    }
    if any(i in intents for i in reasoning_intents):
        if "code" in intents or "coding" in intents:
            models["reasoning"] = config.get("coding_model", "qwen2.5-coder:7b")
        else:
            models["reasoning"] = config.get("reasoning_model", "qwen3:8b")
    return models


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
    config    = config or {}
    has_image = image_data is not None
    has_doc   = doc_text is not None

    intents = detect_intents(message, has_image, has_doc)
    models  = choose_models(intents, config)

    logger.info("Orchestrating: intents=%s, models=%s, mode=%s", intents, models, mode)
    yield _sse({"type": "intent", "content": intents})

    # ── Step 1: Parallel lightweight tasks (no LLM yet) ───────────────────────
    parallel = {}
    if "web_search" in intents and config.get("web_search_enabled", True):
        parallel["search"] = research_svc.search(message)
    if "youtube" in intents:
        urls = re.findall(r"https?://(?:www\.)?(?:youtube\.com|youtu\.be)\S+", message)
        if urls:
            parallel["youtube"] = youtube_svc.process(urls[0])

    search_results  = None
    youtube_results = None

    if parallel:
        results = await asyncio.gather(*parallel.values(), return_exceptions=True)
        for key, result in zip(parallel.keys(), results):
            if isinstance(result, Exception):
                continue
            if key == "search":
                search_results = result
                yield _sse({"type": "tool", "tool": "web_search", "content": (search_results or [])[:3]})
            elif key == "youtube":
                youtube_results = result
                yield _sse({"type": "tool", "tool": "youtube", "content": youtube_results})

    # ── Step 2: Vision model (runs first, then Ollama unloads it) ─────────────
    # On 16 GB M4 this matters: vision model frees ~5 GB before reasoning loads
    vision_text = None
    if "image_analysis" in intents and image_data:
        vision_model = models.get("vision", "qwen2.5vl:3b")
        yield _sse({"type": "status", "content": f"Reading image with {vision_model}..."})
        try:
            vision_text = await image_svc.analyse(
                image_data, image_mime or "image/jpeg", vision_model
            )
            yield _sse({"type": "tool", "tool": "vision", "content": vision_text})
            # Unload vision model immediately — frees ~5 GB RAM for reasoning model
            await ollama.unload_model(vision_model)
        except Exception as e:
            vision_text = f"[Vision model unavailable — using OCR: {e}]"
            yield _sse({"type": "status", "content": "Vision unavailable, falling back to OCR..."})

    # ── Step 3: Memory retrieval (fast, ChromaDB or JSON) ─────────────────────
    memory_context = ""
    if config.get("memory_enabled", True):
        try:
            memories = await memory_svc.retrieve(conversation_id, message, k=4)
            if memories:
                memory_context = "\n".join(f"[Memory] {m}" for m in memories)
        except Exception:
            pass

    # ── Step 4: Build master system prompt ────────────────────────────────────
    system_prompt = _build_system_prompt(
        intents, search_results, vision_text,
        doc_text, memory_context, youtube_results, config
    )

    # ── Step 4b: Apply mode adjustments ───────────────────────────────────────
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

    # ── Step 5: Stream reasoning model ───────────────────────────────────────
    reasoning_model = models.get("reasoning", config.get("reasoning_model", "qwen3:8b"))
    fallback_model  = config.get("fallback_model", "qwen2.5:3b")
    full_response   = ""
    context_window  = 8192 if mode == "think" else 4096

    yield _sse({"type": "status", "content": f"Thinking with {reasoning_model}..."})

    # Try reasoning model, then fallback
    for attempt, model_name in enumerate([reasoning_model, fallback_model]):
        try:
            async for token in ollama.stream(model_name, system_prompt, message, context_window=context_window):
                full_response += token
                yield _sse({"type": "text", "content": token})
            break  # success
        except Exception as e:
            if attempt == 0:
                # First model failed — try fallback
                yield _sse({"type": "status",
                    "content": f"{model_name} unavailable, trying {fallback_model}..."})
                continue
            # Both failed
            yield _sse({"type": "error",
                "content": (
                    f"No AI model available.\n\n"
                    f"Run this in Terminal:\n"
                    f"  ollama pull {reasoning_model}\n\n"
                    f"Then restart ARIA."
                )})
            yield _sse({"type": "done"})
            return

    # ── Step 6: Structured extras (quiz, flashcards, mindmap, study plan) ─────
    extras = await _generate_extras(intents, message, full_response, reasoning_model, config)
    if extras:
        yield _sse({"type": "extras", "content": extras})

    # ── Step 7: Image generation (Pollinations.ai — free, no GPU needed) ───────
    if "image_gen" in intents and config.get("image_gen_enabled", True):
        yield _sse({"type": "status", "content": "Generating image..."})
        try:
            from services.imagegen_service import ImageGenService
            img_svc = ImageGenService()
            poll_model = config.get("pollinations_model", "flux")
            prompt = re.sub(
                r"\b(draw|generate|create|paint|make|sketch|illustrate)\b[\s\w]*?(an?\s+)?(image|picture|illustration|diagram|poster)?\s*(of|showing|about)?\s*",
                "", message, flags=re.I
            ).strip() or message
            result = await img_svc.generate(prompt, model=poll_model)
            img_url = result.get("image") if isinstance(result, dict) else None
            if img_url:
                yield _sse({"type": "image", "content": img_url})
        except Exception as e:
            yield _sse({"type": "status", "content": f"Image gen error: {e}"})

    # ── Step 8: Save to memory ────────────────────────────────────────────────
    if full_response and config.get("memory_enabled", True):
        try:
            await memory_svc.save(conversation_id, message, full_response)
        except Exception:
            pass

    yield _sse({"type": "done"})


# ── System prompt ─────────────────────────────────────────────────────────────

def _build_system_prompt(
    intents, search_results, vision_text, doc_text,
    memory_context, youtube_results, config
) -> str:
    name = config.get("student_name", "Student")
    age  = config.get("student_age",  13)

    parts = [
        f"You are ARIA, a brilliant and encouraging AI tutor for {name} (age {age}).",
        "You are warm, patient, and always explain things clearly — step by step.",
        "You celebrate effort, gently correct mistakes, and use real-world examples.",
        "You are expert in: maths, science, history, geography, English literature, coding, and all school subjects.",
        "",
    ]

    if memory_context:
        parts += [
            "━━ MEMORY (from past conversations) ━━",
            memory_context,
            "Use this to personalise your response and build on prior knowledge.",
            "",
        ]

    if vision_text:
        parts += [
            "━━ IMAGE / WORKSHEET ANALYSIS ━━",
            vision_text,
            "The student uploaded an image. Use this analysis to answer their question.",
            "If it is a worksheet, work through each question carefully with full working.",
            "",
        ]

    if doc_text:
        parts += [
            "━━ DOCUMENT CONTENT (smart-retrieved relevant sections) ━━",
            doc_text,
            "Answer the student's question using the document above.",
            "Always cite page numbers (e.g. 'On page 3...').",
            "For quotes: pull exact text from the document — do not invent quotes.",
            "If the specific page is not included, say 'this may be on another page'.",
            "",
        ]

    if search_results:
        parts += [
            "━━ LIVE WEB SEARCH RESULTS ━━",
            *[f"• {r['title']}: {r['snippet']}" for r in (search_results or [])[:5]],
            "Use this current information in your answer. Mention the source.",
            "",
        ]

    if youtube_results and not (isinstance(youtube_results, dict) and youtube_results.get("error")):
        title      = youtube_results.get("title", "Unknown")
        transcript = youtube_results.get("transcript", "")[:3000]
        parts += [
            "━━ YOUTUBE VIDEO ━━",
            f"Title: {title}",
            f"Transcript: {transcript}",
            "Summarise and answer questions using this video content.",
            "",
        ]

    # Intent-specific instructions
    if "worksheet_solver" in intents:
        parts += [
            "WORKSHEET MODE: Work through every question one by one.",
            "Show full working. Explain each step. Use the image/document above.",
            "Number your answers to match the question numbers.",
            "",
        ]
    if "quote_extraction" in intents and doc_text:
        parts += [
            "QUOTE MODE: The student wants quotes from the document for an essay.",
            "Find direct quotes from the document text above (exact words, in quotation marks).",
            "Include the page number for each quote.",
            "Group quotes by sub-theme. Explain briefly why each quote is relevant.",
            "Format: '\"[exact quote]\" (p. X) — [brief explanation]'",
            "",
        ]
    if "pdf_summarise" in intents and doc_text:
        parts += [
            "SUMMARY MODE: Give a comprehensive summary of the uploaded document.",
            "Include: main topic, key arguments/events, important details, conclusion.",
            "Use clear headings. Note page numbers for key sections.",
            "",
        ]
    if "quiz" in intents or "exam_mode" in intents:
        parts += [
            "QUIZ MODE: Generate exactly 5 multiple-choice questions.",
            "Format each as:",
            "Q1: [question]",
            "A) option  B) option  C) option  D) option",
            "Correct: [letter]",
            "Explanation: [one sentence]",
            "",
        ]
    if "flashcard" in intents:
        parts += [
            "FLASHCARD MODE: After your explanation generate 8 flashcards.",
            "Format each as: FRONT: [term or question] | BACK: [definition or answer]",
            "",
        ]
    if "mindmap" in intents:
        parts += [
            "MIND MAP: After your explanation output JSON on its own line:",
            '{"mindmap": {"center": "topic", "branches": [{"label": "Branch", "children": ["child1", "child2"]}]}}',
            "4–6 branches, 2–4 children each.",
            "",
        ]
    if "study_plan" in intents:
        parts += [
            "STUDY PLAN: Output a JSON study plan on its own line:",
            '[{"day": 1, "title": "...", "tasks": ["task1", "task2"], "time_minutes": 45}]',
            "",
        ]
    if "notes" in intents:
        parts += [
            "NOTES MODE: Write structured study notes with clear headings,",
            "key terms highlighted, examples, and a summary section.",
            "",
        ]
    if "math" in intents:
        parts += [
            "MATHS MODE: Show every step of working. Explain WHY each step is done.",
            "Check the answer. Offer one similar practice problem at the end.",
            "",
        ]
    if "explain" in intents:
        parts += [
            "EXPLANATION MODE: Use analogies and everyday examples.",
            "Build from simple → complex. Auto-flashcards will be generated.",
            "",
        ]
    if "summary" in intents and "pdf_summarise" not in intents:
        parts += [
            "Give a clear summary: key points, key vocabulary, one-sentence takeaway.",
            "",
        ]
    if "coding" in intents:
        parts += [
            "CODE MODE: Write clean, well-commented code.",
            "Explain the logic step by step. Show working examples.",
            "If debugging: identify the bug, explain why it fails, show the fix.",
            "If generating a project: include file structure, all files, and setup instructions.",
            "Use best practices: error handling, meaningful names, DRY principle.",
            "",
        ]
    if "essay_feedback" in intents:
        parts += [
            "ESSAY FEEDBACK MODE: Analyse the essay thoroughly.",
            "Provide feedback on: thesis strength, argument structure, evidence quality,",
            "grammar/spelling, flow/coherence, vocabulary, and conclusion.",
            "Give specific suggestions for improvement with examples.",
            "Rate overall: Needs Work / Good / Very Good / Excellent.",
            "",
        ]
    if "formula" in intents:
        parts += [
            "FORMULA MODE: Explain all relevant formulas for this topic.",
            "For each formula: name, equation, variable definitions, when to use it.",
            "Show a worked example. Include common mistakes to avoid.",
            "",
        ]
    if "timeline" in intents:
        parts += [
            "TIMELINE MODE: Create a clear chronological timeline.",
            "Include dates/periods, key events, cause-and-effect relationships.",
            "Format as a structured timeline with clear markers.",
            "",
        ]

    return "\n".join(parts)


# ── Extras generator ──────────────────────────────────────────────────────────

async def _generate_extras(
    intents: list[str], message: str, response: str,
    model: str, config: dict
) -> dict:
    extras = {}

    if "quiz" in intents or "exam_mode" in intents:
        q = _parse_quiz(response)
        if q:
            extras["quiz"] = q

    if "flashcard" in intents:
        fc = _parse_flashcards(response)
        if fc:
            extras["flashcards"] = fc

    if "mindmap" in intents:
        mm = _parse_mindmap(response)
        if mm:
            extras["mindmap"] = mm

    if "study_plan" in intents:
        sp = _parse_study_plan(response)
        if sp:
            extras["study_plan"] = sp

    # Auto-generate flashcards from any long explanation (no explicit request needed)
    auto_fc_triggers = {"explain", "worksheet_solver", "math", "summary", "doc_chat", "pdf_summarise"}
    if (auto_fc_triggers & set(intents)) and len(response) > 300 and "flashcard" not in intents:
        try:
            fc_prompt = (
                "Based on this content, generate 6 clear flashcards.\n"
                "Format: FRONT: [term or question] | BACK: [answer]\n\n"
                + response[:1800]
            )
            fc_resp = await ollama.complete(model, fc_prompt,
                "Generate concise educational flashcards.")
            parsed = _parse_flashcards(fc_resp)
            if parsed:
                extras["auto_flashcards"] = parsed
        except Exception:
            pass

    # Auto-generate 3 practice questions after worksheet solving
    if "worksheet_solver" in intents and len(response) > 200 and "quiz" not in intents:
        try:
            topic = message[:80]
            qdata = await study_svc.generate_quiz(topic, "medium", 3, model)
            if qdata:
                extras["practice_quiz"] = qdata
        except Exception:
            pass

    return extras


# ── Parsers ───────────────────────────────────────────────────────────────────

def _parse_quiz(text: str) -> list[dict]:
    questions = []
    blocks = re.split(r"\bQ\d+[:.)\s]", text)
    for block in blocks[1:]:
        lines = [l.strip() for l in block.strip().split("\n") if l.strip()]
        if not lines:
            continue
        q = {"question": lines[0], "options": [], "correct": "", "explanation": ""}
        for line in lines[1:]:
            if re.match(r"^[A-D][.)]\s*", line):
                q["options"].append(re.sub(r"^[A-D][.)]\s*", "", line).strip())
            elif re.match(r"(?i)^correct[:\s]", line):
                m = re.search(r"[A-D]", line)
                if m:
                    q["correct"] = m.group()
            elif re.match(r"(?i)^explanation[:\s]", line) or (q["correct"] and len(line) > 15):
                q["explanation"] = (q["explanation"] + " " + line).strip()
        if len(q["options"]) >= 2:
            questions.append(q)
    return questions[:10]


def _parse_flashcards(text: str) -> list[dict]:
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


def _parse_mindmap(text: str) -> dict | None:
    for pattern in [
        r'\{"mindmap"\s*:\s*\{.*?\}\s*\}',
        r'\{[^{}]*"center"[^{}]*"branches".*?\}',
    ]:
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group())
                return data.get("mindmap", data)
            except Exception:
                pass
    return None


def _parse_study_plan(text: str) -> list[dict] | None:
    m = re.search(r'\[.*?\{.*?"day".*?\}.*?\]', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    return None


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"
