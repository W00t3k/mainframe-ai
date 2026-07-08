# BigIron-AI Project

Mainframe AI assistant built on Apple Silicon. Fine-tuned 7B model specialized in z/OS, COBOL, JCL, CICS, RACF, DB2, and VSAM.

## Quick Start

```bash
./start.sh
```

## Project Structure

| Directory | Purpose |
|-----------|---------|
| `app/` | FastAPI web interface |
| `configs/ollama/` | Ollama Modelfiles |
| `data/training/` | Training data and model outputs |
| `data/training/examples/` | JSONL training examples |
| `scripts/training/` | Build and training scripts |
| `tk5/` | TK5 MVS 3.8j emulator |

## Models

**Active:** `bigiron-ai` - Full fine-tuned Mistral-7B (15 epochs, 6,210 samples)

```bash
# Register with Ollama
ollama create bigiron-ai -f configs/ollama/Modelfile.bigiron-ai

# Test
ollama run bigiron-ai "What is RACF?"
```

## Training

```bash
# Retrain with more epochs
./scripts/training/build_bigiron_ai.sh --epochs 20

# Resume from checkpoint
./scripts/training/build_bigiron_ai.sh --resume
```

Uses Python 3.12 environment (`.venv-train/`) for MLX compatibility.

## Adding Training Data

1. Add JSONL to `data/training/examples/`
2. Format: `{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}`
3. Run `./scripts/training/build_bigiron_ai.sh`

## Key Files

- `data/training/bigiron-ai.gguf` - The model (14GB)
- `configs/ollama/Modelfile.bigiron-ai` - Ollama config
- `scripts/training/build_bigiron_ai.sh` - Training pipeline

## Docs

- `docs/BIGIRON_AI.md` - Model architecture and capabilities
- `docs/TRAINING.md` - Training guide
- `docs/EXTERNAL_DATASETS.md` - Available datasets
