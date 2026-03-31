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

# ── Kill stale processes from previous runs ─────────────
pkill -9 -f "run\.py" 2>/dev/null
pkill -9 -f "uvicorn" 2>/dev/null
pkill -9 -f "s3270" 2>/dev/null
lsof -ti :$PORT 2>/dev/null | xargs kill -9 2>/dev/null
sleep 1

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

# ── Auto-detect GPU, RAM & model ──────────────────────
detect_model() {
  GPU_DETECTED=false
  GPU_VRAM_GB=0

  # Check for NVIDIA GPU first
  if command -v nvidia-smi &>/dev/null; then
    GPU_VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1)
    if [ -n "$GPU_VRAM_MB" ] && [ "$GPU_VRAM_MB" -gt 0 ] 2>/dev/null; then
      GPU_DETECTED=true
      GPU_VRAM_GB=$((GPU_VRAM_MB / 1024))
      GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
      ok "GPU detected: $GPU_NAME (${GPU_VRAM_GB}GB VRAM)"

      if [ "$GPU_VRAM_GB" -ge 80 ]; then
        MODEL="deepseek-r1:70b"
        ok "GPU tier: ULTRA — using $MODEL"
      elif [ "$GPU_VRAM_GB" -ge 40 ]; then
        MODEL="deepseek-r1:32b"
        ok "GPU tier: HIGH — using $MODEL"
      elif [ "$GPU_VRAM_GB" -ge 20 ]; then
        MODEL="deepseek-coder-v2:16b"
        ok "GPU tier: MEDIUM — using $MODEL"
      elif [ "$GPU_VRAM_GB" -ge 8 ]; then
        MODEL="deepseek-r1:8b"
        ok "GPU tier: LOW — using $MODEL"
      else
        MODEL="phi3:mini"
        ok "GPU tier: MINIMAL — using $MODEL"
      fi

      # Set GPU-optimized Ollama env vars
      export CUDA_VISIBLE_DEVICES="0"
      if [ "$GPU_VRAM_GB" -ge 80 ]; then
        export OLLAMA_FLASH_ATTENTION="1"
        export OLLAMA_NUM_PARALLEL="4"
        export OLLAMA_MAX_LOADED_MODELS="4"
      elif [ "$GPU_VRAM_GB" -ge 40 ]; then
        export OLLAMA_FLASH_ATTENTION="1"
        export OLLAMA_NUM_PARALLEL="2"
        export OLLAMA_MAX_LOADED_MODELS="2"
      fi

      # Set RAM for status display
      TOTAL_RAM_MB=$(free -m 2>/dev/null | awk '/^Mem:/{print $2}')
      [ -z "$TOTAL_RAM_MB" ] && TOTAL_RAM_MB=$(sysctl -n hw.memsize 2>/dev/null | awk '{printf "%d", $1/1048576}')
      [ -z "$TOTAL_RAM_MB" ] && TOTAL_RAM_MB=0
      return
    fi
  fi

  # Fallback: RAM-based model selection (no GPU)
  TOTAL_RAM_MB=$(free -m 2>/dev/null | awk '/^Mem:/{print $2}')
  # macOS fallback
  [ -z "$TOTAL_RAM_MB" ] && TOTAL_RAM_MB=$(sysctl -n hw.memsize 2>/dev/null | awk '{printf "%d", $1/1048576}')
  [ -z "$TOTAL_RAM_MB" ] && TOTAL_RAM_MB=16000

  if [ "$TOTAL_RAM_MB" -ge 32000 ]; then
    MODEL="deepseek-r1:14b"
  elif [ "$TOTAL_RAM_MB" -ge 16000 ]; then
    MODEL="deepseek-r1:8b"
  elif [ "$TOTAL_RAM_MB" -ge 8000 ]; then
    MODEL="phi3:mini"
  elif [ "$TOTAL_RAM_MB" -ge 4000 ]; then
    MODEL="gemma2:2b"
  else
    MODEL="tinyllama"
  fi
  info "No GPU detected — CPU mode with $MODEL"
}

