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
from services.knowledge_graph_service import KnowledgeGraphService
from services.knowledge_base_service import KnowledgeBaseService

ollama       = OllamaService()
image_svc    = ImageService()
memory_svc   = MemoryService()
research_svc = ResearchService()
study_svc    = StudyService()
youtube_svc  = YouTubeService()
doc_svc      = DocumentService()
kg_svc       = KnowledgeGraphService()
kb_svc       = KnowledgeBaseService()


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
        r"\b(flashcards?|flash cards?|memoris|memoriz|key terms|study cards)\b",
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
        r"\b(solve|calculate|equation|algebra|calculus|differentiate|integrate)\b",
        r"\b(area|volume|perimeter|gradient|probability|statistics|matrix|vector|fraction)\b",
        r"[\d]+\s*[\+\-\*\/\^]\s*[\d]",
    ],
    "geography": [
        r"\b(geography|continent|country|capital city|population|climate|terrain|landscape)\b",
        r"\b(river|mountain|ocean|sea|lake|desert|forest|island|peninsula|strait)\b",
        r"\b(latitude|longitude|hemisphere|equator|tropic|time zone|timezone)\b",
        r"\b(urba|suburb|rural|settlement|migration|demograph|economy|trade|import|export)\b",
        r"\b(ecosystem|biome|erosion|weathering|plate tectonic|earthquake|volcano)\b",
        r"\b(map|globe|atlas|compass|scale|grid reference|aerial photograph)\b",
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
    "translate": [
        r"\b(translat\w*|traducir|übersetzen|traduire|tradurre|переведи|翻訳|번역|번역해|번역해줘|翻译|번역하기|번역해 주세요)\b",
        r"\b(in english|en anglais|auf english|en español|auf spanisch|по английски|英語で|영어로)\b",
    ],
    "doc_chat":         [],   # set by chat router when doc is attached
    "video_summarise":  [],   # set when youtube_results present
}

# ── Language detection ────────────────────────────────────────────────────────
_NON_ENGLISH_INDICATORS = [
    (r"[\uac00-\ud7af]{3,}", "Korean"),
    (r"[\u3040-\u309f\u30a0-\u30ff]{3,}", "Japanese"),
    (r"[\u4e00-\u9fff]{3,}", "Chinese"),
    (r"[\u0600-\u06ff]{3,}", "Arabic"),
    (r"[\u0900-\u097f]{3,}", "Hindi"),
    (r"[\u0b80-\u0bff]{3,}", "Tamil"),
    (r"[\u0400-\u04ff]{3,}", "Russian"),
    (r"\b(por favor|gracias|buenos dias|como estas|necesito|ayuda|tengo|traducir|en espanol)\b", "Spanish"),
    (r"\b(sil vous plait|merci|bonjour|comment|je veux|traduire|en francais)\b", "French"),
    (r"\b(bitte|danke|guten tag|wie|ich brauche|ich helfe|ich will)\b", "German"),
    (r"\b(per favore|grazie|buongiorno|come|ho bisogno|aiuto|voglio)\b", "Italian"),
]


