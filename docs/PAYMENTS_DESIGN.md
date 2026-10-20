# Phase 2 — Charge: Stripe top-up design

Status: **design only — approved by nobody yet, built by nobody yet.**
Gate to build: pilot finished (real numbers from `docs/BUSINESS.md` §7)
+ parent approves + a Stripe account exists on the parent's card.
Until all three, ARIA keeps saying plainly in the UI that card payments
are not implemented.

Owner: Dhanesh (Year 9) · Adult-of-record for the Stripe account: a
parent/guardian (Stripe requires 18+; see `docs/BUSINESS.md` §5).

---

## 1. Summary

Milestone 2 charges money for the first time. The recommended shape for
the first paid phase is **prepaid wallet top-ups** — not monthly
subscriptions:

- The entire credit plumbing already exists and is audited: microdollar
  ledger, sole-mutator `credits.apply()`, the allowed `payment` kind
  (added in Stage 2 for *manually* verified top-ups), wallet precheck on
  every cloud dispatch, hash-chained audit trail.
- A top-up is a one-time Stripe Checkout payment; the webhook turns the
  Stripe truth into ledger truth. One webhook handler, no Stripe
  Billing objects to reconcile.
- Subscriptions ($8.99/month per the plan) remain a **later extension**:
  they need Stripe Billing (customers, subscriptions, proration, portal)
  and are worth building only once the pilot proves people actually pay
  a second and third time.

The decision the pilot answers: does anyone repay? Build subscriptions
after, and only after, that answer is yes.

## 2. What already ships (and is the reason this design is small)

| Piece | Where | Role in payments |
|---|---|---|
| Microdollar ledger, integer-only | `backend/services/credits.py` | The single place balances move (`payment` kind already legal, positive-only) |
| Wallet precheck | `services/ai_providers.py:` `_cloud_precheck` | Students with credit can spend it; the wallet check needs no changes for top-ups |
| Audit chain | `services/audit.py` | Every payment gets an audited entry, like grants today |
| Gateway metering | `deploy/gateway/` | Operator cost stays metered separately (dollar floats); never merged with the wallet |
| Manual `payment` records | Admin Credits tab | Stays supported forever — bank transfer/cash remains a valid channel |
| Wallet page (honest labels) | `frontend/src/pages/WalletPage.jsx` | Gains a "Top up" button **only** when payments are enabled |

## 3. Money boundaries (get this wrong and the books lie)

- **Stripe speaks cents.** Our ledger speaks thousandths-of-a-cent
  (microdollars) — `$1 = 1_000_000` micro.
  Conversion is exact integer arithmetic: `micro = cents × 10_000`.
  `$8.99` → `899` cents → `8_990_000` micro. Never floats, never round.
- Stripe's *fee* is a separate fact Stripe reports; ARIA records the
  **gross credited amount** in the ledger and never invents a fee number.
- Currency: `aud` throughout (Stripe account country = AU).

- Price of packs is **configuration, not code**: env-driven list, e.g.
  `ARIA_TOPUP_PACKS=[{"aud":10},{"aud":25},{"aud":50}]`. The exact
  amounts are the parent's call; suggested starter **$10 / $25 / $50**,
  with **no expiry** on credited amounts (decide explicitly together).

## 4. Flow (the whole system)

```
student (signed in)
  │ 1. Wallet → Top up $10
  ▼
POST /api/payments/checkout {pack: "10"}          (accounts mode only)
  │ backend: create stripe_orders row (status=pending)
  │ backend: Stripe Checkout Session (client_reference_id = order id,
  │          metadata {aria_user_id, order_id}, amount cents, aud)
  ▼ 2. redirect to Stripe-hosted checkout             (card data: Stripe only)
  │
  ├── success_url → /wallet?topup=done (page shows "pending confirmation")
  │
  ▼ 3. Stripe → POST /api/payments/stripe/webhook      (open prefix,
  │        signature-verified; ONLY this endpoint is ever open)
  │
  │    checkout.session.completed:
  │      - verify signature (ConstantCompare, stripe lib)
  │      - INSERT event_id first (unique) → duplicate webhook = no-op
  │      - transaction: credits.apply(user, cents×10_000,
  │               kind="payment", reason="stripe: order #<id>")
  │      - orders row → status=paid, store payment_intent id
  │
  ▼ 4. wallet page reflects the new balance (poll on focus)
```

Rules that make the flow safe:

1. **The redirect never grants credit** — only the verified webhook can.
   A cancelled tab, a lost phone, a faked success URL cannot spend.
2. **Event id first.** Stripe delivers webhooks at-least-once; the
   unique-event insert guarantees a redelivery can never double-credit
   (the ledger apply is already transactional).
3. **No card data, ever, on our server.** Checkout is Stripe-hosted;
   the backend holds a `payment_intent` id and nothing else. PCI scope
   stays at "SAQ A" minimal.
4. **Kill switch** — `ARIA_PAYMENTS_ENABLED=0` (default) makes every
   payments endpoint 404-style "not implemented", folders closed, UI
   label stays honest. The switch exists for a mid-run stop (dispute,
   key rotation, mistake).

## 5. Data model (new table)

`backend/services/payments_service.py` owns it, mirroring credits.py's
style (explicit SQL, no ORM):

