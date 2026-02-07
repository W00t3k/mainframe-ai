#!/usr/bin/env python3
"""
KICKS Installation Script for TK5
Automates the installation of KICKS (CICS) on MVS 3.8j
"""

import sys
import time
sys.path.insert(0, '/Users/w00tock/Desktop/STuFF /mainframe_ai_assistant')

from agent_tools import (
    connect_mainframe, send_string, send_enter, send_pf,
    read_screen, wait_for_string, exec_emulator_command
)

XMIT_PATH = "/Users/w00tock/Desktop/STuFF /mainframe_ai_assistant/kicks_install/kicks-master/kicks-tso-v1r5m0/kicks-tso-v1r5m0.xmi"

def wait_ready():
    """Wait for keyboard to unlock."""
    time.sleep(0.5)
    try:
        exec_emulator_command(b'Wait(3,Unlock)')
    except:
        pass

def send_cmd(text):
    """Send a command string and enter."""
    wait_ready()
    send_string(text)
    time.sleep(0.3)
    send_enter()
    time.sleep(1)

def check_screen(keyword):
    """Check if screen contains keyword."""
    screen = read_screen()
    return keyword.upper() in screen.upper()

def login():
    """Login to TSO as HERC01."""
    print("Logging in as HERC01...")
    
    # Check if at logon screen
    screen = read_screen()
    if "LOGON" in screen.upper() and "HERC01" not in screen.upper():
        send_string("HERC01")
        send_enter()
        time.sleep(2)
        
        # Password
        send_string("CUL8TR")
        send_enter()
        time.sleep(3)
        
        # Press enter through any messages
        for _ in range(5):
            if check_screen("READY") or check_screen("ISPF"):
                break
            send_enter()
            time.sleep(2)
    
    # Exit ISPF if we're there
    if check_screen("ISPF") or check_screen("OPTION"):
        send_pf(3)
        time.sleep(1)
    
    if check_screen("READY"):
        print("✓ At TSO READY")
        return True
    return False

def submit_ickdsf():
    """Submit ICKDSF job to initialize KICKS0."""
    print("Submitting ICKDSF job...")
    
    # Create and submit inline JCL
    jcl = """//ICKDSF JOB (1),ICKDSF,CLASS=A,MSGCLASS=X
//ICKDSF EXEC PGM=ICKDSF,REGION=4096K
//SYSPRINT DD SYSOUT=*
//SYSIN DD *
  INIT UNITADDRESS(351) VERIFY(111111) -
       VOLID(KICKS0) OWNER(HERCULES) -
       VTOC(0,1,15)
/*
//"""
    
    # Use EDIT to create JCL
    send_cmd("EDIT 'HERC01.KICKS.JCL' DATA NEW")
    time.sleep(2)
    
    if check_screen("EDIT"):
        for line in jcl.strip().split('\n'):
            send_cmd(f"I {line}")
        send_cmd("SAVE")
        send_cmd("END")
        send_cmd("SUBMIT 'HERC01.KICKS.JCL'")
        print("✓ ICKDSF job submitted")
        return True
    return False

def submit_defcat():
    """Submit DEFCAT job to create user catalog."""
    print("Submitting DEFCAT job...")
    
    jcl = """//DEFCAT JOB (1),DEFCAT,CLASS=A,MSGCLASS=X
//IDCAMS EXEC PGM=IDCAMS,REGION=4096K
//SYSPRINT DD SYSOUT=*
//KICKS0 DD UNIT=SYSALLDA,DISP=OLD,VOL=SER=KICKS0
//SYSIN DD *
  DEFINE USERCATALOG ( -
      NAME (UCKICKS0) -
      VOLUME (KICKS0) -
      TRACKS (7500 0) -
      FOR (9999) ) -
      DATA (TRACK (15 5) ) -
      INDEX (TRACKS (15) ) -
      CATALOG (SYS1.VSAM.MASTER.CATALOG/SYSPROG)
  DEFINE ALIAS ( -
      NAME (KICKS) -
      RELATE (UCKICKS0) ) -
      CATALOG (SYS1.VSAM.MASTER.CATALOG/SYSPROG)
/*
//"""
    
    send_cmd("EDIT 'HERC01.DEFCAT.JCL' DATA NEW")
    time.sleep(2)
    
    if check_screen("EDIT"):
        for line in jcl.strip().split('\n'):
            send_cmd(f"I {line}")
        send_cmd("SAVE")
        send_cmd("END")
        send_cmd("SUBMIT 'HERC01.DEFCAT.JCL'")
        print("✓ DEFCAT job submitted")
        return True
    return False

def main():
    print("=" * 50)
    print("KICKS Installation for TK5")
    print("=" * 50)
    
    # Check connection
    screen = read_screen()
    if not screen or len(screen) < 10:
        print("Not connected to mainframe. Connecting...")
        connect_mainframe("localhost:3270")
        time.sleep(2)
    
    # Login
    if not login():
        print("Failed to login")
        return
    
    print("\nKICKS0 DASD should be attached at address 351.")
    print("If not, run these commands at Hercules console:")
    print("  attach 351 3350 dasd/kicks0.350")
    print("  v 351,online")
    print("  m 351,vol=(sl,kicks0),use=private")
    print()
    
    # Show next steps
    print("Next manual steps:")
    print("1. Verify KICKS0 is online: D U,DASD,ONLINE (at MVS console)")
    print("2. Initialize volume with ICKDSF")
    print("3. Define user catalog")
    print("4. Upload XMIT file:")
    print(f"   Hercules: devinit 01c \"{XMIT_PATH}\" ebcdic")
    print("5. Submit RECV370 job")
    print()
    
    current_screen = read_screen()
    print("Current screen:")
    print(current_screen[:500])

if __name__ == "__main__":
    main()
