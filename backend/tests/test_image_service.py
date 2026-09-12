"""Tests for image_service preprocessing, OCR and prompt building.

No Ollama needed — vision calls are covered by the live check, not unit tests.
"""
import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from services.image_service import ImageService, _build_prompt, MAX_EDGE, MIN_EDGE

svc = ImageService()


def _make_image(w: int, h: int, color=(255, 255, 255)) -> bytes:
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_worksheet() -> bytes:
    """Synthetic worksheet: two questions + a triangle, black on white."""
    img = Image.new("RGB", (1200, 800), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=48)
    except TypeError:
        font = ImageFont.load_default()
    d.text((60, 60), "Q1 Solve for x: 2x + 5 = 13", fill="black", font=font)
    d.text((60, 200), "Q2 What is 1/2 of 50?", fill="black", font=font)
    d.polygon([(600, 500), (900, 500), (750, 300)], outline="black", width=4)
    d.text((730, 520), "Triangle ABC", fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_preprocess_downscales_huge_photo():
    out, note = svc._preprocess_sync(_make_image(3000, 2000))
    img = Image.open(io.BytesIO(out))
    assert max(img.size) == MAX_EDGE
    assert img.format == "JPEG"


def test_preprocess_upscales_tiny_image():
    out, note = svc._preprocess_sync(_make_image(200, 100))
    img = Image.open(io.BytesIO(out))
    assert max(img.size) == MIN_EDGE
    assert "upscaled" in note


def test_preprocess_boosts_dark_image():
    out, note = svc._preprocess_sync(_make_image(800, 600, color=(30, 30, 30)))
    assert "contrast-boosted" in note
    img = Image.open(io.BytesIO(out))
    assert max(img.size) <= MAX_EDGE


def test_preprocess_keeps_sane_image():
    out, note = svc._preprocess_sync(_make_image(1200, 800))
    img = Image.open(io.BytesIO(out))
    assert img.size == (1200, 800)


def test_prompt_has_all_sections():
    p = _build_prompt()
    for section in ("HAPPENING", "SUBJECTS", "MEANING", "TEXT", "QUESTIONS"):
        assert section in p


def test_prompt_leads_with_understanding_not_transcription():
    p = _build_prompt("some ocr words")
    assert p.index("HAPPENING") < p.index("TEXT")
    assert "UNDERSTAND" in p


def test_prompt_injects_ocr():
    p = _build_prompt("Q1 Solve for x")
    assert "Q1 Solve for x" in p
    assert "OCR" in p


def test_prompt_without_ocr_has_no_ocr_block():
    assert "OCR" not in _build_prompt("")


def test_ocr_reads_synthetic_worksheet():
    text = svc._ocr_sync_raw(_make_worksheet())
    assert "Solve for x" in text
    assert "2x + 5 = 13" in text
    assert "Triangle ABC" in text


@pytest.mark.asyncio
async def test_ocr_fallback_empty_gives_helpful_message():
    msg = await svc._ocr_fallback_text(b"junk", "test-reason", text="  ")
    assert "brighter" in msg
    assert "test-reason" in msg


@pytest.mark.asyncio
async def test_ocr_fallback_returns_text_when_present():
    msg = await svc._ocr_fallback_text(b"junk", "down", text="hello there")
    assert "hello there" in msg
