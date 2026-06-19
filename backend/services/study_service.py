"""Study service — generates quizzes, flashcards, mind maps, study plans."""
import json
import re
from .ollama_service import OllamaService

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

        # Step 1: AI plans the presentation
        plan_prompt = (
            f"You are creating a PowerPoint presentation for a 13-year-old student.\n"
            f"Topic: {topic}\n"
            f"Create exactly {slides} slides. For each slide use this exact format:\n\n"
            f"SLIDE [N]\n"
            f"TITLE: [engaging title]\n"
            f"BULLETS:\n- [point 1]\n- [point 2]\n- [point 3]\n"
            f"IMAGE_SEARCH: [3-word image search query]\n"
            f"EMOJI: [1 relevant emoji]\n"
            f"NOTES: [speaker notes]\n\n"
            f"Use real facts. Make it engaging and educational."
        )
        response = await ollama.complete(model, plan_prompt, max_tokens=4000)

        # Step 2: Parse AI response
        def parse_slides(text):
            blocks = re.split(r'SLIDE\s+\d+', text)[1:]
            parsed = []
            for block in blocks:
                s = {
                    "title": "",
                    "bullets": [],
                    "image_search": "",
                    "emoji": "📚",
                    "notes": "",
                }
                for line in block.split('\n'):
                    line = line.strip()
                    if line.startswith('TITLE:'):
                        s["title"] = line.replace('TITLE:', '').strip()
                    elif line.startswith('IMAGE_SEARCH:'):
                        s["image_search"] = line.replace('IMAGE_SEARCH:', '').strip()
                    elif line.startswith('EMOJI:'):
                        s["emoji"] = line.replace('EMOJI:', '').strip()
                    elif line.startswith('NOTES:'):
                        s["notes"] = line.replace('NOTES:', '').strip()
                    elif line.startswith('-') or line.startswith('•'):
                        s["bullets"].append(line.lstrip('-•').strip())
                if s["title"]:
                    parsed.append(s)
            return parsed

        slide_data = parse_slides(response)
        if not slide_data:
            slide_data = [{"title": topic, "bullets": ["Content loading..."], "image_search": topic, "emoji": "📚", "notes": ""}]

        # Step 3: Fetch images
        def fetch_image(query: str):
            try:
                encoded = urllib.parse.quote(query)
                r = requests.get(
                    f"https://source.unsplash.com/800x500/?{encoded}",
                    timeout=10, allow_redirects=True
                )
                if r.status_code == 200 and len(r.content) > 5000:
                    return io.BytesIO(r.content)
            except Exception:
                pass
            try:
                r = requests.get("https://picsum.photos/800/500", timeout=8)
                if r.status_code == 200:
                    return io.BytesIO(r.content)
            except Exception:
                pass
            return None

        # Step 4: Build PowerPoint
        prs = Presentation()
        prs.slide_width  = Inches(13.33)
        prs.slide_height = Inches(7.5)

        BG     = RGBColor(0x0f, 0x0f, 0x1a)
        PURPLE = RGBColor(0x7c, 0x6a, 0xf7)
        ACCENT = RGBColor(0xa8, 0x9b, 0xf8)
        WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
        YELLOW = RGBColor(0xfb, 0xbf, 0x24)
        GREEN  = RGBColor(0x4a, 0xde, 0x80)
        GRAY   = RGBColor(0x88, 0x88, 0x88)

        def set_bg(slide, color):
            fill = slide.background.fill
            fill.solid()
            fill.fore_color.rgb = color

        def add_textbox(slide, text, left, top, width, height,
                        size=24, bold=False, color=WHITE, align=PP_ALIGN.LEFT):
            txb = slide.shapes.add_textbox(left, top, width, height)
            tf  = txb.text_frame
            tf.word_wrap = True
            p   = tf.paragraphs[0]
            p.alignment = align
            run = p.add_run()
            run.text = text
            run.font.size      = Pt(size)
            run.font.bold      = bold
            run.font.color.rgb = color
            return txb

        def add_rect(slide, left, top, width, height, color):
            shape = slide.shapes.add_shape(1, left, top, width, height)
            shape.fill.solid()
            shape.fill.fore_color.rgb = color
            shape.line.fill.background()
            return shape

        # Title slide
        title_slide = prs.slides.add_slide(prs.slide_layouts[6])
        set_bg(title_slide, BG)
        add_rect(title_slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), PURPLE)
        add_rect(title_slide, Inches(0), Inches(7.2), Inches(13.33), Inches(0.3), PURPLE)

        cover_img = fetch_image(topic)
        if cover_img:
            try:
                title_slide.shapes.add_picture(cover_img, Inches(7.5), Inches(1), Inches(5.5), Inches(5.5))
            except Exception:
                pass

        add_textbox(title_slide, slide_data[0]["emoji"], Inches(0.8), Inches(1.2), Inches(1), Inches(1), size=60)
        add_textbox(title_slide, topic.upper(), Inches(0.8), Inches(2.2), Inches(6.5), Inches(1.5), size=44, bold=True, color=WHITE)
        add_textbox(title_slide, "An ARIA Study Presentation", Inches(0.8), Inches(3.8), Inches(6), Inches(0.6), size=18, color=ACCENT)
        add_textbox(title_slide, f"{len(slide_data)} slides  •  AI Generated", Inches(0.8), Inches(4.5), Inches(6), Inches(0.5), size=14, color=GRAY)

        # Content slides
        BULLET_COLORS = [ACCENT, GREEN, YELLOW, WHITE, ACCENT]

        for i, s in enumerate(slide_data):
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            set_bg(slide, BG)
            add_rect(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.06), PURPLE)
            add_rect(slide, Inches(0), Inches(7.15), Inches(13.33), Inches(0.35), RGBColor(0x1a, 0x1a, 0x2e))

            add_textbox(slide, f"{i+1}/{len(slide_data)}", Inches(11.8), Inches(0.15), Inches(1.4), Inches(0.4), size=11, color=GRAY, align=PP_ALIGN.RIGHT)
            add_textbox(slide, s["emoji"], Inches(0.3), Inches(0.3), Inches(0.8), Inches(0.8), size=32)
            add_textbox(slide, s["title"], Inches(1.2), Inches(0.25), Inches(9), Inches(0.9), size=32, bold=True, color=WHITE)
            add_rect(slide, Inches(1.2), Inches(1.15), Inches(4), Inches(0.04), PURPLE)

            img_data = fetch_image(s["image_search"] or s["title"])
            img_placed = False
            if img_data:
                try:
                    slide.shapes.add_picture(img_data, Inches(8.2), Inches(1.3), Inches(4.8), Inches(3.5))
                    border = add_rect(slide, Inches(8.2), Inches(1.3), Inches(4.8), Inches(3.5), PURPLE)
                    border.fill.background()
                    border.line.color.rgb = PURPLE
                    border.line.width = Pt(2)
                    img_placed = True
                except Exception:
                    pass

            bullet_width = Inches(7.5) if img_placed else Inches(12.3)
            for j, bullet in enumerate(s["bullets"][:5]):
                color = BULLET_COLORS[j % len(BULLET_COLORS)]
                add_rect(slide, Inches(0.5), Inches(1.4) + Inches(j * 0.9) + Inches(0.15), Inches(0.12), Inches(0.12), color)
                add_textbox(slide, bullet, Inches(0.75), Inches(1.4) + Inches(j * 0.9), bullet_width - Inches(0.3), Inches(0.85), size=19, color=WHITE)

            add_textbox(slide, "ARIA — AI Study Assistant", Inches(0.3), Inches(7.18), Inches(4), Inches(0.3), size=10, color=GRAY)
            add_textbox(slide, topic.upper(), Inches(9), Inches(7.18), Inches(4), Inches(0.3), size=10, color=PURPLE, align=PP_ALIGN.RIGHT)

            if s["notes"]:
                slide.notes_slide.notes_text_frame.text = s["notes"]

        # Thank you slide
        end_slide = prs.slides.add_slide(prs.slide_layouts[6])
        set_bg(end_slide, BG)
        add_rect(end_slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), PURPLE)
        add_rect(end_slide, Inches(0), Inches(7.2), Inches(13.33), Inches(0.3), PURPLE)
        add_textbox(end_slide, "🎓", Inches(5.9), Inches(1.8), Inches(1.5), Inches(1.5), size=72)
        add_textbox(end_slide, "Thanks for watching!", Inches(2), Inches(3.2), Inches(9.33), Inches(1), size=42, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        add_textbox(end_slide, f"Topic: {topic}  •  Made with ARIA", Inches(2), Inches(4.3), Inches(9.33), Inches(0.6), size=18, color=ACCENT, align=PP_ALIGN.CENTER)

        buf = io.BytesIO()
        prs.save(buf)
        buf.seek(0)
        return buf.read()