```
CREATE TABLE IF NOT EXISTS stripe_orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id  INTEGER NOT NULL REFERENCES users(id),
  pack_name    TEXT NOT NULL,
  amount_cents INTEGER NOT NULL,          -- gross, Stripe side
  currency     TEXT NOT NULL,             -- 'aud'
  session_id       TEXT UNIQUE,           -- cs_live_…
  payment_intent   TEXT,                  -- set when paid
  event_id         TEXT UNIQUE,           -- idempotency anchor
  status   TEXT NOT NULL DEFAULT 'pending',  -- pending|paid|refunded|cancelled
  created_at TEXT NOT NULL,
  paid_at    TEXT
);
```

Refunds are a **manual operator action by design** (see §7): the orders
row flips to `refunded` and an `adjustment` ledger entry reverses the
wallet with a reason — never silently automatic.

## 6. Endpoints (to be built, listed honestly)

| Method | Path | Auth | Behaviour |
|---|---|---|---|
| POST | `/api/payments/checkout` | session (student+) | Create order + Checkout session; rate-limit-owned |
| GET | `/api/payments/orders` | session | Own orders only (never another account's) |
| POST | `/api/payments/stripe/webhook` | **open prefix** | Signature-verified ingest; the one open doorway, deliberately |
| GET | `/api/v2/admin/payments/orders` | admin + step-up (mutations) | All orders, real numbers only |

The gate's open-prefix list gains the webhook path **only when**
`ARIA_PAYMENTS_ENABLED=1`; signatures verified in the handler before any
data touches the ledger.

## 7. Refunds, disputes, abuse

- **Refund policy (parent wording, proposed):** unused credit on a
  top-up refunded on request within the first month; refund = operator
  action with an audited `adjustment` ledger row; wallet may go to a
  floor of 0 rather than negative.
- **Dispute/chargeback webhook** (`charge.dispute.created`): flip the
  account to a `funds_held` flag (blocks further cloud dispatch), audit,
  notify the admin console. **Never auto-spend or auto-refund.**
- **Redelivery storm**: idempotent by event id (§4). No other state is
  reversible by a webhook.
- Test-mode money (Stripe test cards) can never mix with live: the key
  prefix determines the mode, and test keys only ever produce test
  events against test-mode orders. Nothing reconciles across the line.

## 8. Configuration (all env, nothing secret in code or repo)

```
ARIA_PAYMENTS_ENABLED=0          # master switch, default off
ARIA_STRIPE_SECRET_KEY=sk_live_… # parent's account, never in git (gitleaks hooks exist)
ARIA_STRIPE_WEBHOOK_SECRET=whsec_…
ARIA_TOPUP_PACKS=[{"usd":10},{"usd":25},{"usd":50}]
```

Local development runs the real flow in Stripe **test mode** against
`stripe listen --forward-to …` (Stripe CLI) before any live key exists.
The gateway's own `.env` discipline (never a shared secret between
services) applies unchanged; ARIA and Stripe exchange nothing but
session ids and amounts.

## 9. Acceptance gates before live money (none optional)

1. Mocked-Stripe (respx) e2e: checkout create → webhook paid → ledger
   +audit +order correct, per the flows charted in §4.
2. **Duplicate event** redelivery → exactly one ledger row (the test
   proves the unique insert blocks a second credit).
3. **Tampered/absent signature** → 400, nothing written.
4. **Session expired / abandoned** → order stays pending, usable wallet
   unchanged, no ledger row.
5. **Refund flow** → balance reduced, order `refunded`, audit entry.
6. Kill switch on → all payments endpoints respond "not implemented",
   wallet page keeps today's honest labels.
7. The free/local tier remains untouched by any of it — the wedge in
   `docs/BUSINESS.md` §4 must not degrade to push payments.

## 10. Subscriptions — later extension sketch (NOT milestone 2)

- Stripe Billing: customer per user (parent-owned account),
  $8.99/month or $79/year per the plan, monthly soft allowance
  (e.g. 25 cloud answers/day free quota → wallet overage optional —
  the exact number comes from pilot data, decided then).
- Local mode untouched: free tier has no account and no card, forever.
- Requires the Terms-of-Use + parent-consent page from
  `docs/BUSINESS.md` §5 — both are pre-launch blockers for any paid
  tier, subscription or not.

## 11. What this design deliberately does NOT cover

- Any guessing of Stripe fee percentages (confirm on the account itself).
- Tax/GST positioning — turnover threshold conversation belongs with the
  parent's accountant, not in code.
- In-app store billing (Apple/Google) — the PWA install path avoids
  commission for the pilot; Play Billing is a separate milestone with
  its own data-safety work.
- Crypto, gift cards, anything clever.

## 12. Build order when the gate opens (parent-approved)

1. `payments_service.py` + migration + table (§5)
2. Checkout + webhook endpoints + gate wiring (§6)
3. Wallet "Top up" UI behind the flag; admin orders tab (real-only)
4. Full test-mode runbook with the Stripe CLI; acceptance suite green
5. Parent funding the first live top-up themselves and refunding it —
   the family's own card is test subject zero.
6. Then, and only then, offer the button to pilot users.
