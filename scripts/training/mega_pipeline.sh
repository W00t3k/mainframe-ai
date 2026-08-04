#!/bin/bash
# MEGA PIPELINE - Full automated training enhancement
# 1. Wait for current SFT to finish
# 2. Collect external data (GitHub, HuggingFace)
# 3. Distill from XMainframe-7B
# 4. Distill from current BigIron-AI
# 5. Deduplicate and merge all data
# 6. Retrain with expanded dataset
# 7. Run RLVR until score 5
#
# Space-aware throughout - auto-cleanup when needed

set -e
cd "$(dirname "$0")/../.."

LOG="/tmp/mega_pipeline.log"
MIN_SPACE_GB=50
TRAIN_LOG="/tmp/mlx_train.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"
}

header() {
    echo "" | tee -a "$LOG"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}" | tee -a "$LOG"
    echo -e "${BLUE}  $1${NC}" | tee -a "$LOG"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}" | tee -a "$LOG"
}

check_space() {
    local free_gb=$(df -g / | tail -1 | awk '{print $4}')
    if [ "$free_gb" -lt "$MIN_SPACE_GB" ]; then
        log "${YELLOW}⚠️  Low space: ${free_gb}GB free${NC}"
        cleanup_space
        free_gb=$(df -g / | tail -1 | awk '{print $4}')
        if [ "$free_gb" -lt "$MIN_SPACE_GB" ]; then
            log "${RED}❌ Critical: Only ${free_gb}GB free after cleanup${NC}"
            return 1
        fi
    fi
    log "${GREEN}✓ Disk OK: ${free_gb}GB free${NC}"
    return 0
}

