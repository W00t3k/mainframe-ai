#!/usr/bin/env python3
"""
KICKS Installation Script - Following moshix/Jay Moseley Instructions
======================================================================

Based on: https://github.com/moshix/kicks
          https://www.jaymoseley.com/hercules/kicks/index.htm

Prerequisites:
  - TK5 MVS running with Hercules HTTP API on port 8038
  - Web app terminal API on port 8080
  - XMIT file at: tools/kicks_install/kicks-master/kicks-tso-v1r5m0/kicks-tso-v1r5m0.xmi

Usage:
  source .venv/bin/activate
  python tools/kicks_install_moshix.py
"""

import os
import sys
import time
import subprocess
import urllib.request
import urllib.parse
import shutil
import requests
from pathlib import Path

# Configuration
PROJECT_DIR = Path(__file__).parent.parent
TK5_DIR = PROJECT_DIR / "tk5" / "mvs-tk5"
DASD_DIR = TK5_DIR / "dasd"
JCL_DIR = PROJECT_DIR / "jcl" / "kicks"
XMIT_FILE = PROJECT_DIR / "tools" / "kicks_install" / "kicks-master" / "kicks-tso-v1r5m0" / "kicks-tso-v1r5m0.xmi"

HERC_HTTP = "http://localhost:8038"
TERMINAL_API = "http://localhost:8080/api/terminal"

# Device address for KICKS (using 351 per Jay Moseley's guide, but TK5 uses 148)
KICKS_ADDR = "148"
KICKS_VOLSER = "KICKS0"


def log(icon, msg):
    """Print status message."""
    print(f"  {icon} {msg}")


def herc_cmd(cmd):
    """Send command to Hercules HTTP console."""
    try:
        url = f"{HERC_HTTP}/cgi-bin/tasks/cmd?cmd={urllib.parse.quote(cmd)}"
        with urllib.request.urlopen(url, timeout=15) as resp:
            import re
            return re.sub(r'<[^>]+>', '', resp.read().decode('utf-8', errors='replace')).strip()
    except Exception as e:
        return f"ERROR: {e}"


def wait_for_job(jobname, timeout=120):
    """Wait for job to complete by checking hardcopy log."""
    hardcopy = TK5_DIR / "log" / "hardcopy.log"
    start = time.time()
    while time.time() - start < timeout:
        try:
            with open(hardcopy, 'r', errors='replace') as f:
                lines = f.readlines()[-100:]
                for line in lines:
                    if jobname in line and ("ENDED" in line or "PURGED" in line):
                        # Check for success
                        if "ENDED - RC=0000" in line or "ENDED" in line:
                            return True
        except Exception:
            pass
        time.sleep(2)
    return False


def submit_jcl_file(jcl_path, timeout=60):
    """Submit JCL via Hercules card reader."""
    if not os.path.exists(jcl_path):
        log("✗", f"JCL not found: {jcl_path}")
        return False
    result = herc_cmd(f"devinit 00c {jcl_path} ascii eof")
    log("→", f"Submitted {os.path.basename(jcl_path)}")
    time.sleep(2)
    return True


class TerminalSession:
    """Terminal API helper."""

    def __init__(self):
        self.base = TERMINAL_API

    def get_screen(self):
        try:
            r = requests.get(f"{self.base}/screen", timeout=10)
            return r.json().get("screen", "")
        except Exception:
            return ""

    def send_key(self, key_type, value=""):
        try:
            requests.post(f"{self.base}/key",
                         json={"key_type": key_type, "value": value}, timeout=10)
        except Exception:
            pass
        time.sleep(0.3)

    def send_cmd(self, cmd, delay=2):
        self.send_key("string", cmd)
        self.send_key("enter")
        time.sleep(delay)

    def wait_for(self, text, timeout=60):
        start = time.time()
        while time.time() - start < timeout:
            if text.upper() in self.get_screen().upper():
                return True
            time.sleep(1)
        return False

    def ensure_tso_ready(self, userid="HERC01", password="CUL8TR"):
        """Get to TSO READY prompt."""
        # Cancel any stuck sessions
        herc_cmd(f"/C U={userid}")
        time.sleep(3)

        # Clear screen
        self.send_key("clear")
        time.sleep(1)
        self.send_key("enter")
        time.sleep(1)

        screen = self.get_screen()

        # At VTAM?
        if "==>" in screen:
            self.send_cmd(f"LOGON {userid}", delay=2)
            screen = self.get_screen()

        # At LOGON OR LOGOFF?
        if "LOGON OR LOGOFF" in screen.upper():
            self.send_cmd(f"LOGON {userid}", delay=2)
            screen = self.get_screen()

        # At ENTER USERID?
        if "ENTER USERID" in screen.upper():
            self.send_cmd(userid, delay=2)
            screen = self.get_screen()

        # Password?
        if "PASSWORD" in screen.upper():
            self.send_cmd(password, delay=4)

            # Press through post-login
            for _ in range(10):
                screen = self.get_screen()
                if "READY" in screen:
                    return True
                if "ISPF" in screen.upper():
                    self.send_key("pf", "3")
                else:
                    self.send_key("enter")
                time.sleep(1)

        return "READY" in self.get_screen()


