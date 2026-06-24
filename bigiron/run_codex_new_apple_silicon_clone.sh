#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# mainframe-ai Apple Silicon Codex CLI runner
#
# Goal:
# - Do NOT modify any existing local Apple Silicon/mainframe-ai directory.
# - Create a completely separate local clone:
#     ~/code/mainframe-ai-apple-silicon
# - Create a branch:
#     feature/apple-silicon-bigiron
# - Run Codex CLI only inside that new clone.
###############################################################################

UPSTREAM_REPO="W00t3k/mainframe-ai"
BRANCH_NAME="feature/apple-silicon-bigiron"
BASE_DIR="${HOME}/code"
WORK_DIR="${BASE_DIR}/mainframe-ai-apple-silicon"
PROMPT_FILE="CODEX_APPLE_SILICON_PROMPT.txt"

echo "[*] mainframe-ai Apple Silicon Codex CLI setup"
echo "[*] This will NOT touch any existing mainframe-ai directory."
echo "[*] New work directory: ${WORK_DIR}"
echo "[*] Branch: ${BRANCH_NAME}"
echo

if ! command -v git >/dev/null 2>&1; then
  echo "[!] git not found."
  echo "    Install Git/Xcode Command Line Tools first:"
  echo "    xcode-select --install"
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "[!] GitHub CLI 'gh' not found."
  echo "    Install with:"
  echo "    brew install gh"
  exit 1
fi

if ! command -v codex >/dev/null 2>&1; then
  echo "[!] Codex CLI not found."
  echo "    Install/sign in to Codex CLI first, then rerun this script."
  echo
  echo "    Try one of these:"
  echo "    brew install --cask codex"
  echo "    npm install -g @openai/codex"
  exit 1
fi


mkdir -p "${BASE_DIR}"

if [[ -d "${WORK_DIR}" ]]; then
  echo "[!] Safe clone directory already exists:"
  echo "    ${WORK_DIR}"
  echo
  echo "    I will not modify it automatically."
  echo "    To start over, manually remove it:"
  echo "    rm -rf \"${WORK_DIR}\""
  echo
  echo "    Or edit WORK_DIR in this script."
  exit 1
fi

GH_USER="$(gh api user --jq .login)"
UPSTREAM_OWNER="${UPSTREAM_REPO%%/*}"
REPO_NAME="${UPSTREAM_REPO##*/}"

echo "[*] GitHub user: ${GH_USER}"

if [[ "${GH_USER}" == "${UPSTREAM_OWNER}" ]]; then
  echo "[*] You appear to own ${UPSTREAM_REPO}."
  echo "[*] Creating a separate local clone. Not touching existing repo."
  CLONE_REPO="${UPSTREAM_REPO}"
else
  echo "[*] Creating or using fork: ${GH_USER}/${REPO_NAME}"

  if gh repo view "${GH_USER}/${REPO_NAME}" >/dev/null 2>&1; then
    echo "[*] Fork already exists."
  else
    gh repo fork "${UPSTREAM_REPO}" --clone=false
  fi

  CLONE_REPO="${GH_USER}/${REPO_NAME}"
fi

echo "[*] Cloning ${CLONE_REPO} into ${WORK_DIR}"
gh repo clone "${CLONE_REPO}" "${WORK_DIR}"

cd "${WORK_DIR}"

if ! git remote | grep -qx "upstream"; then
  git remote add upstream "https://github.com/${UPSTREAM_REPO}.git"
fi

git fetch origin || true
git fetch upstream || true

if git show-ref --verify --quiet refs/remotes/origin/main; then
  BASE_BRANCH="main"
elif git show-ref --verify --quiet refs/remotes/origin/master; then
  BASE_BRANCH="master"
elif git show-ref --verify --quiet refs/remotes/upstream/main; then
  BASE_BRANCH="main"
elif git show-ref --verify --quiet refs/remotes/upstream/master; then
  BASE_BRANCH="master"
else
  echo "[!] Could not find main or master."
  exit 1
fi

