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
        import urllib.parse
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN

        # Step 1: AI generates slide content
        plan_prompt = (
            f"Create a {slides}-slide presentation for a 13-year-old student about: {topic}\n\n"
            f"For each slide use EXACTLY this format:\n"
            f"SLIDE [N]\n"
            f"TITLE: [title]\n"
            f"BULLET1: [point]\n"
            f"BULLET2: [point]\n"
            f"BULLET3: [point]\n"
            f"EMOJI: [one emoji]\n\n"
            f"Use real facts. Be educational and engaging."
        )
        response = await ollama.complete(model, plan_prompt, max_tokens=4000)

        # Step 2: Parse
        def parse_slides(text):
            blocks = re.split(r'SLIDE\s+\d+', text)[1:]
            parsed = []
            for block in blocks:
                s = {"title": "", "bullets": [], "emoji": "📚"}
                for line in block.split('\n'):
                    line = line.strip()
                    if line.startswith('TITLE:'):
                        s["title"] = line.replace('TITLE:', '').strip()
                    elif line.startswith('EMOJI:'):
                        s["emoji"] = line.replace('EMOJI:', '').strip()
                    elif re.match(r'BULLET\d:', line):
                        text_part = re.sub(r'BULLET\d:', '', line).strip()
                        if text_part:
                            s["bullets"].append(text_part)
                if s["title"]:
                    parsed.append(s)
            return parsed

        slide_data = parse_slides(response)
        if not slide_data:
            slide_data = [{"title": topic, "bullets": ["Content here"], "emoji": "📚"}]

        # Step 3: Build clean PowerPoint
        prs = Presentation()
        prs.slide_width  = Inches(13.33)
        prs.slide_height = Inches(7.5)

        PURPLE = RGBColor(0x7c, 0x6a, 0xf7)
        WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
        DARK   = RGBColor(0x0f, 0x0f, 0x1a)
        ACCENT = RGBColor(0xa8, 0x9b, 0xf8)
        GRAY   = RGBColor(0x88, 0x88, 0x88)
        GREEN  = RGBColor(0x4a, 0xde, 0x80)
        YELLOW = RGBColor(0xfb, 0xbf, 0x24)

        def set_bg(slide):
            fill = slide.background.fill
            fill.solid()
            fill.fore_color.rgb = DARK

        def add_text(slide, text, left, top, width, height,
                     size=24, bold=False, color=WHITE, align=PP_ALIGN.LEFT):
            txb = slide.shapes.add_textbox(left, top, width, height)
            tf  = txb.text_frame
            tf.word_wrap = True
            p   = tf.paragraphs[0]
            p.alignment = align
            run = p.add_run()
            run.text           = str(text)
            run.font.size      = Pt(size)
            run.font.bold      = bold
            run.font.color.rgb = color

        # Title slide
        ts = prs.slides.add_slide(prs.slide_layouts[6])
        set_bg(ts)
        add_text(ts, slide_data[0]["emoji"], Inches(0.8), Inches(1.5), Inches(2), Inches(1.5), size=60)
        add_text(ts, topic.upper(), Inches(0.8), Inches(2.8), Inches(11), Inches(1.5), size=48, bold=True, color=WHITE, align=PP_ALIGN.LEFT)
        add_text(ts, "An ARIA Study Presentation", Inches(0.8), Inches(4.2), Inches(8), Inches(0.6), size=20, color=ACCENT)
        add_text(ts, f"{len(slide_data)} slides  •  AI Generated", Inches(0.8), Inches(4.9), Inches(6), Inches(0.5), size=14, color=GRAY)

        # Content slides
        COLORS = [ACCENT, GREEN, YELLOW, WHITE, ACCENT]

        for i, s in enumerate(slide_data):
            sl = prs.slides.add_slide(prs.slide_layouts[6])
            set_bg(sl)

            # Slide number
            add_text(sl, f"{i+1} / {len(slide_data)}", Inches(11.5), Inches(0.2), Inches(1.5), Inches(0.4), size=11, color=GRAY, align=PP_ALIGN.RIGHT)

            # Emoji + Title
            add_text(sl, s["emoji"], Inches(0.3), Inches(0.3), Inches(0.9), Inches(0.9), size=36)
            add_text(sl, s["title"], Inches(1.3), Inches(0.3), Inches(10), Inches(0.9), size=34, bold=True, color=WHITE)

            # Divider line using textbox
            add_text(sl, "─" * 80, Inches(0.3), Inches(1.2), Inches(12.5), Inches(0.3), size=8, color=PURPLE)

            # Bullets
            for j, bullet in enumerate(s["bullets"][:5]):
                color = COLORS[j % len(COLORS)]
                add_text(sl, f"▸  {bullet}", Inches(0.5), Inches(1.6) + Inches(j * 0.95), Inches(12), Inches(0.85), size=20, color=color)

            # Footer
            add_text(sl, "ARIA — AI Study Assistant", Inches(0.3), Inches(7.1), Inches(5), Inches(0.3), size=10, color=GRAY)
            add_text(sl, topic.upper(), Inches(8), Inches(7.1), Inches(5), Inches(0.3), size=10, color=PURPLE, align=PP_ALIGN.RIGHT)

        # Thank you slide
        es = prs.slides.add_slide(prs.slide_layouts[6])
        set_bg(es)
        add_text(es, "🎓", Inches(5.9), Inches(1.8), Inches(2), Inches(1.5), size=72)
        add_text(es, "Thanks for watching!", Inches(1), Inches(3.3), Inches(11.33), Inches(1), size=44, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        add_text(es, f"Topic: {topic}  •  Made with ARIA", Inches(1), Inches(4.5), Inches(11.33), Inches(0.6), size=18, color=ACCENT, align=PP_ALIGN.CENTER)

        buf = io.BytesIO()
        prs.save(buf)
        buf.seek(0)
        return buf.read()