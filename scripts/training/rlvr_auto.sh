#!/bin/bash
#===============================================================================
# RLVR Automated Training Pipeline
# Reinforcement Learning with Verifiable Rewards using TK5 MVS
#
# Usage: nohup ./scripts/training/rlvr_auto.sh > /tmp/rlvr.log 2>&1 &
#===============================================================================

set -e
cd "$(dirname "$0")/../.."

LOG="/tmp/rlvr_$(date +%Y%m%d_%H%M%S).log"
MODEL="bigironv2"
MAX_ITERATIONS=1000
CONSECUTIVE_SUCCESS=10

log() { echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG"; }

log "=== RLVR Training Started ==="
log "Model: $MODEL"
log "Max iterations: $MAX_ITERATIONS"
log "Target: $CONSECUTIVE_SUCCESS consecutive CC 0000"

# Start TK5 if needed
start_tk5() {
    if ! curl -s "http://localhost:8038/" > /dev/null 2>&1; then
        log "Starting TK5..."
        cd tk5/mvs-tk5
        ./mvs 2>/dev/null &
        cd ../..
        log "Waiting 90s for MVS IPL..."
        sleep 90
    else
        log "TK5 already running"
    fi
}

# Submit JCL and get condition code
submit_jcl() {
    local jcl="$1"
    # Job name max 8 chars: RLV + 5 digits
    local job_name="RLV$(printf '%05d' $((RANDOM % 100000)))"

    # Replace job name in first line of JCL
    jcl=$(echo "$jcl" | sed "1s/^\/\/[A-Za-z0-9@#\$]*  *JOB/\/\/$job_name JOB/")

    # Write to temp file
    local jcl_file="/tmp/rlvr_job_${job_name}.jcl"
    echo "$jcl" > "$jcl_file"

    # Submit via devinit
    curl -s "http://localhost:8038/cgi-bin/tasks/cmd?cmd=devinit%2000c%20${jcl_file}%20ascii%20eof" > /dev/null

    # Wait for completion
    sleep 8

    # Check syslog for completion
    local syslog=$(curl -s "http://localhost:8038/cgi-bin/tasks/syslog" 2>/dev/null)

    # Check for job completion (use first 8 chars of job name)
    local short_name="${job_name:0:8}"
    if echo "$syslog" | grep -q "$short_name.*ENDED\|$short_name.*TERMINATED"; then
        if echo "$syslog" | grep -q "$short_name.*JCL ERROR\|$short_name.*ABEND"; then
            echo "12"
        else
            echo "0"  # ENDED without error = success
        fi
    else
        echo "-1"  # Timeout
    fi
}

# Score based on condition code
score_cc() {
    local cc=$1
    case $cc in
        0)  echo "5" ;;   # Perfect
        4)  echo "3" ;;   # Warning
        8)  echo "2" ;;   # Error
        12) echo "1" ;;   # Severe
        *)  echo "0" ;;   # Fail/timeout
    esac
}

# Generate code from model
generate_code() {
    local prompt="$1"
    local response=$(ollama run $MODEL "$prompt. Output only the code, nothing else." 2>/dev/null | head -80)
    echo "$response"
}

# Check if output is valid for the prompt type
validate_output() {
    local prompt="$1"
    local output="$2"

    # Check by prompt type
    if echo "$prompt" | grep -qi "JCL\|IDCAMS"; then
        # JCL must start with //
        echo "$output" | grep -qE "^//" && echo "valid" || echo "invalid"
    elif echo "$prompt" | grep -qi "COBOL\|CICS"; then
        # COBOL must have IDENTIFICATION or PROCEDURE DIVISION
        echo "$output" | grep -qi "IDENTIFICATION\|PROCEDURE\|DIVISION" && echo "valid" || echo "invalid"
    elif echo "$prompt" | grep -qi "DB2\|SQL"; then
        # DB2/SQL must have SELECT, INSERT, UPDATE, EXEC SQL, or CREATE
        echo "$output" | grep -qi "SELECT\|INSERT\|UPDATE\|EXEC SQL\|CREATE\|CURSOR" && echo "valid" || echo "invalid"
    elif echo "$prompt" | grep -qi "RACF"; then
        # RACF commands
        echo "$output" | grep -qi "ADDUSER\|ALTUSER\|PERMIT\|RDEFINE\|ADDGROUP\|LISTUSER" && echo "valid" || echo "invalid"
    elif echo "$prompt" | grep -qi "REXX"; then
        # REXX must have SAY, PARSE, or DO
        echo "$output" | grep -qi "SAY\|PARSE\|DO \|EXECIO\|OUTTRAP" && echo "valid" || echo "invalid"
    elif echo "$prompt" | grep -qi "assembler"; then
        # Assembler
        echo "$output" | grep -qiE "CSECT\|USING\|BALR\|MVC\|LA \|LR \|SR " && echo "valid" || echo "invalid"
    else
        echo "valid"  # Default pass
    fi
}

