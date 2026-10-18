# ARIA — Phase 19 Deliverables Report

**Date of report:** 2026-10-19 · **Competitive research date:** 2026-10-18
**Scope:** competitive landscape, differentiation, repo audit result, security findings, remaining work.
**Evidence rule applied throughout:** every claim below distinguishes *implemented & tested* vs *unverified*
vs *known-broken*. Competitive facts cite source and date; nothing is inferred beyond what the source states.
ARIA is a free, local-first study app for one student on one Mac — statements about pricing/features of
competitors describe *them*, not promises to build parity.

---

## 1. Executive Summary

ARIA (v2.6, repo `aria-2`) is a local-first AI study assistant: Ollama on-device (qwen3.5:9b-main +
nomic-embed-Text embeddings), FastAPI backend (~21k LOC, 19 routers), React/Vite frontend (17 pages).
This report closes the audit-fix phase and sets the build order for what remains.

**State after this phase**
- Backend: **216 deterministic tests passing** (was 164 at baseline); full **live suite 245 passed**
  (incl. 41 e2e vs local Ollama `qwen3.5:9b`, 2026-10-18, 11m36s wall).
- Frontend: 8 vitest suites pass; `npm run build` succeeds; ESLint clean on changed files.
- All changes committed in three waves (backend, frontend, repo tooling) through the repo's own
  pre-commit gates (ruff, ruff-format, eslint, bandit, gitleaks, cspell, whitespace/EOF).
- Security posture hardened: untrusted-content fencing, shared rate limiter, middleware order,
  agent drive-by protection, path traversal block, KB persistence, server-anchored maths scoring,
  TLS-verify default, token gates, user-data de-tracking.

**Explicitly NOT done (do not assume these exist):** subscription tiers, model routing/cost tiers,
adaptive explanation styles, unified student-workflow phase, server-side grading of open-response
maths OCR for scans. These are on the remaining-work list (§7).

---

## 2. Competitive Landscape (verified 2026-10-18)

Pricing/features collected from vendor-controlled sources; where a figure came from a third-party
comparison rather than the vendor, that is noted. **No claim here implies ARIA has the equivalent
feature.**

| Product | Verified facts (source, date) | Free-tier limitation leveraged |
|---|---|---|
| **Gauth (ByteDance)** | Terms of Service: free tier = **1 search**; Plus **US$11.99/mo**, $31.99/qtr, $99.99/yr (in-app via Stripe); ToS admits **AI-generated solutions may be wrong** and are not subject-matter-expert reviewed for every case (Gauth DoS/ToS pages, 2026-10-18) | Search quota + paid wall; own ToS concedes correctness risk |
| **Knowt** | ~**20 free AI uses/mo**; positions as free Quizlet import & flashcards (Coursebox "Knowt vs Quizlet" comparison, 2026-01-09 — secondary source) | AI-use cap |
| **Quizlet** | Free tier: **tests capped at 5 questions**, Learn mode **20 rounds/mo** (Coursebox comparison, 2026-01-09 — secondary source) | Feature throttling to push Plus |
| **Gemini for Education (Google)** | Free SAT / JEE practice experience announced (Google blog, **2026-02-13**) | Free but cloud, requires Google account/data pipeline; not a local app |
| **Maigie** | Marketing site live; AI study companion (maigie.com, 2026-10-18) | — |
| **PrepPath (AU)** | Commercial prep for **NAPLAN, OC, Selective, ICAS** (preppath.com.au, 2026-10-18) | Paid practice-test products |
| **RemNote** | Pro **US$8/mo** (remnote.com/pricing, 2026-10-18) | Spaced-repetition core is freemium |
| **Photomath** | Plus **US$9.99/mo** (PennPaper AI-math comparison, 2026-02-28 — secondary); commonly criticized as **solver-not-tutor** (shows answer steps, weak at teaching method) | Paid scan/step features |
| **Intu AI** | ~**A$30/mo**; markets **CAS-based answer verification** (PennPaper, 2026-02-28 — secondary source) | Subscription |

### Market takeaways (only what the sources support)
1. **AI-use quotas and per-question caps are the industry's monetization lever** (Gauth, Knowt, Quizlet).
2. **Correctness is an acknowledged weakness**: Gauth's own ToS concedes LLM solutions may be wrong;
   Intu AI differentiates by CAS-checking — implying AI-math correctness sells — while ARIA
   always states when a result came from deterministic checks (behaviour-backed, not branding).
3. **AU exam-specific practice is a paid niche** (PrepPath), i.e., localized curriculum content has market value.
4. **Tool-competitor** (RemNote, Photomath) pricing sits around $8–10/mo, i.e., ARIA's free local offering hits their paid tier value without a subscription — but only where ARIA genuinely implements the capability.

---

## 3. Five Differentiation Opportunities (grounded in what exists today)

Each opportunity notes the ARIA capability it rests on and its current implementation status. **Nothing
here claims a feature that is not built; items marked PLANNED are where remaining work would land
(§7).**

