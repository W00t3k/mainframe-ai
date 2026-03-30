#!/bin/bash
#
# Linux-specific startup script for MVS TK5 mainframe
# Simplified for debugging Hercules 3.13 compatibility
#

set -e

# Colors
RED='\033[0;31m'
GRN='\033[0;32m'
YEL='\033[1;33m'
BLD='\033[1m'
RST='\033[0m'

ok()   { echo -e "  ${GRN}✓${RST} $*"; }
fail() { echo -e "  ${RED}✗${RST} $*"; }
info() { echo -e "  ${YEL}…${RST} $*"; }

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TK5="$DIR/tk5/mvs-tk5"
LOGDIR="$DIR/logs"

mkdir -p "$LOGDIR"

echo -e "\n${BLD}Linux MVS TK5 Startup (Debug Mode)${RST}\n"

# Check if Hercules is installed
if ! command -v hercules &>/dev/null; then
    fail "Hercules not found"
    info "Install: sudo apt-get install hercules"
    exit 1
fi

HERC_BIN="$(dirname "$(command -v hercules)")"
info "Hercules: $HERC_BIN/hercules"
hercules -v 2>&1 | head -1 || true

# Kill any existing Hercules
pkill -9 hercules 2>/dev/null || true
pkill -9 s3270 2>/dev/null || true
sleep 2

# Prepare logs
mkdir -p "$TK5/log" 2>/dev/null
> "$TK5/log/hardcopy.log" 2>/dev/null || true

# Restore DASD
DASD_CACHE="$DIR/.cache/tk5-files.tar.gz"
if [ -f "$DASD_CACHE" ]; then
    info "Restoring DASD from cache..."
    tar xzf "$DASD_CACHE" -C "$TK5/" dasd/ 2>/dev/null && ok "DASD restored"
else
    info "No DASD cache found, using existing DASD"
fi

# Start Hercules (Hercules 3.13 doesn't support -r flag)
info "Starting Hercules..."
cd "$TK5"

# Create a simple startup script that pipes IPL commands
cat > /tmp/herc-start.sh <<'EOF'
#!/bin/bash
cd "$1"
cat scripts/ipl.rc - | hercules -f conf/tk5.cnf -d
EOF
chmod +x /tmp/herc-start.sh

# Start Hercules with IPL commands piped to stdin (use Linux-compatible config)
nohup bash -c "cd '$TK5' && cat scripts/ipl.rc - | hercules -f conf/tk5-linux.cnf -d" > "$LOGDIR/hercules.log" 2>&1 &
HERC_PID=$!

info "Hercules PID: $HERC_PID"
info "Waiting for MVS to boot (checking every 5s)..."

# Wait for port 3270 to open
for i in {1..60}; do
    sleep 5
    if (echo > /dev/tcp/127.0.0.1/3270) 2>/dev/null; then
        ok "TK5 started on port 3270"
        ok "Login: HERC01 / CUL8TR"
        echo ""
        info "Check hardcopy: tail -f $TK5/log/hardcopy.log"
        info "Check Hercules log: tail -f $LOGDIR/hercules.log"
        exit 0
    fi
    
    # Show progress every 30s
    if [ $((i % 6)) -eq 0 ]; then
        echo "  … Still waiting (${i}0s) - last 5 log lines:"
        tail -5 "$LOGDIR/hercules.log" 2>/dev/null | sed 's/^/    /'
    fi
done

fail "TK5 failed to start after 300s"
echo ""
echo "First 50 lines of Hercules log:"
echo "─────────────────────────────────────────────────────────────"
head -50 "$LOGDIR/hercules.log"
echo "─────────────────────────────────────────────────────────────"
echo ""
echo "Last 20 lines of Hercules log:"
echo "─────────────────────────────────────────────────────────────"
tail -20 "$LOGDIR/hercules.log"
echo "─────────────────────────────────────────────────────────────"

exit 1
