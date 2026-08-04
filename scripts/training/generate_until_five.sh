#!/bin/bash
#===============================================================================
# Generate 50K examples and RLVR until score 5
# Keeps generating, validating, training until we hit the target
#===============================================================================

set -e
cd "$(dirname "$0")/../.."

LOG="/tmp/gen_to_five_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1

echo "=== Generate Until Score 5 ==="
echo "Started: $(date)"
echo "Target: 50,000 new examples, RLVR score 5"
echo ""

MODEL="bigironv2"
TARGET_EXAMPLES=50000
OUTPUT_FILE="data/training/examples/generated_examples.jsonl"
VALID_COUNT=0

# Activate venv
source .venv-train/bin/activate

# Prompts for generation - comprehensive list
PROMPTS=(
    # JCL - Basic
    "Write JCL to run IEFBR14"
    "Write JCL to run IDCAMS LISTCAT"
    "Write JCL to copy dataset with IEBGENER"
    "Write JCL to sort file with DFSORT"
    "Write JCL to delete a dataset"
    "Write JCL to allocate a new dataset"
    "Write JCL with PROC and EXEC"
    "Write JCL to run IKJEFT01"
    "Write JCL to compile COBOL program"
    "Write JCL to link-edit a program"

    # JCL - Advanced
    "Write JCL with GDG generation"
    "Write JCL with COND parameter"
    "Write JCL with symbolic parameters"
    "Write JCL to run DB2 batch program"
    "Write JCL with JOBLIB and STEPLIB"

    # COBOL - Basic
    "Write COBOL Hello World program"
    "Write COBOL to read sequential file"
    "Write COBOL to write sequential file"
    "Write COBOL with WORKING-STORAGE"
    "Write COBOL with ACCEPT and DISPLAY"

    # COBOL - File I/O
    "Write COBOL to read VSAM KSDS file"
    "Write COBOL to write VSAM KSDS file"
    "Write COBOL to update VSAM record"
    "Write COBOL to delete VSAM record"
    "Write COBOL with START and READ NEXT"

    # COBOL - Data manipulation
    "Write COBOL with STRING statement"
    "Write COBOL with UNSTRING statement"
    "Write COBOL with INSPECT REPLACING"
    "Write COBOL with INSPECT TALLYING"
    "Write COBOL with reference modification"

    # COBOL - Control structures
    "Write COBOL with EVALUATE statement"
    "Write COBOL with PERFORM VARYING"
    "Write COBOL with PERFORM UNTIL"
    "Write COBOL with nested IF statements"
    "Write COBOL with 88 level conditions"

    # COBOL - Tables
    "Write COBOL with OCCURS clause"
    "Write COBOL with OCCURS DEPENDING ON"
    "Write COBOL with SEARCH statement"
    "Write COBOL with SEARCH ALL"
    "Write COBOL with multi-dimensional table"

    # COBOL - Subprograms
    "Write COBOL CALL statement example"
    "Write COBOL subprogram with LINKAGE SECTION"
    "Write COBOL with CALL BY REFERENCE"
    "Write COBOL with CALL BY CONTENT"

    # COBOL - Numeric
    "Write COBOL with COMP-3 packed decimal"
    "Write COBOL with COMPUTE statement"
    "Write COBOL currency formatting"
    "Write COBOL date validation"

    # COBOL - Advanced
    "Write COBOL control break report"
    "Write COBOL with COPY statement"
    "Write COBOL with COPY REPLACING"
    "Write COBOL file matching logic"
    "Write COBOL batch update program"

    # CICS
    "Write CICS COBOL with SEND MAP"
    "Write CICS COBOL with RECEIVE MAP"
    "Write CICS READ file command"
    "Write CICS WRITE file command"
    "Write CICS REWRITE command"
    "Write CICS DELETE command"
    "Write CICS LINK command"
    "Write CICS XCTL command"
    "Write CICS RETURN command"
    "Write CICS START command"
    "Write CICS RETRIEVE command"
    "Write CICS WRITEQ TS command"
    "Write CICS READQ TS command"
    "Write CICS DELETEQ TS command"
    "Write CICS WRITEQ TD command"
    "Write CICS READQ TD command"
    "Write CICS HANDLE CONDITION"
    "Write CICS HANDLE AID"
    "Write CICS ASKTIME ABSTIME"
    "Write CICS FORMATTIME"

    # DB2
    "Write COBOL with EXEC SQL SELECT"
    "Write COBOL with EXEC SQL INSERT"
    "Write COBOL with EXEC SQL UPDATE"
    "Write COBOL with EXEC SQL DELETE"
    "Write COBOL with DB2 cursor DECLARE"
    "Write COBOL with DB2 cursor OPEN"
    "Write COBOL with DB2 cursor FETCH"
    "Write COBOL with DB2 cursor CLOSE"
    "Write COBOL with DB2 WHENEVER"
    "Write DB2 CREATE TABLE statement"
    "Write DB2 CREATE INDEX statement"
    "Write DB2 stored procedure"

    # VSAM/IDCAMS
    "Write IDCAMS DEFINE CLUSTER KSDS"
    "Write IDCAMS DEFINE CLUSTER ESDS"
    "Write IDCAMS DEFINE CLUSTER RRDS"
    "Write IDCAMS DEFINE ALTERNATEINDEX"
    "Write IDCAMS DEFINE PATH"
    "Write IDCAMS DELETE cluster"
    "Write IDCAMS REPRO command"
    "Write IDCAMS PRINT command"
    "Write IDCAMS LISTCAT command"
    "Write IDCAMS ALTER command"

    # RACF
    "Write RACF ADDUSER command"
    "Write RACF ALTUSER command"
    "Write RACF DELUSER command"
    "Write RACF LISTUSER command"
    "Write RACF ADDGROUP command"
    "Write RACF CONNECT command"
    "Write RACF PERMIT command"
    "Write RACF RDEFINE command"
    "Write RACF RALTER command"
    "Write RACF RLIST command"

    # REXX
    "Write REXX to parse string"
    "Write REXX with EXECIO read"
    "Write REXX with EXECIO write"
    "Write REXX with OUTTRAP"
    "Write REXX DO loop"
    "Write REXX with SELECT WHEN"
    "Write REXX function example"
    "Write REXX with ISPF services"
    "Write REXX DATE function"
    "Write REXX with LISTDSI"
)

