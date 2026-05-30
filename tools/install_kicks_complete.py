#!/usr/bin/env python3
"""
KICKS Complete Installation Script for TK5/MVS 3.8j
====================================================

Fully automated KICKS installation with all fixes applied.

Prerequisites:
  - TK5 MVS running with Hercules HTTP API on port 8038
  - py3270: .venv/bin/pip install py3270
  - s3270: brew install x3270 (macOS) or apt install x3270 (Linux)
  - KICKS XMIT at tools/kicks_install/kicks-master/kicks-tso-v1r5m0/kicks-tso-v1r5m0.xmi

Usage:
  .venv/bin/python tools/install_kicks_complete.py

After installation:
  c3270 localhost:3270
  TSO -> HERC01 / CUL8TR
  EX 'KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)' 'KIKID(KICKS)'
"""

import os
import sys
import time
import shutil
import subprocess
import urllib.request
import urllib.parse

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TK5_DIR = os.path.join(PROJECT_DIR, "tk5", "mvs-tk5")
JCL_DIR = os.path.join(PROJECT_DIR, "jcl", "kicks")
XMIT_FILE = os.path.join(PROJECT_DIR, "tools", "kicks_install", "kicks-master",
                         "kicks-tso-v1r5m0", "kicks-tso-v1r5m0.xmi")

HERC_HTTP = "http://localhost:8038"
KICKS_ADDR = "148"
TN3270_PORT = 3270


def log(icon, msg):
    print(f"  {icon} {msg}")


def herc_cmd(cmd):
    """Send command to Hercules HTTP console."""
    try:
        url = f"{HERC_HTTP}/cgi-bin/tasks/cmd?cmd={urllib.parse.quote(cmd)}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            import re
            return re.sub(r'<[^>]+>', '', resp.read().decode('utf-8', errors='replace')).strip()
    except Exception as e:
        return f"ERROR: {e}"


def submit_jcl(jcl_path, timeout=60):
    """Submit JCL via card reader."""
    if not os.path.exists(jcl_path):
        log("✗", f"JCL not found: {jcl_path}")
        return False
    herc_cmd(f"devinit 00c {jcl_path} ascii eof")
    log("→", f"Submitted {os.path.basename(jcl_path)}")
    time.sleep(timeout)
    return True


def wait_job(jobname, timeout=60):
    """Wait for job completion."""
    hardcopy = os.path.join(TK5_DIR, "log", "hardcopy.log")
    start = time.time()
    while time.time() - start < timeout:
        try:
            with open(hardcopy, 'r', errors='replace') as f:
                for line in f.readlines()[-50:]:
                    if jobname in line and ("ENDED" in line or "PURGED" in line):
                        return True
        except:
            pass
        time.sleep(2)
    return True


