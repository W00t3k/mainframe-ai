#!/bin/bash
# Start the Interactive z/OS Book
# Requires the main BigIron app running for AI + Terminal features

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║         Interactive z/OS Book                            ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Check if main app is running
if ! curl -s http://localhost:8080/health >/dev/null 2>&1; then
    echo "  ⚠  BigIron app not running on :8080"
    echo "     AI chat and terminal features won't work."
    echo "     Start it with: ./start.sh"
    echo ""
fi

# Check for chapters
CHAPTERS=$(ls chapters/*.md 2>/dev/null | wc -l | tr -d ' ')
echo "  📖 Chapters: $CHAPTERS"
echo ""

# Start the book server
echo "  Starting book server on http://localhost:8888"
echo ""

python3 server.py
