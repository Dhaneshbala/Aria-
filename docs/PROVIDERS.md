# AI Providers — how ARIA routes model work

ARIA is **local-first by design**: every AI feature runs on your Mac through
Ollama. No study content leaves the machine unless you explicitly opt in to a
cloud provider. This document explains the routing rules, the opt-in process,
and all guarantees and limits.

## Current providers

| Provider | Models (verified IDs) | Where it runs | When it's used | Cost |
|---|---|---|---|---|
| **Ollama** (default) | `qwen3.5:9b` (main), `nomic-embed-text` (embeddings) | Your Mac (Metal GPU) | Always — chat, quizzes, flashcards, notes, vision, exams | Free |
| **Anthropic** (opt-in) | `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`, `claude-fable-5-1` | api.anthropic.com | Only on explicit `anthropic:` model IDs | Per-token (see pricing below) |

Model IDs were verified against Anthropic's docs in October 2026
(platform.claude.com/docs). Anthropic keeps a documented retirement schedule;
check before long-term reliance on a specific ID.

## Routing rules

1. **No silent provider switching.** A plain model name (e.g. `qwen3.5:9b`)
   always runs on Ollama — never on the cloud. Ollama being down produces a
   clear error, not a hidden cloud request.
2. **Cloud requires an explicit prefix.** A request only goes to Anthropic
   when the model name is exactly `anthropic:<claude-model-id>`, e.g.
   `anthropic:claude-haiku-5-5`.
3. **Cloud requires consent + credential, server-side.** Even with the prefix,
   the request is refused with a clear error unless BOTH are set in the
   backend environment:
   - `ANTHROPIC_API_KEY=…` (your Anthropic credential), and
   - `ARIA_CLOUD_CONSENT=1` (explicit confirmation that student messages go
     to Anthropic).
4. **System-prompt safety carries over.** The orchestrator's grade-locked
   profanity/safety prompts are only applied at Ollama-level layers today.
   When you opt into a cloud model through `complete()`/`stream()`, the
   `system` prompt is still sent to Anthropic, but verify output suitability
   yourself before handing a device to a child.

## What is sent to Anthropic when enabled

* The `system` prompt text and the single user `message` that ARIA passes to
  `complete()` / `stream()` for that request.
* Conversation history is NOT attached automatically by the provider adapter
  (`stream_chat`, which notebooks use, stays Ollama-only).
* No documents, images, embeddings, or stored memory are uploaded.
* Anthropic's own data-retention policies then apply to the prompt content —
  consult their documentation; ARIA controls only what is transmitted.

## Timeouts, retries and cancellation

| Path | Timeout | Retry policy |
|---|---|---|
| `OllamaService.complete()` via Anthropic | min(requested, 120 s) | one retry after 1 s on 429/5xx; no further retries |
| `OllamaService.stream()` via Anthropic | 120 s | no retry once tokens have streamed (student already saw output) |
| Any Ollama path | 300 s (config `TIMEOUT`) | unchanged — no automatic retry (post-timeout requests are destroyed, payloads may be large) |

## Usage & cost accounting (server-side)

Every model call is written to `~/.aria_data/usage.json` via
`services/usage_service.py`:

* provider + model + date
* provider-reported token counts — these are **exact** counts (Ollama reports
  `prompt_eval_count`/`eval_count`; Anthropic reports `usage.input_tokens`/
  `usage.output_tokens`). Nothing is read from the frontend.
* failures and cache hits, wall time
* an **estimate-of-cost** field computed from `config/pricing.py` (never
  computed inline elsewhere). Local inference is priced at $0. Anthropic
  prices here are the documented base rates (verified 2026-10):
  Haiku 5.5 $0.10/$0.50, Sonnet 5.5 $2/$10, Opus 5.5 $4/$20,
  Fable 5.1 $10/$50 per million input/output tokens.

View totals in the app: **Admin → AI Usage** (last-30-day rollup), or
programmatically:

```
GET /api/v2/usage/summary?days=30
GET /api/v2/usage/today
```

Limits: the ledger is an accounting record. It is not yet a quota system —
per-request concurrency is bounded by OllamaService's semaphore (≤2
concurrent tasks on the local machine), but there is no per-day spend cap
yet. If you enable Anthropic, budget accordingly (or add a `max_tokens` cap
per call).

## Setting Anthropic up (only if you want it)

1. Get an API key from console.anthropic.com.
2. Append to `.env` (which is gitignored):
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ARIA_CLOUD_CONSENT=1
   ```
3. Restart ARIA (`./start.sh`), then pick `anthropic:claude-haiku-5-5` as the
   model in **Admin → model settings** (type it in), or call the API with
   that model string.
4. Check **Admin → AI Usage** after some requests to see tokens/cost.

To disable again: remove the two lines (or unset `ARIA_CLOUD_CONSENT`) and
restart — cloud routing refuses immediately once consent is gone.

## Tests

`backend/tests/test_ai_providers.py` covers the routing, the consent gate,
provider-reported token recording, cost estimation, retry bounds, and the
TLS kill switch — all with faked clients; no real API or Ollama calls.
