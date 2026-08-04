# Codex Prompts For Apple Silicon Work

Use these prompts when iterating on this branch. Keep changes local to the current repository, avoid CUDA-only defaults, and do not commit private Redbooks or copyrighted IBM documentation.

## Improve Apple Silicon Setup Docs

```text
Review docs/APPLE_SILICON.md for Apple Silicon macOS clarity. Keep the branch focused on Homebrew, Ollama, Mistral, local inference, RAG, JSONL validation, and development. Do not add CUDA-only or Linux-only defaults. Make the instructions concise and testable.
```

## Check Ollama And Mistral Integration

```text
Inspect the app's Ollama configuration and docs. Confirm a Mac user can run with OLLAMA_MODEL=mistral or OLLAMA_MODEL=bigiron-mistral. Do not change existing routes unless required. Prefer docs or optional config over behavioral rewrites.
```

## Validate JSONL Examples

```text
Run the JSONL validator on data/training/examples/bigiron_sft_sample.jsonl and data/evals/mainframe_eval_sample.jsonl. Fix only malformed records or schema issues. Keep examples original, safe, and mainframe-native.
```

## Generate Additional Safe SFT Examples

```text
Add original supervised fine-tuning examples that teach BigIron.ai to avoid Unix/Linux assumptions. Use topics like RACF, JES, JCL, TSO, ISPF, datasets, APF, VTAM, CICS, SMF, started task identity, PROCLIB, PARMLIB, spool, and trust boundaries. Do not copy IBM documentation or include offensive step-by-step exploitation.
```

## Add Eval Questions

```text
Add eval JSONL questions that detect whether the assistant understands mainframe-native security concepts. Each record must include id, question, and ideal_keywords. Cover misconceptions such as root, sudo, /etc/passwd, port-scan-only exposure, and generic Linux process assumptions.
```

## Improve RAG Chunking Without Committing Source PDFs

```text
Review RAG ingestion or chunking guidance for private mainframe docs. Improve chunk metadata and retrieval quality without committing source PDFs, Redbooks, copyrighted IBM text, or private corpus files. Keep docs clear that private sources stay local.
```

## Review For Accidental CUDA Or Linux-Only Assumptions

```text
Review this branch for accidental CUDA, NVIDIA, Linux-only, x86_64-only, Docker-only, sudo-heavy, or Axolotl-default assumptions. Keep Apple Silicon as the local inference and development path, and document heavy training as external Linux/CUDA/cloud GPU work.
```