# ── Detect Hercules binary ─────────────────────────────
detect_hercules() {
  # On macOS and Linux, prefer system Hercules over bundled binaries
  # macOS: Homebrew Hercules (ARM64 native, proper device modules)
  # Linux: System Hercules 3.13 (bundled binaries have missing shared libraries)
  if command -v hercules &>/dev/null; then
    HERC_BIN="$(dirname "$(command -v hercules)")"
    # Homebrew device modules directory (macOS only)
    if [ "$(uname -s)" = "Darwin" ] && [ -d "/opt/homebrew/lib/hercules" ]; then
      HERC_LIB="/opt/homebrew/lib/hercules"
    else
      HERC_LIB=""
    fi
    return
  fi

  # Fallback to bundled Hercules if system version not found
  HERC_OS=""
  case "$(uname -s)" in
    Linux)
      case "$(uname -m)" in
        x86_64)  HERC_OS="linux/64" ;;
        aarch64) HERC_OS="linux/aarch64" ;;
        armv7*)  HERC_OS="linux/arm" ;;
        i686)    HERC_OS="linux/32" ;;
        *)       HERC_OS="linux/64" ;;
      esac ;;
  esac

  if [ -n "$HERC_OS" ]; then
    HERC_BIN="$TK5/hercules/$HERC_OS/bin"
    HERC_LIB="$TK5/hercules/$HERC_OS/lib"
    chmod +x "$HERC_BIN/hercules" 2>/dev/null
  else
    HERC_BIN=""
    HERC_LIB=""
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

  # Kill stale s3270 processes (they hold 3270 devices and prevent reconnect after restart)
  pkill -f "s3270" 2>/dev/null

  # Cleanup stale tail processes from old TK5 starts
  pkill -f "tail -f /dev/null" 2>/dev/null

  sleep 1
  echo -e "${GRN}${BLD}All stopped.${RST}\n"
}

# ═══════════════════════════════════════════════════════
#  HEALTH CHECKS (TCP socket — no curl, no OOM risk)
# ═══════════════════════════════════════════════════════
check_webapp() {
  (echo > /dev/tcp/127.0.0.1/$PORT) 2>/dev/null
}

