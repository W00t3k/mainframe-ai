#!/bin/bash
# Quick script to push BigIron-AI changes to GitHub

set -e

cd /Users/w00tock/code/mainframe-ai-apple-silicon

echo "Adding files..."
git add \
  .gitignore \
  README.md \
  CLAUDE.md \
  docs/WHITEPAPER.md \
  docs/MEMORY_ARCHITECTURE.md \
  scripts/training/build_bigiron_ai.sh \
  scripts/apple_silicon_check.sh \
  data/training/examples/*.jsonl \
  data/training/mlx_data/train.jsonl \
  data/rag_seed/*.md \
  configs/ollama/Modelfile.bigiron-ai \
  app/services/*.py

echo "Staged files:"
git status --short

echo ""
echo "Committing..."
git commit -m "feat: BigIron-AI full fine-tuning with whitepaper

- Full fine-tuning pipeline (all 7.2B parameters)
- 6,240+ curated training examples
- Updated whitepaper with contributions and dataset docs
- Plain English BigIron personality
- Lower learning rate (5e-6) for finer tuning"

echo ""
echo "Pushing to origin..."
git push origin feature/apple-silicon-bigiron

echo ""
echo "Done! Now start training:"
echo "  ./scripts/training/build_bigiron_ai.sh --epochs 100"
