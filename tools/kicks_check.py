#!/usr/bin/env python3
"""
KICKS Status Check — verifies if KICKS is installed and working on TK5.
Run: .venv/bin/python kicks_check.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from py3270 import Emulator

HOST = "localhost"
PORT = 3270
USER = "HERC01"
PASS = "CUL8TR"

def log(icon, msg):
    print(f"  {icon} {msg}")

def get_screen_text(em):
    """Read all 24 rows of the screen."""
    lines = []
    for r in range(1, 25):
        lines.append(em.string_get(r, 1, 80))
    return "\n".join(lines)

def wait_for(em, text, timeout=15, interval=1):
    """Wait for text to appear on screen."""
    for _ in range(int(timeout / interval)):
        screen = get_screen_text(em)
        if text.upper() in screen.upper():
            return True
        time.sleep(interval)
    return False

def main():
    print("\n  KICKS Status Check")
    print("  " + "=" * 40)

    # Connect
    log("…", f"Connecting to {HOST}:{PORT}")
    em = Emulator(visible=False)
    try:
        em.connect(f"{HOST}:{PORT}")
    except Exception as e:
        log("✗", f"Connection failed: {e}")
        log("…", "Is Hercules running? Try: ./start.sh")
        return 1
    time.sleep(2)
    screen = get_screen_text(em)
    upper = screen.upper()
    log("…", f"Initial screen: {screen.strip()[:80]}")

    # Step 1: Get to the VTAM logon prompt
    # TK5 often needs ENTER or CLEAR to wake up VTAM
    for attempt in range(8):
        screen = get_screen_text(em)
        upper = screen.upper()

        # Already at READY — done
        if "READY" in upper:
            break

        # Already in ISPF — exit
        if "ISPF" in upper or "OPTION" in upper or "PRIMARY" in upper:
            log("…", "In ISPF, pressing PF3 to exit...")
            em.send_pf(3)
            time.sleep(1)
            continue

        # At VTAM logon prompt — type TSO
        if "LOGON" in upper and "==>" in screen:
            log("…", "At VTAM logon screen, entering TSO...")
            em.exec_command(b'Clear')
            time.sleep(0.5)
            em.send_string("TSO")
            em.send_enter()
            time.sleep(3)
            continue

        # At TSO userid panel
        if "ENTER USERID" in upper or "TSO/E LOGON" in upper:
            log("…", f"Logging in as {USER}...")
            em.send_string(USER)
            em.send_enter()
            time.sleep(2)
            screen = get_screen_text(em)
            if "PASSWORD" in screen.upper():
                em.send_string(PASS)
                em.send_enter()
                time.sleep(3)
            continue

        # INPUT NOT RECOGNIZED or other error — clear and retry
        if "INPUT NOT RECOGNIZED" in upper or "INVALID" in upper:
            log("…", "Clearing error, retrying...")
            em.exec_command(b'Clear')
            time.sleep(2)
            continue

        # Blank or unknown screen — press ENTER to wake VTAM
        log("…", f"Unknown screen (attempt {attempt+1}), pressing ENTER...")
        em.send_enter()
        time.sleep(2)

    screen = get_screen_text(em)
    if "READY" not in screen.upper():
        log("✗", "Could not reach TSO READY prompt")
        print("\n  Current screen:")
        for line in screen.split("\n"):
            stripped = line.rstrip()
            if stripped:
                print(f"    {stripped}")
        em.terminate()
        return 1

    log("✓", "At TSO READY prompt")

    # Check 1: KICKS catalog alias
    print()
    log("…", "Checking KICKS catalog alias...")
    em.send_string("LISTCAT ENT(KICKS) ALL")
    em.send_enter()
    time.sleep(3)
    screen = get_screen_text(em)

    if "ALIAS" in screen.upper() and "KICKS" in screen:
        log("✓", "KICKS catalog alias exists")
    elif "NOT FOUND" in screen.upper() or "NOT DEFINED" in screen.upper():
        log("✗", "KICKS catalog alias NOT found")
        log("…", "KICKS needs full installation — see docs/KICKS_INSTALLATION.md")
        em.send_enter()
        em.terminate()
        return 2
    else:
        log("?", "Unclear catalog status")
        for line in screen.split("\n"):
            line = line.strip()
            if line:
                print(f"    {line}")

    # Press through any "MORE" output
    for _ in range(3):
        screen = get_screen_text(em)
        if "READY" in screen:
            break
        em.send_enter()
        time.sleep(1)

    # Check 2: KICKS CLIST exists
    print()
    log("…", "Checking KICKS CLIST dataset...")
    em.send_string("LISTDS 'KICKS.KICKSSYS.V1R5M0.CLIST'")
    em.send_enter()
    time.sleep(3)
    screen = get_screen_text(em)

    if "NOT IN CATALOG" in screen.upper() or "NOT FOUND" in screen.upper():
        log("✗", "KICKS CLIST dataset NOT found")
        log("…", "KICKS datasets need to be unpacked from XMIT file")
        log("…", "See docs/KICKS_INSTALLATION.md Steps 4-5")
        em.send_enter()
        em.terminate()
        return 3
    elif "KICKS.KICKSSYS" in screen:
        log("✓", "KICKS CLIST dataset exists")
    else:
        log("?", "Could not verify CLIST dataset")

    for _ in range(3):
        screen = get_screen_text(em)
        if "READY" in screen:
            break
        em.send_enter()
        time.sleep(1)

    # Check 3: KICKS load modules
    print()
    log("…", "Checking KICKS load library...")
    em.send_string("LISTDS 'KICKS.KICKSSYS.V1R5M0.SKIKLOAD'")
    em.send_enter()
    time.sleep(3)
    screen = get_screen_text(em)

    if "NOT IN CATALOG" in screen.upper() or "NOT FOUND" in screen.upper():
        log("✗", "KICKS load library NOT found")
    elif "KICKS.KICKSSYS" in screen:
        log("✓", "KICKS load library exists")
    else:
        log("?", "Could not verify load library")

    for _ in range(3):
        screen = get_screen_text(em)
        if "READY" in screen:
            break
        em.send_enter()
        time.sleep(1)

    # Check 4: KICKS COBOL source (demo programs)
    print()
    log("…", "Checking KICKS demo programs...")
    em.send_string("LISTDS 'KICKS.KICKS.V1R5M0.COB'")
    em.send_enter()
    time.sleep(3)
    screen = get_screen_text(em)

    if "NOT IN CATALOG" in screen.upper() or "NOT FOUND" in screen.upper():
        log("✗", "KICKS COBOL source NOT found")
    elif "KICKS.KICKS" in screen:
        log("✓", "KICKS COBOL demo source exists")

    for _ in range(3):
        screen = get_screen_text(em)
        if "READY" in screen:
            break
        em.send_enter()
        time.sleep(1)

    # Check 5: Try to start KICKS
    print()
    log("…", "Attempting to start KICKS...")
    em.send_string("EXEC 'KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)'")
    em.send_enter()
    time.sleep(5)
    screen = get_screen_text(em)

    if "KICKS" in screen and ("BANNER" in screen.upper() or "V1R5" in screen or "TRANSACTION" in screen.upper() or "K I C K S" in screen):
        log("✓", "KICKS started successfully!")
        log("✓", "KICKS is fully installed and working!")
        # Shut down KICKS cleanly
        em.exec_command(b'Clear')
        time.sleep(1)
        em.send_string("KSSF")
        em.send_enter()
        time.sleep(3)
        log("✓", "KICKS shut down")
        result = 0
    elif "ERROR" in screen.upper() or "NOT FOUND" in screen.upper() or "INVALID" in screen.upper():
        log("✗", "KICKS failed to start")
        print("\n  Screen output:")
        for line in screen.split("\n"):
            line = line.strip()
            if line:
                print(f"    {line}")
        result = 4
    else:
        log("?", "KICKS may be starting — check screen:")
        for line in screen.split("\n"):
            line = line.strip()
            if line:
                print(f"    {line}")
        # Try pressing enter to see if banner appears
        em.send_enter()
        time.sleep(3)
        screen = get_screen_text(em)
        if "KICKS" in screen or "K I C K S" in screen:
            log("✓", "KICKS banner appeared!")
            em.exec_command(b'Clear')
            time.sleep(1)
            em.send_string("KSSF")
            em.send_enter()
            time.sleep(3)
            result = 0
        else:
            result = 4

    # Summary
    print()
    print("  " + "=" * 40)
    if result == 0:
        log("✓", "KICKS is installed and working!")
        print()
        print("  To use KICKS:")
        print("    1. Log into TSO (HERC01 / CUL8TR)")
        print("    2. At READY: EXEC 'KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)'")
        print("    3. Press ENTER for banner, CLEAR then type transaction ID")
        print("    4. To quit: CLEAR, type KSSF, press ENTER")
        print()
        print("  Demo transactions: KSGM, INQ1, MNT1, ORD1, ACCT")
    else:
        log("✗", "KICKS needs setup")
        print("    See: docs/KICKS_INSTALLATION.md")

    # Clean up — log off the test session
    try:
        em.send_pf(3)
        time.sleep(1)
        em.send_string("LOGOFF")
        em.send_enter()
        time.sleep(1)
    except:
        pass
    em.terminate()

    print()
    return result


if __name__ == "__main__":
    sys.exit(main())