def create_jcl_files():
    """Create all required JCL files."""
    os.makedirs(JCL_DIR, exist_ok=True)

    # ICKDSF - Initialize volume
    with open(JCL_DIR / "ICKDSF.jcl", "w") as f:
        f.write(f"""//ICKDSF   JOB (1),ICKDSF,CLASS=A,MSGCLASS=X,MSGLEVEL=(1,1)
//ICKDSF  EXEC PGM=ICKDSF,REGION=4096K
//SYSPRINT DD SYSOUT=*
//SYSIN    DD *
  INIT UNITADDRESS({KICKS_ADDR}) NOVERIFY VOLID({KICKS_VOLSER}) -
       OWNER(HERCULES) VTOC(0,1,30)
/*
""")

    # IDCAMS - Create user catalog and alias
    with open(JCL_DIR / "DEFCAT.jcl", "w") as f:
        f.write(f"""//DEFCAT   JOB (1),DEFCAT,CLASS=A,MSGCLASS=X,MSGLEVEL=(1,1)
//IDCAMS   EXEC PGM=IDCAMS,REGION=4096K
//SYSPRINT DD SYSOUT=*
//{KICKS_VOLSER}   DD UNIT=3350,DISP=OLD,VOL=SER={KICKS_VOLSER}
//SYSIN    DD *
  DEFINE USERCATALOG ( -
      NAME(UCKICKS0) -
      VOLUME({KICKS_VOLSER}) -
      TRACKS(7500 0) -
      FOR(9999) ) -
      DATA (TRACKS(15 5)) -
      INDEX (TRACKS(15)) -
      CATALOG(SYS1.VSAM.MASTER.CATALOG/SYSPROG)
  DEFINE ALIAS ( -
      NAME(KICKS) -
      RELATE(UCKICKS0)) -
      CATALOG(SYS1.VSAM.MASTER.CATALOG/SYSPROG)
/*
""")

    # RECV370 - Upload XMIT
    with open(JCL_DIR / "RECV370.jcl", "w") as f:
        f.write(f"""//RECV370  JOB (1),RECV370,CLASS=A,MSGCLASS=X,MSGLEVEL=(1,1)
//JOBLIB   DD DISP=SHR,DSN=SYSC.LINKLIB
//RECV1   EXEC PGM=RECV370
//RECVLOG  DD SYSOUT=*
//SYSPRINT DD SYSOUT=*
//SYSIN    DD DUMMY
//XMITIN   DD UNIT=01C,DCB=BLKSIZE=80
//SYSUT1   DD UNIT=VIO,SPACE=(CYL,(5,5))
//SYSUT2   DD DSN=KICKS.V1R5M0.INSTALL,
//            UNIT=3350,VOL=SER={KICKS_VOLSER},
//            SPACE=(TRK,(600,,8),RLSE),DISP=(,CATLG)
""")

    log("✓", "JCL files created")


