"""Build ARIA's diagram-skills training set (real LoRA data, MLX chat format).

Every example pairs a Year 7 NSW-style question with an answer that contains
a CORRECT, hand-checked ```svg / ```mermaid diagram in ARIA's production
style (520x320, #fafafa background, #7c6af7/#f59e0b highlights).

Outputs (mlx_lm.lora format — {"messages": [...]} chat JSONL):
  ~/.aria_data/lora_data_diagrams/train.jsonl
  ~/.aria_data/lora_data_diagrams/valid.jsonl
  ~/.aria_data/lora_data_diagrams/test.jsonl

Run from the backend directory:
    ../.venv/bin/python scripts/make_diagram_dataset.py
"""
import json
import random
import xml.etree.ElementTree as ET
from pathlib import Path

OUT_DIR = Path.home() / ".aria_data" / "lora_data_diagrams"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DIAGRAM_SYSTEM = (
    "You are ARIA, a friendly AI study assistant for a 13-year-old Australian "
    "student following the NSW curriculum. When explaining anything spatial or "
    "structural (angles, triangles, parallel lines, fractions, cycles, cells, "
    "orbits), you ALWAYS include one clear visual diagram. "
    "Use ```svg for precise geometry with this style: "
    '<svg width="520" height="320" viewBox="0 0 520 320" '
    'xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">, '
    "light #fafafa background, dark #1e1f20 lines (2.5px), highlight rays "
    "#7c6af7 (3px) and #f59e0b (3px), angle arcs #7c6af7 dashed, labels 13px "
    "bold #1e1f20, degree badges as white text on #7c6af7 pills, right angles "
    "marked with a small square, vertex dots #7c6af7. Add a small caps title "
    "at the top. Use ```mermaid (graph TD, 3-8 short nodes) for cycles and "
    "flows. Every diagram must be valid, complete, and geometrically correct."
)

E = []  # (user, assistant)


def add(user: str, assistant: str) -> None:
    E.append((user, assistant))


# ── 1. Angle notation / vertex ──────────────────────────────────────────────
add(
    "In the angle notation angle PQR, which letter is the vertex? Draw it.",
    "The vertex is **Q** — the middle letter. The arms are QP and QR.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">ANGLE PQR — Q IS THE VERTEX</text>'
    '<line x1="260" y1="200" x2="120" y2="130" stroke="#7c6af7" stroke-width="3"/>'
    '<line x1="260" y1="200" x2="410" y2="150" stroke="#f59e0b" stroke-width="3"/>'
    '<circle cx="260" cy="200" r="6" fill="#7c6af7"/>'
    '<path d="M 200 185 A 65 65 0 0 1 315 170" fill="none" stroke="#7c6af7" stroke-width="1.8" stroke-dasharray="5 4"/>'
    '<text x="105" y="125" font-size="14" font-weight="700" fill="#1e1f20">P</text>'
    '<text x="255" y="230" font-size="14" font-weight="700" fill="#1e1f20">Q (vertex)</text>'
    '<text x="415" y="150" font-size="14" font-weight="700" fill="#1e1f20">R</text>'
    "</svg>\n```",
)

# ── 2. Right angle ──────────────────────────────────────────────────────────
add(
    "What is a right angle? Show me.",
    "A right angle measures exactly **90°** — like the corner of a book.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">RIGHT ANGLE — 90 DEGREES</text>'
    '<line x1="150" y1="230" x2="150" y2="90" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="150" y1="230" x2="370" y2="230" stroke="#1e1f20" stroke-width="2.5"/>'
    '<rect x="150" y="210" width="20" height="20" fill="none" stroke="#f59e0b" stroke-width="2.5"/>'
    '<rect x="200" y="120" width="52" height="24" rx="8" fill="#7c6af7"/>'
    '<text x="226" y="137" text-anchor="middle" font-size="13" font-weight="700" fill="#ffffff">90°</text>'
    '<text x="140" y="255" font-size="13" fill="#1e1f20">corner</text>'
    "</svg>\n```",
)

# ── 3. Acute vs obtuse ──────────────────────────────────────────────────────
add(
    "What is the difference between acute and obtuse angles?",
    "Acute angles are **less than 90°** (sharp). Obtuse angles are **between 90° and 180°** (wide).\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">ACUTE VS OBTUSE</text>'
    '<line x1="130" y1="230" x2="60" y2="230" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="130" y1="230" x2="180" y2="120" stroke="#7c6af7" stroke-width="3"/>'
    '<path d="M 100 230 A 32 32 0 0 1 140 205" fill="none" stroke="#7c6af7" stroke-width="1.8" stroke-dasharray="5 4"/>'
    '<text x="130" y="270" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">Acute: 45°</text>'
    '<line x1="390" y1="230" x2="300" y2="230" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="390" y1="230" x2="440" y2="120" stroke="#f59e0b" stroke-width="3"/>'
    '<path d="M 358 230 A 34 34 0 0 1 400 200" fill="none" stroke="#f59e0b" stroke-width="1.8" stroke-dasharray="5 4"/>'
    '<text x="390" y="270" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">Obtuse: 120°</text>'
    "</svg>\n```",
)

# ── 4. Angles on a straight line ────────────────────────────────────────────
add(
    "Two angles sit on a straight line. One is 113 degrees. What is the other? Draw it.",
    "Angles on a straight line add to **180°**, so the other is 180 − 113 = **67°**.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">ANGLES ON A STRAIGHT LINE = 180°</text>'
    '<line x1="60" y1="200" x2="460" y2="200" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="260" y1="200" x2="330" y2="80" stroke="#7c6af7" stroke-width="3"/>'
    '<path d="M 200 200 A 60 60 0 0 0 285 145" fill="none" stroke="#7c6af7" stroke-width="1.8" stroke-dasharray="5 4"/>'
    '<path d="M 320 200 A 60 60 0 0 1 300 145" fill="none" stroke="#f59e0b" stroke-width="1.8" stroke-dasharray="5 4"/>'
    '<text x="180" y="180" font-size="13" font-weight="700" fill="#7c6af7">113°</text>'
    '<text x="330" y="180" font-size="13" font-weight="700" fill="#f59e0b">67°</text>'
    '<text x="260" y="250" text-anchor="middle" font-size="13" fill="#1e1f20">113° + 67° = 180°</text>'
    "</svg>\n```",
)

# ── 5. Angles at a point ────────────────────────────────────────────────────
add(
    "What do angles around a point add up to? Show me with a diagram.",
    "Angles around a point add to **360°** — one full turn.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">ANGLES AT A POINT = 360°</text>'
    '<circle cx="260" cy="180" r="90" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="260" y1="180" x2="260" y2="90" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="260" y1="180" x2="350" y2="180" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="260" y1="180" x2="260" y2="270" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="260" y1="180" x2="170" y2="180" stroke="#1e1f20" stroke-width="2.5"/>'
    '<circle cx="260" cy="180" r="6" fill="#7c6af7"/>'
    '<text x="285" y="140" font-size="13" font-weight="700" fill="#1e1f20">90°</text>'
    '<text x="285" y="220" font-size="13" font-weight="700" fill="#1e1f20">90°</text>'
    '<text x="200" y="140" font-size="13" font-weight="700" fill="#1e1f20">90°</text>'
    '<text x="200" y="220" font-size="13" font-weight="700" fill="#1e1f20">90°</text>'
    "</svg>\n```",
)

# ── 6. Complementary angles ─────────────────────────────────────────────────
add(
    "What are complementary angles? Give an example with a diagram.",
    "Complementary angles add to **90°**. Example: 30° + 60°.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">COMPLEMENTARY ANGLES = 90°</text>'
    '<line x1="160" y1="230" x2="160" y2="110" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="160" y1="230" x2="360" y2="230" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="160" y1="230" x2="320" y2="140" stroke="#7c6af7" stroke-width="3"/>'
    '<rect x="160" y="210" width="20" height="20" fill="none" stroke="#f59e0b" stroke-width="2.5"/>'
    '<text x="200" y="215" font-size="13" font-weight="700" fill="#7c6af7">30°</text>'
    '<text x="265" y="185" font-size="13" font-weight="700" fill="#f59e0b">60°</text>'
    '<text x="260" y="270" text-anchor="middle" font-size="13" fill="#1e1f20">30° + 60° = 90°</text>'
    "</svg>\n```",
)

# ── 7. Vertically opposite angles ───────────────────────────────────────────
add(
    "When two lines cross, which angles are equal? Draw it.",
    "Vertically opposite angles are equal — the pairs across the X from each other.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">VERTICALLY OPPOSITE ANGLES ARE EQUAL</text>'
    '<line x1="140" y1="80" x2="380" y2="260" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="380" y1="80" x2="140" y2="260" stroke="#1e1f20" stroke-width="2.5"/>'
    '<circle cx="260" cy="170" r="6" fill="#7c6af7"/>'
    '<text x="260" y="120" text-anchor="middle" font-size="14" font-weight="700" fill="#7c6af7">a</text>'
    '<text x="260" y="235" text-anchor="middle" font-size="14" font-weight="700" fill="#7c6af7">a</text>'
    '<text x="185" y="175" text-anchor="middle" font-size="14" font-weight="700" fill="#f59e0b">b</text>'
    '<text x="335" y="175" text-anchor="middle" font-size="14" font-weight="700" fill="#f59e0b">b</text>'
    '<text x="260" y="285" text-anchor="middle" font-size="13" fill="#1e1f20">a = a and b = b</text>'
    "</svg>\n```",
)

# ── 8. Parallel lines + transversal ─────────────────────────────────────────
add(
    "Draw parallel lines cut by a transversal and label corresponding angles.",
    "The double arrows mark parallel lines. Corresponding angles (same corner position) are equal.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">PARALLEL LINES + TRANSVERSAL</text>'
    '<line x1="80" y1="120" x2="440" y2="120" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="80" y1="220" x2="440" y2="220" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="180" y1="60" x2="340" y2="280" stroke="#7c6af7" stroke-width="3"/>'
    '<text x="120" y="112" font-size="16" font-weight="700" fill="#1e1f20">&gt;&gt;</text>'
    '<text x="120" y="212" font-size="16" font-weight="700" fill="#1e1f20">&gt;&gt;</text>'
    '<circle cx="238" cy="120" r="10" fill="none" stroke="#f59e0b" stroke-width="2.5"/>'
    '<circle cx="282" cy="220" r="10" fill="none" stroke="#f59e0b" stroke-width="2.5"/>'
    '<text x="238" y="155" text-anchor="middle" font-size="12" fill="#1e1f20">corresponding</text>'
    '<text x="282" y="255" text-anchor="middle" font-size="12" fill="#1e1f20">equal pair</text>'
    "</svg>\n```",
)

# ── 9. Triangle angle sum ───────────────────────────────────────────────────
add(
    "Why do the angles in a triangle add to 180 degrees? Show me.",
    "Tear the three corners off any triangle and they fit exactly on a straight line: 50° + 60° + 70° = **180°**.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">TRIANGLE ANGLES ADD TO 180°</text>'
    '<polygon points="260,70 120,230 400,230" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<circle cx="260" cy="70" r="6" fill="#7c6af7"/>'
    '<circle cx="120" cy="230" r="6" fill="#7c6af7"/>'
    '<circle cx="400" cy="230" r="6" fill="#7c6af7"/>'
    '<text x="260" y="105" text-anchor="middle" font-size="13" font-weight="700" fill="#7c6af7">60°</text>'
    '<text x="160" y="220" text-anchor="middle" font-size="13" font-weight="700" fill="#7c6af7">50°</text>'
    '<text x="360" y="220" text-anchor="middle" font-size="13" font-weight="700" fill="#7c6af7">70°</text>'
    '<text x="260" y="270" text-anchor="middle" font-size="13" fill="#1e1f20">50° + 60° + 70° = 180°</text>'
    "</svg>\n```",
)

