#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  ARIA All-Tasks — Qwen3-VL-8B LoRA fine-tune (MLX-LM on Apple Silicon M4)
#
#  ONE model for ALL ARIA tasks: reasoning/chat + study tools + vision/OCR.
#  Qwen3-VL-8B is the only model family that covers every LLM task ARIA has
#  (text reasoning AND image understanding), and it is fully LoRA-finetunable.
#
#  Pipeline:
#    1. generate dataset (scripts/make_aria_dataset.py) — all ARIA task types
#    2. train a LoRA adapter with mlx-lm QLoRA (4-bit base, fits 16 GB)
#    3. fuse the adapter into the base model
#    4. convert to GGUF and register as an Ollama model "aria-vl-8b"
#    5. point ARIA's reasoning_model + vision_model at it (one model both)
#
#  Expected time on a MacBook Air M4 16 GB: 3-8 hours for 300 iters.
#  Adapters are saved every 100 iters — you can stop and resume.
#
#  Run from anywhere:
#      ./backend/scripts/finetune_aria.sh
#  Options:
#      ./backend/scripts/finetune_aria.sh --iters 300 --base mlx-community/Qwen3-VL-8B-Instruct-4bit
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BACKEND_DIR"

BASE_MODEL="mlx-community/Qwen3-VL-8B-Instruct-4bit"   # 4-bit → QLoRA on 16 GB M4
ITERS=300
STORE_DIR="storage/finetune-aria"
ADAPTER_DIR="$STORE_DIR/adapters"
FUSED_DIR="$STORE_DIR/aria-vl-8b-mlx"
GGUF_OUT="$STORE_DIR/aria-vl-8b.gguf"
MLX_VENV="$STORE_DIR/.venv-mlx"
OLLAMA_MODEL_NAME="aria-vl-8b"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --iters)   ITERS="$2"; shift 2 ;;
    --base)    BASE_MODEL="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

mkdir -p "$STORE_DIR"

echo "── Step 1/5: generate dataset (all ARIA task types) ───────────"
if [ ! -f "$BACKEND_DIR/venv/bin/python" ]; then
  echo "Backend venv missing. Create it first with ./start.sh" >&2
  exit 1
fi
"$BACKEND_DIR/venv/bin/python" scripts/make_aria_dataset.py

echo "── Step 2/5: prepare MLX environment ───────────────────────────"
if [ ! -d "$MLX_VENV" ]; then
  python3 -m venv "$MLX_VENV"
  "$MLX_VENV/bin/pip" install -q -U pip mlx-lm
fi
"$MLX_VENV/bin/pip" install -q -U mlx-lm

echo "── Step 3/5: QLoRA training ($ITERS iters) ─────────────────────"
echo "  base: $BASE_MODEL  (4-bit → fits 16 GB for LoRA training)"
echo "  data: data/finetune-aria"
echo "  This is the long step — expect hours. Logs stream below."
"$MLX_VENV/bin/python" -m mlx_lm.lora \
  --model "$BASE_MODEL" \
  --train \
  --data data/finetune-aria \
  --iters "$ITERS" \
  --batch-size 1 \
  --num-layers 32 \
  --lora-layers 8 \
  --learning-rate 1e-5 \
  --max-seq-len 2048 \
  --steps-per-report 10 \
  --steps-per-eval 50 \
  --save-every 100 \
  --adapter-path "$ADAPTER_DIR"

echo "── Step 4/5: fuse adapter + convert to GGUF ────────────────────"
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
sys.path.insert(0, "storage/finetune-aria/llama.cpp")
from convert_hf_to_gguf import main as convert
sys.argv = ["convert_hf_to_gguf.py", "storage/finetune-aria/aria-vl-8b-mlx",
            "--outfile", "storage/finetune-aria/aria-vl-8b.gguf",
            "--outtype", "q8_0", "--mmproj"]
convert()
PY

echo "── Step 5/5: register in Ollama + point ARIA at it ─────────────"
cat > "$STORE_DIR/Modelfile" <<EOF
FROM ./aria-vl-8b.gguf
ADAPTER ./mmproj-*.gguf

PARAMETER temperature 0.7
PARAMETER num_ctx 8192
EOF
ollama create "$OLLAMA_MODEL_NAME" -f "$STORE_DIR/Modelfile"

"$BACKEND_DIR/venv/bin/python" - <<'PY'
from models.database import save_config
save_config({"reasoning_model": "aria-vl-8b", "vision_model": "aria-vl-8b"})
print("ARIA now uses the fine-tuned 'aria-vl-8b' for reasoning AND vision.")
PY

echo
echo "✅ Done! ONE model ('aria-vl-8b') now powers every ARIA task."
echo "   Test it in ARIA → Chat / Study Tools / File Organizer."
echo "   To revert: set reasoning_model/vision_model back to qwen3-vl:8b-instruct"
echo "   in Admin settings, or re-run the defaults."
echo "   To retrain with more data: add examples to make_aria_dataset.py and re-run."
