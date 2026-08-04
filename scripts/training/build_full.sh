#!/bin/bash
#===============================================================================
# BigIron-AI Full Build Pipeline
# Automated training, conversion, and deployment
#
# Usage: nohup ./scripts/training/build_full.sh > /tmp/build.log 2>&1 &
#===============================================================================

set -e
cd "$(dirname "$0")/../.."

LOG="/tmp/bigiron_build_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1

echo "=== BigIron-AI Full Build ==="
echo "Started: $(date)"
echo "Log: $LOG"
echo ""

# Configuration
ITERS=${1:-10000}
MODEL_NAME="bigironv2"
BASE_MODEL="mistralai/Mistral-7B-Instruct-v0.3"

# Step 1: Prepare training data
echo "[1/6] Preparing training data..."
cat data/training/examples/*.jsonl > /tmp/all_training.jsonl 2>/dev/null || true
total=$(wc -l < /tmp/all_training.jsonl)
train_count=$((total * 90 / 100))
sort -R /tmp/all_training.jsonl > /tmp/shuffled.jsonl
head -$train_count /tmp/shuffled.jsonl > data/training/mlx_data/train.jsonl
tail -$((total - train_count)) /tmp/shuffled.jsonl > data/training/mlx_data/valid.jsonl
echo "Train: $(wc -l < data/training/mlx_data/train.jsonl), Valid: $(wc -l < data/training/mlx_data/valid.jsonl)"

# Step 2: Clean old checkpoints
echo ""
echo "[2/6] Cleaning old files..."
rm -rf data/training/bigiron_lora/0* 2>/dev/null || true
rm -rf data/training/bigiron_fused 2>/dev/null || true
rm -f /tmp/rlvr_*.jcl /tmp/rlvr_*.log 2>/dev/null || true

# Step 3: Train
echo ""
echo "[3/6] Training (${ITERS} iterations)..."
source .venv-train/bin/activate

mlx_lm.lora \
    --model $BASE_MODEL \
    --data data/training/mlx_data \
    --train \
    --fine-tune-type lora \
    --num-layers 16 \
    --iters $ITERS \
    --batch-size 2 \
    --learning-rate 5e-6 \
    --grad-checkpoint \
    --max-seq-length 2048 \
    --save-every 2000 \
    --adapter-path data/training/bigiron_lora

# Step 4: Fuse
echo ""
echo "[4/6] Fusing adapters..."
mlx_lm.fuse \
    --model $BASE_MODEL \
    --adapter-path data/training/bigiron_lora \
    --save-path data/training/bigiron_fused

# Step 5: Convert to GGUF
echo ""
echo "[5/6] Converting to GGUF..."
python /tmp/llama_cpp/convert_hf_to_gguf.py data/training/bigiron_fused \
    --outfile data/training/bigiron-v2.gguf \
    --outtype q8_0 || {
    # Fallback: clone llama.cpp if not present
    git clone --depth 1 https://github.com/ggerganov/llama.cpp /tmp/llama_cpp 2>/dev/null || true
    python /tmp/llama_cpp/convert_hf_to_gguf.py data/training/bigiron_fused \
        --outfile data/training/bigiron-v2.gguf \
        --outtype q8_0
}

# Step 6: Register with Ollama
echo ""
echo "[6/6] Registering with Ollama..."
cat > configs/ollama/Modelfile.bigironv2 << 'EOF'
FROM /Users/w00tock/code/mainframe-ai-apple-silicon/data/training/bigiron-v2.gguf

TEMPLATE """{{ if .System }}<s>[INST] {{ .System }}

{{ .Prompt }} [/INST]{{ else }}<s>[INST] {{ .Prompt }} [/INST]{{ end }}"""

SYSTEM """You are BigIron-AI, a mainframe expert. Provide accurate, production-ready code for COBOL, JCL, CICS, RACF, DB2, VSAM, and REXX."""

PARAMETER temperature 0.3
PARAMETER top_p 0.9
PARAMETER repeat_penalty 1.15
PARAMETER num_predict 1024
PARAMETER stop "</s>"
PARAMETER stop "[INST]"
EOF

ollama create $MODEL_NAME -f configs/ollama/Modelfile.bigironv2

# Cleanup
echo ""
echo "Cleaning up..."
rm -rf data/training/bigiron_fused
rm -rf data/training/bigiron_lora/0*
rm -f /tmp/all_training.jsonl /tmp/shuffled.jsonl

# Test
echo ""
echo "=== Testing ==="
ollama run $MODEL_NAME "Write JCL to run IEFBR14" | head -10

echo ""
echo "=== Build Complete ==="
echo "Model: $MODEL_NAME"
echo "Finished: $(date)"
echo "Log: $LOG"
