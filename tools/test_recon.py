#!/usr/bin/env python3
"""Quick test script for recon enumeration."""
import sys
import time
sys.path.insert(0, '/Users/w00tock/MF-local/mainframe-ai/tools')
sys.path.insert(0, '/Users/w00tock/MF-local/mainframe-ai')

from agent_tools import connection, connect_mainframe, read_screen
from recon_engine import (
    _detect_state, _reset_terminal, _ensure_connection,
    _go_to_vtam, _go_to_tso_logon, TSOEnumerator,
    STATE_VTAM_USS, STATE_TSO_LOGON
)

def test():
    print("1. Connecting...")
    success, msg = connect_mainframe("localhost:3270")
    print(f"   Connected: {success}, {msg}")

    if not success:
        return

    print("2. Reading screen...")
    screen = read_screen()
    print(f"   Screen (first 100 chars): {screen[:100]}...")

    print("3. Detecting state...")
    state = _detect_state()
    print(f"   State: {state}")

    print("4. Resetting terminal...")
    start = time.time()
    _reset_terminal()
    print(f"   Reset took {time.time()-start:.1f}s")

    print("5. Ensuring connection...")
    start = time.time()
    ok = _ensure_connection()
    print(f"   Connection ok: {ok}, took {time.time()-start:.1f}s")

    print("6. Going to VTAM...")
    start = time.time()
    ok = _go_to_vtam()
    print(f"   At VTAM: {ok}, took {time.time()-start:.1f}s")

    print("7. Going to TSO logon...")
    start = time.time()
    ok = _go_to_tso_logon()
    print(f"   At TSO logon: {ok}, took {time.time()-start:.1f}s")

    print("8. Running TSO enumeration with 1 user...")
    start = time.time()
    enum = TSOEnumerator(userids=["HERC01"])
    results = enum.enumerate()
    print(f"   Enumeration took {time.time()-start:.1f}s")
    print(f"   Results: {results}")

if __name__ == "__main__":
    test()
