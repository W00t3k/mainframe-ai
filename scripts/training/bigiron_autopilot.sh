#!/bin/bash
#===============================================================================
# BigIron-AI Autopilot - Fully Automated Training Pipeline
#===============================================================================
# Features:
#   - Generates examples until target count
#   - Validates all outputs
#   - Retrains model automatically
#   - Runs RLVR verification
#   - Watchdog restarts on crash
#   - Checkpoints progress (resume on restart)
#   - Disk space monitoring
#   - Runs until RLVR score >= 5
#
# Usage:
#   ./bigiron_autopilot.sh              # Run with defaults
#   ./bigiron_autopilot.sh --resume     # Resume from checkpoint
#   ./bigiron_autopilot.sh --examples 100000  # Custom example count
#
# Monitor:
#   tail -f /tmp/bigiron_autopilot.log
#
# Stop gracefully:
#   touch /tmp/bigiron_stop
#===============================================================================

set -euo pipefail

#-------------------------------------------------------------------------------
# Configuration
#-------------------------------------------------------------------------------
PROJECT_DIR="/Users/w00tock/code/mainframe-ai-apple-silicon"
LOG_FILE="/tmp/bigiron_autopilot.log"
CHECKPOINT_FILE="/tmp/bigiron_checkpoint.json"
STOP_FILE="/tmp/bigiron_stop"
PID_FILE="/tmp/bigiron_autopilot.pid"

TARGET_EXAMPLES=${TARGET_EXAMPLES:-50000}
TARGET_SCORE=${TARGET_SCORE:-4.5}
TRAIN_ITERS=${TRAIN_ITERS:-20000}
MAX_ROUNDS=${MAX_ROUNDS:-10}
MIN_DISK_GB=${MIN_DISK_GB:-20}

MODEL_NAME="bigironv2"
GENERATION_MODEL="llama3.1:8b"  # Use better model for generating training data
BASE_MODEL="mistralai/Mistral-7B-Instruct-v0.3"

#-------------------------------------------------------------------------------
# Parse arguments
#-------------------------------------------------------------------------------
RESUME=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --resume) RESUME=true; shift ;;
        --examples) TARGET_EXAMPLES="$2"; shift 2 ;;
        --score) TARGET_SCORE="$2"; shift 2 ;;
        --iters) TRAIN_ITERS="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

#-------------------------------------------------------------------------------
# Setup
#-------------------------------------------------------------------------------
cd "$PROJECT_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

# Remove stop file if exists
rm -f "$STOP_FILE"

# Save PID
echo $$ > "$PID_FILE"

# Cleanup on exit
cleanup() {
    rm -f "$PID_FILE"
    log "Autopilot stopped"
}
trap cleanup EXIT

#-------------------------------------------------------------------------------
# Logging
#-------------------------------------------------------------------------------
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_section() {
    echo ""
    echo "==============================================================================="
    log "$1"
    echo "==============================================================================="
}

#-------------------------------------------------------------------------------
# Checkpoint functions
#-------------------------------------------------------------------------------
save_checkpoint() {
    local phase="$1"
    local progress="$2"
    local round="${3:-0}"
    cat > "$CHECKPOINT_FILE" << EOF
{
    "phase": "$phase",
    "progress": $progress,
    "round": $round,
    "timestamp": "$(date -Iseconds)",
    "examples_generated": $EXAMPLES_GENERATED,
    "current_score": $CURRENT_SCORE
}
EOF
    log "Checkpoint saved: phase=$phase, progress=$progress"
}

load_checkpoint() {
    if [[ -f "$CHECKPOINT_FILE" ]]; then
        CHECKPOINT_PHASE=$(jq -r '.phase' "$CHECKPOINT_FILE" 2>/dev/null || echo "")
        CHECKPOINT_PROGRESS=$(jq -r '.progress' "$CHECKPOINT_FILE" 2>/dev/null || echo "0")
        CHECKPOINT_ROUND=$(jq -r '.round' "$CHECKPOINT_FILE" 2>/dev/null || echo "0")
        EXAMPLES_GENERATED=$(jq -r '.examples_generated' "$CHECKPOINT_FILE" 2>/dev/null || echo "0")
        CURRENT_SCORE=$(jq -r '.current_score' "$CHECKPOINT_FILE" 2>/dev/null || echo "0")
        log "Loaded checkpoint: phase=$CHECKPOINT_PHASE, progress=$CHECKPOINT_PROGRESS"
        return 0
    fi
    return 1
}