# ── 10. Triangle types ──────────────────────────────────────────────────────
add(
    "What are the three types of triangles by side length? Draw them.",
    "Equilateral (3 equal sides), isosceles (2 equal sides), scalene (no equal sides).\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">TRIANGLES BY SIDE LENGTH</text>'
    '<polygon points="90,80 40,180 140,180" fill="none" stroke="#7c6af7" stroke-width="2.5"/>'
    '<text x="90" y="210" text-anchor="middle" font-size="12" font-weight="700" fill="#1e1f20">equilateral</text>'
    '<polygon points="260,80 210,180 310,180" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="235" y1="130" x2="245" y2="138" stroke="#f59e0b" stroke-width="2.5"/>'
    '<line x1="285" y1="130" x2="275" y2="138" stroke="#f59e0b" stroke-width="2.5"/>'
    '<text x="260" y="210" text-anchor="middle" font-size="12" font-weight="700" fill="#1e1f20">isosceles</text>'
    '<polygon points="430,80 370,180 480,180" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<text x="425" y="210" text-anchor="middle" font-size="12" font-weight="700" fill="#1e1f20">scalene</text>'
    '<text x="260" y="250" text-anchor="middle" font-size="12" fill="#5f6368">tick marks show equal sides</text>'
    "</svg>\n```",
)

# ── 11. Pythagoras 3-4-5 ────────────────────────────────────────────────────
add(
    "Draw a right-angled triangle and label the hypotenuse.",
    "The hypotenuse is the longest side, always opposite the right angle. In a 3-4-5 triangle: 3² + 4² = 5².\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">RIGHT TRIANGLE — HYPOTENUSE</text>'
    '<polygon points="170,230 170,90 370,230" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<rect x="170" y="210" width="20" height="20" fill="none" stroke="#f59e0b" stroke-width="2.5"/>'
    '<text x="150" y="165" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">3</text>'
    '<text x="270" y="250" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">4</text>'
    '<text x="285" y="150" text-anchor="middle" font-size="13" font-weight="700" fill="#7c6af7">5 hypotenuse</text>'
    '<text x="260" y="285" text-anchor="middle" font-size="13" fill="#1e1f20">3² + 4² = 9 + 16 = 25 = 5²</text>'
    "</svg>\n```",
)

# ── 12. Angle bisector ──────────────────────────────────────────────────────
add(
    "What does an angle bisector do? Draw a 60 degree angle split in half.",
    "An angle bisector cuts an angle into two equal halves: 60° becomes 30° + 30°.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">ANGLE BISECTOR — 60° INTO 30° + 30°</text>'
    '<line x1="160" y1="230" x2="420" y2="230" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="160" y1="230" x2="375" y2="110" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="160" y1="230" x2="400" y2="170" stroke="#7c6af7" stroke-width="3" stroke-dasharray="8 5"/>'
    '<circle cx="160" cy="230" r="6" fill="#7c6af7"/>'
    '<text x="300" y="215" font-size="13" font-weight="700" fill="#1e1f20">30°</text>'
    '<text x="300" y="165" font-size="13" font-weight="700" fill="#1e1f20">30°</text>'
    "</svg>\n```",
)

# ── 13. Fraction number line ────────────────────────────────────────────────
add(
    "Show me one half and three quarters on a number line.",
    "On a number line from 0 to 1, halves split it into 2 parts and quarters into 4.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">FRACTIONS ON A NUMBER LINE</text>'
    '<line x1="60" y1="160" x2="460" y2="160" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="60" y1="150" x2="60" y2="170" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="160" y1="150" x2="160" y2="170" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="260" y1="145" x2="260" y2="175" stroke="#7c6af7" stroke-width="3"/>'
    '<line x1="360" y1="150" x2="360" y2="170" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="460" y1="150" x2="460" y2="170" stroke="#1e1f20" stroke-width="2.5"/>'
    '<text x="60" y="195" text-anchor="middle" font-size="13" fill="#1e1f20">0</text>'
    '<text x="260" y="195" text-anchor="middle" font-size="13" font-weight="700" fill="#7c6af7">1/2</text>'
    '<text x="360" y="195" text-anchor="middle" font-size="13" font-weight="700" fill="#f59e0b">3/4</text>'
    '<text x="460" y="195" text-anchor="middle" font-size="13" fill="#1e1f20">1</text>'
    "</svg>\n```",
)

# ── 14. Fraction bars ───────────────────────────────────────────────────────
add(
    "Which is bigger, one half or three eighths? Draw fraction bars.",
    "1/2 = 4/8, which is bigger than 3/8. The bars make it visible.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">1/2 VS 3/8 — FRACTION BARS</text>'
    '<rect x="80" y="80" width="360" height="44" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<rect x="80" y="80" width="180" height="44" fill="#7c6af7" opacity="0.55"/>'
    '<line x1="260" y1="80" x2="260" y2="124" stroke="#1e1f20" stroke-width="2.5"/>'
    '<text x="260" y="155" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">1/2</text>'
    '<rect x="80" y="190" width="360" height="44" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<rect x="80" y="190" width="135" height="44" fill="#f59e0b" opacity="0.55"/>'
    '<line x1="170" y1="190" x2="170" y2="234" stroke="#1e1f20" stroke-width="1.5"/>'
    '<line x1="260" y1="190" x2="260" y2="234" stroke="#1e1f20" stroke-width="1.5"/>'
    '<line x1="350" y1="190" x2="350" y2="234" stroke="#1e1f20" stroke-width="1.5"/>'
    '<text x="260" y="265" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">3/8</text>'
    "</svg>\n```",
)

# ── 15. Multiplication array ────────────────────────────────────────────────
add(
    "Draw 3 times 4 as an array of dots.",
    "An array shows 3 rows of 4 dots: 3 × 4 = **12**.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">3 × 4 ARRAY = 12</text>'
    '<circle cx="200" cy="90" r="9" fill="#7c6af7"/><circle cx="240" cy="90" r="9" fill="#7c6af7"/><circle cx="280" cy="90" r="9" fill="#7c6af7"/><circle cx="320" cy="90" r="9" fill="#7c6af7"/>'
    '<circle cx="200" cy="140" r="9" fill="#7c6af7"/><circle cx="240" cy="140" r="9" fill="#7c6af7"/><circle cx="280" cy="140" r="9" fill="#7c6af7"/><circle cx="320" cy="140" r="9" fill="#7c6af7"/>'
    '<circle cx="200" cy="190" r="9" fill="#f59e0b"/><circle cx="240" cy="190" r="9" fill="#f59e0b"/><circle cx="280" cy="190" r="9" fill="#f59e0b"/><circle cx="320" cy="190" r="9" fill="#f59e0b"/>'
    '<text x="260" y="240" text-anchor="middle" font-size="13" fill="#1e1f20">3 rows × 4 columns = 12 dots</text>'
    "</svg>\n```",
)

# ── 16. Clock 3 o'clock ─────────────────────────────────────────────────────
add(
    "What angle do the clock hands make at 3 o'clock? Draw it.",
    "At 3:00 the hands form a perfect **right angle (90°)**.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">CLOCK AT 3:00 — RIGHT ANGLE</text>'
    '<circle cx="260" cy="180" r="85" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="260" y1="180" x2="260" y2="110" stroke="#7c6af7" stroke-width="3"/>'
    '<line x1="260" y1="180" x2="330" y2="180" stroke="#f59e0b" stroke-width="3"/>'
    '<circle cx="260" cy="180" r="6" fill="#1e1f20"/>'
    '<rect x="260" y="160" width="20" height="20" fill="none" stroke="#f59e0b" stroke-width="2.5"/>'
    '<text x="260" y="290" text-anchor="middle" font-size="13" fill="#1e1f20">minute hand up, hour hand right = 90°</text>'
    "</svg>\n```",
)

# ── 17. Circle parts ────────────────────────────────────────────────────────
add(
    "Label the radius, diameter and circumference of a circle.",
    "Radius = centre to edge. Diameter = straight across (2 × radius). Circumference = distance around.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">PARTS OF A CIRCLE</text>'
    '<circle cx="250" cy="180" r="85" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<circle cx="250" cy="180" r="5" fill="#7c6af7"/>'
    '<line x1="250" y1="180" x2="335" y2="180" stroke="#7c6af7" stroke-width="3"/>'
    '<text x="295" y="170" text-anchor="middle" font-size="12" font-weight="700" fill="#7c6af7">radius</text>'
    '<line x1="165" y1="180" x2="335" y2="180" stroke="#f59e0b" stroke-width="2" stroke-dasharray="8 5"/>'
    '<text x="250" y="215" text-anchor="middle" font-size="12" font-weight="700" fill="#f59e0b">diameter</text>'
    '<text x="250" y="290" text-anchor="middle" font-size="13" fill="#1e1f20">circumference = the whole rim (2πr)</text>'
    "</svg>\n```",
)

# ── 18. Area of rectangle ───────────────────────────────────────────────────
add(
    "Draw a 4 by 3 rectangle and work out its area.",
    "Area = length × width = 4 × 3 = **12 square units**. Count the squares.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">AREA = LENGTH × WIDTH</text>'
    '<rect x="160" y="70" width="200" height="150" fill="#7c6af7" opacity="0.15" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="210" y1="70" x2="210" y2="220" stroke="#1e1f20" stroke-width="1" opacity="0.4"/>'
    '<line x1="260" y1="70" x2="260" y2="220" stroke="#1e1f20" stroke-width="1" opacity="0.4"/>'
    '<line x1="310" y1="70" x2="310" y2="220" stroke="#1e1f20" stroke-width="1" opacity="0.4"/>'
    '<line x1="160" y1="120" x2="360" y2="120" stroke="#1e1f20" stroke-width="1" opacity="0.4"/>'
    '<line x1="160" y1="170" x2="360" y2="170" stroke="#1e1f20" stroke-width="1" opacity="0.4"/>'
    '<text x="260" y="250" text-anchor="middle" font-size="13" fill="#1e1f20">4 across × 3 down = 12 squares</text>'
    "</svg>\n```",
)

# ── 19. Coordinate point ────────────────────────────────────────────────────
add(
    "Plot the point (3, 2) on a coordinate grid.",
    "Go 3 across (x) then 2 up (y) from the origin (0, 0).\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">PLOTTING (3, 2)</text>'
    '<line x1="110" y1="250" x2="420" y2="250" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="110" y1="250" x2="110" y2="60" stroke="#1e1f20" stroke-width="2.5"/>'
    '<text x="425" y="253" font-size="13" font-weight="700" fill="#1e1f20">x</text>'
    '<text x="113" y="55" font-size="13" font-weight="700" fill="#1e1f20">y</text>'
    '<line x1="110" y1="250" x2="248" y2="250" stroke="#7c6af7" stroke-width="2" stroke-dasharray="6 4"/>'
    '<line x1="248" y1="250" x2="248" y2="174" stroke="#7c6af7" stroke-width="2" stroke-dasharray="6 4"/>'
    '<circle cx="248" cy="174" r="7" fill="#f59e0b"/>'
    '<text x="262" y="170" font-size="13" font-weight="700" fill="#1e1f20">(3, 2)</text>'
    '<text x="110" y="268" text-anchor="middle" font-size="12" fill="#1e1f20">0</text>'
    "</svg>\n```",
)

