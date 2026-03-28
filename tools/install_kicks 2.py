#!/usr/bin/env python3
"""
KICKS Installation Script for TK5
Automates the installation of KICKS (CICS) on MVS 3.8j

Based on Jay Moseley's installation guide (December 2020)

Usage:
    python install_kicks.py [step]
    
Steps:
    status   - Check current installation status
    dasd     - Create and initialize KICKS0 DASD  
    catalog  - Create user catalog UCKICKS0
    upload   - Upload XMIT file (requires Hercules devinit)
    unpack   - Unpack installation datasets
    testdata - Create test VSAM datasets
    fixclist - Fix KICKS CLIST bug
    all      - Run all steps in sequence
"""

import sys
import os
import time
import subprocess
import argparse

# Add project root to path (tools/ is one level below root)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "tools"))

from agent_tools import (
    connect_mainframe, send_terminal_key, read_screen, exec_emulator_command
)

# Paths
XMIT_PATH = f"{PROJECT_ROOT}/tools/kicks_install/kicks-master/kicks-tso-v1r5m0/kicks-tso-v1r5m0.xmi"
JCL_PATH = f"{PROJECT_ROOT}/jcl/kicks"
TK5_PATH = f"{PROJECT_ROOT}/tk5/mvs-tk5"
DASD_PATH = f"{TK5_PATH}/dasd"

# Installation constants
KICKS_VOLUME = "KICKS0"
KICKS_ADDR = "351"
CARD_READER = "01C"
MASTER_CATALOG = "SYS1.VMASTCAT"


