#!/bin/bash
# Free a stuck HERC01 (or any) TSO session via the Hercules integrated console.
# Usage: ./scripts/free_herc01.sh [USERID]   (default HERC01)
# Requires the Hercules HTTP console (HTTP PORT 8038 in tk5.cnf) to be up.
set -euo pipefail
USERID="${1:-HERC01}"
HERC_HTTP="http://127.0.0.1:8038/cgi-bin/tasks/syslog"
HARDCOPY="$(cd "$(dirname "$0")/.." && pwd)/tk5/mvs-tk5/log/hardcopy.log"

send() {
  python3 - "$1" <<'PY'
import sys, urllib.parse, urllib.request
data = urllib.parse.urlencode({'command': sys.argv[1], 'norefresh': '1'}).encode()
req = urllib.request.Request("http://127.0.0.1:8038/cgi-bin/tasks/syslog", data=data, method='POST')
urllib.request.urlopen(req, timeout=10).read()
PY
}

active() { tail -12 "$HARDCOPY" 2>/dev/null | grep -q "$USERID  S"; }

echo "Checking $USERID ..."
send "/D A,L"; sleep 2
if ! active; then echo "$USERID not active — nothing to do."; exit 0; fi

echo "$USERID stuck — issuing CANCEL"
send "/C U=$USERID"; sleep 8
send "/D A,L"; sleep 2
if active; then
  echo "Still active — issuing FORCE"
  send "/FORCE U=$USERID"; sleep 8
  send "/D A,L"; sleep 2
fi
if active; then echo "WARNING: $USERID still active"; exit 1; fi
echo "$USERID freed."
