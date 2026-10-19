"""ARIA model benchmark — current lineup vs any custom list.
Fair settings: same M4 options as backend/services/ollama_service.py, temp 0.7, ctx 8192.
Measures: correctness (exec/JSON/exact), latency, tok/s (Ollama eval stats), RAM via `ollama ps`.
Usage: python bench_models.py [model ...]   (default: qwen3.5:9b)
"""

import base64
import io
import json
import subprocess
import sys
import time

import httpx

OLLAMA = "http://127.0.0.1:11434"
OPTS = {
    "num_gpu_layers": -1,
    "temperature": 0.7,
    "num_ctx": 8192,
    "num_thread": 8,
    "num_batch": 512,
    "repeat_penalty": 1.1,
}


def chat(model, system, user, images_b64=None, timeout=180):
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if images_b64:
        msgs[1]["images"] = images_b64
    t0 = time.time()
    r = httpx.post(
        f"{OLLAMA}/api/chat",
        json={
            "model": model,
            "messages": msgs,
            "stream": False,
            "options": OPTS,
            "keep_alive": "5m",
            **({"think": False} if "qwen3" in model else {}),
        },
        timeout=timeout,
    )
    wall = time.time() - t0
    r.raise_for_status()
    d = r.json()
    return (
        d["message"]["content"],
        d.get("eval_count", 0),
        (d.get("eval_duration", 0) / 1e9),
        wall,
    )


def ps_size(model_short):
    try:
        out = subprocess.run(
            ["ollama", "ps"], capture_output=True, text=True, timeout=10
        ).stdout
        for line in out.splitlines():
            if model_short.split(":")[0] in line:
                parts = line.split()
                # columns: NAME ID SIZE PROCESSOR UNTIL
                for i, p in enumerate(parts):
                    if p in ("GB", "MB") and i > 0:
                        return f"{parts[i - 1]} {p}"
                return line.strip()[:80]
        return "not resident"
    except Exception as e:
        return f"ps fail: {e}"


def unload(model):
    try:
        httpx.post(
            f"{OLLAMA}/api/generate", json={"model": model, "keep_alive": 0}, timeout=30
        )
    except Exception:
        pass
    time.sleep(2)


