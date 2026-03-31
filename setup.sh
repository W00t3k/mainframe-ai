#!/bin/bash
# ─────────────────────────────────────────────────────────
#  Mainframe AI Assistant — First-Time Setup
#
#  Works on macOS (Homebrew) and Linux (apt/Ubuntu/Debian).
#  Run once before ./start.sh
#
#  macOS:  ./setup.sh          (no sudo needed)
#  Linux:  sudo ./setup.sh
# ─────────────────────────────────────────────────────────

set +e

DIR="$(cd "$(dirname "$0")" && pwd)"
TK5="$DIR/tk5/mvs-tk5"
DASD_URL="https://github.com/W00t3k/mainframe-ai/releases/download/v1.0-dasd/tk5-dasd.tar.gz"
DASD_TMP="/tmp/tk5-dasd.tar.gz"

RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[0;33m'
CYN='\033[0;36m'; BLD='\033[1m'; RST='\033[0m'

ok()   { echo -e "  ${GRN}✓${RST} $1"; }
fail() { echo -e "  ${RED}✗${RST} $1"; }
info() { echo -e "  ${YEL}…${RST} $1"; }

OS=$(uname -s)
ARCH=$(uname -m)

echo ""
echo -e "${CYN}${BLD}═══════════════════════════════════════════════════════${RST}"
echo -e "${CYN}${BLD}  Mainframe AI Assistant — Setup ($OS/$ARCH)${RST}"
echo -e "${CYN}${BLD}═══════════════════════════════════════════════════════${RST}"

# ── [1/4] System Dependencies ─────────────────────────
echo -e "\n${BLD}[1/4] System Dependencies${RST}"

if [ "$OS" = "Darwin" ]; then
  # macOS — Homebrew
  if ! command -v brew &>/dev/null; then
    fail "Homebrew not found — install from https://brew.sh"
    exit 1
  fi
  for pkg in python3 s3270 hercules; do
    if command -v "$pkg" &>/dev/null; then
      ok "$pkg already installed"
    else
      info "brew install $pkg..."
      brew install "$pkg" 2>/dev/null && ok "$pkg installed" || fail "$pkg install failed"
    fi
  done
elif [ "$OS" = "Linux" ]; then
  # Linux — apt (Ubuntu/Debian)
  if ! command -v apt-get &>/dev/null; then
    fail "apt-get not found — only Ubuntu/Debian supported by this script"
    exit 1
  fi
  if [ "$(id -u)" != "0" ]; then
    fail "Run as root on Linux: sudo ./setup.sh"
    exit 1
  fi
  apt-get update -qq
  apt-get install -y -qq \
    hercules python3 python3-pip python3-venv \
    curl wget s3270 lsof 2>/dev/null
  ok "Packages installed"
else
  fail "Unsupported OS: $OS"
  exit 1
fi

# ── [2/4] Python Virtual Environment ──────────────────
echo -e "\n${BLD}[2/4] Python Environment${RST}"

if [ -f "$DIR/.venv/bin/python" ]; then
  ok "Virtual env already exists"
else
  python3 -m venv "$DIR/.venv"
  ok "Virtual env created at .venv/"
fi

"$DIR/.venv/bin/pip" install -q --upgrade pip
if [ -f "$DIR/requirements.txt" ]; then
  "$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt"
  ok "Python dependencies installed"
fi

# ── [3/4] DASD Images ─────────────────────────────────
echo -e "\n${BLD}[3/4] DASD Images${RST}"

# Check if real DASD files already present (>1MB = real, not LFS pointer)
_dasd_real() {
  local f
  for f in "$TK5/dasd/"*.390 "$TK5/dasd/"*.392; do
    [ -f "$f" ] && [ "$(wc -c < "$f" 2>/dev/null)" -gt 1048576 ] && return 0
  done
  return 1
}

if _dasd_real; then
  ok "DASD already present"
else
  info "Downloading DASD images (~254 MB from public GitHub release)..."
  if command -v curl &>/dev/null; then
    curl -fL "$DASD_URL" -o "$DASD_TMP"
  else
    wget "$DASD_URL" -O "$DASD_TMP"
  fi

  if [ -f "$DASD_TMP" ] && [ -s "$DASD_TMP" ]; then
    mkdir -p "$TK5/dasd" "$TK5/dasd_backup"
    tar xzf "$DASD_TMP" -C "$TK5/dasd_backup/" 2>/dev/null
    cp -f "$TK5/dasd_backup/"* "$TK5/dasd/" 2>/dev/null || true
    rm -f "$DASD_TMP"
    ok "DASD extracted and dasd_backup/ seeded"
  else
    fail "DASD download failed"
    info "URL: $DASD_URL"
    exit 1
  fi
fi

# Seed dasd_backup/ if empty
if [ -d "$TK5/dasd" ] && [ ! "$(ls "$TK5/dasd_backup/" 2>/dev/null)" ]; then
  mkdir -p "$TK5/dasd_backup"
  cp -f "$TK5/dasd/"* "$TK5/dasd_backup/" 2>/dev/null || true
  ok "dasd_backup/ seeded"
fi

# ── [4/4] Hercules + Permissions ──────────────────────
echo -e "\n${BLD}[4/4] Hercules${RST}"

if command -v hercules &>/dev/null; then
  ok "Hercules: $(hercules --version 2>&1 | head -1)"
else
  fail "Hercules not found"
  if [ "$OS" = "Darwin" ]; then
    info "Install: brew install sdl-hercules"
  else
    info "Install: sudo apt install hercules"
  fi
fi

chmod +x "$DIR/start.sh" "$DIR/kill.sh" 2>/dev/null || true
find "$TK5/hercules" -name "hercules" -type f -exec chmod +x {} \; 2>/dev/null || true
ok "Scripts executable"

# ── Done ──────────────────────────────────────────────
echo ""
echo -e "${CYN}${BLD}═══════════════════════════════════════════════════════${RST}"
echo -e "${CYN}${BLD}  Setup Complete!${RST}"
echo -e "${CYN}${BLD}═══════════════════════════════════════════════════════${RST}"
echo ""
echo -e "  Start:  ${BLD}./start.sh${RST}"
echo -e "  Stop:   ${BLD}./kill.sh${RST}"
echo -e "  Login:  ${BLD}HERC01${RST} / ${BLD}CUL8TR${RST}"
echo ""
