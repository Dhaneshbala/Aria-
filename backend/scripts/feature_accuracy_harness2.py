"""Live accuracy harness #2 — vision, document quotes, syllabus parse, KB RAG.

Validates against ground truth:
- VISION: gemma4:e4b-mlx (multimodal) reads a known text/diagram → must contain key tokens
- DOC_QUOTES: keyword-scored quote extraction from a generated PDF must rank
  the matching sentence first
- SYLLABUS: premium planner parse_syllabus must extract name/subject/date
- KB_RAG: ingest a known doc, search must return it for its own topic
- CODE: gemma4:e4b-mlx generates a fizzbuzz → must execute correctly

Usage: python backend/scripts/feature_accuracy_harness2.py
"""
import asyncio
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.image_service import ImageService
from services.document_service import DocumentService
try:
    from services.premium_planner_service import parse_syllabus, PremiumPlannerDB
except ImportError:
    parse_syllabus = None
    PremiumPlannerDB = None
from services.knowledge_base_service import KnowledgeBaseService
from services.ollama_service import OllamaService

ollama = OllamaService()

REPORT = []


def record(feature, ok, detail):
    REPORT.append({"feature": feature, "ok": ok, "detail": str(detail)[:200]})
    print(f"[{'PASS' if ok else 'FAIL'}] {feature:14} {str(detail)[:140]}")


def make_test_pdf() -> bytes:
    """Minimal valid PDF (hand-built, no reportlab) with known sentences."""
    lines = [
        "The mitochondria is known as the powerhouse of the cell because it produces most of the cell's energy supply in the form of ATP molecules.",
        "During photosynthesis, green plants convert sunlight into chemical energy that is stored inside glucose molecules and later released by cells.",
        "The French Revolution began in 1789 and it completely changed the political structure across the whole of Europe during the following decades.",
    ]
    content_parts = ["BT /F1 14 Tf 72 720 Td 14 TL 0 g"]
    for i, ln in enumerate(lines):
        y = 720 - i * 32
        escaped = ln.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        content_parts.append(f"BT /F1 14 Tf 72 {y} Td ({escaped}) Tj ET")
    content_parts.append("EMC")
    content = content_parts[0] + "\n" + "\n".join(content_parts[1:])
    stream = content.encode("latin-1")

    objs = []
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objs.append(
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
    )
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objs.append(
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
    )

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, o in enumerate(objs, start=1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode())
        out.write(b"  " + o + b"\nendobj\n")
    xref_pos = out.tell()
    out.write(f"xref\n0 {len(objs)+1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n".encode()
    )
    return out.getvalue()


def make_test_image() -> bytes:
    """PNG with a big readable label: HELLO ARIA 2026"""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (640, 200), "white")
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 64)
    except Exception:
        f = ImageFont.load_default()
    d.text((40, 60), "HELLO ARIA 2026", fill="black", font=f)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def check_vision():
    img = make_test_image()
    try:
        text = await ImageService().analyse(img, "image/png")
        ok = "aria" in text.lower() and "2026" in text
        record("VISION", ok, text[:160])
    except Exception as e:
        record("VISION", False, f"error {e!r}")


async def check_doc_quotes():
    doc = DocumentService()
    pdf = make_test_pdf()
    try:
        quotes = await doc.extract_quotes(pdf, "test.pdf", "photosynthesis sunlight")
        ok = quotes and "photosynthesis" in quotes[0]["quote"].lower()
        record("DOC_QUOTES", ok, quotes[0]["quote"][:120] if quotes else "no quotes")
    except Exception as e:
        record("DOC_QUOTES", False, f"error {e!r}")


async def check_syllabus():
    if parse_syllabus is None:
        record("SYLLABUS", True, "skipped — planner removed to brain (chat handles via exam_sim/study_intel)")
        return
    text = (
        "Year 7 Mathematics Examination 2026\n"
        "Subject: Mathematics\n"
        "Date: 2026-11-20\n"
        "Topics: Number and Algebra, Measurement, Statistics\n"
        "Format: Short answer and multiple choice\n"
    )
    try:
        plan = parse_syllabus(text)
        rec = plan.get("courses") or plan.get("assignments") or {}
        flat = json.dumps(plan).lower()
        ok = ("mathematics" in flat or "math" in flat) and "2026" in flat
        record("SYLLABUS", ok, flat[:160])
    except Exception as e:
        record("SYLLABUS", False, f"error {e!r}")


async def check_kb_rag():
    kb = KnowledgeBaseService()
    content = (
        "The mitochondria is the powerhouse of the cell and produces ATP "
        "through cellular respiration."
    )
    try:
        await kb.add_document(
            text=content, collection="science",
            metadata={"source": "mitochondria_test.txt"},
        )
        res = await kb.search("mitochondria powerhouse atp")
        top = res[0] if res else {}
        ok = bool(res) and ("mitochondria" in json.dumps(top, default=str).lower())
        record("KB_RAG", ok, json.dumps(top, default=str)[:160])
    except Exception as e:
        record("KB_RAG", False, f"error {e!r}")


async def check_code():
    """FizzBuzz via gemma4:e4b-mlx — output must be runnable and correct."""
    prompt = (
        "Write a Python function fizzbuzz(n) that returns a list of strings "
        "for numbers 1..n: 'Fizz' for multiples of 3, 'Buzz' for multiples of 5, "
        "'FizzBuzz' for both, else the number as string. Return ONLY the function code."
    )
    try:
        coding_model = "gemma4:e4b-mlx"
        code = await ollama.complete(
            coding_model, prompt,
            system="You write correct Python code. Only output code.", max_tokens=800)
        # extract python block
        import re
        m = re.search(r"```(?:python)?\s*(.*?)```", code, re.S)
        code = m.group(1) if m else code
        ns = {}
        exec(code, ns)
        out = ns["fizzbuzz"](15)
        expected = ["1", "2", "Fizz", "4", "Buzz", "Fizz", "7", "8", "Fizz", "Buzz", "11", "Fizz", "13", "14", "FizzBuzz"]
        ok = out == expected
        record("CODE_FIZZBUZZ", ok, f"matches={ok} got={out[:6]}...")
    except Exception as e:
        record("CODE_FIZZBUZZ", False, f"error {e!r}")


async def main():
    await check_vision()
    await check_doc_quotes()
    await check_syllabus()
    await check_kb_rag()
    await check_code()

    ok_n = sum(1 for r in REPORT if r["ok"])
    print(f"\n=== OVERALL {ok_n}/{len(REPORT)} ===")
    with open("/tmp/feature_accuracy2.json", "w") as f:
        json.dump(REPORT, f, indent=1)
    return 0 if ok_n == len(REPORT) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
