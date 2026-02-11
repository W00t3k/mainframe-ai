#!/bin/bash
# ─────────────────────────────────────────────────────────
#  Mainframe AI Assistant — Start / Restart
#
#  Usage:
#    ./start.sh          Start Ollama + Web App
#    ./start.sh --mvs    Start Ollama + Web App + TK5
#    ./start.sh --kill   Kill everything
# ─────────────────────────────────────────────────────────

DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/.venv/bin/python"
PORT=8080
HOST="0.0.0.0"
# Auto-detect model based on available RAM
TOTAL_RAM_MB=$(free -m 2>/dev/null | awk '/^Mem:/{print $2}' || echo 16000)
if [ "$TOTAL_RAM_MB" -ge 16000 ]; then
  MODEL="llama3.1:8b"
elif [ "$TOTAL_RAM_MB" -ge 8000 ]; then
  MODEL="llama3.2:3b"
else
  MODEL="tinyllama"
fi

RED='\033[0;31m'
GRN='\033[0;32m'
YEL='\033[0;33m'
CYN='\033[0;36m'
RST='\033[0m'

# ── Kill existing processes ──────────────────────────────
kill_all() {
  echo -e "${YEL}[*] Stopping existing processes...${RST}"

  # Kill tracked web app pid first
  if [ -n "$WEBAPP_PID" ] && kill -0 $WEBAPP_PID 2>/dev/null; then
    kill $WEBAPP_PID 2>/dev/null
    wait $WEBAPP_PID 2>/dev/null
  fi

  # Then clean up any orphans on the port
  lsof -ti :$PORT 2>/dev/null | xargs kill -9 2>/dev/null && \
    echo -e "  ${RED}✗ Killed process on port $PORT${RST}" || \
    echo -e "  ${GRN}✓ Port $PORT already free${RST}"

  pkill -f "hercules" 2>/dev/null && \
    echo -e "  ${RED}✗ Killed Hercules/TK5${RST}" || \
    echo -e "  ${GRN}✓ TK5 not running${RST}"

  sleep 1
  echo -e "${GRN}[✓] All stopped${RST}"
}

# ── Start Ollama ─────────────────────────────────────────
start_ollama() {
  # Memory-saving env vars: unload model after 5min idle, single request at a time
  export OLLAMA_KEEP_ALIVE="5m"
  export OLLAMA_MAX_LOADED_MODELS=1
  export OLLAMA_NUM_PARALLEL=1

  if pgrep -x "ollama" > /dev/null 2>&1; then
    echo -e "${GRN}[✓] Ollama already running${RST}"
  else
    echo -e "${YEL}[*] Starting Ollama...${RST}"
    ollama serve > /dev/null 2>&1 &
    sleep 2
    if pgrep -x "ollama" > /dev/null 2>&1; then
      echo -e "${GRN}[✓] Ollama started${RST}"
    else
      echo -e "${RED}[!] Failed to start Ollama — install from https://ollama.com${RST}"
      echo -e "${YEL}[*] Continuing without AI...${RST}"
      return 1
    fi
  fi

  echo -e "${CYN}[*] RAM: ${TOTAL_RAM_MB}MB — will use model: $MODEL${RST}"
  echo -e "${CYN}[*] Model will load on first AI request (saves RAM)${RST}"
}

# ── Start TK5 MVS ───────────────────────────────────────
start_mvs() {
  TK5="$DIR/tk5/mvs-tk5"

  if ! [ -d "$TK5" ]; then
    echo -e "${RED}[!] TK5 not found at $TK5${RST}"
    return 1
  fi

  if pgrep -f "hercules" > /dev/null 2>&1; then
    echo -e "${GRN}[✓] TK5 already running${RST}"
    return 0
  fi

  echo -e "${YEL}[*] Starting TK5 MVS mainframe...${RST}"

  # Detect OS and architecture for Hercules binaries
  HERC_OS=""
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

  HERC_BIN="$TK5/hercules/$HERC_OS/bin"
  HERC_LIB="$TK5/hercules/$HERC_OS/lib"

  # Ensure binary is executable
  chmod +x "$HERC_BIN/hercules" 2>/dev/null

  if [ ! -f "$HERC_BIN/hercules" ]; then
    # Fallback: try system-installed hercules
    if command -v hercules &>/dev/null; then
      echo -e "${YEL}[*] Using system Hercules${RST}"
      HERC_BIN="$(dirname "$(command -v hercules)")"
      HERC_LIB=""
    else
      echo -e "${RED}[!] No Hercules binary found for $(uname -s)/$(uname -m)${RST}"
      echo -e "    Install hercules: sudo apt install hercules  (or equivalent)"
      return 1
    fi
  fi

  nohup bash -c "
    cd \"$TK5\"
    export PATH=\"$HERC_BIN:\$PATH\"
    export LD_LIBRARY_PATH=\"$HERC_LIB:\$LD_LIBRARY_PATH\"
    export DYLD_LIBRARY_PATH=\"$HERC_LIB:\$DYLD_LIBRARY_PATH\"
    export HERCULES_LIB=\"$HERC_LIB/hercules\"
    export HERCULES_PATH=\"$HERC_LIB/hercules\"
    tail -f /dev/null | \"$HERC_BIN/hercules\" -f conf/tk5.cnf -r scripts/ipl.rc -d
  " > "$DIR/tk5_hercules.log" 2>&1 &
  MVS_PID=$!

  sleep 5
  if pgrep -f "hercules" > /dev/null 2>&1; then
    echo -e "${GRN}[✓] TK5 started — TN3270 at localhost:3270${RST}"
    echo -e "    ${CYN}Login: HERC01 / CUL8TR${RST}"
  else
    echo -e "${RED}[!] TK5 failed to start — check $DIR/tk5_hercules.log${RST}"
    tail -5 "$DIR/tk5_hercules.log" 2>/dev/null
  fi
}

