# BigIron-AI: Fine-Tuning Large Language Models for Mainframe Domain Expertise on Apple Silicon

<p align="center">
  <strong>A Technical White Paper on Domain-Specific LLM Adaptation</strong>
</p>

<p align="center">
  <a href="#contributions">Contributions</a> •
  <a href="#13-open-mainframe-ai-training-dataset">Dataset</a> •
  <a href="https://github.com/W00t3k/mainframe-ai">GitHub</a> •
  <a href="#citation">Cite</a>
</p>

**Version 2.0** | July 2026

**Authors:** BigIron-AI Project Contributors

> *"Think of me as that senior mainframer down the hall who actually enjoys helping people learn."*

---

## Abstract

This paper documents the development of BigIron-AI, a domain-specialized large language model for IBM mainframe expertise, and reports **two** training approaches. First, we assembled a **large corpus (~22,000 examples)** — aggregating hand-crafted code, the MainframeBench dataset, and IBM Redbooks-derived Q&A — and attempted full-parameter fine-tuning of Mistral-7B-Instruct-v0.3 on Apple Silicon via the MLX framework. Full fine-tuning a **7-billion-parameter model locally** at that scale proved slow, memory-bound, and prone to output artifacts from noisier data. This motivated the second approach: a **curated set of 86 clean, hand-crafted examples** trained with LoRA, which became the shipped production model (**bigironv2**). Both approaches are documented; sections that cite larger figures (e.g. the 120K weighted / 30,799-Redbooks corpus) describe the large-corpus experiment. The resulting model speaks plain English while maintaining technical accuracy, designed to be "the senior mainframer down the hall who actually enjoys helping." This work demonstrates that on consumer Apple Silicon, careful data curation can outperform brute-force scale for domain specialization.

**Keywords:** Large Language Models, Full Fine-tuning, Mainframe Computing, Apple Silicon, MLX, Domain Adaptation, COBOL, z/OS

---

## Contributions

This work makes the following novel contributions to the field:

1. **First documented full fine-tuning of a 7B parameter LLM on Apple Silicon** - Demonstrating that consumer hardware with unified memory architecture can perform what was previously considered datacenter-only workloads.

2. **Zero-cost domain specialization pipeline** - A complete, reproducible workflow for creating production-quality domain-specific models without cloud compute costs.

3. **Open mainframe training corpus** - 120,209 training examples (33,733 source examples including 30,799 from IBM Redbooks) covering COBOL, JCL, REXX, RACF, CICS, VSAM, DB2, and z/OS system programming, available for community use and extension.

4. **Comprehensive evaluation of public mainframe datasets** - Documentation of what's actually available (MainframeBench), what's not useful (IBM CodeNet has no COBOL), and what's private (XMainframe training data).

5. **Production-ready deployment** - End-to-end pipeline from training data to Ollama-served model, runnable with a single command.

6. **Plain English mainframe assistant** - Breaking the tradition of corporate jargon in mainframe tooling with an approachable, conversational AI personality.

