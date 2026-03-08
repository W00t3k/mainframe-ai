#!/bin/bash
# Diagnostic script for Mainframe AI Assistant — run on the Linux server
# Usage: bash diagnose.sh

DIR="$(cd "$(dirname "$0")" && pwd)"
TK5="$DIR/tk5/mvs-tk5"

echo "=== System Info ==="
uname -a
echo ""

echo "=== Hercules Binary ==="
HERC_OS=""
case "$(uname -s)-$(uname -m)" in
  Linux-x86_64)  HERC_OS="linux/64" ;;
  Linux-aarch64) HERC_OS="linux/aarch64" ;;
  Darwin-arm64)  HERC_OS="darwin" ;;
  Darwin-x86_64) HERC_OS="darwin" ;;
esac
echo "Expected: $TK5/hercules/$HERC_OS/bin/hercules"
ls -la "$TK5/hercules/$HERC_OS/bin/hercules" 2>&1
file "$TK5/hercules/$HERC_OS/bin/hercules" 2>&1
"$TK5/hercules/$HERC_OS/bin/hercules" --version 2>&1 | head -3
echo ""

echo "=== DASD Files ==="
ls -la "$TK5/dasd/" 2>&1 | head -5
du -sh "$TK5/dasd/" 2>&1
echo "Backup:"
ls -la "$TK5/dasd_backup/" 2>&1 | head -3
du -sh "$TK5/dasd_backup/" 2>&1
echo ""

echo "=== Key Config Files ==="
for f in conf/tk5.cnf scripts/ipl.rc scripts/tk5.rc scripts/SCR101A_default mode; do
  [ -f "$TK5/$f" ] && echo "  OK: $f" || echo "  MISSING: $f"
done
echo ""

echo "=== Processes ==="
pgrep -a hercules 2>/dev/null || echo "hercules: not running"
pgrep -a ollama 2>/dev/null || echo "ollama: not running"
pgrep -af "run.py" 2>/dev/null || echo "webapp: not running"
echo ""

echo "=== Ports ==="
for port in 3270 8038 8080 11434; do
  (echo > /dev/tcp/127.0.0.1/$port) 2>/dev/null && echo "  $port: OPEN" || echo "  $port: CLOSED"
done
echo ""

echo "=== Hardcopy Log (last 30 lines) ==="
tail -30 "$TK5/log/hardcopy.log" 2>/dev/null || echo "(empty or missing)"
echo ""

echo "=== Hercules Log (last 20 lines) ==="
tail -20 "$DIR/logs/hercules.log" 2>/dev/null || echo "(empty or missing)"
echo ""

echo "=== Python ==="
which python3 2>&1
python3 --version 2>&1
[ -f "$DIR/.venv/bin/python" ] && echo "venv: OK" || echo "venv: MISSING"
echo ""

echo "=== s3270 ==="
which s3270 2>&1 || echo "s3270: NOT FOUND — install x3270 package"
echo ""

echo "Done. Copy this output and share it."