echo "[*] Base branch: ${BASE_BRANCH}"

git checkout "${BASE_BRANCH}"

if git show-ref --verify --quiet "refs/remotes/upstream/${BASE_BRANCH}"; then
  git pull --ff-only upstream "${BASE_BRANCH}" || true
else
  git pull --ff-only origin "${BASE_BRANCH}" || true
fi

git checkout -b "${BRANCH_NAME}"

cat > "${PROMPT_FILE}" <<'EOF'
You are working locally in a NEW separate clone of mainframe-ai using Codex CLI.

CRITICAL LOCAL SAFETY RULE:
- Do not modify any existing local Apple Silicon setup.
- Do not modify any existing mainframe-ai directory outside the current working directory.
- Work only inside the current repository directory.
- This directory is intended to be a separate Apple Silicon fork-style workspace.

TASK:
Create an Apple Silicon-focused branch variant of mainframe-ai for local macOS development and inference.

BRANCHING RULES:
- You are already on branch feature/apple-silicon-bigiron.
- Do not modify main or master directly.
- Do not merge anything.
- Keep all changes isolated and easy to review.
- At the end, provide a PR-style summary.
- Do not push unless explicitly asked.

APPLE SILICON GOAL:
Make mainframe-ai easier to run on Apple Silicon Macs.

Target:
- macOS on Apple Silicon / ARM64
- Ollama + Mistral for local inference
- CPU-safe fallback behavior
- Homebrew-based setup where appropriate
- Clear docs for Mac users

Do not assume:
- NVIDIA CUDA
- Linux-only training
- x86_64-only paths
- Docker-only workflow

TRAINING BOUNDARY:
- Do not attempt heavy model fine-tuning in this branch.
- Do not add GPU-heavy CUDA training as the default.
- Do not run Axolotl training.
- If training is documented, explain that serious fine-tuning is better on Linux/CUDA/cloud GPU.
- This Apple Silicon branch is for local inference, RAG, validation, dataset prep, docs, and development.
- Apple Silicon can be used for local Ollama inference and lightweight scripts, not full production fine-tuning.

CONTENT RULES:
- Do not commit Redbook PDFs.
- Do not commit copyrighted IBM documentation.
- Do not paste copied IBM Redbook text into training data.
- Training examples should be original, safe, summarized examples that teach mainframe-native reasoning.
- Keep Redbooks/docs private and referenced only as RAG/private corpus material.

PROJECT GOAL:
Add an Apple Silicon-friendly scaffold to the existing mainframe-ai repo without breaking existing app behavior.

The branch should support:
1. Apple Silicon setup documentation
2. Ollama + Mistral local inference instructions
3. Optional local RAG usage
4. Safe training/eval dataset preparation
5. JSONL validation scripts
6. A Codex skill for Apple Silicon development
7. Clear warnings about what this branch does and does not do

ADD OR UPDATE THESE FILES:

1. docs/APPLE_SILICON.md

Explain how to run mainframe-ai on Apple Silicon.

Include:
- Install Homebrew if needed
- Install Python
- Install Git
- Install Ollama
- Pull Mistral with Ollama
- Start Ollama
- Run mainframe-ai
- Troubleshooting notes
- Explain that this branch targets local inference/dev, not heavy CUDA training

Mention:
- Apple Silicon = good for local Ollama inference
- Apple Silicon = good for RAG, docs, scripts, JSONL validation
- Apple Silicon = not ideal for serious QLoRA/Axolotl training compared with Linux/CUDA/cloud GPU

2. docs/MEMORY_ARCHITECTURE.md

Explain:
- short-term memory = current chat/session/current terminal/TN3270 context
- long-term memory = RAG/vector DB/docs/transcripts/private Redbooks
- fine-tuning = behavior/instincts, not fact storage
- skills/tools = repeatable actions the app or Codex can perform

Use BigIron.ai/mainframe examples:
- current terminal output
- current 3270 screen
- RAG snippets
- private Redbooks
- lab transcripts
- JCL/RACF/TSO/ISPF examples

