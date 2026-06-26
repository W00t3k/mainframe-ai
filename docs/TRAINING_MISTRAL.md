# Training And Mistral

This Apple Silicon branch uses Ollama for local inference and **MLX for LoRA fine-tuning**. Both run entirely on Apple Silicon using Metal GPU acceleration.

## Models Available

| Model | Type | Description |
|-------|------|-------------|
| `bigiron-5k` | Fine-tuned | 5000-iteration LoRA on 8,175 IBM Redbook Q&A pairs |
| `bigiron-mistral` | Wrapper | System prompt wrapper around base Mistral |
| `mistral` | Base | Stock Mistral-7B model |

## Local Inference

The app defaults to `bigiron-5k` on Apple Silicon:

```bash
./start.sh
```

Or select a specific model:

```bash
export OLLAMA_MODEL=bigiron-5k      # Fine-tuned (default)
export OLLAMA_MODEL=bigiron-mistral # System prompt wrapper
export OLLAMA_MODEL=mistral          # Base model
```

## Fine-Tuning Is Separate

Fine-tuning changes behavior. It should not be used as the primary fact store.

Near-term approach:

- Use RAG for private facts, Redbooks, vendor docs, lab notes, transcripts, and screen captures.
- Use supervised examples to teach mainframe-native reasoning style.
- Use evals to catch regressions such as Unix/Linux assumptions.
- Use JSONL validation before committing examples.

## Feedback Loop

This branch supports a local right/wrong correction loop without pretending to train the Ollama model live.

1. Ask a question in `/chat`.
2. Mark the answer `RIGHT` or `WRONG`.
3. For wrong answers, enter the corrected answer.
4. Corrections are stored locally in `data/feedback/chat_feedback.jsonl`.
5. Export corrections into SFT JSONL:

```bash
python3 scripts/training/export_feedback_jsonl.py \
  --input data/feedback/chat_feedback.jsonl \
  --output data/training/generated/feedback_sft.jsonl
```

6. Validate the generated SFT data:

```bash
python3 scripts/training/validate_jsonl.py --mode training data/training/generated/feedback_sft.jsonl
```

Use the exported data to improve RAG/direct-answer coverage first. For real LoRA/QLoRA tuning, move the reviewed JSONL to a separate Linux/CUDA/cloud GPU training environment.

## Data Boundary

Do not commit:

- Redbook PDFs.
- Copyrighted IBM documentation.
- Copied vendor text.
- Private client data.
- Large model files or training checkpoints.

Committed training examples should be original, safe, summarized examples that teach how BigIron.ai should reason.

## What The JSONL Should Teach

Training examples should reinforce:

- RACF and dataset profiles instead of root and `/etc/passwd`.
- APF authorization as a trust boundary, not `sudo`.
- JES as deferred execution with spool, SYSOUT, and SMF evidence.
- Started task identity and long-running address spaces.
- Datasets, catalogs, and PDS members instead of generic file trees.
- VTAM, TSO, ISPF, and CICS as mainframe interaction surfaces.
- Port scans as incomplete evidence for mainframe exposure.

## Apple Silicon Role

Apple Silicon with MLX supports the **complete training pipeline**:

- **Ollama inference** with fine-tuned or base models
- **MLX LoRA fine-tuning** using Metal GPU acceleration
- **Local RAG** over IBM Redbooks and private documentation
- **JSONL validation** and eval authoring
- **GGUF conversion** for Ollama deployment

### MLX Fine-Tuning Pipeline

```bash
# 1. Generate Q&A training data from Redbooks
python scripts/training/generate_qa_from_rag.py

# 2. Run MLX LoRA fine-tuning
python scripts/training/mlx_finetune.py --iters 5000

# 3. Fuse adapter into base model
python scripts/training/mlx_finetune.py --fuse

# 4. Convert to GGUF (requires llama.cpp)
python /tmp/llama.cpp/convert_hf_to_gguf.py data/training/bigiron-5k-fused \
  --outfile data/training/bigiron-5k.gguf --outtype q8_0

# 5. Create Ollama model
ollama create bigiron-5k -f configs/ollama/Modelfile.bigiron-5k
```

### Training Results (bigiron-5k)

| Metric | Value |
|--------|-------|
| Training samples | 8,175 |
| Validation samples | 909 |
| Iterations | 5,000 |
| Initial loss | 4.59 |
| Final loss | 1.29 |
| Improvement | 72% |
| Peak memory | 16 GB |
| Model size | 7.7 GB (q8_0) |

### What Requires Linux/CUDA

- Production-scale training (models >16GB)
- Multi-GPU distributed training
- CUDA-specific optimizations (Flash Attention 2)

## Validate Samples

```bash
python3 scripts/training/validate_jsonl.py --mode training data/training/examples/bigiron_sft_sample.jsonl
python3 scripts/training/validate_jsonl.py --mode eval data/evals/mainframe_eval_sample.jsonl
```
