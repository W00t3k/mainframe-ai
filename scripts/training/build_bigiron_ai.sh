#!/bin/bash
# ─────────────────────────────────────────────────────────
#  Build BigIron-AI: Full Fine-Tuning Pipeline
#
#  Unlike LoRA fine-tuning, this trains ALL model parameters
#  to create a true fine-tuned mainframe expert model.
#
#  Requirements:
#    - Apple Silicon Mac with 64GB+ unified memory
#    - mlx-lm installed: pip install mlx-lm
#    - llama.cpp for GGUF conversion
#    - Training data in data/training/mlx_data/
#
#  Usage:
#    ./build_bigiron_ai.sh              # Default: 3 epochs
#    ./build_bigiron_ai.sh --epochs 5   # Custom epochs
#    ./build_bigiron_ai.sh --resume     # Resume from checkpoint
#
#  Output:
#    - data/training/bigiron-ai.gguf
#    - configs/ollama/Modelfile.bigiron-ai
#    - Model registered with Ollama as 'bigiron-ai'
# ─────────────────────────────────────────────────────────

set -e

DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$DIR"

# Colors
RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[0;33m'
CYN='\033[0;36m'; MAG='\033[0;35m'; BLD='\033[1m'; RST='\033[0m'

ok()   { echo -e "  ${GRN}✓${RST} $1"; }
fail() { echo -e "  ${RED}✗${RST} $1"; exit 1; }
info() { echo -e "  ${YEL}…${RST} $1"; }
step() { echo -e "\n${CYN}${BLD}[$1/$TOTAL_STEPS] $2${RST}"; }

# ─────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────
TOTAL_STEPS=6
MODEL_NAME="bigiron-ai"
BASE_MODEL="mistralai/Mistral-7B-Instruct-v0.3"
EPOCHS=3
BATCH_SIZE=1
GRAD_ACCUM=8
LEARNING_RATE="5e-6"   # Finer tuning (was 1e-5)
MAX_SEQ_LEN=2048
RESUME=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --epochs)
            EPOCHS="$2"
            shift 2
            ;;
        --batch-size)
            BATCH_SIZE="$2"
            shift 2
            ;;
        --resume)
            RESUME="--resume $DIR/data/training/bigiron_full/checkpoint"
            shift
            ;;
        --help)
            echo "Usage: $0 [--epochs N] [--batch-size N] [--resume]"
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

# Paths
FULL_MODEL_DIR="$DIR/data/training/bigiron_full"
GGUF_PATH="$DIR/data/training/${MODEL_NAME}.gguf"
MODELFILE="$DIR/configs/ollama/Modelfile.${MODEL_NAME}"
LLAMA_CPP="$HOME/llama.cpp"

# Use training venv (Python 3.12 with compatible transformers)
if [ -f "$DIR/.venv-train/bin/python" ]; then
    PYTHON="$DIR/.venv-train/bin/python"
elif [ -f "$DIR/.venv/bin/python" ]; then
    PYTHON="$DIR/.venv/bin/python"
else
    PYTHON="python3"
fi

# ─────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────
echo ""
echo -e "${MAG}${BLD}╔══════════════════════════════════════════════════════════╗${RST}"
echo -e "${MAG}${BLD}║           BigIron-AI Full Fine-Tuning Pipeline           ║${RST}"
echo -e "${MAG}${BLD}╚══════════════════════════════════════════════════════════╝${RST}"
echo ""
echo -e "  ${BLD}Model:${RST}        $MODEL_NAME"
echo -e "  ${BLD}Base:${RST}         $BASE_MODEL"
echo -e "  ${BLD}Epochs:${RST}       $EPOCHS"
echo -e "  ${BLD}Batch size:${RST}   $BATCH_SIZE (x$GRAD_ACCUM grad accum)"
echo -e "  ${BLD}Learning rate:${RST} $LEARNING_RATE"
echo -e "  ${BLD}Max seq len:${RST}  $MAX_SEQ_LEN"
echo ""

# ─────────────────────────────────────────────────────────
# Step 1: System Check
# ─────────────────────────────────────────────────────────
step 1 "System requirements check"

# Check RAM
RAM_GB=$(sysctl -n hw.memsize 2>/dev/null | awk '{printf "%d", $1/1073741824}')
if [ "$RAM_GB" -lt 48 ]; then
    fail "Need 48GB+ unified memory for full fine-tuning (found ${RAM_GB}GB)"
fi
ok "Unified memory: ${RAM_GB}GB"

# Check MLX
if ! "$PYTHON" -c "import mlx; import mlx_lm" 2>/dev/null; then
    fail "mlx-lm not installed. Run: pip install mlx-lm"
