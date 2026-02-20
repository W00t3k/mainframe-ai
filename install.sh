#!/bin/bash
# ─────────────────────────────────────────────────────────
#  Mainframe AI Assistant — Linux Install Script
#
#  Tested on: Ubuntu 22.04/24.04, Debian 12, Kali, Fedora 39+
#
#  Usage:
#    chmod +x install.sh
#    ./install.sh
#
#  What this does:
#    1. Installs system dependencies (Python 3.11+, git, curl, etc.)
#    2. Installs Ollama (local LLM backend)
#    3. Pulls the llama3.1:8b model
#    4. Clones the repo (or uses current directory)
#    5. Creates Python virtual environment
#    6. Installs Python dependencies
#    7. Downloads & extracts TK5 mainframe emulator (optional)
#    8. Verifies everything works
# ─────────────────────────────────────────────────────────

set -e

RED='\033[0;31m'
GRN='\033[0;32m'
YEL='\033[0;33m'
CYN='\033[0;36m'
RST='\033[0m'

REPO_URL="https://github.com/W00t3k/mainframe-ai.git"
# NOTE: This is a private repo. You need GitHub access to clone.
# Options:
#   1. Use a GitHub Personal Access Token (PAT):
#      git clone https://<YOUR_TOKEN>@github.com/W00t3k/mainframe-ai.git
#   2. Use SSH (if you have keys configured):
#      git clone git@github.com:W00t3k/mainframe-ai.git
#   3. Use GitHub CLI:
#      gh auth login && gh repo clone W00t3k/mainframe-ai
MODEL="llama3.1:8b"   # Default — overridden by GPU detection
GPU_DETECTED=0
GPU_VRAM_GB=0
GPU_NAME=""
PYTHON_MIN="3.11"
INSTALL_DIR=""

# ── Helpers ────────────────────────────────────────────────
info()  { echo -e "${CYN}[*]${RST} $1"; }
ok()    { echo -e "${GRN}[✓]${RST} $1"; }
warn()  { echo -e "${YEL}[!]${RST} $1"; }
fail()  { echo -e "${RED}[✗]${RST} $1"; exit 1; }

check_root() {
  if [ "$(id -u)" -eq 0 ]; then
    warn "Running as root. Will install system packages directly."
    SUDO=""
  else
    SUDO="sudo"
    info "Will use sudo for system packages."
  fi
}

detect_distro() {
  if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO="$ID"
    DISTRO_FAMILY="$ID_LIKE"
  elif command -v lsb_release &>/dev/null; then
    DISTRO=$(lsb_release -si | tr '[:upper:]' '[:lower:]')
  else
    DISTRO="unknown"
  fi
  info "Detected distro: $DISTRO"
}

# ── GPU Detection ────────────────────────────────────────
detect_gpu() {
  info "Checking for NVIDIA GPU..."

  if ! command -v nvidia-smi &>/dev/null; then
    warn "nvidia-smi not found — no NVIDIA GPU detected, using CPU mode"
    return
  fi

  GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader,nounits 2>/dev/null | head -1)
  GPU_VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1)

  if [ -z "$GPU_NAME" ]; then
    warn "nvidia-smi found but no GPU detected"
    return
  fi

  GPU_VRAM_GB=$((GPU_VRAM_MB / 1024))
  GPU_DETECTED=1

  # Select model based on VRAM tier
  if [ "$GPU_VRAM_GB" -ge 80 ]; then
    MODEL="llama3.1:70b"
    GPU_TIER="ULTRA"
  elif [ "$GPU_VRAM_GB" -ge 40 ]; then
    MODEL="llama3.1:70b-instruct-q4_0"
    GPU_TIER="HIGH"
  elif [ "$GPU_VRAM_GB" -ge 20 ]; then
    MODEL="qwen2.5:32b"
    GPU_TIER="MEDIUM"
  elif [ "$GPU_VRAM_GB" -ge 8 ]; then
    MODEL="llama3.1:8b"
    GPU_TIER="LOW"
  else
    MODEL="llama3.2:3b"
    GPU_TIER="MINIMAL"
  fi

  ok "GPU detected: ${GPU_NAME} (${GPU_VRAM_GB}GB VRAM) — Tier: ${GPU_TIER}"
  ok "GPU model selected: ${MODEL}"
}