#-------------------------------------------------------------------------------
# Watchdog - restart on crash
#-------------------------------------------------------------------------------
watchdog() {
    local cmd="$1"
    local max_retries=3
    local retry=0

    while [[ $retry -lt $max_retries ]]; do
        if [[ -f "$STOP_FILE" ]]; then
            log "Stop file detected, exiting watchdog"
            return 1
        fi

        log "Running: $cmd (attempt $((retry + 1))/$max_retries)"
        if eval "$cmd"; then
            return 0
        fi

        retry=$((retry + 1))
        log "Command failed, retry $retry/$max_retries in 30s..."
        sleep 30
    done

    log "ERROR: Command failed after $max_retries attempts"
    return 1
}

#-------------------------------------------------------------------------------
# Health checks
#-------------------------------------------------------------------------------
check_disk_space() {
    local available_gb=$(df -g "$PROJECT_DIR" | awk 'NR==2 {print $4}')
    if [[ $available_gb -lt $MIN_DISK_GB ]]; then
        log "ERROR: Low disk space: ${available_gb}GB < ${MIN_DISK_GB}GB required"
        return 1
    fi
    return 0
}

check_ollama() {
    if ! pgrep -x "ollama" > /dev/null; then
        log "Starting Ollama..."
        ollama serve &
        sleep 5
    fi
    return 0
}

check_tk5() {
    if ! curl -s "http://localhost:8038/" > /dev/null 2>&1; then
        log "Starting TK5..."
        cd "$PROJECT_DIR/tk5/mvs-tk5" && ./start_tk5.sh &
        cd "$PROJECT_DIR"
        sleep 90
    fi
    return 0
}

should_stop() {
    [[ -f "$STOP_FILE" ]]
}

