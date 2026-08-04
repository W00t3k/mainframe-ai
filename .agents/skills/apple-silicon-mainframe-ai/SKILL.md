---
name: apple-silicon-mainframe-ai
description: Guidance for Apple Silicon/macOS local development and inference for mainframe-ai.
---

# Apple Silicon Mainframe AI

Use this skill when working on the Apple Silicon branch variant of mainframe-ai.

## Branch Scope

- Target Apple Silicon/macOS local development and inference.
- Assume Ollama plus Mistral for local inference unless the user says otherwise.
- Prefer Homebrew-based setup instructions for macOS.
- Preserve existing routes and app behavior unless explicitly asked to change them.
- Keep changes isolated, additive, and easy to review.

## Rules

- Do not add CUDA-only requirements as defaults.
- Do not add Linux-only install assumptions as defaults.
- Do not make Docker the only workflow.
- Keep scripts CPU-safe unless explicitly told otherwise.
- Do not run Axolotl training as part of local Apple Silicon work.
- Do not commit Redbook PDFs, copyrighted IBM docs, private corpora, large model files, or checkpoints.
- Treat Redbooks and vendor docs as private RAG material, not committed training data.

## Preferred Work

- Improve Apple Silicon setup docs.
- Validate Ollama and Mistral instructions.
- Add or refine JSONL validators.
- Add safe, original SFT and eval examples.
- Improve RAG guidance without committing source PDFs.
- Add optional configs such as Ollama Modelfiles.
- Keep heavy fine-tuning documented as external Linux/CUDA/cloud GPU work.

## BigIron.ai Behavior

Prefer mainframe-native concepts:

- RACF
- JES
- JCL
- TSO
- ISPF
- datasets and dataset profiles
- APF
- VTAM
- CICS
- SMF
- started task identity
- PROCLIB and PARMLIB
- spool
- trust boundaries

Avoid defaulting to Unix/Linux concepts such as root, sudo, `/etc/passwd`, chmod, bash history, generic process assumptions, or port-scan-only exposure analysis unless explicitly comparing models.