class KICKSInstaller:
    """Automated KICKS installation for MVS 3.8j TK5."""
    
    def __init__(self, verbose=True):
        self.verbose = verbose
        self.connected = False
        
    def log(self, msg, level="INFO"):
        """Print log message."""
        if self.verbose:
            prefix = {"INFO": "•", "OK": "✓", "WARN": "⚠", "ERROR": "✗", "CMD": "→"}
            print(f"{prefix.get(level, '•')} {msg}")
    
    def wait_ready(self, timeout=3):
        """Wait for keyboard to unlock."""
        time.sleep(0.3)
        try:
            exec_emulator_command(f'Wait({timeout},Unlock)'.encode())
        except:
            pass
    
    def send_cmd(self, text, delay=1.0):
        """Send a command string and enter."""
        self.wait_ready()
        exec_emulator_command(f'String("{text}")'.encode())
        time.sleep(0.2)
        send_terminal_key('Enter')
        time.sleep(delay)
        return read_screen()
    
    def check_screen(self, *keywords):
        """Check if screen contains any of the keywords."""
        screen = read_screen().upper()
        return any(kw.upper() in screen for kw in keywords)
    
    def ensure_connected(self):
        """Ensure connection to mainframe."""
        if self.connected:
            return True
            
        screen = read_screen()
        if not screen or len(screen) < 10:
            self.log("Connecting to mainframe...")
            try:
                connect_mainframe("localhost:3270")
                time.sleep(2)
                self.connected = True
            except Exception as e:
                self.log(f"Connection failed: {e}", "ERROR")
                return False
        else:
            self.connected = True
        return True
    
    def ensure_tso_ready(self):
        """Ensure we're at TSO READY prompt."""
        if not self.ensure_connected():
            return False
            
        screen = read_screen()
        
        # Already at READY
        if "READY" in screen.upper():
            return True
        
        # At logon screen
        if "LOGON" in screen.upper() or "TSO/E" in screen.upper():
            self.log("Logging in as HERC01...")
            exec_emulator_command(b'String("HERC01")')
            send_terminal_key('Enter')
            time.sleep(2)
            
            screen = read_screen()
            if "PASSWORD" in screen.upper() or "ENTER" in screen.upper():
                exec_emulator_command(b'String("CUL8TR")')
                send_terminal_key('Enter')
                time.sleep(3)
            
            # Press through messages
            for _ in range(5):
                if self.check_screen("READY"):
                    break
                send_terminal_key('Enter')
                time.sleep(1)
        
        # Exit ISPF if needed
        if self.check_screen("ISPF", "OPTION", "PRIMARY"):
            self.log("Exiting ISPF...")
            send_terminal_key('PF3')
            time.sleep(1)
            if self.check_screen("SPECIFY"):
                send_terminal_key('Enter')
                time.sleep(1)
        
        if self.check_screen("READY"):
            self.log("At TSO READY", "OK")
            return True
        
        self.log("Could not reach TSO READY prompt", "ERROR")
        return False
    
    def submit_jcl_file(self, jcl_name, description):
        """Submit a JCL file from the jcl/kicks directory."""
        jcl_file = os.path.join(JCL_PATH, jcl_name)
        
        if not os.path.exists(jcl_file):
            self.log(f"JCL file not found: {jcl_file}", "ERROR")
            return False
        
        self.log(f"Submitting {jcl_name} ({description})...")
        
        # Read JCL content
        with open(jcl_file, 'r') as f:
            jcl_content = f.read()
        
        # Use TSO SUBMIT from dataset or inline
        # For simplicity, we'll create a temp dataset
        dsn = f"HERC01.KICKS.{jcl_name.replace('.jcl', '').upper()}"
        
        # Delete if exists
        self.send_cmd(f"DELETE '{dsn}'", delay=1)
        
        # Allocate and write
        self.send_cmd(f"ALLOC DA('{dsn}') NEW SPACE(1,1) TRACKS RECFM(F,B) LRECL(80) BLKSIZE(3120)", delay=1)
        
        # Use EDIT to write content
        screen = self.send_cmd(f"EDIT '{dsn}' DATA", delay=1)
        
        if "EDIT" in screen.upper():
            for line in jcl_content.strip().split('\n'):
                line = line[:72]  # Truncate to 72 chars
                self.send_cmd(f"I {line}", delay=0.2)
            
            self.send_cmd("SAVE", delay=1)
            self.send_cmd("END", delay=1)
            
            # Submit
            screen = self.send_cmd(f"SUBMIT '{dsn}'", delay=2)
            
            if "SUBMITTED" in screen.upper() or "JOB" in screen.upper():
                self.log(f"{jcl_name} submitted successfully", "OK")
                return True
        
        self.log(f"Failed to submit {jcl_name}", "ERROR")
        return False
    
    # =========================================================================
    # Installation Steps
    # =========================================================================
    
    def step_create_dasd(self):
        """Step 2: Create and initialize KICKS0 DASD volume."""
        self.log("=" * 50)
        self.log("Step 2: Create KICKS0 DASD Volume")
        self.log("=" * 50)
        
        dasd_file = os.path.join(DASD_PATH, "kicks0.350")
        
        # Check if DASD already exists
        if os.path.exists(dasd_file):
            self.log(f"DASD file already exists: {dasd_file}", "WARN")
            response = input("Delete and recreate? [y/N]: ").strip().lower()
            if response != 'y':
                return True
            os.remove(dasd_file)
        
        # Create DASD image
        self.log("Creating 3350 DASD image...")
        try:
            result = subprocess.run(
                ["dasdinit", "-a", dasd_file, "3350", "111111"],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                self.log(f"dasdinit failed: {result.stderr}", "ERROR")
                return False
            self.log("DASD image created", "OK")
        except FileNotFoundError:
            self.log("dasdinit not found - create DASD manually", "ERROR")
            print(f"  Run: dasdinit -a {dasd_file} 3350 111111")
            return False
        
        # Instructions for Hercules
        self.log("")
        self.log("HERCULES CONSOLE COMMANDS:", "CMD")
        print(f"  attach {KICKS_ADDR} 3350 dasd/kicks0.3350")
        print(f"  v {KICKS_ADDR},online")
        print(f"  m {KICKS_ADDR},vol=(sl,{KICKS_VOLUME}),use=private")
        self.log("")
        
        input("Press Enter after running Hercules commands...")
        
        # Initialize with ICKDSF
        if not self.ensure_tso_ready():
            return False
        
        return self.submit_jcl_file("ICKDSF.jcl", "Initialize KICKS0 volume")
    
    def step_create_catalog(self):
        """Step 3: Create user catalog UCKICKS0."""
        self.log("=" * 50)
        self.log("Step 3: Create User Catalog")
        self.log("=" * 50)
        
        if not self.ensure_tso_ready():
            return False
        
        return self.submit_jcl_file("DEFCAT.jcl", "Create UCKICKS0 catalog with KICKS alias")
    
    def step_upload_xmit(self):
        """Step 4: Upload XMIT file via RECV370."""
        self.log("=" * 50)
        self.log("Step 4: Upload XMIT File")
        self.log("=" * 50)
        
        if not os.path.exists(XMIT_PATH):
            self.log(f"XMIT file not found: {XMIT_PATH}", "ERROR")
            return False
        
        self.log(f"XMIT file: {XMIT_PATH}")
        self.log(f"Size: {os.path.getsize(XMIT_PATH):,} bytes")
        self.log("")
        self.log("HERCULES CONSOLE COMMAND:", "CMD")
        print(f'  devinit {CARD_READER} "{XMIT_PATH}" ebcdic')
        self.log("")
        
        input("Press Enter after running devinit command...")
        
        if not self.ensure_tso_ready():
            return False
        
        return self.submit_jcl_file("RECV370.jcl", "Upload and unpack XMIT")
    
    def step_unpack_datasets(self):
        """Step 5: Unpack all 26 embedded XMIT files."""
        self.log("=" * 50)
        self.log("Step 5: Unpack Installation Datasets")
        self.log("=" * 50)
        
        if not self.ensure_tso_ready():
            return False
        
        self.log("This step unpacks 26 KICKS datasets (may take several minutes)...")
        
        return self.submit_jcl_file("RCVKICK2.jcl", "Unpack all embedded XMIT files")
    
    def step_create_testdata(self):
        """Step 8: Create test VSAM datasets."""
        self.log("=" * 50)
        self.log("Step 8: Create Test Data")
        self.log("=" * 50)
        
        if not self.ensure_tso_ready():
            return False
        
        jobs = [
            ("LOADMUR.jcl", "Murach customer file"),
            ("LOADSDB.jcl", "SDB accounts and transactions"),
            ("LOADTAC.jcl", "TAC test data"),
            ("LODINTRA.jcl", "Intrapartition Transient Data"),
            ("LODTEMP.jcl", "Temporary Storage Queues"),
        ]
        
        success = True
        for jcl, desc in jobs:
            if not self.submit_jcl_file(jcl, desc):
                success = False
                self.log(f"Failed: {jcl}", "ERROR")
        
        return success
    
    def step_fix_clist(self):
        """Step 9: Fix KICKS CLIST bug."""
        self.log("=" * 50)
        self.log("Step 9: Fix KICKS CLIST Bug")
        self.log("=" * 50)
        
        self.log("")
        self.log("MANUAL STEP REQUIRED:", "WARN")
        print("  Edit: KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)")
        print("  Around line 145, remove this line:")
        print("    '&KIKID..KICKS.&VER..SKIKLOAD' +")
        print("")
        print("  Optional: Change TCP parameter in line 5:")
        print("    TCP(1$)")
        self.log("")
        
        return True
    
    def step_check_status(self):
        """Check current installation status."""
        self.log("=" * 50)
        self.log("KICKS Installation Status")
        self.log("=" * 50)
        
        # Check DASD file
        dasd_file = os.path.join(DASD_PATH, "kicks0.350")
        if os.path.exists(dasd_file):
            size_mb = os.path.getsize(dasd_file) / (1024 * 1024)
            self.log(f"DASD file: {dasd_file} ({size_mb:.1f} MB)", "OK")
        else:
            self.log(f"DASD file not found: {dasd_file}", "WARN")
        
        # Check XMIT file
        if os.path.exists(XMIT_PATH):
            size_mb = os.path.getsize(XMIT_PATH) / (1024 * 1024)
            self.log(f"XMIT file: {XMIT_PATH} ({size_mb:.1f} MB)", "OK")
        else:
            self.log(f"XMIT file not found", "ERROR")
        
        # Check JCL files
        jcl_files = [
            "ICKDSF.jcl", "DEFCAT.jcl", "RECV370.jcl", "RCVKICK2.jcl",
            "LOADMUR.jcl", "LOADSDB.jcl", "LOADTAC.jcl",
            "LODINTRA.jcl", "LODTEMP.jcl"
        ]
        
        self.log("")
        self.log("JCL Files:")
        for jcl in jcl_files:
            path = os.path.join(JCL_PATH, jcl)
            if os.path.exists(path):
                self.log(f"  {jcl}", "OK")
            else:
                self.log(f"  {jcl} - MISSING", "ERROR")
        
        # Check connection
        self.log("")
        if self.ensure_connected():
            screen = read_screen()
            self.log(f"Mainframe connected", "OK")
            if "READY" in screen.upper():
                self.log("At TSO READY prompt", "OK")
            elif "LOGON" in screen.upper():
                self.log("At logon screen", "INFO")
            else:
                self.log("Unknown screen state", "WARN")
        else:
            self.log("Not connected to mainframe", "WARN")
        
        return True
    
    def run_all(self):
        """Run all installation steps."""
        self.log("=" * 50)
        self.log("KICKS Full Installation")
        self.log("=" * 50)
        
        steps = [
            ("Check Status", self.step_check_status),
            ("Create DASD", self.step_create_dasd),
            ("Create Catalog", self.step_create_catalog),
            ("Upload XMIT", self.step_upload_xmit),
            ("Unpack Datasets", self.step_unpack_datasets),
            ("Create Test Data", self.step_create_testdata),
            ("Fix CLIST", self.step_fix_clist),
        ]
        
        for name, step_func in steps:
            self.log("")
            response = input(f"Run step '{name}'? [Y/n/q]: ").strip().lower()
            if response == 'q':
                self.log("Installation aborted by user")
                return False
            if response == 'n':
                self.log(f"Skipping {name}")
                continue
            
            if not step_func():
                self.log(f"Step '{name}' failed", "ERROR")
                response = input("Continue anyway? [y/N]: ").strip().lower()
                if response != 'y':
                    return False
        
        self.log("")
        self.log("=" * 50)
        self.log("Installation Complete!", "OK")
        self.log("=" * 50)
        self.log("")
        self.log("To start KICKS:")
        print("  EXEC 'KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)'")
        self.log("")
        self.log("To shutdown KICKS:")
        print("  CLEAR, then type KSSF")
        
        return True


def main():
    parser = argparse.ArgumentParser(
        description="KICKS Installation Script for MVS 3.8j TK5",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Steps:
  status    Check current installation status
  dasd      Create and initialize KICKS0 DASD (Step 2)
  catalog   Create user catalog UCKICKS0 (Step 3)
  upload    Upload XMIT file (Step 4)
  unpack    Unpack installation datasets (Step 5)
  testdata  Create test VSAM datasets (Step 8)
  fixclist  Instructions to fix KICKS CLIST (Step 9)
  all       Run all steps interactively
        """
    )
    
    parser.add_argument(
        'step', nargs='?', default='status',
        choices=['status', 'dasd', 'catalog', 'upload', 'unpack', 'testdata', 'fixclist', 'all'],
        help='Installation step to run (default: status)'
    )
    parser.add_argument('-q', '--quiet', action='store_true', help='Reduce output')
    
    args = parser.parse_args()
    
    installer = KICKSInstaller(verbose=not args.quiet)
    
    step_map = {
        'status': installer.step_check_status,
        'dasd': installer.step_create_dasd,
        'catalog': installer.step_create_catalog,
        'upload': installer.step_upload_xmit,
        'unpack': installer.step_unpack_datasets,
        'testdata': installer.step_create_testdata,
        'fixclist': installer.step_fix_clist,
        'all': installer.run_all,
    }
    
    try:
        success = step_map[args.step]()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nAborted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