#-------------------------------------------------------------------------------
# Prompts for generation
#-------------------------------------------------------------------------------
PROMPTS=(
    # JCL
    "Write JCL to run IEFBR14"
    "Write JCL to run IDCAMS LISTCAT"
    "Write JCL to copy a dataset using IEBGENER"
    "Write JCL to sort a file using DFSORT"
    "Write JCL to delete a dataset"
    "Write JCL to allocate a new dataset"
    "Write JCL with PROC and EXEC"
    "Write JCL to compile COBOL program"
    "Write JCL with GDG dataset"
    "Write JCL with COND parameter"
    "Write JCL to run IKJEFT01 for TSO batch"
    "Write JCL with symbolic parameters"
    "Write JCL to run a DB2 batch program"
    "Write JCL with JOBLIB DD statement"
    "Write JCL for multi-step job"

    # COBOL - Basic
    "Write COBOL program to display Hello World"
    "Write COBOL to read a sequential file"
    "Write COBOL to write a sequential file"
    "Write COBOL with ACCEPT and DISPLAY statements"
    "Write COBOL with WORKING-STORAGE SECTION"

    # COBOL - File I/O
    "Write COBOL to read VSAM KSDS file"
    "Write COBOL to write VSAM KSDS record"
    "Write COBOL to update VSAM record"
    "Write COBOL to delete VSAM record"
    "Write COBOL to browse VSAM file with START"

    # COBOL - String handling
    "Write COBOL with STRING statement"
    "Write COBOL with UNSTRING statement"
    "Write COBOL with INSPECT REPLACING"
    "Write COBOL with INSPECT TALLYING"
    "Write COBOL with reference modification"
    "Write COBOL with intrinsic functions"

    # COBOL - Control flow
    "Write COBOL with EVALUATE statement"
    "Write COBOL with PERFORM VARYING loop"
    "Write COBOL with PERFORM UNTIL"
    "Write COBOL with nested IF statements"
    "Write COBOL with 88 level condition names"

    # COBOL - Tables
    "Write COBOL with OCCURS clause"
    "Write COBOL with OCCURS DEPENDING ON"
    "Write COBOL with SEARCH statement"
    "Write COBOL with SEARCH ALL binary search"
    "Write COBOL with multi-dimensional table"

    # COBOL - Subprograms
    "Write COBOL CALL statement"
    "Write COBOL subprogram with LINKAGE SECTION"
    "Write COBOL with CALL BY REFERENCE"
    "Write COBOL with CALL BY CONTENT"

    # COBOL - Numeric
    "Write COBOL with COMP-3 packed decimal"
    "Write COBOL with COMPUTE statement"
    "Write COBOL for currency editing"
    "Write COBOL date validation routine"

    # COBOL - Advanced
    "Write COBOL control break report"
    "Write COBOL with COPY statement"
    "Write COBOL file matching program"
    "Write COBOL batch update program"
    "Write COBOL with SORT USING"

    # CICS
    "Write CICS COBOL with SEND MAP"
    "Write CICS COBOL with RECEIVE MAP"
    "Write CICS READ command"
    "Write CICS WRITE command"
    "Write CICS REWRITE command"
    "Write CICS DELETE command"
    "Write CICS LINK to another program"
    "Write CICS XCTL command"
    "Write CICS RETURN command"
    "Write CICS WRITEQ TS command"
    "Write CICS READQ TS command"
    "Write CICS temporary storage queue example"
    "Write CICS transient data queue example"
    "Write CICS HANDLE CONDITION"
    "Write CICS ASKTIME and FORMATTIME"

    # DB2
    "Write COBOL with embedded SQL SELECT"
    "Write COBOL with embedded SQL INSERT"
    "Write COBOL with embedded SQL UPDATE"
    "Write COBOL with embedded SQL DELETE"
    "Write COBOL with DB2 cursor"
    "Write COBOL DB2 FETCH loop"
    "Write COBOL with SQLCODE checking"
    "Write DB2 CREATE TABLE statement"
    "Write DB2 CREATE INDEX statement"
    "Write DB2 stored procedure"

    # VSAM/IDCAMS
    "Write IDCAMS DEFINE CLUSTER for KSDS"
    "Write IDCAMS DEFINE CLUSTER for ESDS"
    "Write IDCAMS DEFINE CLUSTER for RRDS"
    "Write IDCAMS DEFINE ALTERNATEINDEX"
    "Write IDCAMS DELETE command"
    "Write IDCAMS REPRO command"
    "Write IDCAMS LISTCAT command"
    "Write IDCAMS PRINT command"

    # RACF
    "Write RACF ADDUSER command"
    "Write RACF ALTUSER command"
    "Write RACF LISTUSER command"
    "Write RACF ADDGROUP command"
    "Write RACF CONNECT command"
    "Write RACF PERMIT command"
    "Write RACF RDEFINE command"
    "Write RACF RALTER command"

    # REXX
    "Write REXX to parse a string"
    "Write REXX with EXECIO to read dataset"
    "Write REXX with EXECIO to write dataset"
    "Write REXX with OUTTRAP"
    "Write REXX DO loop"
    "Write REXX with SELECT WHEN"
    "Write REXX external function"
    "Write REXX with ISPF services"
    "Write REXX DATE and TIME functions"
    "Write REXX with LISTDSI"
)

