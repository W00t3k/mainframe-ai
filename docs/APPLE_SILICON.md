# Apple Silicon Local Development

This branch is optimized for local macOS development, inference, and **MLX-based fine-tuning** on Apple Silicon Macs. It supports Homebrew, Ollama, Mistral, MLX LoRA training, RAG, and the complete BigIron training pipeline.

## What Apple Silicon Is Good For

- **MLX LoRA fine-tuning** - Train custom models using Apple's Metal GPU acceleration
- **Local Ollama inference** with Mistral, bigiron-5k, or other models
- **RAG over private documentation** - lab notes, transcripts, screen captures
- Mainframe workflow development and validation
- JSONL dataset checks and eval authoring
- Safe local testing of BigIron.ai behavior

## BigIron-5k: Fine-Tuned Mainframe Model

This branch includes **bigiron-5k**, a Mistral-7B model fine-tuned on 8,175 Q&A pairs from IBM Redbooks:

| Metric | Value |
|--------|-------|
| Training iterations | 5,000 |
| Training samples | 8,175 Q&A pairs |
| Validation samples | 909 |
| Initial loss | 4.59 |
| Final loss | 1.29 (72% improvement) |
| Model size | 7.7 GB (q8_0 quantized) |
| Peak memory | 16 GB |

### Using the Fine-Tuned Model

The app automatically uses bigiron-5k on Apple Silicon:

```bash
./start.sh
```

Or test directly:

```bash
ollama run bigiron-5k "What is RACF?"
```

### Training Your Own Model

To regenerate or customize the fine-tuned model:

```bash
# 1. Generate Q&A training data from Redbooks
python scripts/training/generate_qa_from_rag.py

# 2. Run MLX LoRA fine-tuning (5000 iterations)
python scripts/training/mlx_finetune.py --iters 5000

# 3. Fuse adapters into base model
python scripts/training/mlx_finetune.py --fuse

# 4. Convert to GGUF for Ollama
python /tmp/llama.cpp/convert_hf_to_gguf.py data/training/bigiron-5k-fused \
  --outfile data/training/bigiron-5k.gguf --outtype q8_0

# 5. Create Ollama model
ollama create bigiron-5k -f configs/ollama/Modelfile.bigiron-5k
```

## What Requires Linux/CUDA

- Production-scale training (>16GB models)
- CUDA-specific QLoRA or Axolotl workflows
- Multi-GPU distributed training

## Install Homebrew

If Homebrew is not installed, install it from the official Homebrew instructions:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Then follow the shell profile instructions printed by the installer.

Check it:

```bash
brew --version
```

## Install Local Dependencies

Install Git, Python, the TN3270 client tools, and Ollama:

```bash
brew install git python x3270 ollama
```

Confirm the basics:

```bash
uname -m
git --version
python3 --version
ollama --version
```

On Apple Silicon, `uname -m` should report `arm64`.

## Ollama Models

Start Ollama:

```bash
ollama serve
```

### Available Models

| Model | Description | Size |
|-------|-------------|------|
| `bigiron-5k` | Fine-tuned on IBM Redbooks (recommended) | 7.7 GB |
| `bigiron-mistral` | System prompt wrapper around Mistral | 4.4 GB |
| `mistral` | Base Mistral-7B model | 4.1 GB |

### Create Models

The fine-tuned model (requires running training pipeline first):

```bash
ollama create bigiron-5k -f configs/ollama/Modelfile.bigiron-5k
```

The system prompt wrapper (no training needed):

```bash
ollama pull mistral
ollama create bigiron-mistral -f configs/ollama/Modelfile.bigiron-mistral
```

### Select Model

Override the default model:

```bash
export OLLAMA_MODEL=bigiron-5k    # Fine-tuned (default on Apple Silicon)
export OLLAMA_MODEL=mistral        # Base model
```

## Run Mainframe AI

From this repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OLLAMA_MODEL=bigiron-mistral
./start.sh
```

If you only want the web app and local inference without starting TK5 MVS:

```bash
./start.sh --no-mvs
```

If Ollama is already running in another terminal:

```bash
./start.sh --no-ollama
```

The app is local-first. Use private RAG material locally and do not commit private Redbooks, copyrighted IBM documentation, or large model artifacts.

## Optional Local RAG

Use RAG for fact storage and retrieval:

- Private Redbooks and vendor docs should remain private local corpus material.
- Lab transcripts, SYSOUT, TN3270 screen captures, JCL snippets, and notes can be used as local retrieval sources.
- Keep copyrighted source text out of committed training examples.
- Use summarized, original examples for SFT or eval data committed to the repo.

## Validate Local Samples

Run the CPU-safe JSONL validator:

```bash
python3 scripts/training/validate_jsonl.py --mode training data/training/examples/bigiron_sft_sample.jsonl
python3 scripts/training/validate_jsonl.py --mode eval data/evals/mainframe_eval_sample.jsonl
```

Run the readiness check:

```bash
bash scripts/apple_silicon_check.sh
```

## Troubleshooting

### Ollama is not reachable

Start it in a dedicated terminal:

```bash
ollama serve
```

Then verify:

```bash
curl http://localhost:11434/api/tags
```

### The model is slow

Use a smaller local model or reduce context. Mistral is reasonable for many Apple Silicon systems, but older or lower-memory Macs may need a smaller model.

### The app uses a different model

Set the model explicitly before starting:

```bash
export OLLAMA_MODEL=mistral
```

or:

```bash
export OLLAMA_MODEL=bigiron-mistral
```

### TN3270 tools are missing

Install x3270:

```bash
brew install x3270
```

### Do not use CUDA-only setup steps here

This branch should not add CUDA-only requirements as the default path. Document heavy training as external Linux/CUDA/cloud GPU work and keep Apple Silicon focused on local inference, RAG, validation, and development.
