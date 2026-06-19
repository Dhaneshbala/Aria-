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
                    return io.BytesIO(r.content)
            except Exception:
                pass
            try:
                r = requests.get(f"https://picsum.photos/{w}/{h}?random={abs(hash(query))%1000}", timeout=8)
                if r.status_code == 200:
                    return io.BytesIO(r.content)
            except Exception:
                pass
            return None

        # ── Step 5: Build PowerPoint ──────────────────────────────────────────
        prs = Presentation()
        prs.slide_width  = Inches(10)
        prs.slide_height = Inches(5.625)
        W = Inches(10)
        H = Inches(5.625)

        def set_bg(slide, color):
            fill = slide.background.fill
            fill.solid()
            fill.fore_color.rgb = color

        def add_text(slide, text, left, top, width, height,
                     size=18, bold=False, color=None, align=PP_ALIGN.LEFT,
                     italic=False, wrap=True):
            if color is None:
                color = C_TEXT
            txb = slide.shapes.add_textbox(left, top, width, height)
            tf  = txb.text_frame
            tf.word_wrap = wrap
            p = tf.paragraphs[0]
            p.alignment = align
            run = p.add_run()
            run.text           = str(text)
            run.font.size      = Pt(size)
            run.font.bold      = bold
            run.font.italic    = italic
            run.font.color.rgb = color
            return txb

        def add_image_bg(slide, img_data, left=0, top=0, width=None, height=None):
            if img_data is None:
                return
            if width is None:  width = W
            if height is None: height = H
            try:
                pic = slide.shapes.add_picture(img_data, left, top, width, height)
                slide.shapes._spTree.remove(pic._element)
                slide.shapes._spTree.insert(2, pic._element)
            except Exception:
                pass

        def add_panel(slide, left, top, width, height, color):
            shape = slide.shapes.add_shape(
                MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, left, top, width, height
            )
            shape.fill.solid()
            shape.fill.fore_color.rgb = color
            shape.line.fill.background()
            shape.adjustments[0] = 0.0
            return shape

        # ── TITLE SLIDE ───────────────────────────────────────────────────────
        ts = prs.slides.add_slide(prs.slide_layouts[6])
        set_bg(ts, C_BG)
        cover_img = fetch_image(f"{topic} landscape", 1000, 563)
        add_image_bg(ts, cover_img)
        add_panel(ts, Inches(0), Inches(0), Inches(5.2), H, C_DARK)
        add_panel(ts, Inches(0), Inches(0), Inches(5.2), Inches(0.08), C_ACCENT)
        add_text(ts, theme_emojis, Inches(0.4), Inches(0.5), Inches(4), Inches(0.7), size=28)
        add_text(ts, topic.upper(), Inches(0.4), Inches(1.2), Inches(4.6), Inches(1.8),
                 size=36, bold=True, color=C_TEXT)
        add_panel(ts, Inches(0.4), Inches(3.0), Inches(1.5), Inches(0.05), C_ACCENT)
        add_text(ts, 'An ARIA Study Presentation', Inches(0.4), Inches(3.2),
                 Inches(4.5), Inches(0.45), size=13, color=C_SUB, italic=True)
        add_text(ts, f'{len(slide_data)} slides  ·  AI Generated', Inches(0.4), Inches(3.7),
                 Inches(4.5), Inches(0.4), size=11, color=C_GRAY)
        add_panel(ts, Inches(0), Inches(5.3), W, Inches(0.325), C_ACCENT)
        add_text(ts, 'ARIA — AI Study Assistant', Inches(0.3), Inches(5.32),
                 Inches(5), Inches(0.3), size=10, color=C_DARK, bold=True)

        # ── TABLE OF CONTENTS ─────────────────────────────────────────────────
        toc = prs.slides.add_slide(prs.slide_layouts[6])
        set_bg(toc, C_BG)
        add_panel(toc, Inches(0), Inches(0), W, Inches(0.08), C_ACCENT)
        add_text(toc, 'Contents', Inches(0.4), Inches(0.2), Inches(6), Inches(0.7),
                 size=30, bold=True, color=C_TEXT)
        cols_x = [Inches(0.3), Inches(5.1)]
        for j, s in enumerate(slide_data[:8]):
            cx = cols_x[j % 2]
            cy = Inches(1.1) + (j // 2) * Inches(1.0)
            add_panel(toc, cx, cy, Inches(4.5), Inches(0.85), C_DARK)
            add_text(toc, f'{j+1:02d}', cx + Inches(0.12), cy + Inches(0.1),
                     Inches(0.5), Inches(0.55), size=18, bold=True, color=C_ACCENT)
            add_text(toc, s['title'], cx + Inches(0.65), cy + Inches(0.12),
                     Inches(3.7), Inches(0.65), size=13, color=C_TEXT)
        add_panel(toc, Inches(0), Inches(5.3), W, Inches(0.325), C_ACCENT)

        # ── CONTENT SLIDES ────────────────────────────────────────────────────
        BULLET_COLORS = [C_ACCENT, C_SUB, C_TEXT]

        for i, s in enumerate(slide_data):
            sl = prs.slides.add_slide(prs.slide_layouts[6])
            set_bg(sl, C_BG)
            img_left = (i % 2 == 0)
            img_data = fetch_image(s['image'] or s['title'], 500, 563)
            if img_data:
                img_x = Inches(5.5) if img_left else Inches(0)
                try:
                    pic = sl.shapes.add_picture(img_data, img_x, Inches(0), Inches(4.5), H)
                    sl.shapes._spTree.remove(pic._element)
                    sl.shapes._spTree.insert(2, pic._element)
                except Exception:
                    pass
            panel_x = Inches(0) if img_left else Inches(4.5)
            add_panel(sl, panel_x, Inches(0), Inches(5.5), H, C_DARK)
            add_panel(sl, Inches(0), Inches(0), W, Inches(0.06), C_ACCENT)
            add_text(sl, f'{i+1}', panel_x + Inches(0.2), Inches(0.15),
                     Inches(0.5), Inches(0.45), size=11, color=C_ACCENT, bold=True)
            add_text(sl, s['icon'], panel_x + Inches(0.15), Inches(0.5),
                     Inches(0.7), Inches(0.7), size=28)
            add_text(sl, s['title'], panel_x + Inches(0.9), Inches(0.5),
                     Inches(4.4), Inches(0.85), size=22, bold=True, color=C_TEXT)
            add_panel(sl, panel_x + Inches(0.2), Inches(1.35), Inches(3.5), Inches(0.04), C_ACCENT)
            for j, bullet in enumerate(s['bullets'][:3]):
                by = Inches(1.55) + Inches(j * 1.1)
                col = BULLET_COLORS[j % len(BULLET_COLORS)]
                add_panel(sl, panel_x + Inches(0.2), by + Inches(0.22),
                          Inches(0.12), Inches(0.12), col)
                add_text(sl, bullet, panel_x + Inches(0.42), by,
                         Inches(4.8), Inches(1.0), size=14, color=C_TEXT)
            add_panel(sl, Inches(0), Inches(5.3), W, Inches(0.325), C_ACCENT)
            add_text(sl, 'ARIA', Inches(0.2), Inches(5.33), Inches(2), Inches(0.28),
                     size=10, color=C_DARK, bold=True)
            add_text(sl, topic.upper(), Inches(6), Inches(5.33), Inches(3.8), Inches(0.28),
                     size=10, color=C_DARK, align=PP_ALIGN.RIGHT)

        # ── THANK YOU SLIDE ───────────────────────────────────────────────────
        es = prs.slides.add_slide(prs.slide_layouts[6])
        set_bg(es, C_BG)
        end_img = fetch_image(f"{topic} beautiful", 1000, 563)
        add_image_bg(es, end_img)
        add_panel(es, Inches(0), Inches(0), W, H, C_DARK)
        add_panel(es, Inches(0), Inches(0), W, Inches(0.08), C_ACCENT)
        add_text(es, theme_emojis, Inches(3.5), Inches(1.0), Inches(3), Inches(0.7),
                 size=40, align=PP_ALIGN.CENTER)
        add_text(es, 'Thanks for watching!', Inches(0.5), Inches(1.9), Inches(9), Inches(1),
                 size=40, bold=True, color=C_TEXT, align=PP_ALIGN.CENTER)
        add_panel(es, Inches(3.5), Inches(3.0), Inches(3), Inches(0.05), C_ACCENT)
        add_text(es, f'Topic: {topic}  ·  Made with ARIA', Inches(0.5), Inches(3.2),
                 Inches(9), Inches(0.5), size=14, color=C_SUB, italic=True, align=PP_ALIGN.CENTER)
        add_panel(es, Inches(0), Inches(5.3), W, Inches(0.325), C_ACCENT)

        # ── Save and return ───────────────────────────────────────────────────
        buf = io.BytesIO()
        prs.save(buf)
        buf.seek(0)
        return buf.read()