# ── Watchdog: restart web app forever on crash ───────────
WEBAPP_PID=""
RESTARTS=0

launch_webapp() {
  # Ensure venv exists
  if [ ! -f "$VENV" ]; then
    echo -e "${YEL}[*] Python venv not found — creating...${RST}"
    python3 -m venv "$DIR/.venv" 2>/dev/null || python -m venv "$DIR/.venv" 2>/dev/null
    if [ -f "$VENV" ]; then
      echo -e "${YEL}[*] Installing dependencies...${RST}"
      "$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt" 2>/dev/null
      echo -e "${GRN}[✓] Venv created${RST}"
    else
      echo -e "${RED}[!] Failed to create venv — install python3: sudo apt install python3 python3-venv${RST}"
      return 1
    fi
  fi

  # Wait for port to be free (up to 15s)
  for i in $(seq 1 15); do
    lsof -ti :$PORT > /dev/null 2>&1 || break
    if [ "$i" = "15" ]; then
      lsof -ti :$PORT 2>/dev/null | xargs kill -9 2>/dev/null
      sleep 1
    fi
    sleep 1
  done

  # Truncate log if > 1MB
  if [ -f "$DIR/webapp.log" ] && [ "$(wc -c < "$DIR/webapp.log" 2>/dev/null)" -gt 1048576 ]; then
    tail -1000 "$DIR/webapp.log" > "$DIR/webapp.log.tmp" && mv "$DIR/webapp.log.tmp" "$DIR/webapp.log"
  fi

  "$VENV" "$DIR/run.py" --host "$HOST" --port "$PORT" --model "$MODEL" >> "$DIR/webapp.log" 2>&1 &
  WEBAPP_PID=$!
  RESTARTS=$((RESTARTS + 1))

  sleep 3
  if kill -0 $WEBAPP_PID 2>/dev/null; then
    if [ $RESTARTS -eq 1 ]; then
      echo -e "${GRN}[✓] Web app running — http://$HOST:$PORT  (pid $WEBAPP_PID)${RST}"
    else
      echo -e "${YEL}[↻] Web app restarted (#$RESTARTS) — http://$HOST:$PORT  (pid $WEBAPP_PID)${RST}"
    fi
    return 0
  else
    echo -e "${RED}[!] Web app failed to start (attempt #$RESTARTS)${RST}"
    WEBAPP_PID=""
    return 1
  fi
}

watchdog() {
  BACKOFF=2
  MAX_BACKOFF=30

  # Initial launch
  launch_webapp

  # Poll forever — check every 3 seconds if the process is alive
  while true; do
    sleep 3
    [ "$SHUTTING_DOWN" = "1" ] && break

    # Check if web app is still alive
    if [ -n "$WEBAPP_PID" ] && kill -0 $WEBAPP_PID 2>/dev/null; then
      BACKOFF=2
      continue
    fi

    # It died — log and restart
    echo -e "${RED}[✗] Web app died — restarting in ${BACKOFF}s...${RST}"
    echo "$(date '+%Y-%m-%d %H:%M:%S') CRASH restart=#$RESTARTS" >> "$DIR/webapp.log"
    sleep $BACKOFF

    [ "$SHUTTING_DOWN" = "1" ] && break

    if launch_webapp; then
      BACKOFF=2
    else
      BACKOFF=$((BACKOFF * 2))
      [ $BACKOFF -gt $MAX_BACKOFF ] && BACKOFF=$MAX_BACKOFF
    fi
  done
}

# ── Banner ───────────────────────────────────────────────
banner() {
  echo ""
  echo -e "${CYN}╔══════════════════════════════════════════════════════════╗${RST}"
  echo -e "${CYN}║       Mainframe AI Assistant — Startup Script           ║${RST}"
  echo -e "${CYN}╠══════════════════════════════════════════════════════════╣${RST}"
  echo -e "${CYN}║  Web App:   http://$HOST:$PORT                         ║${RST}"
  echo -e "${CYN}║  Ollama:    http://localhost:11434                      ║${RST}"
  if [ "$1" = "mvs" ]; then
  echo -e "${CYN}║  TN3270:    localhost:3270  (HERC01 / CUL8TR)          ║${RST}"
  fi
  echo -e "${CYN}╠══════════════════════════════════════════════════════════╣${RST}"
  echo -e "${CYN}║  100% local. No API keys. No cloud.                    ║${RST}"
  echo -e "${CYN}║  Press Ctrl+C or run ./start.sh --kill to stop.        ║${RST}"
  echo -e "${CYN}╚══════════════════════════════════════════════════════════╝${RST}"
  echo ""
}

# ── Shutdown handler ──────────────────────────────────────
SHUTTING_DOWN=0
shutdown() {
  SHUTTING_DOWN=1
  echo ""
  kill_all
  exit 0
}
trap shutdown INT TERM

# ── Main ─────────────────────────────────────────────────
case "${1:-}" in
  --kill)
    kill_all
    exit 0
    ;;
  --mvs)
    kill_all
    start_ollama
    start_mvs
    banner mvs
    # Model pulls in background AFTER web app is stable (watchdog starts web app)
    ( sleep 15 && ollama list 2>/dev/null | grep -q "$MODEL" || ollama pull "$MODEL" ) &
    watchdog
    ;;
  *)
    kill_all
    start_ollama
    banner
    ( sleep 15 && ollama list 2>/dev/null | grep -q "$MODEL" || ollama pull "$MODEL" ) &
    watchdog
    ;;
esac
