#!/bin/bash
# ─────────────────────────────────────────────────────────
#  Mainframe AI Assistant — GPU-Optimized Launcher
#
#  Designed for NVIDIA H200 (141GB VRAM) but auto-detects any GPU.
#
#  Usage:
#    ./start_gpu.sh                    Start with auto-detected GPU model
#    ./start_gpu.sh --model llama3.1:70b   Override model
#    ./start_gpu.sh --setup            First-time GPU setup (pull models)
#    ./start_gpu.sh --info             Show GPU info and exit
# ─────────────────────────────────────────────────────────

set -o pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=8080
HOST="0.0.0.0"
LOGDIR="$DIR/logs"
mkdir -p "$LOGDIR"

# ── Colors ─────────────────────────────────────────────
RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[0;33m'
CYN='\033[0;36m'; BLD='\033[1m'; RST='\033[0m'
MAG='\033[0;35m'

ok()   { echo -e "  ${GRN}✓${RST} $1"; }
fail() { echo -e "  ${RED}✗${RST} $1"; }
info() { echo -e "  ${YEL}…${RST} $1"; }
gpu()  { echo -e "  ${MAG}⚡${RST} $1"; }

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

# ── Detect GPU ─────────────────────────────────────────
detect_gpu() {
  GPU_NAME=""
  GPU_VRAM_MB=0
  GPU_VRAM_GB=0

  if ! command -v nvidia-smi &>/dev/null; then
    fail "nvidia-smi not found — no NVIDIA GPU detected"
    fail "Install NVIDIA drivers: https://docs.nvidia.com/datacenter/tesla/tesla-installation-notes/"
    return 1
  fi

  GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader,nounits 2>/dev/null | head -1)
  GPU_VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1)
  GPU_VRAM_GB=$((GPU_VRAM_MB / 1024))
  GPU_DRIVER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1)
  GPU_CUDA=$(nvidia-smi 2>/dev/null | grep "CUDA Version" | awk '{print $9}')
  GPU_TEMP=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null | head -1)
  GPU_UTIL=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | head -1)
  GPU_COUNT=$(nvidia-smi --query-gpu=count --format=csv,noheader,nounits 2>/dev/null | head -1)

  if [ -z "$GPU_NAME" ] || [ "$GPU_VRAM_MB" -eq 0 ]; then
    fail "GPU detected but could not read VRAM"
    return 1
  fi

  return 0
}

# ── Select model based on VRAM ─────────────────────────
select_gpu_model() {
  if [ "$GPU_VRAM_GB" -ge 80 ]; then
    # ULTRA tier: H100/H200/A100-80GB
    GPU_TIER="ULTRA"
    DEFAULT_MODEL="llama3.1:70b"
    AVAILABLE_MODELS="deepseek-coder-v2:236b llama3.1:70b deepseek-v2.5:236b qwen2.5:72b codellama:70b mixtral:8x22b"
  elif [ "$GPU_VRAM_GB" -ge 40 ]; then
    # HIGH tier: A100-40GB, A6000
    GPU_TIER="HIGH"
    DEFAULT_MODEL="llama3.1:70b-instruct-q4_0"
    AVAILABLE_MODELS="llama3.1:70b-instruct-q4_0 deepseek-coder-v2:16b qwen2.5:32b codellama:34b"
  elif [ "$GPU_VRAM_GB" -ge 20 ]; then
    # MEDIUM tier: RTX 4090/3090
    GPU_TIER="MEDIUM"
    DEFAULT_MODEL="deepseek-coder-v2:16b"
    AVAILABLE_MODELS="deepseek-coder-v2:16b llama3.1:8b codellama:13b"
  elif [ "$GPU_VRAM_GB" -ge 8 ]; then
    # LOW tier: RTX 4070/3060
    GPU_TIER="LOW"
    DEFAULT_MODEL="llama3.1:8b"
    AVAILABLE_MODELS="llama3.1:8b deepseek-coder:6.7b"
  else
    # MINIMAL tier
    GPU_TIER="MINIMAL"
    DEFAULT_MODEL="llama3.2:3b"
    AVAILABLE_MODELS="llama3.2:3b tinyllama"
  fi

  # Use override if provided
  MODEL="${OVERRIDE_MODEL:-$DEFAULT_MODEL}"
}

