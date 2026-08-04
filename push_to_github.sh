#!/bin/bash
# Push to GitHub

cd /Users/w00tock/code/mainframe-ai-apple-silicon

echo "Adding remote..."
git remote add origin https://github.com/W00t3k/mainframe-ai.git 2>/dev/null || echo "Remote already exists"

echo "Pushing to GitHub..."
git push -u origin feature/apple-silicon-bigiron

echo ""
echo "Done! Check: https://github.com/W00t3k/mainframe-ai/tree/feature/apple-silicon-bigiron"
echo ""
echo "Now start training:"
echo "  ./scripts/training/build_bigiron_ai.sh --epochs 100"
