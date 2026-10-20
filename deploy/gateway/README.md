# ARIA Gateway — Cloud Boost proxy

Phase 0 of `docs/BUSINESS.md`: one Anthropic API key lives here, on the
server, and never ships anywhere. Users (pilot: 5–10 classmates) get
**gateway tokens** (`gw_…`), not keys. Every dollar is checked here,
**before** Anthropic sees the request, and metered into a per-token
ledger.

    user's ARIA ──▶ GATEWAY (1 Anthropic key, hashed tokens, cost caps)
                       │ validate → quota left? → meter usage → Claude
                       └ daily/monthly caps · spend log · kill switch

> Status: **built and mock-e2e-tested**, not yet deployed and not yet
> wired into the ARIA client (the "Cloud Boost" toggle is the next Phase
> 0 item). No real key is stored in this repo.

## Quickstart (on any machine, no key required to see the UI)

```bash
GATEWAY_ADMIN_TOKEN=admin-secret ANTHROPIC_API_KEY=sk-ant-... \
  ../.venv/bin/python -m uvicorn --app-dir deploy gateway.main:app --port 8088
```

Test it: `curl localhost:8088/health`.

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `GATEWAY_ADMIN_TOKEN` | none (admin disabled) | Bearer token for `/admin/*` — create/revoke tokens, check spend, kill switch |
| `ANTHROPIC_API_KEY` | none | The single upstream key. `/v1/messages` refuses to work without it |
| `GATEWAY_DB_PATH` | `~/.aria_gateway/gateway.sqlite3` | SQLite ledger (WAL mode) |
| `GATEWAY_MODEL_ALLOWLIST` | `claude-sonnet-5-5` | Models users may request (comma-separated) |
| `GATEWAY_DEFAULT_DAILY_CAP_USD` | `0.50` | Per-token daily cost cap unless overridden at creation |
| `GATEWAY_DEFAULT_MONTHLY_CAP_USD` | `10.00` | Per-token monthly cost cap unless overridden at creation |
| `GATEWAY_MAX_TOKENS_LIMIT` | `8192` | Hard clamp on a request's `max_tokens` (bounds cap overshoot from parallel bursts) |
| `GATEWAY_UPSTREAM_BASE_URL` | `https://api.anthropic.com` | Only for staging/mocks |

Caps are **cost** caps in USD (metered from real usage blocks, not
estimates). Requests beyond a cap get `429` — they are *refused*, never
racked up silently.

## Endpoints

| Route | Auth | What |
|---|---|---|
| `GET /health` | none | Liveness + allowlist + kill-switch state |
| `POST /v1/messages` | `Bearer gw_…` | Anthropic Messages API proxy (streaming + non-streaming) |
| `GET /v1/usage` | `Bearer gw_…` | This token's day/month spend and remaining caps |
| `POST /admin/tokens` | admin | `{label, daily_cap_usd?, monthly_cap_usd?}` → `201 {id, token (shown ONCE), …}` |
| `GET /admin/tokens` | admin | Token list incl. per-token day/month spend |
| `PATCH /admin/tokens/{id}` | admin | `{is_active?, daily_cap_usd?, monthly_cap_usd?, label?}` — revoke or re-cap |
| `GET /admin/usage` | admin | Ledger: today/month totals, per-token spend, last 30 days |
| `GET/POST /admin/kill` | admin | Inspect / flip the kill switch (persisted in SQLite; survives restarts) |

Admin session, typical pilot flow:

```bash
ADMIN="Authorization: Bearer admin-secret"  # must match GATEWAY_ADMIN_TOKEN

# 1. Mint a token for a classmate ($0.50/day, $10/month by default).
curl -X POST localhost:8088/admin/tokens \
  -H "$ADMIN" \
  -H "Content-Type: application/json" \
  -d '{"label":"year9-geography"}'
# → {"id":1,"token":"gw_…","label":"year9-geography",…}   ← copy gw_… now

# 2. The classmate's ARIA points at this gateway with that token.

# 3. Watch spend (the business's real dataset).
curl -H "$ADMIN" localhost:8088/admin/usage

# 4. Panic button — instantly refuse all cloud answers:
curl -X POST -H "$ADMIN" \
  -H "Content-Type: application/json" \
  -d '{"on":true}' localhost:8088/admin/kill
```

