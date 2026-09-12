"""
ARIA Orchestrator — The Brain
─────────────────────────────
Tuned for MacBook Air M4, 16 GB unified memory.

Model strategy (16 GB unified memory — single generation model):
  • gemma4:e4b-mlx  → all generation: chat, reasoning, tutoring, math,
                    coding, vision/multimodal, worksheet/image analysis,
                    tool calling, planning. Multimodal so one model
                    handles images without swapping.
  • nomic-embed-text → embeddings ONLY for memory/RAG retrieval

Memory optimisation:
  • Only one large generation model loaded at a time (gemma)
  • Default context 8K (8192) for normal conversations; 16K only for
    large docs / think mode. Avoids large KV-cache RAM.
  • Unload vision model only if it differs from main (not needed for gemma)
  • Reuses OllamaService concurrency guard (max 2 parallel calls)

Architecture makes it easy to add a specialist model later if testing
proves one is genuinely necessary — extend choose_models() and config.
"""

import asyncio
import json
import re
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

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
# Memory & KB use nomic-embed-text for retrieval (not generation)
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


# ── Intent detection ──────────────────────────────────────────────────────────

INTENT_PATTERNS = {
    "image_analysis": [
        r"\.(jpg|jpeg|png|gif|webp|bmp)$",
        r"\b(look at|read this|what.*image|what.*photo|what.*picture)\b",
        r"\b(worksheet|diagram|handwriting|ocr|scan|handwritten)\b",
    ],
    "quiz": [
        r"\b(quiz|test me|practice questions?|multiple.?choice|quizme)\b",
        r"\b(olympiad|apsmo|amc|competition question)\b",
    ],
    "exam_mode": [
        r"\b(exam mode|exam question|past paper|mark scheme|timed question)\b",
    ],
    "flashcard": [
        r"\b(flashcards?|flash cards?|memoris|memoriz|key terms|study cards)\b",
    ],
    "notes": [
        r"\b(study notes|take notes|create notes|make notes|cornell|outline notes|notes on|notes about)\b",
    ],
    "worksheet_solver": [
        r"\b(solve.*worksheet|help.*worksheet|answer.*question|question \d+|problem \d+)\b",
        r"\b(homework help|help.*homework|do.*question|work.*through)\b",
        r"\b(worksheet|homework)\b",
    ],
    "worksheet_generator": [
        r"\b(generate|create|make|build|design).{0,20}worksheet\b",
        r"\bworksheet.{0,20}(on|for|about|grade|year|topic)\b",
        r"\bworksheet generator\b",
        r"\bcreate\b.*\bworksheet\b",
    ],
    "todo": [
        r"\b(add|create|new)\s+.*\b(todo|task|assignment|homework)\b",
        r"\b(todo|assignment|homework)\s+(due|for|on)\b",
        r"\b(remind me|remember to)\b",
    ],
    "list_todos": [
        r"\b(show|list|what are|my)\s+.*\b(todos|tasks|assignments|homework|due)\b",
        r"\b(what.*due|due.*today|due.*tomorrow)\b",
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
    "diagram": [
        r"\b(diagram of|draw .*diagram|diagram for|diagram showing|diagram that shows)\b",
        r"\b(with|include|including|add)\s+(a\s+)?diagrams?\b",
        r"\bexplain\b.{0,40}\b(diagram|flowchart|visual|mindmap)\b",
        r"\b(diagram|flowchart|visual)\b.{0,40}\b(explain|explanation)\b",
        r"\b(mind.?map|concept map|branch diagram|topic map)\b",
        r"\b(visualis|visualiz)(e|ation)?\b",
        r"\b(flowchart|flow chart|venn diagram|number line|circuit diagram|factor tree|probability tree)\b",
        r"\b(graph of y|plot .*\(.*\)|pie chart|bar chart|timeline of|label.*diagram)\b",
        r"\b(plot|graph|draw)\b.{0,25}\b(y\s*(=|equals)|parabola|coordinate|intercept|x\s*squared)\b",
        r"\bparabola\b|\bvenn\b|\bprotractor\b",
        r"\b(graph|plot)\b.{0,20}\bline\b",
    ],
    "math": [
        r"\b(solve|calculate|evaluate|simplify|expand|factor|differentiate|integrate)\b",
        r"\b(solve|calculate|find).*equation\b",
        r"\b(linear|quadratic|simultaneous|algebraic).*equation\b",
        r"\b(algebra|calculus|geometry|trigonometry|angle|vertex|triangle|quadrilateral|polygon|circle|parallel|perpendicular|congruent|similar)\b",
        r"\b(area|volume|perimeter|gradient|probability|statistics|matrix|vector|fraction|angle|vertex|hypotenuse|radius|diameter|circumference)\b",
        r"\b\angle\b|\bPQR\b|\bXYZ\b",
        r"[\d]+\s*[\+\-\*\/\^]\s*[\d]",
    ],
    "geography": [
        r"\b(geography|continent|country|capital city|population|climate|terrain|landscape)\b",
        r"\b(rivers?|mountains?|oceans?|seas?|lakes?|deserts?|forests?|islands?|peninsulas?|straits?)\b",
        r"\b(latitude|longitude|hemisphere|equator|tropic|time zone|timezone)\b",
        r"\b(urba|suburb|rural|settlement|migration|demograph|economy|trade|import|export)\b",
        r"\b(ecosystems?|biomes?|erosion|weathering|plate tectonic|earthquakes?|volcanoes?)\b",
        r"\b(map|globe|atlas|compass|scale|grid reference|aerial photograph)\b",
    ],
    "summary": [
        r"\b(summarise|summarize|summary|tldr|brief overview|key points|main idea|overview)\b",
    ],
    "explain": [
        r"\b(explain|what is|how does|why does|tell me about|describe|what are|define)\b",
    ],
    "coding": [
        r"\b(code|coding|program|programming|debug|refactor|script|regex)\b",
        r"\b(python|javascript|java|c\+\+|html|css|sql|react|node\.?js)\b",
        r"\b(git|github|commit|branch|merge|pull request|repository)\b",
        r"\b(docker|container|terminal|command line|bash|shell)\b",
        r"\b(explain|fix|debug|review|understand|write|generate|check) .*(code|function|class|method|program|script|bug|error)\b",
        r"\b(unit test|test case|api call|database schema|sql query|stack trace)\b",
    ],
    "essay_feedback": [
        r"\b(essay feedback|review.*essay|grade.*essay|improve.*essay|mark.*essay)\b",
        r"\b(essay.*improve|essay.*better|essay.*grade|check.*essay)\b",
    ],
    "formula": [
        r"\b(formula|theorem|proof|derivation)\b",
        r"\b(scientific|chemistry|physics|biology formula)\b",
    ],
    "timeline": [
        r"\b(timeline|chronological|historical.*order|sequence.*events)\b",
        r"\b(what happened.*when|order.*events|history.*of)\b",
    ],
    "exam_sim": [
        r"\b(exam sim|exam simulation|timed exam|mock exam|practice exam|simulate.*exam)\b",
        r"\b(start.*exam|exam.*practice|test.*simulation)\b",
    ],
    "audio_overview": [
        r"\b(audio overview|audio summary|audio guide|listen.*overview|podcast.*topic)\b",
        r"\b(generate.*audio|create.*audio|audio.*explanation|explain.*audio style)\b",
    ],
    "study_intel": [
        r"\b(study intel|study intelligence|weak topics?|what.*should.*study|revision needs?)\b",
        r"\b(what.*to.*study.*next|my.*progress|how.*am.*doing|study.*recommendation)\b",
        r"\b(weak.*areas?|gaps.*knowledge|what.*am.*weak.*in)\b",
    ],
    "translate": [
        r"\b(translat\w*|traducir|übersetzen|traduire|tradurre|переведи|翻訳|번역|번역해|번역해줘|翻译|번역하기|번역해 주세요)\b",
        r"\b(in english|en anglais|auf english|en español|auf spanisch|по английски|英語で|영어로)\b",
    ],
    "socratic": [
        r"\b(socratic|tutor me|guide me|don.t tell me|help me figure|walk me through)\b",
        r"\b(don.t give.*answer|make me think|lead me|guide my thinking|ask me questions)\b",
        r"\b(socratic method|discovery learning|figure it out|teach me how to think)\b",
    ],
    "roleplay": [
        r"\b(roleplay|pretend|act as|simulate|interview|debate|scenario)\b",
        r"\b(be a|you are a|imagine.*you.*are|as if you were|play the role)\b",
        r"\b(historical figure|scientist|character|persona|from the perspective)\b",
    ],
    "multiple_methods": [
        r"\b(multiple ways|different method|another way|alternative solution|2 ways|3 ways|several approaches)\b",
        r"\b(show me another|is there a faster|what.s another way|compare methods)\b",
    ],
    "doc_chat":         [],   # set by chat router when doc is attached
    "video_summarise":  [],   # set when youtube_results present
}

# ── Language detection ────────────────────────────────────────────────────────
_NON_ENGLISH_INDICATORS = [
    (r"[\uac00-\ud7af]{3,}", "Korean"),
    (r"[\u3040-\u309f\u30a0-\u30ff]{3,}", "Japanese"),
    (r"[\u4e00-\u9fff]{2,}", "Chinese"),
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


# Single source of truth — import from database
try:
    from models.database import MODELS
except Exception:
    MODELS = {
        "main": "gemma4:e4b-mlx",
        "embedding": "nomic-embed-text",
    }

def _main_model(config: dict) -> str:
    """Resolve the main generation model with legacy fallback."""
    return (
        config.get("model")
        or config.get("reasoning_model")
        or MODELS["main"]
    )

def choose_models(intents: list[str], config: dict) -> dict:
    """
    Return which model handles which role.
    16 GB optimisation: single generation model (gemma4:e4b-mlx) handles
    reasoning, coding, vision, and multimodal. No separate vision/coding
    models loaded — avoids RAM pressure. Easy to extend later if a
    specialist is proven necessary (e.g. add config['specialist_model']).
    """
    main = _main_model(config)
    models: dict = {}
    # Vision: gemma4 is multimodal, so same model handles images.
    # Keep a separate 'vision' key so the orchestrator can stream a
    # "Reading image..." status, but it points to the same model.
    if "image_analysis" in intents:
        # Use vision_model if user has set a specialist, else main
        vm = config.get("vision_model", main)
        # Migrate legacy qwen vl if present
        if vm in ("qwen2.5vl:3b", "qwen2.5vl:7b", "llava", "llava:13b"):
            vm = main
        models["vision"] = vm
    # Everything else → main model
    reasoning_intents = {
        "quiz", "exam_mode", "flashcard", "notes",
        "worksheet_solver", "worksheet_generator", "quote_extraction", "pdf_summarise",
        "math", "explain", "chat", "summary", "doc_chat",
        "web_search", "youtube", "video_summarise", "code", "coding",
        "essay_feedback", "formula", "timeline", "translate",
        "exam_sim", "audio_overview", "study_intel", "todo", "list_todos",
        "image_gen", "diagram",
    }
    if any(i in intents for i in reasoning_intents):
        models["reasoning"] = main
        # fallback is same model — no second large model needed for normal operation
        models["fallback"] = main
    # If no reasoning intent matched but we have no models yet (e.g. unknown intent),
    # ensure we still have a reasoning model
    if not models:
        models["reasoning"] = main
        models["fallback"] = main
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
    # explain alone is common (what is...), only hard when combined with factual/scientific content
    is_hard = any(i in intents for i in {"math","formula","coding","geography","history","science","worksheet_solver"})
    if "explain" in intents and any(i in intents for i in {"math","formula","coding","geography","history","science"}):
        is_hard = True

    logger.info("Orchestrating: intents=%s, models=%s, mode=%s", intents, models, mode)
    yield _sse({"type": "intent", "content": intents})
    yield _sse({"type": "progress", "step": "intent", "status": "done", "pct": 10, "label": "Understanding request"})
    try:
        from services.telemetry_service import record_event
        record_event("orchestrate", intents=",".join(intents[:5]), mode=mode)
    except Exception:
        pass

    # ── Step 1: Parallel lightweight tasks — Google is primary source ─────────
    parallel = {}
    cross_check_intents = {"explain", "math", "formula", "timeline", "summary", "worksheet_solver", "notes", "geography", "coding", "history", "science", "study_intel"}
    needs_cross_check = bool(cross_check_intents & set(intents))

    web_enabled = config.get("web_search_enabled", True)
    google_first = config.get("google_first", True)

    # Google-first — smart+fast: search only when it helps, bigger for hard
    google_intents = {"explain", "chat", "summary", "math", "geography", "formula", "timeline", "notes", "coding", "history", "science", "worksheet_solver", "doc_chat", "study_intel", "translate", "socratic", "roleplay"}
    if web_enabled:
        if "web_search" in intents:
            parallel["search"] = research_svc.search(message, max_results=6 if is_hard else 5)
        elif google_first and any(i in intents for i in google_intents):
            parallel["search"] = research_svc.search(message, max_results=6 if is_hard else 5)
        if needs_cross_check and "search" not in parallel:
            parallel["cross_check"] = research_svc.search(message, max_results=5)
    if "youtube" in intents:
        urls = re.findall(r"https?://(?:www\.)?(?:youtube\.com|youtu\.be)\S+", message)
        if urls:
            parallel["youtube"] = youtube_svc.process(urls[0])

    search_results  = None
    youtube_results = None
    cross_check     = None

    if parallel:
        # Progress: show what's running in parallel
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

    # ── Step 2: Vision (gemma4:e4b-mlx is multimodal — same model handles vision) ──
    # No separate vision model to load/unload; saves RAM switching.
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
            # Only unload if vision model differs from main model (gemma: same → skip)
            main_m = _main_model(config)
            if vision_model != main_m:
                await ollama.unload_model(vision_model)
        except Exception as e:
            vision_text = f"[Vision model unavailable — using OCR: {e}]"
            yield _sse({"type": "progress", "step": "vision", "status": "error", "pct": 60, "label": "Vision fallback to OCR"})
            yield _sse({"type": "status", "content": "Vision unavailable, falling back to OCR..."})

    # ── Step 3: Memory & Knowledge Base (optional, via nomic-embed-text) ─────
    # Memory optimisation: only use if enabled; embeddings use nomic, not gemma.
    memory_context = ""
    kb_context = ""
    kb_results = []
    kb_offer = None
    if config.get("memory_enabled") and memory_svc is not None:
        yield _sse({"type": "progress", "step": "memory", "status": "running", "pct": 45, "label": "Checking memory"})
        try:
            # Retrieve memories — 5 for hard (power), 3 for simple (speed), same quality via nomic warmup
            mem_k = 5 if is_hard else 3
            memories = await asyncio.wait_for(
                memory_svc.retrieve(conversation_id, message, k=mem_k), timeout=12
            )
            if memories:
                memory_context = "\n".join(memories[:6 if is_hard else 4])
            yield _sse({"type": "progress", "step": "memory", "status": "done", "pct": 55, "label": f"Memory {len(memories) if memories else 0} hits"})
        except asyncio.TimeoutError:
            logger.debug("Memory retrieve timed out (nomic slow/missing) — skipping")
            yield _sse({"type": "progress", "step": "memory", "status": "error", "pct": 50, "label": "Memory skip (timeout)"})
        except Exception as e:
            logger.debug("Memory retrieve failed: %s", e)
            yield _sse({"type": "progress", "step": "memory", "status": "error", "pct": 50, "label": "Memory skip"})
    if config.get("knowledge_base_enabled") and kb_svc is not None:
        yield _sse({"type": "progress", "step": "kb", "status": "running", "pct": 55, "label": "Searching knowledge base"})
        try:
            kb_n = 6 if is_hard else 4
            # Intent-aware collection filtering — so nomic-embed-text searches the right shards
            if any(i in intents for i in {"math","formula","worksheet_solver","explain"}):
                kb_cols = ["math","education_au","general","science"]
            elif "geography" in intents:
                kb_cols = ["geography","education_au","general"]
            elif "history" in intents:
                kb_cols = ["history","education_au","general"]
            elif "coding" in intents or "code" in intents:
                kb_cols = ["coding","general"]
            else:
                kb_cols = None  # all collections
            kb_results = await asyncio.wait_for(
                kb_svc.search(message, collections=kb_cols, n_results=kb_n), timeout=12
            )
            if kb_results:
                kb_context = "\n".join(r["text"][:500] for r in kb_results[:5 if is_hard else 3])
            yield _sse({"type": "progress", "step": "kb", "status": "done", "pct": 65, "label": f"KB {len(kb_results)} hits" if kb_results else "KB no hits"})
        except asyncio.TimeoutError:
            logger.debug("KB search timed out (nomic slow/missing) — skipping")
            yield _sse({"type": "progress", "step": "kb", "status": "error", "pct": 60, "label": "KB skip (timeout)"})
        except Exception as e:
            logger.debug("KB search failed: %s", e)
            yield _sse({"type": "progress", "step": "kb", "status": "error", "pct": 60, "label": "KB skip"})

    # ── Step 3b: Study Intel enrichment (profile-based) ─────────────────────
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

    # ── Step 4: Build master system prompt ────────────────────────────────────
    # Register sources for citation tracking
    citation_svc.register_sources(
        web_results=search_results,
        kb_results=kb_results if 'kb_results' in dir() else None,
        doc_content=doc_text,
        youtube_results=youtube_results,
        cross_check=cross_check,
    )

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

    # ── Step 5: Worksheet generation (handled directly via study service) ─────
    # Smart+Fast: adaptive context — 8K for quick chat (fast), 12K for hard, 16K for think/docs
    reasoning_model = models.get("reasoning", _main_model(config))
    fallback_model  = models.get("fallback", reasoning_model)
    full_response   = ""
    is_hard = any(i in intents for i in {"math","formula","coding","geography","history","science","worksheet_solver","explain"})
    if mode == "think":
        context_window = 16384
    elif any(i in intents for i in {"quiz","flashcard","worksheet_generator","exam_sim","audio_overview","study_intel"}):
        context_window = 8192
    elif is_hard:
        context_window = 12288  # hard topics: bigger context for power
    else:
        context_window = 8192  # simple chat: 8K = fastest, same quality via prompt
    if doc_text and len(doc_text) > 4000:
        context_window = 16384
    worksheet_handled = False

    if "worksheet_generator" in intents:
        try:
            # Extract topic: text after "worksheet on/for/about" or fallback to full message
            m = re.search(r"worksheet\s*(?:on|for|about)?\s*[:\-]?\s*(.+)", message, re.I)
            topic = (m.group(1).strip() if m else message.strip())[:120]
            # Strip common filler
            topic = re.sub(r"^(a|an|the)\s+", "", topic, flags=re.I)
            topic = re.sub(r"\b(generate|create|make|build)\b", "", topic, flags=re.I).strip(" -:") or message.strip()[:80]
            # Detect grade/year
            gm = re.search(r"(year|grade|yr)\s*(\d{1,2})", message, re.I)
            grade = f"Year {gm.group(2)}" if gm else "Year 8"
            qm = re.search(r"(\d+)\s*(questions|qs)", message, re.I)
            qcount = int(qm.group(1)) if qm else 10
            qcount = max(5, min(20, qcount))

            yield _sse({"type": "status", "content": f"Generating worksheet on {topic} ({grade})..."})
            ws_model = models.get("reasoning", _main_model(config))
            worksheet_md = await study_svc.generate_worksheet(topic, grade, qcount, True, ws_model)

            # Stream the worksheet as markdown chunks so frontend shows progressively
            chunk_size = 60
            for i in range(0, len(worksheet_md), chunk_size):
                chunk = worksheet_md[i:i+chunk_size]
                yield _sse({"type": "text", "content": chunk})
                await asyncio.sleep(0.01)

            # Also send as structured extras for the worksheet renderer + export button
            yield _sse({"type": "extras", "content": {"worksheet": worksheet_md}})
            yield _sse({"type": "tool", "tool": "worksheet", "content": {"topic": topic, "grade": grade, "count": qcount}})

            full_response = worksheet_md
            worksheet_handled = True
        except Exception as e:
            logger.warning(f"Worksheet generation failed, falling back to chat: {e}")

    # ── Step 5a: Todo handling (solo organization) ──────────────────────────
    todo_handled = False
    if "todo" in intents and not worksheet_handled:
        try:
            from services.todo_service import add_todo, parse_due_date, parse_estimate, parse_priority
            import re as _re
            # Parse subject/task from message
            raw = message.strip()
            # Remove leading add/create
            task_text = _re.sub(r"^\s*(add|create|new)\s+(todo\s+)?", "", raw, flags=_re.I)
            # Extract subject if known
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

    # ── Step 5b: Stream reasoning model ───────────────────────────────────────
    # Single main model for normal operation; fallback is same model.
    reasoning_model = models.get("reasoning", _main_model(config))
    fallback_model  = models.get("fallback", reasoning_model)
    if not worksheet_handled and not todo_handled:
        yield _sse({"type": "progress", "step": "reasoning", "status": "running", "pct": 75, "label": f"Thinking with {reasoning_model}"})
        yield _sse({"type": "status", "content": f"Thinking with {reasoning_model}..."})

        # Power: enable deep thinking for hard topics even in normal mode (Astra-like)
        hard_intents = {"math", "formula", "coding", "geography", "history", "science", "worksheet_solver", "explain"}
        stream_think = True if mode == "think" or any(i in intents for i in hard_intents) else False
        # Try reasoning model, then fallback
        for attempt, model_name in enumerate([reasoning_model, fallback_model]):
            try:
                async for token in ollama.stream(model_name, system_prompt, message, context_window=context_window, think=stream_think):
                    full_response += token
                    yield _sse({"type": "text", "content": token})
                yield _sse({"type": "progress", "step": "reasoning", "status": "done", "pct": 95, "label": "Answer complete"})
                break  # success
            except Exception as e:
                if attempt == 0:
                    # First model failed — try fallback
                    yield _sse({"type": "status",
                        "content": f"{model_name} unavailable, trying {fallback_model}..."})
                    continue
                # Both failed
                try:
                    from services.telemetry_service import record_crash
                    record_crash("ollama", e)
                except Exception:
                    pass
                yield _sse({"type": "error",
                    "content": (
                        "ARIA's AI engine isn't responding.\n\n"
                        "Click the status dot in the top bar to retry, or run:\n"
                        f"  ollama pull {reasoning_model}\n\n"
                        "then restart ARIA. Your chats are safe."
                    )})
                yield _sse({"type": "done"})
                return

    # ── Step 5b: Parse citations from response ─────────────────────────────
    _, parsed_citations = citation_svc.parse_citations(full_response)
    source_list = citation_svc.get_source_list()
    if source_list:
        yield _sse({"type": "sources", "content": source_list})
    if parsed_citations:
        yield _sse({"type": "citations", "content": [c.to_dict() for c in parsed_citations]})

    yield _sse({"type": "progress", "step": "extras", "status": "running", "pct": 97, "label": "Building extras"})
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
    # Phase 1 free wins: code exec for math + self-check critic (same gemma4, no RAM cost)
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
            # If critic finds issue, append correction as verification
            yield _sse({"type": "verification", "content": {"verified": False, "notes": critic.get("notes","Self-check flagged potential error")}})

    if suggest_task:
        suggestions = await suggest_task
        if suggestions:
            yield _sse({"type": "suggestions", "content": suggestions})

    yield _sse({"type": "progress", "step": "extras", "status": "done", "pct": 99, "label": "Extras ready"})

    # ── Step 6b: Send cross-check sources to frontend ──────────────────────
    if cross_check:
        yield _sse({"type": "tool", "tool": "cross_check", "content": cross_check[:4]})

    # ── Step 6c: Image generation (Pollinations.ai — FLUX/Sana diffusion, same as top models) ──
    if "image_gen" in intents and config.get("image_gen_enabled", True):
        yield _sse({"type": "progress", "step": "image", "status": "running", "pct": 92, "label": "Generating image with FLUX diffusion"})
        try:
            from services.imagegen_service import ImageGenService
            img_svc = ImageGenService()
            poll_model = config.get("pollinations_model", "flux")
            # Clean prompt: strip leading verbs like "draw/generate an image of"
            clean = re.sub(
                r"^\s*(please\s+)?(draw|generate|create|paint|make|sketch|illustrate)\s+(an?\s+)?(image|picture|illustration|diagram|poster|drawing|artwork)?\s*(of|showing|about)?\s*",
                "", message, flags=re.I
            ).strip()
            # Fallback to full message if cleaning empties it
            prompt = clean if len(clean) >= 3 else message.strip()
            # Limit prompt length for URL safety
            prompt = prompt[:400]
            result = await img_svc.generate(prompt, model=poll_model, width=512, height=512)
            img_url = result.get("image") if isinstance(result, dict) else None
            if img_url:
                yield _sse({"type": "image", "content": img_url})
                yield _sse({"type": "progress", "step": "image", "status": "done", "pct": 96, "label": "Image ready"})
                # Also add to tools so it shows in history
                yield _sse({"type": "tool", "tool": "image_gen", "content": {"prompt": prompt, "model": poll_model}})
            else:
                err = result.get("error", "Image generation failed") if isinstance(result, dict) else "Image generation failed"
                yield _sse({"type": "progress", "step": "image", "status": "error", "pct": 95, "label": err[:80]})
                # Still let the LLM text explain — don't fail the whole chat
        except Exception as e:
            logger.warning("Image generation failed: %s", e)
            yield _sse({"type": "progress", "step": "image", "status": "error", "pct": 95, "label": f"Image gen error: {str(e)[:60]}"})

    # ── Step 6d: Diagram generation (Napkin-style — LLM → spec JSON, frontend renders) ──
    # "Explain THIS diagram" + attached image = explain the existing visual,
    # don't invent a new one (unless they ask for another/new one too).
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
                # LLM text below still explains — chat never fails on diagram alone
        except Exception as e:
            logger.warning("Diagram generation failed: %s", e)
            yield _sse({"type": "progress", "step": "diagram", "status": "error", "pct": 95, "label": f"Diagram error: {str(e)[:60]}"})

    # ── Step 7: Persist memory (if enabled) — nomic-embed-text for retrieval ──
    if config.get("memory_enabled") and memory_svc is not None and full_response:
        try:
            await memory_svc.save(conversation_id, message, full_response)
            # Adaptive title — emit immediately so sidebar updates live (Gemini-style)
            try:
                title = await memory_svc.get_title(conversation_id)
                if title:
                    yield _sse({"type": "title", "content": title, "conversation_id": conversation_id})
                # LLM refinement for longer chats — try quickly, yield second title if improved
                # Only for 3+ turn conversations to keep cost low
                convs_tmp = None
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

    yield _sse({"type": "progress", "step": "done", "status": "done", "pct": 100, "label": "Done"})
    yield _sse({"type": "done"})


# ── System prompt ─────────────────────────────────────────────────────────────

def _build_system_prompt(
    intents, search_results, vision_text, doc_text,
    memory_context, youtube_results, config, cross_check=None, kb_context=None
) -> str:
    name = config.get("student_name", "Student")
    age  = config.get("student_age",  13)

    parts = [
        f"You are ARIA — warm, brilliant tutor for {name} (age {age}), as strong as GPT-6 Astra + Opus 5 Fable but kinder and more patient.",
        "You are top 0.1% in every school subject, you reason like Astra and teach like Fable: you make hard ideas feel easy, you notice effort, you keep the student motivated.",
        "POWER RULES — Be Smarter + Kinder:",
        "- Think step-by-step internally, then give the clearest final answer with every step shown — no skipped algebra.",
        "- Always consider multiple approaches and pick the best one for this student; offer the second method as 'another way'.",
        "- Use the strongest evidence: web results and knowledge base above beat your own memory; cite [1] when you use them.",
        "- If a problem is hard, break it into sub-problems and solve each with a quick check-in.",
        "PRINCIPLES — Mastery + Encouragement:",
        "1) Never just give the answer. First diagnose what the student knows, then scaffold with one hint at a time.",
        "2) For any question, give: a) intuitive explanation + analogy, b) 1 worked example with every step, c) common misconception warning, d) 1 check question for the student to try.",
        "3) When the student is wrong, don't say 'wrong' — ask 'What makes you think that? Have you considered...?' and give a hint, not the answer.",
        "4) Adapt difficulty to age and to memory_context weak_areas — if memory shows weak topic, connect and reinforce it.",
        "5) Always be concise but thorough. No fluff. Use real-world Australian examples where helpful.",
        "6) Verify every fact, date, formula and calculation step-by-step. If using web/KB results, cite them [1]. If unsure, say 'I think' and suggest verifying.",
        f"You are expert in: maths, science, history, geography, English literature, coding, and all school subjects for Year {age-5}-{age-4} NSW syllabus. You solve Olympiad-level problems and explain them simply.",
        "",
        "LANGUAGE RULE: Match the language the user writes in.",
        "If the user writes in English, respond in English.",
        "If the user writes in Tamil, respond in Tamil.",
        "If the user writes in Korean, respond in Korean.",
        "If the user writes in any other language, respond in that same language.",
        "Keep the same language for the entire conversation.",
        "",
        "MATH FORMATTING: When writing math, use LaTeX delimiters:",
        "- Inline math: wrap in single dollar signs, e.g. $x^2 + 3x = 5$",
        "- Display math (standalone equations): wrap in double dollar signs, e.g. $$x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}$$",
        "Never output raw LaTeX commands like \\mathbf or \\underbrace without wrapping them in $ or $$ delimiters.",
        "Plain text examples like '3.14159' should stay as plain text — no LaTeX needed for simple numbers.",
        "",
        "DIAGRAM GENERATION (PREMIUM — make explanations visual and interactive):",
        "When explaining anything spatial or structural (angles, parallel lines, triangles, water cycle, cell, solar system, geometry, maps, processes), ALWAYS include a clear visual diagram. This is mandatory for Year 7 clarity.",
        "FORMAT PREFERENCE (in order):",
        "1. ```svg — PREMIUM VECTOR: Use for precise geometry. Template: <svg width=\"520\" height=\"320\" viewBox=\"0 0 520 320\" xmlns=\"http://www.w3.org/2000/svg\" style=\"background:#fafafa;border-radius:16px;\"><rect width=\"100%\" height=\"100%\" fill=\"#fafafa\" rx=\"16\"/><g font-family=\"Inter,Google Sans,sans-serif\">... content ...</g></svg> Use clean design: #fafafa background, #1e1f20 soft grid (opacity 0.06, 20px), #2d2e30 border, rounded 16px, drop-shadow. Lines: #1e1f20 2.5px, highlight rays: #7c6af7 3px + #f59e0b 3px, arcs: #7c6af7 1.8px dashed, labels: 13px #1e1f20 bold, degree badges: white text on #7c6af7 pill (rx 8). Right angles: small ☐ 10px #f59e0b. Vertex dot: #7c6af7 6px. Add title at top: 14px #5f6368 uppercase tracking-widest.",
        "2. ```mermaid — for cycles/flows/mindmaps. Use: graph TD, flowchart, sequence. Theme will be auto-styled dark (ARIA). Keep nodes short, 3-8 nodes max.",
        "QUALITY BAR (must pass):",
        "- Every ray/line labeled (R1, R2, R3 or A, B, C), every angle has arc + degree pill",
        "- White/very light background for print, not black — ensures Download looks like a textbook figure",
        "- Use <text> with font-family Inter, not default serif; center labels; add <title> for accessibility",
        "- For angles around a point (360°): draw full circle with 4 arcs, each sector different pastel fill (opacity 0.08) — #7c6af7, #f59e0b, #10b981, #ec4899",
        "- For parallel lines: show two horizontals with >> arrows, transversal diagonal, label corresponding/alternate/co-interior with color dots",
        "- Interactive hint: add <g class=\"hover\" data-tooltip> if helpful, but keep static fallback",
        "EXAMPLE SVG for 60°+45° inside 60° (R1-R3=15°): <svg width=\"520\" height=\"280\" viewBox=\"0 0 520 280\" xmlns=\"http://www.w3.org/2000/svg\" style=\"background:#fafafa;border-radius:16px\"><rect width=\"100%\" height=\"100%\" fill=\"#fafafa\" rx=\"16\"/><g stroke=\"#e8eaed\" stroke-width=\"1\" opacity=\"0.6\"><line x1=\"0\" y1=\"40\" x2=\"520\" y2=\"40\"/><line x1=\"0\" y1=\"80\" x2=\"520\" y2=\"80\"/></g><g transform=\"translate(260,180)\"><circle r=\"3\" fill=\"#7c6af7\"/><path d=\"M 100 0 A 100 100 0 0 0 50 -86.6\" fill=\"none\" stroke=\"#7c6af7\" stroke-width=\"2.5\"/><text x=\"70\" y=\"-35\" font-size=\"13\" font-weight=\"700\" fill=\"#7c6af7\">60°</text><path d=\"M 80 0 A 80 80 0 0 0 56.5 -56.5\" fill=\"none\" stroke=\"#f59e0b\" stroke-width=\"2.5\" stroke-dasharray=\"6 4\"/><text x=\"45\" y=\"-15\" font-size=\"11\" fill=\"#f59e0b\">15°</text></g><text x=\"260\" y=\"30\" text-anchor=\"middle\" font-size=\"11\" letter-spacing=\"0.1em\" fill=\"#5f6368\">ANGLES FROM ONE VERTEX</text></svg>",
        "If SVG fails, fallback to box-drawing ┌─┐│└ / \\ → but SVG is strongly preferred and will render with zoom/download controls.",
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
    if "worksheet_generator" in intents:
        parts += [
            "WORKSHEET GENERATOR MODE: The student wants you to CREATE a new worksheet.",
            "Create a professional, Tutero-style worksheet: Title, Learning Intent, Success Criteria,",
            "then 10 questions split into MILD (3), MEDIUM (4), SPICY (3) with increasing difficulty.",
            "Each mild question: MCQ with 4 options A-D. Medium/Spicy: short answer with working space.",
            "End with a separate ANSWER KEY with full worked solutions.",
            "Use NSW curriculum alignment where possible. Make it print-ready markdown.",
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
    if "notes" in intents:
        parts += [
            "NOTES MODE: Write structured study notes with clear headings,",
            "key terms highlighted, examples, and a summary section.",
            "",
        ]
    if "math" in intents:
        parts += [
            "MATHS MODE: Show every step of working. Explain WHY each step is done.",
            "Present 2-3 DIFFERENT SOLUTION METHODS where possible, labelled:",
            "Method 1: [Algebraic/Standard] — the textbook approach",
            "Method 2: [Visual/Number Line/Graphical] — a visual or intuitive way",
            "Method 3: [Working Backwards/Estimation/Simplification] — a shortcut or sanity check",
            "After all methods, show a brief COMPARISON TABLE:",
            "| Method | Speed | Best For | Traps |",
            "End with a similar practice problem.",
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
            "Build from simple → complex.",
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
    if "image_analysis" in intents and vision_text:
        parts += [
            "HANDWRITING/IMAGE GRADING MODE: The student uploaded a handwritten answer (transcribed above).",
            "Grade out of 10 like a fair Year 7 teacher: accuracy, completeness, understanding.",
            "Provide: Score (0-10), 1-2 sentence summary, 2-3 specific tips to improve.",
            "Be encouraging and specific. If a model answer was provided, compare to it.",
            "",
        ]
    if "exam_sim" in intents:
        parts += [
            "EXAM SIMULATION MODE: Generate a timed exam simulation.",
            "Create 10 multiple-choice questions (A-D) with increasing difficulty.",
            "For each: Q: [question] A) B) C) D) Correct: [letter] Explanation: [1 sentence]",
            "After questions, add: Time limit: 20 minutes, Tips: time management & strategy.",
            "Use NSW curriculum alignment where possible.",
            "",
        ]
    if "audio_overview" in intents:
        parts += [
            "AUDIO OVERVIEW MODE: Create a 3-5 minute audio script for this topic.",
            "Structure: Hook (30s why it matters) → Key concepts (3-5 bullets, simple language) → 1-2 formulas if applicable → Real-world example → Encouraging close 'You've got this!'",
            "Keep under 800 words, plain text, no markdown headers — ready for TTS.",
            "If student asks to listen, provide the script and note they can use the Listen button.",
            "",
        ]
    if "study_intel" in intents:
        parts += [
            "STUDY INTEL MODE: Provide personalised study intelligence.",
            "Analyse the student's weak topics, progress, and revision needs (if memory data is injected).",
            "Otherwise, explain how to identify weak areas, suggest next topics, and give a focused revision plan.",
            "Include: Weak topics with accuracy, Suggested next topic with reason, Revision priorities, Encouragement.",
            "Use NSW curriculum outcomes (e.g. MA4-1WM) where relevant.",
            "",
        ]
    if "todo" in intents:
        parts += [
            "TODO MODE: The student wants to add a personal assignment/todo.",
            "You have already created it via the tool. Confirm what was added and offer to show cushion (available time).",
            "Do not ask for subject/due again — it is done.",
            "",
        ]
    if "list_todos" in intents:
        parts += [
            "LIST TODOS MODE: The student wants to see their personal todos.",
            "You have already listed them via the tool. Summarise and highlight overdue/due today/high priority.",
            "Offer to add more or mark as done.",
            "",
        ]
    if "image_gen" in intents:
        parts += [
            "IMAGE GENERATION MODE: The student wants you to generate an image.",
            "You are also generating a real AI image via FLUX diffusion (Pollinations.ai) — same latent diffusion as top models.",
            "The image will be rendered separately in the chat after your text, so DO NOT claim you cannot generate images.",
            "Instead: briefly describe what the image will show (1-2 sentences), then give a short educational explanation of the topic.",
            "Keep it kid-friendly, colourful, and accurate. If the image is a diagram (e.g. solar system), label the parts in your text too.",
            "",
        ]
    if "diagram" in intents:
        parts += [
            "DIAGRAM MODE: The student wants a precise vector diagram (not a photo).",
            "A fine-tuned diagram specialist is drawing it now — validated SVG or mermaid, rendered separately after your text.",
            "DO NOT claim you cannot draw. Do NOT output your own ```svg block — the specialist's diagram is the visual.",
            "Instead: name the answer first (1 sentence), then give a short tutor explanation: labels, working, one misconception warning.",
            "End with: **Try this:** [1 tiny practice question].",
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
    if "socratic" in intents:
        parts += [
            "SOCRATIC TUTORING MODE: You are a Socratic tutor — guide, don't tell.",
            "Ask the student what THEY think the answer is first.",
            "Then ask: 'What makes you think that?' or 'Can you give an example?'",
            "If they're wrong, don't say 'wrong' — ask 'Have you considered...?' or 'What about...?'",
            "Only reveal the full answer AFTER they've tried 2-3 times.",
            "End by asking: 'Can you now teach this back to me?'",
            "",
        ]
    if "roleplay" in intents:
        parts += [
            "ROLEPLAY MODE: You are now a character. Stay in character the entire time.",
            "Possible characters (infer from the message):",
            "- A historical figure (e.g. Einstein, Cleopatra, Captain Cook)",
            "- A scientist explaining their discovery",
            "- A fictional character from a book or movie",
            "- An expert being interviewed (journalist-style)",
            "- A debate opponent arguing the other side",
            "Start the roleplay with an introduction: 'I am [character]. Ask me anything.'",
            "React to the student's questions as the character would.",
            "Break character only at the end with: 'End of roleplay — here's what we covered:' + summary.",
            "",
        ]
    if "multiple_methods" in intents:
        parts += [
            "MULTIPLE SOLUTIONS MODE: Show 2-3 DIFFERENT methods to solve this problem.",
            "Method 1: The standard/textbook approach",
            "Method 2: A visual, intuitive, or shortcut method",
            "Method 3: An alternative approach (if applicable)",
            "After all methods, compare them:",
            "| Method | Speed | Accuracy | Best For | Traps |",
            "Let the student pick which method they prefer.",
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

    # ── Accuracy + Mastery Loop (Astra/Opus 5 style — always active) ───────────
    parts += [
        "━━ ACCURACY RULES (Astra-level — always) ━━",
        "- Double-check every factual claim, date, formula and calculation. Think step-by-step internally, verify the final number before answering.",
        "- For maths: show every step, verify arithmetic, and present 2 methods when useful (like Fable).",
        "- Use the LIVE WEB SEARCH RESULTS and KNOWLEDGE BASE excerpts above when present — prefer them over memory.",
        "- Never hallucinate citations, page numbers or URLs — only cite what was actually provided.",
        "- If unsure, say 'I think' and suggest verifying. If outside confidence, explain limit and offer safe next step.",
        "",
        "━━ MASTERY LOOP (Fable/Opus 5 tutoring — never stop after one answer) ━━",
        "You are a tutor, not a search engine. Every response must follow this loop:",
        "1) Explain clearly (analogy + worked example + misconception warning).",
        "2) Check: ask 1 Socratic question or give 1 tiny practice task (quiz Q, flashcard, 'try this' problem) and invite the student to try — don't give the answer.",
        "3) If the student is wrong, diagnose the misconception, hint, and let them retry — only reveal after 2 hints.",
        "4) Connect to next step: 1-2 sentence 'What next?' linked to their weak area or NSW outcome (e.g. MA4-1WM).",
        "Tone: warm, empathic (Fable), rigorous (Astra). Keep 'What next?' short, e.g. 'Next: 45+23 stickers — what do you get?'",
        "Format: End every answer with: **Try this:** [1 question/task]",
        "",
    ]

    return "\n".join(parts)


# ── Extras generator ──────────────────────────────────────────────────────────

async def _generate_extras(
    intents: list[str], message: str, response: str,
    model: str, config: dict
) -> dict:
    extras = {}

    if "quiz" in intents or "exam_mode" in intents or "exam_sim" in intents:
        q = _parse_quiz(response)
        if q:
            # exam_sim → timed quiz extra
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

    # NOTE: No auto-generation here — flashcards / practice quizzes are ONLY
    # created when the user explicitly asks (flashcard / quiz intent).
    # Previously this auto-generated 6 flashcards + 3 practice questions on
    # every explain/math/summary, which felt random and unwanted.
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
        # Extract last numeric answer from AI response (e.g., "x = 3", "Answer: 42")
        nums = _re.findall(r"[-+]?\d*\.?\d+", answer)
        if not nums:
            return None
        # Try to evaluate any python expression in question (e.g., "2+2*3")
        exprs = _re.findall(r"[\d\.\s\+\-\*\/\(\)\^]+", question)
        # Quick sympy check if available
        code = textwrap.dedent("""
            import re, math
            try:
                import sympy
                has_sympy=True
            except: has_sympy=False
            q = '''{q}'''
            a = '''{a}'''
            # Try to find equation like "3x^2+5x-2=0" -> sympy solve
            # Fallback: eval simple arithmetic safely
            try:
                # Extract simple arithmetic like "45+23"
                m=re.search(r'(\\d+\\s*[\\+\\-\\*\\/]\\s*\\d+[\\s\\+\\-\\*\\/\\d\\(\\)]*)', q)
                if m:
                    expr=m.group(1).replace('^','**')
                    expected=eval(expr, {"__builtins__":{{}}, "math":math})
                    # Check if expected appears in answer
                    if str(int(expected)) not in a and str(expected) not in a:
                        print(f"MISMATCH:{expected}")
                    else:
                        print("OK")
                else:
                    print("SKIP")
            except Exception as e:
                print(f"ERR:{e}")
        """).format(q=question.replace("'", "\\'")[:500], a=answer.replace("'", "\\'")[:500])
        proc = _sp.run(["python3", "-c", code], capture_output=True, timeout=3, text=True)
        out = (proc.stdout or "").strip()
        if out.startswith("MISMATCH:"):
            val = out.split(":",1)[1].strip()
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
                return {"ok": False, "notes": str(data.get("notes","Self-check flagged"))[:200]}
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


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"
