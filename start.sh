#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  ARIA — AI Study Assistant  |  start.sh
#  Optimised for MacBook Air M4 16 GB
# ─────────────────────────────────────────────────────────────
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env so local settings (models, keys, hosts) apply to Ollama,
# backend and frontend below. Nothing here is committed (.env is gitignored).
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
  echo "  ✅ Loaded .env"
fi

# Colours
GRN='\033[0;32m'; YLW='\033[1;33m'; RED='\033[0;31m'; BLU='\033[0;34m'; NC='\033[0m'

echo ""
echo -e "${BLU}  ╔════════════════════════════════════╗${NC}"
echo -e "${BLU}  ║   ARIA — AI Study Assistant v2.0   ║${NC}"
echo -e "${BLU}  ╚════════════════════════════════════╝${NC}"
echo ""

# ── 1. Check macOS / Apple Silicon ───────────────────────────
ARCH=$(uname -m)
if [[ "$ARCH" == "arm64" ]]; then
  echo -e "${GRN}  ✅ Apple Silicon detected (M4) — Metal GPU will be used${NC}"
else
  echo -e "${YLW}  ℹ  Intel Mac detected — models will run on CPU${NC}"
fi

# ── 2. Check free disk space ──────────────────────────────────
FREE_GB=$(df -g "$HOME" | awk 'NR==2{print $4}')
echo -e "  💾 Free disk: ${FREE_GB} GB"
if (( FREE_GB < 8 )); then
  echo -e "${RED}  ❌ Need at least 8 GB free for AI models. Free up space first.${NC}"
  exit 1
fi

# ── 3. Check/start Ollama ─────────────────────────────────────
echo ""
echo "  [1/4] Checking Ollama..."
if ! command -v ollama &>/dev/null; then
  echo -e "${RED}  ❌ Ollama not installed.${NC}"
  echo "       Install it: https://ollama.com"
  echo "       Then re-run this script."
  exit 1
fi

OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
OLLAMA_URL="${OLLAMA_URL%/}"
if ! curl -sf "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
  echo "       Starting Ollama..."
  ollama serve >/dev/null 2>&1 &
  for i in {1..12}; do
    sleep 1
    curl -sf "$OLLAMA_URL/api/tags" >/dev/null 2>&1 && break
  done
fi
echo -e "${GRN}  ✅ Ollama running${NC}"

# ── 4. Pull models (16 GB optimised — single model + embedding) ───────
echo ""
echo "  [2/4] Checking AI models (16 GB optimised)..."

INSTALLED=$(ollama list 2>/dev/null | awk 'NR>1{print $1}' | tr '\n' ' ')

pull_if_missing() {
  local MODEL=$1 DESC=$2 SIZE=$3
  if echo "$INSTALLED" | grep -qF "${MODEL%%:*}"; then
    echo -e "${GRN}  ✅ $MODEL — already installed${NC}"
  else
    echo -e "${YLW}  ⬇  Pulling $MODEL ($DESC, $SIZE)...${NC}"
    ollama pull "$MODEL"
    echo -e "${GRN}  ✅ $MODEL ready${NC}"
  fi
}

# Main model — handles chat, reasoning, coding, math, vision/multimodal (all Study Tools via brain)
pull_if_missing "qwen3.5:9b"   "main model (multimodal, thinking)" "7.6 GB"

# Embedding model — ONLY for memory/RAG retrieval (tiny, not for generation)
pull_if_missing "nomic-embed-text" "embedding model" "274 MB"

echo ""
echo -e "  📊 Disk used by models: ~7.9 GB total (qwen3.5: 7.6 GB + nomic: 274 MB)"
echo -e "  🖥  RAM: Ollama loads ONE generation model at a time (M4 Metal GPU active)"
echo -e "  🧠 Main model handles vision + coding — no extra models needed"

# ── 5. Python backend ─────────────────────────────────────────
echo ""
echo "  [3/4] Starting Python backend..."
cd "$SCRIPT_DIR/backend"

# Single canonical venv at repo root /.venv (migrates old locations)
if [[ -d "../.venv" ]]; then
  source "../.venv/bin/activate"
  echo "       Using existing venv at ../.venv"
