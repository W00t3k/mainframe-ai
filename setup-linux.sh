#!/bin/bash
# ─────────────────────────────────────────────────────────
#  Mainframe AI Assistant — Linux (Ubuntu/Debian) First-Time Setup
#
#  Run once before ./start.sh:
#    chmod +x setup-linux.sh && sudo ./setup-linux.sh
# ─────────────────────────────────────────────────────────

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
TK5="$DIR/tk5/mvs-tk5"

RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[0;33m'
CYN='\033[0;36m'; BLD='\033[1m'; RST='\033[0m'

ok()   { echo -e "  ${GRN}✓${RST} $1"; }
fail() { echo -e "  ${RED}✗${RST} $1"; }
info() { echo -e "  ${YEL}…${RST} $1"; }

echo ""
echo -e "${CYN}${BLD}═══════════════════════════════════════════════════════${RST}"
echo -e "${CYN}${BLD}  Mainframe AI Assistant — Linux Setup${RST}"
echo -e "${CYN}${BLD}═══════════════════════════════════════════════════════${RST}"

# ── Must be run as root (for apt) ──────────────────────
if [ "$(id -u)" != "0" ]; then
  fail "Run as root: sudo ./setup-linux.sh"
  exit 1
fi

# ── Detect distro ──────────────────────────────────────
if ! command -v apt-get &>/dev/null; then
  fail "This script supports Debian/Ubuntu only (apt-get not found)"
  exit 1
fi

# ── Install system dependencies ───────────────────────
echo -e "\n${BLD}[1/4] System packages${RST}"
apt-get update -qq
apt-get install -y -qq \
  hercules \
  python3 python3-pip python3-venv \
  curl wget \
  s3270 \
  lsof \
  2>/dev/null
ok "Packages installed"

# ── Python venv + dependencies ────────────────────────
echo -e "\n${BLD}[2/4] Python environment${RST}"
if [ ! -f "$DIR/.venv/bin/python" ]; then
  python3 -m venv "$DIR/.venv"
  ok "Virtual env created at .venv/"
else
  ok "Virtual env already exists"
fi

"$DIR/.venv/bin/pip" install -q --upgrade pip
if [ -f "$DIR/requirements.txt" ]; then
  "$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt"
  ok "Python dependencies installed"
else
  fail "requirements.txt not found — run: git pull"
fi

# ── Download DASD images ──────────────────────────────
echo -e "\n${BLD}[3/4] DASD images${RST}"
DASD_CACHE="$DIR/.cache/tk5-files.tar.gz"
DASD_BACKUP="$TK5/dasd_backup"
DASD_URL="https://github.com/W00t3k/mainframe-ai/releases/download/v1.0-tk5/tk5-files.tar.gz"

if [ -d "$DASD_BACKUP" ] && [ "$(ls "$DASD_BACKUP"/*.298 2>/dev/null | wc -l)" -gt 0 ]; then
  ok "dasd_backup/ already present — skipping download"
elif [ -f "$DASD_CACHE" ] && [ -s "$DASD_CACHE" ]; then
  ok "DASD cache already present at .cache/tk5-files.tar.gz"
else
  info "Downloading DASD from GitHub (public release, ~65 MB)..."
  mkdir -p "$DIR/.cache"
  if command -v curl &>/dev/null; then
    curl -fL "$DASD_URL" -o "$DASD_CACHE"
  else
    wget "$DASD_URL" -O "$DASD_CACHE"
  fi
  ok "Downloaded to .cache/tk5-files.tar.gz"
fi

# Extract into dasd/ and seed dasd_backup/
if [ -f "$DASD_CACHE" ] && [ -s "$DASD_CACHE" ]; then
  mkdir -p "$TK5/dasd" "$TK5/dasd_backup"
  tar xzf "$DASD_CACHE" -C "$TK5/" dasd/ 2>/dev/null
  cp -f "$TK5"/dasd/*.390 "$TK5/dasd_backup/" 2>/dev/null || true
  cp -f "$TK5"/dasd/*.391 "$TK5/dasd_backup/" 2>/dev/null || true
  cp -f "$TK5"/dasd/*.392 "$TK5/dasd_backup/" 2>/dev/null || true
  cp -f "$TK5"/dasd/*.393 "$TK5/dasd_backup/" 2>/dev/null || true
  cp -f "$TK5"/dasd/*.298 "$TK5/dasd_backup/" 2>/dev/null || true
  ok "DASD extracted and dasd_backup/ seeded"
fi

# ── Permissions ───────────────────────────────────────
echo -e "\n${BLD}[4/4] Permissions${RST}"
chmod +x "$DIR/start.sh" "$DIR/kill.sh" 2>/dev/null || true
find "$TK5/hercules" -name "hercules" -type f -exec chmod +x {} \; 2>/dev/null || true
ok "Scripts marked executable"

# Verify hercules binary
if command -v hercules &>/dev/null; then
  HERC_VER=$(hercules --version 2>&1 | head -1)
  ok "Hercules: $HERC_VER"
else
  fail "Hercules not found after install — check apt output above"
fi

echo ""
echo -e "${GRN}${BLD}Setup complete!${RST}"
echo -e "Now run:  ${BLD}./start.sh${RST}"
echo ""