# ── CUDA / GPU System Deps ────────────────────────────────
install_gpu_deps() {
  [ "$GPU_DETECTED" -eq 0 ] && return

  info "Installing GPU dependencies..."

  case "$DISTRO" in
    ubuntu|debian|kali|pop|linuxmint)
      # nvidia-utils for nvidia-smi (usually already present with driver)
      $SUDO apt-get install -y -qq nvidia-utils-$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1 | cut -d. -f1) 2>/dev/null || true
      ok "GPU utilities ready"
      ;;
    *)
      info "GPU driver assumed pre-installed (non-Debian distro)"
      ;;
  esac
}

# ── System Dependencies ───────────────────────────────────
install_system_deps() {
  info "Installing system dependencies..."

  case "$DISTRO" in
    ubuntu|debian|kali|pop|linuxmint)
      $SUDO apt-get update -qq
      $SUDO apt-get install -y -qq \
        python3 python3-pip python3-venv python3-dev \
        git curl wget build-essential \
        libffi-dev libssl-dev \
        x3270 c3270 s3270 3270-common \
        hercules \
        lsof net-tools unzip
      # GitHub CLI
      if ! command -v gh &>/dev/null; then
        info "Installing GitHub CLI..."
        curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | $SUDO dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg 2>/dev/null
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | $SUDO tee /etc/apt/sources.list.d/github-cli.list > /dev/null
        $SUDO apt-get update -qq
        $SUDO apt-get install -y -qq gh
      fi
      ;;
    fedora)
      $SUDO dnf install -y \
        python3 python3-pip python3-devel \
        git curl wget gcc gcc-c++ make \
        libffi-devel openssl-devel \
        x3270 unzip \
        lsof net-tools
      if ! command -v gh &>/dev/null; then
        $SUDO dnf install -y gh 2>/dev/null || \
          ($SUDO dnf install -y 'dnf-command(config-manager)' && \
           $SUDO dnf config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo && \
           $SUDO dnf install -y gh)
      fi
      ;;
    centos|rhel|rocky|alma)
      $SUDO dnf install -y epel-release 2>/dev/null || true
      $SUDO dnf install -y \
        python3 python3-pip python3-devel \
        git curl wget gcc gcc-c++ make \
        libffi-devel openssl-devel \
        lsof net-tools unzip
      if ! command -v gh &>/dev/null; then
        $SUDO dnf config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo 2>/dev/null
        $SUDO dnf install -y gh 2>/dev/null || warn "Could not install GitHub CLI"
      fi
      ;;
    arch|manjaro|endeavouros)
      $SUDO pacman -Sy --noconfirm \
        python python-pip \
        git curl wget base-devel \
        x3270 github-cli unzip \
        lsof net-tools
      ;;
    opensuse*|sles)
      $SUDO zypper install -y \
        python3 python3-pip python3-devel \
        git curl wget gcc gcc-c++ make \
        libffi-devel libopenssl-devel \
        lsof net-tools unzip
      if ! command -v gh &>/dev/null; then
        $SUDO zypper install -y gh 2>/dev/null || warn "Could not install GitHub CLI"
      fi
      ;;
    *)
      warn "Unknown distro '$DISTRO'. Attempting apt-get..."
      $SUDO apt-get update -qq 2>/dev/null && \
      $SUDO apt-get install -y -qq \
        python3 python3-pip python3-venv python3-dev \
        git curl wget build-essential lsof || \
      fail "Could not install system deps. Install Python 3.11+, git, curl manually."
      ;;
  esac

  ok "System dependencies installed"
}

# ── Python Version Check ──────────────────────────────────
check_python() {
  info "Checking Python version..."

  PYTHON=""
  for cmd in python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
      PY_VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
      PY_MAJOR=$("$cmd" -c "import sys; print(sys.version_info.major)")
      PY_MINOR=$("$cmd" -c "import sys; print(sys.version_info.minor)")
      if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 11 ]; then
        PYTHON="$cmd"
        break
      fi
    fi
  done

  if [ -z "$PYTHON" ]; then
    warn "Python 3.11+ not found. Attempting to install..."
    case "$DISTRO" in
      ubuntu|debian|kali|pop|linuxmint)
        $SUDO apt-get install -y -qq software-properties-common
        $SUDO add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
        $SUDO apt-get update -qq
        $SUDO apt-get install -y -qq python3.11 python3.11-venv python3.11-dev
        PYTHON="python3.11"
        ;;
      fedora)
        $SUDO dnf install -y python3.11
        PYTHON="python3.11"
        ;;
      *)
        fail "Please install Python 3.11+ manually and re-run this script."
        ;;
    esac
  fi

  PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
  ok "Python $PY_VER ($PYTHON)"
}

