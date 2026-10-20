# Known limitations & honest feature status

Last updated: 2026-10-18 (working-tree state, uncommitted work preserved).

This file exists so nobody can assume a feature works just because it appears
in the interface. Every item was established by reading code or running the
relevant tests — not from filenames.

## Verified working (tested today)

* Backend boots; `/api/health` returns ok with Ollama live (tested).
* 204 automated backend tests pass (`make fast` equivalent).
* 11 Playwright e2e checks pass on desktop **and** mobile viewports
  (`npx playwright test`, live backend + frontend).
* Live model E2E suite: 41/41 pass (Ollama + qwen3.5:9b running) — includes
  chat, quiz streaming, flashcards, exam plans, docs, memory.
* Chat streaming with usage accounting (tokens recorded per model call).
* Usage endpoints `/api/v2/usage/{summary,today}` (integration-tested).
* Anthropic adapter logic + consent gate (unit-tested with fakes — no live
  Anthropic call was made; no credentials available in this environment).
* Docs upload/ask, KB upload/search, backups create/download/restore
  (test-suite verified; live e2e also covers docs/KB/backup flows).

## Partial / needs bigger scope (documented, not done)

* **Conversation rename** — Sidebar supports pin/search/delete only; rename
  UI + endpoint do not exist yet.
* **Offline story** — the PWA shell works offline, and KaTeX maths/fonts now
  ship in the bundle, but AI answers (and most pages) need the Mac + backend
  reachable. Flashcard *reviews* queue offline; nothing else does.
* **Quotas/budgets (Stage D)** — usage is recorded and visible, but there is
  no enforced per-day/per-user cap yet. Concurrency is bounded (≤2 local
  inference tasks). If Anthropic is enabled, cost accrues uncapped.
* **Android / Google Play (Stage O/P)** — the frontend is an installable PWA
  only. There is no Capacitor wrapper, no signed Android project, no Billing
  integration, no Play data-safety paperwork. Everyone uses it via browser
  install today. See the "Android readiness" section in the README.
* **Multi-user accounts (Stage K)** — implemented opt-in in Section 13
  (Stages 1–2): `ARIA_AUTH_MODE=accounts` adds registration (students by
  default), CLI-bootstrapped admins, step-up-protected admin APIs, and
  per-account stores for chats, usage, wallets, todos, mistakes, exam
  plans, maths progress, study profile, notebooks, knowledge base and
  prompt caches; system/backup/agent tools are admin-only. Honest edges
  that remain: card payments (Stripe / Play Billing) are not implemented
  — the wallet accepts verified manual `payment` records only;
  `config.json` (model choice, cloud consent) stays a global operator
  setting; and the default `local` mode remains the recommended posture
  on a family machine until the pilot validates accounts mode.
* **Voice TTS voices** — macOS `say` uses the system default voice; no voice
  picker.
* **Research** — Google scrape → Wikipedia → DDG chain, no paid search API.
  TLS-verify fallback exists for school proxies (kill switch:
  `ARIA_SEARCH_STRICT_TLS=1`).
* **Image generation** — Pollinations.ai only (free, needs internet). No SD
  backend is configured by default.

## Accepted risks (documented trade-offs)

* `verify=False` SSL fallback on research requests — deliberate for
  TLS-intercepting school networks, logged each time, can be disabled with
  `ARIA_SEARCH_STRICT_TLS=1`.
* DOMPurify sanitises model-generated SVG in chat; mermaid runs at
  `securityLevel:'strict'`. Residual XSS risk is limited to unknown
  DOMPurify bypasses — acceptable for a single-family deployment, worth
  revisiting before any public/multi-user launch.
* The `aria_api_token` browser side is stored in `localStorage` (XSS-readable
  within the app's own origin). Fine for a 2-party trust domain; use a real
  auth system before multi-party hosting.

## Housekeeping

* `backend/data/example_rules.json` and `backend/data/chromadb/` (stale July
  snapshot) look orphaned — candidates for deletion after backup.
* One F401 lint warning in `idle_learner_service.py` (`Path` import) is
  pre-existing, unrelated to current changes.