# ── 20. Supplementary angles ────────────────────────────────────────────────
add(
    "What are supplementary angles? Example with diagram.",
    "Supplementary angles add to **180°**. Example: 120° + 60°.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">SUPPLEMENTARY ANGLES = 180°</text>'
    '<line x1="80" y1="210" x2="440" y2="210" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="260" y1="210" x2="200" y2="90" stroke="#7c6af7" stroke-width="3"/>'
    '<path d="M 200 210 A 62 62 0 0 1 240 152" fill="none" stroke="#7c6af7" stroke-width="1.8" stroke-dasharray="5 4"/>'
    '<path d="M 320 210 A 62 62 0 0 0 240 152" fill="none" stroke="#f59e0b" stroke-width="1.8" stroke-dasharray="5 4"/>'
    '<text x="185" y="195" font-size="13" font-weight="700" fill="#7c6af7">120°</text>'
    '<text x="320" y="195" font-size="13" font-weight="700" fill="#f59e0b">60°</text>'
    '<text x="260" y="255" text-anchor="middle" font-size="13" fill="#1e1f20">120° + 60° = 180°</text>'
    "</svg>\n```",
)

# ── 21. Perimeter ───────────────────────────────────────────────────────────
add(
    "Draw a square with side 5 cm and find its perimeter.",
    "Perimeter = 4 × side = 4 × 5 = **20 cm**.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">PERIMETER OF A SQUARE</text>'
    '<rect x="185" y="70" width="150" height="150" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<text x="260" y="60" text-anchor="middle" font-size="13" font-weight="700" fill="#7c6af7">5 cm</text>'
    '<text x="260" y="245" text-anchor="middle" font-size="13" fill="#1e1f20">P = 5 + 5 + 5 + 5 = 20 cm</text>'
    "</svg>\n```",
)

# ── 22. Solar system orbits ─────────────────────────────────────────────────
add(
    "Draw the inner planets orbiting the Sun.",
    "The Sun sits in the centre. Mercury, Venus, Earth and Mars orbit it in that order.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">INNER SOLAR SYSTEM</text>'
    '<circle cx="260" cy="180" r="45" fill="none" stroke="#1e1f20" stroke-width="1" stroke-dasharray="5 4" opacity="0.5"/>'
    '<circle cx="260" cy="180" r="75" fill="none" stroke="#1e1f20" stroke-width="1" stroke-dasharray="5 4" opacity="0.5"/>'
    '<circle cx="260" cy="180" r="105" fill="none" stroke="#1e1f20" stroke-width="1" stroke-dasharray="5 4" opacity="0.5"/>'
    '<circle cx="260" cy="180" r="130" fill="none" stroke="#1e1f20" stroke-width="1" stroke-dasharray="5 4" opacity="0.5"/>'
    '<circle cx="260" cy="180" r="22" fill="#f59e0b"/>'
    '<text x="260" y="185" text-anchor="middle" font-size="11" font-weight="700" fill="#ffffff">SUN</text>'
    '<circle cx="305" cy="180" r="6" fill="#7c6af7"/>'
    '<circle cx="260" cy="105" r="8" fill="#7c6af7"/>'
    '<circle cx="155" cy="180" r="9" fill="#7c6af7"/>'
    '<circle cx="260" cy="50" r="7" fill="#f59e0b"/>'
    '<text x="320" y="150" font-size="11" fill="#1e1f20">Mercury Venus Earth Mars</text>'
    "</svg>\n```",
)

# ── 23. Plant cell labels ───────────────────────────────────────────────────
add(
    "Draw a simple plant cell and label three parts.",
    "Three key parts: cell wall (outer support), nucleus (control centre), chloroplast (photosynthesis).\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">SIMPLE PLANT CELL</text>'
    '<rect x="130" y="60" width="260" height="190" rx="40" fill="none" stroke="#1e1f20" stroke-width="3"/>'
    '<circle cx="260" cy="155" r="28" fill="none" stroke="#7c6af7" stroke-width="3"/>'
    '<text x="260" y="160" text-anchor="middle" font-size="11" font-weight="700" fill="#7c6af7">nucleus</text>'
    '<ellipse cx="180" cy="210" rx="22" ry="12" fill="none" stroke="#10b981" stroke-width="3"/>'
    '<text x="180" y="240" text-anchor="middle" font-size="11" font-weight="700" fill="#10b981">chloroplast</text>'
    '<text x="390" y="100" font-size="11" font-weight="700" fill="#1e1f20">cell wall</text>'
    '<line x1="378" y1="105" x2="355" y2="120" stroke="#1e1f20" stroke-width="1.5"/>'
    "</svg>\n```",
)

# ── 24. Water cycle mermaid ─────────────────────────────────────────────────
add(
    "Draw me a mind map of the water cycle.",
    "The water cycle has four main stages that repeat forever.\n\n"
    "```mermaid\n"
    "graph TD\n"
    "    A[Sun heats oceans] --> B[Evaporation]\n"
    "    B --> C[Condensation - clouds form]\n"
    "    C --> D[Precipitation - rain]\n"
    "    D --> E[Collection - rivers and seas]\n"
    "    E --> B\n"
    "```",
)

# ── 25. Photosynthesis flow mermaid ─────────────────────────────────────────
add(
    "Show photosynthesis as a flowchart.",
    "Plants combine sunlight, water and carbon dioxide to make glucose and oxygen.\n\n"
    "```mermaid\n"
    "graph TD\n"
    "    A[Sunlight + Water + Carbon dioxide] --> B[Chlorophyll captures light]\n"
    "    B --> C[Glucose - plant food]\n"
    "    B --> D[Oxygen - released to air]\n"
    "```",
)

# ── 26. Essay structure mermaid ─────────────────────────────────────────────
add(
    "Show me how to structure an essay with a flowchart.",
    "A strong essay flows: introduction with thesis, three body paragraphs, conclusion.\n\n"
    "```mermaid\n"
    "graph TD\n"
    "    A[Introduction + thesis] --> B[Body 1 - strongest point]\n"
    "    B --> C[Body 2 - second point]\n"
    "    C --> D[Body 3 - third point]\n"
    "    D --> E[Conclusion - restate thesis]\n"
    "```",
)

# ── 27. Angles revision mermaid ─────────────────────────────────────────────
add(
    "Give me a quick flowchart to classify any angle.",
    "Ask two questions: is it exactly 90°? Is it more or less than 90°?\n\n"
    "```mermaid\n"
    "graph TD\n"
    "    A[Measure the angle] --> B{Exactly 90 degrees?}\n"
    "    B -->|Yes| C[Right angle]\n"
    "    B -->|No| D{Less than 90?}\n"
    "    D -->|Yes| E[Acute angle]\n"
    "    D -->|No| F{Less than 180?}\n"
    "    F -->|Yes| G[Obtuse angle]\n"
    "    F -->|No| H[Reflex angle]\n"
    "```",
)

# ── 28. Equivalent fractions ────────────────────────────────────────────────
add(
    "Show that one half equals two quarters with bars.",
    "Cut each half into two and you get quarters: 1/2 = **2/4**.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">1/2 = 2/4 — EQUIVALENT FRACTIONS</text>'
    '<rect x="80" y="80" width="360" height="44" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<rect x="80" y="80" width="180" height="44" fill="#7c6af7" opacity="0.55"/>'
    '<line x1="260" y1="80" x2="260" y2="124" stroke="#1e1f20" stroke-width="2.5"/>'
    '<text x="260" y="155" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">1/2 shaded</text>'
    '<rect x="80" y="190" width="360" height="44" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<rect x="80" y="190" width="180" height="44" fill="#7c6af7" opacity="0.55"/>'
    '<line x1="170" y1="190" x2="170" y2="234" stroke="#1e1f20" stroke-width="2"/>'
    '<line x1="260" y1="190" x2="260" y2="234" stroke="#1e1f20" stroke-width="2"/>'
    '<line x1="350" y1="190" x2="350" y2="234" stroke="#1e1f20" stroke-width="2"/>'
    '<text x="260" y="265" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">2/4 shaded — same amount</text>'
    "</svg>\n```",
)

# ── 29. Isosceles triangle angles ───────────────────────────────────────────
add(
    "An isosceles triangle has a vertex angle of 40 degrees. Find the base angles and draw it.",
    "Base angles are equal: (180 − 40) ÷ 2 = **70°** each.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">ISOSCELES — BASE ANGLES EQUAL</text>'
    '<polygon points="260,80 160,230 360,230" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="228" y1="155" x2="240" y2="163" stroke="#f59e0b" stroke-width="2.5"/>'
    '<line x1="292" y1="155" x2="280" y2="163" stroke="#f59e0b" stroke-width="2.5"/>'
    '<line x1="185" y1="215" x2="197" y2="207" stroke="#7c6af7" stroke-width="2.5"/>'
    '<line x1="335" y1="215" x2="323" y2="207" stroke="#7c6af7" stroke-width="2.5"/>'
    '<text x="260" y="115" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">40°</text>'
    '<text x="190" y="225" text-anchor="middle" font-size="13" font-weight="700" fill="#7c6af7">70°</text>'
    '<text x="330" y="225" text-anchor="middle" font-size="13" font-weight="700" fill="#7c6af7">70°</text>'
    '<text x="260" y="270" text-anchor="middle" font-size="13" fill="#1e1f20">tick marks show the equal sides</text>'
    "</svg>\n```",
)

# ── 30. Area of triangle ───────────────────────────────────────────────────
add(
    "Draw a triangle with base 6 cm and height 4 cm. What is its area?",
    "Area = ½ × base × height = ½ × 6 × 4 = **12 cm²**. The dashed line is the height.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">AREA OF A TRIANGLE = HALF BH</text>'
    '<polygon points="140,230 400,230 400,90" fill="#7c6af7" opacity="0.12" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="400" y1="230" x2="400" y2="90" stroke="#7c6af7" stroke-width="3" stroke-dasharray="8 5"/>'
    '<rect x="380" y="210" width="20" height="20" fill="none" stroke="#f59e0b" stroke-width="2.5"/>'
    '<text x="270" y="250" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">base = 6 cm</text>'
    '<text x="425" y="165" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">4 cm</text>'
    '<text x="260" y="285" text-anchor="middle" font-size="13" fill="#1e1f20">Area = half × 6 × 4 = 12 cm²</text>'
    "</svg>\n```",
)

# ── 31. Trapezium area ──────────────────────────────────────────────────────
add(
    "Draw a trapezium with parallel sides 4 cm and 8 cm and height 3 cm. Find its area.",
    "Area = (a + b) ÷ 2 × h = (4 + 8) ÷ 2 × 3 = **18 cm²**.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">AREA OF A TRAPEZIUM</text>'
    '<polygon points="190,110 330,110 380,220 140,220" fill="#7c6af7" opacity="0.12" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="260" y1="110" x2="260" y2="220" stroke="#7c6af7" stroke-width="2.5" stroke-dasharray="8 5"/>'
    '<text x="260" y="100" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">a = 4 cm</text>'
    '<text x="260" y="245" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">b = 8 cm</text>'
    '<text x="285" y="170" font-size="13" font-weight="700" fill="#7c6af7">h = 3</text>'
    '<text x="260" y="280" text-anchor="middle" font-size="13" fill="#1e1f20">(4 + 8) ÷ 2 × 3 = 18 cm²</text>'
    "</svg>\n```",
)