## Cost model (verified, per model)

USD/MTok — verified against the Claude docs (2026-10): the same table as
`backend/config/pricing.py`. Cache **reads** bill at a per-model
fraction of input (Sonnet 5.5 & Opus 5.5: 0.05×, Fable 5.1: 0.025×,
others 0.1×); cache **writes** bill at 1.25× (5-min TTL; the 1-hour TTL
is never requested). `estimate_cost` in `config.py` is the only place
this math lives.

> Before charging anyone: at least one source reports Sonnet 5's $2
> input as **introductory pricing**. Re-verify prices and refresh
> `MODEL_PRICES` — the milestone plan already says pilot data decides
> the final price.

## Honest limitations

- **Parallel bursts can overshoot a cap slightly.** Two concurrent
  requests can both pass the pre-check; the overshoot is bounded by the
  `max_tokens` clamp. The Anthropic-side spending limit is the hard
  backstop — set it when you create the Console account.
- **Manual calendar kill**: caps are UTC day/month windows.
- **Truncated streams undercount output tokens.** If a client drops
  mid-answer, input-side spend is still metered in full (that's when
  the spend happens); the final output count may be missed.
- **No rate limiting yet** — fine for 5–10 known users; add before any
  public signup.
- **One SQLite file.** Perfect for the pilot on one small VM; migrate to
  Postgres-style storage only when the ledger grows past one disk's
  worth of nonsense.
- **Prompt-caching multipliers are config, not law** — Anthropic has
  changed read factors before (0.1× → 0.05× on the 5.5 family); the
  ledger re-reads them from `MODEL_PRICES`, not from anywhere else.

## Deploying (pilot phase — needs a parent-gatekeeper decision)

The gateway is a separate service from the family's self-host ARIA box
(`deploy/docker-compose.yml` puts ARIA behind a basic-auth screen; the
gateway must be token-reachable, so it does **not** go there). At pilot
time, deploy it on any small VM:

```yaml
# pilot compose (only when actually deploying)
services:
  gateway:
    build:
      context: ..
      dockerfile: deploy/Dockerfile.gateway   # to add at pilot time
    environment:
      GATEWAY_ADMIN_TOKEN: <set>
      ANTHROPIC_API_KEY: <set>
      GATEWAY_DB_PATH: /data/gateway.sqlite3
    volumes:
      - gateway_data:/data
```

Behind Caddy, give it its own route **without** the global basic-auth
(e.g. `gw.yourdomain.tld` or a `handle /gw/*` path, with TLS). Only
expose it publicly when the kill switch and the Anthropic spend limit
are both live.

## Tests

```bash
.venv/bin/python -m pytest deploy/gateway/tests -q
```

18 tests, all against a mocked Anthropic via respx — the Phase 0 gate in
`docs/BUSINESS.md` ("Mock-e2e green"). CI runs the same suite.

## ARIA backend integration (Section 13 Stage 2)

Setting `ARIA_GATEWAY_URL` + `ARIA_GATEWAY_TOKEN` in the ARIA backend
routes **all** Anthropic traffic through the gateway instead of
`api.anthropic.com` — the backend carries only its own `gw_` token,
never a real API key. Cloud consent (`ARIA_CLOUD_CONSENT=1`) is still
required. Two ledgers stay deliberately separate: the gateway meters
real operator cost in dollar floats; the ARIA wallet (microdollars)
debts each student's prepaid credit. Also note `/v1/usage` and the
admin endpoints are the operator's — ARIA never calls them.
