# BigIron-AI Project

Mainframe AI assistant built on Apple Silicon. Fine-tuned 7B model specialized in z/OS, COBOL, JCL, CICS, RACF, DB2, VSAM, and REXX.

## Quick Start

```bash
./start.sh
```

## Project Structure

| Directory | Purpose |
|-----------|---------|
| `app/` | FastAPI web interface |
| `configs/ollama/` | Ollama Modelfile (bigironv2) |
| `data/training/examples/` | Curated JSONL training examples (86 total) |
| `data/training/mlx_data/` | Processed train/valid splits |
| `scripts/training/` | Build and training scripts |
| `tk5/` | TK5 MVS 3.8j emulator for RLVR |

## Current Model

**Active:** `bigironv2` - LoRA fine-tuned Mistral-7B (86 curated examples, Q8 quantization)

```bash
# Register with Ollama
ollama create bigironv2 -f configs/ollama/Modelfile.bigironv2

# Test
ollama run bigironv2 "What is RACF?"
```

## Training

```bash
# Full retrain
./scripts/training/build_bigiron_ai.sh --epochs 5

# Resume from checkpoint
./scripts/training/build_bigiron_ai.sh --resume
```

Uses Python 3.12 environment (`.venv-train/`) for MLX compatibility.

## Adding Training Data

1. Add JSONL to `data/training/examples/`
2. Format: `{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}`
3. Run `./scripts/training/build_bigiron_ai.sh`

## Key Files

- `data/training/bigiron-v2.gguf` - The model (7.2GB)
- `configs/ollama/Modelfile.bigironv2` - Ollama config
- `scripts/training/build_bigiron_ai.sh` - Training pipeline

## Training Data

| Category | File | Examples |
|----------|------|----------|
| JCL | `jcl_curated.jsonl` | 20 |
| COBOL | `cobol_curated.jsonl` | 15 |
| CICS | `cics_curated.jsonl` | 10 |
| REXX | `rexx_curated.jsonl` | 10 |
| RACF | `racf_curated.jsonl` | 12 |
| DB2 | `db2_curated.jsonl` | 9 |
| z/OS | `zos_knowledge.jsonl` | 10 |

## Docs

- `docs/WHITEPAPER.md` - Full technical whitepaper
- `docs/BIGIRON_AI.md` - Model architecture
- `docs/TRAINING.md` - Training guide
