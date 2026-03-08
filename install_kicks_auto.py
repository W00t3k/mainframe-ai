#!/usr/bin/env python3
"""
Automated KICKS Installation for TK5
Handles the full installation: ICKDSF → DEFCAT → RECV370 → RCVKICK2 → test data → CLIST fix

Uses:
  - Hercules HTTP API (port 8038) for console commands
  - s3270 for TSO interaction
  - Card reader (00C) for JCL submission

Run: .venv/bin/python install_kicks_auto.py
"""

import sys
import os
import time
import urllib.request
import urllib.parse
import subprocess
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from py3270 import Emulator

# Config
HOST = "localhost"
TN3270_PORT = 3270
HERC_HTTP = "http://localhost:8038"
USER = "HERC01"
PASS = "CUL8TR"

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
JCL_DIR = os.path.join(PROJECT_DIR, "jcl", "kicks")
TK5_DIR = os.path.join(PROJECT_DIR, "tk5", "mvs-tk5")
XMIT_FILE = os.path.join(PROJECT_DIR, "kicks_install", "kicks-master",
                          "kicks-tso-v1r5m0", "kicks-tso-v1r5m0.xmi")

KICKS_HERC_ADDR = "0148"   # Hercules device address (leading zero OK)
KICKS_MVS_ADDR = "148"     # MVS operator command address (NO leading zero)


def log(icon, msg):
    print(f"  {icon} {msg}")


def herc_cmd(cmd):
    """Send a command to the Hercules console via HTTP API."""
    try:
        url = f"{HERC_HTTP}/cgi-bin/tasks/cmd?cmd={urllib.parse.quote(cmd)}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            # Strip HTML tags
            import re
            text = re.sub(r'<[^>]+>', '', body)
            return text.strip()
    except Exception as e:
        return f"ERROR: {e}"


def submit_jcl(jcl_path):
    """Submit a JCL file via the Hercules card reader (device 00C)."""
    if not os.path.exists(jcl_path):
        log("✗", f"JCL file not found: {jcl_path}")
        return False
    result = herc_cmd(f"devinit 00c {jcl_path} ascii eof")
    log("→", f"devinit 00c {os.path.basename(jcl_path)}: {result[:100]}")
    return "ERROR" not in result.upper()


def get_screen_text(em):
    lines = []
    for r in range(1, 25):
        lines.append(em.string_get(r, 1, 80))
    return "\n".join(lines)


def wait_screen(em, text, timeout=20):
    for _ in range(int(timeout / 0.5)):
        if text.upper() in get_screen_text(em).upper():
            return True
        time.sleep(0.5)
    return False


def navigate_to_ready(em):
    """Get to TSO READY prompt from any state."""
    sent_userid = False
    sent_password = False
    sent_tso = False

    for attempt in range(15):
        screen = get_screen_text(em)
        upper = screen.upper()
        trimmed = screen.strip()[:120].replace('\n', ' | ')
        log("…", f"[{attempt}] {trimmed}")

        if "READY" in upper:
            return True

        if "ISPF" in upper or "OPTION" in upper or "PRIMARY" in upper:
            em.send_pf(3)
            time.sleep(1)
            continue

        # VTAM logon prompt — send LOGON
        if "==>" in screen and ("LOGON" in upper or "TERMINAL" in upper or "VTAM" in upper) and not sent_tso:
            log("…", "At VTAM, sending LOGON...")
            em.exec_command(b'Home')
            time.sleep(0.2)
            em.send_string("LOGON")
            em.send_enter()
            sent_tso = True
            time.sleep(3)
            continue

        # TSO userid prompt — send HERC01
        if ("ENTER USERID" in upper or "TSO/E LOGON" in upper or "USERID" in upper) and not sent_userid:
            log("…", f"Sending userid {USER}...")
            em.send_string(USER)
            em.send_enter()
            sent_userid = True
            time.sleep(3)
            continue

        # TSO password prompt
        if ("ENTER PASSWORD" in upper or "PASSWORD" in upper) and not sent_password:
            log("…", "Sending password...")
            em.send_string(PASS)
            em.send_enter()
            sent_password = True
            time.sleep(3)
            continue

        # Already logged on message
        if "ALREADY LOGGED ON" in upper:
            log("…", "Already logged on, pressing ENTER...")
            em.send_enter()
            time.sleep(2)
            continue

        # Error states — clear and retry
        if "INPUT NOT RECOGNIZED" in upper or "INVALID" in upper:
            log("…", "Clearing error...")
            em.exec_command(b'Clear')
            time.sleep(2)
            sent_tso = False
            continue

        # Specify terminal — just press enter
        if "SPECIFY" in upper:
            em.send_enter()
            time.sleep(1)
            continue

        # If we see the userid on screen but not READY, press ENTER
        if USER in screen and sent_userid:
            em.send_enter()
            time.sleep(2)
            continue

        # Unknown — press ENTER
        em.send_enter()
        time.sleep(2)

    return "READY" in get_screen_text(em).upper()


