#!/bin/bash
#
# BigIron-AI RLVR Training Runner
#
# Trains the model using Reinforcement Learning with Verifiable Rewards.
# Requires TK5 MVS to be running for verification.
#
# Usage:
#   ./run_rlvr.sh              # Full training (500 steps)
#   ./run_rlvr.sh --dry-run    # Test without training
#   ./run_rlvr.sh --no-tk5     # Use heuristic rewards
#   ./run_rlvr.sh --steps 100  # Custom step count
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║             BigIron-AI RLVR Training                       ║"
echo "║     Reinforcement Learning with Verifiable Rewards         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check for venv
VENV_PATH="$PROJECT_ROOT/.venv-train"
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${RED}Error: Training venv not found at $VENV_PATH${NC}"
    echo "Run: python3.12 -m venv .venv-train && source .venv-train/bin/activate && pip install -r requirements-train.txt"
    exit 1
fi

# Activate venv
source "$VENV_PATH/bin/activate"

# Check dependencies
echo -e "${YELLOW}Checking dependencies...${NC}"
python -c "import torch, transformers, trl, datasets" 2>/dev/null || {
    echo -e "${RED}Missing dependencies. Installing...${NC}"
    pip install torch transformers trl datasets accelerate py3270
}

# Check if TK5 is running (unless --no-tk5)
if [[ ! " $* " =~ " --no-tk5 " ]] && [[ ! " $* " =~ " --dry-run " ]]; then
    echo -e "${YELLOW}Checking TK5 status...${NC}"
    if curl -s "http://localhost:8038/cgi-bin/tasks/cmd?cmd=d%20a,l" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ TK5 is running${NC}"
    else
        echo -e "${YELLOW}⚠ TK5 not detected. Starting verification in heuristic mode.${NC}"
        echo "  For full verification, start TK5: ./start.sh"
        echo "  Or use --no-tk5 to explicitly use heuristic mode."
        echo ""
        # Add --no-tk5 if not already specified
        set -- "$@" "--no-tk5"
    fi
fi

# Run training
echo ""
echo -e "${BLUE}Starting RLVR training...${NC}"
echo "Arguments: $@"
echo ""

python "$SCRIPT_DIR/rlvr_train.py" "$@"

# If not dry run, show next steps
if [[ ! " $* " =~ " --dry-run " ]]; then
    echo ""
    echo -e "${GREEN}Training complete!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Convert to GGUF: python -m mlx_lm.convert --hf-path data/training/bigiron-rlvr -q"
    echo "  2. Update Ollama: ollama create bigiron-rlvr -f configs/ollama/Modelfile.bigiron-ai"
    echo "  3. Test: ollama run bigiron-rlvr 'Write JCL to copy a dataset'"
fi
