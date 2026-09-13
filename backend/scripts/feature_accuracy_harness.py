"""Live accuracy harness for ARIA's LLM-driven features.

Runs each structured-output feature against the real local Ollama models
and validates against ground truth / schema invariants. Reports per-feature
accuracy and writes a JSON report.

Usage:
    python backend/scripts/feature_accuracy_harness.py [--feature QUIZ]
"""
import asyncio
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.study_service import StudyService
from services.diagram_service import DiagramService
from services.study_intelligence_service import StudyIntelligence
from services.advanced_study_service import AdvancedStudyIntelligence
try:
    from services.premium_planner_service import parse_syllabus
except ImportError:
    parse_syllabus = None  # planner removed, harness skips
try:
    from services.cloud_llm import CloudLLM
except ImportError:
    CloudLLM = None

MODEL = os.environ.get("REASONING_MODEL", "gemma4:e4b-mlx")

# ── per-feature validators ─────────────────────────────────────────────────

def check_quiz(questions):
    """A quiz question must parse to: 4 options, a valid letter, an explanation."""
    issues = []
    if not questions:
        return {"ok": False, "detail": "no questions"}
    for i, q in enumerate(questions):
        if not q.get("question"):
            issues.append(f"Q{i+1}: missing question text")
        if len(q.get("options", [])) < 4:
            issues.append(f"Q{i+1}: only {len(q.get('options', []))} options")
        if q.get("correct") not in ("A", "B", "C", "D"):
            issues.append(f"Q{i+1}: invalid correct {q.get('correct')!r}")
        if not q.get("explanation"):
            issues.append(f"Q{i+1}: missing explanation")
    return {"ok": not issues, "detail": "; ".join(issues) or "ok",
            "n": len(questions)}


def check_flashcards(cards):
    issues = []
    if not cards:
        return {"ok": False, "detail": "no cards", "n": 0}
    for i, c in enumerate(cards):
        if not c.get("front") or not c.get("back"):
            issues.append(f"card{i+1}: missing front/back")
        if len(c.get("front", "")) < 3 or len(c.get("back", "")) < 3:
            issues.append(f"card{i+1}: too short")
    return {"ok": not issues, "detail": "; ".join(issues) or "ok", "n": len(cards)}


def check_diagram_mindmap(spec):
    """Diagram-service mindmap spec: visual_type mindmap; 3-8 nodes with labels."""
    issues = []
    if not isinstance(spec, dict):
        return {"ok": False, "detail": "not a dict"}
    if spec.get("visual_type") != "mindmap":
        issues.append(f"visual_type={spec.get('visual_type')!r}, want mindmap")
    nodes = spec.get("nodes") or []
    if not isinstance(nodes, list) or len(nodes) < 3:
        issues.append(f"need >=3 nodes, got {len(nodes)}")
    for i, n in enumerate(nodes):
        if not (n.get("label") if isinstance(n, dict) else None):
            issues.append(f"node{i}: missing label")
    return {"ok": not issues, "detail": "; ".join(issues) or "ok",
            "n": len(nodes)}


def check_study_plan(plan, days):
    issues = []
    if not isinstance(plan, list) or len(plan) != days:
        return {"ok": False, "detail": f"expected {days} days, got {len(plan)}"}
    for i, d in enumerate(plan):
        if d.get("day") != i + 1:
            issues.append(f"day{i+1}: wrong day number {d.get('day')!r}")
        if not d.get("title"):
            issues.append(f"day{i+1}: missing title")
        if not isinstance(d.get("tasks", []), list) or not d["tasks"]:
            issues.append(f"day{i+1}: no tasks")
        if not isinstance(d.get("time_minutes"), (int, float)) or d["time_minutes"] <= 0:
            issues.append(f"day{i+1}: bad time_minutes {d.get('time_minutes')!r}")
    return {"ok": not issues, "detail": "; ".join(issues) or "ok", "n": len(plan)}


def check_assessment_plan(plan, days):
    issues = []
    if not isinstance(plan, dict):
        return {"ok": False, "detail": "not a dict"}
    a = plan.get("assessment") or {}
    for key in ("name", "subject", "date", "format"):
        if not a.get(key):
            issues.append(f"assessment.{key} missing")
    if not isinstance(plan.get("plan"), list) or len(plan.get("plan", [])) != days:
        issues.append(f"plan days != {days}")
    if not plan.get("tips"):
        issues.append("missing tips")
    return {"ok": not issues, "detail": "; ".join(issues) or "ok"}


async def run_task(name, coro, validator):
    try:
        out = await coro
        return {"feature": name, **validator(out)}
    except Exception as e:
        return {"feature": name, "ok": False, "detail": f"error: {e!r}", "n": 0}


async def _gen_mindmap_spec():
    """Mind-map visual via the chat diagram generator (standalone removed)."""
    res = await DiagramService().generate("the water cycle", visual_type="mindmap")
    if isinstance(res, dict):
        return res.get("spec", res)
    return res


async def main():
    ss = StudyService()
    si = StudyIntelligence()
    asp = AdvancedStudyIntelligence()
    # Run sequentially: one model, many tasks — concurrent calls thrash the
    # Ollama queue and cause timeouts.
    results = []
    tasks = [
        ("QUIZ", ss.generate_quiz("the water cycle", "easy", 4, model=MODEL), check_quiz),
        ("FLASHCARDS", ss.generate_flashcards("World War 2", 6, model=MODEL), check_flashcards),
        ("MINDMAP", _gen_mindmap_spec(), check_diagram_mindmap),
    ]
    # Study plan / assessment moved to brain (chat) — verify via orchestrator intents
    try:
        from services.orchestrator import detect_intents
        brain_ok = "exam_sim" in detect_intents("exam simulation on algebra") and "study_intel" in detect_intents("what are my weak topics")
        results.append({"feature": "BRAIN_STUDY_INTENTS", "ok": brain_ok, "detail": "brain intents ok" if brain_ok else "missing"})
    except Exception as e:
        results.append({"feature": "BRAIN_STUDY_INTENTS", "ok": False, "detail": str(e)})
    for name, coro, validator in tasks:
        results.append(await run_task(name, coro, validator))
        print(f"  ...{name} done", flush=True)
    # difficulty classification (deterministic given empty profile → "medium")
    try:
        diff = await si.get_difficulty("unknown topic 12345")
        ok = diff == "medium"  # blank profile must default to medium
        tasks_result_difficulty = {"feature": "DIFFICULTY", "ok": ok, "detail": diff or ""}
    except Exception as e:
        tasks_result_difficulty = {"feature": "DIFFICULTY", "ok": False, "detail": f"error: {e}"}

    results.append(tasks_result_difficulty)

    print("\n=== FEATURE ACCURACY (live Ollama) ===")
    all_ok = True
    for r in results:
        tag = "PASS" if r.get("ok") else "FAIL"
        if not r.get("ok"):
            all_ok = False
        print(f"[{tag}] {r['feature']:18} {r.get('detail', '')[:140]}")
    print(f"\nOVERALL: {sum(1 for r in results if r.get('ok'))}/{len(results)} features OK")
    with open("/tmp/feature_accuracy.json", "w") as f:
        json.dump(results, f, indent=1)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))