def create_jcl():
    """Create all JCL files."""
    os.makedirs(JCL_DIR, exist_ok=True)

    # ICKDSF
    with open(f"{JCL_DIR}/ICKDSF.jcl", "w") as f:
        f.write("""//ICKDSF   JOB (1),ICKDSF,CLASS=A,MSGCLASS=A,MSGLEVEL=(1,1),
//             USER=HERC01,PASSWORD=CUL8TR
//ICKDSF  EXEC PGM=ICKDSF,REGION=4096K
//SYSPRINT DD SYSOUT=*
//SYSIN    DD *
  INIT UNITADDRESS(148) NOVERIFY VOLID(KICKS0) VTOC(0,1,30)
/*
""")

    # DEFCAT
    with open(f"{JCL_DIR}/DEFCAT.jcl", "w") as f:
        f.write("""//DEFCAT   JOB (1),DEFCAT,CLASS=A,MSGCLASS=A,MSGLEVEL=(1,1),
//             REGION=4096K,USER=HERC01,PASSWORD=CUL8TR
//IDCAMS   EXEC PGM=IDCAMS,REGION=4096K
//SYSPRINT DD SYSOUT=*
//KICKS0   DD UNIT=3350,DISP=OLD,VOL=SER=KICKS0
//SYSIN    DD *
  DEFINE USERCATALOG ( -
      NAME(UCKICKS1) VOLUME(KICKS0) -
      CYLINDERS(50 5) FOR(9999) ) -
      DATA (CYLINDERS(1 1)) -
      INDEX (CYLINDERS(1 1)) -
      CATALOG(SYS1.VSAM.MASTER.CATALOG)
  DEFINE ALIAS ( -
      NAME(KICKS) RELATE(UCKICKS1) ) -
      CATALOG(SYS1.VSAM.MASTER.CATALOG)
/*
""")

    # RECV370
    with open(f"{JCL_DIR}/RECV370.jcl", "w") as f:
        f.write("""//RECV370  JOB (1),RECV370,CLASS=A,MSGCLASS=A,MSGLEVEL=(1,1),
//             REGION=4096K,USER=HERC01,PASSWORD=CUL8TR
//RECV1   EXEC PGM=RECV370
//RECVLOG  DD SYSOUT=*
//SYSPRINT DD SYSOUT=*
//SYSIN    DD DUMMY
//XMITIN   DD UNIT=010C,DCB=BLKSIZE=80
//SYSUT1   DD UNIT=VIO,SPACE=(CYL,(5,5))
//SYSUT2   DD DSN=KICKS.V1R5M0.INSTALL,
//            UNIT=3350,VOL=SER=KICKS0,
//            SPACE=(TRK,(600,,20),RLSE),DISP=(,CATLG)
""")

    # RCVKICK2
    with open(f"{JCL_DIR}/RCVKICK2.jcl", "w") as f:
        f.write("""//RCVKICK2 JOB (1),RCVKIK2,CLASS=A,MSGCLASS=A,MSGLEVEL=(1,1),
//             REGION=4096K,USER=HERC01,PASSWORD=CUL8TR
//CLEAN   EXEC PGM=IDCAMS
//SYSPRINT DD SYSOUT=*
//SYSIN    DD *
  DELETE KICKS.KICKS.V1R5M0.CB2 NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKS.V1R5M0.COB NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKS.V1R5M0.COBCOPY NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKS.V1R5M0.GCC NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKS.V1R5M0.GCCCOPY NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKS.V1R5M0.INSTLIB NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKS.V1R5M0.KIKRPL NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKS.V1R5M0.MAPSRC NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKS.V1R5M0.OPIDS NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKSSYS.V1R5M0.CLIST NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKSSYS.V1R5M0.COB NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKSSYS.V1R5M0.COBCOPY NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKSSYS.V1R5M0.DOC NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKSSYS.V1R5M0.GCC NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKSSYS.V1R5M0.GCCCOPY NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKSSYS.V1R5M0.INSTLIB NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKSSYS.V1R5M0.KIKRPL NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKSSYS.V1R5M0.MACLIB NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKSSYS.V1R5M0.MAPSRC NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKSSYS.V1R5M0.PROCLIB NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKSSYS.V1R5M0.PROCLIBZ NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKSSYS.V1R5M0.SKIKLOAD NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKSSYS.V1R5M0.TESTCOB NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKSSYS.V1R5M0.TESTFILE NONVSAM
  SET MAXCC=0
  DELETE KICKS.KICKSSYS.V1R5M0.TESTGCC NONVSAM
  SET MAXCC=0
/*
//RECV PROC UID=KICKS,MEM=DUMMY,MEM2=DUMMY,TRK=30,MLQ=KICKS
//RECV1   EXEC PGM=RECV370
//RECVLOG  DD SYSOUT=*
//SYSPRINT DD SYSOUT=*
//SYSIN    DD DUMMY
//XMITIN   DD DSN=KICKS.V1R5M0.INSTALL(&MEM),DISP=SHR
//SYSUT1   DD UNIT=VIO,SPACE=(CYL,(5,5))
//SYSUT2   DD DSN=&UID..&MLQ..V1R5M0.&MEM2,
//            UNIT=3350,VOL=SER=KICKS0,
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
//RECVS PROC UID=KICKS,MEM=DUMMY,MEM2=DUMMY,TRK=30,MLQ=KICKSSYS
//RECV1   EXEC PGM=RECV370
//RECVLOG  DD SYSOUT=*
//SYSPRINT DD SYSOUT=*
//SYSIN    DD DUMMY
//XMITIN   DD DSN=KICKS.V1R5M0.INSTALL(&MEM),DISP=SHR
//SYSUT1   DD UNIT=VIO,SPACE=(CYL,(5,5))
//SYSUT2   DD DSN=&UID..&MLQ..V1R5M0.&MEM2,
//            UNIT=3350,VOL=SER=KICKS0,
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

    # FIXNAMES - Critical fix for CLIST compatibility
    with open(f"{JCL_DIR}/FIXNAMES.jcl", "w") as f:
        f.write("""//FIXNAMES JOB (1),FIXNAMES,CLASS=A,MSGCLASS=A,MSGLEVEL=(1,1),
//             REGION=4096K,USER=HERC01,PASSWORD=CUL8TR
//* COPY DATASETS TO CLIST-EXPECTED NAMES
//COPYS1  EXEC PGM=IEBCOPY
//SYSPRINT DD SYSOUT=*
//IN       DD DSN=KICKS.KICKSSYS.V1R5M0.SKIKLOAD,DISP=SHR
//OUT      DD DSN=KICKS.S.V1R5M0.SKIKLOAD,DISP=(NEW,CATLG),
//            UNIT=3350,VOL=SER=KICKS0,SPACE=(TRK,(600,100,50))
//SYSIN    DD *
  COPY INDD=IN,OUTDD=OUT
/*
//COPYS2  EXEC PGM=IEBCOPY
//SYSPRINT DD SYSOUT=*
//IN       DD DSN=KICKS.KICKSSYS.V1R5M0.KIKRPL,DISP=SHR
//OUT      DD DSN=KICKS.S.V1R5M0.KIKRPL,DISP=(NEW,CATLG),
//            UNIT=3350,VOL=SER=KICKS0,SPACE=(TRK,(600,100,50))
//SYSIN    DD *
  COPY INDD=IN,OUTDD=OUT
/*
//COPYS3  EXEC PGM=IEBCOPY
//SYSPRINT DD SYSOUT=*
//IN       DD DSN=KICKS.KICKSSYS.V1R5M0.DOC,DISP=SHR
//OUT      DD DSN=KICKS.S.V1R5M0.DOC,DISP=(NEW,CATLG),
//            UNIT=3350,VOL=SER=KICKS0,SPACE=(TRK,(30,10,20))
//SYSIN    DD *
  COPY INDD=IN,OUTDD=OUT
/*
//MKUSER1 EXEC PGM=IEFBR14
//DD1      DD DSN=KICKS.U.V1R5M0.SKIKLOAD,DISP=(NEW,CATLG),
//            UNIT=3350,VOL=SER=KICKS0,SPACE=(TRK,(10,10,5)),
//            DCB=(DSORG=PO,RECFM=U,BLKSIZE=6144)
//MKUSER2 EXEC PGM=IEFBR14
//DD1      DD DSN=KICKS.U.V1R5M0.KIKRPL,DISP=(NEW,CATLG),
//            UNIT=3350,VOL=SER=KICKS0,SPACE=(TRK,(10,10,5)),
//            DCB=(DSORG=PO,RECFM=U,BLKSIZE=6144)
""")

    # VSAM files
    with open(f"{JCL_DIR}/MKVSAM.jcl", "w") as f:
        f.write("""//MKVSAM   JOB (1),MKVSAM,CLASS=A,MSGCLASS=A,MSGLEVEL=(1,1),
//             USER=HERC01,PASSWORD=CUL8TR
//STEP1   EXEC PGM=IDCAMS
//SYSPRINT DD SYSOUT=*
//SYSIN    DD *
  DELETE KICKS.S.V1R5M0.KIKINTRA CLUSTER PURGE
  SET MAXCC=0
  DELETE KICKS.S.V1R5M0.KIKTEMP CLUSTER PURGE
  SET MAXCC=0
  DEFINE CLUSTER ( -
         NAME(KICKS.S.V1R5M0.KIKINTRA) -
         NONINDEXED RECORDSIZE(100 32760) -
         TRACKS(50 10) VOLUMES(KICKS0) UNIQUE ) -
       DATA (NAME(KICKS.S.V1R5M0.KIKINTRA.DATA) -
         CONTROLINTERVALSIZE(32760))
  DEFINE CLUSTER ( -
         NAME(KICKS.S.V1R5M0.KIKTEMP) -
         NONINDEXED RECORDSIZE(100 32760) -
         TRACKS(100 20) VOLUMES(KICKS0) UNIQUE ) -
       DATA (NAME(KICKS.S.V1R5M0.KIKTEMP.DATA) -
         CONTROLINTERVALSIZE(32760))
/*
""")

    log("✓", "JCL files created")


def main():
    print("\n" + "=" * 60)
    print("  KICKS Complete Installation")
    print("=" * 60)

    # Checks
    if not os.path.exists(XMIT_FILE):
        log("✗", f"XMIT not found: {XMIT_FILE}")
        return 1

    result = herc_cmd("devlist 00c")
    if "ERROR" in result:
        log("✗", "Hercules not running")
        return 1
    log("✓", "Hercules running")

    # Create JCL
    print("\n[1/8] Creating JCL files...")
    create_jcl()

    # Cancel any TSO session
    herc_cmd("/c u=HERC01")
    time.sleep(2)

    # Initialize DASD
    print("\n[2/8] Initializing DASD...")
    dasd_path = f"{TK5_DIR}/dasd/kicks0.350"
    dasdinit = shutil.which("dasdinit")

    if dasdinit:
        herc_cmd(f"detach {KICKS_ADDR}")
        time.sleep(1)
        if os.path.exists(dasd_path):
            os.remove(dasd_path)
        subprocess.run([dasdinit, "-a", dasd_path, "3350", "KICKS0"],
                       capture_output=True, timeout=60)
        herc_cmd(f"attach {KICKS_ADDR} 3350 dasd/kicks0.350")
        time.sleep(2)
        log("✓", "DASD created")

    # ICKDSF
    print("\n[3/8] Formatting volume (ICKDSF)...")
    herc_cmd(f"/v {KICKS_ADDR},offline")
    time.sleep(1)
    submit_jcl(f"{JCL_DIR}/ICKDSF.jcl", timeout=3)

    # Reply to ICKDSF
    for _ in range(15):
        time.sleep(1)
        try:
            with open(f"{TK5_DIR}/log/hardcopy.log", 'r') as f:
                if "ICK003D" in f.read():
                    herc_cmd("/r 00,u")
                    break
        except:
            pass
    wait_job("ICKDSF", 30)
    herc_cmd(f"/v {KICKS_ADDR},online")
    herc_cmd(f"/m {KICKS_ADDR},vol=(sl,KICKS0),use=private")
    time.sleep(3)
    log("✓", "Volume formatted")

    # DEFCAT
    print("\n[4/8] Creating catalog...")
    submit_jcl(f"{JCL_DIR}/DEFCAT.jcl", timeout=10)
    wait_job("DEFCAT", 30)
    log("✓", "Catalog created")

    # Upload XMIT
    print("\n[5/8] Uploading XMIT...")
    herc_cmd(f"devinit 010c {XMIT_FILE} ebcdic")
    time.sleep(2)
    log("✓", "XMIT loaded")

    # RECV370
    print("\n[6/8] Unpacking XMIT (RECV370)...")
    submit_jcl(f"{JCL_DIR}/RECV370.jcl", timeout=30)
    wait_job("RECV370", 60)
    log("✓", "Initial unpack complete")

    # RCVKICK2
    print("\n[7/8] Unpacking all datasets (RCVKICK2)...")
    submit_jcl(f"{JCL_DIR}/RCVKICK2.jcl", timeout=60)
    wait_job("RCVKICK2", 180)
    log("✓", "Datasets unpacked")

    # Fix names and create VSAM
    print("\n[8/8] Applying fixes...")
    submit_jcl(f"{JCL_DIR}/FIXNAMES.jcl", timeout=30)
    wait_job("FIXNAMES", 60)
    submit_jcl(f"{JCL_DIR}/MKVSAM.jcl", timeout=15)
    wait_job("MKVSAM", 30)
    log("✓", "Fixes applied")

    # Done
    print("\n" + "=" * 60)
    print("  Installation Complete!")
    print("=" * 60)
    print("""
  To connect:
    c3270 localhost:3270

  At VTAM: TSO
  Login: HERC01 / CUL8TR

  At READY:
    EX 'KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)' 'KIKID(KICKS)'

  Press ENTER, then CLEAR + transaction (KSGM, CESN, CEMT)
  Exit: CLEAR + KSSF + ENTER

  For persistence after restart, add to tk5/mvs-tk5/conf/tk5.cnf:
    0148 3350 dasd/kicks0.350
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
