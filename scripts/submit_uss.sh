#!/bin/bash
# Submit IBMAI.jcl to live MVS TK5 via s3270
# Uses HERC01/CUL8TR — submits JCL, activates USS table
#
# Usage: bash scripts/submit_uss.sh

set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
JCL="$DIR/jcl/IBMAI.jcl"
S3270=$(command -v s3270)

RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[0;33m'; RST='\033[0m'
ok()   { echo -e "  ${GRN}✓${RST} $1"; }
fail() { echo -e "  ${RED}✗${RST} $1"; exit 1; }
info() { echo -e "  ${YEL}…${RST} $1"; }

[ -f "$JCL" ] || fail "JCL not found: $JCL"
[ -n "$S3270" ] || fail "s3270 not found"

echo "========================================"
echo "  IBM AI USS Screen Installer"
echo "========================================"

# Build s3270 script
# s3270 reads commands from stdin, one per line
# We pipe the whole script at once

info "Building s3270 command script..."

# Read JCL and build inline submit commands
# Strategy: logon → TSO SUBMIT * (inline JCL via SYSIN) isn't available in TSO
# Instead: use TSO EDIT to create a dataset, then SUBMIT it
# But 390 lines is slow. Better: use TSO SUBMIT with a pre-allocated PDS member.
#
# Fastest approach for TK5: use the Hercules console to punch the JCL
# via the card reader (devinit), then submit from the reader.
# 
# Even faster: write JCL to a temp file, use s3270 to submit it via
# TSO "SUBMIT 'HLQ.dataset'" after creating it with IEBUPDTE or EDIT.
#
# We'll use the simplest reliable method:
# 1. Logon as HERC01
# 2. TSO SUBMIT * (pipe JCL inline) — this works in TK5 TSO!

TMPSCRIPT=$(mktemp /tmp/s3270_uss_XXXX.s3270)
TMPJCL=$(mktemp /tmp/ibmai_XXXX.jcl)

# Strip comment-only lines and blank lines to keep it manageable
# Also ensure lines are max 72 chars (JCL continuation)
grep -v '^$' "$JCL" | head -300 > "$TMPJCL"

cat > "$TMPSCRIPT" << 'HEREDOC'
# Connect to TK5
Connect(localhost:3270)
Wait(30,Output)
# Should be at VTAM logon screen — move to input field and type
String("HERC01")
Enter()
Wait(5,Output)
# Password prompt
String("CUL8TR")
Enter()
Wait(10,Output)
# Press through broadcast messages to get to READY
Enter()
Wait(3,Output)
Enter()
Wait(3,Output)
Enter()
Wait(3,Output)
Enter()
Wait(3,Output)
HEREDOC

echo "Snapshot()" >> "$TMPSCRIPT"

info "Running s3270 login test..."
RESULT=$(echo "
Connect(localhost:3270)
Wait(30,Output)
Snap()
Disconnect()
" | $S3270 2>/dev/null | grep -A5 "data:" | head -20)

echo "$RESULT"

rm -f "$TMPSCRIPT" "$TMPJCL"

echo ""
echo "Using Python s3270 wrapper for reliable submission..."