check_ollama() {
  (echo > /dev/tcp/127.0.0.1/11434) 2>/dev/null
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
    nohup ollama serve >> "$LOGDIR/ollama.log" 2>&1 &
    disown $!
    if wait_for "Ollama" check_ollama 10; then
      ok "Ollama started (pid $(pgrep -x ollama 2>/dev/null))"
    else
      fail "Ollama failed to start — install from https://ollama.com"
      info "Continuing without AI..."
      OLLAMA_OK=0
      return 1
    fi
  fi

  info "RAM: ${TOTAL_RAM_MB}MB → target model: ${BLD}$MODEL${RST}"
  OLLAMA_OK=1

  # Check if target model is already pulled
  if timeout 5 ollama list 2>/dev/null | grep -q "$MODEL"; then
    ok "Model $MODEL ready"
  else
    # Use first available model as fallback while target pulls
    FALLBACK=$(timeout 5 ollama list 2>/dev/null | tail -n +2 | head -1 | awk '{print $1}')
    if [ -n "$FALLBACK" ]; then
      info "Using $FALLBACK while pulling $MODEL in background..."
      MODEL="$FALLBACK"
    else
      info "No models installed — pulling $MODEL (this may take a while)..."
    fi
    # Pull target model in background
    ( ollama pull "$MODEL" ) >> "$LOGDIR/ollama.log" 2>&1 &
  fi
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

  pkill -9 s3270 2>/dev/null
  mkdir -p "$TK5/log" 2>/dev/null
  > "$TK5/log/hardcopy.log" 2>/dev/null || true

  # Restore fresh DASD — kill -9 on Hercules corrupts disk images
  DASD_BACKUP="$TK5/dasd_backup"
  DASD_CACHE="$DIR/.cache/tk5-files.tar.gz"
  if [ -d "$DASD_BACKUP" ] && [ "$(ls "$DASD_BACKUP"/*.390 2>/dev/null | wc -l)" -gt 0 ]; then
    cp -f "$DASD_BACKUP"/* "$TK5/dasd/" 2>/dev/null
    ok "DASD restored from dasd_backup/"
  elif [ -f "$DASD_CACHE" ]; then
    mkdir -p "$TK5/dasd" "$TK5/dasd_backup"
    tar xzf "$DASD_CACHE" -C "$TK5/dasd_backup/" 2>/dev/null
    cp -f "$TK5/dasd_backup/"* "$TK5/dasd/" 2>/dev/null || true
    ok "DASD restored from cache"
  else
    info "Downloading DASD from GitHub release (public)..."
    mkdir -p "$DIR/.cache"
    rm -f "$DASD_CACHE"
    DASD_URL="https://github.com/W00t3k/mainframe-ai/releases/download/v1.0-dasd/tk5-dasd.tar.gz"
    if command -v curl &>/dev/null; then
      curl -fsSL "$DASD_URL" -o "$DASD_CACHE" 2>/dev/null
    elif command -v wget &>/dev/null; then
      wget -q "$DASD_URL" -O "$DASD_CACHE" 2>/dev/null
    fi
    if [ -f "$DASD_CACHE" ] && [ -s "$DASD_CACHE" ]; then
      mkdir -p "$TK5/dasd" "$TK5/dasd_backup"
      tar xzf "$DASD_CACHE" -C "$TK5/dasd_backup/" 2>/dev/null
      cp -f "$TK5/dasd_backup/"* "$TK5/dasd/" 2>/dev/null || true
      ok "DASD restored from GitHub release"
    else
      fail "Could not download DASD"
      info "Run: sudo ./setup.sh"
    fi
  fi

  info "Starting Hercules ($(uname -s)/$(uname -m))..."

  # Different startup for Linux (Hercules 3.x) vs macOS (Hercules 4.x)
  if [ "$(uname -s)" = "Linux" ]; then
    # Linux: Hercules 3.13 — use -d (daemon mode, no TTY needed) + pipe ipl.rc via stdin
    info "Using config: $TK5/conf/tk5-linux.cnf"
    info "Using binary: $HERC_BIN/hercules"
    if [ ! -f "$TK5/conf/tk5-linux.cnf" ]; then
      fail "tk5-linux.cnf not found! Run: git pull origin master"
      TK5_OK=0; return 1
    fi
    nohup bash -c "
      cd \"$TK5\"
      export PATH=\"$HERC_BIN:\$PATH\"
      export LD_LIBRARY_PATH=\"$HERC_LIB:\$LD_LIBRARY_PATH\"
      export HERCULES_LIB=\"$HERC_LIB\"
      (cat scripts/ipl.rc; tail -f /dev/null) | \"$HERC_BIN/hercules\" -f conf/tk5-linux.cnf
    " > "$LOGDIR/hercules.log" 2>&1 &
    disown $!
    sleep 3
    info "DASD check: $(ls "$TK5/dasd/"*.390 2>/dev/null | wc -l) .390 files in dasd/"
    info "Hercules log (first 10 lines):"
    head -10 "$LOGDIR/hercules.log" 2>/dev/null | sed 's/^/    /'
  else
    # macOS: Hercules 4.x - use -r flag
    nohup bash -c "
      cd \"$TK5\"
      export PATH=\"$HERC_BIN:\$PATH\"
      export LD_LIBRARY_PATH=\"$HERC_LIB:\$LD_LIBRARY_PATH\"
      export DYLD_LIBRARY_PATH=\"$HERC_LIB:\$DYLD_LIBRARY_PATH\"
      export HERCULES_LIB=\"$HERC_LIB\"
      export HERCULES_PATH=\"$HERC_LIB\"
      tail -f /dev/null | \"$HERC_BIN/hercules\" -f conf/tk5.cnf -r scripts/ipl.rc -d
    " > "$LOGDIR/hercules.log" 2>&1 &
    disown $!
  fi

  if [ "$(uname -s)" = "Linux" ]; then
    # Linux: verbose wait loop - show log every 10s
    TK5_OK=0
    for _i in $(seq 10 10 300); do
      sleep 10
      if check_tk5; then
        ok "TK5 started — TN3270 on port 3270"
        ok "Login: HERC01 / CUL8TR"
        TK5_OK=1
        break
      fi
      echo "  … Still waiting (${_i}s) — last log line:"
      tail -1 "$LOGDIR/hercules.log" 2>/dev/null | sed 's/^/    /'
      # Show errors immediately
      grep -q "HHCIN099I\|Syntax error\|cannot open shared object\|HHCDA020E\|HHCDA001E\|open error" "$LOGDIR/hercules.log" 2>/dev/null && {
        fail "Hercules error detected — dumping log:"
        cat "$LOGDIR/hercules.log" 2>/dev/null | sed 's/^/    /'
        TK5_OK=0
        return 1
      }
    done
    if [ "$TK5_OK" = "0" ]; then
      fail "TK5 failed to start after 300s"
      echo "  Full Hercules log:"
      echo "  ─────────────────────────────────────────────────"
      cat "$LOGDIR/hercules.log" 2>/dev/null | sed 's/^/    /'
      echo "  ─────────────────────────────────────────────────"
    fi
  else
    if wait_for "TK5" check_tk5 300; then
      ok "TK5 started — TN3270 on port 3270"
      ok "Login: HERC01 / CUL8TR"
      TK5_OK=1
    else
      fail "TK5 failed to start"
      info "Check log: $LOGDIR/hercules.log"
      tail -5 "$LOGDIR/hercules.log" 2>/dev/null | while read -r line; do echo "    $line"; done
      TK5_OK=0
    fi
  fi
}

start_webapp_svc() {
  echo -e "\n${BLD}[3/3] Web Application${RST}"
  # Auto-connect to TK5 after webapp starts (background, non-blocking)
  # Uses Python instead of curl — curl gets OOM-killed on Mac under memory pressure
  _auto_connect_tk5() {
    local hardcopy="$TK5/log/hardcopy.log"
    local waited=0
    # Phase 1: Wait for VTAM via hardcopy.log (poll every 2s, up to 600s)
    while [ $waited -lt 600 ]; do
      sleep 2; waited=$((waited+2))
      grep -q "TCAS ACCEPTING LOGONS" "$hardcopy" 2>/dev/null && break
    done
    grep -q "TCAS ACCEPTING LOGONS" "$hardcopy" 2>/dev/null || return 1
    sleep 1

    # Phase 2: Connect web app
    check_webapp || return 1
    "$PYTHON" -c "
import urllib.request, json
req = urllib.request.Request(
  'http://127.0.0.1:$PORT/api/terminal/connect',
  data=json.dumps({'target':'localhost:3270'}).encode(),
  headers={'Content-Type':'application/json'},
  method='POST'
)
urllib.request.urlopen(req, timeout=30)
" 2>/dev/null

    # Phase 2b: Submit JCL via port 3505 card reader (no TN3270 needed)
    # Install extra terminals + FTPD proc if not already done
    _submit_jcl() {
      local jcl_file="$1"
      local label="$2"
      if [ -f "$DIR/$jcl_file" ]; then
        "$PYTHON" -c "
import socket, sys
raw = open('$DIR/$jcl_file').read()
clean = '\n'.join(''.join(c if ord(c)<128 else ' ' for c in l)[:80] for l in raw.splitlines()) + '\n'
try:
    s = socket.socket(); s.settimeout(10)
    s.connect(('localhost', 3505)); s.sendall(clean.encode('ascii')); s.close()
    print('Submitted: $jcl_file')
except Exception as e:
    print(f'Submit failed: {e}', file=sys.stderr)
" 2>/dev/null && ok "$label JCL submitted" || info "$label submit skipped"
      fi
    }

    # Wait for JES2 + submit extra terminals in parallel
    sleep 3
    _submit_jcl "jcl/terminals.jcl" "Extra terminals (32x VTAM)"
    
    # Start FTPD (dasd_backup already has UPDVTAM + custom USS fixes)
    curl -s --max-time 5 -X POST "http://localhost:8038/cgi-bin/tasks/syslog" \
      --data "command=%2FS+FTPD" -o /dev/null 2>&1 \
      && ok "FTPD started" || info "FTPD start skipped"
    
    ok "AI/OS USS screen active (from DASD backup)"

    ok "VTAM ready — AI/OS TN3270 logon screen available"
  }

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
    _auto_connect_tk5 &
    disown $!
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

  # FTP
  if (echo > /dev/tcp/127.0.0.1/2121) 2>/dev/null; then
    echo -e "${CYN}║${RST}  ${GRN}●${RST} FTP Server  ${GRN}RUNNING${RST}   ftp localhost 2121         ${CYN}║${RST}"
  else
    echo -e "${CYN}║${RST}  ${YEL}●${RST} FTP Server  ${YEL}STANDBY${RST}   submit jcl/ftpd.jcl        ${CYN}║${RST}"
  fi

  # KICKS
  if check_tk5; then
    echo -e "${CYN}║${RST}  ${GRN}●${RST} KICKS CICS  ${GRN}AVAILABLE${RST} type CICS at logon         ${CYN}║${RST}"
  else
    echo -e "${CYN}║${RST}  ${YEL}●${RST} KICKS CICS  ${YEL}STANDBY${RST}   needs TK5 running          ${CYN}║${RST}"
  fi

  # GPU (only if detected)
  if command -v nvidia-smi &>/dev/null; then
    local gpu_name_live gpu_vram_used gpu_vram_total gpu_util gpu_temp gpu_vram_pct gpu_tier_label
    gpu_name_live=$(nvidia-smi --query-gpu=name --format=csv,noheader,nounits 2>/dev/null | head -1)
    if [ -n "$gpu_name_live" ]; then
      gpu_vram_used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1)
      gpu_vram_total=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1)
      gpu_util=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | head -1)
      gpu_temp=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null | head -1)
      gpu_vram_pct=0
      [ "$gpu_vram_total" -gt 0 ] 2>/dev/null && gpu_vram_pct=$((gpu_vram_used * 100 / gpu_vram_total))

      # Tier label
      local vgb=$((gpu_vram_total / 1024))
      if [ "$vgb" -ge 80 ]; then gpu_tier_label="ULTRA"
      elif [ "$vgb" -ge 40 ]; then gpu_tier_label="HIGH"
      elif [ "$vgb" -ge 20 ]; then gpu_tier_label="MEDIUM"
      elif [ "$vgb" -ge 8 ]; then gpu_tier_label="LOW"
      else gpu_tier_label="MINIMAL"; fi

      echo -e "${CYN}║${RST}  ${MAG}⚡${RST} GPU         ${GRN}DETECTED${RST}   ${BLD}${gpu_name_live}${RST}        ${CYN}║${RST}"
      echo -e "${CYN}║${RST}    VRAM: ${gpu_vram_used}MB / ${gpu_vram_total}MB (${gpu_vram_pct}%)   Util: ${gpu_util}%   ${gpu_temp}°C  ${CYN}║${RST}"
      echo -e "${CYN}║${RST}    Tier: ${MAG}${BLD}${gpu_tier_label}${RST}   Model: ${BLD}${MODEL}${RST}              ${CYN}║${RST}"
    fi
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

    # Check web app via TCP socket
    if check_webapp; then
      backoff=2
      continue
    fi

    # Also check if process is alive (TCP check can fail during a slow request)
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
