# BigIron-AI Training Guide

This document covers how to train and fine-tune the BigIron-AI model on Apple Silicon.

## Overview

BigIron-AI is a fine-tuned version of Mistral-7B-Instruct, specialized for IBM mainframe expertise. The training pipeline runs entirely on Apple Silicon using MLX.

## Requirements

- **Hardware**: Apple Silicon Mac with 64GB+ unified memory
- **Software**:
  - Python 3.10+
  - mlx-lm (`pip install mlx-lm`)
  - llama.cpp (for GGUF conversion)
  - Ollama (for serving the model)

## Quick Start

```bash
# Build the full fine-tuned model
./scripts/training/build_bigiron_ai.sh
```

This runs the complete pipeline:
1. Merges all training data
2. Runs fine-tuning (high-rank LoRA across all 32 layers)
3. Fuses weights into base model
4. Converts to GGUF format
5. Registers with Ollama

## Training Data

Training data is stored in `data/training/`:

```
data/training/
├── mlx_data/
│   ├── train.jsonl      # Main training set
│   └── valid.jsonl      # Validation set (10%)
├── examples/            # Additional code examples
│   ├── cobol_*.jsonl
│   ├── jcl_*.jsonl
│   ├── cics_*.jsonl
│   └── ...
└── generated/           # Auto-generated Q&A from Redbooks
    └── full_qa.jsonl
```

### Data Format

Training samples use chat format:

```json
{
  "messages": [
    {"role": "user", "content": "How do I define a VSAM KSDS?"},
    {"role": "assistant", "content": "Here's how to define a VSAM KSDS..."}
  ]
}
```

Or Q&A format (auto-converted):

```json
{
  "question": "What is RACF?",
  "answer": "RACF (Resource Access Control Facility) is..."
}
```

## Training Scripts

### `build_bigiron_ai.sh` - Full Training Pipeline

The main script for building BigIron-AI.

```bash
# Default: 3 epochs
./scripts/training/build_bigiron_ai.sh

# Custom epochs
./scripts/training/build_bigiron_ai.sh --epochs 5

# Resume from checkpoint
./scripts/training/build_bigiron_ai.sh --resume
```

**What it does:**
1. Checks system requirements (RAM, dependencies)
2. Merges training data from `examples/` into main dataset
3. Runs fine-tuning with high-rank LoRA (rank 64, 32 layers)
4. Fuses trained weights into base Mistral model
5. Converts fused model to GGUF format
6. Creates Ollama Modelfile and registers the model

**Output:**
- `data/training/bigiron-ai.gguf` - The fine-tuned model
- `configs/ollama/Modelfile.bigiron-ai` - Ollama configuration

### `mlx_finetune.py` - Low-Rank Fine-Tuning (Legacy)

Basic LoRA fine-tuning for quick experiments.

```bash
# Convert data and train
python scripts/training/mlx_finetune.py --iters 1000

# Train only (data already converted)
python scripts/training/mlx_finetune.py --train-only --iters 2000

# Fuse adapter into model
python scripts/training/mlx_finetune.py --fuse
```

### Data Generation Scripts

**`fetch_redbooks.py`** - Download IBM Redbooks PDFs

```bash
python scripts/training/fetch_redbooks.py --max-per-topic 10
```

**`generate_qa_from_rag.py`** - Generate Q&A from indexed content

```bash
python scripts/training/generate_qa_from_rag.py --limit 5000
```

**`validate_jsonl.py`** - Validate training data format

```bash
python scripts/training/validate_jsonl.py data/training/mlx_data/train.jsonl
```

## Model Architecture

BigIron-AI uses Mistral-7B-Instruct as the base model with:

- **Fine-tuning approach**: High-rank LoRA (rank 64) across all 32 transformer layers
- **Training data**: 8,000+ Q&A pairs from IBM Redbooks + 300+ code examples
- **Context length**: 4096 tokens
- **Precision**: FP16

This approximates full fine-tuning while remaining memory-efficient on Apple Silicon.

## Output Models

After training, you'll have:

| File | Description |
|------|-------------|
| `data/training/bigiron_full/adapters/` | Trained LoRA adapters |
| `data/training/bigiron_full/fused/` | Fused HuggingFace model |
| `data/training/bigiron-ai.gguf` | Ollama-ready GGUF model |

## Using the Model

After training, start the application:

```bash
./start.sh
```

This automatically loads `bigiron-ai` if the GGUF exists, or falls back to base Mistral.

### Manual Ollama Commands

```bash
# Create/update the model
ollama create bigiron-ai -f configs/ollama/Modelfile.bigiron-ai

# Test the model
ollama run bigiron-ai "Write JCL to copy a dataset"

# List models
ollama list
```

## Troubleshooting

### Out of Memory

If training runs out of memory:
- Reduce `--batch-size` to 1
- Increase `--grad-accum` to compensate
- Close other applications

### Training Too Slow

- Ensure no other heavy processes are running
- Check Activity Monitor for memory pressure
- Consider reducing `--epochs`

### Model Quality Issues

If the model isn't answering well:
- Add more domain-specific examples to `data/training/examples/`
- Increase training epochs
- Review training data quality with `validate_jsonl.py`

## Adding Training Data

1. Create a JSONL file in `data/training/examples/`:

```bash
# Example: data/training/examples/my_examples.jsonl
{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```

2. Run the build script - it auto-merges examples:

```bash
./scripts/training/build_bigiron_ai.sh
```

## Hardware Notes

**Memory Usage** (approximate):
- Model weights: ~14GB
- Optimizer states: ~28GB
- Gradients: ~14GB
- Activations: varies

Total: ~50-60GB for full fine-tuning

**Training Time** (M2 Max 64GB):
- 1 epoch (~8000 samples): ~2-3 hours
- Full training (3 epochs): ~6-9 hours
