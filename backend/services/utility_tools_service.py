"""
Utility Tools — Graph plotter, citation generator, smart summariser, unit converter.
"""
import json
import logging
import re
import math
from datetime import datetime

from services.ollama_service import OllamaService

logger = logging.getLogger(__name__)

ollama = OllamaService()


class UtilityToolsService:

    # ── Smart Summariser ──────────────────────────────────────────────────────

    async def smart_summarise(self, text: str, level: str = "paragraph", model: str = "qwen3:8b") -> dict:
        """Summarise text at different detail levels."""
        levels = {
            "one_liner": "Summarise in ONE sentence only.",
            "paragraph": "Summarise in a clear paragraph (3-5 sentences).",
            "detailed": "Provide a detailed summary with key points, arguments, and conclusion.",
        }
        system = f"{levels.get(level, levels['paragraph'])}\nBe clear and concise."
        try:
            result = await ollama.complete(model, text[:5000], system=system, max_tokens=1000 if level != "detailed" else 2000)
            return {"level": level, "summary": result.strip()}
        except Exception as e:
            return {"error": str(e)}

    # ── Citation Generator ────────────────────────────────────────────────────

    def generate_citation(self, source: dict, style: str = "apa") -> str:
        """Generate a citation in various styles."""
        author = source.get("author", "Unknown Author")
        title = source.get("title", "Untitled")
        year = source.get("year", str(datetime.now().year))
        publisher = source.get("publisher", "")
        url = source.get("url", "")
        journal = source.get("journal", "")
        volume = source.get("volume", "")
        pages = source.get("pages", "")
        accessed = source.get("accessed", datetime.now().strftime("%d %b %Y"))

        if style == "apa":
            if journal:
                return f"{author} ({year}). {title}. *{journal}*, *{volume}*, {pages}."
            elif url:
                return f"{author} ({year}). {title}. Retrieved {accessed}, from {url}"
            else:
                return f"{author} ({year}). *{title}*. {publisher}."

        elif style == "mla":
            if journal:
                return f"{author}. \"{title}.\" {journal}, vol. {volume}, {year}, pp. {pages}."
            else:
                return f'{author}. *{title}*. {publisher}, {year}.'

        elif style == "harvard":
            if url:
                return f"{author} ({year}) '{title}', Available at: {url} (Accessed: {accessed})."
            else:
                return f"{author} ({year}) *{title}*. {publisher}."

        elif style == "chicago":
            if url:
                return f'{author}. "{title}." Accessed {accessed}. {url}.'
            else:
                return f"{author}. *{title}*. {publisher}, {year}."

        return f"{author} ({year}). {title}."

    # ── Unit Converter ────────────────────────────────────────────────────────

    def convert_unit(self, value: float, from_unit: str, to_unit: str) -> dict:
        """Convert between common units with context-aware suggestions."""
        conversions = {
            # Length
            ("m", "ft"): 3.28084, ("ft", "m"): 0.3048,
            ("km", "mi"): 0.621371, ("mi", "km"): 1.60934,
            ("cm", "in"): 0.393701, ("in", "cm"): 2.54,
            ("mm", "in"): 0.0393701, ("in", "mm"): 25.4,
            # Mass
            ("kg", "lb"): 2.20462, ("lb", "kg"): 0.453592,
            ("g", "oz"): 0.035274, ("oz", "g"): 28.3495,
            # Temperature
            ("C", "F"): "special", ("F", "C"): "special",
            ("C", "K"): "special", ("K", "C"): "special",
            # Volume
            ("L", "gal"): 0.264172, ("gal", "L"): 3.78541,
            ("mL", "fl_oz"): 0.033814, ("fl_oz", "mL"): 29.5735,
            # Speed
            ("km/h", "mph"): 0.621371, ("mph", "km/h"): 1.60934,
            ("m/s", "km/h"): 3.6, ("km/h", "m/s"): 0.277778,
            # Data
            ("KB", "MB"): 0.001, ("MB", "GB"): 0.001,
            ("GB", "TB"): 0.001, ("TB", "GB"): 1000,
        }

        from_u = from_unit.upper().replace("°", "").replace("DEG", "")
        to_u = to_unit.upper().replace("°", "").replace("DEG", "")

        # Handle temperature specially
        if from_u in ("C", "CELSIUS") and to_u in ("F", "FAHRENHEIT"):
            result = value * 9/5 + 32
            formula = "°F = °C × 9/5 + 32"
        elif from_u in ("F", "FAHRENHEIT") and to_u in ("C", "CELSIUS"):
            result = (value - 32) * 5/9
            formula = "°C = (°F − 32) × 5/9"
        elif from_u in ("C", "CELSIUS") and to_u in ("K", "KELVIN"):
            result = value + 273.15
            formula = "K = °C + 273.15"
        elif from_u in ("K", "KELVIN") and to_u in ("C", "CELSIUS"):
            result = value - 273.15
            formula = "°C = K − 273.15"
        else:
            key = (from_u, to_u)
            if key in conversions:
                result = value * conversions[key]
                formula = f"1 {from_unit} = {conversions[key]} {to_unit}"
            else:
                return {"error": f"Unknown conversion: {from_unit} → {to_unit}"}

        return {
            "input": value,
            "from": from_unit,
            "output": round(result, 4),
            "to": to_unit,
            "formula": formula,
        }

    # ── Graph Plotter ─────────────────────────────────────────────────────────

    def plot_function(self, expression: str, x_min: float = -10, x_max: float = 10, points: int = 200) -> dict:
        """Plot a mathematical function and return SVG-like data points."""
        import re as _re
        try:
            # Clean expression
            expr = expression.replace("^", "**")
            # Generate x values
            step = (x_max - x_min) / points
            data_points = []

            for i in range(points + 1):
                x = x_min + i * step
                try:
                    # Safe evaluation with math functions
                    import math
                    local_vars = {
                        "x": x, "pi": math.pi, "e": math.e,
                        "sin": math.sin, "cos": math.cos, "tan": math.tan,
                        "log": math.log, "log10": math.log10, "sqrt": math.sqrt,
                        "abs": abs, "pow": pow,
                    }
                    y = eval(expr, {"__builtins__": {}}, local_vars)
                    if isinstance(y, (int, float)) and not math.isnan(y) and not math.isinf(y):
                        data_points.append({"x": round(x, 3), "y": round(y, 3)})
                except Exception:
                    continue

            if not data_points:
                return {"error": f"Could not plot: {expression}"}

            return {
                "expression": expression,
                "x_range": [x_min, x_max],
                "points": data_points[:200],
                "y_min": min(p["y"] for p in data_points),
                "y_max": max(p["y"] for p in data_points),
            }
        except Exception as e:
            return {"error": str(e)}

    # ── Handwriting OCR ───────────────────────────────────────────────────────

    async def process_handwriting(self, image_bytes: bytes, mime_type: str = "image/jpeg", model: str = "qwen2.5vl:3b") -> dict:
        """Process handwritten text from an image."""
        from services.image_service import ImageService
        image_svc = ImageService()
        try:
            result = await image_svc.analyse(image_bytes, mime_type, model)
            return {
                "text": result,
                "type": "handwriting",
            }
        except Exception as e:
            return {"error": f"OCR failed: {e}"}

    # ── Voice to Flashcards ───────────────────────────────────────────────────

    async def voice_to_flashcards(self, transcript: str, count: int = 5, model: str = "qwen3:8b") -> dict:
        """Convert voice transcript into flashcards."""
        system = (
            f"Generate {count} flashcards from this spoken content.\n"
            "Format: FRONT: [question] | BACK: [answer]\n"
            "Focus on the main concepts mentioned."
        )
        try:
            result = await ollama.complete(model, transcript[:3000], system=system, max_tokens=1000)
            cards = []
            for line in result.split("\n"):
                if "|" in line and "front:" in line.lower():
                    parts = line.split("|", 1)
                    if len(parts) == 2:
                        front = parts[0].replace("FRONT:", "").replace("front:", "").strip()
                        back = parts[1].replace("BACK:", "").replace("back:", "").strip()
                        if front and back:
                            cards.append({"front": front, "back": back})
            return {"transcript": transcript, "cards": cards}
        except Exception as e:
            return {"error": str(e)}
