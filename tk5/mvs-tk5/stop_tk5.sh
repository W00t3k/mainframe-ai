#!/bin/bash
#
# stop_tk5.sh - Clean TK5 shutdown script
#
cd "$(dirname "$0")"

echo "Shutting down TK5 MVS..."

# Send shutdown command to MVS
curl -s "http://localhost:8038/cgi-bin/tasks/cmd?cmd=/$p+jes2" > /dev/null 2>&1
sleep 2
curl -s "http://localhost:8038/cgi-bin/tasks/cmd?cmd=/z+eod" > /dev/null 2>&1
sleep 3

# Stop Hercules
curl -s "http://localhost:8038/cgi-bin/tasks/cmd?cmd=quit" > /dev/null 2>&1
sleep 2

# Force kill if still running
pkill -9 hercules 2>/dev/null

echo "TK5 MVS stopped."
