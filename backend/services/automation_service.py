"""
Automation — Auto flashcards from PDFs, quiz from notes, paper summariser pipeline.
"""
import json
import logging
from pathlib import Path

from services.ollama_service import OllamaService
from services.document_service import DocumentService
from services.study_service import StudyService
from services.memory_service import MemoryService

logger = logging.getLogger(__name__)

ollama = OllamaService()
doc_svc = DocumentService()
study_svc = StudyService()
memory_svc = MemoryService()


class AutomationService:

    async def auto_flashcards_from_pdf(self, file_bytes: bytes, filename: str, count: int = 10) -> dict:
        """Upload a PDF → auto-extract text → generate flashcards."""
        try:
            text = await doc_svc.extract_text(file_bytes, filename)
            if not text or len(text) < 50:
                return {"error": "Could not extract enough text from the document"}

            # Use AI to generate flashcards from the extracted text
            system = (
                f"Generate {count} clear flashcards from this document content.\n"
                "Format each as: FRONT: [term/question] | BACK: [definition/answer]\n"
                "Focus on key concepts, definitions, and important facts.\n"
                "Make flashcards suitable for a 13-year-old student."
            )
            prompt = text[:4000]
            result = await ollama.complete("qwen3:8b", prompt, system=system, max_tokens=2000)

            # Parse flashcards
            cards = []
            for line in result.split("\n"):
                if "|" in line and "front:" in line.lower():
                    parts = line.split("|", 1)
                    if len(parts) == 2:
                        front = parts[0].replace("FRONT:", "").replace("front:", "").strip()
                        back = parts[1].replace("BACK:", "").replace("back:", "").strip()
                        if front and back:
                            cards.append({"front": front, "back": back})

            return {
                "filename": filename,
                "cards_generated": len(cards),
                "cards": cards[:count],
            }
        except Exception as e:
            return {"error": str(e)}

    async def quiz_from_notes(self, file_bytes: bytes, filename: str, count: int = 5) -> dict:
        """Upload notes → auto-generate quiz questions."""
        try:
            text = await doc_svc.extract_text(file_bytes, filename)
            if not text or len(text) < 50:
                return {"error": "Could not extract enough text from the notes"}

            # Generate quiz from notes
            system = (
                f"Generate {count} multiple-choice quiz questions from these notes.\n"
                "Format each as:\n"
                "Q1: [question]\n"
                "A) option  B) option  C) option  D) option\n"
                "Correct: [letter]\n"
                "Explanation: [one sentence]\n"
                "Make questions test understanding, not just recall."
            )
            prompt = text[:4000]
            result = await ollama.complete("qwen3:8b", prompt, system=system, max_tokens=2000)

            # Parse quiz
            import re
            questions = []
            blocks = re.split(r"\bQ\d+[:.)\s]", result)
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

            return {
                "filename": filename,
                "questions_generated": len(questions),
                "questions": questions[:count],
            }
        except Exception as e:
            return {"error": str(e)}

    async def summarise_paper_pipeline(self, file_bytes: bytes, filename: str) -> dict:
        """Full pipeline: extract text → summarise → key findings → study materials."""
        try:
            text = await doc_svc.extract_text(file_bytes, filename)
            if not text or len(text) < 50:
                return {"error": "Could not extract text from the document"}

            # Generate comprehensive summary
            system = (
                "Analyse this document and provide:\n"
                "1. A concise summary (2-3 paragraphs)\n"
                "2. Key findings or arguments\n"
                "3. Important terminology\n"
                "4. Study questions to test understanding\n"
                "5. Key takeaways\n"
                "Format with clear headings."
            )
            prompt = text[:5000]
            result = await ollama.complete("qwen3:8b", prompt, system=system, max_tokens=2000)

            # Auto-generate flashcards too
            fc_system = (
                "Generate 6 flashcards from this content.\n"
                "Format: FRONT: [term/question] | BACK: [definition/answer]"
            )
            try:
                fc_result = await ollama.complete("qwen3:8b", text[:3000], system=fc_system, max_tokens=1000)
                cards = []
                for line in fc_result.split("\n"):
                    if "|" in line and "front:" in line.lower():
                        parts = line.split("|", 1)
                        if len(parts) == 2:
                            front = parts[0].replace("FRONT:", "").replace("front:", "").strip()
                            back = parts[1].replace("BACK:", "").replace("back:", "").strip()
                            if front and back:
                                cards.append({"front": front, "back": back})
            except Exception:
                cards = []

            return {
                "filename": filename,
                "summary": result,
                "auto_flashcards": cards,
                "text_length": len(text),
            }
        except Exception as e:
            return {"error": str(e)}

    async def batch_process(self, files: list[dict], operation: str = "summarise") -> dict:
        """Process multiple files at once."""
        results = []
        for f in files:
            try:
                file_bytes = f.get("bytes", b"")
                filename = f.get("name", "unknown")
                if operation == "flashcards":
                    result = await self.auto_flashcards_from_pdf(file_bytes, filename)
                elif operation == "quiz":
                    result = await self.quiz_from_notes(file_bytes, filename)
                else:
                    result = await self.summarise_paper_pipeline(file_bytes, filename)
                results.append({"filename": filename, "result": result, "success": "error" not in result})
            except Exception as e:
                results.append({"filename": f.get("name", "?"), "error": str(e), "success": False})

        return {
            "total": len(files),
            "successful": sum(1 for r in results if r.get("success")),
            "results": results,
        }
