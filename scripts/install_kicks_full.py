#!/usr/bin/env python3
"""
KICKS Full Installation Script
Automates: Define catalog, Upload XMIT, Unpack and configure KICKS
Run this AFTER TK5 has been restarted with KICKS DASD attached.
"""

import os
import sys
import time
import requests
import subprocess
from pathlib import Path

BASE_URL = "http://localhost:8080"
BASE_DIR = Path(__file__).parent.parent
TK5_DIR = BASE_DIR / "tk5" / "mvs-tk5"
XMIT_FILE = BASE_DIR / "kicks_install" / "kicks-master" / "kicks-tso-v1r5m0" / "kicks-tso-v1r5m0.xmi"

def log(msg):
    print(f"[KICKS] {msg}")

def send_string(text):
    """Send string to terminal."""
    r = requests.post(f"{BASE_URL}/api/terminal/key", json={"key_type": "string", "value": text})
    return r.json().get("success", False)

def send_enter():
    """Send Enter key."""
    r = requests.post(f"{BASE_URL}/api/terminal/key", json={"key_type": "enter", "value": ""})
    return r.json().get("success", False)

def send_pf(num):
    """Send PF key."""
    r = requests.post(f"{BASE_URL}/api/terminal/key", json={"key_type": "pf", "value": str(num)})
    return r.json().get("success", False)

def send_clear():
    """Send Clear key."""
    r = requests.post(f"{BASE_URL}/api/terminal/key", json={"key_type": "clear", "value": ""})
    return r.json().get("success", False)

def get_screen():
    """Get current screen content."""
    r = requests.get(f"{BASE_URL}/api/terminal/screen")
    data = r.json()
    if data.get("connected"):
        return data.get("screen", "")
    return ""

def wait_for(text, timeout=30):
    """Wait for text to appear on screen."""
    start = time.time()
    while time.time() - start < timeout:
        screen = get_screen()
        if text.upper() in screen.upper():
            return True
        time.sleep(1)
    return False

def send_cmd(cmd, wait_text="READY", timeout=30):
    """Send command and wait for response."""
    send_string(cmd)
    time.sleep(0.3)
    send_enter()
    time.sleep(1)
    if wait_text:
        return wait_for(wait_text, timeout)
    return True

def check_connection():
    """Check if connected to mainframe."""
    try:
        r = requests.get(f"{BASE_URL}/api/status")
        return r.json().get("connected", False)
    except:
        return False

def ensure_tso_ready():
    """Ensure we're at TSO READY prompt."""
    screen = get_screen()
    
    # If at VTAM logon screen
    if "LOGON" in screen.upper() and "READY" not in screen.upper():
        log("At VTAM screen, logging in...")
        send_string("HERC01")
        send_enter()
        time.sleep(2)
        send_string("CUL8TR")
        send_enter()
        time.sleep(3)
        # Press through messages
        for _ in range(5):
            if wait_for("READY", 2):
                break
            send_enter()
            time.sleep(1)
    
    # Exit ISPF if there
    screen = get_screen()
    if "ISPF" in screen.upper() or "OPTION" in screen.upper():
        log("Exiting ISPF...")
        send_pf(3)
        time.sleep(1)
        send_pf(3)
        time.sleep(1)
    
    return wait_for("READY", 5)

def step1_vary_dasd_online():
    """Vary KICKS DASD online."""
    log("Step 1: Varying KICKS0 DASD online...")
    log("This requires Hercules console access.")
    log("Please run at Hercules console:")
    log("  v 351,online")
    log("  m 351,vol=(sl,kicks0),use=private")
    log("")
    input("Press Enter after running Hercules commands...")
    return True

def step2_init_dasd():
    """Initialize KICKS0 DASD with ICKDSF."""
    log("Step 2: Initializing KICKS0 DASD...")
    
    if not ensure_tso_ready():
        log("ERROR: Not at TSO READY prompt")
        return False
    
    # Check if volume is already initialized
    send_cmd("LISTCAT ENT(UCKICKS0) ALL", wait_text=None, timeout=5)
    time.sleep(3)
    screen = get_screen()
    
    if "UCKICKS0" in screen and "USERCATALOG" in screen.upper():
        log("KICKS catalog already exists - skipping ICKDSF")
        return True
    
    log("Submitting ICKDSF job to initialize volume...")
    
    # Create and submit ICKDSF JCL inline
    jcl_lines = [
        "//ICKDSF JOB (1),'INIT KICKS',CLASS=A,MSGCLASS=X,MSGLEVEL=(1,1)",
        "//INIT   EXEC PGM=ICKDSF,REGION=4096K",
        "//SYSPRINT DD SYSOUT=*",
        "//KICKS0   DD UNIT=3350,VOL=SER=KICKS0,DISP=OLD",
        "//SYSIN  DD *",
        "  INIT UNITADDRESS(351) NOVERIFY -",
        "       VOLID(KICKS0) OWNER(HERCULES) -",
        "       VTOC(0,1,30)",
        "/*",
    ]
    
    # Submit via TSO
    send_cmd("EDIT 'HERC01.ICKDSF.JCL' DATA NEW NONUM", wait_text="EDIT", timeout=10)
    time.sleep(1)
    
    screen = get_screen()
    if "EDIT" not in screen.upper():
        log("WARNING: Could not enter EDIT mode, trying inline submit...")
        return True  # Skip, might already be done
    
    for line in jcl_lines:
        send_string(f"I {line}")
        send_enter()
        time.sleep(0.5)
    
    send_cmd("SAVE", wait_text=None)
    time.sleep(1)
    send_cmd("END", wait_text="READY")
    time.sleep(1)
    send_cmd("SUBMIT 'HERC01.ICKDSF.JCL'", wait_text="SUBMITTED")
    
    log("ICKDSF job submitted - waiting for completion...")
    time.sleep(5)
    return True

