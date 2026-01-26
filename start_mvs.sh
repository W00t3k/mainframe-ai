#!/bin/bash
# Start MVS TK5 for Mainframe AI Assistant

cd "$(dirname "$0")/tk5/mvs-tk5"

# Set up paths for Hercules
export PATH="$PWD/hercules/darwin/bin:$PATH"
export DYLD_LIBRARY_PATH="$PWD/hercules/darwin/lib:$DYLD_LIBRARY_PATH"
export HERCULES_LIB="$PWD/hercules/darwin/lib/hercules"
export HERCULES_PATH="$PWD/hercules/darwin/lib/hercules"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║              Starting MVS TK5 Mainframe                  ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  TN3270 will be available at: localhost:3270             ║"
echo "║  Connect with: /connect localhost:3270                   ║"
echo "║                                                          ║"
echo "║  Default login: HERC01 / CUL8TR                         ║"
echo "║  Press Ctrl+C to stop MVS                               ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Run Hercules directly
tail -f /dev/null | ./hercules/darwin/bin/hercules -f conf/tk5.cnf -r scripts/ipl.rc -p "$HERCULES_LIB" -d
