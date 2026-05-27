#!/usr/bin/env python3
"""Full test script for all recon modules."""
import sys
import time
sys.path.insert(0, '/Users/w00tock/MF-local/mainframe-ai/tools')
sys.path.insert(0, '/Users/w00tock/MF-local/mainframe-ai')

from agent_tools import connection, connect_mainframe, read_screen
from recon_engine import (
    TSOEnumerator, CICSEnumerator, VTAMEnumerator, SystemEnumerator,
    _detect_state, _reset_terminal, _go_to_vtam
)

def test_tso():
    """Test TSO userid enumeration."""
    print("\n=== TSO Enumeration ===")
    start = time.time()
    enum = TSOEnumerator(userids=["HERC01", "HERC02", "IBMUSER"])
    results = enum.enumerate()
    print(f"   Took {time.time()-start:.1f}s")
    for r in results:
        print(f"   - {r.get('userid', '?')}: {r['status']} ({r['message']})")
    return results

def test_cics():
    """Test CICS transaction enumeration."""
    print("\n=== CICS Enumeration ===")
    start = time.time()
    enum = CICSEnumerator(transactions=["CEMT", "CEDA", "CESN", "XXXX"])
    results = enum.enumerate()
    print(f"   Took {time.time()-start:.1f}s")
    for r in results:
        print(f"   - {r.get('transaction_id', '?')}: {r['status']} ({r['message']})")
    return results

def test_vtam():
    """Test VTAM APPLID enumeration."""
    print("\n=== VTAM Enumeration ===")
    start = time.time()
    enum = VTAMEnumerator(applids=["TSO", "CICS", "NVAS", "INVALID"])
    results = enum.enumerate()
    print(f"   Took {time.time()-start:.1f}s")
    for r in results:
        print(f"   - {r.get('applid', '?')}: {r['status']} ({r['message']})")
    return results

def test_system():
    """Test System enumeration (most important)."""
    print("\n=== System Enumeration ===")
    print("   Using userid=HERC01, password=CUL8TR")
    start = time.time()
    # Only run a few commands to keep test short
    enum = SystemEnumerator(
        userid="HERC01",
        password="CUL8TR",
        commands=["vers_status", "vers_time", "sec_identity", "path_listalc"]
    )
    results = enum.enumerate()
    print(f"   Took {time.time()-start:.1f}s")
    for r in results:
        findings = r.get('findings', [])
        finding_str = f" [{len(findings)} findings]" if findings else ""
        print(f"   - {r['label']}: {len(r.get('output', ''))} chars{finding_str}")
        if r.get('output', '').startswith('[ERROR]'):
            print(f"     ERROR: {r['output'][:100]}")
    return results

def main():
    print("1. Connecting...")
    success, msg = connect_mainframe("localhost:3270")
    print(f"   Connected: {success}, {msg}")
    if not success:
        return

    print("2. Current state:", _detect_state())

    # Reset to clean state
    print("3. Resetting terminal...")
    _reset_terminal()
    print("   State after reset:", _detect_state())

    # Run all tests
    test_system()
    test_tso()
    test_vtam()

    print("\n=== Done ===")

if __name__ == "__main__":
    main()
