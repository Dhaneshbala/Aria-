"""
Image service — makes Study Buddy actually understand what's in a picture.

Pipeline (single local model, no extra RAM):
  1. PREPROCESS — normalise size for the vision model: downscale huge phone
     photos to 1568px on the long edge (detail preserved, tokens bounded),
     upscale tiny images so small text becomes readable, auto-boost contrast
     on dark/flat images (CLAHE). Output is always JPEG.
  2. PARALLEL — OCR (tesseract, with the same preprocessing) + one vision
     call run at the same time. OCR text is injected into the vision prompt
     so the model transcribes accurately instead of guessing words.
  3. UNDERSTANDING-FIRST PROMPT — forces the model to report meaning
     first (what's happening, subjects, spatial relationships, what it
     teaches), with text transcription secondary (OCR already has words).
     Vague one-liners are rejected.
  4. RETRY — empty or one-line answers trigger one simpler retry.
  5. FALLBACK — if vision is down entirely, pure OCR result is returned.

Primary: gemma4:e4b-mlx multimodal (same model as text — no RAM swap).
"""
import asyncio
import base64
import logging

import httpx

import os as _os
_raw = _os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_URL = _raw.rsplit("/api", 1)[0]

logger = logging.getLogger(__name__)

# Vision sweet spots: detail survives, token/time cost stays bounded
MAX_EDGE = 1568        # downscale huge photos to this long edge
MIN_EDGE = 600         # upscale tiny images below this long edge
VISION_TIMEOUT = 90    # seconds — M4 needs room for 1568px images
MIN_GOOD_LEN = 60      # answers shorter than this trigger a retry


def _build_prompt(ocr_text: str = "") -> str:
    """Understanding-first prompt — meaning before transcription.

    The model's main job is to UNDERSTAND the image: what is happening,
    who/what is in it, how things relate in space, and what it means.
    Text transcription is secondary (OCR already captured the words).
    """
    base = (
        "You are looking at an image a student uploaded. Your main job is "
        "to UNDERSTAND it — not just read its words. Report in this order:\n"
        "1. HAPPENING: 2-3 sentences — what is going on in this image? Who "
        "or what are the subjects, what are they doing, and what is the "
        "overall situation or story?\n"
        "2. SUBJECTS & RELATIONSHIPS: list each important thing (people, "
        "animals, objects, shapes). For each: what it looks like (colour, "
        "size, appearance), WHERE it is (top/bottom/left/right/centre, "
        "in front of / behind / next to / above / below what), and how it "
        "relates to the others. Count things explicitly (how many people, "
        "how many shapes).\n"
        "3. MEANING: what does this image show, teach or ask? If it is a "
        "diagram, explain what each part represents and how the parts work "
        "together. If it is a photo, describe the setting, mood and action.\n"
        "4. TEXT (secondary — keep it short): copy visible text exactly, "
        "line by line. If handwriting is unclear, mark guesses with (?). "
        "If no text, write 'No text visible'.\n"
        "5. QUESTIONS: only if it is a worksheet or exam — list each "
        "question numbered (Q1, Q2, ...) with full text.\n"
        "Never answer with a single vague sentence. Spend most words on "
        "sections 1-3 (understanding), not on copying text."
    )
    if ocr_text and ocr_text.strip():
        base += (
            "\n\nAn OCR scan of this image read the following text. Use it to "
            "transcribe accurately, but trust your own eyes for layout, "
            "diagrams and anything the OCR may have garbled:\n"
            f"--- OCR ---\n{ocr_text.strip()[:2000]}"
        )
    return base


