"""Generate sample test data for the File Organizer.

Creates a realistic student Downloads-style folder with mixed file types
so you can try scanning, AI analysis, preview and organization without
touching real files.

Usage:
    python scripts/make_sample_data.py [dest] [--files N]

Example:
    python scripts/make_sample_data.py /tmp/sample_downloads
"""
import argparse
import logging
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

SAMPLES = {
    # (relative path, content)
    "algebra_homework_1.txt": "Solve for x: 2x + 5 = 13. Show all working.\nHomework due Friday 12 Sept.",
    "fractions_worksheet.txt": "Simplify: 1/2 + 3/4\nConvert 7/8 to a decimal.",
    "cell_biology_notes.txt": "Plant cells have chloroplasts and a cell wall.\nAnimal cells do not have these structures.",
    "forces_energy_notes.txt": "Newton's laws of motion. Kinetic energy = 1/2 mv^2.",
    "ancient_egypt_essay.txt": "Ancient Egypt: the Nile, pharaohs and pyramids. Essay outline for History.",
    "narrative_english.txt": "My narrative essay about the lost lighthouse. Draft 2 with feedback.",
    "python_program.py": "def fibonacci(n):\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a\nprint(fibonacci(10))",
    "geometry_proof.pdf.txt": "Proof that opposite angles of a parallelogram are equal. Geometry worksheet.",
    "screenshot_error.png": "FAKE PNG",
    "invoice_acme.png": "FAKE PNG",
    "homework_sheet_3.txt": "Week 3 homework: fractions and percentages.",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dest", nargs="?", default="/tmp/sample_downloads")
    parser.add_argument("--files", type=int, default=0, help="duplicate N extra generic files")
    args = parser.parse_args()

    dest = Path(args.dest).expanduser()
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    for name, content in SAMPLES.items():
        (dest / name).write_text(content)

    for i in range(args.files):
        (dest / f"download_{i:03d}.txt").write_text(
            f"Untitled document {i} with some text content about nothing in particular.")

    logger.info(f"Created {len(SAMPLES) + args.files} sample files in {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