elif [[ -d "../venv" ]]; then
  echo "       Migrating ../venv → ../.venv"
  mv "../venv" "../.venv" 2>/dev/null || true
  source "../.venv/bin/activate"
elif [[ -d venv ]]; then
  echo "       Migrating backend/venv → ../.venv"
  mv venv "../.venv" 2>/dev/null || true
  source "../.venv/bin/activate"
else
  echo "       Creating virtual environment at ../.venv..."
  python3 -m venv ../.venv
  source ../.venv/bin/activate
fi

# Install deps with pip-compile style check — fail fast if broken
pip install -r requirements.txt || { echo -e "${RED}  ❌ pip install failed${NC}"; exit 1; }

# Ensure pdfminer is installed for better PDF text extraction
pip install -q pdfminer.six 2>/dev/null || true

echo "       Starting FastAPI on ${ARIA_HOST:-127.0.0.1}:${ARIA_PORT:-8000}..."
python -m uvicorn main:app --host "${ARIA_HOST:-127.0.0.1}" --port "${ARIA_PORT:-8000}" --reload \
  --log-level warning &
BACKEND_PID=$!

if [[ -n "${ARIA_LAN:-}" || "${ARIA_HOST:-127.0.0.1}" != "127.0.0.1" ]]; then
  echo -e "${YLW}  ⚠  LAN mode: backend reachable on your Wi-Fi network.${NC}"
  echo -e "${YLW}     Agent terminal/file tools stay loopback-only; use trusted Wi-Fi only.${NC}"
fi

# Wait up to 15s for backend
_HEALTH_HOST="127.0.0.1"
_HEALTH_PORT="${ARIA_PORT:-8000}"
for i in {1..15}; do
  sleep 1
  curl -sf "http://${_HEALTH_HOST}:${_HEALTH_PORT}/api/health" >/dev/null 2>&1 && break
done
echo -e "${GRN}  ✅ Backend ready (PID $BACKEND_PID)${NC}"

# ── 6. Frontend ───────────────────────────────────────────────
echo ""
echo "  [4/4] Starting frontend..."
cd "$SCRIPT_DIR/frontend"

if [[ ! -d node_modules ]]; then
  echo "       Installing npm packages (first run only, ~30 seconds)..."
  npm ci --silent || npm install --silent
else
  # Verify lockfile integrity on subsequent runs
  npm ci --silent 2>/dev/null || true
fi

if [[ -n "${ARIA_LAN:-}" ]]; then
  echo "       LAN mode: frontend reachable on your Wi-Fi network."
  npm run dev -- --host &
else
  npm run dev &
fi
FRONTEND_PID=$!
sleep 3

# ── Done ──────────────────────────────────────────────────────
echo ""
echo -e "${GRN}  ╔════════════════════════════════════╗${NC}"
echo -e "${GRN}  ║  ✅ ARIA is ready!                  ║${NC}"
echo -e "${GRN}  ║                                     ║${NC}"
echo -e "${GRN}  ║  Open: http://localhost:5173         ║${NC}"
echo -e "${GRN}  ║                                     ║${NC}"
echo -e "${GRN}  ║  Press Ctrl+C to stop               ║${NC}"
echo -e "${GRN}  ╚════════════════════════════════════╝${NC}"
echo ""
echo -e "  Models loaded: qwen3.5:9b (main, multimodal) + nomic-embed-text (embeddings)"
echo -e "  Image gen:     Pollinations.ai (free, no GPU needed)"
echo -e "  Memory/RAG:    ChromaDB + nomic-embed-text saved to ~/.aria_data/"
echo ""
if command -v tailscale &>/dev/null; then
  echo -e "  📱 Remote access (no Cloudflare): run this once, then open the URL on your phone anywhere:"
  echo -e "     tailscale serve --bg 5173"
  echo ""
fi

# Open browser automatically
sleep 1
open http://localhost:5173 2>/dev/null || true

# Keep running until Ctrl+C
trap "echo ''; echo 'Stopping ARIA...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait $BACKEND_PID $FRONTEND_PID