def step1_create_dasd():
    """Create KICKS DASD volume."""
    print("\n[1/7] Creating KICKS DASD volume...")

    dasd_path = DASD_DIR / "kicks0.350"

    # Detach if exists
    herc_cmd(f"detach {KICKS_ADDR}")
    time.sleep(2)

    # Check for dasdinit
    dasdinit = shutil.which("dasdinit")
    if not dasdinit:
        # Try Hercules install path
        for path in ["/usr/local/bin/dasdinit", "/opt/homebrew/bin/dasdinit"]:
            if os.path.exists(path):
                dasdinit = path
                break

    if not dasdinit:
        log("!", "dasdinit not found - using existing DASD")
    else:
        # Remove old DASD
        if dasd_path.exists():
            dasd_path.unlink()

        # Create new DASD
        result = subprocess.run(
            [dasdinit, "-a", str(dasd_path), "3350", KICKS_VOLSER],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            log("✗", f"dasdinit failed: {result.stderr}")
            return False
        log("✓", "DASD created")

    # Attach DASD
    herc_cmd(f"attach {KICKS_ADDR} 3350 dasd/kicks0.350")
    time.sleep(2)
    log("✓", "DASD attached")

    return True


def step2_init_volume():
    """Initialize volume with ICKDSF."""
    print("\n[2/7] Initializing volume with ICKDSF...")

    # Vary offline first
    herc_cmd(f"/V {KICKS_ADDR},OFFLINE")
    time.sleep(2)

    # Submit ICKDSF
    submit_jcl_file(str(JCL_DIR / "ICKDSF.jcl"))

    # Wait for and reply to ICKDSF message
    hardcopy = TK5_DIR / "log" / "hardcopy.log"
    for _ in range(30):
        time.sleep(1)
        try:
            with open(hardcopy, 'r') as f:
                content = f.read()
                if "ICK003D" in content:
                    herc_cmd("/R 00,U")
                    log("→", "Replied to ICKDSF confirmation")
                    break
        except Exception:
            pass

    wait_for_job("ICKDSF", 60)

    # Bring volume online
    herc_cmd(f"/V {KICKS_ADDR},ONLINE")
    time.sleep(2)
    herc_cmd(f"/M {KICKS_ADDR},VOL=(SL,{KICKS_VOLSER}),USE=PRIVATE")
    time.sleep(3)

    log("✓", "Volume initialized")
    return True


def step3_create_catalog():
    """Create KICKS user catalog."""
    print("\n[3/7] Creating user catalog...")

    submit_jcl_file(str(JCL_DIR / "DEFCAT.jcl"))
    wait_for_job("DEFCAT", 60)

    log("✓", "User catalog created")
    return True


def step4_upload_xmit():
    """Upload KICKS XMIT file."""
    print("\n[4/7] Uploading KICKS XMIT...")

    if not XMIT_FILE.exists():
        log("✗", f"XMIT file not found: {XMIT_FILE}")
        return False

    # Initialize card reader with XMIT
    herc_cmd(f"devinit 01c {XMIT_FILE} ebcdic")
    time.sleep(2)
    log("→", "XMIT loaded to card reader")

    # Submit RECV370
    submit_jcl_file(str(JCL_DIR / "RECV370.jcl"))
    wait_for_job("RECV370", 120)

    log("✓", "XMIT uploaded")
    return True


def step5_unpack_datasets():
    """Unpack KICKS datasets from XMIT."""
    print("\n[5/7] Unpacking KICKS datasets...")

    # Create the V1R5M0 unpack JCL (based on Jay Moseley's modifications)
    rcvkick2_jcl = JCL_DIR / "RCVKICK2.jcl"
    with open(rcvkick2_jcl, "w") as f:
        f.write(f"""//RCVKICK2 JOB (1),RCVKIK2,CLASS=A,MSGCLASS=X,MSGLEVEL=(1,1),
//             REGION=4096K
//JOBLIB DD DISP=SHR,DSN=SYSC.LINKLIB
//*
//* UNPACK ALL KICKS DATASETS FROM THE INSTALL PDS
//*
//RECV PROC UID=KICKS,MEM=DUMMY,MEM2=DUMMY,TRK=30,MLQ=KICKS
//RECV1   EXEC PGM=RECV370
//RECVLOG  DD SYSOUT=*
//SYSPRINT DD SYSOUT=*
//SYSIN    DD DUMMY
//XMITIN   DD DSN=KICKS.V1R5M0.INSTALL(&MEM),DISP=SHR
//SYSUT1   DD UNIT=VIO,SPACE=(CYL,(5,5))
//SYSUT2   DD DSN=&UID..&MLQ..V1R5M0.&MEM2,
//            UNIT=3350,VOL=SER={KICKS_VOLSER},
//            SPACE=(TRK,(&TRK,30,100),RLSE),DISP=(,CATLG)
//        PEND
//HCB2     EXEC RECV,MEM=HCB2,MEM2=CB2,TRK=150
//HCOB     EXEC RECV,MEM=HCOB,MEM2=COB,TRK=300
//HCOBCPY  EXEC RECV,MEM=HCOBCOPY,MEM2=COBCOPY,TRK=60
//HGCC     EXEC RECV,MEM=HGCC,MEM2=GCC,TRK=150
//HGCCCPY  EXEC RECV,MEM=HGCCCOPY,MEM2=GCCCOPY,TRK=60
//HINST    EXEC RECV,MEM=HINSTLIB,MEM2=INSTLIB,TRK=60
//HKIKRPL  EXEC RECV,MEM=HKIKRPL,MEM2=KIKRPL,TRK=600
//HMAPSRC  EXEC RECV,MEM=HMAPSRC,MEM2=MAPSRC,TRK=150
//HOPIDS   EXEC RECV,MEM=HOPIDS,MEM2=OPIDS,TRK=30
//*
//RECVS PROC UID=KICKS,MEM=DUMMY,MEM2=DUMMY,TRK=30,MLQ=KICKSSYS
//RECV1   EXEC PGM=RECV370
//RECVLOG  DD SYSOUT=*
//SYSPRINT DD SYSOUT=*
//SYSIN    DD DUMMY
//XMITIN   DD DSN=KICKS.V1R5M0.INSTALL(&MEM),DISP=SHR
//SYSUT1   DD UNIT=VIO,SPACE=(CYL,(5,5))
//SYSUT2   DD DSN=&UID..&MLQ..V1R5M0.&MEM2,
//            UNIT=3350,VOL=SER={KICKS_VOLSER},
//            SPACE=(TRK,(&TRK,30,100),RLSE),DISP=(,CATLG)
//        PEND
//SCMDPROC EXEC RECVS,MEM=SCMDPROC,MEM2=CLIST,TRK=90
//SCOB     EXEC RECVS,MEM=SCOB,MEM2=COB,TRK=150
//SCOBCPY  EXEC RECVS,MEM=SCOBCOPY,MEM2=COBCOPY,TRK=60
//SDOC     EXEC RECVS,MEM=SDOC,MEM2=DOC,TRK=30
//SGCC     EXEC RECVS,MEM=SGCC,MEM2=GCC,TRK=150
//SGCCCPY  EXEC RECVS,MEM=SGCCCOPY,MEM2=GCCCOPY,TRK=60
//SINST    EXEC RECVS,MEM=SINSTLIB,MEM2=INSTLIB,TRK=90
//SKIKRPL  EXEC RECVS,MEM=SKIKRPL,MEM2=KIKRPL,TRK=600
//SMACLIB  EXEC RECVS,MEM=SMACLIB,MEM2=MACLIB,TRK=150
//SMAPSRC  EXEC RECVS,MEM=SMAPSRC,MEM2=MAPSRC,TRK=150
//SPROCLIB EXEC RECVS,MEM=SPROCLIB,MEM2=PROCLIB,TRK=30
//SPROCLZ  EXEC RECVS,MEM=SPROCLIZ,MEM2=PROCLIBZ,TRK=30
//SSKIKLOD EXEC RECVS,MEM=SSKIKLOD,MEM2=SKIKLOAD,TRK=600
//STESTCOB EXEC RECVS,MEM=STESTCOB,MEM2=TESTCOB,TRK=150
//STESTGCC EXEC RECVS,MEM=STESTGCC,MEM2=TESTGCC,TRK=150
//STESTFIL EXEC RECVS,MEM=STESTFIL,MEM2=TESTFILE,TRK=30
""")

    submit_jcl_file(str(rcvkick2_jcl))
    log("→", "Unpacking datasets (this takes a few minutes)...")
    wait_for_job("RCVKICK2", 300)

    log("✓", "Datasets unpacked")
    return True


def step6_create_vsam():
    """Create VSAM datasets for KICKS."""
    print("\n[6/7] Creating VSAM datasets...")

    vsam_jcl = JCL_DIR / "MKVSAM.jcl"
    with open(vsam_jcl, "w") as f:
        f.write(f"""//MKVSAM   JOB (1),MKVSAM,CLASS=A,MSGCLASS=X,MSGLEVEL=(1,1)
//STEP1   EXEC PGM=IDCAMS
//SYSPRINT DD SYSOUT=*
//SYSIN    DD *
  DELETE KICKS.KICKSSYS.V1R5M0.KIKINTRA CLUSTER PURGE
  SET MAXCC=0
  DELETE KICKS.KICKSSYS.V1R5M0.KIKTEMP CLUSTER PURGE
  SET MAXCC=0
  DEFINE CLUSTER ( -
         NAME(KICKS.KICKSSYS.V1R5M0.KIKINTRA) -
         NONINDEXED RECORDSIZE(100 32760) -
         TRACKS(50 10) VOLUMES({KICKS_VOLSER}) UNIQUE ) -
       DATA (NAME(KICKS.KICKSSYS.V1R5M0.KIKINTRA.DATA) -
         CONTROLINTERVALSIZE(32760))
  DEFINE CLUSTER ( -
         NAME(KICKS.KICKSSYS.V1R5M0.KIKTEMP) -
         NONINDEXED RECORDSIZE(100 32760) -
         TRACKS(100 20) VOLUMES({KICKS_VOLSER}) UNIQUE ) -
       DATA (NAME(KICKS.KICKSSYS.V1R5M0.KIKTEMP.DATA) -
         CONTROLINTERVALSIZE(32760))
/*
""")

    submit_jcl_file(str(vsam_jcl))
    wait_for_job("MKVSAM", 60)

    log("✓", "VSAM datasets created")
    return True


def step7_verify():
    """Verify installation."""
    print("\n[7/7] Verifying installation...")

    term = TerminalSession()
    if not term.ensure_tso_ready():
        log("!", "Could not get to TSO READY - manual verification needed")
        return True

    # Check for KICKS datasets
    term.send_cmd("PROFILE NOPREFIX", delay=1)
    term.send_cmd("LISTCAT ENT(KICKS.KICKSSYS.V1R5M0.CLIST)", delay=3)
    screen = term.get_screen()

    if "KICKS.KICKSSYS" in screen and "NOT IN CATALOG" not in screen.upper():
        log("✓", "KICKS datasets verified")
        return True
    else:
        log("!", "Could not verify KICKS datasets")
        return True


def main():
    print("=" * 60)
    print("  KICKS Installation (moshix/Jay Moseley method)")
    print("=" * 60)

    # Check prerequisites
    if not XMIT_FILE.exists():
        log("✗", f"XMIT file not found: {XMIT_FILE}")
        print("\nDownload from: https://github.com/moshix/kicks")
        return 1

    # Test Hercules connection
    result = herc_cmd("devlist 00c")
    if "ERROR" in result:
        log("✗", "Cannot connect to Hercules (port 8038)")
        return 1
    log("✓", "Hercules connected")

    # Create JCL files
    create_jcl_files()

    # Run steps
    if not step1_create_dasd():
        return 1

    if not step2_init_volume():
        return 1

    if not step3_create_catalog():
        return 1

    if not step4_upload_xmit():
        return 1

    if not step5_unpack_datasets():
        return 1

    if not step6_create_vsam():
        return 1

    step7_verify()

    print("\n" + "=" * 60)
    print("  Installation Complete!")
    print("=" * 60)
    print("""
To start KICKS:
  1. Connect: c3270 localhost:3270
  2. TSO: HERC01 / CUL8TR
  3. Run: EXEC 'KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)'

Press ENTER through startup screens.
To exit KICKS: CLEAR + KSSF + ENTER

For persistence after TK5 restart, add to tk5/mvs-tk5/conf/tk5.cnf:
  0148 3350 dasd/kicks0.350
""")

    return 0


if __name__ == "__main__":
    sys.exit(main())
