#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  ARIA — Oracle Always Free setup (run ONCE on the VM)
#  Target: VM.Standard.A1.Flex, 4 OCPU, 24 GB RAM, Ubuntu 24.04
# ─────────────────────────────────────────────────────────────
set -e
APP_DIR=/opt/aria
TARBALL="${1:-}"

if [[ "$(uname -m)" != "aarch64" ]]; then
  echo "Refusing: this deploy targets ARM (Ampere A1). uname -m = $(uname -m)"
  exit 1
fi

if [[ $EUID -ne 0 ]]; then
  echo "Run as root (or with sudo): sudo $0 [aria.tar.gz]"
  exit 1
fi

# ── 1. Docker ────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo "[1/6] Installing Docker..."
  apt-get update -qq
  apt-get install -y -qq docker.io docker-compose-plugin ufw
  systemctl enable --now docker
else
  echo "[1/6] Docker already installed."
fi

# ── 2. Firewall: SSH + HTTP only ─────────────────────────────
echo "[2/6] Configuring firewall (22 + 80 only)..."
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw --force enable

# ── 3. App code ──────────────────────────────────────────────
echo "[3/6] Installing app code to $APP_DIR..."
mkdir -p "$APP_DIR"
if [[ -n "$TARBALL" && -f "$TARBALL" ]]; then
  # The tarball contains a top-level aria-2/ dir; flatten it into $APP_DIR.
  tar -xzf "$TARBALL" --strip-components=1 -C "$APP_DIR"
else
  echo "No tarball given — expecting code already at $APP_DIR"
  echo "On your Mac (copy-paste):"
  echo "  cd ~/Projects/ARIA"
  echo "  tar -czf aria.tar.gz --exclude 'aria-2/.git' --exclude 'aria-2/.venv' \\"
  echo "      --exclude 'aria-2/venv' --exclude 'aria-2/frontend/node_modules' \\"
  echo "      --exclude 'aria-2/frontend/dist' --exclude 'aria-2/attic' aria-2"
  echo "Then: scp aria.tar.gz deploy/oracle-setup.sh ubuntu@<VM-IP>:/tmp/"
  echo "      ssh ubuntu@<VM-IP> && sudo bash /tmp/oracle-setup.sh /tmp/aria.tar.gz"
  [[ -f "$APP_DIR/docker-compose.yml" ]] || { echo "No code found. Aborting."; exit 1; }
fi
cd "$APP_DIR/deploy"

# ── 4. Deployment config (.env.deploy — auth mode, registration, models) ──
echo "[4/6] Deployment config..."
if [[ ! -f .env.deploy ]]; then
  cp .env.deploy.example .env.deploy
  chmod 600 .env.deploy
  echo "Wrote .env.deploy from the example (accounts mode, open registration,"
  echo "model names). Review it any time: nano $APP_DIR/deploy/.env.deploy"
else
  echo ".env.deploy exists — keeping existing config."
fi

# ── 5. Build + start ─────────────────────────────────────────
echo "[5/6] Building images (takes several minutes on first run)..."
docker compose build
docker compose up -d ollama backend
docker compose up frontend-build  # exits after building the PWA
docker compose up -d caddy

# ── 6. Pull AI models (slow on CPU box — go make lunch) ──────
echo "[6/6] Pulling models: qwen3.5:9b (~8 GB) + nomic-embed-text..."
docker compose exec ollama ollama pull qwen3.5:9b
docker compose exec ollama ollama pull nomic-embed-text

echo ""
echo "✅ ARIA is live: http://<your-VM-public-IP>"
echo ""
echo "Next: create the FIRST admin (inside the VM — never via the app UI):"
echo "  cd $APP_DIR/deploy && docker compose exec backend python -m tools.superadmin <username>"
echo "(prompts for a 10+ character password; then students can sign up at the URL above)"
echo ""
echo "Check health:  curl http://<your-VM-public-IP>/api/health"
echo "Logs:          cd $APP_DIR/deploy && docker compose logs -f backend"
echo ""
echo "Remaining manual step (Oracle console): VCN → subnet security list →"
echo "add Ingress rules for TCP 80 (and 22 for SSH) from 0.0.0.0/0."
echo ""
echo "WARNING: plain HTTP. OK for a same-house try-out; before real students"
echo "join, do the HTTPS step — deploy/README.md §HTTPS (free domain + TLS)."
echo ""
echo "Expect slow answers: CPU-only 12B inference on 4 Ampere cores is"
echo "~10x slower than your M4 Mac."