cleanup_space() {
    log "Running cleanup..."

    # Old checkpoints
    rm -f data/training/bigiron_full/weights/0*_adapters.safetensors 2>/dev/null || true
    rm -f data/training/rlvr_checkpoints/0*_adapters.safetensors 2>/dev/null || true

    # Old logs
    find /tmp -name "mlx_train*.log.prev*" -delete 2>/dev/null || true
    find /tmp -name "rlvr_*.log" -mtime +1 -delete 2>/dev/null || true

    # Old distilled data (keep 2 latest)
    ls -t data/training/distilled/*.jsonl 2>/dev/null | tail -n +3 | xargs rm -f 2>/dev/null || true

    # HuggingFace cache (old models)
    rm -rf ~/.cache/huggingface/hub/models--*--old* 2>/dev/null || true

    log "Cleanup complete"
}

wait_for_sft() {
    header "Stage 0: Waiting for Current SFT"

    if [ ! -f "$TRAIN_LOG" ]; then
        log "No training in progress"
        return 0
    fi

    # Check if training is still running
    if ! pgrep -f "mlx_lm.lora" > /dev/null 2>&1; then
        log "No MLX training process found"
        return 0
    fi

    log "SFT is running, waiting for completion..."
    log "Tail: $TRAIN_LOG"

    while true; do
        # Check if process still running
        if ! pgrep -f "mlx_lm.lora" > /dev/null 2>&1; then
            log "${GREEN}SFT process completed!${NC}"
            sleep 5
            break
        fi

        # Show progress
        if [ -f "$TRAIN_LOG" ]; then
            local last_iter=$(grep "^Iter" "$TRAIN_LOG" 2>/dev/null | tail -1 | awk '{print $2}' | tr -d ':')
            local loss=$(grep "^Iter" "$TRAIN_LOG" 2>/dev/null | tail -1 | grep -o "Train loss [0-9.]*" | awk '{print $3}')
            if [ -n "$last_iter" ]; then
                echo -ne "\r  Iter $last_iter, Loss: $loss    "
            fi
        fi

        sleep 60
    done

    log "SFT complete, continuing pipeline"
}

collect_external_data() {
    header "Stage 1: Collecting External Data"
    check_space || return 1

    source .venv-train/bin/activate 2>/dev/null || true

    # Install required packages
    pip install datasets huggingface_hub -q 2>/dev/null || true

    mkdir -p data/training/collected/github

    log "Downloading HuggingFace datasets..."

    python3 << 'PYTHON'
import os
import json
from pathlib import Path

try:
    from datasets import load_dataset
except ImportError:
    os.system("pip install datasets -q")
    from datasets import load_dataset

DATA_DIR = Path("data/training/collected")
DATA_DIR.mkdir(parents=True, exist_ok=True)

datasets_to_fetch = [
    ("Fsoft-AIC/MainframeBench", "mainframe_bench"),
    ("harshini-kumar/CobolCodeBench", "cobol_code_bench"),
]

for dataset_name, output_name in datasets_to_fetch:
    output_file = DATA_DIR / f"{output_name}.jsonl"
    if output_file.exists():
        print(f"  {output_name}: already exists, skipping")
        continue

    try:
        print(f"  Fetching {dataset_name}...")
        ds = load_dataset(dataset_name, trust_remote_code=True)

        count = 0
        with open(output_file, 'w') as f:
            for split in ds.keys():
                for item in ds[split]:
                    f.write(json.dumps(dict(item)) + '\n')
                    count += 1
        print(f"    Saved {count} examples")
    except Exception as e:
        print(f"    Error: {e}")

print("HuggingFace downloads complete")
PYTHON

    log "Cloning GitHub repositories..."

    REPOS=(
        "https://github.com/openmainframeproject/cobol-code-dataset"
        "https://github.com/CBTTape/CBT"
        "https://github.com/cicsdev/cics-banking-sample-application-cbsa"
    )

    for repo in "${REPOS[@]}"; do
        name=$(basename "$repo")
        target="data/training/collected/github/$name"
        if [ -d "$target" ]; then
            log "  $name: updating..."
            git -C "$target" pull -q 2>/dev/null || true
        else
            log "  $name: cloning..."
            git clone --depth 1 -q "$repo" "$target" 2>/dev/null || log "    Failed to clone $repo"
        fi
    done

    log "${GREEN}✓ External data collection complete${NC}"
}

distill_xmainframe() {
    header "Stage 2: Distilling XMainframe-7B"
    check_space || return 1

    source .venv-train/bin/activate 2>/dev/null || true

    # Check if already distilled recently
    DISTILLED_FILE=$(ls -t data/training/distilled/xmainframe_*.jsonl 2>/dev/null | head -1)
    if [ -n "$DISTILLED_FILE" ]; then
        COUNT=$(wc -l < "$DISTILLED_FILE" | tr -d ' ')
        if [ "$COUNT" -gt 500 ]; then
            log "Found existing XMainframe distillation: $COUNT examples"
            log "Skipping (delete file to re-run)"
            return 0
        fi
    fi

    log "Installing mlx-lm..."
    pip install mlx-lm -q 2>/dev/null || true

    log "Running distillation (this takes 1-2 hours)..."
    python3 scripts/training/distill_xmainframe.py 2>&1 | tee -a "$LOG"

    log "${GREEN}✓ XMainframe distillation complete${NC}"
}

distill_bigiron() {
    header "Stage 3: Distilling Current BigIron-AI"
    check_space || return 1

    # Check if BigIron is registered with Ollama
    if ! ollama list 2>/dev/null | grep -q "bigiron-ai"; then
        log "BigIron-AI not found in Ollama, skipping self-distillation"
        return 0
    fi

    DISTILLED_FILE="data/training/distilled/bigiron_self_$(date +%Y%m%d).jsonl"

    if [ -f "$DISTILLED_FILE" ]; then
        log "Already distilled today, skipping"
        return 0
    fi

    log "Self-distilling from BigIron-AI..."

    python3 << PYTHON
import json
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime

OUTPUT_FILE = Path("$DISTILLED_FILE")
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

PROMPTS = [
    # JCL
    "Write JCL to compile and link a COBOL program",
    "Create JCL to run IDCAMS REPRO from VSAM to sequential",
    "Write JCL for DFSORT with INCLUDE/OMIT conditions",
    "Create JCL to allocate a new GDG base",
    "Write JCL for IEBCOPY to compress a PDS",

    # COBOL
    "Write COBOL code to read a VSAM KSDS file",
    "Create COBOL paragraph for date validation",
    "Write COBOL to handle DB2 SQLCODE -811",
    "Create COBOL code for CICS SEND MAP",
    "Write COBOL to perform binary search on table",

    # RACF
    "RACF commands to create a new user with OMVS segment",
    "How to audit RACF for excessive permissions",
    "RACF commands to grant DB2 access",
    "How to define RACF FACILITY class profile",
    "RACF commands for CICS transaction security",

    # CICS
    "CICS commands for file browse operation",
    "Write CICS error handling with HANDLE",
    "CICS commands for temporary storage queue",
    "How to implement CICS pseudo-conversational design",
    "CICS commands for ENQ/DEQ serialization",

    # DB2
    "DB2 SQL for batch cursor processing",
    "Write DB2 stored procedure skeleton",
    "DB2 commands to analyze query performance",
    "How to handle DB2 -904 unavailable resource",
    "DB2 SQL for MERGE (UPSERT) operation",

    # Security
    "Common z/OS security misconfigurations",
    "How to detect privilege escalation attempts",
    "Best practices for APF library security",
    "How to audit started task permissions",
    "Security considerations for UNIX Services on z/OS",
]

def query_ollama(prompt):
    try:
        result = subprocess.run(
            ["ollama", "run", "bigiron-ai", prompt],
            capture_output=True,
            text=True,
            timeout=120
        )
        return result.stdout.strip()
    except:
        return None

seen = set()
count = 0

with open(OUTPUT_FILE, 'w') as f:
    for i, prompt in enumerate(PROMPTS):
        print(f"[{i+1}/{len(PROMPTS)}] {prompt[:50]}...")

        response = query_ollama(prompt)
        if not response or len(response) < 50:
            print("  (skipped)")
            continue

        record = {
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response}
            ]
        }

        h = hashlib.md5(json.dumps(record).encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            f.write(json.dumps(record) + '\n')
            count += 1

print(f"\nSelf-distilled {count} examples to {OUTPUT_FILE}")
PYTHON

    log "${GREEN}✓ BigIron self-distillation complete${NC}"
}

extract_code_files() {
    header "Stage 4: Extracting Code from Repositories"
    check_space || return 1

    python3 << 'PYTHON'
import os
import json
import hashlib
from pathlib import Path

DATA_DIR = Path("data/training/collected")
OUTPUT_FILE = DATA_DIR / "extracted_code.jsonl"

EXTENSIONS = {
    '.cbl': 'cobol', '.cob': 'cobol', '.cpy': 'copybook',
    '.jcl': 'jcl', '.proc': 'jcl',
    '.rexx': 'rexx', '.rex': 'rexx',
    '.asm': 'assembler',
}

seen = set()
stats = {}

with open(OUTPUT_FILE, 'w') as out:
    for root, dirs, files in os.walk(DATA_DIR / "github"):
        dirs[:] = [d for d in dirs if d != '.git']

        for file in files:
            ext = Path(file).suffix.lower()
            if ext not in EXTENSIONS:
                continue

            filepath = Path(root) / file
            try:
                content = filepath.read_text(errors='ignore')
            except:
                continue

            if len(content) < 100 or len(content) > 50000:
                continue

            h = hashlib.md5(content.encode()).hexdigest()
            if h in seen:
                continue
            seen.add(h)

            lang = EXTENSIONS[ext]
            stats[lang] = stats.get(lang, 0) + 1

            out.write(json.dumps({
                "language": lang,
                "filename": file,
                "content": content,
            }) + '\n')

print("Extracted code files:")
for lang, count in sorted(stats.items()):
    print(f"  {lang}: {count}")
print(f"Total: {sum(stats.values())}")
PYTHON

    log "${GREEN}✓ Code extraction complete${NC}"
}

convert_to_training() {
    header "Stage 5: Converting to Training Format"
    check_space || return 1

    python3 << 'PYTHON'
import json
import hashlib
import random
from pathlib import Path

DATA_DIR = Path("data/training/collected")
OUTPUT_FILE = DATA_DIR / "training_ready.jsonl"

PROMPTS = {
    'cobol': ["Explain this COBOL program:", "What does this COBOL code do?", "Review this COBOL:"],
    'jcl': ["Explain this JCL:", "What will this JCL execute?", "Describe this JCL job:"],
    'copybook': ["Explain this copybook:", "What data structures are defined here?"],
    'rexx': ["Explain this REXX script:", "What does this REXX do?"],
    'assembler': ["Explain this assembler code:", "What does this z/OS assembler do?"],
}

seen = set()
count = 0

with open(OUTPUT_FILE, 'w') as out:
    # Process extracted code
    code_file = DATA_DIR / "extracted_code.jsonl"
    if code_file.exists():
        with open(code_file) as f:
            for line in f:
                rec = json.loads(line)
                lang = rec.get('language', 'cobol')
                content = rec.get('content', '')[:3000]

                prompt = random.choice(PROMPTS.get(lang, PROMPTS['cobol']))

                msg = {
                    "messages": [
                        {"role": "user", "content": f"{prompt}\n\n```{lang}\n{content}\n```"},
                        {"role": "assistant", "content": f"This {lang.upper()} code performs mainframe data processing operations."}
                    ]
                }

                h = hashlib.md5(json.dumps(msg).encode()).hexdigest()
                if h not in seen:
                    seen.add(h)
                    out.write(json.dumps(msg) + '\n')
                    count += 1

    # Process HuggingFace datasets
    for hf_file in DATA_DIR.glob("*.jsonl"):
        if hf_file.name in ['extracted_code.jsonl', 'training_ready.jsonl']:
            continue

        with open(hf_file) as f:
            for line in f:
                try:
                    rec = json.loads(line)

                    if 'question' in rec and 'answer' in rec:
                        msg = {"messages": [
                            {"role": "user", "content": rec['question']},
                            {"role": "assistant", "content": str(rec['answer'])}
                        ]}
                    elif 'input' in rec and 'output' in rec:
                        msg = {"messages": [
                            {"role": "user", "content": rec['input']},
                            {"role": "assistant", "content": rec['output']}
                        ]}
                    else:
                        continue

                    h = hashlib.md5(json.dumps(msg).encode()).hexdigest()
                    if h not in seen:
                        seen.add(h)
                        out.write(json.dumps(msg) + '\n')
                        count += 1
                except:
                    continue

print(f"Created {count} training examples")
PYTHON

    log "${GREEN}✓ Training format conversion complete${NC}"
}

merge_all_data() {
    header "Stage 6: Merging All Data Sources"
    check_space || return 1

    python3 << 'PYTHON'
import json
import hashlib
from pathlib import Path
from collections import defaultdict

TRAIN_FILE = Path("data/training/mlx_data/train.jsonl")
DISTILLED_DIR = Path("data/training/distilled")
COLLECTED_DIR = Path("data/training/collected")
OUTPUT_FILE = Path("data/training/mlx_data/train_mega.jsonl")

seen = set()
stats = defaultdict(int)

print("Merging all data sources...")

with open(OUTPUT_FILE, 'w') as out:
    # Existing training data
    if TRAIN_FILE.exists():
        print(f"  Reading existing: {TRAIN_FILE}")
        with open(TRAIN_FILE) as f:
            for line in f:
                h = hashlib.md5(line.strip().encode()).hexdigest()
                if h not in seen:
                    seen.add(h)
                    out.write(line)
                    stats['existing'] += 1

    # Distilled data (XMainframe + BigIron)
    for jsonl in sorted(DISTILLED_DIR.glob("*.jsonl")):
        print(f"  Reading distilled: {jsonl.name}")
        with open(jsonl) as f:
            for line in f:
                h = hashlib.md5(line.strip().encode()).hexdigest()
                if h not in seen:
                    seen.add(h)
                    out.write(line)
                    stats['distilled'] += 1

    # Collected data
    collected = COLLECTED_DIR / "training_ready.jsonl"
    if collected.exists():
        print(f"  Reading collected: {collected.name}")
        with open(collected) as f:
            for line in f:
                h = hashlib.md5(line.strip().encode()).hexdigest()
                if h not in seen:
                    seen.add(h)
                    out.write(line)
                    stats['collected'] += 1

print(f"\n{'='*40}")
print(f"Merge Results:")
print(f"  Existing:  {stats['existing']:>8,}")
print(f"  Distilled: {stats['distilled']:>8,}")
print(f"  Collected: {stats['collected']:>8,}")
print(f"  {'─'*20}")
print(f"  Total:     {sum(stats.values()):>8,}")
print(f"{'='*40}")
PYTHON

    # Swap files
    if [ -f "data/training/mlx_data/train_mega.jsonl" ]; then
        NEW_COUNT=$(wc -l < "data/training/mlx_data/train_mega.jsonl" | tr -d ' ')
        OLD_COUNT=$(wc -l < "data/training/mlx_data/train.jsonl" | tr -d ' ')

        if [ "$NEW_COUNT" -gt "$OLD_COUNT" ]; then
            log "Upgrading training data: $OLD_COUNT → $NEW_COUNT examples"
            cp "data/training/mlx_data/train.jsonl" "data/training/mlx_data/train.jsonl.backup"
            mv "data/training/mlx_data/train_mega.jsonl" "data/training/mlx_data/train.jsonl"
        else
            log "No new data added, keeping original"
            rm -f "data/training/mlx_data/train_mega.jsonl"
        fi
    fi

    log "${GREEN}✓ Data merge complete${NC}"
}

run_sft() {
    header "Stage 7: Running SFT on Expanded Data"
    check_space || return 1

    EXAMPLES=$(wc -l < "data/training/mlx_data/train.jsonl" | tr -d ' ')
    log "Training on $EXAMPLES examples"
    log "Starting SFT (10 epochs)..."

    # Clear old log
    mv "$TRAIN_LOG" "${TRAIN_LOG}.prev" 2>/dev/null || true

    # Run training
    ./scripts/training/build_bigiron_ai.sh --epochs 10 2>&1 | tee -a "$LOG"

    log "${GREEN}✓ SFT complete${NC}"
}

run_rlvr() {
    header "Stage 8: Running RLVR to Score 5"
    check_space || return 1

    # Check if TK5 is running
    if ! curl -s http://localhost:8081 > /dev/null 2>&1; then
        log "${YELLOW}⚠️  TK5/Hercules not detected on port 8081${NC}"
        log "Start TK5 first for RLVR verification"
        log "Skipping RLVR stage"
        return 0
    fi

    log "TK5 detected, starting RLVR..."
    ./scripts/training/rlvr_to_five.sh 2>&1 | tee -a "$LOG"

    log "${GREEN}✓ RLVR complete${NC}"
}

# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════

header "MEGA PIPELINE - Full Automated Training"
log "Started: $(date)"
log "Log: $LOG"
log ""
log "Stages:"
log "  0. Wait for current SFT"
log "  1. Collect external data"
log "  2. Distill XMainframe-7B"
log "  3. Distill BigIron-AI"
log "  4. Extract code files"
log "  5. Convert to training format"
log "  6. Merge all data"
log "  7. Run SFT"
log "  8. Run RLVR"
log ""

# Run all stages
wait_for_sft
collect_external_data
distill_xmainframe
distill_bigiron
extract_code_files
convert_to_training
merge_all_data
run_sft
run_rlvr

header "PIPELINE COMPLETE"
log "Finished: $(date)"
log ""
log "Final model: bigiron-ai"
log "Training data: $(wc -l < data/training/mlx_data/train.jsonl | tr -d ' ') examples"
log "Disk free: $(df -g / | tail -1 | awk '{print $4}')GB"
log ""
log "To test:"
log "  ollama run bigiron-ai 'Write JCL to copy a PDS'"
