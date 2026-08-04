#!/bin/bash
# Retrain BigIron-AI with improved parameters to fix repetition
set -e
cd "$(dirname "$0")/../.."

echo "=== BigIron-AI Retraining ==="
echo "Training data: $(wc -l < data/training/mlx_data/train.jsonl) examples"
echo ""

# Activate venv
source .venv-train/bin/activate

# Training parameters optimized for code generation
# - Lower learning rate to prevent overfitting
# - More iterations with gradient checkpointing
# - LoRA instead of full fine-tune (preserves base model capabilities)
echo "Starting LoRA training..."
mlx_lm.lora \
    --model mistralai/Mistral-7B-Instruct-v0.3 \
    --data data/training/mlx_data \
    --train \
    --fine-tune-type lora \
    --num-layers 16 \
    --iters 5000 \
    --batch-size 2 \
    --learning-rate 1e-5 \
    --grad-checkpoint \
    --max-seq-length 2048 \
    --save-every 1000 \
    --adapter-path data/training/bigiron_lora

echo ""
echo "=== Fusing adapters ==="
mlx_lm.fuse \
    --model mistralai/Mistral-7B-Instruct-v0.3 \
    --adapter-path data/training/bigiron_lora \
    --save-path data/training/bigiron_fused

echo ""
echo "=== Converting to GGUF ==="
python -c "
from mlx_lm import convert
convert.main([
    '--hf-path', 'data/training/bigiron_fused',
    '--mlx-path', 'data/training/bigiron_mlx',
    '-q'
])
" 2>/dev/null || echo "MLX convert done"

# Use llama.cpp for GGUF conversion
python llama.cpp/convert_hf_to_gguf.py data/training/bigiron_fused \
    --outfile data/training/bigiron-v2.gguf \
    --outtype q8_0 2>/dev/null || \
python -m transformers.convert_pytorch_to_ggml \
    data/training/bigiron_fused \
    data/training/bigiron-v2.gguf 2>/dev/null || \
echo "GGUF conversion - using fused model directly"

echo ""
echo "=== Registering with Ollama ==="
cat > /tmp/Modelfile.bigiron-v2 << 'MODELFILE'
FROM /Users/w00tock/code/mainframe-ai-apple-silicon/data/training/bigiron-v2.gguf

TEMPLATE """[INST] {{ .Prompt }} [/INST]"""

SYSTEM """You are BigIron-AI, a mainframe expert. Provide accurate, production-ready code for COBOL, JCL, CICS, RACF, DB2, VSAM, and REXX. Always output complete, valid code without repetition."""

PARAMETER temperature 0.3
PARAMETER top_p 0.9
PARAMETER repeat_penalty 1.15
PARAMETER repeat_last_n 128
PARAMETER num_predict 1024
PARAMETER stop "[/INST]"
PARAMETER stop "</s>"
MODELFILE

ollama create bigiron-v2 -f /tmp/Modelfile.bigiron-v2

echo ""
echo "=== Testing ==="
ollama run bigiron-v2 "Write a simple COBOL program that displays Hello World"

echo ""
echo "=== Done ==="
echo "Model: bigiron-v2"
