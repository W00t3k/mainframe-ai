#!/bin/bash
#
# start_tk5.sh - Reliable TK5 startup script for macOS
#
cd "$(dirname "$0")"

# Ensure homebrew binaries are on PATH (needed when launched from web server)
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# Kill any existing Hercules processes
pkill -9 hercules 2>/dev/null
sleep 1

# Set daemon mode
echo "DAEMON" > mode

# Set environment
export HERCULES_RC=scripts/tk5.rc

# Start Hercules in daemon mode with stdin kept open
(tail -f /dev/null | hercules -f conf/tk5.cnf -d > log/hercules_console.log 2>&1) &
HERC_PID=$!
echo "Started Hercules (PID: $HERC_PID)"

# Wait for Hercules to initialize
sleep 5

# Check if running
if ! ps -p $HERC_PID > /dev/null 2>&1; then
    echo "ERROR: Hercules failed to start"
    exit 1
fi

# Send IPL command
echo "Sending IPL command..."
curl -s "http://localhost:8038/cgi-bin/tasks/cmd?cmd=ipl+390" > /dev/null

# Wait for IEA101A prompt and reply with defaults
sleep 8
echo "Replying to system parameters prompt..."
curl -s "http://localhost:8038/cgi-bin/tasks/cmd?cmd=/r+0," > /dev/null

echo ""
echo "TK5 MVS is starting up..."
echo "- Console: http://localhost:8038"
echo "- 3270 port: localhost:3270"
echo ""
echo "Wait ~30 seconds for VTAM/TSO to fully initialize."
echo "Log: log/hercules_console.log"
