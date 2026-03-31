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

RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[0;33m'
CYN='\033[0;36m'; BLD='\033[1m'; RST='\033[0m'

ok()   { echo -e "  ${GRN}✓${RST} $1"; }
fail() { echo -e "  ${RED}✗${RST} $1"; }
info() { echo -e "  ${YEL}…${RST} $1"; }

. "$DIR/scripts/dasd.sh"

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
  for pkg in python3 s3270 hercules git-lfs; do
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
    git git-lfs hercules python3 python3-pip python3-venv \
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

PIP="$DIR/.venv/bin/pip"

requirements_installed() {
  local pkg
  while IFS= read -r pkg; do
    [ -n "$pkg" ] || continue
    "$PIP" show "$pkg" >/dev/null 2>&1 || return 1
  done < <(
    awk '
      {
        sub(/#.*/, "", $0)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", $0)
        if ($0 != "") {
          split($0, parts, /[<>=!~]/)
          print parts[1]
        }
      }
    ' "$DIR/requirements.txt"
  )
  return 0
}

if [ -f "$DIR/requirements.txt" ]; then
  if requirements_installed; then
    ok "Python dependencies already satisfied"
  else
    info "Installing Python dependencies..."
    if "$PIP" install -q --disable-pip-version-check -r "$DIR/requirements.txt"; then
      ok "Python dependencies installed"
    else
      fail "Python dependency install failed"
      info "If offline, rerun setup where PyPI is reachable."
      exit 1
    fi
  fi
fi

# ── [3/4] DASD Images ─────────────────────────────────
echo -e "\n${BLD}[3/4] DASD Images${RST}"

DASD_CACHE="$DIR/.cache/tk5-files.tar.gz"
DASD_ARCHIVE_URL="${DASD_ARCHIVE_URL:-}"

if dasd_has_real_set "$TK5/dasd"; then
  ok "DASD already present in repo"
else
  info "Trying DASD archive fallback..."
  DASD_ARCHIVE_USED="$(
    dasd_restore_from_candidates "$TK5/dasd" "$TK5/dasd_backup" \
      "$DIR/tk5-files.tar.gz" \
      "$DASD_CACHE" \
      "$DIR/tk5-dasd.tar.gz"
  )"
  if [ -n "$DASD_ARCHIVE_USED" ]; then
    ok "DASD restored from archive: $(basename "$DASD_ARCHIVE_USED")"
  elif [ -n "$DASD_ARCHIVE_URL" ] && \
       dasd_download_archive "$DASD_ARCHIVE_URL" "$DASD_CACHE" && \
       dasd_restore_from_archive "$DASD_CACHE" "$TK5/dasd" "$TK5/dasd_backup"; then
    ok "DASD restored from downloaded archive"
  else
    info "Archive fallback unavailable — trying Git LFS..."
    if dasd_sync_from_lfs && dasd_has_real_set "$TK5/dasd"; then
      ok "DASD synced from Git LFS"
    else
      fail "DASD images missing after archive and Git LFS fallback"
      info "Place tk5-files.tar.gz in the repo root or .cache/"
      [ -n "$DASD_ARCHIVE_URL" ] || info "Optional: set DASD_ARCHIVE_URL to a downloadable DASD .tar.gz"
      info "Run: git lfs pull"
      info "Expected: $(dasd_expected_count) configured DASD images in tk5/mvs-tk5/dasd/"
      exit 1
    fi
  fi
fi

# Seed dasd_backup/ if missing or incomplete
if dasd_has_real_set "$TK5/dasd" && ! dasd_has_real_set "$TK5/dasd_backup"; then
  dasd_seed_backup "$TK5/dasd" "$TK5/dasd_backup"
  ok "dasd_backup/ seeded from repo DASD"
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
