# Fine-tuning ARIA's File Organizer (Ollama)

ARIA's File Organizer (AI Rename + Organize) runs on a local Ollama model.
Out of the box it already works well thanks to the few-shot examples baked
into `services/organizer_deep.py`. This guide explains how to take it
further by **fine-tuning a LoRA adapter** on a small custom dataset — the
real "training" path.

> Ollama itself can't be trained. It only *runs* models. What we train is
> a lightweight LoRA adapter that plugs into a base model, then register
> the result back into Ollama.

---

## What you get

| | Before | After fine-tune |
|---|---|---|
| Model | `qwen3:8b` (generic reasoning) | `organizer-3b` (specialised in renaming + filing) |
| Rename accuracy | Good | Better, follows your naming style |
| Speed | ~8 tok/s | ~30 tok/s (3B vs 8B) |
| RAM | ~8 GB | ~3 GB |

## The dataset (100 examples)

`scripts/make_organizer_dataset.py` contains 100 curated examples:

- Every school subject (Maths, Science, English, History, Geography,
  Computing, PDHPE, Music, Visual Arts, Languages, Religion) **plus**
  household files that should go to `General` (invoices, receipts, photos,
  resumes, recipes, contracts…).
- Documents, images/OCR (`DESCRIPTION:` vision-style content), code,
  spreadsheets, slides and PDFs.
- Each example matches the exact prompt format the app uses at runtime
  (`DeepOrganizer.propose_one`), so training = production.

Regenerating:
```bash
cd backend && source venv/bin/activate
python scripts/make_organizer_dataset.py
# → backend/data/finetune/{organizer_dataset,train,valid}.jsonl
```

Add more examples any time — the script validates every folder against the
curriculum taxonomy and will refuse to write invalid data.

## Training (one command)

```bash
./backend/scripts/finetune_organizer.sh
```

What it does:

1. Generates the dataset.
2. Creates a scratch venv with `mlx-lm` (Apple's MLX framework — the fast
   path on M4; it does not touch the app's own venv).
3. Trains a LoRA adapter (8 layers, r=8, lr 1e-5, 400 iters, seq len 4096)
   on `Qwen/Qwen2.5-3B-Instruct` (auto-downloads ~6 GB, one time only).
4. Fuses the adapter into the base model and converts to GGUF (q8_0) using
   llama.cpp's converter (cloned shallow into `storage/finetune/`).
5. `ollama create organizer-3b` and sets the app's `organizer_model`
   config to use it.

### How long does it take?

On a MacBook Air M4 (16 GB): **roughly 2–5 hours** for 400 iters. You can
run fewer with `--iters 200`. The adapter is saved every 100 iters, so a
power cut only costs the last few minutes.

### What does it cost?

Nothing — 100% local. Disk: ~6 GB base model + ~2 GB fused output
(in `backend/storage/finetune/`, delete freely).

## Verifying & reverting

After training, open ARIA → **File Organizer → AI Rename + Organize** and
try a few files you haven't tested before. Compare names/folders against
what you'd expect.

- **Revert to the default model:** Admin page → set *Organizer model* to
  empty (or run `python -c "from models.database import save_config;
  save_config({'organizer_model': ''})"` from `backend/`).
- **Delete the trained model:** `ollama rm organizer-3b`
- **Retrain with more data:** add examples to `make_organizer_dataset.py`,
  then re-run the script — it is deterministic (seed 42), so only new
  examples change the training split.

## Model choices

| Base model | Size | Why |
|---|---|---|
| `Qwen/Qwen2.5-3B-Instruct` (default) | 3B | Best quality/speed trade-off for 16 GB M4 training |
| `Qwen/Qwen2.5-7B-Instruct` | 7B | Higher ceiling, but slow/risky to train on 16 GB |
| `meta-llama/Llama-3.2-3B-Instruct` | 3B | Smaller footprint; slightly weaker at JSON |

The app always falls back gracefully: if the `organizer-3b` model is
missing or Ollama is offline, the existing keyword guard + fallback paths
(`organizer_deep.py`) still produce safe proposals.

## Why not use the downloaded education datasets?

`HighSchool_Study_AI_Datasets/` (GSM8K, MMLU, SQuAD, ARC, SciQ,
OpenAssistant) is general education QA data — great for improving a
model's *knowledge*, but it contains **no examples of file renaming or
folder categorisation**, so it can't teach the organizer its job. The
100 examples in this pipeline are purpose-built for the task.
