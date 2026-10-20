# Attic

Superseded drafts kept for reference — none are imported by the app.

- `services/auth_service.py` + `services/userctx.py` + `models/store.py`:
  an earlier per-user-directory multi-user approach (`ARIA_MULTIUSER`).
  Section 13 replaced it with session accounts (`ARIA_AUTH_MODE=accounts`,
  roles via `ARIA_MULTIUSER`-free gate/credits/ledger). Delete them if
  nobody wants them back; they must NOT be reintroduced without review
  because they pre-date the step-up/audit model.