def detect_message_language(message: str) -> str | None:
    for pattern, lang in _NON_ENGLISH_INDICATORS:
        if re.search(pattern, message, re.I):
            return lang
    return None


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
        "essay_feedback", "formula", "timeline", "translate",
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
    cross_check_intents = {"explain", "math", "formula", "timeline", "summary", "worksheet_solver", "notes", "geography"}
    needs_cross_check = bool(cross_check_intents & set(intents))

    if "web_search" in intents and config.get("web_search_enabled", True):
        parallel["search"] = research_svc.search(message)
    if needs_cross_check and config.get("web_search_enabled", True):
        parallel["cross_check"] = research_svc.search(message, max_results=4)
    if "youtube" in intents:
        urls = re.findall(r"https?://(?:www\.)?(?:youtube\.com|youtu\.be)\S+", message)
        if urls:
            parallel["youtube"] = youtube_svc.process(urls[0])

    search_results  = None
    youtube_results = None
    cross_check     = None

    if parallel:
        results = await asyncio.gather(*parallel.values(), return_exceptions=True)
        for key, result in zip(parallel.keys(), results):
            if isinstance(result, Exception):
                continue
            if key == "search":
                search_results = result
                yield _sse({"type": "tool", "tool": "web_search", "content": (search_results or [])[:3]})
            elif key == "cross_check":
                cross_check = result
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

    # ── Step 3b: Knowledge Base RAG search ───────────────────────────────────
    kb_context = ""
    if config.get("knowledge_base_enabled", True):
        try:
            kb_results = await kb_svc.search(message, n_results=5)
            if kb_results:
                kb_parts = []
                for r in kb_results:
                    src = r.get("metadata", {}).get("source", "unknown")
                    score = r.get("score", 0)
                    if score > 0.3:  # relevance threshold
                        kb_parts.append(f"[KB:{src}] {r['text'][:500]}")
                if kb_parts:
                    kb_context = "\n\n".join(kb_parts)
                    yield _sse({"type": "tool", "tool": "knowledge_base", "content": kb_results[:3]})
        except Exception:
            pass

    # ── Step 4: Build master system prompt ────────────────────────────────────
    system_prompt = _build_system_prompt(
        intents, search_results, vision_text,
        doc_text, memory_context, youtube_results, config, cross_check, kb_context
    )

    # ── Step 4b: Detect language and inject context ──────────────────────────
    detected_lang = detect_message_language(message)
    if detected_lang:
        system_prompt += (
            f"\nThe user is writing in {detected_lang}. "
            f"Respond in {detected_lang} for this entire conversation.\n"
        )

    # ── Step 4c: Apply mode adjustments ───────────────────────────────────────
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

    # ── Step 6: Structured extras + reliability checks (run in parallel) ──────
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

    extras = await extras_task
    if extras:
        yield _sse({"type": "extras", "content": extras})

    if verify_task:
        verification = await verify_task
        if verification:
            yield _sse({"type": "verification", "content": verification})

    if suggest_task:
        suggestions = await suggest_task
        if suggestions:
            yield _sse({"type": "suggestions", "content": suggestions})

    # ── Step 6b: Send cross-check sources to frontend ──────────────────────
    if cross_check:
        yield _sse({"type": "tool", "tool": "cross_check", "content": cross_check[:4]})

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

    # ── Step 8: Save to memory + extract knowledge graph ────────────────────────
    if full_response and config.get("memory_enabled", True):
        try:
            await memory_svc.save(conversation_id, message, full_response)
        except Exception:
            pass
        try:
            await kg_svc.extract_and_store(conversation_id, message, full_response)
        except Exception:
            pass

    yield _sse({"type": "done"})


# ── System prompt ─────────────────────────────────────────────────────────────

