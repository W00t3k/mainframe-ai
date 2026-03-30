#!/bin/bash
# Start Mainframe AI with watchdog

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Kill any existing processes
pkill -f run.py 2>/dev/null
pkill -f watchdog.py 2>/dev/null
sleep 2

# Start the web app
echo "Starting web app..."
nohup .venv/bin/python run.py > logs/webapp.log 2>&1 &
WEBAPP_PID=$!

# Wait for web app to start
sleep 5

# Start the watchdog
echo "Starting watchdog..."
nohup python3 watchdog.py > logs/watchdog.log 2>&1 &
WATCHDOG_PID=$!

echo "Web app PID: $WEBAPP_PID"
echo "Watchdog PID: $WATCHDOG_PID"
echo "Logs: logs/webapp.log, logs/watchdog.log"
echo ""
echo "To stop: pkill -f run.py && pkill -f watchdog.py"
echo "To check logs: tail -f logs/watchdog.log"
