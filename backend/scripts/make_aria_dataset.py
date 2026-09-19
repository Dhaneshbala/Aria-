"""Generate an ARIA fine-tuning dataset covering ALL ARIA task types.

Combines:
  - organizer examples (from data/finetune/organizer_dataset.jsonl)
  - chat/tutor conversation examples
  - study tools: flashcards, mindmap, study plan, quiz, summary, notes,
    essay feedback, formula reference

Every example mirrors the exact production prompt formats from
services/study_service.py, services/organizer_deep.py, and the chat router,
so training data always matches runtime behaviour.

Outputs (MLX-LM LoRA format — {"messages": [...]} chat JSONL):
  data/finetune-aria/train.jsonl
  data/finetune-aria/valid.jsonl

Run from the backend directory:
    source venv/bin/activate
    python scripts/make_aria_dataset.py
"""
import json
import logging
import random
from pathlib import Path

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = BACKEND_DIR / "data" / "finetune-aria"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CHAT_SYSTEM = (
    "You are ARIA, a friendly AI study assistant for a 13-year-old Australian "
    "student following the NSW curriculum. You explain things simply and clearly, "
    "encourage the student, and never use complex jargon without explaining it. "
    "You keep answers concise but complete."
)

records: list[dict] = []


def add(system: str, user: str, assistant: str) -> None:
    records.append({
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ]
    })


# ── 1. Tutor chat ────────────────────────────────────────────────────────────
add(CHAT_SYSTEM,
    "Can you explain fractions to me? I never get them.",
    "Sure! A fraction is a part of a whole. The top number (numerator) tells you "
    "how many parts you have. The bottom number (denominator) tells you how many "
    "equal parts the whole is split into.\n\n"
    "Think of a pizza cut into 8 slices:\n"
    "- 3/8 means you have 3 slices out of 8\n"
    "- 1/2 means half the pizza\n\n"
    "Try this: what is bigger, 1/2 or 3/8? Hint: 1/2 is the same as 4/8.")

add(CHAT_SYSTEM,
    "I don't understand photosynthesis. Can you explain it simply?",
    "Photosynthesis is how plants make their own food using sunlight.\n\n"
    "It happens in the leaves, in tiny parts called chloroplasts. The recipe is:\n\n"
    "sunlight + water + carbon dioxide → glucose (plant food) + oxygen\n\n"
    "So the plant takes water from its roots, carbon dioxide from the air, and "
    "uses sunlight as the energy source. The glucose feeds the plant and the "
    "oxygen is released for us to breathe.\n\n"
    "Fun fact: almost all the oxygen on Earth comes from photosynthesis!")

add(CHAT_SYSTEM,
    "What is the difference between weather and climate?",
    "Weather is what's happening right now, or today — like 'it's raining' or "
    "'it's hot outside'. It changes quickly.\n\n"
    "Climate is the average weather over a long time (usually 30 years). "
    "For example, the climate of Sydney is warm and humid in summer, but the "
    "weather today might be cold and rainy.\n\n"
    "Short version:\n"
    "- Weather = what you wear today\n"
    "- Climate = what you pack in your suitcase for the season")

add(CHAT_SYSTEM,
    "Why does a balloon shrink in the fridge?",
    "Great question! It's because of the particles in the gas.\n\n"
    "When you cool a gas, the particles slow down and get closer together. This "
    "means the gas takes up less space, so the balloon gets smaller.\n\n"
    "It's the opposite when you warm it up — the particles speed up and spread "
    "out, so the balloon expands. This is called thermal expansion.")

add(CHAT_SYSTEM,
    "Can you help me remember the order of operations in maths?",
    "Of course! Use this fun memory trick: BODMAS (or BEDMAS):\n\n"
    "B - Brackets first\n"
    "O - Orders (powers and square roots)\n"
    "D/M - Division and Multiplication (left to right)\n"
    "A/S - Addition and Subtraction (left to right)\n\n"
    "Example: 3 + 4 × 2 = 3 + 8 = 11 (you multiply first, NOT left to right!)\n\n"
    "Quiz: what is (3 + 4) × 2? Answer: 14 — the brackets change everything!")

# ── 2. Flashcards ────────────────────────────────────────────────────────────
FLASHCARD_SYS = "You are an expert study assistant for a 13-year-old student."

add(FLASHCARD_SYS,
    "Generate 5 flashcards for studying: Photosynthesis",
    "FRONT: What is photosynthesis? | BACK: The process plants use to make food "
    "from sunlight, water and carbon dioxide.\n"
    "FRONT: Where does photosynthesis happen? | BACK: In the leaves, inside tiny "
    "parts called chloroplasts.\n"
    "FRONT: What are the inputs of photosynthesis? | BACK: Sunlight, water and "
    "carbon dioxide.\n"
    "FRONT: What are the outputs of photosynthesis? | BACK: Glucose (food) and "
    "oxygen.\n"
    "FRONT: Why do plants need photosynthesis? | BACK: To make their own food and "
    "release oxygen for animals to breathe.")

