#!/bin/bash
# Full Data Pipeline - Collect, Distill, Dedupe, Train
# Space-aware throughout

set -e
cd "$(dirname "$0")/../.."

MIN_SPACE_GB=50
LOG="/tmp/data_pipeline.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"
}

check_space() {
    local free_gb=$(df -g / | tail -1 | awk '{print $4}')
    log "Disk space: ${free_gb}GB free"
    if [ "$free_gb" -lt "$MIN_SPACE_GB" ]; then
        log "⚠️  LOW SPACE: ${free_gb}GB < ${MIN_SPACE_GB}GB minimum"
        return 1
    fi
    return 0
}

cleanup_if_needed() {
    if ! check_space; then
        log "Running emergency cleanup..."

        # Remove old checkpoints
        rm -f data/training/bigiron_full/weights/0*_adapters.safetensors 2>/dev/null
        rm -f data/training/rlvr_checkpoints/0*_adapters.safetensors 2>/dev/null

        # Remove old logs
        find /tmp -name "mlx_train*.log*" -mtime +1 -delete 2>/dev/null

        # Remove old distilled data (keep latest)
        ls -t data/training/distilled/*.jsonl 2>/dev/null | tail -n +2 | xargs rm -f 2>/dev/null

        check_space || {
            log "❌ Still not enough space after cleanup!"
            exit 1
        }
    fi
}

log "========================================"
log "Full Data Pipeline"
log "========================================"
log "Stages:"
log "  1. Collect from GitHub/HuggingFace"
log "  2. Distill from XMainframe-7B"
log "  3. Deduplicate all data"
log "  4. Merge into training set"
log "========================================"

# Check initial space
cleanup_if_needed

# ============================================
# Stage 1: Collect external data
# ============================================
log ""
log "=== Stage 1: Collecting External Data ==="
cleanup_if_needed

if [ -f scripts/training/collect_mainframe_data.sh ]; then
    bash scripts/training/collect_mainframe_data.sh 2>&1 | tee -a "$LOG"
else
    log "Skipping collection (script not found)"
fi

# ============================================
# Stage 2: Distill from XMainframe
# ============================================
log ""
log "=== Stage 2: Distilling from XMainframe ==="
cleanup_if_needed

# Check if we should run distillation
if [ "${SKIP_DISTILL:-}" != "1" ]; then
    source .venv-train/bin/activate 2>/dev/null || true

    # Check if mlx-lm is installed
    if python3 -c "import mlx_lm" 2>/dev/null; then
        log "Running distillation (this takes a while)..."
        python3 scripts/training/distill_xmainframe.py 2>&1 | tee -a "$LOG"
    else
        log "Installing mlx-lm..."
        pip install mlx-lm -q
        python3 scripts/training/distill_xmainframe.py 2>&1 | tee -a "$LOG"
    fi
else
    log "Skipping distillation (SKIP_DISTILL=1)"
fi

# ============================================
# Stage 3: Deduplicate and Merge
# ============================================
log ""
log "=== Stage 3: Deduplicating and Merging ==="
cleanup_if_needed

python3 << 'PYTHON'
import json
import hashlib
from pathlib import Path
from collections import defaultdict

TRAIN_FILE = Path("data/training/mlx_data/train.jsonl")
DISTILLED_DIR = Path("data/training/distilled")
COLLECTED_DIR = Path("data/training/collected")
OUTPUT_FILE = Path("data/training/mlx_data/train_expanded.jsonl")

seen_hashes = set()
stats = defaultdict(int)

print("Deduplicating and merging all data sources...")

with open(OUTPUT_FILE, 'w') as out:
    # 1. Read existing training data
    if TRAIN_FILE.exists():
        with open(TRAIN_FILE) as f:
            for line in f:
                h = hashlib.md5(line.strip().encode()).hexdigest()
                if h not in seen_hashes:
                    seen_hashes.add(h)
                    out.write(line)
                    stats['existing'] += 1

    # 2. Add distilled data
    for jsonl in sorted(DISTILLED_DIR.glob("*.jsonl")):
        with open(jsonl) as f:
            for line in f:
                h = hashlib.md5(line.strip().encode()).hexdigest()
                if h not in seen_hashes:
                    seen_hashes.add(h)
                    out.write(line)
                    stats['distilled'] += 1

    # 3. Add collected data
    collected_file = COLLECTED_DIR / "training_ready.jsonl"
    if collected_file.exists():
        with open(collected_file) as f:
            for line in f:
                h = hashlib.md5(line.strip().encode()).hexdigest()
                if h not in seen_hashes:
                    seen_hashes.add(h)
                    out.write(line)
                    stats['collected'] += 1

print(f"\nMerge complete:")
print(f"  Existing:  {stats['existing']:,}")
print(f"  Distilled: {stats['distilled']:,}")
print(f"  Collected: {stats['collected']:,}")
print(f"  ─────────────────")
print(f"  Total:     {sum(stats.values()):,}")
print(f"\nOutput: {OUTPUT_FILE}")
PYTHON

# ============================================
# Stage 4: Swap in new training file
# ============================================
log ""
log "=== Stage 4: Finalizing ==="

NEW_FILE="data/training/mlx_data/train_expanded.jsonl"
CURRENT_FILE="data/training/mlx_data/train.jsonl"
BACKUP_FILE="data/training/mlx_data/train.jsonl.bak"

if [ -f "$NEW_FILE" ]; then
    NEW_COUNT=$(wc -l < "$NEW_FILE" | tr -d ' ')
    OLD_COUNT=$(wc -l < "$CURRENT_FILE" | tr -d ' ')

    log "Old training set: $OLD_COUNT examples"
    log "New training set: $NEW_COUNT examples"

    if [ "$NEW_COUNT" -gt "$OLD_COUNT" ]; then
        # Backup old
        cp "$CURRENT_FILE" "$BACKUP_FILE"
        # Swap in new
        mv "$NEW_FILE" "$CURRENT_FILE"
        log "✅ Training data updated!"
        log "   Backup at: $BACKUP_FILE"
    else
        log "⚠️  New data not larger, keeping original"
        rm -f "$NEW_FILE"
    fi
fi

# Final space check
cleanup_if_needed

log ""
log "========================================"
log "Pipeline Complete!"
log "========================================"
log "Training data: $(wc -l < data/training/mlx_data/train.jsonl | tr -d ' ') examples"
log "Disk space: $(df -g / | tail -1 | awk '{print $4}')GB free"
log ""
log "To train on this data:"
log "  ./scripts/training/build_bigiron_ai.sh --epochs 10"
