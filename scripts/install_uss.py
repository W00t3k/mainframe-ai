#!/usr/bin/env python3
"""
Install IBM AI USS Logon Screen on live MVS TK5

Submits jcl/IBMAI.jcl via the web app terminal API:
  1. Ensures connected to localhost:3270
  2. Logs in as IBMUSER / SYS1
  3. Submits the JCL via TSO SUBMIT
  4. Activates the new USS table via Hercules console command

Usage:
  python3 scripts/install_uss.py
"""

import sys
import time
import requests
from pathlib import Path

BASE_URL = "http://localhost:8080"
JCL_PATH = Path(__file__).parent.parent / "jcl" / "IBMAI.jcl"

# IBMUSER has authority to write USER.VTAMLIB
TSO_USER = "IBMUSER"
TSO_PASS = "SYS1"


def send_string(text):
    r = requests.post(f"{BASE_URL}/api/terminal/key",
                      json={"key_type": "string", "value": text}, timeout=10)
    return r.json().get("success", False)


def send_enter():
    r = requests.post(f"{BASE_URL}/api/terminal/key",
                      json={"key_type": "enter", "value": ""}, timeout=10)
    return r.json().get("success", False)


def send_pf(n):
    r = requests.post(f"{BASE_URL}/api/terminal/key",
                      json={"key_type": "pf", "value": str(n)}, timeout=10)
    return r.json().get("success", False)


def send_clear():
    r = requests.post(f"{BASE_URL}/api/terminal/key",
                      json={"key_type": "clear", "value": ""}, timeout=10)
    return r.json().get("success", False)


def get_screen():
    try:
        r = requests.get(f"{BASE_URL}/api/terminal/screen", timeout=10)
        data = r.json()
        return data.get("screen", "")
    except Exception:
        return ""


def wait_for(text, timeout=60, interval=1):
    start = time.time()
    while time.time() - start < timeout:
        if text.upper() in get_screen().upper():
            return True
        time.sleep(interval)
    return False


def cmd(text, delay=1.5):
    send_string(text)
    time.sleep(0.3)
    send_enter()
    time.sleep(delay)


def ensure_connected():
    print("[*] Checking connection to localhost:3270...")
    screen = get_screen()
    if not screen or len(screen.strip()) < 5:
        print("[*] Not connected — connecting now...")
        r = requests.post(f"{BASE_URL}/api/terminal/connect",
                          json={"target": "localhost:3270"}, timeout=90)
        data = r.json()
        if not data.get("success"):
            print(f"[!] Connect failed: {data.get('message')}")
            return False
        print(f"[+] Connected: {data.get('message')}")
    else:
        print("[+] Already connected")
    return True


def ensure_tso_ready():
    """Get to TSO READY prompt as IBMUSER."""
    screen = get_screen()

    # At VTAM USS screen — type logon
    if "LOGON" in screen.upper() or "COMMAND" in screen.upper():
        print(f"[*] At VTAM screen — logging in as {TSO_USER}...")
        cmd(f"LOGON {TSO_USER}", delay=2)
        screen = get_screen()

    # Password prompt
    if "PASSWORD" in screen.upper() or "ENTER" in screen.upper():
        print("[*] Sending password...")
        cmd(TSO_PASS, delay=3)

    # Press through BROADCAST / ICH messages
    for _ in range(6):
        screen = get_screen()
        if "READY" in screen.upper():
            break
        send_enter()
        time.sleep(1)

    # Exit ISPF if we landed there
    screen = get_screen()
    if "ISPF" in screen.upper() or "OPTION ===>" in screen.upper():
        print("[*] Exiting ISPF...")
        send_pf(3)
        time.sleep(1)
        send_pf(3)
        time.sleep(1)

    if wait_for("READY", timeout=15):
        print("[+] At TSO READY prompt")
        return True

    print(f"[!] Could not reach READY. Screen:\n{get_screen()[:400]}")
    return False