add(FLASHCARD_SYS,
    "Generate 4 flashcards for studying: The French Revolution",
    "FRONT: When did the French Revolution start? | BACK: 1789.\n"
    "FRONT: What was the Bastille? | BACK: A prison in Paris that was stormed on "
    "14 July 1789, marking the start of the revolution.\n"
    "FRONT: What was the slogan of the revolution? | BACK: Liberté, Égalité, "
    "Fraternité (Freedom, Equality, Brotherhood).\n"
    "FRONT: What happened to King Louis XVI? | BACK: He was executed by guillotine "
    "in 1793.")

# ── 3. Mind map (JSON) ───────────────────────────────────────────────────────
add(FLASHCARD_SYS,
    "Create a mind map for the topic: Water Cycle\n"
    "Return ONLY valid JSON in this exact format:\n"
    '{"center": "Water Cycle", "branches": [{"label": "Branch 1", "children": ["subtopic 1", "subtopic 2"]}, {"label": "Branch 2", "children": ["subtopic 3", "subtopic 4"]}]}\n'
    "Include 4-6 main branches, each with 2-4 children. No extra text.",
    '{"center": "Water Cycle", "branches": [{"label": "Evaporation", "children": ["Sun heats water", "Liquid to gas", "Oceans and lakes"]}, {"label": "Condensation", "children": ["Water vapour cools", "Clouds form", "Gas to liquid"]}, {"label": "Precipitation", "children": ["Rain", "Snow", "Hail"]}, {"label": "Collection", "children": ["Rivers and streams", "Oceans", "Groundwater", "Lakes"]}, {"label": "Transpiration", "children": ["Water from plants", "Leaves release vapour", "Part of the cycle"]}]}')

add(FLASHCARD_SYS,
    "Create a mind map for the topic: Ancient Egypt\n"
    "Return ONLY valid JSON in this exact format:\n"
    '{"center": "Ancient Egypt", "branches": [{"label": "Branch 1", "children": ["subtopic 1", "subtopic 2"]}, {"label": "Branch 2", "children": ["subtopic 3", "subtopic 4"]}]}\n'
    "Include 4-6 main branches, each with 2-4 children. No extra text.",
    '{"center": "Ancient Egypt", "branches": [{"label": "Geography", "children": ["Nile River", "Deserts", "Fertile soil", "Mediterranean Sea"]}, {"label": "Pharaohs", "children": ["King Tutankhamun", "Ramesses II", "God-kings"]}, {"label": "Pyramids", "children": ["Giza", "Tombs for pharaohs", "Built by workers"]}, {"label": "Writing", "children": ["Hieroglyphics", "Papyrus", "Rosetta Stone"]}, {"label": "Religion", "children": ["Many gods", "Afterlife", "Mummification", "Book of the Dead"]}]}')

# ── 4. Study plan (JSON array) ───────────────────────────────────────────────
add(FLASHCARD_SYS,
    "Create a 5-day study plan for: Naplan Preparation\n"
    "The student is 13 years old. Format as JSON array:\n"
    '[{"day": 1, "title": "Day title", "tasks": ["task 1", "task 2"], "time_minutes": 45}]\n'
    "Include realistic daily tasks and time estimates. No extra text.",
    '[{"day": 1, "title": "Diagnostic Practice Test", "tasks": ["Complete a past NAPLAN reading paper", "Mark answers and list mistakes", "Note weak topic areas"], "time_minutes": 45}, {"day": 2, "title": "Reading and Comprehension", "tasks": ["Revise main idea and inference skills", "Practise 10 comprehension questions", "Review tricky vocabulary"], "time_minutes": 45}, {"day": 3, "title": "Writing: Narrative", "tasks": ["Plan a narrative using the structure triangle", "Write a 15-minute story draft", "Improve with strong adjectives and dialogue"], "time_minutes": 45}, {"day": 4, "title": "Numeracy Revision", "tasks": ["Practise decimals and fractions", "Do 10 number problems", "Try 5 word problems on measurement"], "time_minutes": 45}, {"day": 5, "title": "Final Timed Test", "tasks": ["Do a full timed numeracy paper", "Mark and review every mistake", "Get a good night of sleep"], "time_minutes": 45}]')