# ── Set Ollama GPU environment ─────────────────────────
set_ollama_gpu_env() {
  export CUDA_VISIBLE_DEVICES="0"

  if [ "$GPU_VRAM_GB" -ge 80 ]; then
    export OLLAMA_KEEP_ALIVE="60m"
    export OLLAMA_NUM_PARALLEL="4"
    export OLLAMA_MAX_LOADED_MODELS="3"
    export OLLAMA_FLASH_ATTENTION="1"
  elif [ "$GPU_VRAM_GB" -ge 40 ]; then
    export OLLAMA_KEEP_ALIVE="30m"
    export OLLAMA_NUM_PARALLEL="2"
    export OLLAMA_MAX_LOADED_MODELS="2"
    export OLLAMA_FLASH_ATTENTION="1"
  elif [ "$GPU_VRAM_GB" -ge 20 ]; then
    export OLLAMA_KEEP_ALIVE="15m"
    export OLLAMA_NUM_PARALLEL="2"
    export OLLAMA_MAX_LOADED_MODELS="1"
  else
    export OLLAMA_KEEP_ALIVE="10m"
    export OLLAMA_NUM_PARALLEL="1"
    export OLLAMA_MAX_LOADED_MODELS="1"
  fi
}

# ── Pull recommended models ───────────────────────────
setup_gpu_models() {
  echo -e "\n${BLD}${MAG}⚡ GPU Model Setup${RST}"
  echo -e "  Pulling recommended models for ${GPU_TIER} tier (${GPU_NAME}, ${GPU_VRAM_GB}GB)...\n"

  for m in $AVAILABLE_MODELS; do
    info "Pulling $m ..."
    if ollama pull "$m" 2>&1 | tail -1; then
      ok "$m ready"
    else
      fail "$m failed to pull (may not exist yet)"
    fi
    echo ""
  done

  echo -e "\n${GRN}${BLD}Setup complete!${RST}"
  echo -e "  Default model: ${BLD}$DEFAULT_MODEL${RST}"
  echo -e "  Start with: ${CYN}./start_gpu.sh${RST}\n"
}

# ── Show GPU info ──────────────────────────────────────
show_gpu_info() {
  detect_python
  $PYTHON run.py --gpu-info
}

# ── Start Ollama with GPU ──────────────────────────────
start_ollama_gpu() {
  echo -e "\n${BLD}[1/2] Ollama AI Backend (GPU-Accelerated)${RST}"

  set_ollama_gpu_env

  # Check if already running
  if curl -sf --max-time 3 "http://127.0.0.1:11434/api/tags" > /dev/null 2>&1; then
    ok "Ollama already running"
  else
    info "Starting Ollama with GPU acceleration..."
    nohup ollama serve > "$LOGDIR/ollama_gpu.log" 2>&1 &
    sleep 3

    if curl -sf --max-time 5 "http://127.0.0.1:11434/api/tags" > /dev/null 2>&1; then
      ok "Ollama started with GPU"
    else
      fail "Ollama failed to start — check $LOGDIR/ollama_gpu.log"
      return 1
    fi
  fi

  # Pre-load the model into GPU VRAM
  gpu "Pre-loading $MODEL into GPU VRAM..."
  ollama pull "$MODEL" 2>/dev/null
  # Warm up: send a tiny request to load model into VRAM
  curl -sf "http://127.0.0.1:11434/api/generate" \
    -d "{\"model\":\"$MODEL\",\"prompt\":\"hello\",\"stream\":false,\"options\":{\"num_predict\":1}}" \
    > /dev/null 2>&1 &

  ok "Model $MODEL loading into GPU VRAM"
}

