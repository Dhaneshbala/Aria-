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
        self,
        topic: str,
        level: str = "medium",
        num_questions: int = 5,
        model: str = "qwen3:8b",
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

    async def generate_mindmap(self, topic: str, model: str = "qwen3:8b") -> dict:
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
            return {
                "center": topic,
                "branches": [{"label": "Could not parse", "children": []}],
            }

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
            return [
                {"day": i + 1, "title": f"Day {i+1}", "tasks": [], "time_minutes": 45}
                for i in range(days)
            ]

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

    async def generate_notes(
        self, topic: str, style: str = "structured", model: str = "qwen3:8b"
    ) -> str:
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

    async def generate_exam_questions(
        self, topic: str, num: int = 10, model: str = "qwen3:8b"
    ) -> list[dict]:
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

    async def _generate_pptx_fallback(self, topic: str, slides: int = 10, model: str = "qwen3:8b") -> bytes:
        async def generate_pptx(self, topic: str, slides: int = 10, model: str = "qwen3:8b") -> bytes:
        import httpx
        from pathlib import Path

        PRESENTON_URL  = "http://127.0.0.1:5000"
        PRESENTON_DATA = Path.home() / "presenton_data"
        PRESENTON_USER = "Dhanesh"
        PRESENTON_PASS = "123456"

        try:
            async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
                # Login — cookies persist automatically on this client
                login_resp = await client.post(
                    f"{PRESENTON_URL}/api/v1/auth/login",
                    json={"username": PRESENTON_USER, "password": PRESENTON_PASS},
                )
                if login_resp.status_code != 200:
                    raise Exception(f"Presenton login failed: {login_resp.text}")

                # Generate the presentation
                gen_resp = await client.post(
                    f"{PRESENTON_URL}/api/v1/ppt/presentation/generate",
                    json={
                        "content": f"{topic} for a 13 year old student",
                        "n_slides": slides,
                        "template": "general",
                        "tone": "educational",
                        "verbosity": "standard",
                        "include_title_slide": True,
                        "export_as": "pptx",
                    },
                )
                if gen_resp.status_code != 200:
                    raise Exception(f"Presenton generation failed: {gen_resp.text}")

                result = gen_resp.json()
                path = result["path"]

                # Try reading directly off the mounted volume first (fast, reliable)
                if path.startswith("/app_data"):
                    local_path = PRESENTON_DATA / Path(path).relative_to("/app_data")
                    if local_path.exists():
                        return local_path.read_bytes()

                # Fallback — download over HTTP using the same authenticated client
                full_url = path if path.startswith("http") else f"{PRESENTON_URL}{path}"
                dl_resp = await client.get(full_url)
                if dl_resp.status_code == 200 and len(dl_resp.content) > 1000:
                    return dl_resp.content

                raise Exception(f"Could not retrieve file at path: {path}")

        except Exception as e:
            print(f"[Presenton] Failed, falling back to python-pptx: {e}")
            return await self._generate_pptx_fallback(topic, slides, model)
        import httpx
        import asyncio

        PRESENTON_URL = "http://127.0.0.1:5000"
        AUTH = ("admin", "admin")  # default Presenton credentials

        # Step 1: Generate presentation via Presenton API
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{PRESENTON_URL}/api/v1/ppt/presentation/generate",
                auth=AUTH,
                json={
                    "content": topic,
                    "n_slides": slides,
                    "language": "English",
                    "template": "general",
                    "tone": "educational",
                    "verbosity": "standard",
                    "include_title_slide": True,
                    "include_table_of_contents": True,
                    "export_as": "pptx",
                    "instructions": (
                        f"This presentation is for a 13-year-old student. "
                        f"Use vivid real facts, engaging titles, and clear explanations. "
                        f"Make each slide visually interesting with relevant content about {topic}."
                    ),
                }
            )
            resp.raise_for_status()
            result = resp.json()
            presentation_id = result["presentation_id"]
            file_path = result["path"]

        # Step 2: Download the generated PPTX file
        async with httpx.AsyncClient(timeout=30) as client:
            # Download directly from the path endpoint
            download_resp = await client.get(
                f"{PRESENTON_URL}/api/v1/ppt/presentation/{presentation_id}/download",
                auth=AUTH,
            )
            if download_resp.status_code == 200:
                return download_resp.content

            # Fallback: try the direct file endpoint
            download_resp = await client.get(
                f"{PRESENTON_URL}/api/v1/ppt/files/download?path={file_path}",
                auth=AUTH,
            )
            if download_resp.status_code == 200:
                return download_resp.content

        raise Exception("Could not download generated presentation from Presenton")