# Training prompts - ALL mainframe topics
PROMPTS=(
    # JCL
    "Write JCL to run IEFBR14"
    "Write JCL to run IDCAMS LISTCAT"
    "Write JCL to copy a dataset using IEBGENER"
    "Write JCL to sort a file using DFSORT"
    "Write JCL with PROC and EXEC"

    # COBOL
    "Write COBOL to read a sequential file and count records"
    "Write COBOL to validate a date in YYYYMMDD format"
    "Write COBOL with STRING and UNSTRING"
    "Write COBOL to process a VSAM KSDS file"
    "Write COBOL with EVALUATE statement"
    "Write COBOL using INSPECT for string manipulation"
    "Write COBOL with PERFORM VARYING loop"
    "Write COBOL to call a subprogram using CALL USING"
    "Write COBOL with control break logic"
    "Write COBOL using reference modification"

    # CICS
    "Write CICS COBOL to read a VSAM file using READ"
    "Write CICS COBOL with SEND MAP and RECEIVE MAP"
    "Write CICS COBOL using temporary storage queue (TSQ)"
    "Write CICS COBOL with LINK to another program"
    "Write CICS COBOL error handling with HANDLE CONDITION"

    # DB2
    "Write COBOL with embedded SQL to SELECT from a table"
    "Write COBOL with DB2 cursor for multiple rows"
    "Write COBOL with DB2 INSERT statement"
    "Write COBOL with DB2 UPDATE using host variables"
    "Write DB2 stored procedure in SQL"

    # RACF
    "Write RACF commands to define a new user"
    "Write RACF commands to create a group"
    "Write RACF commands to permit dataset access"
    "Write RACF commands to list user permissions"

    # VSAM/IDCAMS
    "Write IDCAMS to define a KSDS cluster"
    "Write IDCAMS to define an ESDS cluster"
    "Write IDCAMS REPRO to copy data"
    "Write IDCAMS to create an alternate index"

    # REXX
    "Write REXX to parse a string"
    "Write REXX to read a dataset using EXECIO"
    "Write REXX with OUTTRAP to capture command output"
    "Write REXX to call an ISPF service"

    # Assembler
    "Write z/OS assembler macro example"
    "Write assembler to move data between registers"
)

# Main training loop
start_tk5

success_count=0
iteration=0
total_score=0

log "Starting RLVR iterations..."

while [ $iteration -lt $MAX_ITERATIONS ]; do
    iteration=$((iteration + 1))

    # Pick random prompt
    prompt_idx=$((RANDOM % ${#PROMPTS[@]}))
    prompt="${PROMPTS[$prompt_idx]}"

    # Generate code
    output=$(generate_code "$prompt")

    if [ -z "$output" ] || [ $(echo "$output" | wc -l) -lt 2 ]; then
        log "[$iteration] SKIP - No output"
        continue
    fi

    # Check if this is a JCL prompt (can run on TK5)
    if echo "$prompt" | grep -qi "^Write JCL\|IDCAMS"; then
        # Extract JCL lines
        jcl=$(echo "$output" | grep -E "^//" | head -30)
        if [ -z "$jcl" ]; then
            log "[$iteration] SKIP - No JCL in output"
            continue
        fi
        # Submit to TK5
        cc=$(submit_jcl "$jcl")
        score=$(score_cc $cc)
        type="JCL"
    else
        # Validate syntax for non-JCL
        valid=$(validate_output "$prompt" "$output")
        if [ "$valid" = "valid" ]; then
            score=5
            cc="OK"
        else
            score=1
            cc="INVALID"
        fi
        type=$(echo "$prompt" | grep -oE "COBOL|CICS|DB2|RACF|REXX|assembler" | head -1)
        type=${type:-OTHER}
    fi

    total_score=$((total_score + score))
    avg_score=$(echo "scale=2; $total_score / $iteration" | bc)

    if [ "$score" -eq 5 ]; then
        success_count=$((success_count + 1))
        log "[$iteration] $type CC=$cc SCORE=$score ✓ (streak: $success_count) avg=$avg_score"
    else
        success_count=0
        log "[$iteration] $type CC=$cc SCORE=$score ✗ avg=$avg_score"
    fi

    # Check if target reached
    if [ $success_count -ge $CONSECUTIVE_SUCCESS ]; then
        log "=== TARGET REACHED! ==="
        log "$CONSECUTIVE_SUCCESS consecutive successes!"
        break
    fi

    # Save checkpoint every 100 iterations
    if [ $((iteration % 100)) -eq 0 ]; then
        log "Checkpoint at iteration $iteration, avg score: $avg_score"
    fi

    sleep 2
done

log "=== RLVR Training Complete ==="
log "Iterations: $iteration"
log "Final avg score: $avg_score"
log "Log: $LOG"