# ── Ollama ────────────────────────────────────────────────
install_ollama() {
  info "Setting up Ollama..."

  if command -v ollama &>/dev/null; then
    ok "Ollama already installed ($(ollama --version 2>/dev/null || echo 'unknown version'))"
  else
    info "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    if command -v ollama &>/dev/null; then
      ok "Ollama installed"
    else
      fail "Ollama installation failed. Visit https://ollama.com for manual install."
    fi
  fi

  # Set GPU env vars before starting Ollama
  if [ "$GPU_DETECTED" -eq 1 ]; then
    export CUDA_VISIBLE_DEVICES="0"
    export OLLAMA_FLASH_ATTENTION="1"
    if [ "$GPU_VRAM_GB" -ge 80 ]; then
      export OLLAMA_NUM_PARALLEL="4"
      export OLLAMA_MAX_LOADED_MODELS="4"
      export OLLAMA_KEEP_ALIVE="60m"
    elif [ "$GPU_VRAM_GB" -ge 40 ]; then
      export OLLAMA_NUM_PARALLEL="2"
      export OLLAMA_MAX_LOADED_MODELS="2"
      export OLLAMA_KEEP_ALIVE="30m"
    fi
    info "Ollama GPU mode: ${GPU_TIER} tier, ${GPU_VRAM_GB}GB VRAM"
  fi

  # Start Ollama if not running
  if ! pgrep -x "ollama" > /dev/null 2>&1; then
    info "Starting Ollama service..."
    ollama serve > /dev/null 2>&1 &
    sleep 3
  fi

  # Pull model
  if ollama list 2>/dev/null | grep -q "$(echo $MODEL | cut -d: -f1)"; then
    ok "Model $MODEL already available"
  else
    info "Pulling $MODEL — this may take a while on first run..."
    if [ "$GPU_VRAM_GB" -ge 80 ]; then
      warn "Large model (~40GB+). This will take 10-30 min depending on network speed."
    fi
    ollama pull "$MODEL"
    ok "Model $MODEL downloaded"
  fi
}

# ── GitHub Auth ────────────────────────────────────────────
setup_gh_auth() {
  if ! command -v gh &>/dev/null; then
    warn "GitHub CLI not available — you'll need to authenticate manually for git clone."
    return
  fi

  # Check if already authenticated
  if gh auth status &>/dev/null 2>&1; then
    ok "GitHub CLI already authenticated"
    return
  fi

  echo ""
  echo -e "${CYN}┌──────────────────────────────────────────────────┐${RST}"
  echo -e "${CYN}│  GitHub Authentication Required                  │${RST}"
  echo -e "${CYN}│                                                  │${RST}"
  echo -e "${CYN}│  This is a private repo. You need to log in      │${RST}"
  echo -e "${CYN}│  to GitHub to clone it.                          │${RST}"
  echo -e "${CYN}│                                                  │${RST}"
  echo -e "${CYN}│  Choose HTTPS when prompted.                     │${RST}"
  echo -e "${CYN}│  Choose 'Login with a web browser' or paste      │${RST}"
  echo -e "${CYN}│  a Personal Access Token.                        │${RST}"
  echo -e "${CYN}└──────────────────────────────────────────────────┘${RST}"
  echo ""

  gh auth login --hostname github.com

  if gh auth status &>/dev/null 2>&1; then
    ok "GitHub authentication successful"
  else
    warn "GitHub auth may have failed — clone might prompt for credentials"
  fi
}

# ── Clone Repo ────────────────────────────────────────────
setup_repo() {
  # Check if we're already inside the repo
  if [ -f "run.py" ] && [ -f "requirements.txt" ] && [ -d "app" ]; then
    INSTALL_DIR="$(pwd)"
    ok "Already in project directory: $INSTALL_DIR"
    return
  fi

  # Check if repo exists in current dir
  if [ -d "mainframe-ai" ]; then
    INSTALL_DIR="$(pwd)/mainframe-ai"
    ok "Repo already cloned: $INSTALL_DIR"
    cd "$INSTALL_DIR"
    git pull --quiet 2>/dev/null || true
    return
  fi

  info "Cloning repository..."
  if command -v gh &>/dev/null && gh auth status &>/dev/null 2>&1; then
    gh repo clone W00t3k/mainframe-ai
  else
    git clone "$REPO_URL" mainframe-ai
  fi
  INSTALL_DIR="$(pwd)/mainframe-ai"
  cd "$INSTALL_DIR"
  ok "Cloned to $INSTALL_DIR"
}

