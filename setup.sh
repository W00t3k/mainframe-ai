#!/bin/bash
# ─────────────────────────────────────────────────────────
#  Mainframe AI Assistant — Setup Script
#
#  Detects OS/arch, downloads TK5 (DASD + Hercules binaries),
#  installs dependencies, creates Python venv, and prepares
#  everything for start.sh
#
#  Usage: bash setup.sh
# ─────────────────────────────────────────────────────────

set +e

DIR="$(cd "$(dirname "$0")" && pwd)"
TK5="$DIR/tk5/mvs-tk5"

RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[0;33m'
CYN='\033[0;36m'; BLD='\033[1m'; RST='\033[0m'

ok()   { echo -e "  ${GRN}✓${RST} $1"; }
fail() { echo -e "  ${RED}✗${RST} $1"; }
info() { echo -e "  ${YEL}…${RST} $1"; }

TK5_RELEASE_URL="https://github.com/W00t3k/mainframe-ai/releases/download/v1.0-tk5/tk5-files.tar.gz"

echo ""
echo -e "${CYN}${BLD}═══════════════════════════════════════════════════════${RST}"
echo -e "${CYN}${BLD}  Mainframe AI Assistant — Setup${RST}"
echo -e "${CYN}${BLD}═══════════════════════════════════════════════════════${RST}"

# ── Detect OS / Arch ──────────────────────────────────
echo -e "\n${BLD}[1/6] System Detection${RST}"

OS=$(uname -s)
ARCH=$(uname -m)
ok "OS: $OS / $ARCH"

HERC_OS=""
case "$OS" in
  Darwin) HERC_OS="darwin" ;;
  Linux)
    case "$ARCH" in
      x86_64)  HERC_OS="linux/64" ;;
      aarch64) HERC_OS="linux/aarch64" ;;
      armv7*)  HERC_OS="linux/arm" ;;
      i686)    HERC_OS="linux/32" ;;
      *)       HERC_OS="linux/64" ;;
    esac ;;
  *)
    fail "Unsupported OS: $OS"
    exit 1 ;;
esac
ok "Hercules platform: $HERC_OS"

# ── Install System Dependencies ───────────────────────
echo -e "\n${BLD}[2/6] System Dependencies${RST}"

install_pkg() {
  local pkg="$1"
  if command -v "$pkg" &>/dev/null; then
    ok "$pkg already installed"
    return 0
  fi

  info "Installing $pkg..."
  if command -v apt-get &>/dev/null; then
    sudo apt-get update -qq && sudo apt-get install -y -qq "$pkg" 2>/dev/null
  elif command -v yum &>/dev/null; then
    sudo yum install -y -q "$pkg" 2>/dev/null
  elif command -v brew &>/dev/null; then
    brew install "$pkg" 2>/dev/null
  else
    fail "Cannot install $pkg — no package manager found"
    return 1
  fi

  command -v "$pkg" &>/dev/null && ok "$pkg installed" || fail "$pkg install failed"
}

# s3270 — needed for terminal emulation
if command -v s3270 &>/dev/null; then
  ok "s3270 already installed"
else
  info "Installing s3270 (3270 terminal emulator)..."
  if command -v apt-get &>/dev/null; then
    sudo apt-get update -qq && sudo apt-get install -y -qq x3270 2>/dev/null || sudo apt-get install -y -qq s3270 2>/dev/null
  elif command -v yum &>/dev/null; then
    sudo yum install -y -q x3270-text 2>/dev/null
  elif command -v brew &>/dev/null; then
    brew install x3270 2>/dev/null
  fi
  command -v s3270 &>/dev/null && ok "s3270 installed" || fail "s3270 not found — install x3270 package manually"
fi

# python3
if command -v python3 &>/dev/null; then
  ok "python3 $(python3 --version 2>&1 | awk '{print $2}')"
else
  install_pkg python3
fi

# python3-venv (needed on Debian/Ubuntu)
if [ "$OS" = "Linux" ] && command -v apt-get &>/dev/null; then
  if ! python3 -m venv --help &>/dev/null 2>&1; then
    info "Installing python3-venv..."
    sudo apt-get install -y -qq python3-venv 2>/dev/null && ok "python3-venv installed"
  fi