def submit_jcl():
    """Read IBMAI.jcl and submit it line-by-line via TSO EDIT."""
    print(f"[*] Reading {JCL_PATH}...")
    if not JCL_PATH.exists():
        print(f"[!] JCL file not found: {JCL_PATH}")
        return False

    lines = JCL_PATH.read_text().splitlines()
    # Strip blank lines at end
    while lines and not lines[-1].strip():
        lines.pop()

    print(f"[*] JCL has {len(lines)} lines")

    # Delete any previous attempt
    ds = "IBMUSER.IBMAI.JCL"
    print(f"[*] Deleting old dataset '{ds}' if it exists...")
    cmd(f"DELETE '{ds}'", delay=2)

    # Allocate new sequential dataset
    print(f"[*] Allocating '{ds}'...")
    cmd(
        f"ALLOC DA('{ds}') NEW CATALOG RECFM(F,B) LRECL(80) "
        f"BLKSIZE(3120) SPACE(5,5) TRACKS",
        delay=2
    )

    # Open EDIT
    print(f"[*] Opening EDIT session for '{ds}'...")
    cmd(f"EDIT '{ds}' DATA NONUM", delay=2)

    screen = get_screen()
    if "EDIT" not in screen.upper() and "INPUT" not in screen.upper() and "EMPTY" not in screen.upper():
        print(f"[!] Did not enter EDIT mode. Screen:\n{screen[:400]}")
        return False

    print("[*] Entering JCL lines (this may take a minute)...")
    for i, line in enumerate(lines, 1):
        # Truncate to 80 chars, pad to avoid issues
        safe = line[:80]
        send_string(safe)
        send_enter()
        time.sleep(0.15)
        if i % 20 == 0:
            print(f"    ... {i}/{len(lines)} lines entered")

    # Save and exit
    print("[*] Saving dataset...")
    cmd("SAVE", delay=2)
    cmd("END", delay=2)

    # Submit
    print(f"[*] Submitting '{ds}'...")
    cmd(f"SUBMIT '{ds}'", delay=3)

    screen = get_screen()
    if "SUBMITTED" in screen.upper() or "JOB" in screen.upper():
        print("[+] JCL submitted successfully!")
        # Extract job number if visible
        for word in screen.split():
            if word.startswith("JOB") and len(word) > 3:
                print(f"[+] Job ID: {word}")
                break
        return True
    else:
        print(f"[!] Submit may have failed. Screen:\n{screen[:500]}")
        return False


def activate_uss():
    """Send VTAM activate command via Hercules HTTP console."""
    print("[*] Attempting to activate USS table via Hercules console...")
    try:
        # Hercules HTTP console on port 8038
        r = requests.get(
            "http://localhost:8038/cgi-bin/tasks/syslog",
            timeout=5
        )
        print("[*] Hercules console reachable")
    except Exception:
        print("[!] Hercules HTTP console not reachable on 8038 — skipping auto-activate")
        print("    Manually run from Hercules console:  /V NET,ACT,ID=USSN")
        return

    # The VTAM command to activate the new USS table
    # Issue via TSO operator command
    print("[*] Issuing VTAM activate via TSO OPERATOR command...")
    if wait_for("READY", timeout=10):
        cmd("OPERATOR 'V NET,ACT,ID=USSN'", delay=3)
        screen = get_screen()
        print(f"[*] Console response:\n{screen[:300]}")


def main():
    print("=" * 60)
    print("  IBM AI USS Logon Screen Installer")
    print("=" * 60)

    # 1. Connect
    if not ensure_connected():
        sys.exit(1)
    time.sleep(2)

    # 2. Get to TSO READY as IBMUSER
    if not ensure_tso_ready():
        sys.exit(1)

    # 3. Submit JCL
    if not submit_jcl():
        print("[!] JCL submission failed")
        sys.exit(1)

    # 4. Wait for job to complete (assemble + link ~30s)
    print("[*] Waiting up to 90s for job to complete...")
    time.sleep(10)
    if wait_for("READY", timeout=80):
        print("[+] Job completed (back at READY)")
    else:
        print("[!] Timeout waiting for job — check SYSOUT for errors")

    # 5. Activate
    activate_uss()

    print()
    print("=" * 60)
    print("  DONE!")
    print("  The IBM AI USS logon screen should now be active.")
    print("  If not, from the Hercules console run:")
    print("    /V NET,ACT,ID=USSN")
    print("  Or restart VTAM:")
    print("    /P VTAM")
    print("    /S VTAM")
    print("=" * 60)


if __name__ == "__main__":
    main()
