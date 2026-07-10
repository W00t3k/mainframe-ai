#!/bin/bash
# Upload BigIron-AI model and dataset to HuggingFace
# Usage: ./scripts/upload_to_huggingface.sh [--model] [--dataset] [--both]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration - UPDATE THESE
HF_USERNAME="${HF_USERNAME:-bigiron-ai}"
MODEL_REPO="${MODEL_REPO:-bigiron-7b}"
DATASET_REPO="${DATASET_REPO:-mainframe-instruct}"

MODEL_PATH="$PROJECT_DIR/data/training/bigiron_full/fused"
DATASET_PATH="$PROJECT_DIR/data/training/mlx_data"
EXAMPLES_PATH="$PROJECT_DIR/data/training/examples"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

check_requirements() {
    log "Checking requirements..."

    if ! command -v huggingface-cli &> /dev/null; then
        error "huggingface-cli not found. Install with: pip install huggingface_hub"
    fi

    # Check if logged in
    if ! huggingface-cli whoami &> /dev/null; then
        warn "Not logged in to HuggingFace"
        log "Running: huggingface-cli login"
        huggingface-cli login
    fi

    log "Logged in as: $(huggingface-cli whoami)"
}

upload_model() {
    log "Uploading model to $HF_USERNAME/$MODEL_REPO..."

    if [ ! -d "$MODEL_PATH" ]; then
        error "Model path not found: $MODEL_PATH"
    fi

    # Check model files exist
    if [ ! -f "$MODEL_PATH/config.json" ]; then
        error "config.json not found in model path"
    fi

    log "Model contents:"
    ls -lh "$MODEL_PATH"

    # Create repo if it doesn't exist
    huggingface-cli repo create "$MODEL_REPO" --type model 2>/dev/null || true

    # Upload
    log "Uploading model files (this may take a while for ~14GB)..."
    huggingface-cli upload "$HF_USERNAME/$MODEL_REPO" "$MODEL_PATH" . \
        --commit-message "Upload BigIron-AI v1.0 - Mainframe Expert LLM"

    log "Model uploaded to: https://huggingface.co/$HF_USERNAME/$MODEL_REPO"
}

upload_dataset() {
    log "Preparing dataset for upload..."

    # Create temporary directory for dataset
    TEMP_DATASET="/tmp/bigiron-dataset"
    rm -rf "$TEMP_DATASET"
    mkdir -p "$TEMP_DATASET"

    # Copy training splits
    cp "$DATASET_PATH/train.jsonl" "$TEMP_DATASET/"
    cp "$DATASET_PATH/valid.jsonl" "$TEMP_DATASET/"
    cp "$DATASET_PATH/test.jsonl" "$TEMP_DATASET/"

    # Create dataset card
    cat > "$TEMP_DATASET/README.md" << 'EOF'
---
license: apache-2.0
language:
- en
tags:
- mainframe
- cobol
- jcl
- rexx
- racf
- z/os
- ibm
- code
- instruction-tuning
size_categories:
- 1K<n<10K
task_categories:
- text-generation
- question-answering
---

# Mainframe Instruct Dataset

Training dataset for BigIron-AI, a mainframe-specialized LLM.

## Dataset Description

9,042 instruction-response pairs covering IBM mainframe technologies:

- **COBOL** - Arithmetic, tables, copybooks, DB2 integration, file I/O
- **JCL** - Utilities, procedures, conditional execution, SORT
- **REXX** - EXECIO, TSO, ISPF, OUTTRAP, system programming
- **RACF** - User/group management, dataset protection, security
- **CICS** - BMS maps, file operations, transactions
- **DB2** - DDL, stored procedures, embedded SQL
- **VSAM** - KSDS operations, IDCAMS
- **Assembler** - Macros, SVCs, system programming
- **Utilities** - DFSORT, IDCAMS, IEBCOPY, ADRDSSU

## Dataset Structure

```
train.jsonl  - 7,686 examples (85%)
valid.jsonl  -   904 examples (10%)
test.jsonl   -   452 examples (5%)
```

## Format

```json
{
  "messages": [
    {"role": "user", "content": "Write JCL to copy a PDS"},
    {"role": "assistant", "content": "Here's the JCL..."}
  ]
}
```

## Usage

```python
from datasets import load_dataset

dataset = load_dataset("bigiron-ai/mainframe-instruct")
print(dataset["train"][0])
```

## Sources

- Hand-crafted code examples
- MainframeBench (Fsoft-AIC)
- IBM Redbooks extracts

## License

Apache 2.0
EOF

    log "Dataset prepared in $TEMP_DATASET"
    log "Files:"
    wc -l "$TEMP_DATASET"/*.jsonl

    # Create repo if it doesn't exist
    huggingface-cli repo create "$DATASET_REPO" --type dataset 2>/dev/null || true

    # Upload
    log "Uploading dataset..."
    huggingface-cli upload "$HF_USERNAME/$DATASET_REPO" "$TEMP_DATASET" . \
        --repo-type dataset \
        --commit-message "Upload Mainframe Instruct Dataset v1.0"

    log "Dataset uploaded to: https://huggingface.co/datasets/$HF_USERNAME/$DATASET_REPO"

    # Cleanup
    rm -rf "$TEMP_DATASET"
}

show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --model     Upload model only"
    echo "  --dataset   Upload dataset only"
    echo "  --both      Upload both model and dataset (default)"
    echo "  --help      Show this help"
    echo ""
    echo "Environment variables:"
    echo "  HF_USERNAME   HuggingFace username (default: bigiron-ai)"
    echo "  MODEL_REPO    Model repository name (default: bigiron-7b)"
    echo "  DATASET_REPO  Dataset repository name (default: mainframe-instruct)"
}

main() {
    local upload_model=false
    local upload_dataset=false

    # Parse arguments
    if [ $# -eq 0 ]; then
        upload_model=true
        upload_dataset=true
    else
        while [ $# -gt 0 ]; do
            case "$1" in
                --model)
                    upload_model=true
                    ;;
                --dataset)
                    upload_dataset=true
                    ;;
                --both)
                    upload_model=true
                    upload_dataset=true
                    ;;
                --help)
                    show_usage
                    exit 0
                    ;;
                *)
                    error "Unknown option: $1"
                    ;;
            esac
            shift
        done
    fi

    check_requirements

    if [ "$upload_model" = true ]; then
        upload_model
    fi

    if [ "$upload_dataset" = true ]; then
        upload_dataset
    fi

    log "Done!"
    echo ""
    echo "Next steps:"
    echo "  1. Visit https://huggingface.co/$HF_USERNAME to verify uploads"
    echo "  2. Update model card with any additional details"
    echo "  3. Add model to Ollama library (optional)"
}

main "$@"