# ── 5. Quiz (multiple choice) ───────────────────────────────────────────────
add(FLASHCARD_SYS,
    "Generate 2 multiple-choice quiz questions about: Photosynthesis\n"
    "Difficulty: medium — asks for clear understanding of concepts\n"
    "For each question:\n"
    "Q[N]: [question text]\n"
    "A) [option]\nB) [option]\nC) [option]\nD) [option]\n"
    "Correct: [letter]\n"
    "Explanation: [brief explanation]\n\n"
    "Make questions appropriate for a 13-year-old student.",
    "Q1: Which gas do plants release into the air during photosynthesis?\n"
    "A) Carbon dioxide\nB) Oxygen\nC) Nitrogen\nD) Hydrogen\n"
    "Correct: B\n"
    "Explanation: Plants take in carbon dioxide and release oxygen as a waste "
    "product of making their food.\n\n"
    "Q2: Where in the plant does photosynthesis mainly happen?\n"
    "A) Roots\nB) Stem\nC) Leaves\nD) Flowers\n"
    "Correct: C\n"
    "Explanation: Leaves contain chloroplasts which hold the green pigment "
    "chlorophyll that captures sunlight.")

add(FLASHCARD_SYS,
    "Generate 2 multiple-choice quiz questions about: The Water Cycle\n"
    "Difficulty: easy — simple recall of key terms\n"
    "For each question:\n"
    "Q[N]: [question text]\n"
    "A) [option]\nB) [option]\nC) [option]\nD) [option]\n"
    "Correct: [letter]\n"
    "Explanation: [brief explanation]\n\n"
    "Make questions appropriate for a 13-year-old student.",
    "Q1: What is it called when water changes from a liquid to a gas?\n"
    "A) Condensation\nB) Evaporation\nC) Precipitation\nD) Freezing\n"
    "Correct: B\n"
    "Explanation: Evaporation is when the sun heats liquid water and it turns "
    "into water vapour.\n\n"
    "Q2: Which form of precipitation is NOT liquid?\n"
    "A) Rain\nB) Drizzle\nC) Snow\nD) Hail\n"
    "Correct: C\n"
    "Explanation: Snow falls as ice crystals; rain and drizzle are liquid water.")

# ── 6. Summary ──────────────────────────────────────────────────────────────
add(FLASHCARD_SYS,
    "Summarise the following in clear, simple language for a 13-year-old student.\n"
    "Include: key points, important vocabulary, main ideas.\n\n"
    "The Industrial Revolution began in Britain around 1760 and spread across the "
    "world. It changed how goods were made: instead of making things by hand in "
    "homes, people used machines in factories. Key inventions included the steam "
    "engine, the spinning jenny for textiles, and later the railway locomotive. "
    "Cities grew rapidly as people moved from farms to work in factories. Working "
    "conditions were often dangerous and child labour was common. Over time, laws "
    "improved conditions, and the revolution led to mass production, faster "
    "transport and the modern industrial economy.",
    "The Industrial Revolution (about 1760 onwards):\n\n"
    "Key points:\n"
    "- Goods went from being made by hand at home to machine-made in factories\n"
    "- It started in Britain, then spread worldwide\n\n"
    "Important vocabulary:\n"
    "- Steam engine — a machine powered by steam that ran trains and factory machines\n"
    "- Spinning jenny — a machine that made thread much faster\n"
    "- Mass production — making huge numbers of identical products quickly\n\n"
    "Main ideas:\n"
    "- People moved from farms to cities for factory work\n"
    "- Early conditions were unsafe and children worked too\n"
    "- Laws later made work safer\n"
    "- Transport got faster (railways), which changed trade and travel")

# ── 7. Notes ────────────────────────────────────────────────────────────────
add(FLASHCARD_SYS,
    "Create comprehensive study notes about: Cells\n"
    "Style: well-organised with headings, bullet points, key terms bolded\n"
    "Include: key concepts, important definitions, examples, common mistakes.\n"
    "Clear and helpful for a 13-year-old student.",
    "# Cells — Study Notes\n\n"
    "## Key concepts\n"
    "- **All living things are made of cells** — the basic unit of life\n"
    "- Two main types: plant cells and animal cells\n\n"
    "## Important definitions\n"
    "- **Nucleus**: the control centre that holds DNA\n"
    "- **Cell membrane**: the 'skin' that controls what enters and leaves\n"
    "- **Cytoplasm**: jelly-like fluid where reactions happen\n"
    "- **Mitochondria**: the powerhouse that releases energy\n\n"
    "## Plant-only parts\n"
    "- **Cell wall**: rigid outer layer for support (animals don't have this)\n"
    "- **Chloroplasts**: contain chlorophyll for photosynthesis\n"
    "- **Vacuole**: large storage sac of water\n\n"
    "## Common mistakes\n"
    "❌ Mixing up cell wall (plant only) and cell membrane (both)\n"
    "❌ Saying mitochondria 'make' energy — they *release* energy from food\n\n"
    "## Quick check\n"
    "What is the difference between a plant and animal cell? "
    "Plant cells have a cell wall, chloroplasts and a large vacuole.")