def _build_system_prompt(
    intents, search_results, vision_text, doc_text,
    memory_context, youtube_results, config, cross_check=None, kb_context=None
) -> str:
    name = config.get("student_name", "Student")
    age  = config.get("student_age",  13)

    parts = [
        f"You are ARIA, a brilliant and encouraging AI tutor for {name} (age {age}).",
        "You are warm, patient, and always explain things clearly — step by step.",
        "You celebrate effort, gently correct mistakes, and use real-world examples.",
        "You are expert in: maths, science, history, geography, English literature, coding, and all school subjects.",
        "",
        "LANGUAGE RULE: Match the language the user writes in.",
        "If the user writes in English, respond in English.",
        "If the user writes in Tamil, respond in Tamil.",
        "If the user writes in Korean, respond in Korean.",
        "If the user writes in any other language, respond in that same language.",
        "Keep the same language for the entire conversation.",
        "",
    ]

    # ── NSW Curriculum Knowledge ───────────────────────────────────────────────
    # ARIA automatically knows the NSW syllabus for this student's stage
    try:
        from services.nsw_curriculum_service import NSWCurriculumService, NSW_STAGES
        from services.advanced_study_service import AdvancedStudyIntelligence
        _curr = NSWCurriculumService()
        _adv = AdvancedStudyIntelligence()
        stage = _curr.get_stage_for_age(age)
        if stage:
            stage_info = NSW_STAGES.get(stage, {})
            parts += [
                f"━━ NSW CURRICULUM CONTEXT ━━",
                f"Student is in {stage_info.get('name', 'Stage 4')} (ages {stage_info.get('ages', '11-14')}, Year {stage_info.get('years', '7-8')}).",
                "You MUST align your teaching with the NSW Education Standards Authority (NESA) syllabus.",
                "Reference specific curriculum outcomes (e.g. MA4-1WM, EN4-1A, SC4-10ES) when relevant.",
                "Use the terminology and content progression expected for this stage.",
                "For Maths: follow the NSW Mathematics syllabus (Number & Algebra, Measurement & Geometry, Statistics & Probability).",
                "For Science: follow the NSW Science & Technology syllabus (Living World, Earth & Space, Physical World, Chemical World).",
                "For English: follow the NSW English syllabus (Responding & Composing, Understanding & Using Language, Thinking Critically).",
                "For History: follow the NSW History syllabus (Historical Skills, Historical Concepts & Terms, Contextual Knowledge).",
                "For Geography: follow the NSW Geography syllabus (Geographical Inquiry, Spatial Significance, Interconnections).",
                "",
            ]
            # Inject specific content only for the subject being asked about
            subject_map = {
                "math": "mathematics", "formula": "mathematics",
                "geography": "geography",
                "explain": None, "chat": None,  # general — inject nothing
            }
            injected = set()
            for intent in intents:
                kla = subject_map.get(intent)
                if kla and kla not in injected:
                    injected.add(kla)
                    content = _curr.get_subject_content(kla, stage)
                    if content:
                        parts.append(f"Stage {stage.replace('S','').replace('ES1','0')} {kla.title()} covers: {'; '.join(content[:5])}")
            parts.append("")
    except Exception:
        pass  # Graceful fallback if curriculum service unavailable

    if memory_context:
        parts += [
            "━━ MEMORY (from past conversations) ━━",
            memory_context,
            "Use this to personalise your response and build on prior knowledge.",
            "",
        ]

    if kb_context:
        parts += [
            "━━ KNOWLEDGE BASE (from indexed documents) ━━",
            kb_context,
            "Use this information to answer the student's question. Cite the source document when relevant.",
            "If the knowledge base contains relevant information, prioritise it over general knowledge.",
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
    if "geography" in intents:
        parts += [
            "GEOGRAPHY MODE: Use real-world examples and maps where possible.",
            "Reference specific countries, cities, and landmarks. Include key facts and statistics.",
            "If discussing climate or ecosystems, mention Australian examples where relevant.",
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
    if "translate" in intents:
        parts += [
            "TRANSLATION MODE: Translate the content accurately while preserving meaning and tone.",
            "If a target language is specified, translate to that language.",
            "If no target language is specified, detect the user's native language from the message and translate to English.",
            "Include the original text and the translation clearly separated.",
            "For complex phrases, provide context and usage examples.",
            "",
        ]

    if cross_check:
        parts += [
            "━━ INTERNET CROSS-CHECK (for accuracy) ━━",
            "The following web results were found to verify your answer:",
            *[f"[{i+1}] {r['title']}: {r['snippet'][:200]}" for i, r in enumerate(cross_check[:4])],
            "**CITATIONS:** Support your key facts with the web results by adding the result number",
            "in square brackets right after the fact, e.g. 'The Nile is 6,650 km long [1]'.",
            "After your answer, add a short section:",
            "**Verify:** [Confirm or correct your answer using the web results above. If any facts differ, note the correction.]",
            "**Sources:** [List the web result numbers you cited, with their titles and URLs]",
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


# ── Answer verification (2nd-model cross-check) ───────────────────────────────

async def _verify_answer(
    question: str, answer: str, evidence: list[dict], model: str = "llama3.2:3b"
) -> dict | None:
    """Check the answer's facts against web evidence with an independent model."""
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


# ── Follow-up suggestions (NotebookLM-style) ──────────────────────────────────

async def _generate_suggestions(
    question: str, answer: str, model: str = "llama3.2:3b"
) -> list[str] | None:
    """Generate 3 short follow-up questions the student would likely ask next."""
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
                m = re.search(r"correct\s*[):.\s]+([A-Da-d])", line, re.I)
                if m:
                    q["correct"] = m.group(1).upper()
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
