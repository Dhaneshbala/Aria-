"""Study service — generates quizzes, flashcards, mind maps, study plans."""
import json
import re
from .ollama_service import OllamaService
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE

ollama = OllamaService()

QUIZ_LEVELS = {
    "easy": "simple recall and basic understanding, single-step problems",
    "medium": "application and some analysis, two-step problems",
    "hard": "deep analysis, multi-step reasoning, challenging edge cases",
    "exam": "timed exam simulation — comprehensive coverage, varied question types, mark-scheme style answers",
    "olympiad": "competition-level (APSMO/AMC/IMO style), highly challenging, creative lateral thinking, proof-based",
}


class StudyService:

    async def generate_quiz(
        self, topic: str, level: str = "medium",
        num_questions: int = 5, model: str = "qwen3:8b"
    ) -> list[dict]:
        level_desc = QUIZ_LEVELS.get(level, QUIZ_LEVELS["medium"])
        prompt = (
            f"Generate {num_questions} multiple-choice quiz questions about: {topic}\n"
            f"Difficulty: {level_desc}\n"
            f"For each question:\n"
            f"Q[N]: [question text]\n"
            f"A) [option]\nB) [option]\nC) [option]\nD) [option]\n"
            f"Correct: [letter]\n"
            f"Explanation: [brief explanation]\n\n"
            f"Make questions appropriate for a 13-year-old student."
        )
        response = await ollama.complete(model, prompt)
        return self._parse_quiz(response)

    async def generate_flashcards(
        self, topic: str, num_cards: int = 10, model: str = "qwen3:8b"
    ) -> list[dict]:
        prompt = (  
            f"Generate {num_cards} flashcards for studying: {topic}\n"
            f"Format exactly:\n"
            f"FRONT: [term or question] | BACK: [definition or answer]\n"
            f"One flashcard per line. Make them clear and memorable for a 13-year-old."
        )
        response = await ollama.complete(model, prompt)
        return self._parse_flashcards(response)

    async def generate_mindmap(
        self, topic: str, model: str = "qwen3:8b"
    ) -> dict:
        prompt = (
            f"Create a mind map for the topic: {topic}\n"
            f"Return ONLY valid JSON in this exact format:\n"
            f'{{"center": "{topic}", "branches": [{{"label": "Branch 1", "children": ["subtopic 1", "subtopic 2"]}}, {{"label": "Branch 2", "children": ["subtopic 3", "subtopic 4"]}}]}}\n'
            f"Include 4-6 main branches, each with 2-4 children. No extra text."
        )
        response = await ollama.complete(model, prompt)
        try:
            clean = response.strip()
            if clean.startswith("```"):
                clean = re.sub(r"```(?:json)?", "", clean).strip()
            data = json.loads(clean)
            return data
        except Exception:
            return {"center": topic, "branches": [{"label": "Could not parse", "children": []}]}

    async def generate_study_plan(
        self, topic: str, days: int = 7, model: str = "qwen3:8b"
    ) -> list[dict]:
        prompt = (
            f"Create a {days}-day study plan for: {topic}\n"
            f"The student is 13 years old. Format as JSON array:\n"
            f'[{{"day": 1, "title": "Day title", "tasks": ["task 1", "task 2"], "time_minutes": 45}}]\n'
            f"Include realistic daily tasks and time estimates. No extra text."
        )
        response = await ollama.complete(model, prompt)
        try:
            clean = response.strip()
            if clean.startswith("```"):
                clean = re.sub(r"```(?:json)?", "", clean).strip()
            return json.loads(clean)
        except Exception:
            return [{"day": i+1, "title": f"Day {i+1}", "tasks": [], "time_minutes": 45} for i in range(days)]

    async def generate_summary(self, text: str, model: str = "qwen3:8b") -> str:
        prompt = (
            f"Summarise the following in clear, simple language for a 13-year-old student.\n"
            f"Include: key points, important vocabulary, main ideas.\n\n{text[:4000]}"
        )
        return await ollama.complete(model, prompt)

    def _parse_quiz(self, text: str) -> list[dict]:
        questions = []
        blocks = re.split(r"Q\d+[:.)]", text)
        for block in blocks[1:]:
            lines = [l.strip() for l in block.strip().split("\n") if l.strip()]
            if not lines:
                continue
            q = {"question": lines[0], "options": [], "correct": "", "explanation": ""}
            for line in lines[1:]:
                if re.match(r"[A-D][.):]\s*", line):
                    q["options"].append(re.sub(r"^[A-D][.):]\s*", "", line))
                elif re.search(r"^correct", line, re.I):
                    m = re.search(r"[A-D]", line)
                    if m:
                        q["correct"] = m.group()
                elif "explanation" in line.lower() or (q["correct"] and len(line) > 20):
                    q["explanation"] += line + " "
            if len(q["options"]) >= 2:
                questions.append(q)
        return questions[:10]

    def _parse_flashcards(self, text: str) -> list[dict]:
        cards = []
        for line in text.split("\n"):
            if "|" in line and re.search(r"(?i)front:", line):
                parts = line.split("|")
                if len(parts) >= 2:
                    front = re.sub(r"(?i)front:\s*", "", parts[0]).strip()
                    back = re.sub(r"(?i)back:\s*", "", parts[1]).strip()
                    if front and back:
                        cards.append({"front": front, "back": back})
        return cards[:20]

    async def generate_notes(self, topic: str, style: str = "structured", model: str = "qwen3:8b") -> str:
        """Generate structured study notes on a topic."""
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
        return await ollama.complete(model, prompt)

    async def generate_exam_questions(self, topic: str, num: int = 10, model: str = "qwen3:8b") -> list[dict]:
        """Exam mode — timed, mark-scheme style questions."""
        prompt = (
            f"Create {num} exam-style questions about: {topic}\n"
            f"Mix of multiple choice, short answer, extended response.\n"
            f"Include mark allocation and model answers.\n"
            f"Format: Q[N]: question\nA) B) C) D) options\nCorrect: letter\nExplanation: answer\n"
            f"Suitable for a 13-year-old."
        )
        response = await ollama.complete(model, prompt)
        return self._parse_quiz(response)
    async def generate_pptx(self, topic: str, slides: int = 10, model: str = "qwen3:8b") -> bytes:
        import io
        import re
        import requests
        import urllib.parse
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN
        from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE

        # ── Step 1: AI determines theme + generates content ───────────────────
        plan_prompt = (
            f"You are creating a Slidesgo-style PowerPoint presentation for a 13-year-old student.\n"
            f"Topic: {topic}\n\n"
            f"First, suggest a visual theme for this topic:\n"
            f"THEME_BG: [dark hex color e.g. #1a0a00 for ancient china, #001524 for ocean]\n"
            f"THEME_ACCENT: [vivid accent hex color]\n"
            f"THEME_TEXT: [light text hex color]\n"
            f"THEME_SUB: [secondary text hex color]\n"
            f"THEME_EMOJI: [3 emojis that represent this topic]\n\n"
            f"Then create exactly {slides} content slides. For each use EXACTLY:\n"
            f"SLIDE [N]\n"
            f"TITLE: [engaging title max 8 words]\n"
            f"BULLET1: [fascinating fact, complete sentence]\n"
            f"BULLET2: [fascinating fact, complete sentence]\n"
            f"BULLET3: [fascinating fact, complete sentence]\n"
            f"IMAGE: [specific 3-word image search for this slide]\n"
            f"ICON: [single relevant emoji]\n\n"
            f"Use real verified facts. Be vivid, specific and engaging."
        )
        response = await ollama.complete(model, plan_prompt, max_tokens=5000)

        # ── Step 2: Parse theme colours ───────────────────────────────────────
        def parse_hex(text, key, default):
            m = re.search(rf'{key}:\s*#?([A-Fa-f0-9]{{6}})', text)
            if m:
                h = m.group(1)
                return RGBColor(int(h[0:2],16), int(h[2:4],16), int(h[4:6],16))
            h = default.lstrip('#')
            return RGBColor(int(h[0:2],16), int(h[2:4],16), int(h[4:6],16))

        C_BG     = parse_hex(response, 'THEME_BG',     '#0f0f1a')
        C_ACCENT = parse_hex(response, 'THEME_ACCENT',  '#7c6af7')
        C_TEXT   = parse_hex(response, 'THEME_TEXT',    '#ffffff')
        C_SUB    = parse_hex(response, 'THEME_SUB',     '#a89bf8')
        C_DARK   = RGBColor(0x0a, 0x0a, 0x10)
        C_GRAY   = RGBColor(0x88, 0x88, 0x99)

        emoji_match = re.search(r'THEME_EMOJI:\s*(.+)', response)
        theme_emojis = emoji_match.group(1).strip() if emoji_match else '📚✨🎓'

        # ── Step 3: Parse slide content ───────────────────────────────────────
        def parse_slides(text):
            blocks = re.split(r'\bSLIDE\s+\d+\b', text)[1:]
            parsed = []
            for block in blocks:
                s = {'title': '', 'bullets': [], 'image': '', 'icon': '📚'}
                for line in block.split('\n'):
                    line = line.strip()
                    if line.startswith('TITLE:'):
                        s['title'] = line.replace('TITLE:', '').strip()
                    elif re.match(r'BULLET\d:', line):
                        b = re.sub(r'BULLET\d:\s*', '', line).strip()
                        if b:
                            s['bullets'].append(b)
                    elif line.startswith('IMAGE:'):
                        s['image'] = line.replace('IMAGE:', '').strip()
                    elif line.startswith('ICON:'):
                        s['icon'] = line.replace('ICON:', '').strip()
                if s['title']:
                    parsed.append(s)
            return parsed

        slide_data = parse_slides(response)
        if not slide_data:
            slide_data = [{'title': topic, 'bullets': ['Content here'], 'image': topic, 'icon': '📚'}]

        # ── Step 4: Fetch images from Unsplash ────────────────────────────────
        def fetch_image(query, w=960, h=540):
            try:
                enc = urllib.parse.quote(f"{query},{topic}")
                r = requests.get(
                    f"https://source.unsplash.com/{w}x{h}/?{enc}",
                    timeout=12, allow_redirects=True,
                    headers={'User-Agent': 'Mozilla/5.0'}
                )
                if r.status_code == 200 and len(r.content) > 8000:
                    return