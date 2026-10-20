# ARIA pilot operations runbook (Section 13)

Field guide for running the ARIA pilot from the current family-local
setup to a small shared-server pilot. Every step here is already
implemented and tested; nothing in this document requires new code.
Where something is deliberately not built (card payments), it is said
so.

## 0. Vocabulary

- **local mode** — today's single-user behaviour. Everything works with
  no sign-in; all data attributes to the built-in `local-owner`
  account. The default.
- **accounts mode** — `ARIA_AUTH_MODE=accounts`: every `/api` call needs
  a bearer session; new sign-ups are students; admins run operator
  tools. Each account's data (chats, usage, todos, mistakes, exam
  plans, maths progress, study profile, notebooks, knowledge base,
  caches) is isolated in its own store directory.
- **step-up** — admin mutations need a password re-verification inside
  the previous 15 minutes (`POST /api/auth/admin/unlock`); the frontend
  prompts for it automatically.

## 1. Before enabling accounts mode

1. Finish validating the family-local app in local mode first. Local
   mode must stay the default: it is the product even when the pilot
   runs accounts.
2. Take a backup (Admin → backups, or `POST /api/backup/create`).
   The first accounts-mode boot migrates every legacy store into the
   first human admin's account — nothing is deleted, and the backup is
   the safety line anyway.
3. Review `.env.example` fully: bind host, CORS origins (only your own
   origins — never `*`), and any cloud settings.

## 2. Enabling accounts mode for the pilot

```bash
# in .env (server)
ARIA_AUTH_MODE=accounts
ARIA_OPEN_REGISTRATION=1   # open while the pilot group signs up
```

Then create the FIRST admin via the CLI (never promote via the app —
role changes are superadmin-only and there is no self-promotion):

```bash
cd backend && ../.venv/bin/python -m tools.superadmin <username>
# prompts for a 10+ character password; safe to re-run for updates
```

Boot the app. On this first boot:

- Stage-1 tables are created (users, sessions, audit, ledger, budget,
  feedback);
- legacy conversations become the first admin's chats;
- legacy stores (todos/mistakes/exam plans/maths/profile/notebooks/KB
  files/caches) move into the first admin's user directory;
- the built-in `local-owner` account exists but cannot be signed into
  and never receives migrated data.

First admin sign-in: the admin unlocks with
`POST /api/auth/admin/unlock` (the frontend shows the step-up modal
automatically when performing an admin change).

## 3. Day-to-day pilot operations

- **Who is in?** Admin → Users: registrations, roles, plans, status.
  Students cannot promote themselves; promote only via another
  superadmin (or the CLI above for the bootstrap).
- **Starting credits**: Admin → Credits → apply an amount to a user id.
  Entry types: grant (provided free), payment (money you received and
  verified outside ARIA — bank transfer/cash; charging cards is NOT
  implemented), adjustment/refund for corrections. Every change is
  written to the credit ledger with reason + actor and is audited.
- **Wallet behaviour**: students with no credit simply can't use cloud
  models (`anthropic:…`) — local models stay free, always.
  Superadmins are exempt from the wallet check.
- **Budget**: Admin → budget caps global daily cloud spend before any
  dispatch. Leave it small for the pilot.
- **Monitoring**: Admin → Overview (real aggregates only), audit trail
  (hash-chained — verify it on the server from time to time), per-user
  usage. Telemetry (if enabled) is stored locally and admin-visible
  only, with the acting account recorded.
- **Operator tools**: system diagnostics/logs, backups and the agent
  (terminal/file tools) are admin-only in accounts mode — students get
  a clean 403 that is audited.
- **End of sign-up window**: set `ARIA_OPEN_REGISTRATION=0` (or delete
  it) and restart. Late arrivals are added by the admin, if ever.

## 4. Phones (Android)

The app installs as a PWA (browser → install). No Play Store billing,
no data-safety paperwork exists — see docs/KNOWN_LIMITATIONS.md. For a
pilot that's fine: browser-install each student's phone.

## 5. When something breaks

- 401 everywhere → session expired; sign in again (the frontend flags
  it and shows the login screen).
- `admin_locked` → run the step-up (the modal does it);
- Ollama down → only local answers die; cloud still works if enabled.
- Anything data-related: restore from a backup zip (Admin → backups →
  restore), which includes conversations, per-user stores, notebooks
  and the knowledge base.

## 6. Honest boundaries (do not promise these)

- No card payments of any kind — Stripe/Play Billing are deliberately
  not implemented. Manual `payment` records are bookkeeping only.
- `config.json` settings (model choice, cloud consent) are global
  operator settings shared by the whole pilot, by design.
- Cloud costs are measured twice on purpose: the gateway meters the
  operator's real spend; each student's wallet debits their prepaid
  credit. Keep the two reports separate when you reconcile.