def make_worksheet_image():
    """Synthetic worksheet photo: white PNG with printed math problem."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    img = Image.new("RGB", (600, 200), "white")
    d = ImageDraw.Draw(img)
    d.text((40, 60), "Worksheet Q1: Solve 3x + 7 = 22.  x = ?", fill="black")
    d.text((40, 110), "Q2: What is 3/4 + 1/8 ?  Give simplest fraction.", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


TASKS = [
    (
        "math_easy",
        "You are a maths tutor. Be exact.",
        "Solve: 3x + 7 = 22. Reply with just x = ? and one line working.",
        ["x = 5", "x=5"],
    ),
    (
        "math_hard",
        "You are a maths tutor. Be exact.",
        "A password is a 2-digit number: tens digit is twice the ones digit, digits sum to 12. Reply with the number and one line working.",
        ["84"],
    ),
    (
        "coding",
        "You are a coding tutor. Reply with a python code block only.",
        "Write a Python function add(a, b) returning their sum.",
        ["def add"],
    ),
    (
        "quiz_json",
        "Return valid JSON only, no markdown fences.",
        'Return JSON only: {"questions": [{"q": "...", "options": ["A","B","C","D"], "answer": "A"}]} with exactly 3 photosynthesis Year-7 questions.',
        None,
    ),
    (
        "explain",
        "You are a Year 7 tutor.",
        "Explain photosynthesis in 2 sentences for Year 7.",
        ["sunlight", "glucose", "chlorophyll", "carbon dioxide"],
    ),
]

results = {}
TEXT_MODELS = sys.argv[1:] if len(sys.argv) > 1 else ["qwen3.5:9b"]
for model in TEXT_MODELS:
    print(f"\n===== {model} =====", flush=True)
    mr = {"tasks": {}}
    for tid, sys, usr, expect in TASKS:
        try:
            content, toks, eval_s, wall = chat(model, sys, usr)
            tps = round(toks / eval_s, 1) if eval_s > 0 else 0
            ok = True
            note = ""
            if tid == "quiz_json":
                try:
                    q = json.loads(
                        content.strip()
                        .removeprefix("```json")
                        .removeprefix("```")
                        .removesuffix("```")
                        .strip()
                    )
                    n = len(q.get("questions", []))
                    ok = n == 3 and all("answer" in x for x in q["questions"])
                    note = f"questions={n}"
                except Exception as e:
                    ok = False
                    note = f"JSON invalid: {str(e)[:80]} | raw[:120]={content[:120]!r}"
            elif tid == "coding":
                ok = "def add" in content
                try:
                    ns = {}
                    code = (
                        content.split("```python")[-1].split("```")[0]
                        if "```" in content
                        else content
                    )
                    exec(code, ns)
                    assert ns["add"](2, 3) == 5
                    note = "exec add(2,3)==5 OK"
                except Exception as e:
                    ok = False
                    note = f"exec fail: {e}"
            else:
                hits = [e for e in expect if e.lower() in content.lower()]
                ok = len(hits) > 0
                note = (
                    f"matched {hits}"
                    if ok
                    else f"missing {expect} | got[:150]={content[:150]!r}"
                )
            mr["tasks"][tid] = {
                "pass": ok,
                "tok_s": tps,
                "wall_s": round(wall, 1),
                "note": note,
                "toks": toks,
            }
            print(
                f"  {tid}: {'PASS' if ok else 'FAIL'} {tps} t/s wall={wall:.1f}s {note}",
                flush=True,
            )
        except Exception as e:
            mr["tasks"][tid] = {"pass": False, "error": str(e)[:200]}
            print(f"  {tid}: ERROR {e}", flush=True)
    time.sleep(1)
    mr["ram_resident"] = ps_size(model)
    print(f"  RAM resident: {mr['ram_resident']}", flush=True)
    results[model] = mr
    unload(model)

# Vision round on synthetic worksheet image (main model is multimodal)
ws = make_worksheet_image()
if ws:
    for model in [m for m in TEXT_MODELS if m not in results]:
        print(f"\n===== VISION {model} =====", flush=True)
        try:
            content, toks, eval_s, wall = chat(
                model,
                "You are a tutor. Read the worksheet image exactly, then answer each question.",
                "Read ALL text in this worksheet image, then solve Q1 and Q2. Show answers as 'Q1: ...' and 'Q2: ...'.",
                images_b64=[ws],
            )
            tps = round(toks / eval_s, 1) if eval_s > 0 else 0
            ok1 = "5" in content
            ok2 = "7/8" in content
            ok = ok1 and ok2
            results[f"vision:{model}"] = {
                "pass": ok,
                "tok_s": tps,
                "wall_s": round(wall, 1),
                "note": f"Q1(x=5)={ok1} Q2(7/8)={ok2}",
                "reply": content[:400],
            }
            print(
                f"  vision: {'PASS' if ok else 'FAIL'} {tps} t/s wall={wall:.1f}s Q1={ok1} Q2={ok2}",
                flush=True,
            )
            print(f"  reply[:300]: {content[:300]!r}", flush=True)
        except Exception as e:
            results[f"vision:{model}"] = {"pass": False, "error": str(e)[:300]}
            print(f"  vision ERROR: {e}", flush=True)
        time.sleep(1)
        results[f"vision:{model}"]["ram_resident"] = ps_size(model)
        print(
            f"  RAM resident: {results[f'vision:{model}']['ram_resident']}", flush=True
        )
        unload(model)
else:
    print("PIL missing — skipped vision image gen")

print("\n===== ollama list (disk) =====")
print(subprocess.run(["ollama", "list"], capture_output=True, text=True).stdout)
print("\n===== JSON SUMMARY =====")
print(json.dumps(results, indent=1))
