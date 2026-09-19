# Hardening Slices 4–8 — Caps & Correctness Notes

## Feature 4 — Analytics (`services/analytics_service.py`)
- Pinned baselines: `_calculate_streak(daily, now)` consecutive-day logic,
  heatmap `level` 0–4 bounded, empty-profile safe (`overall_accuracy 0`).
- Tests: `tests/test_analytics_logic.py` (4 hermetic).
- Known vibes (1000-day target): grade thresholds + focus weights need backtest
  harness (predicted Band vs actual), not hard-coded `0.9/0.8`, `/3,/5,/20`.

## Feature 5 — KB (`routers/kb.py`)
- `POST /upload`: empty → 400, >20 MB → 413 (was: unbounded read → RAM/OOM).
- `POST /upload-multiple`: >10 files → 400, per-file empty/oversize → per-item
  error (was: unbounded fan-out).
- `GET /search`: `n` 1–20 (422 outside).
- Tests: `tests/test_kb_caps.py` (3, validation-only, no model).

## Feature 6 — Citations (`services/citation_service.py`)
- `parse_citations` drops hallucinated indices (no matching source → skipped),
  dedupes repeats. Pinned by `tests/test_citation_correctness.py` (3).
- 1000-day target: URL liveness + trust/recency + citation-F1 eval bank.

## Feature 7 — Imagegen (`routers/imagegen.py`)
- Validation already good (`prompt` 1–2000, `w/h` 64–2048); added 30/min
  slowapi limit (no-op where absent) to prevent remote-FLUX abuse.
- Tests: `tests/test_imagegen_caps.py` (2 × 422).

## Feature 8 — Notebooks (`routers/notebooks.py:438`)
- Crash fix: `svc._save_notebooks()` (missing → 500) → `svc._save_notebook(notebook)`.
- Pinned by `tests/test_notebook_fix.py` (static + hasattr, hermetic).
