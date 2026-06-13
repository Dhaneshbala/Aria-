"""
Image service — analyses images using:
1. qwen2.5-VL (primary, if available)
2. OCR fallback (pytesseract)
3. OpenCV preprocessing for low-quality images
"""
import base64
import asyncio
import httpx
import json
from io import BytesIO

OLLAMA_URL = "http://127.0.0.1:11434"


class ImageService:

    async def analyse(
        self, image_data: bytes, mime_type: str, model: str = "qwen2.5vl:3b"
    ) -> str:
        """Analyse an image — try vision model first, then OCR fallback."""
        # Try vision model
        try:
            result = await self._vision_model(image_data, mime_type, model)
            if result:
                return result
        except Exception:
            pass
        # OCR fallback
        try:
            return await self._ocr_fallback(image_data)
        except Exception as e:
            return f"Could not analyse image: {e}"

    async def _vision_model(self, image_data: bytes, mime_type: str, model: str) -> str:
        b64 = base64.b64encode(image_data).decode()
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": "Please analyse this image in detail. If it contains text, read all of it. If it's a worksheet or diagram, explain what it shows.",
                    "images": [b64],
                }
            ],
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
            return data.get("message", {}).get("content", "")

    async def _ocr_fallback(self, image_data: bytes) -> str:
        """Pytesseract OCR with OpenCV preprocessing."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._ocr_sync, image_data)

    def _ocr_sync(self, image_data: bytes) -> str:
        try:
            import cv2
            import numpy as np
            import pytesseract
            from PIL import Image

            # Decode
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                img = np.array(Image.open(BytesIO(image_data)))

            # Preprocess
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Upscale small images
            h, w = gray.shape
            if max(h, w) < 800:
                scale = 800 / max(h, w)
                gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            # Denoise and threshold
            denoised = cv2.fastNlMeansDenoising(gray, h=10)
            _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            text = pytesseract.image_to_string(thresh)
            if text.strip():
                return f"[OCR Result]\n{text.strip()}"
            return "Image contains no readable text. It may be a diagram or photo."
        except Exception as e:
            return f"OCR not available ({e}). Please describe the image in words."

    async def enhance_for_analysis(self, image_data: bytes) -> bytes:
        """Enhance image quality before vision model."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._enhance_sync, image_data)

    def _enhance_sync(self, image_data: bytes) -> bytes:
        try:
            import cv2
            import numpy as np
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            # Enhance contrast
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            enhanced = cv2.merge([l, a, b])
            enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
            _, buffer = cv2.imencode(".jpg", enhanced)
            return buffer.tobytes()
        except Exception:
            return image_data
