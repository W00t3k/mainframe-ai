# BigIron-AI: Mainframe Expert Model

A fully fine-tuned 7B parameter LLM specialized in IBM mainframe technology, built on Apple Silicon.

## Overview

BigIron-AI is a fine-tuned version of Mistral-7B-Instruct, trained on 6,200+ mainframe Q&A pairs and code examples. It speaks plain English while maintaining deep expertise in z/OS, COBOL, JCL, CICS, RACF, DB2, VSAM, and related technologies.

## Model Details

| Property | Value |
|----------|-------|
| Base Model | Mistral-7B-Instruct-v0.3 |
| Parameters | 7.2B total, 3.5B trained (48%) |
| Training Method | High-rank LoRA (rank 64, 32 layers) |
| Training Data | 6,210 samples |
| Epochs | 15 |
| Iterations | 11,643 |
| Final Val Loss | ~1.5 (target) |
| Format | GGUF (F16) |
| Size | ~14GB |

## Training Data Sources

1. **IBM Redbooks** - Automatically extracted Q&A from official IBM documentation
2. **Code Examples** - Hand-crafted examples covering:
   - COBOL (arithmetic, tables, copybooks, DB2, sorting, strings)
   - JCL (procedures, conditional execution, utilities)
   - CICS (BMS maps, file operations, interval control, queues)
   - REXX (OUTTRAP, LISTDSI, ISPF services, string functions)
   - RACF (user/group management, dataset protection, general resources)
   - Assembler (macros, SVCs, system programming)
   - VSAM (KSDS operations, IDCAMS)
   - DB2 (DDL, stored procedures)
   - JES2 (commands, spool management)
   - Utilities (DFSORT, IDCAMS, IEBCOPY, ADRDSSU)

## Personality

BigIron-AI is designed to be a friendly, approachable mainframe expert:

```
You are BigIron, a friendly mainframe expert. I know z/OS, COBOL, JCL,
CICS, RACF, DB2, VSAM, and all the technology that keeps banks, airlines,
and governments running.

I explain things in plain English. When you ask me something, I'll give
you a straight answer - no corporate jargon, no "please refer to the
manual" nonsense. If you need code, I'll write it. If you need an
explanation, I'll make it make sense.
```

## Files

| File | Purpose |
|------|---------|
| `data/training/bigiron-ai.gguf` | The fine-tuned model (GGUF format) |
| `configs/ollama/Modelfile.bigiron-ai` | Ollama configuration |
| `data/training/bigiron_full/weights/` | Training checkpoints |
| `data/training/bigiron_full/fused/` | Fused HuggingFace model |
| `data/training/mlx_data/` | Training data (train/valid/test splits) |

## Usage

### With start.sh (Recommended)

```bash
./start.sh
```

This automatically:
1. Starts Ollama
2. Loads bigiron-ai model
3. Starts the web interface
4. Connects to TK5 mainframe

### Manual Ollama Usage

```bash
# Register the model
ollama create bigiron-ai -f configs/ollama/Modelfile.bigiron-ai

# Run interactively
ollama run bigiron-ai

# Example queries
ollama run bigiron-ai "Write JCL to copy a PDS"
ollama run bigiron-ai "Explain RACF PERMIT command"
ollama run bigiron-ai "Debug S0C7 abend in COBOL"
```

## Training Pipeline

The model was built using `scripts/training/build_bigiron_ai.sh`:

1. **System Check** - Verifies 64GB+ RAM, mlx-lm, llama.cpp
2. **Data Preparation** - Merges examples, creates train/valid/test splits
3. **Fine-Tuning** - MLX LoRA training with high rank (approximates full fine-tuning)
4. **Fusion** - Merges trained weights into base model
5. **GGUF Conversion** - Converts to Ollama-compatible format
6. **Registration** - Creates Modelfile and registers with Ollama

### Retraining

To retrain with different parameters:

```bash
# More epochs
./scripts/training/build_bigiron_ai.sh --epochs 20

# Resume from checkpoint
./scripts/training/build_bigiron_ai.sh --resume

# Custom batch size
./scripts/training/build_bigiron_ai.sh --batch-size 2
```

## Training Environment

A separate Python 3.12 virtual environment is used for training due to compatibility issues with newer Python versions:

```bash
# Training environment
.venv-train/bin/python  # Python 3.12 with mlx-lm

# Application environment
.venv/bin/python        # Python 3.14 for web app
```

## Performance

Training metrics from a typical run:

| Metric | Start | End |
|--------|-------|-----|
| Train Loss | 6.1 | 1.5-1.8 |
| Val Loss | 4.7 | 1.5-1.9 |
| Memory | 32GB | 39GB peak |
| Speed | 2 it/sec | - |

## Capabilities

BigIron-AI excels at:

- Writing complete, working code (COBOL, JCL, REXX, Assembler)
- Explaining mainframe concepts in plain English
- Debugging common abend codes (S0C7, S0C4, S322, etc.)
- RACF security configuration
- JES2/JES3 job management
- VSAM file operations
- CICS application development
- DB2 database queries and administration
- Utility usage (IDCAMS, DFSORT, IEBCOPY, etc.)

## Limitations

- Based on publicly available IBM documentation
- May not cover proprietary vendor extensions
- Code examples should be reviewed before production use
- Does not have access to live mainframe systems during inference

## License

The fine-tuned model inherits licensing from:
- Mistral-7B-Instruct (Apache 2.0)
- Training data derived from IBM Redbooks (fair use for training)

## Advanced: RLVR Training

After SFT, you can run RLVR (Reinforcement Learning with Verifiable Rewards) to improve code generation:

```bash
# Run RLVR training (requires TK5 for verification)
./scripts/training/run_rlvr.sh --steps 500
```

RLVR trains the model through trial-and-error:
1. Generate JCL/COBOL dynamically
2. Submit to TK5 MVS for execution
3. Reward based on success (CC 0000 = perfect)
4. Update model via GRPO

See `docs/RLVR_TRAINING.md` for details.

## Version History

| Version | Date | Changes |
|---------|------|---------|
| bigiron-ai | 2024-07 | Full fine-tuning, 15 epochs, plain English personality |
| bigiron-v4 | 2024-07 | LoRA fine-tuning, 5000 iterations |
| bigiron-v3 | 2024-06 | Initial LoRA experiments |