#-------------------------------------------------------------------------------
# Validation
#-------------------------------------------------------------------------------
validate_output() {
    local prompt="$1"
    local output="$2"

    # Must have content
    [[ ${#output} -lt 30 ]] && echo "invalid" && return

    # Check by type
    if echo "$prompt" | grep -qi "^Write JCL\|IDCAMS"; then
        echo "$output" | grep -qE "^//[A-Z@#$]" && echo "valid" || echo "invalid"
    elif echo "$prompt" | grep -qi "COBOL\|CICS"; then
        echo "$output" | grep -qi "IDENTIFICATION DIVISION\|PROCEDURE DIVISION\|EXEC CICS" && echo "valid" || echo "invalid"
    elif echo "$prompt" | grep -qi "DB2\|SQL"; then
        echo "$output" | grep -qi "EXEC SQL\|SELECT \|CREATE \|INSERT " && echo "valid" || echo "invalid"
    elif echo "$prompt" | grep -qi "RACF"; then
        echo "$output" | grep -qi "ADDUSER\|ALTUSER\|PERMIT\|RDEFINE\|CONNECT\|ADDGROUP" && echo "valid" || echo "invalid"
    elif echo "$prompt" | grep -qi "REXX"; then
        echo "$output" | grep -qi "SAY \|PARSE \|DO \|EXECIO\|ADDRESS " && echo "valid" || echo "invalid"
    else
        echo "valid"
    fi
}

#-------------------------------------------------------------------------------
# Phase 1: Generate examples
#-------------------------------------------------------------------------------
phase_generate() {
    log_section "PHASE 1: Generating $TARGET_EXAMPLES examples"

    local output_file="$PROJECT_DIR/data/training/examples/generated_examples.jsonl"
    local start_count=0

    # Resume from checkpoint
    if [[ "$RESUME" == true ]] && [[ -f "$output_file" ]]; then
        start_count=$(wc -l < "$output_file" | tr -d ' ')
        log "Resuming from $start_count examples"
    else
        > "$output_file"
    fi

    EXAMPLES_GENERATED=$start_count
    local iteration=0
    local num_prompts=${#PROMPTS[@]}

    while [[ $EXAMPLES_GENERATED -lt $TARGET_EXAMPLES ]]; do
        # Check for stop signal
        if should_stop; then
            log "Stop signal received"
            save_checkpoint "generate" $EXAMPLES_GENERATED
            return 1
        fi

        # Health checks every 100 iterations
        if [[ $((iteration % 100)) -eq 0 ]]; then
            check_disk_space || return 1
            check_ollama || return 1
        fi

        iteration=$((iteration + 1))

        # Pick random prompt
        local prompt_idx=$((RANDOM % num_prompts))
        local prompt="${PROMPTS[$prompt_idx]}"

        # Generate using a capable model (not the one we're training)
        # Use gtimeout on macOS (from coreutils)
        local output
        output=$(gtimeout 60 ollama run "$GENERATION_MODEL" "$prompt. Output only the code, no explanation." 2>/dev/null | head -100) || continue

        # Validate
        local valid
        valid=$(validate_output "$prompt" "$output")

        if [[ "$valid" == "valid" ]]; then
            EXAMPLES_GENERATED=$((EXAMPLES_GENERATED + 1))

            # Escape for JSON
            local escaped_prompt escaped_output
            escaped_prompt=$(printf '%s' "$prompt" | jq -Rs '.')
            escaped_output=$(printf '%s' "$output" | jq -Rs '.')

            # Save as JSONL
            echo "{\"messages\": [{\"role\": \"user\", \"content\": $escaped_prompt}, {\"role\": \"assistant\", \"content\": $escaped_output}]}" >> "$output_file"

            # Progress
            if [[ $((EXAMPLES_GENERATED % 500)) -eq 0 ]]; then
                local rate=$((EXAMPLES_GENERATED * 100 / iteration))
                log "Generated $EXAMPLES_GENERATED/$TARGET_EXAMPLES (${rate}% success rate)"
                save_checkpoint "generate" $EXAMPLES_GENERATED
            fi
        fi

        # Safety limit
        if [[ $iteration -gt 500000 ]]; then
            log "Hit iteration limit"
            break
        fi
    done

    log "Generated $EXAMPLES_GENERATED examples"
    save_checkpoint "generate_complete" $EXAMPLES_GENERATED
    return 0
}

#-------------------------------------------------------------------------------
# Phase 2: Train model
#-------------------------------------------------------------------------------
phase_train() {
    log_section "PHASE 2: Training model ($TRAIN_ITERS iterations)"

    source "$PROJECT_DIR/.venv-train/bin/activate"

    # Merge training data
    log "Merging training data..."
    cat "$PROJECT_DIR"/data/training/examples/*.jsonl > /tmp/all_train.jsonl
    local total=$(wc -l < /tmp/all_train.jsonl | tr -d ' ')
    local train_count=$((total * 90 / 100))

    sort -R /tmp/all_train.jsonl > /tmp/shuffled.jsonl
    head -$train_count /tmp/shuffled.jsonl > "$PROJECT_DIR/data/training/mlx_data/train.jsonl"
    tail -$((total - train_count)) /tmp/shuffled.jsonl > "$PROJECT_DIR/data/training/mlx_data/valid.jsonl"

    log "Training data: $total examples (train: $train_count)"

    # Train
    log "Starting LoRA training..."
    watchdog "mlx_lm.lora \
        --model $BASE_MODEL \
        --data $PROJECT_DIR/data/training/mlx_data \
        --train \
        --fine-tune-type lora \
        --num-layers 16 \
        --iters $TRAIN_ITERS \
        --batch-size 2 \
        --learning-rate 5e-6 \
        --grad-checkpoint \
        --max-seq-length 2048 \
        --save-every 5000 \
        --adapter-path $PROJECT_DIR/data/training/bigiron_lora" || return 1

    save_checkpoint "train_complete" $TRAIN_ITERS
    return 0
}

#-------------------------------------------------------------------------------
# Phase 3: Fuse and convert
#-------------------------------------------------------------------------------
phase_convert() {
    log_section "PHASE 3: Fusing and converting model"

    source "$PROJECT_DIR/.venv-train/bin/activate"

    # Fuse
    log "Fusing adapters..."
    watchdog "mlx_lm.fuse \
        --model $BASE_MODEL \
        --adapter-path $PROJECT_DIR/data/training/bigiron_lora \
        --save-path $PROJECT_DIR/data/training/bigiron_fused" || return 1

    # Convert to GGUF
    log "Converting to GGUF..."
    if [[ ! -d "/tmp/llama_cpp" ]]; then
        git clone --depth 1 https://github.com/ggerganov/llama.cpp /tmp/llama_cpp
    fi

    watchdog "python /tmp/llama_cpp/convert_hf_to_gguf.py \
        $PROJECT_DIR/data/training/bigiron_fused \
        --outfile $PROJECT_DIR/data/training/bigiron-v2.gguf \
        --outtype q8_0" || return 1

    # Register with Ollama
    log "Registering with Ollama..."
    ollama create "$MODEL_NAME" -f "$PROJECT_DIR/configs/ollama/Modelfile.bigironv2"

    # Cleanup
    rm -rf "$PROJECT_DIR/data/training/bigiron_fused"
    rm -rf "$PROJECT_DIR/data/training/bigiron_lora"/0*

    save_checkpoint "convert_complete" 100
    return 0
}

#-------------------------------------------------------------------------------
# Phase 4: RLVR verification
#-------------------------------------------------------------------------------
phase_rlvr() {
    local round=${1:-1}
    log_section "PHASE 4: RLVR Verification (Round $round)"

    check_tk5 || return 1

    # Run RLVR
    "$PROJECT_DIR/scripts/training/rlvr_auto.sh" 2>&1 | tee /tmp/rlvr_round_$round.log

    # Get score
    CURRENT_SCORE=$(grep "Final avg score" /tmp/rlvr_round_$round.log | grep -oE "[0-9]+\.[0-9]+" | tail -1 || echo "0")

    log "RLVR Round $round Score: $CURRENT_SCORE"
    save_checkpoint "rlvr" "$CURRENT_SCORE" "$round"

    # Check if target reached
    if (( $(echo "$CURRENT_SCORE >= $TARGET_SCORE" | bc -l) )); then
        return 0
    fi
    return 1
}

#-------------------------------------------------------------------------------
# Main
#-------------------------------------------------------------------------------
main() {
    log_section "BigIron-AI Autopilot Started"
    log "Target: $TARGET_EXAMPLES examples, score >= $TARGET_SCORE"
    log "Resume: $RESUME"

    EXAMPLES_GENERATED=0
    CURRENT_SCORE=0

    # Load checkpoint if resuming
    if [[ "$RESUME" == true ]]; then
        load_checkpoint || true
    fi

    # Initial health checks
    check_disk_space || exit 1
    check_ollama || exit 1

    # Main loop - keep going until we hit target score
    for round in $(seq 1 $MAX_ROUNDS); do
        log_section "=== ROUND $round / $MAX_ROUNDS ==="

        if should_stop; then
            log "Stop signal received"
            exit 0
        fi

        # Phase 1: Generate examples (first round only, or if score too low)
        if [[ $round -eq 1 ]] || (( $(echo "$CURRENT_SCORE < 3.0" | bc -l) )); then
            phase_generate || exit 1
        fi

        # Phase 2: Train
        phase_train || exit 1

        # Phase 3: Convert
        phase_convert || exit 1

        # Phase 4: RLVR
        if phase_rlvr $round; then
            log_section "TARGET ACHIEVED! Score: $CURRENT_SCORE"
            break
        fi

        log "Score $CURRENT_SCORE < $TARGET_SCORE, continuing..."

        # Generate more examples for next round
        TARGET_EXAMPLES=$((TARGET_EXAMPLES + 10000))
    done

    log_section "Autopilot Complete"
    log "Final Score: $CURRENT_SCORE"
    log "Model: $MODEL_NAME"

    # Cleanup
    rm -f "$CHECKPOINT_FILE"
}

main "$@"