# ── Python Virtual Environment ────────────────────────────
setup_venv() {
  info "Setting up Python virtual environment..."

  if [ -d ".venv" ] && [ -f ".venv/bin/python" ]; then
    ok "Virtual environment already exists"
  else
    "$PYTHON" -m venv .venv
    ok "Virtual environment created"
  fi

  # Upgrade pip
  .venv/bin/python -m pip install --upgrade pip --quiet

  # Install requirements
  info "Installing Python dependencies (this may take a minute)..."
  .venv/bin/pip install -r requirements.txt --quiet
  ok "Python dependencies installed"
}

# ── TK5 Mainframe Emulator (Optional) ────────────────────
install_tk5() {
  echo ""
  echo -e "${CYN}┌──────────────────────────────────────────────────┐${RST}"
  echo -e "${CYN}│  TK5 MVS 3.8j Mainframe Emulator (Optional)     │${RST}"
  echo -e "${CYN}│                                                  │${RST}"
  echo -e "${CYN}│  This provides a local MVS mainframe with:       │${RST}"
  echo -e "${CYN}│  • TN3270 terminal access on port 3270           │${RST}"
  echo -e "${CYN}│  • TSO, ISPF, JES2, VTAM, RACF                  │${RST}"
  echo -e "${CYN}│  • Default login: HERC01 / CUL8TR                │${RST}"
  echo -e "${CYN}│                                                  │${RST}"
  echo -e "${CYN}│  Requires ~1.5 GB disk space.                    │${RST}"
  echo -e "${CYN}│  Runs via Hercules (SDL version).                │${RST}"
  echo -e "${CYN}└──────────────────────────────────────────────────┘${RST}"
  echo ""

  read -p "Install TK5 mainframe emulator? [y/N] " -n 1 -r
  echo ""

  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    warn "Skipping TK5. You can connect to any remote TN3270 host instead."
    return
  fi

  if [ -d "tk5" ]; then
    ok "TK5 directory already exists"
    return
  fi

  # Install Hercules SDL
  info "Installing Hercules mainframe emulator..."
  case "$DISTRO" in
    ubuntu|debian|kali|pop|linuxmint)
      $SUDO apt-get install -y -qq hercules
      ;;
    fedora)
      $SUDO dnf install -y hercules
      ;;
    arch|manjaro)
      $SUDO pacman -S --noconfirm hercules
      ;;
    *)
      warn "Please install Hercules manually: https://sdl-hercules-390.github.io/html/"
      ;;
  esac

  # Download TK5
  info "Downloading TK5 MVS distribution..."
  TK5_URL="https://www.prince-webdesign.nl/images/downloads/mvs-tk5.zip"
  mkdir -p tk5
  cd tk5

  if command -v wget &>/dev/null; then
    wget -q --show-progress "$TK5_URL" -O mvs-tk5.zip
  else
    curl -L -o mvs-tk5.zip "$TK5_URL"
  fi

  info "Extracting TK5 (this may take a moment)..."
  unzip -q mvs-tk5.zip
  rm -f mvs-tk5.zip
  cd ..

  ok "TK5 installed to tk5/"
}

