#!/usr/bin/env python3
"""
KICKS Complete Installation Script for MVS 3.8j TK5
Based on Jay Moseley's detailed installation guide (December 2020)

This script automates:
1. ICKDSF volume initialization
2. IDCAMS user catalog creation  
3. RECV370 XMIT upload
4. Unpack installation datasets (V1R5M0)
5. KFIX CLIST customization
6. Test data creation (5 jobs)
7. Fix KICKS CLIST bug (line 145)

Prerequisites:
- TK5 running with KICKS DASD attached at 351
- Hercules commands already run:
    v 351,online
    m 351,vol=(sl,kicks0),use=private
    devinit 01c <path>/kicks-tso-v1r5m0.xmi ebcdic
"""

import os
import sys
import time
import requests
from pathlib import Path

BASE_URL = "http://localhost:8080"
BASE_DIR = Path(__file__).parent.parent
XMIT_FILE = BASE_DIR / "kicks_install" / "kicks-master" / "kicks-tso-v1r5m0" / "kicks-tso-v1r5m0.xmi"

class KicksInstaller:
    def __init__(self):
        self.step = 0
        self.total_steps = 8
        
    def log(self, msg):
        print(f"[Step {self.step}/{self.total_steps}] {msg}")
    
    def send_string(self, text):
        try:
            r = requests.post(f"{BASE_URL}/api/terminal/key", 
                            json={"key_type": "string", "value": text}, timeout=10)
            return r.json().get("success", False)
        except Exception as e:
            print(f"Error sending string: {e}")
            return False
    
    def send_enter(self):
        try:
            r = requests.post(f"{BASE_URL}/api/terminal/key",
                            json={"key_type": "enter", "value": ""}, timeout=10)
            return r.json().get("success", False)
        except:
            return False
    
    def send_pf(self, num):
        try:
            r = requests.post(f"{BASE_URL}/api/terminal/key",
                            json={"key_type": "pf", "value": str(num)}, timeout=10)
            return r.json().get("success", False)
        except:
            return False
    
    def send_clear(self):
        try:
            r = requests.post(f"{BASE_URL}/api/terminal/key",
                            json={"key_type": "clear", "value": ""}, timeout=10)
            return r.json().get("success", False)
        except:
            return False
    
    def get_screen(self):
        try:
            r = requests.get(f"{BASE_URL}/api/terminal/screen", timeout=10)
            data = r.json()
            return data.get("screen", "") if data.get("connected") else ""
        except:
            return ""
    
    def send_cmd(self, cmd, delay=2):
        self.send_string(cmd)
        time.sleep(0.3)
        self.send_enter()
        time.sleep(delay)
        return True
    
    def wait_for(self, text, timeout=60):
        start = time.time()
        while time.time() - start < timeout:
            screen = self.get_screen()
            if text.upper() in screen.upper():
                return True
            time.sleep(1)
        return False
    
    def wait_for_job(self, timeout=120):
        """Wait for job to complete - look for READY prompt."""
        return self.wait_for("READY", timeout)
    
    def check_connected(self):
        try:
            r = requests.get(f"{BASE_URL}/api/status", timeout=5)
            return r.json().get("connected", False)
        except:
            return False
    
    def ensure_tso_ready(self):
        """Get to TSO READY prompt."""
        screen = self.get_screen()
        
        # At VTAM logon?
        if "LOGON" in screen.upper() and "READY" not in screen.upper():
            self.log("Logging into TSO as HERC01...")
            self.send_string("HERC01")
            self.send_enter()
            time.sleep(2)
            self.send_string("CUL8TR")
            self.send_enter()
            time.sleep(3)
            # Press through messages
            for _ in range(5):
                if self.wait_for("READY", 3):
                    break
                self.send_enter()
                time.sleep(1)
        
        # In ISPF?
        screen = self.get_screen()
        if "ISPF" in screen.upper() or "OPTION ==>" in screen.upper():
            self.log("Exiting ISPF...")
            self.send_pf(3)
            time.sleep(1)
            self.send_pf(3)
            time.sleep(1)
        
        return self.wait_for("READY", 10)
    
    def submit_jcl_inline(self, jcl_lines, job_name, wait_time=30):
        """Submit JCL by creating a dataset and submitting it."""
        self.log(f"Submitting {job_name}...")
        
        # Create temp dataset
        ds_name = f"HERC01.{job_name}.JCL"
        self.send_cmd(f"DELETE '{ds_name}'", delay=2)
        self.send_cmd(f"EDIT '{ds_name}' DATA NEW NONUM", delay=2)
        
        screen = self.get_screen()
        if "EDIT" not in screen.upper() and "INPUT" not in screen.upper():
            self.log(f"WARNING: Could not enter EDIT mode for {job_name}")
            self.send_enter()
            time.sleep(1)
            return False
        
        # Input JCL lines
        for line in jcl_lines:
            self.send_string(f"I {line}")
            self.send_enter()
            time.sleep(0.3)
        
        # Save and exit
        self.send_cmd("SAVE", delay=1)
        self.send_cmd("END", delay=1)
        
        # Submit
        self.send_cmd(f"SUBMIT '{ds_name}'", delay=2)
        
        screen = self.get_screen()
        if "SUBMITTED" in screen.upper() or "JOB" in screen.upper():
            self.log(f"✓ {job_name} submitted")
            time.sleep(wait_time)  # Wait for job
            return True
        else:
            self.log(f"WARNING: {job_name} may not have submitted")
            return False
    
    # ========== INSTALLATION STEPS ==========
    
    def step1_check_volume(self):
        """Check if KICKS0 volume is online."""
        self.step = 1
        self.log("Checking if KICKS0 volume is accessible...")
        
        if not self.ensure_tso_ready():
            self.log("ERROR: Cannot get to TSO READY")
            return False
        
        # Try to list the volume
        self.send_cmd("LISTCAT ENT(UCKICKS0) ALL", delay=3)
        screen = self.get_screen()
        
        if "USERCATALOG" in screen.upper() and "UCKICKS0" in screen:
            self.log("✓ KICKS catalog already exists - skipping ICKDSF and IDCAMS")
            return "catalog_exists"
        
        if "NOT IN CATALOG" in screen.upper() or "NOT FOUND" in screen.upper():
            self.log("Catalog does not exist - need to initialize volume")
            return "needs_init"
        
        return "needs_init"
    
    def step2_ickdsf(self):
        """Initialize KICKS0 volume with ICKDSF."""
        self.step = 2
        self.log("Initializing KICKS0 volume with ICKDSF...")
        
        jcl = [
            "//ICKDSF  JOB (1),ICKDSF,CLASS=A,MSGCLASS=X,MSGLEVEL=(1,1)",
            "//ICKDSF EXEC PGM=ICKDSF,REGION=4096K",
            "//SYSPRINT DD SYSOUT=*",
            "//SYSIN DD *",
            "  INIT UNITADDRESS(351) NOVERIFY -",
            "       VOLID(KICKS0) OWNER(HERCULES) -",
            "       VTOC(0,1,30)",
            "/*",
        ]
        
        return self.submit_jcl_inline(jcl, "ICKDSF", wait_time=15)
    
    def step3_idcams(self):
        """Create KICKS user catalog and alias."""
        self.step = 3
        self.log("Creating KICKS user catalog with IDCAMS...")
        
        jcl = [
            "//IDCAMS  JOB (1),IDCAMS,CLASS=A,MSGCLASS=X,MSGLEVEL=(1,1)",
            "//IDCAMS EXEC PGM=IDCAMS,REGION=4096K",
            "//SYSPRINT DD SYSOUT=*",
            "//KICKS0 DD UNIT=3350,VOL=SER=KICKS0,DISP=OLD",
            "//SYSIN DD *",
            "  DEFINE USERCATALOG ( -",
            "      NAME (UCKICKS0) -",
            "      VOLUME (KICKS0) -",
            "      TRACKS (7500 0) -",
            "      FOR (9999) ) -",
            "      DATA (TRACKS (15 5) ) -",
            "      INDEX (TRACKS (15) ) -",
            "      CATALOG (SYS1.VSAM.MASTER.CATALOG/SYSPROG)",
            "  DEFINE ALIAS ( -",
            "      NAME (KICKS) -",
            "      RELATE (UCKICKS0) ) -",
            "      CATALOG (SYS1.VSAM.MASTER.CATALOG/SYSPROG)",
            "/*",
        ]
        
        return self.submit_jcl_inline(jcl, "IDCAMS", wait_time=15)
    
    def step4_recv370(self):
        """Upload KICKS XMIT file via RECV370."""
        self.step = 4
        self.log("Uploading KICKS XMIT via RECV370...")
        self.log(f"XMIT file: {XMIT_FILE}")
        self.log("")
        self.log("*** HERCULES COMMAND REQUIRED ***")
        self.log(f"Run at Hercules console:")
        self.log(f"  devinit 01c {XMIT_FILE} ebcdic")
        self.log("")
        
        input("Press Enter after running Hercules command...")
        
        if not self.ensure_tso_ready():
            return False
        
        jcl = [
            "//RECV370 JOB (1),RECV370,CLASS=A,MSGCLASS=X,MSGLEVEL=(1,1)",
            "//RECV1  EXEC RECV370",
            "//XMITIN DD UNIT=01C,DCB=BLKSIZE=80",
            "//SYSUT2 DD DSN=KICKS.V1R5M0.INSTALL,",
            "//          VOL=SER=KICKS0,UNIT=3350,",
            "//          SPACE=(TRK,(600,,8),RLSE),",
            "//          DISP=(,CATLG)",
        ]
        
        result = self.submit_jcl_inline(jcl, "RECV370", wait_time=60)
        
        # Verify dataset was created
        self.send_cmd("LISTCAT ENT(KICKS.V1R5M0.INSTALL) ALL", delay=3)
        screen = self.get_screen()
        
        if "KICKS.V1R5M0.INSTALL" in screen:
            self.log("✓ KICKS.V1R5M0.INSTALL created successfully")
            return True
        else:
            self.log("WARNING: Could not verify KICKS.V1R5M0.INSTALL")
            return result
    
    def step5_unpack(self):
        """Unpack installation datasets using pre-built V1R5M0 job."""
        self.step = 5
        self.log("Unpacking installation datasets...")
        
        if not self.ensure_tso_ready():
            return False
        
        # Check if datasets already exist
        self.send_cmd("LISTCAT ENT(KICKS.KICKSSYS.V1R5M0.CLIST) ALL", delay=3)
        screen = self.get_screen()
        
        if "KICKS.KICKSSYS" in screen and "NONVSAM" in screen.upper():
            self.log("✓ KICKS datasets already unpacked!")
            return True
        
        # Use pre-built JCL from jcl/kicks/RCVKICK2.jcl
        jcl_file = BASE_DIR / "jcl" / "kicks" / "RCVKICK2.jcl"
        if not jcl_file.exists():
            self.log(f"ERROR: Pre-built JCL not found: {jcl_file}")
            return False
        
        self.log("Uploading pre-built RCVKICK2 job...")
        jcl_lines = jcl_file.read_text().strip().split('\n')
        
        # Submit via inline JCL
        return self.submit_jcl_inline(jcl_lines, "RCVKICK2", wait_time=120)
    
    def step6_kfix(self):
        """Run KFIX CLIST for customization."""
        self.step = 6
        self.log("Running KFIX CLIST for customization...")
        
        if not self.ensure_tso_ready():
            return False
        
        # Set prefix to KICKS
        self.send_cmd("PROFILE PREFIX(KICKS)", delay=1)
        
        # Run KFIX
        self.log("Starting KFIX CLIST - select 'KICKS' as HLQ...")
        self.send_cmd("EXEC 'KICKS.KICKSSYS.V1R5M0.CLIST(KFIX)'", delay=3)
        
        # KFIX shows HLQ options - need to select KICKS
        screen = self.get_screen()
        if "HLQ" in screen.upper() or "PREFIX" in screen.upper():
            self.log("KFIX started - cycling to find KICKS HLQ...")
            # Press enter to cycle through options
            for _ in range(5):
                screen = self.get_screen()
                if "KICKS" in screen and "HERC" not in screen:
                    self.log("Found KICKS HLQ")
                    self.send_string("yes")
                    self.send_enter()
                    time.sleep(2)
                    break
                self.send_enter()
                time.sleep(1)
        
        # Reset prefix
        self.send_cmd("PROFILE NOPREFIX", delay=1)
        
        self.log("✓ KFIX complete")
        return True
    
    def step7_test_data(self):
        """Create test data using pre-built JCL jobs."""
        self.step = 7
        self.log("Creating test data (5 jobs)...")
        
        if not self.ensure_tso_ready():
            return False
        
        # Use pre-built JCL files
        jcl_dir = BASE_DIR / "jcl" / "kicks"
        jobs = ["LOADMUR", "LOADSDB", "LOADTAC", "LODINTRA", "LODTEMP"]
        
        for job_name in jobs:
            jcl_file = jcl_dir / f"{job_name}.jcl"
            if not jcl_file.exists():
                self.log(f"WARNING: {jcl_file} not found, skipping")
                continue
            
            self.log(f"Submitting {job_name}...")
            jcl_lines = jcl_file.read_text().strip().split('\n')
            self.submit_jcl_inline(jcl_lines, job_name, wait_time=15)
        
        self.log("✓ Test data jobs submitted")
        return True
    
    def step8_fix_clist(self):
        """Fix the bug in KICKS CLIST (remove line 145) via ISPF EDIT."""
        self.step = 8
        self.log("Fixing KICKS CLIST bug (line 145)...")
        
        if not self.ensure_tso_ready():
            return False
        
        # Enter ISPF
        self.log("Entering ISPF to edit CLIST...")
        self.send_cmd("ISPF", delay=2)
        
        # Wait for ISPF primary menu
        if not self.wait_for("OPTION", 10):
            self.log("Could not enter ISPF, trying PDF...")
            self.send_cmd("PDF", delay=2)
        
        # Go to EDIT (option 2)
        self.send_cmd("2", delay=2)
        
        # Enter dataset name
        self.send_string("KICKS.KICKSSYS.V1R5M0.CLIST")
        self.send_enter()
        time.sleep(2)
        
        # Select KICKS member
        self.send_string("s KICKS")
        self.send_enter()
        time.sleep(2)
        
        # Delete line 145 (the bad dataset reference)
        # Use LOCATE command to find the line
        self.log("Locating and deleting bad line...")
        self.send_string("L 'KIKID..KICKS.&VER..SKIKLOAD'")
        self.send_enter()
        time.sleep(1)
        
        # Delete the line with D command
        self.send_string("D")
        self.send_enter()
        time.sleep(1)
        
        # Also change TCP(2$) to TCP(1$) for better terminal support
        self.log("Changing TCP(2$) to TCP(1$)...")
        self.send_string("C 'TCP(2$)' 'TCP(1$)' ALL")
        self.send_enter()
        time.sleep(1)
        
        # Save and exit
        self.send_pf(3)  # Save/End
        time.sleep(1)
        self.send_pf(3)  # Exit member list
        time.sleep(1)
        self.send_pf(3)  # Exit EDIT
        time.sleep(1)
        self.send_pf(3)  # Exit ISPF
        time.sleep(1)
        
        self.log("✓ KICKS CLIST fixed")
        return True
    
    def run(self):
        """Run the complete installation."""
        print("=" * 60)
        print("  KICKS Complete Installation for MVS 3.8j TK5")
        print("  Based on Jay Moseley's installation guide")
        print("=" * 60)
        print()
        
        # Check connection
        if not self.check_connected():
            print("ERROR: Not connected to mainframe")
            print("Please connect via web UI first")
            return 1
        
        # Step 1: Check volume
        result = self.step1_check_volume()
        
        if result == "catalog_exists":
            self.log("Catalog exists - checking if datasets are installed...")
            self.send_cmd("LISTCAT ENT(KICKS.KICKSSYS.V1R5M0.CLIST) ALL", delay=3)
            screen = self.get_screen()
            
            if "KICKS.KICKSSYS" in screen:
                self.log("✓ KICKS appears to be already installed!")
                self.log("")
                self.log("To start KICKS:")
                self.log("  EXEC 'KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)'")
                return 0
        
        elif result == "needs_init":
            # Step 2: ICKDSF
            print("\n*** PREREQUISITE CHECK ***")
            print("Before continuing, run these at Hercules console:")
            print("  v 351,online")
            print("  m 351,vol=(sl,kicks0),use=private")
            input("\nPress Enter after running Hercules commands...")
            
            if not self.step2_ickdsf():
                print("ICKDSF may have failed - check job output")
            
            # Step 3: IDCAMS
            if not self.step3_idcams():
                print("IDCAMS may have failed - check job output")
        
        # Step 4: RECV370
        if not self.step4_recv370():
            print("RECV370 failed")
            return 1
        
        # Step 5: Unpack
        if not self.step5_unpack():
            print("Unpack failed")
            return 1
        
        # Step 6: KFIX
        if not self.step6_kfix():
            print("KFIX failed")
        
        # Step 7: Test data
        if not self.step7_test_data():
            print("Test data creation may have failed")
        
        # Step 8: Fix CLIST
        self.step8_fix_clist()
        
        print()
        print("=" * 60)
        print("  KICKS Installation Complete!")
        print("=" * 60)
        print()
        print("To start KICKS:")
        print("  EXEC 'KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)'")
        print()
        print("To sign off KICKS:")
        print("  Press CLEAR, type KSSF, press ENTER")
        print()
        
        return 0


if __name__ == "__main__":
    installer = KicksInstaller()
    sys.exit(installer.run())
