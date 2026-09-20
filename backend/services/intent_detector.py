"""
Intent detection and language identification for Study Buddy.
──────────────────────────────────────────────────────
Extracted from orchestrator.py for maintainability.
Every user message passes through detect_intents() — the front door.
"""

import re
import logging

logger = logging.getLogger(__name__)

# ── Intent patterns ──────────────────────────────────────────────────────────

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
    "cheatsheet": [
        r"\b(cheat.?sheet|cheat sheet|cheatsheet)\b",
        r"\b(one.?page|one page).{0,20}(summary|revision|notes)\b",
        r"\b(bus ride|quick revision|revision sheet)\b",
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
        r"\b(angle|vertex|ray|complement|supplement|protract|parallel|perpendicular|transversal)\b.{0,30}\b(diagram|draw|show|visual|illustrat)\b",
        r"\b(diagram|draw|show|visual|illustrat)\b.{0,30}\b(angle|vertex|ray|complement|supplement|protract|parallel|perpendicular|transversal)\b",
        r"\b(angles?|geometry)\b.{0,20}\b(around|on|between|inside|outside)\b",
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
    """Detect non-English language from the user's message."""
    for pattern, lang in _NON_ENGLISH_INDICATORS:
        if re.search(pattern, message, re.I):
            return lang
    return None


def detect_intents(message: str, has_image: bool = False, has_doc: bool = False) -> list[str]:
    """Classify user message into one or more intents.

    This is Study Buddy's front door — every message is classified here.
    Returns at least one intent (defaults to "chat").
    """
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