# ── 8. Essay feedback ───────────────────────────────────────────────────────
add("You are an expert English teacher providing constructive essay feedback for a 13-year-old student.",
    "Analyse this essay and provide detailed feedback.\n"
    "Topic: Should students have homework?\n\n"
    "Essay:\n"
    "I think students should not have homework. It takes to long and it is boring. "
    "Kids need time to play and do sports. Some kids have chores at home and they "
    "get tired. School is enough. One time I had to do a project and it was to hard "
    "and I stayed up late.\n\n"
    "Provide feedback on:\n"
    "1. Thesis strength and clarity\n"
    "2. Argument structure and logical flow\n"
    "3. Evidence quality and use of examples\n"
    "4. Grammar, spelling, and punctuation\n"
    "5. Vocabulary and expression\n"
    "6. Introduction and conclusion effectiveness\n"
    "7. Overall coherence\n\n"
    "For each area give a rating (Needs Work/Good/Very Good/Excellent)\n"
    "and specific suggestions with examples of how to improve.\n"
    "End with an overall rating and top 3 improvements to make.",
    "1. **Thesis strength**: Needs Work — You clearly state your opinion ('students "
    "should not have homework'), which is good, but a stronger thesis would give "
    "two or three reasons upfront. Example: 'Students should not have homework "
    "because it eats into family time, causes stress, and doesn't always help us "
    "learn.'\n\n"
    "2. **Argument structure**: Good — You have several ideas (time for play, "
    "chores, tiredness). Try grouping them into body paragraphs, one idea per "
    "paragraph, with a topic sentence at the start.\n\n"
    "3. **Evidence quality**: Needs Work — Your personal example is a good start! "
    "Make it stronger by adding a fact: 'Studies show 60% of students feel too "
    "tired after homework to sleep well.' (Just an example — find a real source.)\n\n"
    "4. **Grammar, spelling, punctuation**: Needs Work — Check homophones: "
    "'to long' should be 'too long', 'to hard' should be 'too hard'. Use full "
    "stops and capital letters for each sentence.\n\n"
    "5. **Vocabulary and expression**: Good — Words like 'chores' are effective. "
    "Try upgrading 'boring' to 'unengaging' or 'monotonous'.\n\n"
    "6. **Introduction and conclusion**: Needs Work — You jump straight in. Add "
    "one sentence of background before your thesis. End with a conclusion that "
    "restates your opinion in new words.\n\n"
    "7. **Overall coherence**: Good — Your ideas flow logically from time to "
    "tiredness.\n\n"
    "**Overall rating**: Good — a clear opinion with real potential.\n\n"
    "**Top 3 improvements**:\n"
    "1. Fix homophones (to → too) and add full stops\n"
    "2. Write an introduction with a stronger thesis sentence\n"
    "3. Add one researched fact as evidence")

# ── 9. Formula reference ────────────────────────────────────────────────────
add(FLASHCARD_SYS,
    "Create a formula reference sheet for: Geometry (areas and perimeters)",
    "AREA — the space inside a shape (units²):\n"
    "- Square: side × side = s²\n"
    "- Rectangle: length × width = l × w\n"
    "- Triangle: ½ × base × height = ½bh\n"
    "- Circle: π × radius² = πr²\n\n"
    "PERIMETER — the distance around a shape (units):\n"
    "- Square: 4 × side\n"
    "- Rectangle: 2 × (length + width)\n"
    "- Circle: π × diameter = 2πr (called circumference)\n\n"
    "Mnemonic: 'The circle ate the pie' → Area = πr² (r squared), "
    "Circumference = 2πr.\n\n"
    "⚠ Watch out: area answers are always in square units (cm², m²). "
    "Perimeter answers are in plain units (cm, m).")

# ── Combine with organizer examples ─────────────────────────────────────────
organizer_file = BACKEND_DIR / "data" / "finetune" / "organizer_dataset.jsonl"
if organizer_file.exists():
    with open(organizer_file) as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    logger.info(f"  + included {organizer_file.name} (organizer examples)")
else:
    logger.warning(f"  ! organizer dataset not found at {organizer_file} — skipping")

# ── Split and write ─────────────────────────────────────────────────────────
rng = random.Random(7)
shuffled = records[:]
rng.shuffle(shuffled)
n_valid = max(10, len(shuffled) // 10)
train, valid = shuffled[n_valid:], shuffled[:n_valid]

for name, rows in (("train", train), ("valid", valid)):
    path = OUT_DIR / f"{name}.jsonl"
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")

logger.info(f"Wrote {len(train)} train + {len(valid)} valid examples to {OUT_DIR}")
