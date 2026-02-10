#!/bin/bash
# ─────────────────────────────────────────────────────────
#  MVS TK5 Mainframe — Management Script
#
#  Usage:
#    ./mvs.sh start      Start MVS TK5
#    ./mvs.sh stop       Stop MVS TK5 (graceful)
#    ./mvs.sh kill       Force kill MVS TK5
#    ./mvs.sh restart    Stop + Start
#    ./mvs.sh status     Show if running, PID, ports
#    ./mvs.sh log        Tail the Hercules log
#    ./mvs.sh console    Attach to Hercules console
# ─────────────────────────────────────────────────────────

DIR="$(cd "$(dirname "$0")" && pwd)"
TK5="$DIR/tk5/mvs-tk5"
LOGFILE="$DIR/tk5_hercules.log"
PIDFILE="$DIR/tk5_hercules.pid"

RED='\033[0;31m'
GRN='\033[0;32m'
YEL='\033[0;33m'
CYN='\033[0;36m'
RST='\033[0m'

# ── Detect Hercules binary ─────────────────────────────────
find_hercules() {
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

  if [ ! -f "$HERC_BIN/hercules" ]; then
    if command -v hercules &>/dev/null; then
      HERC_BIN="$(dirname "$(command -v hercules)")"
      HERC_LIB=""
      echo -e "${YEL}[*] Using system Hercules: $(command -v hercules)${RST}"
    else
      echo -e "${RED}[!] Hercules not found for $(uname -s)/$(uname -m)${RST}"
      echo -e "    Install: sudo apt install hercules"
      return 1
    fi
  fi
}

# ── Get Hercules PID ───────────────────────────────────────
get_pid() {
  # Check pidfile first
  if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if kill -0 "$PID" 2>/dev/null; then
      echo "$PID"
      return 0
    fi
    rm -f "$PIDFILE"
  fi

  # Fallback: find by process name
  PID=$(pgrep -f "hercules.*tk5.cnf" 2>/dev/null | head -1)
  if [ -n "$PID" ]; then
    echo "$PID"
    return 0
  fi

  return 1
}

# ── Start ──────────────────────────────────────────────────
do_start() {
  if ! [ -d "$TK5" ]; then
    echo -e "${RED}[!] TK5 not found at $TK5${RST}"
    echo -e "    Run ./install.sh and choose to install TK5"
    return 1
  fi

  if PID=$(get_pid); then
    echo -e "${GRN}[✓] TK5 already running (pid $PID)${RST}"
    return 0
  fi

  find_hercules || return 1

  echo -e "${YEL}[*] Starting TK5 MVS mainframe...${RST}"

  nohup bash -c "
    cd \"$TK5\"
    export PATH=\"$HERC_BIN:\$PATH\"
    export LD_LIBRARY_PATH=\"$HERC_LIB:\$LD_LIBRARY_PATH\"
    export DYLD_LIBRARY_PATH=\"$HERC_LIB:\$DYLD_LIBRARY_PATH\"
    export HERCULES_LIB=\"$HERC_LIB/hercules\"
    export HERCULES_PATH=\"$HERC_LIB/hercules\"
    tail -f /dev/null | \"$HERC_BIN/hercules\" -f conf/tk5.cnf -r scripts/ipl.rc -d
  " > "$LOGFILE" 2>&1 &
  echo $! > "$PIDFILE"

  echo -e "${YEL}[*] Waiting for MVS to IPL...${RST}"

  # Wait up to 30 seconds for hercules to start and TN3270 port to open
  for i in $(seq 1 30); do
    if ! kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
      echo -e "${RED}[!] Hercules process died during startup${RST}"
      echo -e "    Check log: $LOGFILE"
      tail -10 "$LOGFILE" 2>/dev/null
      rm -f "$PIDFILE"
      return 1
    fi

    # Check if TN3270 port is listening
    if ss -tlnp 2>/dev/null | grep -q ":3270 " || \
       lsof -i :3270 -sTCP:LISTEN &>/dev/null; then
      echo -e "${GRN}[✓] TK5 started — TN3270 at localhost:3270${RST}"
      echo -e "    ${CYN}PID: $(cat "$PIDFILE")${RST}"
      echo -e "    ${CYN}Login: HERC01 / CUL8TR${RST}"
      echo -e "    ${CYN}Log: $LOGFILE${RST}"
      return 0
    fi

    sleep 1
  done

  # Port didn't open but process is alive — might still be IPLing
  if kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
    echo -e "${YEL}[*] Hercules running (pid $(cat "$PIDFILE")) but TN3270 port not yet open${RST}"
    echo -e "    MVS may still be IPLing. Wait a minute and check: ./mvs.sh status"
  else
    echo -e "${RED}[!] TK5 failed to start${RST}"
    tail -10 "$LOGFILE" 2>/dev/null
    rm -f "$PIDFILE"
    return 1
  fi
}

# ── Stop (graceful) ────────────────────────────────────────
do_stop() {
  PID=$(get_pid) || {
    echo -e "${GRN}[✓] TK5 not running${RST}"
    return 0
  }

  echo -e "${YEL}[*] Stopping TK5 (pid $PID)...${RST}"

  # Send SIGTERM first for graceful shutdown
  kill "$PID" 2>/dev/null

  # Wait up to 15 seconds for graceful stop
  for i in $(seq 1 15); do
    if ! kill -0 "$PID" 2>/dev/null; then
      echo -e "${GRN}[✓] TK5 stopped gracefully${RST}"
      rm -f "$PIDFILE"
      return 0
    fi
    sleep 1
  done

  # Still alive — force kill
  echo -e "${YEL}[*] Graceful stop timed out, force killing...${RST}"
  do_kill
}