# ── Verify Installation ───────────────────────────────────
verify() {
  echo ""
  echo -e "${CYN}══════════════════════════════════════════════════════${RST}"
  echo -e "${CYN}  Verification${RST}"
  echo -e "${CYN}══════════════════════════════════════════════════════${RST}"

  ERRORS=0

  # Python
  if .venv/bin/python -c "import fastapi, uvicorn, jinja2, httpx, psutil" 2>/dev/null; then
    ok "Python dependencies OK"
  else
    warn "Some Python dependencies missing — run: .venv/bin/pip install -r requirements.txt"
    ERRORS=$((ERRORS + 1))
  fi

  # Ollama
  if command -v ollama &>/dev/null; then
    ok "Ollama installed"
  else
    warn "Ollama not found"
    ERRORS=$((ERRORS + 1))
  fi

  # Model
  if ollama list 2>/dev/null | grep -q "$MODEL"; then
    ok "Model $MODEL available"
  else
    warn "Model $MODEL not pulled — run: ollama pull $MODEL"
    ERRORS=$((ERRORS + 1))
  fi

  # TK5
  if [ -d "tk5/mvs-tk5" ] || [ -d "tk5" ]; then
    ok "TK5 directory present"
  else
    warn "TK5 not installed (optional — can connect to remote mainframe)"
  fi

  # s3270 (required for web TN3270 terminal)
  if command -v s3270 &>/dev/null; then
    ok "s3270 available (TN3270 web terminal will work)"
  else
    warn "s3270 not found — TN3270 web terminal won't connect"
    warn "Fix: sudo apt-get install -y x3270   (installs s3270)"
    ERRORS=$((ERRORS + 1))
  fi

  # GPU
  if [ "$GPU_DETECTED" -eq 1 ]; then
    ok "GPU: ${GPU_NAME} (${GPU_VRAM_GB}GB) — ${GPU_TIER} tier"
    ok "GPU model: ${MODEL}"
  else
    info "No GPU detected — running in CPU mode with ${MODEL}"
  fi

  echo ""
  if [ $ERRORS -eq 0 ]; then
    echo -e "${GRN}══════════════════════════════════════════════════════${RST}"
    echo -e "${GRN}  Installation Complete!${RST}"
    echo -e "${GRN}══════════════════════════════════════════════════════${RST}"
  else
    echo -e "${YEL}══════════════════════════════════════════════════════${RST}"
    echo -e "${YEL}  Installation complete with $ERRORS warning(s)${RST}"
    echo -e "${YEL}══════════════════════════════════════════════════════${RST}"
  fi

  echo ""
  echo -e "  ${CYN}To start:${RST}"
  echo -e "    cd $INSTALL_DIR"
  if [ "$GPU_DETECTED" -eq 1 ]; then
    echo -e "    ${GRN}./start_gpu.sh${RST}          # GPU-optimized start (recommended for ${GPU_NAME})"
    echo -e "    ./start.sh              # Standard start (also GPU-aware)"
  else
    echo -e "    ./start.sh              # Web app + Ollama"
    echo -e "    ./start.sh --mvs        # Web app + Ollama + TK5 mainframe"
  fi
  # Detect server IP for display
  SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
  [ -z "$SERVER_IP" ] && SERVER_IP="0.0.0.0"

  echo ""
  echo -e "  ${CYN}Then open:${RST}"
  echo -e "    http://${SERVER_IP}:8080"
  echo ""
  echo -e "  ${CYN}Default TN3270 login:${RST}"
  echo -e "    Host: ${SERVER_IP}:3270"
  echo -e "    User: HERC01  Pass: CUL8TR"
  echo ""
}

# ── Banner ────────────────────────────────────────────────
banner() {
  echo ""
  echo -e "${CYN}╔══════════════════════════════════════════════════════════╗${RST}"
  echo -e "${CYN}║     Mainframe AI Assistant — Linux Installer            ║${RST}"
  echo -e "${CYN}╠══════════════════════════════════════════════════════════╣${RST}"
  echo -e "${CYN}║  Components:                                            ║${RST}"
  echo -e "${CYN}║    • Python 3.11+ virtual environment                   ║${RST}"
  echo -e "${CYN}║    • Ollama (local LLM backend)                         ║${RST}"
  echo -e "${CYN}║    • llama3.1:8b model (~4.7 GB)                        ║${RST}"
  echo -e "${CYN}║    • FastAPI web application                            ║${RST}"
  echo -e "${CYN}║    • TK5 MVS mainframe emulator (optional)              ║${RST}"
  echo -e "${CYN}╠══════════════════════════════════════════════════════════╣${RST}"
  echo -e "${CYN}║  100% local. No API keys. No cloud.                     ║${RST}"
  echo -e "${CYN}╚══════════════════════════════════════════════════════════╝${RST}"
  echo ""
}

# ── Main ──────────────────────────────────────────────────
banner
check_root
detect_distro
detect_gpu
install_system_deps
install_gpu_deps
check_python
install_ollama
setup_gh_auth
setup_repo
setup_venv
install_tk5
verify
