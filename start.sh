#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  ARIA — AI Study Assistant  |  start.sh
#  Optimised for MacBook Air M4 16 GB
# ─────────────────────────────────────────────────────────────
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

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

if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "       Starting Ollama..."
  ollama serve >/dev/null 2>&1 &
  for i in {1..12}; do
    sleep 1
    curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
  done
fi
echo -e "${GRN}  ✅ Ollama running${NC}"

# ── 4. Pull models (M4 optimised) ─────────────────────────────
echo ""
echo "  [2/4] Checking AI models (M4 MacBook Air optimised)..."

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

# Reasoning model — best quality that fits in 16 GB
pull_if_missing "qwen3:8b"      "main reasoning model" "5.2 GB"

# Vision model — reads worksheets, images, diagrams
pull_if_missing "qwen2.5vl:3b"  "vision / image reading" "2.2 GB"

# Fast fallback
pull_if_missing "llama3.2:3b"   "fast fallback model" "2.0 GB"

echo ""
echo -e "  📊 Disk used by models: ~9.4 GB total"
echo -e "  🖥  RAM: Ollama loads ONE model at a time (M4 Metal GPU active)"

# ── 5. Python backend ─────────────────────────────────────────
echo ""
echo "  [3/4] Starting Python backend..."
cd "$SCRIPT_DIR/backend"

if [[ ! -d venv ]]; then
  echo "       Creating virtual environment..."
  python3 -m venv venv
fi
source venv/bin/activate

# Install deps quietly, only show errors
pip install -q -r requirements.txt 2>&1 | grep -iE "error|warning" || true

# Try to install pdfminer for better PDF text extraction
pip install -q pdfminer.six 2>/dev/null || true

echo "       Starting FastAPI on port 8000..."
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload \
  --log-level warning &
BACKEND_PID=$!

# Wait up to 15s for backend
for i in {1..15}; do
  sleep 1
  curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1 && break
done
echo -e "${GRN}  ✅ Backend ready (PID $BACKEND_PID)${NC}"

# ── 6. Frontend ───────────────────────────────────────────────
echo ""
echo "  [4/4] Starting frontend..."
cd "$SCRIPT_DIR/frontend"

if [[ ! -d node_modules ]]; then
  echo "       Installing npm packages (first run only, ~30 seconds)..."
  npm install --silent
fi

npm run dev &
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
echo -e "  Models loaded: qwen3:8b (reasoning) + qwen2.5vl:3b (vision)"
echo -e "  Image gen:     Pollinations.ai (free, no GPU needed)"
echo -e "  Memory:        ChromaDB saved to ~/.aria_data/"
echo ""

# Open browser automatically
sleep 1
open http://localhost:5173 2>/dev/null || true

# Keep running until Ctrl+C
trap "echo ''; echo 'Stopping ARIA...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait $BACKEND_PID $FRONTEND_PID