# ── 32. Circumference ───────────────────────────────────────────────────────
add(
    "A circle has diameter 10 cm. Draw it and find the circumference.",
    "C = π × d ≈ 3.14 × 10 = **31.4 cm**.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">CIRCUMFERENCE = PI × DIAMETER</text>'
    '<circle cx="250" cy="170" r="80" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="170" y1="170" x2="330" y2="170" stroke="#7c6af7" stroke-width="3"/>'
    '<text x="250" y="160" text-anchor="middle" font-size="13" font-weight="700" fill="#7c6af7">d = 10 cm</text>'
    '<text x="250" y="280" text-anchor="middle" font-size="13" fill="#1e1f20">C ≈ 3.14 × 10 = 31.4 cm</text>'
    "</svg>\n```",
)

# ── 33. Translation on a grid ───────────────────────────────────────────────
add(
    "Show the point A at (1, 1) translated 3 units right to B. Draw it.",
    "Add 3 to the x-coordinate: A(1, 1) → B(**4**, 1). The arrow shows the slide.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">TRANSLATION — SLIDE 3 RIGHT</text>'
    '<line x1="100" y1="240" x2="430" y2="240" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="100" y1="240" x2="100" y2="70" stroke="#1e1f20" stroke-width="2.5"/>'
    '<circle cx="148" cy="192" r="8" fill="#7c6af7"/>'
    '<text x="148" y="180" text-anchor="middle" font-size="12" font-weight="700" fill="#1e1f20">A(1,1)</text>'
    '<circle cx="292" cy="192" r="8" fill="#f59e0b"/>'
    '<text x="292" y="180" text-anchor="middle" font-size="12" font-weight="700" fill="#1e1f20">B(4,1)</text>'
    '<line x1="160" y1="192" x2="280" y2="192" stroke="#1e1f20" stroke-width="2.5"/>'
    '<polygon points="280,184 296,192 280,200" fill="#1e1f20"/>'
    '<text x="220" y="215" text-anchor="middle" font-size="12" fill="#1e1f20">3 right</text>'
    "</svg>\n```",
)

# ── 34. Line of symmetry ────────────────────────────────────────────────────
add(
    "Draw a shape with one line of symmetry.",
    "This isosceles triangle mirrors perfectly across the dashed line.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">ONE LINE OF SYMMETRY</text>'
    '<polygon points="260,70 150,230 370,230" fill="#7c6af7" opacity="0.12" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="260" y1="60" x2="260" y2="240" stroke="#f59e0b" stroke-width="2.5" stroke-dasharray="10 6"/>'
    '<text x="260" y="270" text-anchor="middle" font-size="13" fill="#1e1f20">fold here — both halves match</text>'
    "</svg>\n```",
)

# ── 35. Net of a cube ───────────────────────────────────────────────────────
add(
    "Draw the net of a cube.",
    "Six squares joined in a cross fold up into a cube.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">NET OF A CUBE — 6 SQUARES</text>'
    '<rect x="220" y="50" width="60" height="60" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<rect x="160" y="110" width="60" height="60" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<rect x="220" y="110" width="60" height="60" fill="#7c6af7" opacity="0.15" stroke="#1e1f20" stroke-width="2.5"/>'
    '<rect x="280" y="110" width="60" height="60" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<rect x="220" y="170" width="60" height="60" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<rect x="220" y="230" width="60" height="60" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    "</svg>\n```",
)

# ── 36. Pie chart ───────────────────────────────────────────────────────────
add(
    "Draw a pie chart: half the class walks, a quarter buses, a quarter is driven.",
    "Walk = 1/2, bus = 1/4, driven = 1/4. The slices add to one whole.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">HOW WE GET TO SCHOOL</text>'
    '<path d="M 210 180 L 210 90 A 90 90 0 0 1 300 180 Z" fill="#7c6af7" opacity="0.7" stroke="#ffffff" stroke-width="2"/>'
    '<path d="M 210 180 L 300 180 A 90 90 0 0 1 210 270 Z" fill="#f59e0b" opacity="0.7" stroke="#ffffff" stroke-width="2"/>'
    '<path d="M 210 180 L 210 270 A 90 90 0 0 1 210 90 Z" fill="#10b981" opacity="0.7" stroke="#ffffff" stroke-width="2"/>'
    '<text x="330" y="120" font-size="12" font-weight="700" fill="#1e1f20">walk 1/2</text>'
    '<text x="330" y="200" font-size="12" font-weight="700" fill="#1e1f20">bus 1/4</text>'
    '<text x="120" y="200" font-size="12" font-weight="700" fill="#1e1f20">driven 1/4</text>'
    "</svg>\n```",
)

# ── 37. Bar chart ───────────────────────────────────────────────────────────
add(
    "Draw a bar chart of favourite colours: red 5, blue 8, green 3.",
    "Blue wins with 8 votes. Bars make comparisons instant.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">FAVOURITE COLOURS</text>'
    '<line x1="100" y1="240" x2="440" y2="240" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="100" y1="240" x2="100" y2="60" stroke="#1e1f20" stroke-width="2.5"/>'
    '<rect x="140" y="140" width="60" height="100" fill="#ec4899" opacity="0.75"/>'
    '<text x="170" y="260" text-anchor="middle" font-size="12" fill="#1e1f20">red 5</text>'
    '<rect x="230" y="80" width="60" height="160" fill="#7c6af7" opacity="0.75"/>'
    '<text x="260" y="260" text-anchor="middle" font-size="12" fill="#1e1f20">blue 8</text>'
    '<rect x="320" y="180" width="60" height="60" fill="#10b981" opacity="0.75"/>'
    '<text x="350" y="260" text-anchor="middle" font-size="12" fill="#1e1f20">green 3</text>'
    "</svg>\n```",
)

# ── 38. Venn diagram ────────────────────────────────────────────────────────
add(
    "Draw a Venn diagram for multiples of 2 and multiples of 3 up to 10.",
    "Overlap = multiples of both (6). Left = only multiples of 2. Right = only multiples of 3.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">MULTIPLES OF 2 AND 3</text>'
    '<circle cx="200" cy="170" r="80" fill="#7c6af7" opacity="0.18" stroke="#7c6af7" stroke-width="2.5"/>'
    '<circle cx="320" cy="170" r="80" fill="#f59e0b" opacity="0.18" stroke="#f59e0b" stroke-width="2.5"/>'
    '<text x="200" y="70" text-anchor="middle" font-size="12" font-weight="700" fill="#1e1f20">×2</text>'
    '<text x="320" y="70" text-anchor="middle" font-size="12" font-weight="700" fill="#1e1f20">×3</text>'
    '<text x="160" y="175" text-anchor="middle" font-size="12" fill="#1e1f20">2 4 8 10</text>'
    '<text x="260" y="175" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">6</text>'
    '<text x="360" y="175" text-anchor="middle" font-size="12" fill="#1e1f20">3 9</text>'
    "</svg>\n```",
)

# ── 39. Probability tree ────────────────────────────────────────────────────
add(
    "Draw a probability tree for flipping a coin twice.",
    "Each flip: heads 1/2, tails 1/2. Multiply along branches: P(HH) = 1/2 × 1/2 = 1/4.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">COIN FLIPPED TWICE</text>'
    '<circle cx="70" cy="170" r="7" fill="#1e1f20"/>'
    '<line x1="70" y1="170" x2="200" y2="100" stroke="#7c6af7" stroke-width="2.5"/>'
    '<line x1="70" y1="170" x2="200" y2="240" stroke="#f59e0b" stroke-width="2.5"/>'
    '<text x="130" y="125" font-size="12" fill="#1e1f20">H 1/2</text>'
    '<text x="130" y="225" font-size="12" fill="#1e1f20">T 1/2</text>'
    '<circle cx="200" cy="100" r="7" fill="#1e1f20"/>'
    '<circle cx="200" cy="240" r="7" fill="#1e1f20"/>'
    '<line x1="200" y1="100" x2="330" y2="70" stroke="#7c6af7" stroke-width="2"/>'
    '<line x1="200" y1="100" x2="330" y2="130" stroke="#7c6af7" stroke-width="2"/>'
    '<line x1="200" y1="240" x2="330" y2="210" stroke="#f59e0b" stroke-width="2"/>'
    '<line x1="200" y1="240" x2="330" y2="270" stroke="#f59e0b" stroke-width="2"/>'
    '<text x="345" y="73" font-size="12" font-weight="700" fill="#1e1f20">HH 1/4</text>'
    '<text x="345" y="133" font-size="12" fill="#1e1f20">HT 1/4</text>'
    '<text x="345" y="213" font-size="12" fill="#1e1f20">TH 1/4</text>'
    '<text x="345" y="273" font-size="12" fill="#1e1f20">TT 1/4</text>'
    "</svg>\n```",
)

# ── 40. Graph y = x ─────────────────────────────────────────────────────────
add(
    "Draw the graph of y equals x.",
    "y = x is a diagonal through the origin: every point has equal coordinates.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">GRAPH OF Y = X</text>'
    '<line x1="80" y1="260" x2="450" y2="260" stroke="#1e1f20" stroke-width="2"/>'
    '<line x1="140" y1="290" x2="140" y2="50" stroke="#1e1f20" stroke-width="2"/>'
    '<line x1="140" y1="260" x2="400" y2="60" stroke="#7c6af7" stroke-width="3"/>'
    '<polygon points="400,60 388,72 392,58" fill="#7c6af7"/>'
    '<circle cx="200" cy="220" r="6" fill="#f59e0b"/>'
    '<circle cx="260" cy="180" r="6" fill="#f59e0b"/>'
    '<circle cx="320" cy="140" r="6" fill="#f59e0b"/>'
    '<text x="330" y="120" font-size="12" font-weight="700" fill="#1e1f20">(2, 2)</text>'
    '<text x="420" y="90" font-size="13" font-weight="700" fill="#7c6af7">y = x</text>'
    "</svg>\n```",
)

# ── 41. Parabola ────────────────────────────────────────────────────────────
add(
    "Draw the parabola y equals x squared using plotted points.",
    "Square each x: (−2, 4), (−1, 1), (0, 0), (1, 1), (2, 4). Join with a smooth U curve.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">PARABOLA Y = X SQUARED</text>'
    '<line x1="60" y1="240" x2="460" y2="240" stroke="#1e1f20" stroke-width="2"/>'
    '<line x1="260" y1="290" x2="260" y2="50" stroke="#1e1f20" stroke-width="2"/>'
    '<polyline points="140,80 200,200 260,240 320,200 380,80" fill="none" stroke="#7c6af7" stroke-width="3"/>'
    '<circle cx="140" cy="80" r="6" fill="#f59e0b"/>'
    '<circle cx="200" cy="200" r="6" fill="#f59e0b"/>'
    '<circle cx="260" cy="240" r="6" fill="#f59e0b"/>'
    '<circle cx="320" cy="200" r="6" fill="#f59e0b"/>'
    '<circle cx="380" cy="80" r="6" fill="#f59e0b"/>'
    '<text x="390" y="70" font-size="12" font-weight="700" fill="#1e1f20">(2, 4)</text>'
    "</svg>\n```",
)

