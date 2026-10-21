# Hosting ARIA on a public VM — launch guide

One Oracle "Always Free" Ampere ARM VM runs everything: Ollama (local AI),
the ARIA backend, and Caddy (web server). This is the deployment the
**Play Store track** builds on — an app in the Play catalogue still calls a
server; this document creates that server.

```
student browser / (later) Play Store app
        │  HTTPS  — per-student login sessions (accounts mode)
        ▼
        Caddy  :80/:443  ─── static frontend (built once at install)
        ▼
   backend (FastAPI)  ─── wallet, credits, admin, ledger (per-account)
        ▼
     Ollama  (qwen/gemma on CPU)  ← cloud AI stays OFF unless you consent
```

What is already true on this deployment:

- **accounts mode**: every `/api` call needs a login session; admins get
  step-up unlock for operator actions (`docs/OPERATIONS.md`).
- **wallet safety**: cloud calls refuse to run on an empty student wallet,
  so an unattended VM costs nothing unless you deliberately consent and
  grant credits.
- **agent tools disabled**: terminal/file tools reject non-localhost
  callers — effectively switched off on a VM, which is the safe posture.
- **no secrets in the repo**: real config lives in `.env.deploy`
  (gitignored; created from `.env.deploy.example`).
- **the model is gemma3:12b** on the VM (GGUF CPU build — the MLX build
  only runs on Apple Silicon, so the repo ships GGUF defaults).

**Honest expectations:** the VM is CPU-only — 12B-class answers take tens
of seconds, roughly 10x slower than the M4 Mac. Keep the Mac as the fast
daily driver; this box is the always-on copy the pilot relies on.

---

## 0. One-time external steps (browser + adult)

| What | Who | Cost |
|---|---|---|
| Oracle Cloud account (card-checked at signup; Always Free costs nothing) | adult | $0 |
| DuckDNS subdomain for HTTPS (10 min, §4) | adult | $0 |
| Google Play developer account — **later**, §7 | adult | ~US$25 once |

## 1. Create the VM (Oracle console)

1. **Networking → Virtual cloud networks** → your VCN → **Security list
   → Add ingress rules**: TCP `22`, `80`, `443` from `0.0.0.0/0`.
   (Caddy must reach port 80 for the HTTPS certificate handshake.)
2. **Create instance**: shape `VM.Standard.A1.Flex` — **4 OCPU / 24 GB RAM**
   (the Always-Free split; don't exceed it or billing starts), image
   **Ubuntu 24.04**, boot volume **100 GB**.
   - If the shape says **"out of capacity"** — Ampere free capacity comes
     and goes; retry later or on another home region.
3. Add your SSH public key, save the **public IP**.

## 2. Launch — from your Mac

```bash
cd ~/Projects/ARIA
tar -czf aria.tar.gz --exclude 'aria-2/.git' --exclude 'aria-2/.venv' \
    --exclude 'aria-2/venv' --exclude 'aria-2/frontend/node_modules' \
    --exclude 'aria-2/frontend/dist' --exclude 'aria-2/attic' aria-2
scp aria.tar.gz deploy/oracle-setup.sh ubuntu@<VM-IP>:/tmp/
ssh ubuntu@<VM-IP>
sudo bash /tmp/oracle-setup.sh /tmp/aria.tar.gz
```

The script installs Docker, opens the firewall (SSH + HTTP), deploys the
stack, builds the frontend once, pulls the AI models (~8 GB — slow; go do
something else), and writes `.env.deploy` from the example.

## 3. First-boot checklist (on the VM)

```bash
# the FIRST admin — never self-promoted in the app (accounts mode):
cd /opt/aria/deploy && docker compose exec backend \
    python -m tools.superadmin <username>     # prompts for a 10+ char password
```

- From any browser: open `http://<VM-IP>` → register a test student →
  sign in. Grant starter credits via **Admin → Credits** (students start
  at zero).
- `curl http://<VM-IP>/api/health` should be `"status": "ok"`.
- When the pilot group has signed up, close registration:
  edit `.env.deploy` → `ARIA_OPEN_REGISTRATION=0` → `docker compose up -d backend`.

## 4. HTTPS — do this before real students join

Passwords and chats must not cross the internet unencrypted. Caddy gets a
free Let's Encrypt certificate automatically — it only needs a domain name:

1. Sign up at **duckdns.org** (free), create e.g. `aria-family`, point it
   to the VM's public IP (on the DuckDNS page itself).
2. On the VM: `sudo ufw allow 443/tcp` (port rule already added in §1).
3. Edit `/opt/aria/deploy/.env.deploy` →
   `ARIA_TLS_DOMAIN=aria-family.duckdns.org` (remove the leading `#`).
4. `docker compose up -d caddy` — recreates with the new site address;
   Caddy fetches the certificate on first request.
5. Verify: `curl -s https://aria-family.duckdns.org/api/health`.

## 5. Day-to-day operations

| Task | How |
|---|---|
| Weekly backup (do set this up — it's the safety line) | `15 3 * * 1  cd /opt/aria/deploy && ./backup.sh >> backup.log 2>&1` (`crontab -e`). Keeps the newest 14 archives in `/opt/aria/backups/`. |
| Logs | `docker compose logs -f backend` |
| Restart the backend (e.g. after `.env.deploy` edits) | `docker compose up -d backend` |
| Upgrade the app | same tar+scp as §2, then `cd /opt/aria/deploy && docker compose build && docker compose up -d --build`. Data lives in named volumes and **survives upgrades**. |
| Close the pilot | `ARIA_OPEN_REGISTRATION=0` → `docker compose up -d backend` |
| Emergency stop | `docker compose down` (all data stays in volumes) |

## 6. Restore

The backup archive replaces the whole data volume (accounts, chats,
credits ledger, per-account stores). From `deploy/`:

```bash
docker cp ../backups/<archive>.tar.gz "$(docker compose ps -q backend)":/tmp/restore.tar.gz
docker compose stop backend
docker compose run --rm --entrypoint sh backend \
    -c "tar -xzf /tmp/restore.tar.gz -C /data"
docker compose start backend
```

## 7. Play Store track — honest status

| Piece | Status |
|---|---|
| Hosting (this guide) | ready — needs the Oracle account |
| Accounts, sessions, admin, credit wallet | **built** (Stages 1–2, on `main`) |
| Cloud (Claude) via the gateway — wallet-gated | built; gateway deployment documented in `deploy/gateway/` |
| Cloud consent on the VM | deliberately OFF until the pilot proves usage is sensible |
| Android app wrapper (Capacitor) | not started — needs a machine with the Android SDK; the web app already works in mobile browsers |
| Prepaid top-ups (Stripe / Play Billing) | **not built** — design in `docs/PAYMENTS_DESIGN.md`; will not be built without phase-gate approval (`docs/BUSINESS.md`) |

So the honest launch sequence for the store track is: **free-tier VM →
pilot on it (§3) → HTTPS (§4) → then the store wrapper**, with payments
staying behind the phase gate.