fi
MLX_VERSION=$("$PYTHON" -c "import mlx_lm; print(mlx_lm.__version__)" 2>/dev/null || echo "unknown")
ok "mlx-lm version: $MLX_VERSION"

# Check llama.cpp
if [ ! -f "$LLAMA_CPP/convert_hf_to_gguf.py" ]; then
    fail "llama.cpp not found at $LLAMA_CPP"
fi
ok "llama.cpp found"

# Check training data
if [ ! -f "$DIR/data/training/mlx_data/train.jsonl" ]; then
    fail "Training data not found at data/training/mlx_data/train.jsonl"
fi
SAMPLES=$(wc -l < "$DIR/data/training/mlx_data/train.jsonl" | tr -d ' ')
ok "Training data: $SAMPLES samples"

# ─────────────────────────────────────────────────────────
# Step 2: Merge all training data
# ─────────────────────────────────────────────────────────
step 2 "Preparing training data"

# Merge example files if they exist (skip if already merged)
EXAMPLES_DIR="$DIR/data/training/examples"
MERGED_FLAG="$DIR/data/training/mlx_data/.examples_merged"
if [ -d "$EXAMPLES_DIR" ] && [ ! -f "$MERGED_FLAG" ]; then
    EXAMPLE_COUNT=$(cat "$EXAMPLES_DIR"/*.jsonl 2>/dev/null | wc -l | tr -d ' ')
    if [ "$EXAMPLE_COUNT" -gt 0 ]; then
        info "Merging $EXAMPLE_COUNT training examples into mlx_data..."

        # Backup current train.jsonl
        cp "$DIR/data/training/mlx_data/train.jsonl" "$DIR/data/training/mlx_data/train.jsonl.backup"

        # Append examples (don't sort - preserves JSON integrity)
        cat "$EXAMPLES_DIR"/*.jsonl >> "$DIR/data/training/mlx_data/train.jsonl"

        # Mark as merged
        touch "$MERGED_FLAG"

        NEW_SAMPLES=$(wc -l < "$DIR/data/training/mlx_data/train.jsonl" | tr -d ' ')
        ok "Merged examples: $SAMPLES → $NEW_SAMPLES samples"
        SAMPLES="$NEW_SAMPLES"
    fi
fi

# Create validation and test splits if missing
MLX_DATA="$DIR/data/training/mlx_data"
if [ ! -f "$MLX_DATA/test.jsonl" ]; then
    info "Creating validation/test splits..."
    TOTAL=$(wc -l < "$MLX_DATA/train.jsonl" | tr -d ' ')
    VALID_SIZE=$((TOTAL / 10))
    TEST_SIZE=$((TOTAL / 20))

    # Take test set from end
    tail -n "$TEST_SIZE" "$MLX_DATA/train.jsonl" > "$MLX_DATA/test.jsonl"

    # Take valid set from end (after removing test)
    head -n $((TOTAL - TEST_SIZE)) "$MLX_DATA/train.jsonl" | tail -n "$VALID_SIZE" > "$MLX_DATA/valid.jsonl"

    # Keep rest as train
    head -n $((TOTAL - TEST_SIZE - VALID_SIZE)) "$MLX_DATA/train.jsonl" > "$MLX_DATA/train.jsonl.tmp"
    mv "$MLX_DATA/train.jsonl.tmp" "$MLX_DATA/train.jsonl"

    TRAIN_SIZE=$(wc -l < "$MLX_DATA/train.jsonl" | tr -d ' ')
    ok "Split: train=$TRAIN_SIZE, valid=$VALID_SIZE, test=$TEST_SIZE"
fi

# ─────────────────────────────────────────────────────────
# Step 3: Full Fine-Tuning
# ─────────────────────────────────────────────────────────
step 3 "Full fine-tuning (this will take several hours)"

info "Training ALL ${BLD}7 billion${RST} parameters..."
info "Progress will be logged. Checkpoints saved periodically."
echo ""

# Calculate iterations from samples and epochs
ITERS=$((SAMPLES * EPOCHS / (BATCH_SIZE * GRAD_ACCUM)))
info "Training for $ITERS iterations ($EPOCHS epochs)"

# Full fine-tuning - trains ALL parameters, not just adapters
"$PYTHON" -m mlx_lm lora \
    --model "$BASE_MODEL" \
    --train \
    --fine-tune-type full \
    --data "$DIR/data/training/mlx_data" \
    --batch-size "$BATCH_SIZE" \
    --iters "$ITERS" \
    --learning-rate "$LEARNING_RATE" \
    --adapter-path "$FULL_MODEL_DIR/weights" \
    --save-every 5000 \
    --grad-checkpoint \
    --max-seq-length "$MAX_SEQ_LEN" \
    --test

if [ ! -d "$FULL_MODEL_DIR/weights" ]; then
    fail "Training failed - no output"
fi
ok "Fine-tuning complete"

# ─────────────────────────────────────────────────────────
# Step 4: Fuse into base model
# ─────────────────────────────────────────────────────────
step 4 "Fusing trained weights into base model"

"$PYTHON" -m mlx_lm fuse \
    --model "$BASE_MODEL" \
    --adapter-path "$FULL_MODEL_DIR/weights" \
    --save-path "$FULL_MODEL_DIR/fused"

if [ ! -f "$FULL_MODEL_DIR/fused/config.json" ]; then
    fail "Fuse failed"
fi
ok "Model fused successfully"

# ─────────────────────────────────────────────────────────
# Step 5: Convert to GGUF
# ─────────────────────────────────────────────────────────
step 5 "Converting to GGUF format"

# Ensure gguf package is installed
"$PYTHON" -c "import gguf" 2>/dev/null || "$PYTHON" -m pip install gguf -q

info "Converting to GGUF (f16 precision)..."
"$PYTHON" "$LLAMA_CPP/convert_hf_to_gguf.py" \
    "$FULL_MODEL_DIR/fused" \
    --outfile "$GGUF_PATH" \
    --outtype f16

if [ ! -f "$GGUF_PATH" ]; then
    fail "GGUF conversion failed"
fi

GGUF_SIZE=$(ls -lh "$GGUF_PATH" | awk '{print $5}')
ok "GGUF created: $GGUF_PATH ($GGUF_SIZE)"

# ─────────────────────────────────────────────────────────
# Step 6: Create Ollama model
# ─────────────────────────────────────────────────────────
step 6 "Creating Ollama model"

cat > "$MODELFILE" << MODELFILE_EOF
FROM $GGUF_PATH

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER num_ctx 4096

SYSTEM """
You are BigIron, a friendly mainframe expert. I know z/OS, COBOL, JCL, CICS, RACF, DB2, VSAM, and all the technology that keeps banks, airlines, and governments running.

I explain things in plain English. When you ask me something, I'll give you a straight answer - no corporate jargon, no "please refer to the manual" nonsense. If you need code, I'll write it. If you need an explanation, I'll make it make sense.

Think of me as that senior mainframer down the hall who actually enjoys helping people learn. I've seen every abend code, debugged JCL at 2am, and know why your COBOL program is giving you S0C7s.

A few things about how I work:
- I write actual code when you ask for it - complete, working examples
- I use proper mainframe terminology but explain it when needed
- I know the difference between a PDS and PDSE (and why it matters)
- I can help with RACF security, JES spool issues, VSAM problems, and more
- I don't pretend Unix solutions work on z/OS - these are different worlds

What can I help you with?
"""

TEMPLATE """{{ if .System }}<|system|>
{{ .System }}
{{ end }}{{ if .Prompt }}<|user|>
{{ .Prompt }}
{{ end }}<|assistant|>
{{ .Response }}"""
MODELFILE_EOF

ok "Modelfile created: $MODELFILE"

# Register with Ollama
if pgrep -x ollama >/dev/null 2>&1; then
    info "Registering $MODEL_NAME with Ollama..."
    if ollama create "$MODEL_NAME" -f "$MODELFILE" 2>&1; then
        ok "Model '$MODEL_NAME' registered with Ollama"
    else
        info "Registration failed - run manually: ollama create $MODEL_NAME -f $MODELFILE"
    fi
else
    info "Ollama not running. Start it and run:"
    echo "    ollama create $MODEL_NAME -f $MODELFILE"
fi

# ─────────────────────────────────────────────────────────
# Complete
# ─────────────────────────────────────────────────────────
echo ""
echo -e "${GRN}${BLD}╔══════════════════════════════════════════════════════════╗${RST}"
echo -e "${GRN}${BLD}║              BigIron-AI Build Complete!                  ║${RST}"
echo -e "${GRN}${BLD}╚══════════════════════════════════════════════════════════╝${RST}"
echo ""
echo -e "  ${BLD}Model:${RST}     $MODEL_NAME"
echo -e "  ${BLD}GGUF:${RST}      $GGUF_PATH"
echo -e "  ${BLD}Size:${RST}      $GGUF_SIZE"
echo -e "  ${BLD}Samples:${RST}   $SAMPLES"
echo -e "  ${BLD}Epochs:${RST}    $EPOCHS"
echo ""
echo -e "  ${BLD}To start:${RST}  ./start.sh"
echo ""