# ── 42. Line y = 2x + 1 ─────────────────────────────────────────────────────
add(
    "Draw y equals 2x plus 1 and label the gradient and intercept.",
    "Gradient 2 (up 2 for each 1 across). y-intercept 1 (crosses at (0, 1)).\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">Y = 2X + 1</text>'
    '<line x1="60" y1="250" x2="460" y2="250" stroke="#1e1f20" stroke-width="2"/>'
    '<line x1="150" y1="290" x2="150" y2="50" stroke="#1e1f20" stroke-width="2"/>'
    '<line x1="150" y1="210" x2="390" y2="50" stroke="#7c6af7" stroke-width="3"/>'
    '<circle cx="150" cy="210" r="7" fill="#f59e0b"/>'
    '<text x="165" y="205" font-size="12" font-weight="700" fill="#1e1f20">intercept (0, 1)</text>'
    '<text x="330" y="60" font-size="12" font-weight="700" fill="#7c6af7">gradient = 2</text>'
    "</svg>\n```",
)

# ── 43. Fraction decimal percent ────────────────────────────────────────────
add(
    "Show one half as a fraction, decimal and percentage in one diagram.",
    "Same amount, three names: 1/2 = 0.5 = **50%**.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">HALF IN THREE FORMS</text>'
    '<rect x="90" y="90" width="340" height="60" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<rect x="90" y="90" width="170" height="60" fill="#7c6af7" opacity="0.55"/>'
    '<line x1="260" y1="90" x2="260" y2="150" stroke="#1e1f20" stroke-width="2.5"/>'
    '<text x="130" y="180" font-size="13" font-weight="700" fill="#1e1f20">1/2</text>'
    '<text x="250" y="180" font-size="13" font-weight="700" fill="#1e1f20">0.5</text>'
    '<text x="360" y="180" font-size="13" font-weight="700" fill="#1e1f20">50%</text>'
    '<text x="260" y="220" text-anchor="middle" font-size="13" fill="#5f6368">shade half the bar — all three match</text>'
    "</svg>\n```",
)

# ── 44. Factor tree ─────────────────────────────────────────────────────────
add(
    "Draw a factor tree for 12.",
    "Split 12 into 2 × 6, then 6 into 2 × 3. Primes in circles: 12 = 2 × 2 × 3.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">FACTOR TREE OF 12</text>'
    '<text x="260" y="80" text-anchor="middle" font-size="16" font-weight="700" fill="#1e1f20">12</text>'
    '<line x1="250" y1="90" x2="180" y2="140" stroke="#1e1f20" stroke-width="2"/>'
    '<line x1="270" y1="90" x2="340" y2="140" stroke="#1e1f20" stroke-width="2"/>'
    '<circle cx="170" cy="155" r="18" fill="none" stroke="#7c6af7" stroke-width="3"/>'
    '<text x="170" y="161" text-anchor="middle" font-size="14" font-weight="700" fill="#1e1f20">2</text>'
    '<text x="350" y="161" text-anchor="middle" font-size="16" font-weight="700" fill="#1e1f20">6</text>'
    '<line x1="340" y1="170" x2="290" y2="220" stroke="#1e1f20" stroke-width="2"/>'
    '<line x1="360" y1="170" x2="410" y2="220" stroke="#1e1f20" stroke-width="2"/>'
    '<circle cx="280" cy="235" r="18" fill="none" stroke="#7c6af7" stroke-width="3"/>'
    '<text x="280" y="241" text-anchor="middle" font-size="14" font-weight="700" fill="#1e1f20">2</text>'
    '<circle cx="420" cy="235" r="18" fill="none" stroke="#7c6af7" stroke-width="3"/>'
    '<text x="420" y="241" text-anchor="middle" font-size="14" font-weight="700" fill="#1e1f20">3</text>'
    '<text x="260" y="280" text-anchor="middle" font-size="13" fill="#1e1f20">12 = 2 × 2 × 3</text>'
    "</svg>\n```",
)

# ── 45. Numerator denominator ───────────────────────────────────────────────
add(
    "Label the parts of a fraction using 3 quarters as the example.",
    "Top = numerator (how many parts). Bottom = denominator (how many equal parts total).\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">PARTS OF A FRACTION</text>'
    '<text x="260" y="120" text-anchor="middle" font-size="44" font-weight="700" fill="#1e1f20">3</text>'
    '<line x1="200" y1="140" x2="320" y2="140" stroke="#1e1f20" stroke-width="3"/>'
    '<text x="260" y="190" text-anchor="middle" font-size="44" font-weight="700" fill="#1e1f20">4</text>'
    '<line x1="330" y1="110" x2="420" y2="80" stroke="#7c6af7" stroke-width="2"/>'
    '<text x="425" y="78" font-size="13" font-weight="700" fill="#7c6af7">numerator</text>'
    '<line x1="330" y1="180" x2="420" y2="210" stroke="#f59e0b" stroke-width="2"/>'
    '<text x="425" y="215" font-size="13" font-weight="700" fill="#f59e0b">denominator</text>'
    "</svg>\n```",
)

# ── 46. Place value ─────────────────────────────────────────────────────────
add(
    "Draw a place value chart for 4529.",
    "4 thousands, 5 hundreds, 2 tens, 9 ones: 4000 + 500 + 20 + 9.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">PLACE VALUE — 4529</text>'
    '<rect x="70" y="90" width="95" height="80" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<rect x="165" y="90" width="95" height="80" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<rect x="260" y="90" width="95" height="80" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<rect x="355" y="90" width="95" height="80" fill="#7c6af7" opacity="0.12" stroke="#7c6af7" stroke-width="2.5"/>'
    '<text x="117" y="80" text-anchor="middle" font-size="12" fill="#1e1f20">Th</text>'
    '<text x="212" y="80" text-anchor="middle" font-size="12" fill="#1e1f20">H</text>'
    '<text x="307" y="80" text-anchor="middle" font-size="12" fill="#1e1f20">T</text>'
    '<text x="402" y="80" text-anchor="middle" font-size="12" fill="#1e1f20">O</text>'
    '<text x="117" y="140" text-anchor="middle" font-size="28" font-weight="700" fill="#1e1f20">4</text>'
    '<text x="212" y="140" text-anchor="middle" font-size="28" font-weight="700" fill="#1e1f20">5</text>'
    '<text x="307" y="140" text-anchor="middle" font-size="28" font-weight="700" fill="#1e1f20">2</text>'
    '<text x="402" y="140" text-anchor="middle" font-size="28" font-weight="700" fill="#1e1f20">9</text>'
    '<text x="260" y="210" text-anchor="middle" font-size="13" fill="#1e1f20">4000 + 500 + 20 + 9 = 4529</text>'
    "</svg>\n```",
)

# ── 47. Angle types chart ───────────────────────────────────────────────────
add(
    "Draw all four angle types side by side for revision.",
    "Acute (&lt;90°), right (=90°), obtuse (90–180°), reflex (&gt;180°).\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">FOUR ANGLE TYPES</text>'
    '<line x1="70" y1="200" x2="30" y2="200" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="70" y1="200" x2="100" y2="140" stroke="#7c6af7" stroke-width="3"/>'
    '<text x="65" y="240" text-anchor="middle" font-size="12" font-weight="700" fill="#1e1f20">acute</text>'
    '<line x1="190" y1="200" x2="190" y2="140" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="190" y1="200" x2="250" y2="200" stroke="#1e1f20" stroke-width="2.5"/>'
    '<rect x="190" y="180" width="20" height="20" fill="none" stroke="#f59e0b" stroke-width="2.5"/>'
    '<text x="205" y="240" text-anchor="middle" font-size="12" font-weight="700" fill="#1e1f20">right</text>'
    '<line x1="340" y1="200" x2="280" y2="200" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="340" y1="200" x2="370" y2="140" stroke="#f59e0b" stroke-width="3"/>'
    '<text x="340" y="240" text-anchor="middle" font-size="12" font-weight="700" fill="#1e1f20">obtuse</text>'
    '<circle cx="455" cy="185" r="28" fill="none" stroke="#10b981" stroke-width="3"/>'
    '<circle cx="455" cy="185" r="5" fill="#1e1f20"/>'
    '<text x="455" y="240" text-anchor="middle" font-size="12" font-weight="700" fill="#1e1f20">reflex</text>'
    "</svg>\n```",
)

# ── 48. Electric circuit ────────────────────────────────────────────────────
add(
    "Draw a simple circuit with a battery, switch and bulb.",
    "Current flows around the loop when the switch is closed and the bulb lights.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">SIMPLE CIRCUIT</text>'
    '<rect x="120" y="100" width="280" height="120" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="200" y1="100" x2="200" y2="85" stroke="#1e1f20" stroke-width="3"/>'
    '<line x1="240" y1="100" x2="240" y2="85" stroke="#1e1f20" stroke-width="3"/>'
    '<line x1="185" y1="85" x2="255" y2="85" stroke="#1e1f20" stroke-width="2.5"/>'
    '<text x="220" y="70" text-anchor="middle" font-size="12" font-weight="700" fill="#1e1f20">battery</text>'
    '<circle cx="260" cy="220" r="22" fill="none" stroke="#f59e0b" stroke-width="3"/>'
    '<line x1="248" y1="208" x2="272" y2="232" stroke="#f59e0b" stroke-width="2.5"/>'
    '<line x1="272" y1="208" x2="248" y2="232" stroke="#f59e0b" stroke-width="2.5"/>'
    '<text x="260" y="265" text-anchor="middle" font-size="12" font-weight="700" fill="#1e1f20">bulb</text>'
    '<text x="120" y="130" font-size="12" font-weight="700" fill="#7c6af7">switch</text>'
    "</svg>\n```",
)

# ── 49. Day and night ───────────────────────────────────────────────────────
add(
    "Draw why we get day and night.",
    "Earth spins once every 24 hours. The half facing the Sun has day; the other half has night.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">DAY AND NIGHT — EARTH SPINS</text>'
    '<circle cx="110" cy="170" r="40" fill="#f59e0b"/>'
    '<text x="110" y="175" text-anchor="middle" font-size="12" font-weight="700" fill="#ffffff">SUN</text>'
    '<line x1="160" y1="150" x2="300" y2="150" stroke="#f59e0b" stroke-width="2"/>'
    '<line x1="160" y1="170" x2="300" y2="170" stroke="#f59e0b" stroke-width="2"/>'
    '<line x1="160" y1="190" x2="300" y2="190" stroke="#f59e0b" stroke-width="2"/>'
    '<circle cx="370" cy="170" r="55" fill="#1e1f20" opacity="0.85"/>'
    '<path d="M 370 115 A 55 55 0 0 0 370 225 Z" fill="#7c6af7" opacity="0.8"/>'
    '<text x="370" y="260" text-anchor="middle" font-size="12" font-weight="700" fill="#1e1f20">Earth spins this way</text>'
    '<text x="315" y="140" font-size="11" fill="#ffffff">day</text>'
    '<text x="405" y="175" font-size="11" fill="#ffffff">night</text>'
    "</svg>\n```",
)

