#!/bin/bash
#===============================================================================
# BigIron-AI Full Training - Run with nohup
# Usage: nohup ./scripts/training/full_train_nohup.sh > /tmp/bigiron_train.log 2>&1 &
#===============================================================================

set -e
cd "$(dirname "$0")/../.."
LOG="/tmp/bigiron_train_$(date +%Y%m%d_%H%M%S).log"

log() { echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG"; }

log "=== BigIron-AI Full Training Started ==="
log "Log: $LOG"

# Activate venv
source .venv-train/bin/activate

# Cleanup old stuff
log "Cleaning up old files..."
rm -rf data/training/bigiron_full 2>/dev/null || true
rm -rf data/training/quick_* 2>/dev/null || true

# Phase 1: Full Fine-Tuning (10,000 iterations)
log "=== Phase 1: Full Fine-Tuning (10,000 iters, ~8 hours) ==="
mkdir -p data/training/bigiron_full/weights

mlx_lm.lora \
    --model mistralai/Mistral-7B-Instruct-v0.3 \
    --data data/training/mlx_data \
    --train \
    --fine-tune-type full \
    --iters 10000 \
    --batch-size 1 \
    --learning-rate 5e-6 \
    --grad-checkpoint \
    --max-seq-length 2048 \
    --save-every 2000 \
    --steps-per-report 100 \
    --steps-per-eval 1000 \
    --adapter-path data/training/bigiron_full/weights 2>&1 | tee -a "$LOG"

log "Training complete. Cleaning checkpoints..."
# Keep only final weights
cd data/training/bigiron_full/weights
ls -t *_adapters.safetensors 2>/dev/null | tail -n +2 | xargs rm -f 2>/dev/null || true
cd - > /dev/null

# Phase 2: Fuse
log "=== Phase 2: Fusing model ==="
mlx_lm.fuse \
    --model mistralai/Mistral-7B-Instruct-v0.3 \
    --adapter-path data/training/bigiron_full/weights \
    --save-path data/training/bigiron_full/fused \
    --dequantize 2>&1 | tee -a "$LOG"

# Phase 3: Convert to GGUF
log "=== Phase 3: Converting to GGUF ==="
python ~/llama.cpp/convert_hf_to_gguf.py \
    data/training/bigiron_full/fused \
    --outfile data/training/bigiron-ai.gguf \
    --outtype q8_0 2>&1 | tee -a "$LOG"

# Phase 4: Register with Ollama
log "=== Phase 4: Registering with Ollama ==="
cat > configs/ollama/Modelfile.bigiron-ai << EOF
FROM $(pwd)/data/training/bigiron-ai.gguf

TEMPLATE """[INST] {{ .Prompt }} [/INST]"""

SYSTEM """You are BigIron-AI, a mainframe expert. Provide accurate, production-ready code for COBOL, JCL, CICS, RACF, DB2, VSAM, and REXX."""

PARAMETER temperature 0.3
PARAMETER top_p 0.9
EOF

ollama create bigiron-ai -f configs/ollama/Modelfile.bigiron-ai 2>&1 | tee -a "$LOG"

# Phase 5: Test
log "=== Phase 5: Testing ==="
echo "Test: Write COBOL FILE-CONTROL for VSAM KSDS"
ollama run bigiron-ai "Write COBOL FILE-CONTROL for VSAM KSDS" 2>&1 | tee -a "$LOG"

# Final cleanup
log "=== Final Cleanup ==="
rm -rf data/training/bigiron_full/fused
rm -rf data/training/bigiron_full/weights/*_adapters.safetensors 2>/dev/null || true

log "=== COMPLETE ==="
log "Model: bigiron-ai"
log "GGUF: data/training/bigiron-ai.gguf"
log "Test: ollama run bigiron-ai 'What is RACF?'"
