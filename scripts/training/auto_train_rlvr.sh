#!/bin/bash
# =============================================================================
# Auto Training Pipeline with Retry
# SFT → GGUF → Ollama → RLVR (with auto-retry on failure)
# =============================================================================
set -e

cd /Users/w00tock/code/mainframe-ai-apple-silicon
LOG="/tmp/auto_train_rlvr.log"
MAX_RETRIES=3

log() { echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG"; }

cleanup() {
    log "Cleaning up..."
    find data/training -name "0*_adapters.safetensors" -delete 2>/dev/null
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
    find . -name "*.pyc" -delete 2>/dev/null
    rm -f /tmp/rlvr_job_*.jcl 2>/dev/null
    log "Cleanup done"
}

run_sft() {
    log "=== Phase 1: SFT Training ==="
    source .venv-train/bin/activate
    
    python -m mlx_lm.lora \
        --model mistralai/Mistral-7B-Instruct-v0.3 \
        --train \
        --fine-tune-type full \
        --data ./data/training/mlx_data \
        --batch-size 1 \
        --iters 10000 \
        --learning-rate 5e-6 \
        --adapter-path ./data/training/bigiron_final \
        --save-every 2500 \
        --grad-checkpoint \
        --max-seq-length 2048 \
        2>&1 | tee -a "$LOG"
}

run_fuse() {
    log "=== Phase 2: Fuse Model ==="
    python -m mlx_lm.fuse \
        --model mistralai/Mistral-7B-Instruct-v0.3 \
        --adapter-path ./data/training/bigiron_final \
        --save-path ./data/training/bigiron_final_fused \
        2>&1 | tee -a "$LOG"
}

run_gguf() {
    log "=== Phase 3: Convert to GGUF ==="
    LLAMA_CPP="/tmp/llama.cpp"
    [ ! -d "$LLAMA_CPP" ] && git clone --depth 1 https://github.com/ggerganov/llama.cpp "$LLAMA_CPP"
    
    python "$LLAMA_CPP/convert_hf_to_gguf.py" \
        ./data/training/bigiron_final_fused \
        --outfile ./data/training/bigiron-final.gguf \
        --outtype q8_0 \
        2>&1 | tee -a "$LOG"
    
    # Remove fused dir to save space
    rm -rf ./data/training/bigiron_final_fused
}

run_ollama() {
    log "=== Phase 4: Register with Ollama ==="
    cat > configs/ollama/Modelfile.bigiron-final << 'EOF'
FROM ./data/training/bigiron-final.gguf

SYSTEM """You are BigIron-AI, a mainframe expert. You know z/OS, COBOL, JCL, CICS, RACF, DB2, VSAM, REXX, Assembler, and mainframe security. You provide accurate, working code."""

PARAMETER temperature 0.3
PARAMETER top_p 0.9
PARAMETER num_ctx 4096
EOF
    
    ollama create bigiron:final -f configs/ollama/Modelfile.bigiron-final 2>&1 | tee -a "$LOG"
}

run_rlvr() {
    log "=== Phase 5: RLVR Verification ==="
    # Update RLVR to use new model
    sed -i '' 's/bigiron:clean/bigiron:final/g' scripts/training/rlvr_to_five.sh
    ./scripts/training/rlvr_to_five.sh 2>&1 | tee -a "$LOG"
}

# Main with retry
log "Starting auto training pipeline"
cleanup

for attempt in $(seq 1 $MAX_RETRIES); do
    log "Attempt $attempt of $MAX_RETRIES"
    
    if run_sft && run_fuse && run_gguf && run_ollama && run_rlvr; then
        log "SUCCESS! Pipeline completed."
        cleanup
        exit 0
    else
        log "Attempt $attempt failed. Cleaning up and retrying..."
        cleanup
        sleep 10
    fi
done

log "FAILED after $MAX_RETRIES attempts"
exit 1