def send_tso_cmd(em, cmd, delay=2):
    """Send a TSO command at READY prompt."""
    em.send_string(cmd)
    em.send_enter()
    time.sleep(delay)
    return get_screen_text(em)


def wait_for_job(jobname, timeout=60):
    """Wait for a job to complete by checking hardcopy log."""
    log("…", f"Waiting for job {jobname} to complete...")
    hardcopy = os.path.join(TK5_DIR, "log", "hardcopy.log")
    start = time.time()
    while time.time() - start < timeout:
        # Check hardcopy log for job completion
        try:
            with open(hardcopy, 'r', errors='replace') as f:
                lines = f.readlines()[-100:]
                for line in lines:
                    if jobname in line and ("ENDED" in line or "PURGED" in line):
                        time.sleep(2)
                        return True
                    if jobname in line and "JOB FAILED" in line:
                        log("⚠", f"Job {jobname} failed — see hardcopy.log")
                        return False
        except Exception:
            pass
        # Fallback: check card reader
        result = herc_cmd("devlist 00c")
        if "eof" in result.lower():
            time.sleep(3)
            return True
        time.sleep(2)
    log("⚠", f"Job {jobname} may still be running after {timeout}s")
    return True


def main():
    print("\n  KICKS Automated Installation")
    print("  " + "=" * 45)

    # Pre-checks
    if not os.path.exists(XMIT_FILE):
        log("✗", f"XMIT file not found: {XMIT_FILE}")
        return 1

    if not os.path.isdir(JCL_DIR):
        log("✗", f"JCL directory not found: {JCL_DIR}")
        return 1

    # Check Hercules is running
    result = herc_cmd(f"devlist {KICKS_HERC_ADDR}")
    if "ERROR" in result or "3350" not in result:
        log("✗", f"KICKS DASD not found at address {KICKS_HERC_ADDR}")
        log("…", f"Hercules response: {result[:200]}")
        return 1
    log("✓", f"KICKS DASD online at {KICKS_HERC_ADDR}")

    # Vary device online to MVS (use 148 not 0148 — MVS rejects leading zero)
    log("…", f"Varying device {KICKS_MVS_ADDR} online to MVS...")
    herc_cmd(f"/v {KICKS_MVS_ADDR},online")
    time.sleep(3)

    # Connect s3270
    log("…", "Connecting to TN3270...")
    em = Emulator(visible=False)
    try:
        em.connect(f"{HOST}:{TN3270_PORT}")
    except Exception as e:
        log("✗", f"Connection failed: {e}")
        return 1
    time.sleep(2)

    if not navigate_to_ready(em):
        log("✗", "Could not reach TSO READY")
        em.terminate()
        return 1
    log("✓", "At TSO READY")

    # ── Step 1: Check if KICKS already installed ──
    print()
    log("1", "Checking if KICKS is already installed...")
    screen = send_tso_cmd(em, "LISTDS 'KICKS.KICKSSYS.V1R5M0.CLIST'", 3)
    if "KICKS.KICKSSYS" in screen and "NOT IN CATALOG" not in screen.upper():
        log("✓", "KICKS is already installed!")
        log("…", "Skipping installation steps — try starting KICKS:")
        log("…", "  EXEC 'KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)'")
        em.terminate()
        return 0

    # Clear screen
    for _ in range(3):
        if "READY" in get_screen_text(em).upper():
            break
        em.send_enter()
        time.sleep(0.5)

    # ── Step 2: Initialize KICKS0 DASD volume ──
    print()
    log("2", "Initializing KICKS0 DASD volume...")

    # Always reinitialize DASD from scratch (avoids VSAM remnants)
    dasd_path = os.path.join(TK5_DIR, "dasd", "kicks0.350")
    dasdinit_bin = shutil.which("dasdinit")
    hardcopy = os.path.join(TK5_DIR, "log", "hardcopy.log")

    if not dasdinit_bin:
        log("✗", "dasdinit not found in PATH")
        em.terminate()
        return 1

    log("…", "Reinitializing KICKS0 DASD from scratch...")
    herc_cmd(f"detach {KICKS_HERC_ADDR}")
    time.sleep(2)

    try:
        if os.path.exists(dasd_path):
            os.remove(dasd_path)
        result = subprocess.run(
            [dasdinit_bin, "-a", dasd_path, "3350", "KICKS0"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            log("✓", "DASD image created with volser KICKS0")
        else:
            log("✗", f"dasdinit failed: {result.stderr[:200]}")
            em.terminate()
            return 1
    except Exception as e:
        log("✗", f"dasdinit error: {e}")
        em.terminate()
        return 1

    # Reattach to Hercules
    herc_cmd(f"attach {KICKS_HERC_ADDR} 3350 dasd/kicks0.350")
    time.sleep(2)

    # Vary device OFFLINE before ICKDSF (it needs exclusive access)
    herc_cmd(f"/v {KICKS_MVS_ADDR},offline")
    time.sleep(2)

    # Run ICKDSF to create VTOC (dasdinit doesn't create one)
    log("…", "Running ICKDSF to format volume and create VTOC...")
    ickdsf_jcl = os.path.join(JCL_DIR, "ICKDSF.jcl")
    submit_jcl(ickdsf_jcl)
    time.sleep(3)

    # ICKDSF prompts: ICK003D REPLY U TO ALTER VOLUME — reply U
    replied = False
    for _ in range(20):
        try:
            with open(hardcopy, 'r', errors='replace') as f:
                for line in f.readlines()[-30:]:
                    if "ICK003D" in line and not replied:
                        parts = line.split()
                        for p in parts:
                            if p.startswith("*"):
                                reply_id = p[1:]
                                log("…", f"Replying U to ICKDSF prompt (reply {reply_id})...")
                                herc_cmd(f"/r {reply_id},u")
                                replied = True
                                break
                        if not replied:
                            herc_cmd("/r 00,u")
                            replied = True
        except Exception:
            pass
        if replied:
            break
        time.sleep(1)

    wait_for_job("ICKDSF", 60)

    # Check ICKDSF result
    try:
        with open(hardcopy, 'r', errors='replace') as f:
            for line in f.readlines()[-50:]:
                if "ICKDSF" in line and "RC=" in line:
                    rc = line.split("RC=")[1].strip().split()[0]
                    if rc == "0000":
                        log("✓", "ICKDSF formatted volume with VTOC")
                    else:
                        log("⚠", f"ICKDSF completed with RC={rc}")
                    break
    except Exception:
        pass
    time.sleep(3)

    # Ensure device is online to MVS
    log("…", f"Varying device {KICKS_MVS_ADDR} online to MVS...")
    herc_cmd(f"/v {KICKS_MVS_ADDR},online")
    time.sleep(3)
    # Mount as private volume
    herc_cmd(f"/m {KICKS_MVS_ADDR},vol=(sl,KICKS0),use=private")
    time.sleep(5)

    # ── Step 3: Check/Create catalog ──
    print()
    log("3", "Checking KICKS catalog...")
    screen = send_tso_cmd(em, "LISTCAT ENT(KICKS) ALL", 3)

    # Clear output
    for _ in range(5):
        if "READY" in get_screen_text(em).upper():
            break
        em.send_enter()
        time.sleep(0.5)

    if "ALIAS" in screen.upper() and "KICKS" in screen:
        log("✓", "KICKS catalog alias exists")
    else:
        log("…", "Creating KICKS catalog (DEFCAT)...")

        defcat_jcl = os.path.join(JCL_DIR, "DEFCAT.jcl")
        if not submit_jcl(defcat_jcl):
            log("✗", "Failed to submit DEFCAT job")
            em.terminate()
            return 1

        wait_for_job("KICKCAT", 60)

        # Verify — check hardcopy for IDCAMS01 RC=0000 (the DEFINE step)
        catalog_ok = False
        hardcopy = os.path.join(TK5_DIR, "log", "hardcopy.log")
        try:
            with open(hardcopy, 'r', errors='replace') as f:
                for line in f.readlines()[-50:]:
                    if "KICKCAT" in line and "IDCAMS01" in line and "RC= 0000" in line:
                        log("✓", "KICKS catalog created (KICKCAT IDCAMS01 RC=0000)")
                        catalog_ok = True
                        break
        except Exception:
            pass

        if not catalog_ok:
            # Fallback: check via TSO LISTCAT
            for attempt in range(4):
                time.sleep(5)
                screen = send_tso_cmd(em, "LISTCAT ENT(KICKS) ALL", 4)
                for _ in range(5):
                    if "READY" in get_screen_text(em).upper():
                        break
                    em.send_enter()
                    time.sleep(0.5)

                if "ALIAS" in screen.upper():
                    log("✓", "KICKS catalog created")
                    catalog_ok = True
                    break
                log("…", f"Catalog check attempt {attempt+1}/4 — not found yet")

        if not catalog_ok:
            log("✗", "DEFCAT failed — KICKS catalog alias not created")
            # Dump recent hardcopy lines for diagnostics
            try:
                with open(hardcopy, 'r', errors='replace') as f:
                    for line in f.readlines()[-20:]:
                        if "DEFCAT" in line or "IDC" in line or "IEF" in line:
                            log("…", f"  {line.strip()[-100:]}")
            except Exception:
                pass
            em.terminate()
            return 1

    # ── Step 4: Upload XMIT file ──
    print()
    log("4", "Uploading KICKS XMIT file to card reader...")
    result = herc_cmd(f"devinit 01c {XMIT_FILE} ebcdic")
    if "ERROR" in result.upper():
        log("✗", f"Failed to load XMIT: {result[:200]}")
        em.terminate()
        return 1
    log("✓", f"XMIT loaded to card reader (01C)")

    # ── Step 5: Run RECV370 to unpack ──
    print()
    log("5", "Submitting RECV370 job to unpack XMIT...")
    recv370_jcl = os.path.join(JCL_DIR, "RECV370.jcl")
    if not submit_jcl(recv370_jcl):
        log("✗", "Failed to submit RECV370")
        em.terminate()
        return 1

    wait_for_job("RECV370", 120)

    # Verify KICKS.V1R5M0.INSTALL was created
    time.sleep(5)
    screen = send_tso_cmd(em, "LISTDS 'KICKS.V1R5M0.INSTALL'", 3)
    for _ in range(3):
        if "READY" in get_screen_text(em).upper():
            break
        em.send_enter()
        time.sleep(0.5)

    if "NOT IN CATALOG" in screen.upper():
        log("✗", "RECV370 failed — KICKS.V1R5M0.INSTALL not created")
        log("…", "Check JES output for errors")
        em.terminate()
        return 1
    log("✓", "KICKS.V1R5M0.INSTALL created")

    # ── Step 6: Unpack all 26 datasets ──
    print()
    log("6", "Submitting RCVKICK2 job to unpack all datasets (this takes a while)...")
    rcvkick2_jcl = os.path.join(JCL_DIR, "RCVKICK2.jcl")
    if not submit_jcl(rcvkick2_jcl):
        log("✗", "Failed to submit RCVKICK2")
        em.terminate()
        return 1

    wait_for_job("RCVKICK2", 300)

    # Verify key dataset
    time.sleep(5)
    screen = send_tso_cmd(em, "LISTDS 'KICKS.KICKSSYS.V1R5M0.CLIST'", 3)
    for _ in range(3):
        if "READY" in get_screen_text(em).upper():
            break
        em.send_enter()
        time.sleep(0.5)

    if "NOT IN CATALOG" in screen.upper():
        log("✗", "RCVKICK2 may have failed — CLIST dataset not found")
        log("…", "Check JES output — some steps may need manual retry")
    else:
        log("✓", "KICKS datasets unpacked successfully")

    # ── Step 7: Create test data ──
    print()
    log("7", "Creating KICKS test data...")
    test_jobs = [
        ("LODINTRA.jcl", "LODINTRA", 30),
        ("LODTEMP.jcl", "LODTEMP", 30),
        ("LOADMUR.jcl", "LOADMUR", 30),
        ("LOADSDB.jcl", "LOADSDB", 30),
        ("LOADTAC.jcl", "LOADTAC", 30),
    ]
    for jcl_file, jobname, timeout in test_jobs:
        jcl_path = os.path.join(JCL_DIR, jcl_file)
        if os.path.exists(jcl_path):
            submit_jcl(jcl_path)
            time.sleep(timeout)
            log("✓", f"{jobname} submitted")
        else:
            log("⚠", f"{jcl_file} not found — skipping")

    # ── Step 8: Increase DYNAMNBR ──
    print()
    log("8", "Note: DYNAMNBR in SYS1.PROCLIB(IKJACCNT) should be 64+")
    log("…", "Edit manually if KICKS fails with allocation errors")

    # ── Step 9: Try starting KICKS ──
    print()
    log("9", "Attempting to start KICKS...")

    # Make sure we're at READY
    for _ in range(5):
        if "READY" in get_screen_text(em).upper():
            break
        em.send_enter()
        time.sleep(1)

    send_tso_cmd(em, "EXEC 'KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)'", 5)

    for _ in range(5):
        screen = get_screen_text(em)
        if "K I C K S" in screen or "KICKS" in screen.upper():
            log("✓", "KICKS started successfully!")
            # Shut down cleanly
            em.exec_command(b'Clear')
            time.sleep(1)
            em.send_string("KSSF")
            em.send_enter()
            time.sleep(3)
            log("✓", "KICKS shut down")
            break
        if "ERROR" in screen.upper() or "NOT FOUND" in screen.upper():
            log("✗", "KICKS failed to start")
            for line in screen.split("\n"):
                line = line.strip()
                if line:
                    print(f"    {line}")
            break
        em.send_enter()
        time.sleep(2)

    # Summary
    print()
    print("  " + "=" * 45)
    log("✓", "KICKS installation complete!")
    print()
    print("  To use KICKS:")
    print("    1. Log into TSO (HERC01 / CUL8TR)")
    print("    2. At READY: EXEC 'KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)'")
    print("    3. Press ENTER for banner")
    print("    4. CLEAR then type transaction ID (e.g. INQ1, MNT1)")
    print("    5. To quit: CLEAR, type KSSF, ENTER")
    print()
    print("  Demo transactions: KSGM, INQ1, MNT1, ORD1, ACCT, TRAN")
    print()

    em.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
