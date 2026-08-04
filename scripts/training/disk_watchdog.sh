#!/bin/bash
# Disk space watchdog for training
# Monitors disk usage and cleans up old checkpoints when space is low

THRESHOLD_GB=50  # Clean when less than 50GB free
CHECK_INTERVAL=300  # Check every 5 minutes
LOG_FILE="/tmp/disk_watchdog.log"
TRAINING_DIR="/Users/w00tock/code/mainframe-ai-apple-silicon/data/training"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

get_free_space_gb() {
    df -g / | tail -1 | awk '{print $4}'
}

cleanup_checkpoints() {
    log "Running cleanup..."

    # Remove old numbered checkpoint files (keep only latest adapters.safetensors)
    local removed=0
    for f in "$TRAINING_DIR"/bigiron_full/weights/0*_adapters.safetensors; do
        if [ -f "$f" ]; then
            size=$(du -h "$f" | cut -f1)
            rm -f "$f"
            log "  Removed: $(basename $f) ($size)"
            ((removed++))
        fi
    done

    # Remove old RLVR checkpoints if they exist
    for f in "$TRAINING_DIR"/rlvr_checkpoints/0*_adapters.safetensors; do
        if [ -f "$f" ]; then
            size=$(du -h "$f" | cut -f1)
            rm -f "$f"
            log "  Removed: $(basename $f) ($size)"
            ((removed++))
        fi
    done

    # Clean temp JCL files from RLVR
    rm -f /tmp/rlvr_job_*.jcl 2>/dev/null

    # Clean old logs if they're huge
    for logfile in /tmp/mlx_train.log.prev /tmp/mlx_train_run*.log; do
        if [ -f "$logfile" ] && [ $(stat -f%z "$logfile" 2>/dev/null || echo 0) -gt 104857600 ]; then
            rm -f "$logfile"
            log "  Removed old log: $logfile"
            ((removed++))
        fi
    done

    if [ $removed -eq 0 ]; then
        log "  Nothing to clean"
    else
        log "  Cleaned $removed files"
    fi

    log "Free space now: $(get_free_space_gb)GB"
}

log "========================================"
log "Disk Watchdog Started"
log "========================================"
log "Threshold: ${THRESHOLD_GB}GB free"
log "Check interval: ${CHECK_INTERVAL}s"
log "Watching: $TRAINING_DIR"
log ""

while true; do
    free_gb=$(get_free_space_gb)

    if [ "$free_gb" -lt "$THRESHOLD_GB" ]; then
        log "⚠️  Low disk space: ${free_gb}GB free (threshold: ${THRESHOLD_GB}GB)"
        cleanup_checkpoints
    else
        # Silent check, only log every hour
        if [ $((SECONDS % 3600)) -lt $CHECK_INTERVAL ]; then
            log "✓ Disk OK: ${free_gb}GB free"
        fi
    fi

    sleep $CHECK_INTERVAL
done
