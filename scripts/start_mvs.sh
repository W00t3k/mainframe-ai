#!/bin/bash
# ─────────────────────────────────────────────────────────
#  Start MVS TK5 Mainframe (foreground, interactive)
#
#  This runs Hercules in the foreground with console output.
#  For background/managed mode, use: ./mvs.sh start
#  For full stack (Ollama + TK5 + Web), use: ./start.sh
# ─────────────────────────────────────────────────────────

DIR="$(cd "$(dirname "$0")" && pwd)"
TK5="$DIR/tk5/mvs-tk5"

GRN='\033[0;32m'; RED='\033[0;31m'; YEL='\033[0;33m'
CYN='\033[0;36m'; BLD='\033[1m'; RST='\033[0m'

if [ ! -d "$TK5" ]; then
  echo -e "${RED}[!] TK5 not found at $TK5${RST}"
  exit 1
fi

cd "$TK5"

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
    esac ;;
esac

HERC_BIN="$PWD/hercules/$HERC_OS/bin"
HERC_LIB="$PWD/hercules/$HERC_OS/lib"

chmod +x "$HERC_BIN/hercules" 2>/dev/null

if [ ! -f "$HERC_BIN/hercules" ]; then
  if command -v hercules &>/dev/null; then
    HERC_BIN="$(dirname "$(command -v hercules)")"
    HERC_LIB=""
    echo -e "${YEL}[*] Using system Hercules: $(command -v hercules)${RST}"
  else
    echo -e "${RED}[!] No Hercules binary found for $(uname -s)/$(uname -m)${RST}"
    echo -e "    Install: sudo apt install hercules"
    exit 1
  fi
fi

export PATH="$HERC_BIN:$PATH"
export LD_LIBRARY_PATH="$HERC_LIB:$LD_LIBRARY_PATH"
export DYLD_LIBRARY_PATH="$HERC_LIB:$DYLD_LIBRARY_PATH"
export HERCULES_LIB="$HERC_LIB/hercules"
export HERCULES_PATH="$HERC_LIB/hercules"

echo ""
echo -e "${CYN}${BLD}╔══════════════════════════════════════════════════════════╗${RST}"
echo -e "${CYN}${BLD}║              Starting MVS TK5 Mainframe                  ║${RST}"
echo -e "${CYN}${BLD}╠══════════════════════════════════════════════════════════╣${RST}"
echo -e "${CYN}║${RST}  Platform:  $(uname -s)/$(uname -m)                              ${CYN}║${RST}"
echo -e "${CYN}║${RST}  Hercules:  $HERC_BIN/hercules"
echo -e "${CYN}║${RST}  TN3270:    localhost:3270                               ${CYN}║${RST}"
echo -e "${CYN}║${RST}  Login:     ${BLD}HERC01${RST} / ${BLD}CUL8TR${RST}                                 ${CYN}║${RST}"
echo -e "${CYN}║${RST}  Press Ctrl+C to stop                                   ${CYN}║${RST}"
echo -e "${CYN}${BLD}╚══════════════════════════════════════════════════════════╝${RST}"
echo ""

# Run Hercules in foreground
tail -f /dev/null | "$HERC_BIN/hercules" -f conf/tk5.cnf -r scripts/ipl.rc -d