3. docs/TRAINING_MISTRAL.md

Explain:
- This Apple Silicon branch uses Mistral/Ollama for local inference.
- Fine-tuning is separate from inference.
- The correct near-term approach is RAG + supervised examples + evals.
- Redbooks stay private in RAG, not committed.
- Training JSONL teaches mainframe-native behavior.
- Serious LoRA/QLoRA training is recommended on Linux x86_64 with NVIDIA CUDA or cloud GPU.
- Apple Silicon can still be used for dataset prep, validation, local testing, and inference.

4. data/training/examples/bigiron_sft_sample.jsonl

Add 10 safe sample supervised fine-tuning examples.

Each record must be one JSON object per line using this format:

{"messages":[{"role":"system","content":"..."},{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}

Topics:
- root vs RACF
- APF vs sudo
- writable PROCLIB
- JES as deferred execution
- datasets vs files
- VTAM/session fabric
- started task identity
- SMF evidence
- port-scan limitations
- Linux assumptions failing on mainframes

Rules:
- Do not copy IBM text.
- Keep examples original and summarized.
- Keep examples safe and educational.
- Avoid real-world offensive exploitation instructions.
- Make the assistant answer in BigIron.ai style.

5. data/evals/mainframe_eval_sample.jsonl

Add 20 eval questions.

Each record should be one JSON object per line with:

{
  "id": "eval_001",
  "question": "...",
  "ideal_keywords": ["...", "..."]
}

Eval topics:
- z/OS root misconception
- APF vs sudo
- writable PROCLIB
- /etc/passwd misconception
- port scan limitations
- JES spool/SYSOUT/SMF evidence
- datasets vs files
- started task identity
- JCL security relevance
- Unix assumptions failing on mainframes
- TSO
- ISPF
- APF libraries
- spool access
- VTAM exposure
- CICS transactions
- writable system datasets
- mainframe control-plane mindset
- explaining a finding
- why Redbooks should stay in RAG

6. scripts/training/validate_jsonl.py

Add a CPU-safe Python validator.

It should validate training JSONL:
- one JSON object per line
- messages array exists
- at least one user message
- at least one assistant message
- role must be system/user/assistant
- content must be non-empty string

It should validate eval JSONL:
- id exists
- question exists and is non-empty
- ideal_keywords exists and is a non-empty list of non-empty strings

CLI usage:

python3 scripts/training/validate_jsonl.py --mode training data/training/examples/bigiron_sft_sample.jsonl

python3 scripts/training/validate_jsonl.py --mode eval data/evals/mainframe_eval_sample.jsonl

7. scripts/apple_silicon_check.sh

Add a simple shell script that checks Apple Silicon readiness.

It should:
- print uname -m
- warn if architecture is not arm64
- check whether brew exists
- check whether python3 exists
- check whether ollama exists
- check whether git exists
- optionally run "ollama list" if Ollama exists
- print friendly next steps

Make it safe:
- no destructive commands
- no sudo
- no installs unless explicitly documented elsewhere
- just check and report

8. configs/ollama/Modelfile.bigiron-mistral

Add an example Ollama Modelfile for BigIron.ai Mistral behavior.

It should use Mistral as the base:

FROM mistral

SYSTEM """
You are BigIron.ai, a mainframe security assistant.
Use mainframe-native reasoning.
Avoid Unix/Linux assumptions unless explicitly comparing them.
Prefer RACF, JES, JCL, TSO, ISPF, datasets, APF, VTAM, CICS, SMF, started task identity, PROCLIB, PARMLIB, spool, and trust-boundary language.
Explain concepts as: concept, security impact, assessment angle, lab-safe example.
"""

9. .agents/skills/apple-silicon-mainframe-ai/SKILL.md

Create a Codex skill for this Apple Silicon branch.

The SKILL.md file should include YAML front matter with:
name: apple-silicon-mainframe-ai
description: Guidance for Apple Silicon/macOS local development and inference for mainframe-ai.

The skill should tell Codex:
- This branch targets Apple Silicon/macOS local dev and inference.
- Use Ollama + Mistral assumptions.
- Do not add CUDA-only requirements as defaults.
- Do not add Linux-only install assumptions as defaults.
- Keep scripts CPU-safe unless explicitly told otherwise.
- Do not commit Redbook PDFs or copyrighted IBM docs.
- Preserve existing routes and app behavior unless explicitly asked to change them.
- Prefer docs, validation scripts, setup checks, and optional configs.
- Heavy fine-tuning should be documented as external Linux/CUDA/cloud GPU work, not the default Apple Silicon path.

10. docs/CODEX_PROMPTS_APPLE_SILICON.md

Add reusable Codex prompts for:
- improving Apple Silicon setup docs
- checking Ollama/Mistral integration
- validating JSONL examples
- generating additional safe SFT examples
- adding eval questions
- improving RAG chunking without committing source PDFs
- reviewing the branch for accidental CUDA/Linux-only assumptions

11. README addition or new docs index

Do not rewrite the whole README unless necessary.

Add a small section or docs link that points to:
- docs/APPLE_SILICON.md
- docs/MEMORY_ARCHITECTURE.md
- docs/TRAINING_MISTRAL.md

Keep it minimal.

DESIRED BIGIRON.AI MODEL BEHAVIOR:
The model should avoid generic Unix/Linux assumptions.

Bad/default patterns to avoid:
- root
- sudo
- /etc/passwd
- chmod
- bash history
- generic Linux process model
- assuming all exposure is visible through a port scan

Mainframe-native concepts to prefer:
- RACF
- JES
- JCL
- TSO
- ISPF
- datasets
- dataset profiles
- APF
- VTAM
- CICS
- SMF
- started task identity
- PROCLIB
- PARMLIB
- spool
- trust boundary

VALIDATION:
After creating files:
- Run the JSONL validator on the sample SFT file.
- Run the JSONL validator on the sample eval file.
- Run the Apple Silicon check script if the environment supports shell execution.
- Do not run heavy model training.
- Do not download Redbooks.
- Do not add large model files to the repo.

COMMANDS TO RUN IF APPROPRIATE:

python3 scripts/training/validate_jsonl.py --mode training data/training/examples/bigiron_sft_sample.jsonl

python3 scripts/training/validate_jsonl.py --mode eval data/evals/mainframe_eval_sample.jsonl

bash scripts/apple_silicon_check.sh

FINAL RESPONSE:
When finished, provide:
1. Branch name used
2. Files added/modified
3. Validation results
4. Anything skipped and why
5. PR-style summary
6. Any follow-up commands I should run locally on my Apple Silicon Mac

Do not merge.
Do not modify main/master.
Do not push unless explicitly asked.
EOF

echo
echo "[*] Codex prompt written to:"
echo "    ${WORK_DIR}/${PROMPT_FILE}"

if command -v pbcopy >/dev/null 2>&1; then
  pbcopy < "${PROMPT_FILE}"
  echo "[*] Prompt copied to clipboard."
fi

echo
echo "[*] Launching Codex CLI inside the safe clone:"
echo "    ${WORK_DIR}"
echo

codex \
  --cd "${WORK_DIR}" \
  --sandbox workspace-write \
  --ask-for-approval on-request \
  "$(cat "${PROMPT_FILE}")"

echo
echo "[*] Codex finished or exited."
echo
echo "Review changes:"
echo "  cd \"${WORK_DIR}\""
echo "  git status"
echo "  git diff"
echo
echo "Validate manually if needed:"
echo "  python3 scripts/training/validate_jsonl.py --mode training data/training/examples/bigiron_sft_sample.jsonl"
echo "  python3 scripts/training/validate_jsonl.py --mode eval data/evals/mainframe_eval_sample.jsonl"
echo "  bash scripts/apple_silicon_check.sh"
echo
echo "Commit only after review:"
echo "  git add ."
echo "  git commit -m \"Add Apple Silicon BigIron scaffold\""
echo "  git push -u origin ${BRANCH_NAME}"
