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
  tar -xzf "$TARBALL" -C "$APP_DIR"
else
  echo "No tarball given — expecting code already at $APP_DIR"
  echo "On your Mac: tar -czf aria.tar.gz -C ~/Projects/ARIA aria-2"
  echo "Then: scp aria.tar.gz ubuntu@<VM-IP>:/tmp/ && sudo $0 /tmp/aria.tar.gz"
  [[ -f "$APP_DIR/docker-compose.yml" ]] || { echo "No code found. Aborting."; exit 1; }
fi
cd "$APP_DIR/deploy"

# ── 4. Login password (basic-auth, stored as bcrypt hash) ────
echo "[4/6] Login protection..."
if [[ ! -f .env.deploy ]]; then
  read -rsp "Choose an ARIA login password: " PW; echo
  read -rsp "Repeat it: " PW2; echo
  [[ "$PW" == "$PW2" && -n "$PW" ]] || { echo "Passwords differ/empty. Aborting."; exit 1; }
  HASH=$(docker run --rm caddy:2-alpine caddy hash-password --plaintext "$PW")
  printf 'ADMIN_USER=student\nADMIN_HASH=%s\n' "$HASH" > .env.deploy
  chmod 600 .env.deploy
  echo "Login user: student (password set)."
else
  echo ".env.deploy exists — keeping existing password."
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
echo "✅ ARIA is live: http://<your-VM-public-IP>  (login: student)"
echo "Check health:  curl http://<your-VM-public-IP>/api/health"
echo "Logs:          cd $APP_DIR/deploy && docker compose logs -f backend"
echo ""
echo "Remaining manual step (Oracle console): VCN → subnet security list →"
echo "add Ingress rules for TCP 80 (and 22 for SSH) from 0.0.0.0/0."
echo ""
echo "WARNING: plain HTTP + password login. Fine on trusted networks, but"
echo "never reuse that password elsewhere. Expect slow answers: CPU-only 12B"
echo "inference on 4 Ampere cores is ~10x slower than your M4 Mac."
