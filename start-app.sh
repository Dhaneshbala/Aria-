#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  Study Buddy — production single-server start (what Study Buddy.app runs)
#  One process: FastAPI serves the API + the built UI on :8000.
#  Dev flow is untouched — keep using ./start.sh for hot-reload.
# ─────────────────────────────────────────────────────────────
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

GRN='\033[0;32m'; YLW='\033[1;33m'; RED='\033[0;31m'; BLU='\033[0;34m'; NC='\033[0m'

echo ""
echo -e "${BLU}  ╔════════════════════════════════════╗${NC}"
echo -e "${BLU}  ║   Study Buddy — AI Study Assistant (app)  ║${NC}"
echo -e "${BLU}  ╚════════════════════════════════════╝${NC}"
echo ""

# ── 1. Ollama ────────────────────────────────────────────────
if ! command -v ollama &>/dev/null; then
  echo -e "${RED}  ❌ Ollama not installed: https://ollama.com — install it, then reopen Study Buddy.${NC}"
  read -n 1 -s -r -p "  Press any key to close..."
  exit 1
fi
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
OLLAMA_URL="${OLLAMA_URL%/}"
if ! curl -sf "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
  echo "  Starting Ollama..."
  ollama serve >/dev/null 2>&1 &
  for i in {1..12}; do
    sleep 1
    curl -sf "$OLLAMA_URL/api/tags" >/dev/null 2>&1 && break
  done
fi
echo -e "${GRN}  ✅ Ollama running${NC}"

# ── 2. Models (skip surprises: only pull if missing) ─────────
INSTALLED=$(ollama list 2>/dev/null | awk 'NR>1{print $1}' | tr '\n' ' ')
for MODEL in "gemma4:e4b-mlx" "mxbai-embed-large"; do
  if echo "$INSTALLED" | grep -qF "${MODEL%%:*}"; then
    echo -e "${GRN}  ✅ $MODEL ready${NC}"
  else
    echo -e "${YLW}  ⬇  Pulling $MODEL (first run only)...${NC}"
    ollama pull "$MODEL"
  fi
done

# ── 3. Frontend build (only if dist is missing) ──────────────
if [[ ! -f "frontend/dist/index.html" ]]; then
  echo "  Building UI (one-time, ~1 min)..."
  cd frontend
  [[ -d node_modules ]] || npm ci --silent || npm install --silent
  npm run build --silent
  cd "$SCRIPT_DIR"
fi

# ── 4. Backend (single server, no reload) ────────────────────
PORT="${ARIA_PORT:-8000}"
cd "$SCRIPT_DIR/backend"
[[ -d "../.venv" ]] || python3 -m venv ../.venv
source "../.venv/bin/activate"
pip install -q -r requirements.txt || { echo -e "${RED}  ❌ pip install failed${NC}"; exit 1; }

echo "  Starting Study Buddy on http://127.0.0.1:$PORT ..."
python -m uvicorn main:app --host 127.0.0.1 --port "$PORT" --log-level warning &
BACKEND_PID=$!
for i in {1..15}; do
  sleep 1
  curl -sf http://127.0.0.1:$PORT/api/health >/dev/null 2>&1 && break
done

echo ""
echo -e "${GRN}  ✅ Study Buddy is ready — http://127.0.0.1:$PORT${NC}"
echo -e "  Close this window (or press Ctrl+C) to stop."
echo ""
open http://127.0.0.1:$PORT 2>/dev/null || true

trap "echo ''; echo 'Stopping Study Buddy...'; kill $BACKEND_PID 2>/dev/null; exit 0" INT TERM
wait $BACKEND_PID
