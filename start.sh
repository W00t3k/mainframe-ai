#!/bin/bash
# ─────────────────────────────────────────────────────────
#  Mainframe AI Assistant — One-Script Launcher
#
#  Usage:
#    ./start.sh              Start all services (Ollama + Web App + TK5)
#    ./start.sh --no-mvs     Start without TK5 mainframe
#    ./start.sh --no-ollama  Start without Ollama AI
#    ./start.sh --kill       Kill everything
#    ./start.sh --status     Health check all services
# ─────────────────────────────────────────────────────────

set -o pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=8080
HOST="0.0.0.0"
TK5="$DIR/tk5/mvs-tk5"
LOGDIR="$DIR/logs"
mkdir -p "$LOGDIR"

# ── Colors ─────────────────────────────────────────────
RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[0;33m'
CYN='\033[0;36m'; BLD='\033[1m'; RST='\033[0m'

ok()   { echo -e "  ${GRN}✓${RST} $1"; }
fail() { echo -e "  ${RED}✗${RST} $1"; }
info() { echo -e "  ${YEL}…${RST} $1"; }

# ── Auto-detect Python ─────────────────────────────────
detect_python() {
  if [ -f "$DIR/.venv/bin/python" ]; then
    PYTHON="$DIR/.venv/bin/python"
  elif [ -f "$DIR/venv/bin/python" ]; then
    PYTHON="$DIR/venv/bin/python"
  elif command -v python3 &>/dev/null; then
    PYTHON="python3"
  else
    PYTHON="python"
  fi
}

# ── Auto-detect RAM & model ────────────────────────────
detect_model() {
  TOTAL_RAM_MB=$(free -m 2>/dev/null | awk '/^Mem:/{print $2}')
  # macOS fallback
  [ -z "$TOTAL_RAM_MB" ] && TOTAL_RAM_MB=$(sysctl -n hw.memsize 2>/dev/null | awk '{printf "%d", $1/1048576}')
  [ -z "$TOTAL_RAM_MB" ] && TOTAL_RAM_MB=16000

  if [ "$TOTAL_RAM_MB" -ge 16000 ]; then
    MODEL="llama3.1:8b"
  elif [ "$TOTAL_RAM_MB" -ge 8000 ]; then
    MODEL="llama3.2:3b"
  else
    MODEL="tinyllama"
  fi
}

# ── Detect Hercules binary ─────────────────────────────
detect_hercules() {
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
      esac ;;
  esac

  HERC_BIN="$TK5/hercules/$HERC_OS/bin"
  HERC_LIB="$TK5/hercules/$HERC_OS/lib"

  chmod +x "$HERC_BIN/hercules" 2>/dev/null

  if [ ! -f "$HERC_BIN/hercules" ]; then
    if command -v hercules &>/dev/null; then
      HERC_BIN="$(dirname "$(command -v hercules)")"
      HERC_LIB=""
    else
      HERC_BIN=""
      HERC_LIB=""
    fi
  fi
}

# ═══════════════════════════════════════════════════════
#  KILL
# ═══════════════════════════════════════════════════════
kill_all() {
  echo -e "\n${BLD}Stopping all services...${RST}"

  # Web app
  lsof -ti :$PORT 2>/dev/null | xargs kill -9 2>/dev/null && fail "Killed web app on :$PORT" || ok "Web app not running"

  # Ollama
  pkill -f "ollama serve" 2>/dev/null && fail "Killed Ollama" || ok "Ollama not running"

  # Hercules
  pkill -f "hercules" 2>/dev/null && fail "Killed Hercules/TK5" || ok "TK5 not running"

  # Cleanup stale tail processes from old TK5 starts
  pkill -f "tail -f /dev/null" 2>/dev/null

  sleep 1
  echo -e "${GRN}${BLD}All stopped.${RST}\n"
}

# ═══════════════════════════════════════════════════════
#  HEALTH CHECKS (curl-based)
# ═══════════════════════════════════════════════════════
check_webapp() {
  curl -sf --max-time 5 "http://127.0.0.1:$PORT/api/status" > /dev/null 2>&1
}

check_ollama() {
  curl -sf --max-time 5 "http://127.0.0.1:11434/api/tags" > /dev/null 2>&1
}

check_tk5() {
  # Check if port 3270 is listening
  (echo > /dev/tcp/127.0.0.1/3270) 2>/dev/null
}

# Wait for a service with retries
wait_for() {
  local name="$1" check_fn="$2" max_wait="${3:-30}"
  local elapsed=0
  while [ $elapsed -lt $max_wait ]; do
    if $check_fn; then
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  return 1
}

# ═══════════════════════════════════════════════════════
#  START SERVICES
# ═══════════════════════════════════════════════════════

start_ollama_svc() {
  echo -e "\n${BLD}[1/3] Ollama AI Backend${RST}"

  export OLLAMA_KEEP_ALIVE="5m"
  export OLLAMA_MAX_LOADED_MODELS=1
  export OLLAMA_NUM_PARALLEL=1

  if check_ollama; then
    ok "Ollama already running"
  else
    info "Starting Ollama..."
    ollama serve > "$LOGDIR/ollama.log" 2>&1 &
    if wait_for "Ollama" check_ollama 10; then
      ok "Ollama started (pid $(pgrep -x ollama 2>/dev/null))"
    else
      fail "Ollama failed to start — install from https://ollama.com"
      info "Continuing without AI..."
      OLLAMA_OK=0
      return 1
    fi
  fi

  info "RAM: ${TOTAL_RAM_MB}MB → model: ${BLD}$MODEL${RST}"
  info "Model loads on first AI request (saves RAM)"
  OLLAMA_OK=1

  # Ensure model is available (background, non-blocking)
  ( ollama list 2>/dev/null | grep -q "$MODEL" || ollama pull "$MODEL" ) >> "$LOGDIR/ollama.log" 2>&1 &
}

start_tk5_svc() {
  echo -e "\n${BLD}[2/3] TK5 MVS 3.8j Mainframe${RST}"

  if [ ! -d "$TK5" ]; then
    fail "TK5 not found at $TK5"
    TK5_OK=0
    return 1
  fi

  if check_tk5; then
    ok "TK5 already running (port 3270 open)"
    TK5_OK=1
    return 0
  fi

  detect_hercules

  if [ -z "$HERC_BIN" ]; then
    fail "No Hercules binary found for $(uname -s)/$(uname -m)"
    info "Install: sudo apt install hercules"
    TK5_OK=0
    return 1
  fi

  info "Starting Hercules ($(uname -s)/$(uname -m))..."

  nohup bash -c "
    cd \"$TK5\"
    export PATH=\"$HERC_BIN:\$PATH\"
    export LD_LIBRARY_PATH=\"$HERC_LIB:\$LD_LIBRARY_PATH\"
    export DYLD_LIBRARY_PATH=\"$HERC_LIB:\$DYLD_LIBRARY_PATH\"
    export HERCULES_LIB=\"$HERC_LIB/hercules\"
    export HERCULES_PATH=\"$HERC_LIB/hercules\"
    tail -f /dev/null | \"$HERC_BIN/hercules\" -f conf/tk5.cnf -r scripts/ipl.rc -d
  " > "$LOGDIR/hercules.log" 2>&1 &

  if wait_for "TK5" check_tk5 30; then
    ok "TK5 started — TN3270 on port 3270"
    ok "Login: HERC01 / CUL8TR"
    TK5_OK=1
  else
    fail "TK5 failed to start"
    info "Check log: $LOGDIR/hercules.log"
    tail -5 "$LOGDIR/hercules.log" 2>/dev/null | while read -r line; do echo "    $line"; done
    TK5_OK=0
  fi
}

start_webapp_svc() {
  echo -e "\n${BLD}[3/3] Web Application${RST}"

  detect_python

  # Auto-create venv if needed
  if [ "$PYTHON" = "python3" ] || [ "$PYTHON" = "python" ]; then
    if [ -f "$DIR/requirements.txt" ]; then
      info "No venv found — creating .venv..."
      python3 -m venv "$DIR/.venv" 2>/dev/null || python -m venv "$DIR/.venv" 2>/dev/null
      if [ -f "$DIR/.venv/bin/python" ]; then
        PYTHON="$DIR/.venv/bin/python"
        "$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt" 2>/dev/null
        ok "Venv created and deps installed"
      fi
    fi
  fi

  # Kill anything on the port
  lsof -ti :$PORT 2>/dev/null | xargs kill -9 2>/dev/null
  sleep 1

  # Truncate log if > 1MB
  if [ -f "$LOGDIR/webapp.log" ] && [ "$(wc -c < "$LOGDIR/webapp.log" 2>/dev/null)" -gt 1048576 ]; then
    tail -1000 "$LOGDIR/webapp.log" > "$LOGDIR/webapp.log.tmp" && mv "$LOGDIR/webapp.log.tmp" "$LOGDIR/webapp.log"
  fi

  info "Starting web app with: $PYTHON"
  "$PYTHON" "$DIR/run.py" --host "$HOST" --port "$PORT" --model "$MODEL" >> "$LOGDIR/webapp.log" 2>&1 &
  WEBAPP_PID=$!

  if wait_for "Web App" check_webapp 15; then
    ok "Web app running — http://$HOST:$PORT (pid $WEBAPP_PID)"
    WEBAPP_OK=1
  else
    fail "Web app failed to start (pid $WEBAPP_PID)"
    info "Check log: $LOGDIR/webapp.log"
    tail -5 "$LOGDIR/webapp.log" 2>/dev/null | while read -r line; do echo "    $line"; done
    WEBAPP_OK=0
    WEBAPP_PID=""
  fi
}

# ═══════════════════════════════════════════════════════
#  STATUS DASHBOARD
# ═══════════════════════════════════════════════════════
status_dashboard() {
  local mode="${1:-full}"
  echo ""
  echo -e "${CYN}${BLD}╔══════════════════════════════════════════════════════════╗${RST}"
  echo -e "${CYN}${BLD}║         Mainframe AI Assistant — Status                  ║${RST}"
  echo -e "${CYN}${BLD}╠══════════════════════════════════════════════════════════╣${RST}"

  # Web App
  if check_webapp; then
    echo -e "${CYN}║${RST}  ${GRN}●${RST} Web App     ${GRN}RUNNING${RST}   http://$HOST:$PORT          ${CYN}║${RST}"
  else
    echo -e "${CYN}║${RST}  ${RED}●${RST} Web App     ${RED}DOWN${RST}                                   ${CYN}║${RST}"
  fi

  # Ollama
  if check_ollama; then
    echo -e "${CYN}║${RST}  ${GRN}●${RST} Ollama AI   ${GRN}RUNNING${RST}   model: $MODEL        ${CYN}║${RST}"
  else
    echo -e "${CYN}║${RST}  ${RED}●${RST} Ollama AI   ${RED}DOWN${RST}                                   ${CYN}║${RST}"
  fi

  # TK5
  if check_tk5; then
    echo -e "${CYN}║${RST}  ${GRN}●${RST} TK5 MVS     ${GRN}RUNNING${RST}   TN3270 port 3270           ${CYN}║${RST}"
  else
    echo -e "${CYN}║${RST}  ${RED}●${RST} TK5 MVS     ${RED}DOWN${RST}                                   ${CYN}║${RST}"
  fi

  echo -e "${CYN}${BLD}╠══════════════════════════════════════════════════════════╣${RST}"

  # Memory
  local mem_used mem_total
  mem_used=$(free -m 2>/dev/null | awk '/^Mem:/{print $3}')
  mem_total=$(free -m 2>/dev/null | awk '/^Mem:/{print $2}')
  if [ -n "$mem_used" ]; then
    echo -e "${CYN}║${RST}  RAM: ${mem_used}MB / ${mem_total}MB                                  ${CYN}║${RST}"
  fi

  echo -e "${CYN}║${RST}  Login: ${BLD}HERC01${RST} / ${BLD}CUL8TR${RST}                                 ${CYN}║${RST}"
  echo -e "${CYN}║${RST}  Logs:  $LOGDIR/                           ${CYN}║${RST}"
  echo -e "${CYN}${BLD}╠══════════════════════════════════════════════════════════╣${RST}"
  echo -e "${CYN}║${RST}  ${BLD}Ctrl+C${RST} or ${BLD}./start.sh --kill${RST} to stop all              ${CYN}║${RST}"
  echo -e "${CYN}║${RST}  ${BLD}./start.sh --status${RST} to check health                  ${CYN}║${RST}"
  echo -e "${CYN}${BLD}╚══════════════════════════════════════════════════════════╝${RST}"
  echo ""
}

# ═══════════════════════════════════════════════════════
#  WATCHDOG — keeps web app alive
# ═══════════════════════════════════════════════════════
watchdog() {
  local backoff=2 max_backoff=30

  while true; do
    sleep 5
    [ "$SHUTTING_DOWN" = "1" ] && break

    # Check web app via curl (more reliable than kill -0)
    if check_webapp; then
      backoff=2
      continue
    fi

    # Also check if process is alive (curl might fail during request)
    if [ -n "$WEBAPP_PID" ] && kill -0 $WEBAPP_PID 2>/dev/null; then
      continue
    fi

    # Web app is truly dead — restart
    echo -e "${RED}[✗] Web app died — restarting in ${backoff}s...${RST}"
    echo "$(date '+%Y-%m-%d %H:%M:%S') CRASH" >> "$LOGDIR/webapp.log"
    sleep $backoff
    [ "$SHUTTING_DOWN" = "1" ] && break

    # Kill any zombies on the port
    lsof -ti :$PORT 2>/dev/null | xargs kill -9 2>/dev/null
    sleep 1

    detect_python
    "$PYTHON" "$DIR/run.py" --host "$HOST" --port "$PORT" --model "$MODEL" >> "$LOGDIR/webapp.log" 2>&1 &
    WEBAPP_PID=$!

    if wait_for "Web App" check_webapp 15; then
      echo -e "${GRN}[✓] Web app restarted (pid $WEBAPP_PID)${RST}"
      backoff=2
    else
      echo -e "${RED}[!] Web app failed to restart${RST}"
      WEBAPP_PID=""
      backoff=$((backoff * 2))
      [ $backoff -gt $max_backoff ] && backoff=$max_backoff
    fi
  done
}

# ═══════════════════════════════════════════════════════
#  SHUTDOWN HANDLER
# ═══════════════════════════════════════════════════════
SHUTTING_DOWN=0
shutdown() {
  SHUTTING_DOWN=1
  echo ""
  kill_all
  exit 0
}
trap shutdown INT TERM

# ═══════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════
detect_model

SKIP_MVS=0
SKIP_OLLAMA=0

case "${1:-}" in
  --kill)
    kill_all
    exit 0
    ;;
  --status)
    status_dashboard
    exit 0
    ;;
  --no-mvs)
    SKIP_MVS=1
    ;;
  --no-ollama)
    SKIP_OLLAMA=1
    ;;
esac

echo ""
echo -e "${CYN}${BLD}═══════════════════════════════════════════════════════${RST}"
echo -e "${CYN}${BLD}  Mainframe AI Assistant — Starting All Services${RST}"
echo -e "${CYN}${BLD}═══════════════════════════════════════════════════════${RST}"

kill_all

# Start services in order
OLLAMA_OK=0; TK5_OK=0; WEBAPP_OK=0

if [ "$SKIP_OLLAMA" = "0" ]; then
  start_ollama_svc
else
  echo -e "\n${BLD}[1/3] Ollama AI Backend${RST}"
  info "Skipped (--no-ollama)"
fi

if [ "$SKIP_MVS" = "0" ]; then
  start_tk5_svc
else
  echo -e "\n${BLD}[2/3] TK5 MVS 3.8j Mainframe${RST}"
  info "Skipped (--no-mvs)"
fi

start_webapp_svc

# Final status
status_dashboard

# Keep running — watchdog monitors web app
watchdog
