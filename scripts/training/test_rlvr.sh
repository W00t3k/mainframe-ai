#!/bin/bash
# Quick test of RLVR pipeline - single JCL generation and submission

cd "$(dirname "$0")/../.."

MODEL="bigiron-ai"
HERC_HTTP="http://localhost:8038"

echo "=== RLVR Pipeline Test ==="

# 1. Generate JCL
echo "Generating JCL from $MODEL..."
JCL=$(ollama run $MODEL "Write JCL to run IEFBR14. Output only valid JCL, nothing else." 2>/dev/null)
echo "Generated:"
echo "$JCL"
echo ""

# 2. Clean and prepare JCL
# Extract just the JCL lines
CLEAN_JCL=$(echo "$JCL" | grep -E "^//")

# Ensure job name
if ! echo "$CLEAN_JCL" | head -1 | grep -q "JOB"; then
    CLEAN_JCL="//RLVRTEST JOB (ACCT),'TEST',CLASS=A,MSGCLASS=X
$CLEAN_JCL"
fi

echo "Clean JCL:"
echo "$CLEAN_JCL"
echo ""

# 3. Write to temp file
JCL_FILE="/tmp/rlvr_test.jcl"
echo "$CLEAN_JCL" > "$JCL_FILE"
echo "Saved to: $JCL_FILE"

# 4. Submit via Hercules console
echo "Submitting to TK5..."
curl -s "$HERC_HTTP/cgi-bin/tasks/cmd?cmd=devinit%2000c%20${JCL_FILE}%20ascii%20eof" > /dev/null

# 5. Wait and check
echo "Waiting for completion (15s)..."
sleep 15

# 6. Check result
echo "Checking syslog..."
SYSLOG=$(curl -s "$HERC_HTTP/cgi-bin/tasks/syslog" 2>/dev/null | grep -v "^<" | tail -30)
echo "$SYSLOG"

# 7. Parse result
if echo "$SYSLOG" | grep -qi "RLVR\|IEFBR14.*ENDED\|CC 0000"; then
    echo ""
    echo "=== SUCCESS: Job completed ==="
    if echo "$SYSLOG" | grep -qi "MAXCC=0000\|CC 0000"; then
        echo "SCORE: 5 (CC 0000)"
    elif echo "$SYSLOG" | grep -qi "ABEND\|ERROR"; then
        echo "SCORE: 1 (Error)"
    else
        echo "SCORE: 3 (Warning/Unknown)"
    fi
else
    echo ""
    echo "=== Job not found in syslog ==="
fi
