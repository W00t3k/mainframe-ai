#!/bin/bash
# Reset training data and start fresh

cd /Users/w00tock/code/mainframe-ai-apple-silicon

echo "Resetting training data..."

# Restore from backup
cp data/training/mlx_data/train.jsonl.backup data/training/mlx_data/train.jsonl
echo "✓ Restored train.jsonl from backup"

# Remove splits (will be recreated)
rm -f data/training/mlx_data/valid.jsonl
rm -f data/training/mlx_data/test.jsonl
echo "✓ Removed old splits"

# Remove merge flag (examples will be re-merged)
rm -f data/training/mlx_data/.examples_merged
echo "✓ Reset merge flag"

echo ""
echo "Starting training..."
./scripts/training/build_bigiron_ai.sh --epochs 100