# ── 50. States of matter mermaid ────────────────────────────────────────────
add(
    "Show the changes between solid, liquid and gas as a diagram.",
    "Heat melts solids and evaporates liquids; cooling freezes and condenses.\n\n"
    "```mermaid\n"
    "graph LR\n"
    "    A[Solid - ice] -->|melt - heat| B[Liquid - water]\n"
    "    B -->|evaporate - heat| C[Gas - steam]\n"
    "    C -->|condense - cool| B\n"
    "    B -->|freeze - cool| A\n"
    "```",
)

# ── 51. Rock cycle mermaid ──────────────────────────────────────────────────
add(
    "Draw the rock cycle.",
    "Rocks transform between igneous, sedimentary and metamorphic over millions of years.\n\n"
    "```mermaid\n"
    "graph TD\n"
    "    A[Magma cools] --> B[Igneous rock]\n"
    "    B --> C[Weathering + erosion]\n"
    "    C --> D[Sedimentary rock]\n"
    "    D --> E[Heat + pressure]\n"
    "    E --> F[Metamorphic rock]\n"
    "    F --> G[Melting]\n"
    "    G --> A\n"
    "```",
)

# ── 52. Food chain mermaid ──────────────────────────────────────────────────
add(
    "Draw a simple food chain.",
    "Energy flows from producers to consumers: grass to rabbit to fox.\n\n"
    "```mermaid\n"
    "graph LR\n"
    "    A[Grass - producer] --> B[Rabbit - consumer]\n"
    "    B --> C[Fox - predator]\n"
    "    C --> D[Decomposers recycle]\n"
    "```",
)

# ── 53. Australia timeline ──────────────────────────────────────────────────
add(
    "Draw a timeline of early Australia: 1788, 1851 gold rush, 1901 Federation.",
    "First Fleet 1788, gold rush 1851 brought migrants, Federation 1901 united the colonies.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">EARLY AUSTRALIA TIMELINE</text>'
    '<line x1="60" y1="170" x2="460" y2="170" stroke="#1e1f20" stroke-width="3"/>'
    '<circle cx="110" cy="170" r="8" fill="#7c6af7"/>'
    '<text x="110" y="145" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">1788</text>'
    '<text x="110" y="205" text-anchor="middle" font-size="11" fill="#1e1f20">First Fleet</text>'
    '<circle cx="260" cy="170" r="8" fill="#f59e0b"/>'
    '<text x="260" y="145" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">1851</text>'
    '<text x="260" y="205" text-anchor="middle" font-size="11" fill="#1e1f20">Gold rush</text>'
    '<circle cx="410" cy="170" r="8" fill="#10b981"/>'
    '<text x="410" y="145" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">1901</text>'
    '<text x="410" y="205" text-anchor="middle" font-size="11" fill="#1e1f20">Federation</text>'
    "</svg>\n```",
)

# ── 54. Flower parts ────────────────────────────────────────────────────────
add(
    "Draw a simple flower and label petal, stem and leaf.",
    "Petals attract pollinators, the stem holds the flower up, leaves make food.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">PARTS OF A FLOWER</text>'
    '<line x1="260" y1="150" x2="260" y2="270" stroke="#10b981" stroke-width="4"/>'
    '<ellipse cx="220" cy="230" rx="30" ry="12" fill="#10b981" opacity="0.5"/>'
    '<text x="170" y="255" font-size="12" font-weight="700" fill="#10b981">leaf</text>'
    '<circle cx="260" cy="100" r="16" fill="#f59e0b"/>'
    '<ellipse cx="260" cy="70" rx="14" ry="24" fill="#ec4899" opacity="0.6"/>'
    '<ellipse cx="260" cy="130" rx="14" ry="24" fill="#ec4899" opacity="0.6"/>'
    '<ellipse cx="230" cy="100" rx="24" ry="14" fill="#ec4899" opacity="0.6"/>'
    '<ellipse cx="290" cy="100" rx="24" ry="14" fill="#ec4899" opacity="0.6"/>'
    '<text x="330" y="80" font-size="12" font-weight="700" fill="#1e1f20">petal</text>'
    '<line x1="322" y1="82" x2="285" y2="90" stroke="#1e1f20" stroke-width="1.5"/>'
    '<text x="300" y="220" font-size="12" font-weight="700" fill="#1e1f20">stem</text>'
    "</svg>\n```",
)

# ── 55. Butterfly life cycle mermaid ────────────────────────────────────────
add(
    "Draw the life cycle of a butterfly.",
    "Four stages in a loop: egg, caterpillar, chrysalis, adult.\n\n"
    "```mermaid\n"
    "graph TD\n"
    "    A[Egg on leaf] --> B[Caterpillar hatches and eats]\n"
    "    B --> C[Chrysalis - pupa stage]\n"
    "    C --> D[Adult butterfly emerges]\n"
    "    D --> A\n"
    "```",
)

# ── 56. Science experiment steps mermaid ────────────────────────────────────
add(
    "Show the steps of a science experiment as a flowchart.",
    "Every fair test follows: question, hypothesis, method, results, conclusion.\n\n"
    "```mermaid\n"
    "graph TD\n"
    "    A[Ask a question] --> B[Make a hypothesis]\n"
    "    B --> C[Plan a fair method]\n"
    "    C --> D[Record results]\n"
    "    D --> E[Draw a conclusion]\n"
    "```",
)

# ── 57. Long division steps mermaid ─────────────────────────────────────────
add(
    "Show the steps of long division as a flowchart.",
    "Repeat four steps until nothing is left: divide, multiply, subtract, bring down.\n\n"
    "```mermaid\n"
    "graph TD\n"
    "    A[Divide the first digits] --> B[Multiply back]\n"
    "    B --> C[Subtract]\n"
    "    C --> D[Bring down next digit]\n"
    "    D --> E{Digits left?}\n"
    "    E -->|Yes| A\n"
    "    E -->|No| F[Remainder - done]\n"
    "```",
)

# ── 58. Food web mermaid ────────────────────────────────────────────────────
add(
    "Draw a simple food web with two chains.",
    "Grass feeds rabbits and grasshoppers; foxes and birds hunt them.\n\n"
    "```mermaid\n"
    "graph TD\n"
    "    A[Grass] --> B[Rabbit]\n"
    "    A --> C[Grasshopper]\n"
    "    B --> D[Fox]\n"
    "    C --> E[Bird]\n"
    "    C --> D\n"
    "```",
)

# ── 59. Ordering online sequence mermaid ────────────────────────────────────
add(
    "Show ordering a book online as a sequence diagram.",
    "Messages pass between customer, website and warehouse in order.\n\n"
    "```mermaid\n"
    "sequenceDiagram\n"
    "    Customer->>Website: search for book\n"
    "    Website-->>Customer: show results\n"
    "    Customer->>Website: place order\n"
    "    Website->>Warehouse: send book\n"
    "    Warehouse-->>Customer: book arrives\n"
    "```",
)

# ── 60. Sports pie mermaid ──────────────────────────────────────────────────
add(
    "Draw a pie chart of favourite sports: soccer 10, cricket 6, swimming 4.",
    "Soccer is half the class. Mermaid pie takes labels and values.\n\n"
    "```mermaid\n"
    "pie title Favourite sports\n"
    "    \"Soccer\" : 10\n"
    "    \"Cricket\" : 6\n"
    "    \"Swimming\" : 4\n"
    "```",
)

# ── 61. Solar system mindmap mermaid ────────────────────────────────────────
add(
    "Draw a mindmap of the solar system.",
    "One centre with three branches: star, rocky planets, gas giants.\n\n"
    "```mermaid\n"
    "mindmap\n"
    "  root((Solar System))\n"
    "    Star\n"
    "      Sun\n"
    "    Rocky planets\n"
    "      Mercury\n"
    "      Venus\n"
    "      Earth\n"
    "      Mars\n"
    "    Gas giants\n"
    "      Jupiter\n"
    "      Saturn\n"
    "      Uranus\n"
    "      Neptune\n"
    "```",
)

# ── 62. How laws are made mermaid ───────────────────────────────────────────
add(
    "Show how a law is made in Australia as a flowchart.",
    "A bill must pass both houses of parliament, then the Governor-General signs it.\n\n"
    "```mermaid\n"
    "graph TD\n"
    "    A[Idea for a law] --> B[Bill in House of Reps]\n"
    "    B --> C{Passed?}\n"
    "    C -->|Yes| D[Bill in Senate]\n"
    "    C -->|No| Z[Bill fails]\n"
    "    D --> E{Passed?}\n"
    "    E -->|Yes| F[Signed into law]\n"
    "    E -->|No| Z\n"
    "```",
)

# ── 63. Mean median mode SVG ────────────────────────────────────────────────
add(
    "Find the mean, median and mode of 4, 7, 9, 9, 11. Draw the data.",
    "Mean = 40 ÷ 5 = **8**. Median (middle) = **9**. Mode (most common) = **9**.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">MEAN MEDIAN MODE — 4 7 9 9 11</text>'
    '<line x1="80" y1="230" x2="440" y2="230" stroke="#1e1f20" stroke-width="2.5"/>'
    '<rect x="100" y="170" width="50" height="60" fill="#7c6af7" opacity="0.6"/>'
    '<text x="125" y="250" text-anchor="middle" font-size="12" fill="#1e1f20">4</text>'
    '<rect x="165" y="125" width="50" height="105" fill="#7c6af7" opacity="0.6"/>'
    '<text x="190" y="250" text-anchor="middle" font-size="12" fill="#1e1f20">7</text>'
    '<rect x="230" y="95" width="50" height="135" fill="#f59e0b" opacity="0.7"/>'
    '<text x="255" y="250" text-anchor="middle" font-size="12" fill="#1e1f20">9</text>'
    '<rect x="295" y="95" width="50" height="135" fill="#f59e0b" opacity="0.7"/>'
    '<text x="320" y="250" text-anchor="middle" font-size="12" fill="#1e1f20">9</text>'
    '<rect x="360" y="65" width="50" height="165" fill="#7c6af7" opacity="0.6"/>'
    '<text x="385" y="250" text-anchor="middle" font-size="12" fill="#1e1f20">11</text>'
    '<text x="260" y="285" text-anchor="middle" font-size="13" fill="#1e1f20">mean 8 · median 9 · mode 9</text>'
    "</svg>\n```",
)

# ── 64. Map scale bar SVG ───────────────────────────────────────────────────
add(
    "Draw a map scale bar from 0 to 15 km.",
    "Each block is 5 km. Measure on the map, then read the real distance.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">MAP SCALE BAR — KILOMETRES</text>'
    '<rect x="80" y="140" width="120" height="30" fill="#1e1f20"/>'
    '<rect x="200" y="140" width="120" height="30" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<rect x="320" y="140" width="120" height="30" fill="#1e1f20"/>'
    '<text x="80" y="195" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">0</text>'
    '<text x="200" y="195" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">5</text>'
    '<text x="320" y="195" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">10</text>'
    '<text x="440" y="195" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">15 km</text>'
    "</svg>\n```",
)

# ── 65. Pyramid net SVG ─────────────────────────────────────────────────────
add(
    "Draw the net of a square-based pyramid.",
    "One square base with a triangle on each side — 5 faces total.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">NET OF A SQUARE PYRAMID</text>'
    '<rect x="220" y="140" width="80" height="80" fill="#7c6af7" opacity="0.15" stroke="#1e1f20" stroke-width="2.5"/>'
    '<polygon points="220,140 300,140 260,70" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<polygon points="220,220 300,220 260,290" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<polygon points="220,140 220,220 150,180" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<polygon points="300,140 300,220 370,180" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<text x="260" y="310" text-anchor="middle" font-size="12" fill="#5f6368">1 square + 4 triangles fold into a pyramid</text>'
    "</svg>\n```",
)

