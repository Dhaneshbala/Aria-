# Study Buddy Changelog

## Unreleased — renamed ARIA → Study Buddy
- User-visible rename: app window, Study Buddy.app bundle, browser title,
  header logo, onboarding, placeholders, toasts, AI self-intro
  ("You are Study Buddy"), error messages, PWA manifest, new S icon.
  Technical identifiers untouched on purpose: `ARIA_*` env vars, `~/.aria_data`,
  `aria-backup-*` files (old backups still restore), CSS theme names.

## Unreleased — Mac app
- **ARIA.app, real window** (`backend/aria_window.py` + `./build-app.sh`):
  double-click opens ARIA in a native WKWebView window (pywebview) — no
  Terminal ever. Server runs in-process; closing the window stops it.
  Single-instance: a second launch connects to the running server.
  Ollama/model/UI problems render as in-window error pages.
  Headless check: `ARIA_WINDOW_TEST=1` (no popup); pinned by
  `tests/test_aria_window.py` (7 tests).
- **App fix — false "install models" page:** model check used the `ollama` CLI,
  invisible to double-clicked apps (no `/usr/local/bin` on GUI PATH), so it
  reported missing models you already have. Now checked over HTTP `/api/tags`
  (handles registry `:latest` suffix); `find_bin()` covers ollama/npm
  fallbacks; bundle launcher exports a fuller PATH. Verified healthy under a
  stripped GUI-like PATH.
- **App fix — `{"detail":"Not Found"}` window:** the window reused any server
  answering `/api/health`, including a stale pre-single-server backend (yours:
  detached PID from this morning, no UI routes) — hence raw JSON. Reuse now
  requires `/` to serve HTML; otherwise the app starts its own server on the
  next free port (8001…). Verified healthy with :8000 stale-occupied.
  Pinned by fake-server tests in `tests/test_aria_window.py` (13 tests).
- **App fix — "Backend didn't start" page:** cold start measured ~14 s, so the
  20 s budget was too tight on a busy machine. Budget is now 60 s; every phase
  logs to `~/.aria_data/aria-app.log` (Finder apps have no console) and the
  error page points at it.
- **Jail fix:** agent file jail used `cwd` — Finder launches with `cwd=/`,
  jailing nothing. Now anchored on the repo root (writes still DATA_DIR-only).
- **App fix — Rosetta crash `(exited, code 1)`:** the venv Python is universal2
  but its compiled wheels are arm64-only; the app had run translated, so every
  child inherited x86_64 and died on import (byte-identical ImportError
  reproduced with `arch -x86_64`). Triple guard now: `LSRequiresNativeExecution`
  in Info.plist, `arch -arm64` on the bundle launcher, `arch -arm64` on the
  sidecar argv (proven to recover to arm64 even from a translated parent).
  Pinned by launcher/cmd tests (`test_aria_window.py`, 17 tests).
- **App fix — silent server death:** the in-thread server died after ~10 healthy
  minutes with zero traceback. Server now runs as a sidecar child process
  (isolated from the Cocoa runloop) with stderr captured to
  `~/.aria_data/aria-server.log`; a watchdog shows an in-window "Server
  stopped" page with log paths if it ever exits, and window close terminates
  it. Verified healthy via sidecar (`test_aria_window.py`, 16 tests).
- **Single-server mode:** FastAPI serves `frontend/dist` on :8000
  (`/` + SPA fallback; `/api/*` stays JSON, unknown → 404 JSON). No second
  process, no vite in prod. Dev flow untouched (`./start.sh` + `npm run dev`).
  Opt-out: `ARIA_SERVE_FRONTEND=0`. New `start-app.sh` (`ARIA_PORT` override).
- App icons: `frontend/public/icon-192/512.png` (+ apple-touch-icon) generated
  offline; wired as favicon. Verified on spare ports (200 UI + API, JSON 404s).

## Unreleased — all-features quality program (per `backend/docs/quality-bar.md`)
- **Eval harness, first correctness baseline** (`backend/scripts/eval_bank_maths.py`):
  warm-up bank 20/20, hard bank 28/30 on gemma4:e4b-mlx. Both misses are
  two-step algebra (stops a step early) — exactly what the orchestrator's
  math verifier exists to catch. This number must not go down.
- **Feature 1 (chat core), slice 1:** orchestrate emits an additive `timings`
  event (`intent/retrieval/vision/prompt_ready/ttft/llm_done/total` ms)
  before `done`; frontends ignore unknown types. Baseline hunting starts here.