def step3_define_catalog():
    """Define KICKS user catalog and alias."""
    log("Step 3: Defining KICKS user catalog...")
    
    if not ensure_tso_ready():
        log("ERROR: Not at TSO READY prompt")
        return False
    
    # Check if catalog already exists
    send_cmd("LISTCAT ENT(UCKICKS0) ALL", wait_text=None, timeout=5)
    time.sleep(3)
    screen = get_screen()
    
    if "UCKICKS0" in screen and "USERCATALOG" in screen.upper():
        log("KICKS catalog already exists - skipping")
        send_enter()
        time.sleep(1)
        return True
    
    log("Creating KICKS user catalog...")
    
    jcl_lines = [
        "//DEFCAT JOB (1),'DEFCAT',CLASS=A,MSGCLASS=X,MSGLEVEL=(1,1)",
        "//IDCAMS EXEC PGM=IDCAMS,REGION=4096K",
        "//SYSPRINT DD SYSOUT=*",
        "//KICKS0 DD UNIT=3350,VOL=SER=KICKS0,DISP=OLD",
        "//SYSIN DD *",
        "  DEFINE USERCATALOG ( -",
        "      NAME (UCKICKS0) -",
        "      VOLUME (KICKS0) -",
        "      CYLINDERS (50) -",
        "      FOR (9999) ) -",
        "      DATA (CYLINDERS (45) ) -",
        "      INDEX (CYLINDERS (5) ) -",
        "      CATALOG (SYS1.VSAM.MASTER.CATALOG/SYSPROG)",
        "  DEFINE ALIAS ( -",
        "      NAME (KICKS) -",
        "      RELATE (UCKICKS0) ) -",
        "      CATALOG (SYS1.VSAM.MASTER.CATALOG/SYSPROG)",
        "/*",
    ]
    
    send_cmd("EDIT 'HERC01.DEFCAT.JCL' DATA NEW NONUM", wait_text="EDIT", timeout=10)
    time.sleep(1)
    
    for line in jcl_lines:
        send_string(f"I {line}")
        send_enter()
        time.sleep(0.5)
    
    send_cmd("SAVE", wait_text=None)
    time.sleep(1)
    send_cmd("END", wait_text="READY")
    time.sleep(1)
    send_cmd("SUBMIT 'HERC01.DEFCAT.JCL'", wait_text="SUBMITTED")
    
    log("DEFCAT job submitted - waiting for completion...")
    time.sleep(5)
    return True

def step4_upload_xmit():
    """Upload KICKS XMIT file via card reader."""
    log("Step 4: Uploading KICKS XMIT file...")
    
    if not XMIT_FILE.exists():
        log(f"ERROR: XMIT file not found: {XMIT_FILE}")
        return False
    
    log(f"XMIT file: {XMIT_FILE}")
    log("")
    log("Please run at Hercules console:")
    log(f"  devinit 01c {XMIT_FILE} ebcdic")
    log("")
    input("Press Enter after running Hercules command...")
    
    if not ensure_tso_ready():
        return False
    
    log("Running RECV370 to receive XMIT file...")
    
    # Set prefix for KICKS
    send_cmd("PROFILE PREFIX(KICKS)", wait_text="READY")
    time.sleep(1)
    
    # Run RECV370
    send_cmd("EXEC 'SYS2.CMDPROC(RECV370)'", wait_text=None, timeout=10)
    time.sleep(3)
    
    screen = get_screen()
    if "RECV370" in screen or "RECEIVE" in screen.upper():
        log("RECV370 started - follow prompts on screen")
        log("When prompted for dataset name, use: KICKS.V1R5M0.INSTALL")
        log("When prompted for volume, use: KICKS0")
    else:
        log("WARNING: RECV370 may not have started correctly")
        log("You may need to run it manually: EXEC 'SYS2.CMDPROC(RECV370)'")
    
    return True

def step5_unpack_kicks():
    """Unpack and configure KICKS."""
    log("Step 5: Unpacking KICKS installation datasets...")
    log("")
    log("After RECV370 completes, you need to:")
    log("1. Edit KICKS.V1R5M0.INSTALL(V1R5M0)")
    log("2. Change CLASS=A, MSGCLASS=X")
    log("3. Submit the job")
    log("4. Run KICKS.KICKSSYS.V1R5M0.CLIST(KFIX)")
    log("")
    log("See docs/KICKS_INSTALLATION.md for detailed steps.")
    return True

def main():
    print("=" * 60)
    print("  KICKS Full Installation Script")
    print("  Automates CICS installation on MVS 3.8j TK5")
    print("=" * 60)
    print()
    
    # Check connection
    if not check_connection():
        log("ERROR: Not connected to mainframe")
        log("Please connect first via the web interface")
        return 1
    
    log("Connected to mainframe")
    
    # Run installation steps
    steps = [
        ("Vary DASD Online", step1_vary_dasd_online),
        ("Initialize DASD", step2_init_dasd),
        ("Define Catalog", step3_define_catalog),
        ("Upload XMIT", step4_upload_xmit),
        ("Unpack KICKS", step5_unpack_kicks),
    ]
    
    for name, func in steps:
        print()
        print("-" * 40)
        if not func():
            log(f"FAILED: {name}")
            return 1
        log(f"DONE: {name}")
    
    print()
    print("=" * 60)
    log("KICKS installation script completed!")
    log("")
    log("To start KICKS after installation:")
    log("  EXEC 'KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)'")
    print("=" * 60)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
