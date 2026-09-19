# Chat API — Core Contract + Prompt Budget

Base prefix: `/api/chat`. SSE stream (`text/event-stream`), one `data: {...}\n\n` per event.

## Request

`POST /api/chat` (multipart form):
- `message` (≤8000 chars, stripped of control chars except `\n\t`; empty → 400)
- `conversation_id` (optional, ≤64 chars, else uuid assigned; returned as `X-Conversation-Id`)
- `image` (optional, ≤20 MB → 413), `document`/`documents` (each ≤50 MB → 413, max 10 files)
- `mode`: `normal|think|fast|socratic|hype|voice` (unknown → `normal`)

Rate: 30/min chat (slowapi; no-op where slowapi absent).

## SSE events (frontend must ignore unknown `type`s)

`intent` → `progress` (intent/search/vision/reasoning/extras/done, pct 10→100) →
`status` (human label) → `tool` (web_search/youtube/vision/cheatsheet/worksheet/todo/…) →
`text` (tokens) → `sources` / `citations` / `extras` / `verification` / `suggestions` →
`image` / `diagram` → `title` / `achievement` → `timings` → `done`.
Errors: `progress{status:error}` (per-step, non-fatal) or `error` (fatal, friendly text) then `done`.

`timings` (additive, ms since orchestrate start): `intent/retrieval/vision/prompt_ready/ttft/llm_done/total`.
Baseline hunting starts here — record TTFT per mode before optimising.

## Prompt budget (slice 2)

`_build_system_prompt(..., max_chars)` caps total system prompt.
Default `max_chars=20000` (≈5k tokens; always fits 8k window).
Override: runtime config `max_prompt_chars`, or `AriaSettings.max_prompt_chars` (`ARIA_MAX_PROMPT_CHARS`).

Measured baseline (this Mac):
- base chat prompt ~6,737 chars
- worst-case combined (doc 15k + mem 5k + KB 5k + search + vision + youtube + cross-check) ~41,226 chars ≈ 10k tokens — exceeds 8k window.

Priority (cut first → keep last): cross_check → youtube transcript → search snippets → KB → memory → vision → doc.
Truncation appends `…[truncated to fit prompt budget]` and logs `Prompt budget applied`.
Small prompts are byte-identical (no behaviour change).

Pure helper `enforce_prompt_budget()` in `services/prompt_builder.py` is hermetic — pinned by `tests/test_prompt_budget.py`.

## Limits

- Doc context: `doc_context_chars` (default 8000, multi-doc up to 15000 cap) then prompt budget.
- Ollama: per-loop semaphore 2, `TIMEOUT=300s` stream (future: lower + breaker, measured).
- Concurrency (slice 3): max 4 SSE streams (`MAX_CHAT_STREAMS`), 5th → `429 busy`
  (matches voice WS 4-session cap). Validation (400/422/413) runs before acquire
  so rejected requests never consume a slot; slot released in `finally`.