# ── 66. Reflection SVG ──────────────────────────────────────────────────────
add(
    "Show the letter F reflected across a mirror line.",
    "A reflection flips the shape — every point jumps the same distance across the line.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">REFLECTION — MIRROR IMAGE</text>'
    '<line x1="260" y1="60" x2="260" y2="260" stroke="#f59e0b" stroke-width="2.5" stroke-dasharray="10 6"/>'
    '<text x="260" y="50" text-anchor="middle" font-size="12" font-weight="700" fill="#f59e0b">mirror</text>'
    '<text x="200" y="180" text-anchor="middle" font-size="72" font-weight="700" fill="#7c6af7">F</text>'
    '<text x="320" y="180" text-anchor="middle" font-size="72" font-weight="700" fill="#7c6af7" transform="translate(640,0) scale(-1,1)">F</text>'
    "</svg>\n```",
)

# ── 67. Equivalent ratios mermaid ───────────────────────────────────────────
add(
    "Show how to check if 2:3 and 4:6 are equivalent ratios.",
    "Multiply both parts by the same number: 2 × 2 = 4 and 3 × 2 = 6, so they match.\n\n"
    "```mermaid\n"
    "graph LR\n"
    "    A[Ratio 2:3] -->|multiply both by 2| B[Ratio 4:6]\n"
    "    B --> C{Equal?}\n"
    "    C -->|Yes| D[Equivalent ratios]\n"
    "```",
)

# ── 68. Data collection cycle mermaid ───────────────────────────────────────
add(
    "Draw the data investigation cycle.",
    "NSW maths uses: pose a question, collect data, display it, interpret results.\n\n"
    "```mermaid\n"
    "graph TD\n"
    "    A[Pose a question] --> B[Collect data]\n"
    "    B --> C[Display in tables and graphs]\n"
    "    C --> D[Interpret results]\n"
    "    D --> A\n"
    "```",
)

# ── 69. Cube drawing SVG ────────────────────────────────────────────────────
add(
    "Draw a 3D-looking cube with side 4 cm and find its volume.",
    "Volume = side³ = 4 × 4 × 4 = **64 cm³**. The offset square gives depth.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">CUBE — VOLUME = SIDE CUBED</text>'
    '<rect x="170" y="110" width="130" height="130" fill="#7c6af7" opacity="0.1" stroke="#1e1f20" stroke-width="2.5"/>'
    '<rect x="210" y="70" width="130" height="130" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="170" y1="110" x2="210" y2="70" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="300" y1="110" x2="340" y2="70" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="170" y1="240" x2="210" y2="200" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="300" y1="240" x2="340" y2="200" stroke="#1e1f20" stroke-width="2.5"/>'
    '<text x="255" y="275" text-anchor="middle" font-size="13" fill="#1e1f20">V = 4 × 4 × 4 = 64 cm³</text>'
    "</svg>\n```",
)

# ── 70. Trapezium variant (harder numbers) ─────────────────────────────────
add(
    "Draw a trapezium with parallel sides 6 cm and 10 cm and height 4 cm. Find its area.",
    "Area = (6 + 10) ÷ 2 × 4 = 8 × 4 = **32 cm²**. The dashed line is the height.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">TRAPEZIUM — BASES 6 AND 10</text>'
    '<polygon points="220,110 340,110 360,190 160,190" fill="#7c6af7" opacity="0.12" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="260" y1="110" x2="260" y2="190" stroke="#7c6af7" stroke-width="2.5" stroke-dasharray="8 5"/>'
    '<text x="280" y="100" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">a = 6 cm</text>'
    '<text x="260" y="215" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">b = 10 cm</text>'
    '<text x="282" y="155" font-size="13" font-weight="700" fill="#7c6af7">h = 4</text>'
    '<text x="260" y="250" text-anchor="middle" font-size="13" fill="#1e1f20">(6 + 10) ÷ 2 × 4 = 32 cm²</text>'
    "</svg>\n```",
)

# ── 71. Parallelogram area ──────────────────────────────────────────────────
add(
    "Draw a parallelogram with base 7 cm and height 5 cm. Find its area.",
    "Area = base × height = 7 × 5 = **35 cm²**. The slanted sides lean but the height stays vertical.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">PARALLELOGRAM — BASE × HEIGHT</text>'
    '<polygon points="170,220 350,220 410,110 230,110" fill="#7c6af7" opacity="0.12" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="300" y1="220" x2="300" y2="110" stroke="#7c6af7" stroke-width="2.5" stroke-dasharray="8 5"/>'
    '<text x="260" y="245" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">base = 7 cm</text>'
    '<text x="322" y="170" font-size="13" font-weight="700" fill="#7c6af7">h = 5</text>'
    '<text x="260" y="280" text-anchor="middle" font-size="13" fill="#1e1f20">Area = 7 × 5 = 35 cm²</text>'
    "</svg>\n```",
)

# ── 72. Three-set Venn ──────────────────────────────────────────────────────
add(
    "Draw a three-circle Venn diagram for kids who play soccer, tennis and swimming.",
    "Each lens is labelled separately with leader space so no labels overlap: only-soccer 5, only-tennis 6, only-swimming 7, pairs 3/4/1, all three 2.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">SPORTS VENN — 3 SETS</text>'
    '<circle cx="210" cy="150" r="62" fill="#7c6af7" opacity="0.15" stroke="#7c6af7" stroke-width="2.5"/>'
    '<circle cx="310" cy="150" r="62" fill="#f59e0b" opacity="0.15" stroke="#f59e0b" stroke-width="2.5"/>'
    '<circle cx="260" cy="235" r="62" fill="#10b981" opacity="0.15" stroke="#10b981" stroke-width="2.5"/>'
    '<text x="210" y="60" text-anchor="middle" font-size="12" font-weight="700" fill="#1e1f20">soccer</text>'
    '<text x="310" y="60" text-anchor="middle" font-size="12" font-weight="700" fill="#1e1f20">tennis</text>'
    '<text x="260" y="305" text-anchor="middle" font-size="12" font-weight="700" fill="#1e1f20">swimming</text>'
    '<text x="170" y="145" text-anchor="middle" font-size="12" fill="#1e1f20">5</text>'
    '<text x="350" y="145" text-anchor="middle" font-size="12" fill="#1e1f20">6</text>'
    '<text x="260" y="280" text-anchor="middle" font-size="12" fill="#1e1f20">7</text>'
    '<text x="260" y="130" text-anchor="middle" font-size="12" font-weight="700" fill="#1e1f20">3</text>'
    '<text x="222" y="215" text-anchor="middle" font-size="12" font-weight="700" fill="#1e1f20">4</text>'
    '<text x="298" y="215" text-anchor="middle" font-size="12" font-weight="700" fill="#1e1f20">1</text>'
    '<text x="260" y="180" text-anchor="middle" font-size="12" font-weight="700" fill="#1e1f20">2</text>'
    "</svg>\n```",
)

# ── 73. Protractor ──────────────────────────────────────────────────────────
add(
    "Draw a protractor measuring a 60 degree angle.",
    "Line the base on 0°, read where the ray crosses the scale: **60°**.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">PROTRACTOR READS 60°</text>'
    '<path d="M 160 220 A 100 100 0 0 1 360 220 Z" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="160" y1="220" x2="360" y2="220" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="173.4" y1="170" x2="183.8" y2="176" stroke="#1e1f20" stroke-width="2"/>'
    '<line x1="210" y1="133.4" x2="217" y2="143.9" stroke="#1e1f20" stroke-width="2"/>'
    '<line x1="260" y1="120" x2="260" y2="132" stroke="#1e1f20" stroke-width="2"/>'
    '<line x1="310" y1="133.4" x2="303" y2="143.9" stroke="#1e1f20" stroke-width="2"/>'
    '<line x1="346.6" y1="170" x2="336.2" y2="176" stroke="#1e1f20" stroke-width="2"/>'
    '<line x1="260" y1="220" x2="320" y2="117" stroke="#7c6af7" stroke-width="3"/>'
    '<circle cx="260" cy="220" r="5" fill="#7c6af7"/>'
    '<text x="330" y="110" font-size="13" font-weight="700" fill="#7c6af7">60°</text>'
    "</svg>\n```",
)

# ── 74. Four-slice pie with leader lines ────────────────────────────────────
add(
    "Draw a pie chart of pets: dogs 40 percent, cats 30 percent, birds 20 percent, fish 10 percent.",
    "Each label sits outside its slice with a leader line so nothing overlaps.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">PETS PIE — LEADER LABELS</text>'
    '<path d="M 230 175 L 230 90 A 85 85 0 0 1 280 243.8 Z" fill="#7c6af7" opacity="0.7" stroke="#ffffff" stroke-width="2"/>'
    '<path d="M 230 175 L 280 243.8 A 85 85 0 0 1 149.2 201.3 Z" fill="#f59e0b" opacity="0.7" stroke="#ffffff" stroke-width="2"/>'
    '<path d="M 230 175 L 149.2 201.3 A 85 85 0 0 1 180 106.2 Z" fill="#10b981" opacity="0.7" stroke="#ffffff" stroke-width="2"/>'
    '<path d="M 230 175 L 180 106.2 A 85 85 0 0 1 230 90 Z" fill="#ec4899" opacity="0.7" stroke="#ffffff" stroke-width="2"/>'
    '<line x1="270" y1="220" x2="330" y2="245" stroke="#1e1f20" stroke-width="1.5"/>'
    '<text x="335" y="249" font-size="12" font-weight="700" fill="#1e1f20">dogs 40%</text>'
    '<line x1="195" y1="215" x2="130" y2="240" stroke="#1e1f20" stroke-width="1.5"/>'
    '<text x="40" y="244" font-size="12" font-weight="700" fill="#1e1f20">cats 30%</text>'
    '<line x1="165" y1="150" x2="115" y2="120" stroke="#1e1f20" stroke-width="1.5"/>'
    '<text x="40" y="118" font-size="12" font-weight="700" fill="#1e1f20">birds 20%</text>'
    '<line x1="205" y1="100" x2="260" y2="70" stroke="#1e1f20" stroke-width="1.5"/>'
    '<text x="265" y="68" font-size="12" font-weight="700" fill="#1e1f20">fish 10%</text>'
    "</svg>\n```",
)

# ── 75. Kite ────────────────────────────────────────────────────────────────
add(
    "Draw a kite shape and show its line of symmetry.",
    "A kite has two pairs of equal adjacent sides. The dashed line is the symmetry axis.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">KITE — ONE SYMMETRY LINE</text>'
    '<polygon points="260,60 355,150 260,260 165,150" fill="#7c6af7" opacity="0.12" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="260" y1="50" x2="260" y2="270" stroke="#f59e0b" stroke-width="2.5" stroke-dasharray="10 6"/>'
    '<line x1="290" y1="100" x2="300" y2="108" stroke="#7c6af7" stroke-width="2.5"/>'
    '<line x1="230" y1="100" x2="220" y2="108" stroke="#7c6af7" stroke-width="2.5"/>'
    '<line x1="295" y1="205" x2="285" y2="213" stroke="#10b981" stroke-width="2.5"/>'
    '<line x1="225" y1="205" x2="235" y2="213" stroke="#10b981" stroke-width="2.5"/>'
    "</svg>\n```",
)

