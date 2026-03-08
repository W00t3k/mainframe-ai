#!/bin/bash
# Kill all Mainframe AI Assistant services
echo "Stopping all services..."

# Kill by port — filter to LISTEN only (avoids killing browser clients)
for port in 8080 3270 8038 11434; do
  pids=$(lsof -ti :$port -sTCP:LISTEN 2>/dev/null)
  if [ -n "$pids" ]; then
    echo "$pids" | xargs kill -9 2>/dev/null
    echo "  ✗ Killed process(es) on port $port"
  else
    echo "  ✓ Port $port clear"
  fi
done

# Kill by name (catches anything not listening on a port)
pkill -9 hercules 2>/dev/null && echo "  ✗ Killed hercules" || true
pkill -9 s3270 2>/dev/null
pkill -9 -f "run\.py" 2>/dev/null
pkill -9 -f "uvicorn" 2>/dev/null
pkill -f "ollama serve" 2>/dev/null
pkill -f "tail -f /dev/null" 2>/dev/null

rm -f "$(dirname "$0")/logs/start.pid"
echo "All stopped."
