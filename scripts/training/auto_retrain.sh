#!/bin/bash
# Auto-retrain after current run completes
# Monitors /tmp/mlx_train.log for completion, then starts new training

set -e
cd "$(dirname "$0")/../.."

LOG_FILE="/tmp/mlx_train.log"
TRAIN_SCRIPT="./scripts/training/build_bigiron_ai.sh"

echo "=============================================="
echo "Auto-Retrain Monitor"
echo "=============================================="
echo "Watching: $LOG_FILE"
echo "Will run: $TRAIN_SCRIPT --epochs 10"
echo ""
echo "Current training data: $(wc -l < data/training/mlx_data/train.jsonl) examples"
echo ""

# Function to check if training is complete
check_complete() {
    if [ -f "$LOG_FILE" ]; then
        # Look for completion indicators
        if grep -q "Saving final model" "$LOG_FILE" 2>/dev/null; then
            return 0
        fi
        if grep -q "Training complete" "$LOG_FILE" 2>/dev/null; then
            return 0
        fi
        # Check if adapters were saved (MLX completion)
        if grep -q "Saved adapter" "$LOG_FILE" 2>/dev/null; then
            # Make sure it's the final save, not a checkpoint
            local last_iter=$(grep "^Iter" "$LOG_FILE" | tail -1 | awk '{print $2}' | tr -d ':')
            local total_iter=$(grep "iters_per_epoch" "$LOG_FILE" | head -1 | grep -o 'total.*' | grep -o '[0-9]*' | head -1)
            if [ -n "$last_iter" ] && [ -n "$total_iter" ]; then
                if [ "$last_iter" -ge "$total_iter" ] 2>/dev/null; then
                    return 0
                fi
            fi
        fi
    fi
    return 1
}

# Function to get current progress
get_progress() {
    if [ -f "$LOG_FILE" ]; then
        local last_line=$(grep "^Iter" "$LOG_FILE" | tail -1)
        if [ -n "$last_line" ]; then
            echo "$last_line" | awk '{print $2, $4, $6}'
        fi
    fi
}

echo "Monitoring training progress..."
echo "Press Ctrl+C to cancel"
echo ""

# Wait for completion
while true; do
    if check_complete; then
        echo ""
        echo "=============================================="
        echo "Current training COMPLETE!"
        echo "=============================================="
        break
    fi

    # Show progress every 60 seconds
    progress=$(get_progress)
    if [ -n "$progress" ]; then
        echo -ne "\r[$(date '+%H:%M:%S')] $progress                    "
    fi

    sleep 60
done

echo ""
echo "Waiting 30 seconds before starting new training..."
sleep 30

echo ""
echo "=============================================="
echo "Starting NEW training run with updated data"
echo "=============================================="
echo "Training examples: $(wc -l < data/training/mlx_data/train.jsonl)"
echo ""

# Clear old log
mv "$LOG_FILE" "${LOG_FILE}.prev" 2>/dev/null || true

# Start new training (10 epochs for the incremental data)
$TRAIN_SCRIPT --epochs 10

echo ""
echo "=============================================="
echo "Retrain complete!"
echo "=============================================="