fi

# ── Download TK5 Files (DASD + Hercules) ──────────────
echo -e "\n${BLD}[3/6] Downloading DASD + Hercules (~305MB)${RST}"

info "Downloading TK5 files from GitHub release..."
rm -f /tmp/tk5-files.tar.gz
gh release download v1.0-tk5 -R W00t3k/mainframe-ai -p "tk5-files.tar.gz" -D /tmp

if [ -f /tmp/tk5-files.tar.gz ]; then
  info "Extracting..."
  tar xzf /tmp/tk5-files.tar.gz -C "$TK5/" 2>/dev/null
  mkdir -p "$DIR/.cache"
  mv /tmp/tk5-files.tar.gz "$DIR/.cache/tk5-files.tar.gz"
  chmod -R +x "$TK5/hercules/" 2>/dev/null
  ok "DASD + Hercules downloaded"
else
  fail "Download failed — run: gh auth login"
  exit 1
fi

# ── Validate DASD Files ───────────────────────────────
echo -e "\n${BLD}[4/6] DASD Validation${RST}"

DASD_OK=1
for vol in tk5res.390 tk5cat.391 tk5dlb.392 tk5001.298 tk5002.299 kicks0.350 int001.380 page00.248 spool0.249 tso001.190 tso002.191 tso003.192 work01.290 work02.291 work03.292 work04.293; do
  f="$TK5/dasd/$vol"
  if [ ! -f "$f" ]; then
    fail "Missing: $vol"
    DASD_OK=0
  else
    sz=$(wc -c < "$f")
    if [ "$sz" -lt 1000 ]; then
      fail "$vol: ${sz} bytes — Git LFS pointer, not real file"
      DASD_OK=0
    else
      if [ "$sz" -ge 1048576 ]; then
        ok "$vol: $(( sz / 1024 / 1024 ))MB"
      else
        ok "$vol: $(( sz / 1024 ))KB"
      fi
    fi
  fi
done

if [ "$DASD_OK" = "0" ]; then
  fail "DASD files bad — re-run setup.sh"
  exit 1
fi

# ── Create Python Venv ────────────────────────────────
echo -e "\n${BLD}[5/6] Python Environment${RST}"

if [ -f "$DIR/.venv/bin/python" ]; then
  ok "Virtual environment exists"
else
  info "Creating virtual environment..."
  python3 -m venv "$DIR/.venv"
  ok "Virtual environment created"
fi

if [ -f "$DIR/requirements.txt" ]; then
  info "Installing Python dependencies..."
  "$DIR/.venv/bin/pip" install -q --upgrade pip 2>/dev/null
  "$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt" 2>/dev/null
  ok "Python dependencies installed"
fi

# ── Hercules Binary Check ─────────────────────────────
echo -e "\n${BLD}[6/6] Hercules Binary${RST}"

HERC_BIN="$TK5/hercules/$HERC_OS/bin/hercules"
if [ -f "$HERC_BIN" ]; then
  ok "Hercules binary: $HERC_OS"
  chmod +x "$HERC_BIN" 2>/dev/null
else
  if command -v hercules &>/dev/null; then
    ok "Using system Hercules: $(command -v hercules)"
  else
    fail "Hercules binary not found for $HERC_OS"
    info "Install: apt install hercules (or brew install sdl-hercules on macOS)"
  fi
fi

# ── Summary ───────────────────────────────────────────
echo ""
echo ""
echo -e "${CYN}${BLD}═══════════════════════════════════════════════════════${RST}"
echo -e "${CYN}${BLD}  Setup Complete!${RST}"
echo -e "${CYN}${BLD}═══════════════════════════════════════════════════════${RST}"
echo ""
echo -e "  To start:  ${BLD}./start.sh${RST}"
echo -e "  To stop:   ${BLD}./kill.sh${RST}"
echo -e "  Login:     ${BLD}HERC01${RST} / ${BLD}CUL8TR${RST}"
echo ""
