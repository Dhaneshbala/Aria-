#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  ARIA File Organizer — LoRA fine-tune (MLX-LM on Apple Silicon M4)
#
#  Trains a small LoRA adapter on the 100-example organizer dataset so
#  Ollama gets measurably better at renaming + filing documents and images.
#
#  Pipeline:
#    1. generate the dataset (scripts/make_organizer_dataset.py)
#    2. train a LoRA adapter with mlx-lm (Apple's MLX framework)
#    3. fuse the adapter into the base model
#    4. convert to GGUF and register as an Ollama model "organizer-3b"
#    5. point ARIA's File Organizer at it (organizer_model config)
#
#  Expected time on a MacBook Air M4 16 GB: roughly 2-5 hours for 400 iters.
#  You can stop and re-run later — adapters are saved every 100 iters.
#
#  Run from anywhere:
#      ./backend/scripts/finetune_organizer.sh
#  Options:
#      ./backend/scripts/finetune_organizer.sh --iters 200 --base Qwen/Qwen2.5-3B-Instruct
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BACKEND_DIR"

BASE_MODEL="Qwen/Qwen2.5-3B-Instruct"     # 3B fits 16 GB M4 for LoRA training
ITERS=400
STORE_DIR="storage/finetune"
ADAPTER_DIR="$STORE_DIR/adapters"
FUSED_DIR="$STORE_DIR/organizer-3b-mlx"
GGUF_OUT="$STORE_DIR/organizer-3b.gguf"
MLX_VENV="$STORE_DIR/.venv-mlx"
OLLAMA_MODEL_NAME="organizer-3b"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --iters)   ITERS="$2"; shift 2 ;;
    --base)    BASE_MODEL="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

mkdir -p "$STORE_DIR"

echo "── Step 1/5: generate dataset ──────────────────────────────"
if [ ! -f "$BACKEND_DIR/venv/bin/python" ]; then
  echo "Backend venv missing. Create it first with ./start.sh" >&2
  exit 1
fi
"$BACKEND_DIR/venv/bin/python" scripts/make_organizer_dataset.py

echo "── Step 2/5: prepare MLX environment ────────────────────────"
if [ ! -d "$MLX_VENV" ]; then
  python3 -m venv "$MLX_VENV"
  "$MLX_VENV/bin/pip" install -q -U pip mlx-lm
fi
"$MLX_VENV/bin/pip" install -q -U mlx-lm

echo "── Step 3/5: LoRA training ($ITERS iters) ───────────────────"
echo "  base: $BASE_MODEL"
echo "  data: data/finetune (90 train / 10 valid)"
echo "  This is the long step — expect hours. Be patient; logs stream below."
"$MLX_VENV/bin/python" -m mlx_lm.lora \
  --model "$BASE_MODEL" \
  --train \
  --data data/finetune \
  --iters "$ITERS" \
  --batch-size 2 \
  --num-layers 24 \
  --lora-layers 8 \
  --learning-rate 1e-5 \
  --max-seq-len 4096 \
  --steps-per-report 10 \
  --steps-per-eval 50 \
  --save-every 100 \
  --adapter-path "$ADAPTER_DIR"

echo "── Step 4/5: fuse adapter + convert to GGUF ─────────────────"
"$MLX_VENV/bin/python" -m mlx_lm.fuse \
  --model "$BASE_MODEL" \
  --adapter-path "$ADAPTER_DIR" \
  --save-path "$FUSED_DIR"

LLAMACPP_DIR="$STORE_DIR/llama.cpp"
if [ ! -f "$LLAMACPP_DIR/convert_hf_to_gguf.py" ]; then
  git clone --depth 1 https://github.com/ggml-org/llama.cpp "$LLAMACPP_DIR"
fi
"$MLX_VENV/bin/pip" install -q torch transformers gguf 2>/dev/null || true
python3 - <<'PY'
import sys
sys.path.insert(0, "storage/finetune/llama.cpp")
from convert_hf_to_gguf import main as convert
sys.argv = ["convert_hf_to_gguf.py", "storage/finetune/organizer-3b-mlx",
            "--outfile", "storage/finetune/organizer-3b.gguf", "--outtype", "q8_0"]
convert()
PY

echo "── Step 5/5: register in Ollama + point ARIA at it ──────────"
cat > "$STORE_DIR/Modelfile" <<EOF
FROM ./organizer-3b.gguf

PARAMETER temperature 0.2
PARAMETER num_ctx 8192
EOF
ollama create "$OLLAMA_MODEL_NAME" -f "$STORE_DIR/Modelfile"

"$BACKEND_DIR/venv/bin/python" - <<'PY'
from models.database import save_config
save_config({"organizer_model": "organizer-3b"})
print("ARIA File Organizer now uses: organizer-3b")
PY

echo
echo "✅ Done! The File Organizer now uses the fine-tuned 'organizer-3b' model."
echo "   Test it in ARIA → File Organizer → AI Rename + Organize."
echo "   To revert: set organizer_model back to '' in Admin settings."
echo "   To retrain with more data: add examples to make_organizer_dataset.py and re-run."
