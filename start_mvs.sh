#!/bin/bash
# Start MVS TK5 for Mainframe AI Assistant

cd "$(dirname "$0")/tk5/mvs-tk5"

# Detect OS and architecture
case "$(uname -s)" in
  Darwin) HERC_OS="darwin" ;;
  Linux)
    case "$(uname -m)" in
      x86_64)  HERC_OS="linux/64" ;;
      aarch64) HERC_OS="linux/aarch64" ;;
      armv7*)  HERC_OS="linux/arm" ;;
      i686)    HERC_OS="linux/32" ;;
      *)       HERC_OS="linux/64" ;;
    esac
    ;;
esac

HERC_BIN="$PWD/hercules/$HERC_OS/bin"
HERC_LIB="$PWD/hercules/$HERC_OS/lib"

# Ensure binary is executable
chmod +x "$HERC_BIN/hercules" 2>/dev/null

# Fallback to system hercules if bundled binary not found
if [ ! -f "$HERC_BIN/hercules" ]; then
  if command -v hercules &>/dev/null; then
    HERC_BIN="$(dirname "$(command -v hercules)")"
    HERC_LIB=""
    echo "[*] Using system Hercules: $(command -v hercules)"
  else
    echo "[!] No Hercules binary found for $(uname -s)/$(uname -m)"
    echo "    Install: sudo apt install hercules"
    exit 1
  fi
fi

export PATH="$HERC_BIN:$PATH"
export LD_LIBRARY_PATH="$HERC_LIB:$LD_LIBRARY_PATH"
export DYLD_LIBRARY_PATH="$HERC_LIB:$DYLD_LIBRARY_PATH"
export HERCULES_LIB="$HERC_LIB/hercules"
export HERCULES_PATH="$HERC_LIB/hercules"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║              Starting MVS TK5 Mainframe                  ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Hercules: $HERC_BIN/hercules"
echo "║  TN3270 will be available at: localhost:3270             ║"
echo "║  Connect with: /connect localhost:3270                   ║"
echo "║                                                          ║"
echo "║  Default login: HERC01 / CUL8TR                         ║"
echo "║  Press Ctrl+C to stop MVS                               ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Run Hercules
tail -f /dev/null | "$HERC_BIN/hercules" -f conf/tk5.cnf -r scripts/ipl.rc -d