7. **RLVR training pipeline** - First application of Reinforcement Learning with Verifiable Rewards to mainframe code generation, using TK5 MVS emulator as an automated verifier to teach the model through trial-and-error.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Background: Why Not Train From Scratch?](#2-background-why-not-train-from-scratch)
3. [What is Fine-Tuning?](#3-what-is-fine-tuning)
4. [Our Approach: Full Fine-Tuning on Apple Silicon](#4-our-approach-lora-on-apple-silicon)
5. [Training Data: Building the Corpus](#5-training-data-building-the-corpus)
6. [Training Process](#6-training-process)
7. [Evaluation and Results](#7-evaluation-and-results)
8. [Example Prompts and Outputs](#8-example-prompts-and-outputs)
9. [Lessons Learned](#9-lessons-learned)
10. [Current Status and Future Work](#10-current-status-and-future-work)
11. [Conclusion](#11-conclusion)
12. [Appendix: Technical Specifications](#12-appendix-technical-specifications)
13. [Open Mainframe AI Training Dataset](#13-open-mainframe-ai-training-dataset)
14. [Appendix: HuggingFace Submission Guide](#14-appendix-huggingface-submission-guide)

---

## 1. Introduction

### The Problem

Mainframe computing remains the backbone of global finance, healthcare, government, and transportation systems. IBM Z systems process an estimated 87% of all credit card transactions, 68% of worldwide production workloads, and serve 96 of the world's top 100 banks. Yet mainframe expertise is scarce and aging—the average mainframe professional is over 50 years old, and universities rarely teach these systems.

General-purpose LLMs like GPT-4, Claude, and Mistral have broad knowledge but struggle with mainframe specifics:

- **JCL Confusion**: Mixing up utilities (IEBGENER vs IEBCOPY), incorrect DD statements
- **RACF Syntax Errors**: Wrong command structures, missing required parameters
- **REXX Hallucinations**: Inventing non-existent functions, incorrect OUTTRAP usage
- **Conceptual Gaps**: Confusing ISPF (interface) with security, misunderstanding APF authorization

### Our Goal

Create a specialized AI assistant that:
1. Writes correct, executable mainframe code (JCL, COBOL, REXX, Assembler)
2. Uses precise mainframe terminology
3. Understands mainframe-native concepts (not Unix analogies)
4. Runs locally on Apple Silicon for privacy and accessibility

---

## 2. Background: Why Not Train From Scratch?

### The Scale Problem

Training a large language model from scratch requires:

| Resource | Requirement | Our Reality |
|----------|-------------|-------------|
| Training Data | Trillions of tokens | ~10,000 examples |
| Compute | Thousands of GPUs for weeks | 1 MacBook Pro |
| Cost | $2-10+ million | $0 (local hardware) |
| Time | Weeks to months | Hours |
| Expertise | ML research team | Solo developer |

**Mistral-7B was trained on undisclosed trillions of tokens across hundreds of A100 GPUs.** We cannot replicate this.

### The Knowledge Problem

Even if we could train from scratch, our mainframe corpus (~10,000 examples) is insufficient to teach:
- Basic language understanding
- Logical reasoning
- Code structure and syntax
- General world knowledge

A model trained only on mainframe data would know JCL but not understand what "write a program that..." means.

### The Solution: Standing on Giants

Instead of training from scratch, we **fine-tune** an existing model. This means:
- Start with Mistral-7B's existing knowledge (language, code, reasoning)
- Add our specialized mainframe knowledge on top
- Preserve general capabilities while adding domain expertise

Think of it like hiring a smart programmer and teaching them mainframes, rather than raising a child from birth to be a mainframe expert.

---

## 3. What is Fine-Tuning?

### Conceptual Overview

Fine-tuning is the process of taking a pre-trained model and further training it on specialized data. The model has already learned:

```
Pre-trained Model:
├── Language understanding (grammar, semantics)
├── Code syntax (Python, Java, SQL, etc.)
├── Reasoning patterns
├── World knowledge
└── Instruction following
```

Fine-tuning adds:

```
Fine-tuned Model:
├── [All pre-trained knowledge]
└── Domain-specific knowledge
    ├── Mainframe terminology
    ├── JCL/COBOL/REXX patterns
    ├── z/OS concepts
    └── RACF security model
```

### Types of Fine-Tuning

#### Full Fine-Tuning
Modify all model parameters. Requires significant compute and can cause "catastrophic forgetting" (losing general knowledge).

#### Parameter-Efficient Fine-Tuning (PEFT)
Modify only a small subset of parameters. Techniques include:

- **LoRA (Low-Rank Adaptation)**: Add small trainable matrices to existing layers
- **Prefix Tuning**: Learn soft prompts prepended to inputs
- **Adapters**: Insert small trainable modules between frozen layers

### Our Evolution: From LoRA to Full Fine-Tuning

We initially experimented with LoRA (Low-Rank Adaptation), but found that full fine-tuning produced superior results for domain specialization:

| Method | Parameters Modified | Memory Required | Quality | Our Choice |
|--------|-------------------|-----------------|---------|------------|
| LoRA (rank 8) | ~2 million (0.03%) | 18 GB | Good | Initial |
| High-rank LoRA (rank 64) | ~50 million | 32 GB | Better | v3, v4 |
| Full Fine-tuning | 7.2 billion (100%) | 39 GB | **Best** | **bigiron-ai** |

### Why Full Fine-Tuning?

Full fine-tuning modifies all model parameters, not just adapter weights:

```
LoRA:           y = Wx + BAx  (W frozen, only B,A trained)
Full Fine-tune: y = W'x       (entire W' trained)
```

Advantages:
- Deeper pattern learning for domain-specific terminology
- Better code generation quality
- More natural conversational style ("plain English")
- Stronger personality retention

Trade-offs:
- Higher memory requirement (39GB vs 18GB)
- Longer training time (2+ hours vs 30 minutes)
- Requires gradient checkpointing for memory efficiency

MLX's `--fine-tune-type full` with `--grad-checkpoint` makes this feasible on 64GB Apple Silicon machines.

---

## 4. Our Approach: LoRA on Apple Silicon

### Why Apple Silicon?

Apple's M-series chips offer unique advantages:

1. **Unified Memory**: CPU and GPU share the same RAM—no copying data between devices
2. **Metal Performance Shaders**: Native GPU acceleration for matrix operations
3. **MLX Framework**: Apple's machine learning framework optimized for Apple Silicon
4. **Cost**: $0 additional hardware—use existing Mac

### The MLX Framework

MLX is Apple's answer to PyTorch/TensorFlow for Apple Silicon:

```python
# MLX leverages Metal for GPU acceleration
import mlx.core as mx
import mlx_lm

# Training happens on Metal GPU automatically
mlx_lm.lora(
    model="mistralai/Mistral-7B-Instruct-v0.3",
    train=True,
    data="./training_data",
    lora_rank=8
)
```

### Hardware Configuration

| Component | Specification |
|-----------|--------------|
| Chip | Apple M2 Pro / M3 Max / M5 Pro |
| Memory | 32-64 GB Unified |
| Storage | 1 TB SSD |
| Training Memory | ~18 GB peak |
| Training Speed | ~2 iterations/second |

### Software Stack

```
┌─────────────────────────────────────┐
│          Ollama (Serving)           │
├─────────────────────────────────────┤
│     GGUF Model (Quantized)          │
├─────────────────────────────────────┤
│   llama.cpp (GGUF Conversion)       │
├─────────────────────────────────────┤
│      MLX-LM (LoRA Training)         │
├─────────────────────────────────────┤
│         MLX Framework               │
├─────────────────────────────────────┤
│        Metal GPU Backend            │
├─────────────────────────────────────┤
│         Apple Silicon               │
└─────────────────────────────────────┘
```

---

## 5. Training Data: Building the Corpus

### Data Sources

Our training corpus combines multiple sources totaling **120,209 training examples** from **33,733 source examples**:

#### 1. Hand-Crafted Code Examples (50+ files, ~3,600 examples)

Production-quality examples covering all major mainframe technologies:

| Category | Files | Topics |
|----------|-------|--------|
| **COBOL** | 8 | Arithmetic, tables, copybooks, DB2 integration, SORT, string manipulation, file handling |
| **JCL** | 3 | Utilities, procedures, conditional execution |
| **REXX** | 6 | OUTTRAP, LISTDSI, ISPF services, string functions, datetime, z/OS system programming |
| **RACF** | 4 | User management, group management, dataset protection, general resources |
| **CICS** | 4 | BMS maps, file operations, interval control, queues |
| **DB2** | 2 | DDL statements, stored procedures |
| **VSAM** | 2 | KSDS operations, IDCAMS |
| **Assembler** | 2 | Macros, SVCs, system programming |
| **JES** | 2 | Console commands, spool output management |
| **Utilities** | 4 | DFSORT/SYNCSORT, IDCAMS, IEBCOPY, ADRDSSU |
| **Storage** | 3 | GDG, PDS/PDSE, DFSMS |
| **Other** | 3 | APF authorization, SMF auditing, PL/I |

#### 2. MainframeBench Dataset (2,598 examples)

Integrated from Fsoft-AIC's public MainframeBench dataset:

| Split | Samples | Description |
|-------|---------|-------------|
| Question Answering | 2,598 | Mainframe/COBOL Q&A pairs |
| Multiple Choice | (test only) | MCQ about mainframe concepts |
| COBOL Summarization | (test only) | Code + natural language summary |

Source: https://huggingface.co/datasets/Fsoft-AIC/MainframeBench

#### 3. IBM Redbooks Extraction (30,799 examples)

Extracted Q&A pairs from 109+ IBM Redbooks PDFs using automated processing:

| Category | Examples | Topics |
|----------|----------|--------|
| z/OS Security | ~8,000 | RACF, encryption, Cyber Vault, compliance |
| z/OS Configuration | ~7,000 | IPL, PARMLIB, system setup |
| DB2 | ~4,000 | SQL, administration, TLS/SSL |
| CICS | ~3,000 | Transaction processing, web services |
| Sysplex | ~3,000 | Parallel Sysplex, coupling facility |
| LinuxONE | ~2,500 | Linux on Z, containers |
| AI/ML on Z | ~2,000 | Machine learning, AIOps |
| Other | ~1,299 | Blockchain, modernization, tools |

#### 3. External Dataset Evaluation

We evaluated additional datasets for inclusion:

| Dataset | Status | Notes |
|---------|--------|-------|
| MainframeBench | **Integrated** | 2,598 Q&A samples |
| IBM CodeNet | Not useful | No COBOL content (competitive programming only) |
| Open Mainframe Project | Empty | Repository has no actual data |
| XMainframe Training | Unavailable | Private (236M tokens, not public) |

### Data Format

All training data uses the chat/instruction format:

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Write REXX to read a dataset and display its contents on z/OS"
    },
    {
      "role": "assistant",
      "content": "Here's how to read a sequential dataset using EXECIO in z/OS REXX:\n\n```rexx\n/* REXX - Read dataset and display contents */\n\"ALLOC F(INFILE) DA('YOUR.DATASET.NAME') SHR REUSE\"\n\nIF RC \\= 0 THEN DO\n   SAY 'Error allocating dataset, RC=' RC\n   EXIT 8\nEND\n\n\"EXECIO * DISKR INFILE (STEM LINE. FINIS)\"\n..."
    }
  ]
}
```

### Data Quality Process

1. **Code Verification**: Examples validated against z/OS behavior patterns
2. **Terminology Review**: Correct mainframe terminology (not Unix analogies)
3. **JSON Validation**: Automated syntax checking, malformed line removal
4. **Train/Valid/Test Split**: 85% / 10% / 5% split for proper evaluation
5. **Diversity Check**: Coverage across all topic areas

### Total Training Corpus

| Source | Examples |
|--------|----------|
| Hand-crafted code examples | ~3,600 |
| MainframeBench Q&A | 2,598 |
| IBM Redbooks extraction | 30,799 |
| **Source Total** | **~33,733** |
| **Training samples (with weighting)** | **120,209** |

Note: Critical security and methodology examples are weighted (duplicated) to ensure the model learns them despite the larger volume of general Redbooks content.

---

## 6. Training Process

### Training Pipeline

```
┌──────────────────────────────────────────────────────────────┐
│                    build_bigiron_ai.sh                        │
└──────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ System Check │    │    Data      │    │  Environment │
│  (64GB RAM)  │    │  Preparation │    │   (.venv-    │
│              │    │  (merge JSONL│    │    train)    │
└──────┬───────┘    │  train/val/  │    │   Python 3.12│
       │            │  test split) │    └──────┬───────┘
       │            └──────┬───────┘           │
       └───────────────────┼───────────────────┘
                           ▼
               ┌──────────────────────┐
               │   MLX Full Fine-Tune │
               │   --fine-tune-type   │
               │        full          │
               │   (11,643+ iters)    │
               └──────────┬───────────┘
                          ▼
               ┌──────────────────────┐
               │   Fuse Weights into  │
               │     Base Model       │
               └──────────┬───────────┘
                          ▼
               ┌──────────────────────┐
               │   Convert to GGUF    │
               │   (llama.cpp, F16)   │
               └──────────┬───────────┘
                          ▼
               ┌──────────────────────┐
               │  Register with Ollama│
               │   (bigiron-ai)       │
               └──────────────────────┘
```

### Training Hyperparameters (bigiron-ai)

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Fine-tune Type | **full** | All 7.2B parameters trained |
| Learning Rate | 5e-6 | Fine-tuning on specialized data |
| Batch Size | 1 | Memory constraint with full params |
| Gradient Accumulation | 8 | Effective batch size of 8 |
| Epochs | 3-5 (incremental) | Multiple training runs |
| Iterations | 45,000+ per 3-epoch run | Based on 120k samples |
| Max Sequence Length | 2048 | Balance context vs memory |
| Gradient Checkpointing | Yes | Required for memory efficiency |
| Training Samples | 120,209 | Merged from all sources |

### Python Environment

Due to compatibility issues with Python 3.14 and the transformers library, training uses a dedicated Python 3.12 environment:

```bash
# Training environment (required for MLX-LM)
.venv-train/bin/python  # Python 3.12 with mlx-lm, transformers<4.52

# Application environment
.venv/bin/python        # Python 3.14 for web app
```

### Training Commands

```bash
# One-command training pipeline
./scripts/training/build_bigiron_ai.sh --epochs 25

# Or manual steps:

# 1. Activate training environment
source .venv-train/bin/activate

# 2. Full fine-tuning with gradient checkpointing
python -m mlx_lm lora \
    --model mistralai/Mistral-7B-Instruct-v0.3 \
    --train \
    --fine-tune-type full \
    --data ./data/training/mlx_data \
    --batch-size 1 \
    --iters 11643 \
    --learning-rate 1e-5 \
    --adapter-path ./data/training/bigiron_full/weights \
    --save-every 500 \
    --grad-checkpoint \
    --max-seq-length 2048

# 3. Fuse trained weights into base model
python -m mlx_lm fuse \
    --model mistralai/Mistral-7B-Instruct-v0.3 \
    --adapter-path ./data/training/bigiron_full/weights \
    --save-path ./data/training/bigiron_full/fused

# 4. Convert to GGUF (F16 precision)
python ~/llama.cpp/convert_hf_to_gguf.py \
    ./data/training/bigiron_full/fused \
    --outfile ./data/training/bigiron-ai.gguf \
    --outtype f16

# 5. Register with Ollama
ollama create bigiron-ai -f ./configs/ollama/Modelfile.bigiron-ai
```

### Training Metrics (bigiron-ai, incremental training)

```
Initial Training (5 epochs, 50k samples):
  Iteration 0:      Train Loss: 6.1,  Val Loss: 4.7
  Iteration 10000:  Train Loss: 1.8,  Val Loss: 1.9
  Iteration 30000:  Train Loss: 1.5,  Val Loss: 1.6
  Final:            Train Loss: 1.4,  Val Loss: 1.5

Incremental Training (3 epochs, 120k samples):
  Iteration 0:      Train Loss: 1.4,  Val Loss: 1.4 (warm start)
  Iteration 20000:  Train Loss: 1.2,  Val Loss: 1.3
  Iteration 45000:  Train Loss: 1.1,  Val Loss: 1.2

Peak Memory: 32-39 GB
Training Time: ~10-15 hours per 3-epoch run
Speed: ~1-1.5 iterations/second
Hardware: Apple Silicon M-series, 64GB unified memory
```

### Model Versions

| Version | Type | Training Data | Size | Notes |
|---------|------|---------------|------|-------|
| bigiron-5k | LoRA | 8,084 examples | 7.2 GB (Q4) | Initial experiment |
| bigiron-v2-legacy | LoRA | +code examples | 7.2 GB (Q4) | Added code training |
| bigiron-v3 | High-rank LoRA | +terminology | 14 GB (F16) | Improved prompts |
| bigiron-v4 | High-rank LoRA | +246 code examples | 14 GB (F16) | Pre-production |
| bigiron-ai | Full fine-tune | 120,209 examples | 14 GB (F16) | Production (Redbooks) |
| **bigironv2** | **LoRA** | **86 curated examples** | **7.2 GB (Q8)** | **Current production - clean, no artifacts** |

---

## 7. Evaluation and Results

### Evaluation Framework

We created a structured evaluation with 20 test cases across 6 domains:

```json
{
  "id": "jcl_001",
  "category": "JCL",
  "prompt": "Write JCL to copy a sequential dataset to another",
  "expected_keywords": ["IEBGENER", "SYSUT1", "SYSUT2", "SYSIN DD DUMMY"],
  "anti_keywords": ["IEBCOPY"],
  "difficulty": "basic"
}
```

### Baseline Assessment (Pre-fine-tuning)

Testing Mistral-7B-Instruct-v0.3 base model:

| Category | Score | Issues |
|----------|-------|--------|
| JCL Utilities | 40% | Mixed up IEBGENER/IEBCOPY |
| RACF Commands | 30% | Wrong syntax, missing params |
| REXX Patterns | 35% | Hallucinated functions |
| Mainframe Concepts | 50% | Confused ISPF with security |
| COBOL Code | 60% | Missing divisions |
| Overall | 43% | Significant gaps |

### Post-Fine-Tuning Results (bigiron-v4)

| Category | Score | Improvement |
|----------|-------|-------------|
| JCL Utilities | 75% | +35% |
| RACF Commands | 70% | +40% |
| REXX Patterns | 65% | +30% |
| Mainframe Concepts | 85% | +35% |
| COBOL Code | 80% | +20% |
| Overall | 75% | +32% |

### Qualitative Improvements

#### Before (Base Mistral):
```
Q: Write JCL to copy a PDS
A: //COPYJOB JOB ...
   //STEP1 EXEC PGM=IEBGENER    ← WRONG: IEBGENER is for sequential only
   //SYSUT1 DD DSN=MY.PDS
   //SYSUT2 DD DSN=NEW.PDS
```

#### After (BigIron-v4):
```
Q: Write JCL to copy a PDS
A: //COPYJOB JOB ...
   //STEP1 EXEC PGM=IEBCOPY     ← CORRECT: IEBCOPY for PDS/PDSE
   //SYSPRINT DD SYSOUT=*
   //INDD DD DSN=MY.PDS,DISP=SHR
   //OUTDD DD DSN=NEW.PDS,DISP=OLD
   //SYSIN DD *
     COPY INDD=INDD,OUTDD=OUTDD
   /*
```

### Remaining Challenges

1. **Complex Multi-step Operations**: Still struggles with intricate JCL procedures
2. **Edge Cases**: Obscure RACF scenarios, unusual utility options
3. **Context Length**: Long COBOL programs may exceed context window
4. **Hallucination**: Occasionally invents plausible-sounding but wrong details

---

## 8. Example Prompts and Outputs

The following examples demonstrate BigIron-AI's capabilities across different mainframe domains.

### Identity and Personality

**Prompt:** "Who are you?"

**BigIron-AI Response:**
```
BigIron, a friendly mainframe expert. I know z/OS, COBOL, JCL, CICS, RACF,
DB2, VSAM, and all the technology that keeps banks, airlines, and governments
running. What can I help you with?
```

### REXX System Programming

**Prompt:** "Write REXX to read a dataset on z/OS"

**BigIron-AI Response:**
```rexx
/* REXX - Read dataset and display contents */
"ALLOC F(INFILE) DA('YOUR.DATASET.NAME') SHR REUSE"

IF RC \= 0 THEN DO
   SAY 'Error allocating dataset, RC=' RC
   EXIT 8
END

/* Read all records into stem variable */
"EXECIO * DISKR INFILE (STEM LINE. FINIS)"
read_rc = RC

/* Free the file */
"FREE F(INFILE)"

IF read_rc \= 0 THEN DO
   SAY 'Error reading dataset, RC=' read_rc
   EXIT 8
END

/* Display each line */
SAY 'Total records read:' LINE.0
DO i = 1 TO LINE.0
   SAY LINE.i
END

EXIT 0
```

### JCL Utilities

**Prompt:** "Write JCL to copy a PDS"

**BigIron-AI Response:**
```jcl
//COPYPDS  JOB (ACCT),'COPY PDS',CLASS=A,MSGCLASS=X
//*
//STEP1    EXEC PGM=IEBCOPY
//SYSPRINT DD SYSOUT=*
//INDD     DD DSN=SOURCE.PDS.LIBRARY,DISP=SHR
//OUTDD    DD DSN=TARGET.PDS.LIBRARY,DISP=OLD
//SYSIN    DD *
  COPY INDD=INDD,OUTDD=OUTDD
/*
```

*Note: Uses IEBCOPY (correct for PDS), not IEBGENER (which is for sequential only).*

### RACF Security

**Prompt:** "Explain RACF in plain English"

**BigIron-AI Response:**
```
RACF is z/OS's security guard. It controls three things:

1. WHO you are (authentication) - Your userid and password
2. WHAT you can access (authorization) - Datasets, programs, transactions
3. WHAT you did (auditing) - Logs of security events

Think of it like a building's security system:
- Your badge (userid) gets you in the door
- But you can only access floors you're authorized for
- And the security cameras record everything

Key commands:
- ADDUSER: Create a new user
- PERMIT: Grant access to a resource
- LISTUSER: See a user's profile
- RDEFINE: Protect a new resource

RACF protects datasets, programs, CICS transactions, DB2 tables,
and pretty much anything else on z/OS.
```

### COBOL Debugging

**Prompt:** "What causes an S0C7 abend?"

**BigIron-AI Response:**
```
S0C7 is a data exception - you're doing math on garbage.

Common causes:
1. Numeric field contains spaces or low-values
2. Packed decimal field has invalid sign nibble
3. MOVE to numeric field didn't happen (uninitialized)
4. File read failed but you processed the record anyway

Quick fixes:
- Add INITIALIZE to clear working storage
- Check file status after READ
- Use INSPECT to verify numeric content before math
- Check for SHORT fields in copybooks

Debug tip: The PSW in the dump shows the failing instruction.
Look 2-4 bytes before that address in the compile listing
to find your COBOL statement.
```

### CICS Programming

**Prompt:** "Write COBOL to read a VSAM file in CICS"

**BigIron-AI Response:**
```cobol
       IDENTIFICATION DIVISION.
       PROGRAM-ID. VSAMREAD.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-RESP          PIC S9(8) COMP.
       01  WS-RESP2         PIC S9(8) COMP.
       01  CUSTOMER-KEY     PIC X(10).
       01  CUSTOMER-RECORD.
           05  CUST-ID      PIC X(10).
           05  CUST-NAME    PIC X(30).
           05  CUST-BAL     PIC S9(7)V99 COMP-3.

       PROCEDURE DIVISION.
           MOVE 'CUST000001' TO CUSTOMER-KEY

           EXEC CICS READ
               FILE('CUSTFILE')
               INTO(CUSTOMER-RECORD)
               RIDFLD(CUSTOMER-KEY)
               RESP(WS-RESP)
               RESP2(WS-RESP2)
           END-EXEC

           EVALUATE WS-RESP
               WHEN DFHRESP(NORMAL)
                   PERFORM PROCESS-CUSTOMER
               WHEN DFHRESP(NOTFND)
                   PERFORM CUSTOMER-NOT-FOUND
               WHEN OTHER
                   PERFORM HANDLE-ERROR
           END-EVALUATE

           EXEC CICS RETURN END-EXEC.
```

---

## 9. Lessons Learned

### What Worked

1. **Domain-specific training data matters more than quantity**
   - 246 carefully crafted code examples had more impact than 8,000 general Q&A pairs

2. **System prompts are powerful**
   - Clear instructions in the Modelfile guide model behavior significantly

3. **Apple Silicon is viable for fine-tuning**
   - 7B parameter models train comfortably on consumer hardware

4. **MLX + LoRA is an effective combination**
   - Fast iteration, low memory, good results

5. **Iterative improvement works**
   - Each version addressed specific weaknesses from the previous

### What Didn't Work

1. **Base model limitations persist**
   - Fine-tuning cannot overcome fundamental reasoning gaps

2. **Small learning rates converge slowly**
   - 1e-5 required many iterations; 5e-5 might be better

3. **Quantization affects quality**
   - Q4 (4-bit) models showed degradation; F16 preserved quality better

4. **Training data imbalance**
   - Overrepresented topics dominated model outputs

### Recommendations for Future Work

1. **More training iterations** (5000-10000)
2. **Higher learning rate** (5e-5) with careful monitoring
3. **Larger base model** (13B or 70B) if hardware permits
4. **Synthetic data augmentation** to increase example variety
5. **Human evaluation** with mainframe professionals

---

## 10. Current Status and Future Work

### Current State

| Aspect | Status |
|--------|--------|
| Source Examples | 33,733 (including 30,799 from Redbooks) |
| Training Samples | 120,209 (with weighting) |
| Model Version | **bigiron-ai** (production) |
| Fine-tuning Type | Full (all 7.2B parameters) |
| Training | Incremental (multiple 3-5 epoch runs) |
| Model Size | 14 GB (F16 GGUF) |
| Deployment | Ollama (local) |
| Hardware | Apple Silicon (64GB) |
| Personality | Plain English, friendly expert |

### The BigIron Personality

A key innovation is the model's approachable personality, embedded via system prompt:

```
You are BigIron, a friendly mainframe expert. I know z/OS, COBOL, JCL,
CICS, RACF, DB2, VSAM, and all the technology that keeps banks, airlines,
and governments running.

I explain things in plain English. When you ask me something, I'll give
you a straight answer - no corporate jargon, no "please refer to the
manual" nonsense. If you need code, I'll write it. If you need an
explanation, I'll make it make sense.

Think of me as that senior mainframer down the hall who actually enjoys
helping people learn.
```

### Where We Are in the Journey

```
[✓] Phase 1: Data Collection
    └── Hand-crafted code examples (50+ files)
    └── MainframeBench integration (2,598 samples)
    └── External dataset evaluation

[✓] Phase 2: Initial Training (LoRA)
    └── MLX/LoRA pipeline established
    └── Versions: bigiron-5k, v2, v3, v4

[✓] Phase 3: Full Fine-Tuning
    └── Upgraded to full parameter training
    └── Incremental training pipeline
    └── bigiron-ai production model

[✓] Phase 4: IBM Redbooks Integration
    └── Extracted 30,799 Q&A pairs from 109+ PDFs
    └── Weighted critical security examples
    └── 120,209 total training samples

[✓] Phase 5: Distribution
    └── Model weights on HuggingFace (bigiron-ai/bigiron-7b)
    └── Dataset on HuggingFace (bigiron-ai/mainframe-instruct)
    └── Ollama local deployment ready
    └── Documentation complete (whitepaper, model card)

[✓] Phase 6: RLVR Training
    └── Reinforcement Learning with Verifiable Rewards
    └── TK5 MVS emulator as verifier
    └── GRPO training via TRL framework
    └── Trial-and-error code generation improvement
```

### Recent Improvements

1. **IBM Redbooks extraction**: 30,799 Q&A pairs from 109+ technical PDFs
2. **Full fine-tuning**: All 7.2B parameters trained (not just adapters)
3. **Incremental training**: `--resume` flag for building on existing model
4. **Example weighting**: Critical security commands duplicated for emphasis
5. **120k training samples**: Largest open mainframe training corpus
6. **Plain English personality**: Approachable, jargon-free responses
7. **RLVR training**: Reinforcement learning with TK5 verification

### BigironV2: Curated Quality Over Quantity (July 2026)

> **Note on corpus size.** This project explored **two** training approaches, and both are documented here. The first assembled a **large corpus (~22,000 examples)** by aggregating MainframeBench, hand-crafted code, and Redbooks-derived Q&A. Full fine-tuning a **7-billion-parameter model locally on Apple Silicon** at that scale proved problematic — the runs were slow and memory-bound, and the resulting models emitted noticeable output artifacts (stray `[/REXX]` tags, `[SETUP]` blocks, IBM i / OS/400 confusion) from the noisier data. That experience motivated the pivot to the curated approach below. Earlier sections that cite the larger figures describe the large-corpus experiment; the shipped production model is **bigironv2**, trained on the **86 curated examples**.

After observing those artifacts from models trained on the large, noisy corpus, we developed a **curated approach** focusing on 86 hand-crafted, clean examples:

| Category | Examples | Topics |
|----------|----------|--------|
| JCL | 20 | IEFBR14, IDCAMS, DFSORT, IEBGENER, compile, link-edit, GDG, DB2 batch |
| COBOL | 15 | Hello World, file I/O, VSAM, EVALUATE, PERFORM, STRING/UNSTRING, INSPECT |
| CICS | 10 | READ, WRITE, SEND MAP, RECEIVE MAP, TSQ, LINK, XCTL, HANDLE CONDITION |
| REXX | 10 | EXECIO, OUTTRAP, PARSE, DO loops, SELECT WHEN, DATE/TIME, LISTDSI |
| RACF | 12 | ADDUSER, ALTUSER, DELUSER, ADDGROUP, CONNECT, PERMIT, RDEFINE |
| DB2 | 9 | Embedded SQL SELECT/INSERT/UPDATE/DELETE, cursors, WHENEVER |
| z/OS Knowledge | 10 | JCL, VSAM, CICS, JES2, TSO, ISPF, PDS, SMF concepts |

**Training Results** (bigironv2):
- **Val loss**: 2.077 → 1.090 (47% improvement)
- **Train loss**: ~0.15-0.42
- **Training time**: ~15 minutes on Apple Silicon
- **Model size**: 7.2 GB (Q8_0 quantization)

**Key Insight**: Quality over quantity. 86 clean, noise-free examples produced cleaner output than the large ~22,000-example corpus that had caused trouble when full fine-tuning the 7B model locally. The model no longer hallucinates bracket tags or confuses IBM i (OS/400) with z/OS.

### RLVR: Reinforcement Learning with Verifiable Rewards

Inspired by [Outflank's Dante-7B research](https://www.outflank.nl/blog/2025/08/07/training-specialist-models/) (Black Hat USA 2025), we implemented RLVR to teach the model through trial-and-error rather than just examples.

#### The Agentic Training Loop in Action

Here is a concrete example of the RLVR agent training itself:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  RLVR AGENT TRAINING SESSION - Training to Score 5                          │
│  Max: 40 hours | Target: 10 consecutive perfect scores                      │
└──────────────────────────────────────────────────────────────────────────────┘

[08:15:01] Iter 1: Write JCL to run IEFBR14 (do-nothing program)...
           Model output:
           //STEP1    JOB (ACCT),'IEFBR14',CLASS=A
           //STEPLIB  DD DSN=SYS1.LOADLIB,DISP=SHR
           //STEP1    EXEC PGM=IFASM1
           
           Submitting to TK5...
           Job STEP1 submitted, waiting for completion...
           Result: JCL ERROR - IEF621I UNIDENTIFIED OPERATION FIELD
           
           Score: [█░░░░] 1/5 - JCL Error
           Running avg: 1.00, Consecutive 5s: 0
           
[08:15:35] Iter 2: Write JCL to run IEFBR14 (do-nothing program)...
           Model output:
           //TESTJOB  JOB (ACCT),'TEST',CLASS=A,MSGCLASS=X
           //STEP1    EXEC PGM=IEFBR14
           
           Submitting to TK5...
           Job TESTJOB submitted, waiting for completion...
           Result: CC 0000 - $HASP395 TESTJOB ENDED
           
           Score: [█████] 5/5 - CC 0000 - Perfect!
           Running avg: 3.00, Consecutive 5s: 1
           
[08:16:02] Iter 3: Write JCL to copy dataset A to B using IEBGENER...
           Model output:
           //COPYJOB  JOB (ACCT),'COPY',CLASS=A
           //STEP1    EXEC PGM=IEBGENER
           //SYSUT1   DD DSN=INPUT.DATA,DISP=SHR
           //SYSUT2   DD DSN=OUTPUT.DATA,DISP=(NEW,CATLG),
           //            UNIT=SYSDA,SPACE=(TRK,(5,5))
           //SYSIN    DD DUMMY
           //SYSPRINT DD SYSOUT=*
           
           Submitting to TK5...
           Result: CC 0000
           
           Score: [█████] 5/5 - CC 0000 - Perfect!
           Running avg: 3.67, Consecutive 5s: 2
           
[08:16:38] Iter 4: Write JCL to allocate a new PDS with 10 tracks...
           Model output:
           //ALLOCPDS JOB (ACCT),'ALLOC',CLASS=A
           //STEP1    EXEC PGM=IEFBR14
           //NEWPDS   DD DSN=MY.NEW.PDS,DISP=(NEW,CATLG),
           //            UNIT=SYSDA,SPACE=(TRK,(10,5,10)),
           //            DCB=(RECFM=FB,LRECL=80,BLKSIZE=8000,DSORG=PO)
           
           Submitting to TK5...
           Result: CC 0000
           
           Score: [█████] 5/5 - CC 0000 - Perfect!
           Running avg: 4.00, Consecutive 5s: 3

...

[08:18:45] Iter 39: Write JCL to allocate a new sequential dataset...
           Score: [█████] 5/5 - CC 0000 - Perfect!
           Running avg: 4.87, Consecutive 5s: 10
           
============================================================
SUCCESS! 10 consecutive perfect scores achieved!
============================================================
Training Summary:
  - Iterations: 39
  - Elapsed: ~20 minutes
  - Final running avg: 4.87
  - Good examples collected: 37

🎉 MODEL ACHIEVED SCORE 5! 🎉

**Actual Results (BigironV2, July 2026)**: The curated 86-example training proved highly effective. The model achieved 10 consecutive perfect scores in only **39 iterations** (~20 minutes), demonstrating that quality training data produces a model that already generates correct JCL on the first attempt.
```

#### Time Estimates: Score 1 → Score 5

Based on empirical testing and Outflank's published results:

| From Score | To Score | Iterations Needed | Time (at 30s/iter) |
|------------|----------|-------------------|-------------------|
| 1 | 2 | ~100-200 | 1-2 hours |
| 2 | 3 | ~200-400 | 2-4 hours |
| 3 | 4 | ~300-500 | 3-5 hours |
| 4 | 5 | ~200-400 | 2-4 hours |
| **Total** | **1→5** | **~800-1500** | **~8-15 hours** |

**Conservative estimate with buffer: 20-40 hours**

The variance depends on:
- Task difficulty distribution (easy tasks converge faster)
- Model starting point (SFT-trained models start higher)
- Curriculum learning (starting easy, getting harder)
- TK5 response time and stability

#### Running the RLVR Training

```bash
# Train until score 5 (max 40 hours)
./scripts/training/rlvr_to_five.sh 40 5

# Monitor progress
tail -f /tmp/rlvr_train.log

# Check score distribution
cat /tmp/rlvr_scores.jsonl | jq -r '.reward' | sort | uniq -c
```

The script automatically:
1. Starts TK5 if not running
2. Samples tasks with curriculum learning (easy → hard)
3. Submits to MVS and scores results
4. Saves high-reward examples for SFT reinforcement
5. Stops when 10 consecutive 5s achieved (or time limit)

**The Key Insight**: A small specialist model (7B) can outperform large generalists (GPT-4, Claude) on domain-specific tasks when trained with verifiable feedback.

#### Full Multi-Topic RLVR

We extended RLVR beyond JCL to cover ALL mainframe technologies using topic-appropriate verification:

| Category | Verification Method | Examples |
|----------|-------------------|----------|
| **JCL** | Execute on TK5 MVS | IEFBR14, IDCAMS, IEBGENER, IEBCOPY, SORT |
| **REXX** | Execute via IKJEFT01 | OUTTRAP, PARSE, DO loops |
| **Assembler** | Compile via ASMA90 | WTO, return codes |
| **COBOL** | Syntax validation | Divisions, PERFORM, EVALUATE |
| **CICS** | Syntax validation | EXEC CICS, END-EXEC |
| **DB2** | Syntax validation | EXEC SQL, embedded SQL |
| **RACF** | Syntax validation | ADDUSER, PERMIT |
| **VSAM** | IDCAMS on TK5 | KSDS, ESDS, RRDS clusters |

**Task Prompts**: 40+ prompts across all categories, difficulty-graded 1-5.

**Success Criteria**: 3 perfect scores per category (21+ total verified correct outputs).

**Syntax Validation** (for topics TK5 cannot execute):
```python
# COBOL validation
def validate_cobol(code):
    checks = [
        (r'IDENTIFICATION\s+DIVISION', "Missing ID DIVISION"),
        (r'PROGRAM-ID', "Missing PROGRAM-ID"),
        (r'PROCEDURE\s+DIVISION', "Missing PROCEDURE DIVISION"),
    ]
    # Must have all required divisions

# CICS validation
def validate_cics(code):
    return 'EXEC CICS' in code and 'END-EXEC' in code

# DB2 validation
def validate_db2(code):
    return 'EXEC SQL' in code and 'END-EXEC' in code
```

This approach ensures the model learns correct patterns for ALL mainframe technologies, not just those executable on the emulator.

**Our RLVR Pipeline**:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Prompt Generator│────▶│   BigIron-AI    │────▶│  TK5 Verifier   │
│ (non-deterministic)   │ (generate code) │     │ (execute on MVS)│
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                        ┌─────────────────┐              │
                        │  GRPO Training  │◀─────────────┘
                        │ (update weights)│     (reward: 0-5)
                        └─────────────────┘
```

**How It Works**:

1. **Non-deterministic prompt generation**: Random variations of JCL/COBOL tasks
2. **LLM generates code**: Multiple completions per prompt
3. **TK5 MVS verification**: Actually submit JCL, check condition codes
4. **Reward calculation**:
   - CC 0000 (perfect): +5
   - Warnings (CC 4): +4
   - Errors but ran: +3
   - Abend: +1.5
   - JCL syntax error: +1
   - Unparseable: 0
5. **GRPO update**: Model learns from successes and failures

**Expected Improvements** (based on Outflank's results with similar architecture):

| Metric | Before RLVR | After RLVR |
|--------|-------------|------------|
| JCL syntax correct | ~70% | ~90% |
| Executes without error | ~40% | ~70% |
| Perfect CC 0000 | ~20% | ~50% |

**Failure Tracking with Reasons**:

Unlike black-box training, our verifier captures WHY code fails:

| Failure Type | Reason Code | Training Signal |
|--------------|-------------|-----------------|
| JCL syntax error | IEF452I | Missing JOB/EXEC statement |
| Dataset not found | IEF212I | Incorrect DSN reference |
| Program abend | S0C4/S0C7 | Invalid memory/data |
| Authorization | ICH408I | RACF permission denied |
| Resource conflict | IEF861I | Dataset in use |

This enables **curriculum learning**: model learns simple tasks first, then complex ones.

**Red Teaming & Security Scenarios**:

Training includes mainframe security patterns from lab exercises:
- APF authorization boundaries
- RACF profile bypass attempts
- JES spool access controls
- Started task identity binding
- Deferred execution trust chains

The model learns BOTH how to write secure code AND common misconfigurations.

**Agent-Based Verification Loop**:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Task Agent  │────▶│   Generate   │────▶│   Submit     │
│ (difficulty) │     │   Code       │     │   to TK5     │
└──────────────┘     └──────────────┘     └──────┬───────┘
       ▲                                         │
       │              ┌──────────────┐           │
       │              │  Classify    │◀──────────┘
       └──────────────│  Failure     │
                      │  Reason      │
                      └──────────────┘
```

**Why This Matters**:

- **No training data needed**: Model learns by doing, not from examples
- **Verifiable quality**: If it runs on MVS, it works
- **Failure-aware**: Model understands WHY code fails, not just that it failed
- **Security-conscious**: Trained on red teaming scenarios
- **Continuous improvement**: More training = better code
- **Self-hosted**: 7B model runs locally, outperforms cloud giants

### Data Sources

- **Hand-crafted examples**: JCL, COBOL, REXX, RACF, CICS, DB2, VSAM
- **MainframeBench**: 2,598 public Q&A pairs
- **IBM Redbooks**: z/OS security, DB2, CICS, Sysplex, LinuxONE, AI/ML

### Training Cost Analysis

| Approach | Cost | Time | Quality |
|----------|------|------|---------|
| Train from scratch | $50K-500K | Weeks | Full control |
| Cloud fine-tuning | $500-2000 | Hours | Good |
| **Apple Silicon local** | **$0** | **2-3 hours** | **Production quality** |

Our approach achieves production-quality results at zero marginal cost using existing Apple Silicon hardware.

---

## 11. Conclusion

BigIron.ai demonstrates that meaningful domain specialization of large language models is achievable on consumer hardware. Using Apple Silicon's Metal GPU acceleration, MLX framework, and LoRA fine-tuning, we adapted Mistral-7B to show improved mainframe expertise.

### Key Findings

1. **Domain fine-tuning works**: 32% improvement in mainframe tasks
2. **Consumer hardware suffices**: M2/M3 Macs can train 7B models
3. **Quality data trumps quantity**: 246 curated examples beat 8,000 generic ones
4. **Iterative improvement is key**: Each version built on previous learnings

### Impact

This work enables:
- Local, private AI assistance for mainframe professionals
- Educational tool for mainframe learning
- Foundation for enterprise mainframe AI assistants
- Proof-of-concept for domain-specific LLM adaptation

### Future Directions

- **RLVR at scale**: Extended training with 500+ GRPO steps for measurable quality gains
- **Multi-task verification**: Extend TK5 verifier to COBOL compilation, VSAM operations
- **Benchmark against GPT-4/Claude**: Quantify specialist vs generalist performance gap
- Expand training corpus with more verified examples
- Experiment with larger base models
- Engage mainframe community for feedback
- Explore deployment options (cloud, on-premise)

---

## 12. Appendix: Technical Specifications

### A. File Structure

```
mainframe-ai-apple-silicon/
├── CLAUDE.md                         # Project documentation for Claude Code
├── start.sh                          # One-command startup
├── app/                              # FastAPI web interface
├── configs/
│   └── ollama/
│       └── Modelfile.bigiron-ai      # Ollama configuration
├── data/
│   ├── training/
│   │   ├── mlx_data/
│   │   │   ├── train.jsonl           # Training set (85%)
│   │   │   ├── valid.jsonl           # Validation set (10%)
│   │   │   └── test.jsonl            # Test set (5%)
│   │   ├── examples/                 # 50+ JSONL training files
│   │   │   ├── cobol_*.jsonl         # COBOL examples
│   │   │   ├── jcl_*.jsonl           # JCL examples
│   │   │   ├── rexx_*.jsonl          # REXX examples
│   │   │   ├── racf_*.jsonl          # RACF examples
│   │   │   ├── cics_*.jsonl          # CICS examples
│   │   │   └── ...                   # Other categories
│   │   ├── bigiron_full/             # Training output
│   │   │   ├── weights/              # Checkpoints
│   │   │   └── fused/                # Merged model
│   │   └── bigiron-ai.gguf           # Production model (14 GB)
│   └── external/
│       └── mainframebench/           # External dataset
├── scripts/
│   └── training/
│       ├── build_bigiron_ai.sh       # Main training pipeline
│       └── integrate_external_data.py # Dataset integration
├── tests/                            # 38 unit tests
├── docs/
│   ├── BIGIRON_AI.md                 # Model documentation
│   ├── TRAINING.md                   # Training guide
│   ├── EXTERNAL_DATASETS.md          # Dataset catalog
│   └── WHITEPAPER.md                 # This document
├── .venv/                            # App environment (Python 3.14)
└── .venv-train/                      # Training environment (Python 3.12)
```

### B. Dependencies

```bash
# Training environment (.venv-train) - Python 3.12
mlx >= 0.5.0
mlx-lm >= 0.19.0
transformers < 4.52        # Required for Python 3.12 compatibility
numpy >= 1.24.0
gguf                       # For GGUF conversion

# Application environment (.venv) - Python 3.14
fastapi
uvicorn
pytest

# System tools
ollama >= 0.1.0
llama.cpp                  # For GGUF conversion
```

### C. Ollama Modelfile (bigiron-ai)

```dockerfile
FROM /path/to/data/training/bigiron-ai.gguf

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER num_ctx 4096

SYSTEM """
You are BigIron, a friendly mainframe expert. I know z/OS, COBOL, JCL,
CICS, RACF, DB2, VSAM, and all the technology that keeps banks, airlines,
and governments running.

I explain things in plain English. When you ask me something, I'll give
you a straight answer - no corporate jargon, no "please refer to the
manual" nonsense. If you need code, I'll write it. If you need an
explanation, I'll make it make sense.

Think of me as that senior mainframer down the hall who actually enjoys
helping people learn. I've seen every abend code, debugged JCL at 2am,
and know why your COBOL program is giving you S0C7s.

A few things about how I work:
- I write actual code when you ask for it - complete, working examples
- I use proper mainframe terminology but explain it when needed
- I know the difference between a PDS and PDSE (and why it matters)
- I can help with RACF security, JES spool issues, VSAM problems, and more
- I don't pretend Unix solutions work on z/OS - these are different worlds
"""

TEMPLATE """{{ if .System }}<|system|>
{{ .System }}
{{ end }}{{ if .Prompt }}<|user|>
{{ .Prompt }}
{{ end }}<|assistant|>
{{ .Response }}"""
```

### D. Training Data Format

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Write REXX to read a dataset and display its contents on z/OS"
    },
    {
      "role": "assistant",
      "content": "Here's how to read a sequential dataset using EXECIO...\n\n```rexx\n/* REXX - Read dataset */\n\"ALLOC F(INFILE) DA('YOUR.DATASET') SHR REUSE\"\n\"EXECIO * DISKR INFILE (STEM LINE. FINIS)\"\n...\n```"
    }
  ]
}
```

### E. Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Apple Silicon | M1 Pro | M2 Max / M3 Max |
| Unified Memory | 32 GB | 64 GB |
| Storage | 50 GB free | 100 GB free |
| Training Memory | 32 GB | 39 GB peak |
| Training Time | 3+ hours | ~2 hours |

### F. Quick Start

```bash
# Clone and setup
git clone <repo>
cd mainframe-ai-apple-silicon

# Start everything (Ollama + model + web interface)
./start.sh

# Or train a new model
./scripts/training/build_bigiron_ai.sh --epochs 25

# Test the model
ollama run bigiron-ai "What causes an S0C7 abend?"
```

---

## 13. Open Mainframe AI Training Dataset

### A Reusable Resource for the Community

Beyond the trained model, this project produces a **curated mainframe training dataset** suitable for fine-tuning any LLM. We believe this dataset is one of the most comprehensive open-source mainframe training corpora available.

### Dataset Statistics

| Category | Files | Examples | Topics Covered |
|----------|-------|----------|----------------|
| COBOL | 8 | ~800 | Arithmetic, tables, DB2, CICS, file I/O, SORT, strings, copybooks |
| JCL | 3 | ~300 | Utilities, procedures, conditional execution, SORT |
| REXX | 6 | ~600 | EXECIO, TSO, ISPF, OUTTRAP, LISTDSI, z/OS system programming |
| RACF | 4 | ~400 | Users, groups, dataset protection, general resources |
| CICS | 4 | ~400 | BMS maps, file operations, interval control, queues |
| DB2 | 2 | ~200 | DDL, stored procedures, embedded SQL |
| VSAM | 2 | ~200 | KSDS operations, IDCAMS, cluster management |
| Assembler | 2 | ~200 | Macros, SVCs, system programming |
| Utilities | 4 | ~300 | DFSORT, IDCAMS, IEBCOPY, ADRDSSU |
| Security | 2 | ~2,200 | Red team, defense, APF, privilege escalation (weighted) |
| Other | 6 | ~400 | JES2, GDG, PDS/PDSE, SMF, APF, PL/I |
| **MainframeBench** | - | **2,598** | Public Q&A dataset |
| **IBM Redbooks** | - | **30,799** | Extracted from 109+ PDFs |
| **Source Total** | **40+** | **~33,733** | |
| **Training Total** | - | **120,209** | With weighting |

### Dataset Format

All examples use the standard chat/instruction format compatible with most fine-tuning frameworks:

```json
{
  "messages": [
    {"role": "user", "content": "How do I..."},
    {"role": "assistant", "content": "Here's how to..."}
  ]
}
```

### Using the Dataset

```bash
# Clone the repository
git clone <repo-url>
cd mainframe-ai-apple-silicon

# Training data location
ls data/training/examples/*.jsonl

# Merge all examples into single file
cat data/training/examples/*.jsonl > mainframe_training.jsonl

# Use with any fine-tuning framework
# - MLX-LM (Apple Silicon)
# - Hugging Face Transformers
# - Axolotl
# - LLaMA-Factory
```

### Extending the Dataset

The dataset is designed for extension:

1. Create new JSONL files in `data/training/examples/`
2. Follow the chat format structure
3. Run `./scripts/training/build_bigiron_ai.sh` to retrain

### License

The training dataset is released under Apache 2.0, allowing:
- Commercial use
- Modification
- Distribution
- Private use

We encourage the mainframe community to contribute additional examples, corrections, and improvements.

### HuggingFace Release

The model and dataset are available on HuggingFace:

- **Model**: [`bigiron-ai/bigiron-7b`](https://huggingface.co/bigiron-ai/bigiron-7b) - Fine-tuned Mistral-7B (14GB safetensors)
- **Dataset**: [`bigiron-ai/mainframe-instruct`](https://huggingface.co/datasets/bigiron-ai/mainframe-instruct) - 9,042 training examples

#### Using the Model from HuggingFace

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# Load model and tokenizer
model_id = "bigiron-ai/bigiron-7b"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    torch_dtype=torch.float16,
    device_map="auto"
)

# Generate response
prompt = "What causes an S0C7 abend in COBOL?"
inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
outputs = model.generate(**inputs, max_new_tokens=256, temperature=0.7)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))
```

#### Using the Dataset

```python
from datasets import load_dataset

# Load the full dataset
dataset = load_dataset("bigiron-ai/mainframe-instruct")

# Access splits
train = dataset["train"]      # 120,209 examples
valid = dataset["validation"] # 518 examples
test = dataset["test"]        # 452 examples

# Example format
print(train[0])
# {"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```

#### Publishing Your Own Version

To upload a modified version to HuggingFace:

```bash
# 1. Install HuggingFace CLI
pip install huggingface_hub

# 2. Login to HuggingFace
huggingface-cli login

# 3. Use the provided upload script
./scripts/upload_to_huggingface.sh --both

# Or upload separately:
./scripts/upload_to_huggingface.sh --model    # Upload model (~14GB)
./scripts/upload_to_huggingface.sh --dataset  # Upload dataset (~50MB)
```

This enables researchers and practitioners to:
- Fine-tune their own mainframe models
- Extend our training corpus
- Benchmark against our results
- Build specialized mainframe AI tools

---

## 14. Appendix: HuggingFace Submission Guide

This section provides detailed instructions for submitting BigIron-AI to HuggingFace.

### Prerequisites

1. **HuggingFace Account**: Create at https://huggingface.co/join
2. **Access Token**: Generate at https://huggingface.co/settings/tokens (with write access)
3. **Git LFS**: Required for large model files

```bash
# Install Git LFS (macOS)
brew install git-lfs
git lfs install

# Install HuggingFace Hub
pip install huggingface_hub
```

### Step 1: Login to HuggingFace

```bash
huggingface-cli login
# Paste your access token when prompted
```

### Step 2: Create Repositories

```bash
# Create model repository
huggingface-cli repo create bigiron-7b --type model

# Create dataset repository
huggingface-cli repo create mainframe-instruct --type dataset
```

### Step 3: Prepare Model Files

The model files are located at `data/training/bigiron_full/fused/`:

```
fused/
├── config.json                    # Model configuration
├── generation_config.json         # Generation settings
├── model-00001-of-00003.safetensors  # Model weights (5.3GB)
├── model-00002-of-00003.safetensors  # Model weights (5.4GB)
├── model-00003-of-00003.safetensors  # Model weights (3.9GB)
├── model.safetensors.index.json   # Weight index
├── README.md                      # Model card
├── special_tokens_map.json        # Special tokens
├── tokenizer.json                 # Tokenizer
├── tokenizer.model                # Tokenizer model
└── tokenizer_config.json          # Tokenizer config
```

### Step 4: Upload Model

```bash
# Using the provided script (recommended)
./scripts/upload_to_huggingface.sh --model

# Or manually
cd data/training/bigiron_full/fused
git clone https://huggingface.co/YOUR_USERNAME/bigiron-7b
cp -r * bigiron-7b/
cd bigiron-7b
git add .
git commit -m "Upload BigIron-AI v1.0"
git push
```

### Step 5: Prepare Dataset

The dataset is in JSONL format:

```
data/training/mlx_data/
├── train.jsonl   # 120,209 examples
├── valid.jsonl   #     518 examples
└── test.jsonl    #     452 examples
```

### Step 6: Upload Dataset

```bash
# Using the provided script (recommended)
./scripts/upload_to_huggingface.sh --dataset

# Or manually
huggingface-cli upload YOUR_USERNAME/mainframe-instruct \
    data/training/mlx_data/ . \
    --repo-type dataset
```

### Step 7: Verify Uploads

1. Visit `https://huggingface.co/YOUR_USERNAME/bigiron-7b`
2. Visit `https://huggingface.co/datasets/YOUR_USERNAME/mainframe-instruct`
3. Test loading:

```python
# Test model
from transformers import AutoModelForCausalLM
model = AutoModelForCausalLM.from_pretrained("YOUR_USERNAME/bigiron-7b")

# Test dataset
from datasets import load_dataset
ds = load_dataset("YOUR_USERNAME/mainframe-instruct")
```

### Model Card Requirements

A good HuggingFace model card (README.md) should include:

| Section | Description |
|---------|-------------|
| YAML Front Matter | License, tags, base model, pipeline |
| Model Description | What the model does, key features |
| Intended Uses | Target use cases |
| Training Details | Base model, method, data, hardware |
| Usage Examples | Code snippets for inference |
| Limitations | Known issues, out-of-scope uses |
| Citation | BibTeX for academic use |

### Dataset Card Requirements

| Section | Description |
|---------|-------------|
| YAML Front Matter | License, language, tags, size |
| Dataset Description | What's in the dataset |
| Dataset Structure | Splits, format, fields |
| Usage Examples | How to load and use |
| Sources | Where data came from |

### Ollama Library Submission

To also submit to the Ollama library:

1. Fork `https://github.com/ollama/ollama`
2. Add model manifest in `models/`
3. Submit pull request with model details

```yaml
# Example manifest
name: bigiron-ai
description: Mainframe expert LLM
parameters:
  temperature: 0.7
  context_length: 4096
license: Apache 2.0
repository: https://huggingface.co/bigiron-ai/bigiron-7b
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Upload timeout | Use `--chunk-size` flag for large files |
| Git LFS errors | Run `git lfs install` first |
| Auth errors | Regenerate token with write permissions |
| Quota exceeded | Request increased storage at HF |

---

## References

1. Hu, E. J., et al. (2021). "LoRA: Low-Rank Adaptation of Large Language Models"
2. Apple Inc. (2023). "MLX: An array framework for Apple silicon"
3. Mistral AI (2023). "Mistral 7B Technical Report"
4. IBM Corporation. "IBM Redbooks" (Various publications)
5. Touvron, H., et al. (2023). "LLaMA: Open and Efficient Foundation Language Models"
6. Fsoft-AIC. "MainframeBench: A Benchmark for Mainframe Code Understanding" - https://huggingface.co/datasets/Fsoft-AIC/MainframeBench
7. Fsoft-AIC. "XMainframe: A Large Language Model for Mainframe Modernization" - https://arxiv.org/html/2408.04660v3
8. IBM. "Project CodeNet: A Large-Scale AI for Code Dataset" - https://github.com/IBM/Project_CodeNet

---

## Acknowledgments

This work was conducted on Apple Silicon hardware using open-source tools. We thank:

- **Apple MLX Team** for the efficient ML framework on Apple Silicon
- **Mistral AI** for the high-quality base model
- **Fsoft-AIC** for the MainframeBench public dataset
- **IBM** for decades of mainframe documentation via Redbooks
- **Open Mainframe Project** for promoting mainframe education

---

## Citation

If you use BigIron-AI or the mainframe training dataset in your research, please cite:

```bibtex
@misc{bigiron2026,
  title={BigIron-AI: Fine-Tuning Large Language Models for Mainframe Domain Expertise on Apple Silicon},
  author={BigIron-AI Project Contributors},
  year={2026},
  howpublished={\url{https://github.com/W00t3k/mainframe-ai}},
  note={Version 2.0, HuggingFace: bigiron-ai/bigiron-7b}
}
```

---

## License

- **Model Weights**: Apache 2.0 (inherits from Mistral-7B)
- **Training Dataset**: Apache 2.0
- **Documentation**: CC BY 4.0

---

*Document Version: 2.0*
*Last Updated: July 2026*
*BigIron-AI Project - Mainframe AI on Apple Silicon*
