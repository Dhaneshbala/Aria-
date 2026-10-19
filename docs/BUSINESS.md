# ARIA — Business Plan (small-scale, kid-run, parent-backed)

Status: **planning** · Owner: Dhanesh (Year 9) · Legal owner/adult-of-record: **a parent/guardian** (required — see §5)
Last updated: 2026-10-19

---

## 1. What we're selling

ARIA is already built: a local-first AI study assistant for NSW students
(chat brain, quizzes, mistake book with drill-to-mastery, flashcards + spaced
repetition, maths accelerator, exam plans, syllabus tracker, voice tutor).

**Freemium shape:**

| Tier | Brain | Price | What you get |
|---|---|---|---|
| **Free (Local)** | gemma3/qwen via Ollama, on-device | $0, forever | The entire suite. Private, offline, no account, no card. |
| **Cloud Boost** | Claude Sonnet 5.5 via Dhanesh's gateway | subscription | Frontier-grade answers, marking, and generation on top of the same app. |

The Free tier is the moat, not the compromise: no competitor gives a
classmate a genuinely usable, private, offline study app with zero signup.
Cloud Boost is a premium layer over it.

**Critical architecture rule (non-negotiable):** the Anthropic key never
ships inside the app and is never handed to a user (Anthropic ToS requires
keys stay confidential; distributing it is also financially fatal — every
user bills our card with no cap). Users get *tokens to our gateway*, not
the key.

```
user's ARIA ──▶ OUR GATEWAY (holds 1 Anthropic key server-side)
                   │ validate user token → quota left? → meter usage → Claude
                   └ per-user daily/monthly caps, spend log, kill switch
```

---

## 2. Unit economics (estimates — to be validated in the pilot, §7)

Anthropic prices (Sep 2026, Claude API):

- Claude Sonnet 5.5: **$2 / MTok input, $10 / MTok output** (Batch API −50%)
- Prompt cache reads: **5% of input price on Sonnet 5.5 (≈$0.10 / MTok)** —
  big for us: system prompt + syllabus context get cached.
- Effort setting changes cost: **`medium` effort = fewer thinking tokens**.
  Thinking tokens bill as output. We default to medium, high for exam-prep.

Per-action rough cost (Sonnet 5.5, medium effort, cache hits):

| Action | ~Tokens in/out | ~Cost |
|---|---|---|
| Chat answer (RAG sources attached) | 4–6K / 0.3–1K | $0.01–0.02 |
| Quiz set (5 questions + marking) | 1.5K / 1K | $0.013 |
| Flashcard deck (10 cards) | 1.2K / 0.8K | $0.010 |
| Maths set + step-marking | 2K / 1.2K | $0.016 |
| Topic summary / cheat sheet | 2K / 0.6K | $0.010 |

A **moderate** student ≈ 10 chats + 15 generations/week ≈ **$3–8 / month**.
A **heavy** student (active daily, exam season) ≈ **$10–25 / month**.

**Pricing target: $8.99 / month per user** (or $79/year). Assumes ~30%
cache-hit mix and medium effort; margin survives even at the heavy-user
edge, and daily caps make abuse impossible. If pilot data disagrees, the
price moves — that's why the pilot exists.

**Free quota for a paid tier:** e.g. 25 cloud answers/day + unlimited local
fallback, so caps degrade gracefully instead of "error: no money".

**Fixed costs:** gateway hosting $0 (Oracle Always-Free ARM VM or Cloudflare
Workers free tier — both cardless-account problems, see §5) to ~$5–10/mo
(latest-gen VPS). Anthropic is the only real variable.

---

## 3. The pilot (before any money changes hands)

Run on a parent-owned Anthropic account with a hard **$20/month spend cap**
(Anthropic supports spend limits + multiple workspace keys):

1. Deploy gateway on a VM (Oracle free tier or $5 VPS).
2. Hand signed gateway tokens to **5–10 classmates**, free.
3. The gateway logs per-user token spend from day one (this is the business's
   real dataset).
4. After 4 weeks: real $/user/month → set final price and caps.
5. Weekly review with parent: spend log + feedback; kill switch ready.

Budget: capped at $20/mo. Worst case we learn for $20.