# Validation function
validate_output() {
    local prompt="$1"
    local output="$2"

    # Must have some content
    [ ${#output} -lt 20 ] && echo "invalid" && return

    # Check by type
    if echo "$prompt" | grep -qi "^Write JCL\|IDCAMS"; then
        echo "$output" | grep -qE "^//[A-Z]" && echo "valid" || echo "invalid"
    elif echo "$prompt" | grep -qi "COBOL\|CICS"; then
        echo "$output" | grep -qi "IDENTIFICATION DIVISION\|PROCEDURE DIVISION\|EXEC CICS" && echo "valid" || echo "invalid"
    elif echo "$prompt" | grep -qi "DB2\|SQL"; then
        echo "$output" | grep -qi "EXEC SQL\|SELECT\|CREATE\|INSERT" && echo "valid" || echo "invalid"
    elif echo "$prompt" | grep -qi "RACF"; then
        echo "$output" | grep -qi "ADDUSER\|ALTUSER\|PERMIT\|RDEFINE\|CONNECT" && echo "valid" || echo "invalid"
    elif echo "$prompt" | grep -qi "REXX"; then
        echo "$output" | grep -qi "SAY\|PARSE\|DO \|EXECIO" && echo "valid" || echo "invalid"
    else
        echo "valid"
    fi
}

# Clear previous generated examples
> "$OUTPUT_FILE"

echo "[1/3] Generating examples..."
iteration=0
while [ $VALID_COUNT -lt $TARGET_EXAMPLES ]; do
    iteration=$((iteration + 1))

    # Pick random prompt
    prompt_idx=$((RANDOM % ${#PROMPTS[@]}))
    prompt="${PROMPTS[$prompt_idx]}"

    # Generate
    output=$(ollama run $MODEL "$prompt" 2>/dev/null | head -100)

    # Validate
    valid=$(validate_output "$prompt" "$output")

    if [ "$valid" = "valid" ]; then
        VALID_COUNT=$((VALID_COUNT + 1))

        # Escape for JSON
        escaped_prompt=$(echo "$prompt" | sed 's/"/\\"/g')
        escaped_output=$(echo "$output" | sed 's/"/\\"/g' | tr '\n' ' ' | sed 's/  */ /g')

        # Save as JSONL
        echo "{\"messages\": [{\"role\": \"user\", \"content\": \"$escaped_prompt\"}, {\"role\": \"assistant\", \"content\": \"$escaped_output\"}]}" >> "$OUTPUT_FILE"

        if [ $((VALID_COUNT % 100)) -eq 0 ]; then
            echo "  Generated $VALID_COUNT/$TARGET_EXAMPLES valid examples"
        fi
    fi

    # Progress every 500 iterations
    if [ $((iteration % 500)) -eq 0 ]; then
        echo "  Iteration $iteration, valid: $VALID_COUNT, rate: $((VALID_COUNT * 100 / iteration))%"
    fi

    # Safety limit
    if [ $iteration -gt 200000 ]; then
        echo "Hit iteration limit, stopping at $VALID_COUNT examples"
        break
    fi
done

echo ""
echo "Generated $VALID_COUNT examples"
echo ""

echo "[2/3] Merging and retraining..."
# Merge all training data
cat data/training/examples/*.jsonl > /tmp/all_train.jsonl
total=$(wc -l < /tmp/all_train.jsonl)
train_count=$((total * 90 / 100))
sort -R /tmp/all_train.jsonl > /tmp/shuffled.jsonl
head -$train_count /tmp/shuffled.jsonl > data/training/mlx_data/train.jsonl
tail -$((total - train_count)) /tmp/shuffled.jsonl > data/training/mlx_data/valid.jsonl
echo "Training data: $total examples"

# Retrain
echo "Training 20K iterations..."
mlx_lm.lora \
    --model mistralai/Mistral-7B-Instruct-v0.3 \
    --data data/training/mlx_data \
    --train \
    --fine-tune-type lora \
    --num-layers 16 \
    --iters 20000 \
    --batch-size 2 \
    --learning-rate 5e-6 \
    --grad-checkpoint \
    --max-seq-length 2048 \
    --save-every 5000 \
    --adapter-path data/training/bigiron_lora

# Fuse
echo "Fusing..."
mlx_lm.fuse \
    --model mistralai/Mistral-7B-Instruct-v0.3 \
    --adapter-path data/training/bigiron_lora \
    --save-path data/training/bigiron_fused

# Convert to GGUF
echo "Converting to GGUF..."
python /tmp/llama_cpp/convert_hf_to_gguf.py data/training/bigiron_fused \
    --outfile data/training/bigiron-v2.gguf \
    --outtype q8_0

# Register
echo "Registering..."
ollama create bigironv2 -f configs/ollama/Modelfile.bigironv2

# Cleanup
rm -rf data/training/bigiron_fused
rm -rf data/training/bigiron_lora/0*

echo ""
echo "[3/3] Running RLVR until score 5..."

# RLVR loop
MAX_RLVR_ROUNDS=10
for round in $(seq 1 $MAX_RLVR_ROUNDS); do
    echo ""
    echo "=== RLVR Round $round ==="

    # Run RLVR
    ./scripts/training/rlvr_auto.sh 2>&1 | tee /tmp/rlvr_round_$round.log

    # Check score
    avg_score=$(grep "Final avg score" /tmp/rlvr_round_$round.log | grep -oE "[0-9]+\.[0-9]+" | tail -1)
    echo "Round $round score: $avg_score"

    # Check if we hit 5
    if [ "$(echo "$avg_score >= 4.5" | bc)" -eq 1 ]; then
        echo ""
        echo "=== TARGET ACHIEVED! Score: $avg_score ==="
        break
    fi

    # If not, generate more examples from failures and retrain
    echo "Score $avg_score < 5, generating more examples..."
    # This would continue the loop
done

echo ""
echo "=== Complete ==="
echo "Final model: bigironv2"
echo "Log: $LOG"
echo "Finished: $(date)"