# ── Kill (force) ───────────────────────────────────────────
do_kill() {
  # Kill all hercules processes
  PIDS=$(pgrep -f "hercules" 2>/dev/null)

  if [ -z "$PIDS" ]; then
    echo -e "${GRN}[✓] No Hercules processes found${RST}"
    rm -f "$PIDFILE"
    return 0
  fi

  echo -e "${RED}[*] Force killing Hercules processes: $PIDS${RST}"
  echo "$PIDS" | xargs kill -9 2>/dev/null

  # Also kill any tail processes feeding hercules
  pkill -9 -f "tail -f /dev/null" 2>/dev/null

  sleep 1

  if pgrep -f "hercules" > /dev/null 2>&1; then
    echo -e "${RED}[!] Some processes may still be running${RST}"
    pgrep -af "hercules"
  else
    echo -e "${GRN}[✓] All Hercules processes killed${RST}"
  fi

  rm -f "$PIDFILE"

  # Free up port 3270 if stuck
  lsof -ti :3270 2>/dev/null | xargs kill -9 2>/dev/null
}

# ── Restart ────────────────────────────────────────────────
do_restart() {
  echo -e "${YEL}[*] Restarting TK5...${RST}"
  do_stop
  sleep 2
  do_start
}

# ── Status ─────────────────────────────────────────────────
do_status() {
  echo ""
  echo -e "${CYN}═══ MVS TK5 Status ═══${RST}"
  echo ""

  # Hercules process
  PID=$(get_pid) && {
    echo -e "  ${GRN}● Hercules:  RUNNING  (pid $PID)${RST}"

    # Uptime
    if [ -f "/proc/$PID/stat" ]; then
      START=$(stat -c %Y "/proc/$PID" 2>/dev/null)
      if [ -n "$START" ]; then
        NOW=$(date +%s)
        UPTIME=$(( NOW - START ))
        HOURS=$(( UPTIME / 3600 ))
        MINS=$(( (UPTIME % 3600) / 60 ))
        echo -e "  ${CYN}  Uptime:    ${HOURS}h ${MINS}m${RST}"
      fi
    fi

    # Memory
    RSS=$(ps -o rss= -p "$PID" 2>/dev/null | tr -d ' ')
    if [ -n "$RSS" ]; then
      MB=$(( RSS / 1024 ))
      echo -e "  ${CYN}  Memory:    ${MB} MB${RST}"
    fi
  } || {
    echo -e "  ${RED}● Hercules:  STOPPED${RST}"
  }

  # TN3270 port
  if ss -tlnp 2>/dev/null | grep -q ":3270 " || \
     lsof -i :3270 -sTCP:LISTEN &>/dev/null 2>&1; then
    echo -e "  ${GRN}● TN3270:    LISTENING on port 3270${RST}"
  else
    echo -e "  ${RED}● TN3270:    NOT listening${RST}"
  fi

  # HTTP console (Hercules web interface, usually port 8038)
  if ss -tlnp 2>/dev/null | grep -q ":8038 " || \
     lsof -i :8038 -sTCP:LISTEN &>/dev/null 2>&1; then
    echo -e "  ${GRN}● Console:   http://localhost:8038${RST}"
  fi

  # Log file
  if [ -f "$LOGFILE" ]; then
    SIZE=$(du -h "$LOGFILE" 2>/dev/null | cut -f1)
    echo -e "  ${CYN}  Log:       $LOGFILE ($SIZE)${RST}"
  fi

  echo ""
}

# ── Log ────────────────────────────────────────────────────
do_log() {
  if [ ! -f "$LOGFILE" ]; then
    echo -e "${RED}[!] No log file found at $LOGFILE${RST}"
    return 1
  fi
  echo -e "${CYN}[*] Tailing $LOGFILE (Ctrl+C to stop)${RST}"
  tail -f "$LOGFILE"
}

# ── Usage ──────────────────────────────────────────────────
usage() {
  echo ""
  echo -e "${CYN}MVS TK5 Mainframe Manager${RST}"
  echo ""
  echo "  Usage: ./mvs.sh <command>"
  echo ""
  echo "  Commands:"
  echo "    start     Start MVS TK5 mainframe"
  echo "    stop      Graceful shutdown (SIGTERM, waits 15s)"
  echo "    kill      Force kill all Hercules processes"
  echo "    restart   Stop + Start"
  echo "    status    Show running state, PID, ports, memory"
  echo "    log       Tail the Hercules log"
  echo ""
  echo "  TN3270:  localhost:3270"
  echo "  Login:   HERC01 / CUL8TR"
  echo ""
}

# ── Main ───────────────────────────────────────────────────
case "${1:-}" in
  start)   do_start   ;;
  stop)    do_stop    ;;
  kill)    do_kill    ;;
  restart) do_restart ;;
  status)  do_status  ;;
  log)     do_log     ;;
  *)       usage      ;;
esac