class ImageService:

    async def analyse(
        self, image_data: bytes, mime_type: str, model: str = "gemma4:e4b-mlx"
    ) -> str:
        """Full pipeline: preprocess → fast OCR → vision WITH ocr text → validate."""
        loop = asyncio.get_running_loop()
        try:
            processed, prep_note = await loop.run_in_executor(
                None, self._preprocess_sync, image_data
            )
        except Exception as e:
            logger.debug("Preprocess failed, using raw bytes: %s", e)
            processed, prep_note = image_data, "raw"

        # OCR first (~1s) — its text goes into EVERY vision prompt so the
        # model transcribes accurately instead of guessing words
        try:
            ocr_text = await asyncio.wait_for(self._ocr_text(processed), timeout=20)
        except Exception as e:
            logger.debug("OCR failed: %s", e)
            ocr_text = ""

        try:
            vision_result = await self._vision_model(processed, model, ocr_text)
        except Exception as e:
            logger.info("Vision failed, retrying with simple prompt: %s", e)
            try:
                vision_result = await self._vision_model(
                    processed, model, ocr_text, simple=True
                )
            except Exception as e2:
                return await self._ocr_fallback_text(processed, f"vision error: {e2}")

        vision_result = (vision_result or "").strip()
        if len(vision_result) < MIN_GOOD_LEN:
            # Too thin — one simpler retry with OCR context
            try:
                retry = await self._vision_model(
                    processed, model, ocr_text or "",
                    simple=True,
                )
                if retry and len(retry.strip()) > len(vision_result):
                    vision_result = retry.strip()
            except Exception:
                pass

        if not vision_result:
            return await self._ocr_fallback_text(processed, "empty vision result")

        header = f"[Image {prep_note}]\n" if prep_note != "raw" else ""
        return header + vision_result

    # ── Preprocessing ──────────────────────────────────────────────────────

    def _preprocess_sync(self, image_data: bytes) -> tuple[bytes, str]:
        """Normalise size/contrast. Returns (jpeg_bytes, note)."""
        import cv2
        import numpy as np
        from PIL import Image
        from io import BytesIO

        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            pil = Image.open(BytesIO(image_data)).convert("RGB")
            img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

        notes = []
        h, w = img.shape[:2]
        long_edge = max(h, w)

        # Upscale tiny images so small text is readable
        if long_edge < MIN_EDGE:
            scale = MIN_EDGE / long_edge
            img = cv2.resize(img, None, fx=scale, fy=scale,
                             interpolation=cv2.INTER_CUBIC)
            notes.append(f"upscaled {w}x{h}")
            h, w = img.shape[:2]

        # Downscale huge photos — detail survives at 1568, tokens don't explode
        if max(h, w) > MAX_EDGE:
            scale = MAX_EDGE / max(h, w)
            img = cv2.resize(img, None, fx=scale, fy=scale,
                             interpolation=cv2.INTER_AREA)
            notes.append(f"downscaled to {img.shape[1]}x{img.shape[0]}")

        # Auto-contrast dark or flat images (the previously dead enhance step,
        # now wired in and applied only when the image actually needs it)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        mean, std = float(gray.mean()), float(gray.std())
        # Dark photo (mean<90) or flat mid-tone scan (low spread, not white
        # paper — white pages have high mean so they skip the boost)
        if mean < 90 or (std < 40 and mean < 200):
            img = self._clahe_sync(img)
            notes.append("contrast-boosted")

        ok, buffer = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])
        if not ok:
            return image_data, "raw"
        note = ", ".join(notes) if notes else f"{w}x{h} jpeg"
        return buffer.tobytes(), note

    def _clahe_sync(self, img):
        import cv2
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(l)
        return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)

    async def enhance_for_analysis(self, image_data: bytes) -> bytes:
        """Kept for backwards-compat — preprocessing now runs inside analyse()."""
        loop = asyncio.get_running_loop()
        try:
            out, _ = await loop.run_in_executor(None, self._preprocess_sync, image_data)
            return out
        except Exception:
            return image_data

    # ── Vision call ────────────────────────────────────────────────────────

    async def _vision_model(
        self, image_data: bytes, model: str, ocr_text: str = "",
        simple: bool = False,
    ) -> str:
        b64 = base64.b64encode(image_data).decode()
        prompt = (
            "What is happening in this image? Describe the subjects, what "
            "they are doing, where everything is, and what it means. Then "
            "copy any visible text exactly. Be specific, not vague."
            if simple else _build_prompt(ocr_text)
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt, "images": [b64]}
            ],
            "stream": False,
            "options": {"num_ctx": 8192, "temperature": 0.2},
        }
        async with httpx.AsyncClient(timeout=VISION_TIMEOUT) as client:
            r = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
            r.raise_for_status()
            return r.json().get("message", {}).get("content", "") or ""

    # ── OCR ────────────────────────────────────────────────────────────────

    async def _ocr_text(self, image_data: bytes) -> str:
        """Raw OCR text (for prompt injection). Empty string if none."""
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, self._ocr_sync_raw, image_data)
        except Exception as e:
            logger.debug("OCR error: %s", e)
            return ""

    def _ocr_sync_raw(self, image_data: bytes) -> str:
        import cv2
        import numpy as np
        import pytesseract
        from PIL import Image
        from io import BytesIO

        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            img = cv2.cvtColor(np.array(Image.open(BytesIO(image_data)).convert("RGB")),
                               cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        if max(h, w) < 1000:
            scale = 1000 / max(h, w)
            gray = cv2.resize(gray, None, fx=scale, fy=scale,
                              interpolation=cv2.INTER_CUBIC)
        denoised = cv2.fastNlMeansDenoising(gray, h=10)
        _, thresh = cv2.threshold(denoised, 0, 255,
                                  cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return pytesseract.image_to_string(thresh).strip()

    async def _ocr_fallback(self, image_data: bytes) -> str:
        """Legacy entry — full pipeline already tried vision first."""
        text = await self._ocr_text(image_data)
        return await self._ocr_fallback_text(image_data, "", text)

    async def _ocr_fallback_text(
        self, image_data: bytes, reason: str = "", text: str | None = None
    ) -> str:
        if text is None:
            text = await self._ocr_text(image_data)
        if text.strip():
            return f"[OCR Result — vision unavailable ({reason})]\n{text.strip()}"
        return ("Could not read this image: no text found by OCR and the "
                f"vision model is unavailable ({reason}). Try a brighter, "
                "closer photo.")
