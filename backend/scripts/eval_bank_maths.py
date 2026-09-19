"""Day 55: first CORRECTNESS eval — fixed maths bank, known answers.

Unlike feature_accuracy_harness (schema/invariant checks), this grades
whether the tutor's answers are actually RIGHT. Twenty Year-7 questions
with deterministic answers; the model answers cold; a regex extracts the
final number and compares with tolerance.

Baseline-first: run it, record the number, every later improvement must
not move it down. See backend/docs/quality-bar.md (multiplier #1).

Usage:
    python3 backend/scripts/eval_bank_maths.py [--model gemma4:e4b-mlx]
Requires: Ollama running locally (reads :11434 only — never the :8000 app).
"""
import asyncio
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BANK = [  # (question, expected float)
    ("What is 7 + 8?", 15),
    ("What is 23 - 9?", 14),
    ("What is 6 times 7?", 42),
    ("What is 144 divided by 12?", 12),
    ("Solve for x: 3x + 5 = 20.", 5),
    ("Solve for x: 2x - 7 = 11.", 9),
    ("What is 15% of 200?", 30),
    ("What is the area of a rectangle 8 cm by 5 cm? Give just the number.", 40),
    ("What is 2 to the power 5?", 32),
    ("What is the square root of 81?", 9),
    ("Simplify: 4/8 as a decimal.", 0.5),
    ("What is 1/2 + 1/4 as a decimal?", 0.75),
    ("What is 9 squared?", 81),
    ("What is 100 - 37?", 63),
    ("What is 13 times 4?", 52),
    ("Solve for y: y/4 = 9.", 36),
    ("What is 1000 divided by 8?", 125),
    ("What is 3 cubed?", 27),
    ("A triangle has base 10 and height 6. What is its area? Give just the number.", 30),
    ("What is 17 + 28?", 45),
]

# Day 56: multi-step headroom. The warm-up bank scores 20/20 — a gate that
# always passes gates nothing. These need 2+ steps; all still grade
# deterministically by final number.
BANK_HARD = [
    ("What is 2 + 3 times 4? Order of operations applies.", 14),
    ("What is (2 + 3) times 4?", 20),
    ("What is 100 divided by 4 divided by 5?", 5),
    ("Solve for x: 5x - 3 = 2x + 12.", 5),
    ("A shop discounts $80 by 25%. What is the sale price? Give just the number.", 60),
    ("What is 3/4 of 96?", 72),
    ("A train travels 60 km in 1.5 hours. What is its speed in km/h? Give just the number.", 40),
    ("What is 7 squared minus 3 squared?", 40),
    ("Solve for x: x/3 + x/6 = 9.", 18),
    ("What is the next prime after 47?", 53),
]

MODEL = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--model=")), "gemma4:e4b-mlx")
BANK = BANK + BANK_HARD if "--hard" in sys.argv else BANK


def extract_number(text: str) -> float | None:
    nums = re.findall(r"-?\d+(?:\.\d+)?", (text or "").replace(",", ""))
    if not nums:
        return None
    try:
        return float(nums[-1])
    except ValueError:
        return False


async def grade_one(svc, q: str, expected: float) -> dict:
    t0 = time.perf_counter()
    try:
        ans = await svc.complete(
            MODEL,
            f"{q} Reply with just the final number, no working.",
            system="You are a maths tutor. Answer with just the final number.",
            max_tokens=64,
            timeout=120,
            think=False,
        )
    except Exception as e:
        return {"ok": False, "error": str(e)[:100], "seconds": round(time.perf_counter() - t0, 1)}
    got = extract_number(ans)
    ok = got is not False and got is not None and abs(got - expected) < 1e-6
    return {"ok": ok, "expected": expected, "got": got, "seconds": round(time.perf_counter() - t0, 1)}


async def main() -> int:
    from services.ollama_service import OllamaService
    svc = OllamaService()
    results = []
    for q, expected in BANK:
        r = await grade_one(svc, q, expected)
        results.append({"q": q, **r})
        mark = "✓" if r["ok"] else "✗"
        print(f"  {mark} {q} → {r.get('got')} (want {expected}) [{r.get('seconds', '?')}s]")
    passed = sum(1 for r in results if r["ok"])
    total_s = round(sum(r.get("seconds", 0) for r in results), 1)
    print(f"SCORE {passed}/{len(results)} in {total_s}s [{MODEL}]")
    out = Path(__file__).resolve().parent.parent / "storage" / "eval_maths_latest.json"
    try:
        out.write_text(json.dumps({"model": MODEL, "score": passed, "total": len(results),
                                   "seconds": total_s, "ts": time.time(), "results": results}, indent=1))
        print(f"report: {out}")
    except Exception as e:
        print(f"(report not written: {e})")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