1. **No caps, no subscription — friction-free unlimited use.**
   ARIA's core loops (chat tutor, quiz generation, KB RAG, exams maths sets) are local and free.
   Competitors meter exactly these (Gauth 1 search; Quizlet 5-question tests; Knowt 20 AI uses).
   Status: implemented & tested for the loops that exist. Requires no new engineering.

2. **Checkable correctness instead of confident hallucination.**
   Only deterministic math (AST eval + sympy) may rewrite quiz answer keys; contradictions
   become `disputed` rather than silently rewritten; untrusted sourced content is nonce-fenced so
   stored pages/web results cannot hijack the tutor prompt. This maps to the CAS-verification
   differentiator Intu AI charges for, **with the open method visible**. Status: implemented & tested
   (`tests/test_answer_key_safety.py`, untrusted tests). PLANNED: extend verification beyond quiz/math.

3. **Local-first privacy as a first-class property.**
   Conversations, KB, notebooks never leave the Mac; no cloud consent required to be useful; user
   transcripts untracked from git. Competitive packages are all cloud. Status: implemented (offline
   fallback banks keep core flows working with Ollama down). PLANNED: document the privacy audit trail.

4. **Exam-anchored revision loop (AU-selective flavour).**
   Exam plan → desktop maths accelerator (fallback bank is selective-style) → mistake book →
   spaced repetition, with server-anchored mastery so scores reflect generated sets. NSW syllabus
   gating exists in KB collections (education_au, Stage 5.2/5.3 topic tiers). Status: implemented
   end-to-end wiring exists; dashboard stays honest (real heatmap streaks). PLANNED: deeper NSW
   outcome-level curriculum mapping (align with NESA outcomes explicitly beyond current topic metadata).

5. **Extensible model routing later — but honestly, not yet.**
   `backend/services/ai_providers.py` + pricing config exist (cloud off by default; ANTHROPIC keys +
   explicit `ARIA_CLOUD_CONSENT=1` required, docs/PROVIDERS.md). This positions ARIA to offer
   "free local / paid cloud per-token" later WITHOUT paid-gating features that don't exist.
   Status: plumbing only, **no entitlement/billing system exists; subscriptions remain deferred**.

---

## 4. What's Implemented & Tested vs Unverified vs Broken (audit verdicts)

Frontend/backend audits were run via two independent subagent passes; **every major claim was
individually verified before being acted on** — including one false positive: the audit's #1 frontend
issue claimed `ChatPage.jsx` didn't import `showToast`; hand-check proved it **does** (claim withdrawn
from the fix list).

### Implemented & tested (evidence: named test files/commands)
- Chat + RAG (KB search → grounded prompt), quiz generation + verification, dedupe (0.80 threshold)
  — `tests/test_answer_key_safety.py`, e2e suite.
- Sympy-backed equation solving & single-variable math checks — same file.
- Untrusted-content fencing across orchestrator/docs/kb/notebook paths — hardening tests.
- Shared rate limit (chat 30/min + app 120/min on one counter) — token-gate & middleware tests.
- Maths accelerator: fallback bank works offline; **session-anchored mastery** (spoof-resistant) —
  `tests/test_maths_sessions.py`.
- KB persistence: uploads stored in `DATA_DIR/knowledge_base/files` keyed by content hash;
  `rebuild_index` rebuilds rather than eternally skipping; delete removes managed copies —
  `tests/test_kb_rebuild.py`.
- Exam plan, mistakes book, syllabus, notebooks (path-traversal-safe), spaced repetition (digit 0–5
  grading), dashboard honest data (heatmap streaks), a11y (aria-live quiz feedback, contrast mode fixed).

### Unverified (exists, not yet covered by regression tests)
- `routers/docs.py`, `routers/research.py`, `routers/voice.py` — endpoints ship, but no router tests yet.
- Frontend Playwright e2e (`frontend/e2e/`) — configured, not exercised in this session's runs.
- Model routing plumbing (ai_providers/pricing) — module-level tests only (`test_ai_providers.py`);
  no multi-provider live check beyond Ollama.

### Known-broken → fixed this phase (before/after in parentheses)
- `rebuild_index` was permanently broken (every doc "skipped") → now rebuilds (test added).
- `/api/maths/submit` accepted client-claimed scores unbounded → session-anchored, clamped (test added).
- Rate limiter's chat/app counters were disjoint (30-min cap unenforceable) → shared limiter.
- Scanned PDFs silently produced "No text found in PDF." → honest document notice surfaced to chat.
- Frontend: dead high-contrast class (CSS never matched) → fixed at `documentElement`.
- Dashboard showed achievements-count as "streak" → real heatmap streak.

---

## 5. Security Findings

