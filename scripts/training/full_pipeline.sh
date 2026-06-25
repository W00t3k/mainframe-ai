#!/bin/bash
# Full Training Pipeline: Fetch Redbooks → Index → Generate Q&A → Fine-tune

set -e
cd "$(dirname "$0")/../.."
source .venv/bin/activate

LOG="/tmp/full_pipeline.log"
echo "=== Full Training Pipeline ===" | tee $LOG
echo "Started: $(date)" | tee -a $LOG

# Step 1: Fetch more IBM Redbooks
echo "" | tee -a $LOG
echo "[1/5] Fetching IBM Redbooks..." | tee -a $LOG
python scripts/training/fetch_redbooks.py --max-per-topic 15 2>&1 | tee -a $LOG

# Step 2: Index new PDFs into RAG
echo "" | tee -a $LOG
echo "[2/5] Indexing PDFs into RAG..." | tee -a $LOG
python scripts/training/fetch_redbooks.py --index-only 2>&1 | tee -a $LOG

# Step 3: Generate Q&A from all RAG content
echo "" | tee -a $LOG
echo "[3/5] Generating Q&A pairs (this takes a while)..." | tee -a $LOG
python scripts/training/generate_qa_from_rag.py --limit 5000 --output data/training/generated/full_qa.jsonl 2>&1 | tee -a $LOG

# Step 4: Combine all training data
echo "" | tee -a $LOG
echo "[4/5] Combining training data..." | tee -a $LOG
cat data/training/generated/*.jsonl > data/training/generated/all_training.jsonl 2>/dev/null || true
TOTAL=$(wc -l < data/training/generated/all_training.jsonl 2>/dev/null || echo 0)
echo "Total training samples: $TOTAL" | tee -a $LOG

# Step 5: Run MLX fine-tuning
echo "" | tee -a $LOG
echo "[5/5] Starting MLX fine-tuning..." | tee -a $LOG
python scripts/training/mlx_finetune.py --iters 1000 --batch-size 4 2>&1 | tee -a $LOG

echo "" | tee -a $LOG
echo "=== Pipeline Complete ===" | tee -a $LOG
echo "Finished: $(date)" | tee -a $LOG
echo "" | tee -a $LOG
echo "Next steps:" | tee -a $LOG
echo "  1. Fuse adapter: python scripts/training/mlx_finetune.py --fuse" | tee -a $LOG
echo "  2. Test model locally with MLX" | tee -a $LOG
echo "  3. Convert to GGUF for Ollama" | tee -a $LOG