- **Feature 1 (chat core), slice 2:** prompt budget (`max_prompt_chars=20000`,
  `ARIA_MAX_PROMPT_CHARS`). Baseline: base ~6.7k chars, worst combined ~41k
  chars (~10k tokens, blows 8k window). Now capped (cross-check → youtube →
  search → KB → memory → vision → doc priority); small prompts byte-identical.
  Pinned by `tests/test_prompt_budget.py` (5 tests); contract in `backend/docs/chat_api.md`.
- **Feature 2 (quiz/exam sim), slice 1:** request caps + rate limit.
  `StudyRequest`: `topic` 1–300, `level` allowlist, `count` 1–15 (was uncapped —
  `count=100` burned a full LLM run before parser capped to 10), `days` 1–365;
  30/min slowapi; notification uploads ≤10 MB → 413. Pinned by
  `tests/test_study_caps.py` (7 tests); contract in `backend/docs/study_api.md`.
- **Feature 3 (SR/flashcards), slice 1:** SM-2 pinned + ID/cap fixes. IDs are
  now uuid-hex (was `timestamp_ms` — collided under bulk-same-ms); bulk caps
  200 + skips blanks (was unbounded + stored blanks); CSV import ≤2 MB / 200
  rows (was OOM-able). Pinned by `tests/test_sr_correctness.py` (6 tests);
  contract in `backend/docs/spaced_repetition.md`.
- **Features 4–8, slice 1 (caps + correctness):** analytics streak/heatmap
  baselines pinned (`test_analytics_logic.py`); KB upload ≤20 MB / ≤10 files
  (`test_kb_caps.py`); citation hallucination-drop pinned
  (`test_citation_correctness.py`); imagegen 30/min limit + 422s pinned
  (`test_imagegen_caps.py`); notebook autofolder crash fix
  `_save_notebooks()` → `_save_notebook(notebook)` (`test_notebook_fix.py`).
  Notes in `backend/docs/caps_slices.md`. Suite: 81 passed.
- **Feature 1 (chat core), slice 3:** SSE concurrency guard (`MAX_CHAT_STREAMS=4`,
  5th → 429 busy, matches voice WS cap). Validation runs before acquire; slot
  released in `finally`. Pinned by `tests/test_chat_concurrency.py`. Suite: 85 passed.

Restart the backend to pick this up (`Ctrl+C` → `./start.sh`).

### Speak & hear
- Voice replies start on sentence 1 while the AI still streams (was: wait
  for the whole answer). Time-to-first-audio ≈ LLM first token + ~0.5 s.
- **Piper neural TTS** for en/hi/te/bn/ml/mr/ur (0.1–0.5 s/sentence, offline,
  consistent). macOS voices stay as fallback — incl. Tamil (Vani), the only
  engine for ta/kn/fr/…. Provision: `ARIA_FETCH_VOICES=1 ./start.sh`.
- Live partial transcripts while you talk (WebSocket), with REST as the
  accuracy source of truth — if the final pass fails, the live partial
  saves the turn instead of discarding it.
- Barge-in: Interrupt button / `Esc` cuts ARIA off mid-answer and listens.
- Silence auto-send (2.5 s) with mic level meter; stop never fires ghost turns.
- Maths spoken aloud (`x^2` → "x squared"), answers match your language,
  no "Hello!" filler burning the first sentence.

### Robustness (all measured or tested)
- 93 voice tests green; 177 across the runnable suite.
- Caps everywhere: 4 concurrent streams (5th gets `busy`), TTS concurrency 2,
  3 resident Piper voices (~200 MB), 25 MB uploads, 1 MB WS chunks,
  5 min idle / 15 min session limits, REST rate limits.
- TTS cache (LRU, per-language, per-engine) + next-sentence prefetch.
- Whisper warms on voice-open (first turn 4.8 s → ~2.3 s); turbo stays lazy
  so nobody downloads 1.6 GB by surprise.

### Measured budgets (`backend/scripts/bench_voice.py`, this Mac)
- Full spoken turn end-to-end: LLM first token 10–15 s, TTS ~0.5 s.
  The remaining wait is the AI thinking, not the voice.
- A smaller voice model (`qwen3:4b`) was evaluated but its registry is
  unreachable from managed networks — gemma stays until that changes.

### Docs & ops
- `backend/docs/voice_api.md`: full protocol reference + budgets.
- README troubleshooting: voice slowness, neural voices, Tamil voice setup.
- Admin → System Status shows the voice engine map.
