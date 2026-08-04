# RLVR Training for BigIron-AI

Reinforcement Learning with Verifiable Rewards (RLVR) training for BigIron-AI, inspired by the [Outflank Dante-7B approach](https://www.outflank.nl/blog/2025/08/07/training-specialist-models/).

## Overview

RLVR allows the model to learn through trial-and-error rather than just from examples. The model generates code, we verify it on TK5 MVS, and use the results as rewards for training.

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Prompt Generator│────▶│   LLM (BigIron) │────▶│   TK5 Verifier  │
│ (non-deterministic)   │                 │     │                 │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                        ┌─────────────────┐              │
                        │  GRPO Training  │◀─────────────┘
                        │  (reward update)│     (reward: 0-5)
                        └─────────────────┘
```

## Training Pipeline

### 1. SFT (Supervised Fine-Tuning) - What we already do
- Train on 120k+ examples
- Model learns format and domain knowledge
- Run: `./scripts/training/build_bigiron_ai.sh`

### 2. RLVR (Reinforcement Learning) - New capability
- Model generates JCL/COBOL
- TK5 verifies execution
- GRPO updates model based on rewards
- Run: `./scripts/training/run_rlvr.sh`

## Quick Start

```bash
# Ensure TK5 is running (optional but recommended)
./start.sh &

# Run RLVR training
./scripts/training/run_rlvr.sh --steps 500

# Or dry run to test
./scripts/training/run_rlvr.sh --dry-run
```

## Components

### Prompt Generator (`rlvr_agent.py`)

Generates non-deterministic prompts from templates:

```python
from rlvr_agent import PromptGenerator

gen = PromptGenerator()
prompts = gen.generate(n=10, difficulty_range=(1, 5))

# Output:
# [2] vsam: Write JCL to define a VSAM KSDS
# [3] cobol_file: Write a COBOL program that reads multiple files
# [1] jcl_utility: create a job that will copy a dataset using IEBGENER
```

Task categories:
- `jcl_utility` (difficulty 1): IEBGENER, IEBCOPY, IDCAMS basics
- `vsam` (difficulty 2): VSAM cluster operations
- `sort` (difficulty 2): DFSORT/SYNCSORT
- `jcl_control` (difficulty 3): COND, IF/THEN, procedures
- `cobol_basic` (difficulty 2): Simple COBOL programs
- `cobol_file` (difficulty 3): COBOL file I/O
- `cobol_table` (difficulty 4): COBOL tables and arrays

### TK5 Verifier (`tk5_verifier.py`)

Verifies LLM output by executing on TK5:

```python
from tk5_verifier import TK5Verifier

verifier = TK5Verifier()
result = verifier.verify(llm_output, task_type="jcl")

# result.reward: 0-5 scale
# result.success: bool
# result.condition_code: 0=success, 999=abend
```

Reward structure:
| Reward | Meaning |
|--------|---------|
| 0 | Invalid output format |
| 1 | Parseable but JCL error |
| 1.5 | Submitted but timeout |
| 2 | Serious errors |
| 3 | Errors but completed |
| 4 | Warnings |
| 5 | Perfect (CC 0000) |

### GRPO Trainer (`rlvr_train.py`)

Uses TRL's GRPO implementation:

```bash
python scripts/training/rlvr_train.py \
    --steps 500 \
    --batch-size 4 \
    --lr 1e-6
```

Options:
- `--steps N`: Training steps (default 500)
- `--batch-size N`: Prompts per batch (default 4)
- `--no-tk5`: Use heuristic rewards (no TK5 required)
- `--dry-run`: Test without actual training

## Hardware Requirements

| Mode | Memory | Time (500 steps) |
|------|--------|------------------|
| TK5 verification | 32GB+ | ~4-6 hours |
| Heuristic mode | 16GB+ | ~2-3 hours |

Apple Silicon (M1/M2/M3) supported via MPS backend.

## Expected Results

Based on Outflank's research with similar architecture:

| Metric | Before RLVR | After RLVR |
|--------|-------------|------------|
| JCL syntax correct | ~70% | ~90% |
| Executes without error | ~40% | ~70% |
| Perfect CC 0000 | ~20% | ~50% |

## Configuration

Edit `RLVRConfig` in `rlvr_train.py`:

```python
@dataclass
class RLVRConfig:
    model_name_or_path: str = "mistralai/Mistral-7B-v0.1"
    max_steps: int = 500
    batch_size: int = 4
    generations_per_prompt: int = 4  # Multiple attempts per prompt
    learning_rate: float = 1e-6
    temperature: float = 0.8         # Higher = more exploration
    verify_on_tk5: bool = True
```

## Extending

### Add new task templates

Edit `TASK_TEMPLATES` in `rlvr_agent.py`:

```python
TaskTemplate(
    category=TaskCategory.VSAM,
    base_prompt="Write JCL to {action} a VSAM {cluster_type}",
    parameters={
        "action": ["define", "delete", "repro"],
        "cluster_type": ["KSDS", "ESDS", "RRDS"],
    },
    difficulty=2
)
```

### Add new verification types

Extend `TK5Verifier` in `tk5_verifier.py`:

```python
def verify_rexx(self, rexx_code: str) -> VerifyResult:
    # Submit REXX via TSO
    # Check output
    # Return reward
```

## References

- [Outflank: Training Specialist Models](https://www.outflank.nl/blog/2025/08/07/training-specialist-models/)
- [DeepSeek R1 Paper](https://arxiv.org/abs/2501.12948)
- [TRL GRPO Documentation](https://huggingface.co/docs/trl/grpo_trainer)
- [Open R1 Framework](https://github.com/huggingface/open-r1)