# ── 76. Rhombus diagonals ───────────────────────────────────────────────────
add(
    "Draw a rhombus and show that its diagonals cross at right angles.",
    "The two diagonals bisect each other at 90° — marked with the small square.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">RHOMBUS DIAGONALS MEET AT 90°</text>'
    '<polygon points="260,70 365,165 260,260 155,165" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="260" y1="70" x2="260" y2="260" stroke="#7c6af7" stroke-width="2.5"/>'
    '<line x1="155" y1="165" x2="365" y2="165" stroke="#f59e0b" stroke-width="2.5"/>'
    '<rect x="260" y="165" width="16" height="16" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<text x="260" y="290" text-anchor="middle" font-size="13" fill="#1e1f20">diagonals cut each other in half at 90°</text>'
    "</svg>\n```",
)

# ── 77. Missing triangle angle ──────────────────────────────────────────────
add(
    "A triangle has angles 70 degrees and 60 degrees. Draw it and find the missing angle.",
    "Missing angle = 180 − 70 − 60 = **50°**. Label the unknown corner x first.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">FIND THE MISSING ANGLE</text>'
    '<polygon points="150,230 370,230 280,90" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<text x="150" y="210" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">A</text>'
    '<text x="370" y="210" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">B</text>'
    '<text x="280" y="75" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">C</text>'
    '<text x="190" y="215" font-size="13" font-weight="700" fill="#7c6af7">70°</text>'
    '<text x="320" y="215" font-size="13" font-weight="700" fill="#f59e0b">x = 50°</text>'
    '<text x="280" y="125" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">60°</text>'
    '<text x="260" y="270" text-anchor="middle" font-size="13" fill="#1e1f20">x = 180 − 70 − 60 = 50°</text>'
    "</svg>\n```",
)

# ── 78. Exterior angle ──────────────────────────────────────────────────────
add(
    "Draw a triangle with one side extended and mark the exterior angle.",
    "Interior + exterior = 180° on a straight line. Here exterior 120° means interior 60°.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">EXTERIOR ANGLE = 180° − INTERIOR</text>'
    '<polygon points="150,220 370,220 280,100" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="370" y1="220" x2="460" y2="220" stroke="#1e1f20" stroke-width="2.5"/>'
    '<path d="M 340 220 A 32 32 0 0 0 355 195" fill="none" stroke="#7c6af7" stroke-width="1.8" stroke-dasharray="5 4"/>'
    '<path d="M 410 220 A 45 45 0 0 1 390 185" fill="none" stroke="#f59e0b" stroke-width="1.8" stroke-dasharray="5 4"/>'
    '<text x="315" y="210" font-size="12" font-weight="700" fill="#7c6af7">60°</text>'
    '<text x="405" y="200" font-size="12" font-weight="700" fill="#f59e0b">120°</text>'
    '<text x="260" y="260" text-anchor="middle" font-size="13" fill="#1e1f20">60° + 120° = 180° on a straight line</text>'
    "</svg>\n```",
)

# ── 79. Fraction wall ───────────────────────────────────────────────────────
add(
    "Draw a fraction wall showing a whole, halves, quarters and eighths.",
    "Each row shows the same whole split smaller: 1 = 2/2 = 4/4 = 8/8.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">FRACTION WALL</text>'
    '<rect x="100" y="55" width="320" height="36" fill="#7c6af7" opacity="0.5" stroke="#1e1f20" stroke-width="2"/>'
    '<text x="60" y="80" text-anchor="middle" font-size="12" fill="#1e1f20">1</text>'
    '<rect x="100" y="100" width="320" height="36" fill="none" stroke="#1e1f20" stroke-width="2"/>'
    '<rect x="100" y="100" width="160" height="36" fill="#7c6af7" opacity="0.5"/>'
    '<line x1="260" y1="100" x2="260" y2="136" stroke="#1e1f20" stroke-width="2"/>'
    '<text x="60" y="125" text-anchor="middle" font-size="12" fill="#1e1f20">1/2</text>'
    '<rect x="100" y="145" width="320" height="36" fill="none" stroke="#1e1f20" stroke-width="2"/>'
    '<rect x="100" y="145" width="160" height="36" fill="#7c6af7" opacity="0.5"/>'
    '<line x1="180" y1="145" x2="180" y2="181" stroke="#1e1f20" stroke-width="1.5"/>'
    '<line x1="260" y1="145" x2="260" y2="181" stroke="#1e1f20" stroke-width="1.5"/>'
    '<line x1="340" y1="145" x2="340" y2="181" stroke="#1e1f20" stroke-width="1.5"/>'
    '<text x="60" y="170" text-anchor="middle" font-size="12" fill="#1e1f20">1/4</text>'
    '<rect x="100" y="190" width="320" height="36" fill="none" stroke="#1e1f20" stroke-width="2"/>'
    '<rect x="100" y="190" width="160" height="36" fill="#7c6af7" opacity="0.5"/>'
    '<line x1="140" y1="190" x2="140" y2="226" stroke="#1e1f20" stroke-width="1"/>'
    '<line x1="180" y1="190" x2="180" y2="226" stroke="#1e1f20" stroke-width="1"/>'
    '<line x1="220" y1="190" x2="220" y2="226" stroke="#1e1f20" stroke-width="1"/>'
    '<line x1="260" y1="190" x2="260" y2="226" stroke="#1e1f20" stroke-width="1"/>'
    '<line x1="300" y1="190" x2="300" y2="226" stroke="#1e1f20" stroke-width="1"/>'
    '<line x1="340" y1="190" x2="340" y2="226" stroke="#1e1f20" stroke-width="1"/>'
    '<line x1="380" y1="190" x2="380" y2="226" stroke="#1e1f20" stroke-width="1"/>'
    '<text x="60" y="215" text-anchor="middle" font-size="12" fill="#1e1f20">1/8</text>'
    "</svg>\n```",
)

# ── 80. Thermometer ─────────────────────────────────────────────────────────
add(
    "Draw a thermometer showing 25 degrees Celsius.",
    "Read the top of the red liquid against the scale: halfway to 50.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">THERMOMETER — 25°C</text>'
    '<rect x="230" y="60" width="40" height="180" rx="20" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<rect x="236" y="150" width="28" height="84" fill="#ec4899"/>'
    '<circle cx="250" cy="255" r="26" fill="#ec4899" stroke="#1e1f20" stroke-width="2.5"/>'
    '<line x1="270" y1="80" x2="290" y2="80" stroke="#1e1f20" stroke-width="2"/>'
    '<text x="300" y="84" font-size="12" fill="#1e1f20">50</text>'
    '<line x1="270" y1="150" x2="290" y2="150" stroke="#1e1f20" stroke-width="2"/>'
    '<text x="300" y="154" font-size="12" font-weight="700" fill="#1e1f20">25</text>'
    '<line x1="270" y1="220" x2="290" y2="220" stroke="#1e1f20" stroke-width="2"/>'
    '<text x="300" y="224" font-size="12" fill="#1e1f20">0 °C</text>'
    "</svg>\n```",
)

# ── 81. Compass ─────────────────────────────────────────────────────────────
add(
    "Draw a compass rose with the eight main directions.",
    "North points up. Go clockwise: N, NE, E, SE, S, SW, W, NW.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">COMPASS ROSE</text>'
    '<circle cx="260" cy="180" r="85" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<polygon points="260,95 250,125 270,125" fill="#ec4899"/>'
    '<text x="260" y="70" text-anchor="middle" font-size="14" font-weight="700" fill="#1e1f20">N</text>'
    '<text x="365" y="185" text-anchor="middle" font-size="14" font-weight="700" fill="#1e1f20">E</text>'
    '<text x="260" y="285" text-anchor="middle" font-size="14" font-weight="700" fill="#1e1f20">S</text>'
    '<text x="155" y="185" text-anchor="middle" font-size="14" font-weight="700" fill="#1e1f20">W</text>'
    '<text x="335" y="110" text-anchor="middle" font-size="11" fill="#5f6368">NE</text>'
    '<text x="335" y="255" text-anchor="middle" font-size="11" fill="#5f6368">SE</text>'
    '<text x="185" y="255" text-anchor="middle" font-size="11" fill="#5f6368">SW</text>'
    '<text x="185" y="110" text-anchor="middle" font-size="11" fill="#5f6368">NW</text>'
    "</svg>\n```",
)

# ── 82. Half past four ──────────────────────────────────────────────────────
add(
    "Draw a clock showing half past 4.",
    "Minute hand on 6 (30 minutes). Hour hand halfway between 4 and 5.\n\n"
    "```svg\n"
    '<svg width="520" height="320" viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg" style="background:#fafafa">'
    '<rect width="100%" height="100%" fill="#fafafa"/>'
    '<text x="260" y="30" text-anchor="middle" font-size="12" letter-spacing="0.15em" fill="#5f6368">HALF PAST 4 — 4:30</text>'
    '<circle cx="260" cy="180" r="85" fill="none" stroke="#1e1f20" stroke-width="2.5"/>'
    '<text x="260" y="115" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">12</text>'
    '<text x="325" y="185" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">3</text>'
    '<text x="260" y="255" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">6</text>'
    '<text x="195" y="185" text-anchor="middle" font-size="13" font-weight="700" fill="#1e1f20">9</text>'
    '<line x1="260" y1="180" x2="260" y2="235" stroke="#f59e0b" stroke-width="3"/>'
    '<line x1="260" y1="180" x2="299" y2="219" stroke="#7c6af7" stroke-width="4"/>'
    '<circle cx="260" cy="180" r="6" fill="#1e1f20"/>'
    '<text x="260" y="290" text-anchor="middle" font-size="13" fill="#1e1f20">hour hand creeps past the 4</text>'
    "</svg>\n```",
)

print(f"Built {len(E)} diagram examples (batch 4 appended)")


def _to_record(user: str, assistant: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": DIAGRAM_SYSTEM},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ]
    }


# ── Validate every SVG parses as XML before writing ─────────────────────────
import re as _re

bad = []
for i, (u, a) in enumerate(E):
    for m in _re.findall(r"```svg\n(.*?)```", a, _re.DOTALL):
        try:
            ET.fromstring(m.strip())
        except Exception as e:
            bad.append((i, u[:40], str(e)[:100]))
if bad:
    print("INVALID SVG FOUND:")
    for b in bad:
        print(" ", b)
    raise SystemExit("Fix invalid SVGs before writing dataset")

# ── Split and write ─────────────────────────────────────────────────────────
rng = random.Random(7)
idx = list(range(len(E)))
rng.shuffle(idx)
n_valid = max(2, len(E) // 10)
n_test = max(2, len(E) // 10)
valid_i = set(idx[:n_valid])
test_i = set(idx[n_valid:n_valid + n_test])

splits = {"train": [], "valid": [], "test": []}
for i, (u, a) in enumerate(E):
    rec = _to_record(u, a)
    if i in valid_i:
        splits["valid"].append(rec)
    elif i in test_i:
        splits["test"].append(rec)
    else:
        splits["train"].append(rec)

for name, rows in splits.items():
    path = OUT_DIR / f"{name}.jsonl"
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")

print(f"Wrote {len(splits['train'])} train + {len(splits['valid'])} valid "
      f"+ {len(splits['test'])} test examples to {OUT_DIR}")