---

## 4. Go-to-market

1. **Seed (school):** free via word-of-mouth, install the PWA, 30-second
   signup. Classmates need no card for the free tier — that's the wedge.
2. **Validate:** mistake-book streaks + syllabus progress show real usage
   without asking anyone.
3. **Convert:** Cloud Boost pitch exactly where the local brain is weakest
   (exam marking, essay feedback, hard Extension maths).
4. **Careful lane:** doesn't replace school rules — local mode works on
   school networks; cloud mode stays optional. Don't market inside class.

No ads paid for at any stage this year. The free tier is the marketing.

---

## 5. Legal & compliance (needs the parent-gatekeeper)

| Item | Reality | Fix |
|---|---|---|
| Anthropic API account | **18+** | Parent owns the account + card. |
| Payments (Stripe/PayPal) | **18+**, bank account | Parent owns until we're of age. |
| Business structure | ABN — free to register; **no GST under $75K turnover** | Sole trader under a parent; revisit at scale. |
| Privacy Act (AU) | Small-business exemption under $3M turnover — but users are kids | Behave as if regulated anyway (see below). |
| Minors' data + Claude | API inputs are **not** used for Anthropic training by default | Tell every parent exactly what leaves the device when Cloud Boost is on: chat text, documents they explicitly upload, marks/scores. Never: identity, location, other files. Delete-on-request supported (gateway keeps a usage ledger, not chat contents). |

Also required before paid launch: Terms of Use + a plain-English parent
consent page, refund rule (something simple, e.g. unused months refunded
on request), and a support email.

---

## 6. Product work needed (I can build most of this now, $0)

Now (no card, no parent needed):

- [x] **Gateway service** (FastAPI in `deploy/gateway/`): one upstream
  key in env, hashed user-token table, daily/monthly cost caps, per-token
  metering + spend ledger, model allowlist, kill switch; 18
  mocked-upstream e2e tests green (2026-10-19). The "batch of one queue"
  is *deliberately not built yet* — batched requests cost less but take
  ~1h, the wrong shape for interactive chat; revisit later.
- [ ] **ARIA client "cloud brain" toggle** (off by default): points at a
  gateway base URL + user token; falls back to local brain on any failure.
  The existing `ARIA_API_TOKEN` pattern, reused.
- [ ] Pricing/consent page skeleton.

Pilot phase (needs parent):
- [ ] Oracle/VPS deploy (the deploy/ folder exists; Docker-free Mac is no
  longer a blocker once a VM exists), real key, spend cap.
- [ ] Usage dashboard from the gateway's ledger.

Paid phase:
- [ ] Stripe (parent), $8.99/month automation, refund flow.

---

## 7. Honest risks

- **Anthropic changes prices or retires the model** → gateway is
  model-agnostic (it already bills per-token; swap `claude-sonnet-5-5` for
  whatever wins next, including a hosted open model). Cost model updates
  are a pricing page edit.
- **Free local models keep closing the gap** (qwen-class already strong) →
  our paid tier must stay a *real* gap: marking quality, long explanations.
  If it evaporates, the business dies — plan for it, don't pretend.
- **One user hammers the API** → daily caps + kill switch, enforced at the
  gateway before Anthropic sees the request.
- **School policy on AI tools** → free/local tier is the answer; never
  promote in class.
- **Nobody pays** → the free tier was always the product; the pilot costs
  $20 and answers the question.
- **Chargebacks / refund abuse** → month-to-month only, no annual lock-in
  until there's trust (and volume).

---

## 8. Milestones

| Phase | When | Gate to next phase |
|---|---|---|
| **0 — Build** (gateways, toggle, metering) | now | Mock-e2e green, docs done |
| **1 — Pilot** (5–10 users, $20 cap) | parent says go | Real cost/user + retention numbers from ledger |
| **2 — Charge** (Stripe, pricing page) | pilot + parent approval | 1 paying non-classmate |
| **3 — Grow** (school/region, 2nd model, support) | organic | Don't force it |

Rule for this plan the way the app is built: **local-first is the product,
cloud is premium — never the reverse.** If we ever have to make the free
tier bad to push Cloud Boost, we've lost the thing that made it worth doing.
