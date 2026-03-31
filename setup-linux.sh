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
  git-lfs \
  2>/dev/null
git lfs install --skip-smudge 2>/dev/null || true
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
DASD_BACKUP="$TK5/dasd_backup"

# Check if real DASD already present (not LFS pointers)
_dasd_real() {
  local f
  for f in "$TK5/dasd/"*.390 "$TK5/dasd/"*.392; do
    [ -f "$f" ] && [ "$(wc -c < "$f" 2>/dev/null)" -gt 1048576 ] && return 0
  done
  return 1
}

if _dasd_real; then
  ok "DASD already present (real images)"
else
  info "Fetching DASD via git LFS (public repo, ~200 MB)..."
  git lfs pull 2>&1 | tail -3
  if _dasd_real; then
    ok "DASD fetched via git LFS"
  else
    fail "git lfs pull did not produce real DASD files"
    info "Try manually: git lfs install && git lfs pull"
    exit 1
  fi
fi

# Seed dasd_backup/ from live dasd/
mkdir -p "$TK5/dasd_backup"
for ext in 190 191 248 249 290 291 292 293 350 380 390 391 392 393; do
  cp -f "$TK5"/dasd/*.${ext} "$TK5/dasd_backup/" 2>/dev/null || true
done
ok "dasd_backup/ seeded from dasd/"

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
