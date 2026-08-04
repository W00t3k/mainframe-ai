#!/bin/bash
# =============================================================================
# Auto-Chain: SFT → GGUF → Ollama → RLVR
# =============================================================================
# Monitors SFT training completion, then automatically:
#   1. Converts trained model to GGUF
#   2. Registers with Ollama
#   3. Starts RLVR training to score 5
#   4. Cleans up old checkpoints
# =============================================================================

set -e
cd "$(dirname "$0")/../.."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

LOG_FILE="/tmp/auto_chain.log"
SFT_LOG="/tmp/sft_v3_train.log"
ADAPTER_DIR="data/training/adapters_v3"
MODEL_NAME="bigiron:v3"

log() {
    echo -e "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

echo -e "${BLUE}=============================================="
echo "Auto-Chain: SFT → GGUF → Ollama → RLVR"
echo "=============================================="
echo -e "${NC}"

# Step 1: Wait for SFT completion
log "${YELLOW}[1/5] Waiting for SFT training to complete...${NC}"
while true; do
    if grep -q "Iter 5000:" "$SFT_LOG" 2>/dev/null; then
        log "${GREEN}✓ SFT training complete!${NC}"
        break
    fi
    if ! pgrep -f "mlx_lm" > /dev/null 2>&1; then
        # Check if it completed or crashed
        if grep -q "Iter 5000:" "$SFT_LOG" 2>/dev/null; then
            log "${GREEN}✓ SFT training complete!${NC}"
            break
        else
            log "${RED}ERROR: SFT process died before completion${NC}"
            tail -20 "$SFT_LOG"
            exit 1
        fi
    fi
    sleep 30
done

# Step 2: Fuse adapters with base model
log "${YELLOW}[2/5] Fusing adapters with base model...${NC}"
source .venv-train/bin/activate

python -m mlx_lm.fuse \
    --model mistralai/Mistral-7B-Instruct-v0.3 \
    --adapter-path "$ADAPTER_DIR" \
    --save-path data/training/bigiron-v3-fused \
    2>&1 | tee -a "$LOG_FILE"

log "${GREEN}✓ Model fused${NC}"

# Step 3: Convert to GGUF
log "${YELLOW}[3/5] Converting to GGUF...${NC}"

# Use llama.cpp converter
LLAMA_CPP="/tmp/llama.cpp"
if [ ! -d "$LLAMA_CPP" ]; then
    log "Cloning llama.cpp..."
    git clone --depth 1 https://github.com/ggerganov/llama.cpp "$LLAMA_CPP"
fi

python "$LLAMA_CPP/convert_hf_to_gguf.py" \
    data/training/bigiron-v3-fused \
    --outfile data/training/bigiron-ai-v3.gguf \
    --outtype q8_0 \
    2>&1 | tee -a "$LOG_FILE"

log "${GREEN}✓ GGUF created: data/training/bigiron-ai-v3.gguf${NC}"

# Step 4: Register with Ollama
log "${YELLOW}[4/5] Registering with Ollama...${NC}"

cat > configs/ollama/Modelfile.bigiron-v3 << 'EOF'
FROM ./data/training/bigiron-ai-v3.gguf

SYSTEM """You are BigIron-AI, a specialized mainframe assistant expert in z/OS, COBOL, JCL, CICS, RACF, DB2, and VSAM. You provide accurate, production-ready code examples."""

PARAMETER temperature 0.3
PARAMETER top_p 0.9
PARAMETER num_ctx 4096
EOF

ollama create bigiron:v3 -f configs/ollama/Modelfile.bigiron-v3 2>&1 | tee -a "$LOG_FILE"
log "${GREEN}✓ Registered as ${MODEL_NAME}${NC}"

# Step 5: Clean up old checkpoints (keep only final)
log "${YELLOW}[5/5] Cleaning up old checkpoints...${NC}"
cd "$ADAPTER_DIR"
# Keep only the final adapters.safetensors, remove intermediate numbered ones
find . -name "0*_adapters.safetensors" -delete 2>/dev/null || true
log "${GREEN}✓ Cleaned up intermediate checkpoints${NC}"
cd - > /dev/null

# Summary
echo ""
echo -e "${GREEN}=============================================="
echo "Auto-Chain Complete!"
echo "=============================================="
echo -e "${NC}"
echo "Model: ${MODEL_NAME}"
echo "GGUF: data/training/bigiron-ai-v3.gguf"
echo ""
echo "Test with:"
echo "  ollama run bigiron:v3 'Write JCL to run IEFBR14'"
echo ""
echo "To start RLVR:"
echo "  ./scripts/training/rlvr_to_five.sh"
echo ""

# Optional: Auto-start RLVR
read -p "Start RLVR now? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log "Starting RLVR..."
    ./scripts/training/rlvr_to_five.sh
fi