# ── Start Web App ──────────────────────────────────────
start_webapp_gpu() {
  echo -e "\n${BLD}[2/2] Web Application (GPU-Optimized)${RST}"

  # Kill existing
  lsof -ti :$PORT 2>/dev/null | xargs kill -9 2>/dev/null

  detect_python

  export OLLAMA_MODEL="$MODEL"
  nohup $PYTHON run.py --host $HOST --port $PORT --model "$MODEL" \
    > "$LOGDIR/webapp_gpu.log" 2>&1 &

  sleep 2

  if curl -sf --max-time 5 "http://127.0.0.1:$PORT/api/status" > /dev/null 2>&1; then
    ok "Web app running on http://$HOST:$PORT"
  else
    # Give it more time for large model init
    sleep 3
    if curl -sf --max-time 5 "http://127.0.0.1:$PORT/api/status" > /dev/null 2>&1; then
      ok "Web app running on http://$HOST:$PORT"
    else
      info "Web app starting (may take a moment with large models)..."
    fi
  fi
}

# ═══════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════

OVERRIDE_MODEL=""

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --model)
      OVERRIDE_MODEL="$2"
      shift 2
      ;;
    --setup)
      detect_gpu || exit 1
      select_gpu_model
      setup_gpu_models
      exit 0
      ;;
    --info)
      detect_gpu
      select_gpu_model
      echo -e "\n${BLD}${MAG}⚡ GPU Information${RST}"
      echo -e "  GPU:        ${BLD}$GPU_NAME${RST}"
      echo -e "  VRAM:       ${GPU_VRAM_GB}GB"
      echo -e "  Driver:     $GPU_DRIVER"
      echo -e "  CUDA:       $GPU_CUDA"
      echo -e "  Temp:       ${GPU_TEMP}°C"
      echo -e "  Util:       ${GPU_UTIL}%"
      echo -e "  Count:      $GPU_COUNT"
      echo -e "  Tier:       ${BLD}$GPU_TIER${RST}"
      echo -e "  Default:    ${BLD}$DEFAULT_MODEL${RST}"
      echo -e "  Available:  $AVAILABLE_MODELS"
      echo ""
      show_gpu_info
      exit 0
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --host)
      HOST="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: ./start_gpu.sh [--model MODEL] [--setup] [--info] [--port PORT] [--host HOST]"
      exit 1
      ;;
  esac
done

# Main flow
echo -e "\n${BLD}${MAG}⚡ Mainframe AI Assistant — GPU Edition${RST}\n"

if ! detect_gpu; then
  echo ""
  fail "No NVIDIA GPU detected. Use ./start.sh for CPU mode."
  exit 1
fi

select_gpu_model

echo ""
gpu "GPU:   $GPU_NAME ($GPU_VRAM_GB GB VRAM)"
gpu "Tier:  $GPU_TIER"
gpu "Model: $MODEL"
gpu "CUDA:  $GPU_CUDA | Driver: $GPU_DRIVER"
echo ""

start_ollama_gpu
start_webapp_gpu

echo -e "\n${BLD}${GRN}═══════════════════════════════════════════════════════${RST}"
echo -e "${BLD}${GRN}  GPU-Accelerated Mainframe AI Assistant is READY${RST}"
echo -e "${BLD}${GRN}═══════════════════════════════════════════════════════${RST}"
echo -e "  ${CYN}Web UI:${RST}  http://$HOST:$PORT/"
echo -e "  ${CYN}Chat:${RST}    http://$HOST:$PORT/chat"
echo -e "  ${CYN}GPU API:${RST} http://$HOST:$PORT/api/gpu/status"
echo -e "  ${CYN}Model:${RST}   $MODEL"
echo -e "  ${CYN}GPU:${RST}     $GPU_NAME ($GPU_VRAM_GB GB)"
echo -e ""
echo -e "  ${YEL}Switch model:${RST} curl -X POST 'http://$HOST:$PORT/api/gpu/switch-model?model=deepseek-coder-v2:236b'"
echo -e ""