### Fixed in this phase (all with regression tests unless noted)
| # | Finding | Severity | Fix |
|---|---|---|---|
| 1 | LLM-facing external content (KB, docs, web search, YouTube, vision) could inject prompt instructions | High | `services/untrusted.py` nonce-fenced wrapping applied at every ingestion site |
| 2 | Chat 30/min cap unenforceable: two disjoint SlowAPI limiter instances | Med | `services/rate_limit.py` shared instance, middleware-ordered |
| 3 | 401 responses from token gate lacked CORS headers (opaque browser errors, no clean feedback) | Low | Middleware reorder: CORS outermost |
| 4 | Cross-site drive-by on agent endpoints (browser-form POST from any site) | Med | `X-Agent-Request: 1` required header; loopback-only file jail stays |
| 5 | KB notebook `_safe_path` accepted `../` ids → path traversal on read/write | High | Regex-validated ids + travel-ceiling check |
| 6 | KB uploads used ephemeral temp path; original files never kept → rebuild impossible | Med (reliability+privacy) | Persist originals under DATA_DIR (keyed by hash); deletion cleans managed copies |
| 7 | `/api/maths/submit` trusted transcript client-side → unbounded fake mastery | Med (integrity) | Server-side session: generate registers set; submit scores per-question marks clamped to it |
| 8 | Web-search TLS: cert verification weakened by default for "school proxy" compat | Med | `ARIA_SEARCH_STRICT_TLS` default-on; opt-out documented + logged; warnings scoped |
| 9 | `/api` token gate optional only; agent token separate — acceptable for local-first but thin on LAN | Low | Documented hardening path; LAN-mode warning in start.sh; header requirement above |
| 10 | Scanned-PDF honesty: a blank-PDF notice could be mistaken for an answer | Low | Explicit "ARIA DOCUMENT NOTICE" — tutor says it cannot read the file |
| 11 | **User chat transcripts (`backend/data/conversations.json`) were tracked in git** — leak-on-push risk | Med (privacy) | Untracked (`git rm --cached`), `.gitignore` rule; file intact on disk |

### Open (tracked, not fixed — do not leak through silent omission)
- **DTZ debt (61 findings)**: `datetime.now()`/`date.today()` naive usage across services/scripts/tests.
  *Deferred deliberately*: a correct fix must migrate stored timestamps **and** comparison sites
  together (Sydney local-time vs UTC affects day-boundary logic: streaks, exam dues). Covered by
  explicit, documented `pyproject` ignores, NOT silent suppression; changes are behaviour-risky with
  the app live. Plan in §7 item 1.
- Agent token (`ARIA_AGENT_TOKEN`) exists but is opt-in; when LAN exposure is enabled, loopback-only
  jail is the main barrier (documented).
- ChromaDB pip-audit exceptions (tenant/RBAC server CVEs) not exploitable with embedded
  PersistentClient — re-verify yearly (Makefile `audit` target).
- No CSRF-style auth wall on `/api` for non-loopback by default (token gate is the recommended
  opt-in; localhost-first design accepted).

---

## 6. How to Verify Every Claim Above

```bash
# Deterministic backend suite (isolates ARIA_DATA_DIR — safe while app runs)
cd backend && ../.venv/bin/python -m pytest tests/ -q --ignore=tests/test_e2e_features.py   # 216 passed

# Full live suite incl. e2e vs Ollama (needs Ollama up: qwen3.5:9b + nomic-embed-text)
cd backend && ../.venv/bin/python -m pytest tests/ -q    # 245 passed on 2026-10-18 (11m36s)

# Frontend
cd frontend && npm test           # 8 suites
cd frontend && npm run build      # succeeds

# Lint/security gates (same ones pre-commit runs per commit)
cd ../ && pre-commit run --all-files
```

Commit trail: `3845b05` backend wave+Stage A · `090db52` frontend Stage B+wave · tooling commit (§7 refs).

---

## 7. Remaining Work (calibrated, priority order)

1. **Timezone normalization pass** — migrate 61 DTZ findings + stored timestamps coherently
   (datasets: streaks, exam plans, usage). Do NOT piecemeal; needs data-backup test plan.
2. **Regression tests for untested routers** — `docs`, `research`, `voice` (each endpoint's happy
   path + auth/length clamps).
3. **Server-side grading of open-response maths** requires an LLM-grade pass — today only the
   count mechanics are server-anchored; per-mark honesty still relies on the student.
   Deciding honestly: build it as a *hint*, not a guarantee. Note UX: self-mark with revealed
   solutions stays; server anchor prevents count inflation.
4. **Scanned-PDF path** — either honest frontend UX (progressive notice + "cannot read, ask
   something else" affordance, surfacing existing backend) or opt-in OCR. Decide UX first.
5. **Frontend Playwright e2e** — run and wire into CI (configs exist, currently unexercised).
6. **Phases 3–13 core builds (not started)** — unified student workflow, adaptive explanation
   styles, lesson-of-the-day, model routing with cost caps, deeper NSW outcome mapping.
7. **Deferred by design**: subscription tiers/billing — no entitlement system exists; do not
   propose paid gating while core student-facing features remain unbuilt.
8. **Yearly**: re-run pip-audit exceptions; re-verify competitive pricing snapshot.

---

*Prepared with a no-fabrication constraint: competitor facts only from cited sources with dates;
ARIA capabilities only where a runnable test or verified code path exists. Corrections to this report
should cite the same standard.*
