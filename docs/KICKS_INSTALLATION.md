# KICKS Installation Guide for MVS 3.8j (TK5)

> Based on Jay Moseley's comprehensive installation guide (December 2020, updated April 2022)

## Overview

**KICKS** is a transaction processing system modeled on IBM CICS. It provides high-level source code compatibility with CICS—applications can migrate between CICS and KICKS by recompiling. KICKS runs as a library in the TSO address space, making it ideal for:

- Learning CICS programming skills
- Developing and testing CICS applications
- Prototyping applications for later deployment on z/OS CICS
- Supporting small groups of users (demonstrated up to several hundred)

| Item | Value |
|------|-------|
| **Current Version** | 1.5.0 (2014) |
| **DASD Volume** | KICKS0 (3350) |
| **User Catalog** | UCKICKS0 |
| **HLQ** | KICKS |
| **System Datasets** | KICKS.KICKSSYS.* |
| **User Datasets** | KICKS.KICKS.* |
| **Forum** | https://groups.io/g/KICKSforTSO |
| **Documentation** | http://www.kicksfortso.com/ |
| **Source Archive** | https://github.com/moshix/kicks |

---

## Pre-Installation Checklist

- [ ] MVS 3.8j TK5 running on Hercules
- [ ] Access to Hercules console
- [ ] TSO access with privileged userid (HERC01)
- [ ] KICKS archive downloaded and extracted
- [ ] JCL files prepared in `jcl/kicks/`

---

## Step 1: Download KICKS

```bash
# Download from GitHub
wget https://github.com/moshix/kicks/archive/master.zip
unzip master.zip

# The key file is:
# kicks-master/kicks-tso-v1r5m0/kicks-tso-v1r5m0.xmi
```

**Local path:** `kicks_install/kicks-master/kicks-tso-v1r5m0/kicks-tso-v1r5m0.xmi`

---

## Step 2: Prepare DASD Volume

### 2.1 Create Empty 3350 DASD Image

On the host system (not Hercules):

```bash
dasdinit -a kicks0.3350 3350 111111
```

This creates an empty 3350 DASD image with serial number `111111` (to be changed during initialization).

### 2.2 Attach DASD to Hercules

At the Hercules console:

```
attach 351 3350 dasd/kicks0.3350
```

### 2.3 Initialize Volume with ICKDSF

Submit `jcl/kicks/ICKDSF.jcl`:

```jcl
//ICKDSF   JOB (1),ICKDSF,CLASS=A,MSGCLASS=X                              
//ICKDSF EXEC PGM=ICKDSF,REGION=4096K                                   
//SYSPRINT DD  SYSOUT=*                                                 
//SYSIN    DD  *                                                        
  INIT UNITADDRESS(351) VERIFY(111111) -                                
               VOLID(KICKS0) OWNER(HERCULES) -                          
               VTOC(0,1,15)                                             
//
```

### 2.4 Vary Online and Mount

At MVS console:

```
v 351,online
m 351,vol=(sl,kicks0),use=private
```

### 2.5 Add to Hercules Configuration

Edit `conf/tk5.cnf` (or your Hercules config) to persist the DASD:

```
0351  3350  dasd/kicks0.3350
```

### 2.6 Add to Volume Attribute List

Edit `SYS1.PARMLIB(VATLST00)` and add:

```
KICKS0,0,2,3350    ,N        KICKS LIBRARIES/DATA (PRIVATE)
```

---

## Step 3: Create User Catalog

Submit `jcl/kicks/DEFCAT.jcl`:

```jcl
//DEFCAT   JOB (1),DEFCAT,CLASS=A,MSGCLASS=X
//IDCAMS01 EXEC PGM=IDCAMS,REGION=4096K
//SYSPRINT DD SYSOUT=*
//KICKS0   DD UNIT=SYSALLDA,DISP=OLD,VOL=SER=KICKS0
//SYSIN    DD *
  DEFINE USERCATALOG ( -
      NAME (UCKICKS0) -
      VOLUME (KICKS0) -
      TRACKS (7500 0) -
      FOR (9999) ) -
      DATA (TRACK (15 5) ) -
      INDEX (TRACKS (15) ) -
      CATALOG (SYS1.VMASTCAT/SYSPROG)

  DEFINE ALIAS ( -
      NAME (KICKS) -
      RELATE (UCKICKS0) ) -
      CATALOG (SYS1.VMASTCAT/SYSPROG)
//
```

This allocates:
- **7,500 tracks** (250 cylinders) for VSAM dataspace
- **KICKS** alias pointing to UCKICKS0 catalog

---

## Step 4: Upload XMIT File with RECV370

### 4.1 Initialize Card Reader

At Hercules console:

```
devinit 01c /full/path/to/kicks-tso-v1r5m0.xmi ebcdic
```

> **Critical:** Include the `ebcdic` operand to prevent ASCII-to-EBCDIC translation.

### 4.2 Submit RECV370 Job

Submit `jcl/kicks/RECV370.jcl`:

```jcl
//RECV370  JOB (1),'UNPACK XMIT',CLASS=A,MSGCLASS=X            
//RECV1   EXEC RECV370                                         
//XMITIN   DD  UNIT=01C,DCB=BLKSIZE=80           
//SYSUT2   DD  DSN=KICKS.V1R5M0.INSTALL,         
//             VOL=SER=KICKS0,UNIT=3350,                       
//             SPACE=(TRK,(600,,8),RLSE),                      
//             DISP=(,CATLG)                                   
//
```

This creates `KICKS.V1R5M0.INSTALL` containing 29 members (26 embedded XMIT files + documentation).

---

## Step 5: Unpack Installation Datasets

Submit `jcl/kicks/RCVKICK2.jcl` (pre-configured for TK5):

This job unpacks all 26 embedded XMIT files to create:

**User Datasets (KICKS.KICKS.V1R5M0.*):**
| Dataset | Content | Tracks |
|---------|---------|--------|
| ASM | Assembler source | 150 |
| COB | COBOL source | 300 |
| COPY | COBOL copybooks | 60 |
| EXEC | REXX execs | 30 |
| HELP | Help panels | 30 |
| INSTLIB | Installation JCL/data | 60 |
| JCL | Sample JCL | 30 |
| MACLIB | Assembler macros | 150 |
| MAPSRC | BMS map source | 150 |
| PANELS | ISPF panels | 30 |
| SKELS | ISPF skeletons | 30 |
| SOURCE | Miscellaneous source | 150 |
| TABLES | Table source | 30 |
| DOC | Documentation | 30 |

**System Datasets (KICKS.KICKSSYS.V1R5M0.*):**
| Dataset | Content | Tracks |
|---------|---------|--------|
| CLIST | CLISTs including KICKS startup | 90 |
| EXEC | System REXX | 30 |
| INSTLIB | System installation | 90 |
| SKIKLOAD | Load modules | 600 |
| MACLIB | System macros | 150 |
| PROCLIB | JCL procedures | 30 |

After successful execution, you may delete `KICKS.V1R5M0.INSTALL`.

---

## Step 6: Increase TSO Dynamic Allocation Limit

The KICKS CLIST allocates many datasets dynamically. The default limit of 20 is insufficient.

Edit `SYS1.PROCLIB(IKJACCNT)`:

```jcl
// Before:
//IKJACCNT EXEC PGM=IKJEFT01,DYNAMNBR=20,

// After:
//IKJACCNT EXEC PGM=IKJEFT01,DYNAMNBR=64,
```

**Log off and back on** for the change to take effect.

---

## Step 7: Customize KICKS with KFIX CLIST

At TSO READY:

```
PROFILE PREFIX(KICKS)
EXEC 'KICKS.KICKSSYS.V1R5M0.CLIST(KFIX)'
```

The KFIX CLIST cycles through possible High Level Qualifiers. Select **KICKS** (the second one) by typing `yes` when it appears.

After completion:

```
PROFILE NOPREFIX
```

---

## Step 8: Create Test Data

### 8.1 User Test Data

Submit these jobs (pre-configured in `jcl/kicks/`):

| Job | Purpose | VSAM Cluster Created |
|-----|---------|---------------------|
| `LOADMUR.jcl` | Murach customer file | KICKS.KICKS.V1R5M0.CUSTMAST |
| `LOADSDB.jcl` | SDB accounts & transactions | KICKS.KICKS.V1R5M0.ACCOUNTS, .TRANSACT |
| `LOADTAC.jcl` | TAC test data | KICKS.KICKS.V1R5M0.TACDATA |

### 8.2 System Data

Submit these jobs (pre-configured in `jcl/kicks/`):

| Job | Purpose | VSAM Cluster Created |
|-----|---------|---------------------|
| `LODINTRA.jcl` | Intrapartition Transient Data | KICKS.KICKSSYS.V1R5M0.DFHINTRA |
| `LODTEMP.jcl` | Temporary Storage Queues | KICKS.KICKSSYS.V1R5M0.DFHTEMP |

---

## Step 9: Fix KICKS CLIST Bug

**Required fix:** Edit `KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)` around line 145.

Find:
```
ALLOC FILE(SKIKLOAD) DSN('&TSOID..KICKS.&VER..SKIKLOAD' +
                         '&KIKID..KICKS.&VER..SKIKLOAD' +
                         '&KIKID..KICKSSYS.&VER..SKIKLOAD' +
                              ) SHR BLKSIZE(32760)
```

Change to (remove the second dataset which doesn't exist):
```
ALLOC FILE(SKIKLOAD) DSN('&TSOID..KICKS.&VER..SKIKLOAD' +    
                         '&KIKID..KICKSSYS.&VER..SKIKLOAD' + 
                              ) SHR BLKSIZE(32760)           
```

### Optional: Enable Higher Function Terminal Driver

For TK4-/TK5, edit line 5 of the KICKS CLIST and change:

```
KCP() PCP() FCP() DCP() SCP() TSP() BMS() TCP(1$)
```

This enables the Z/OS-style terminal driver for better function.

---

## Step 10: Start KICKS

At TSO READY:

```
EXEC 'KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)'
```

You'll see startup information, then press **ENTER** for the KICKS color banner.

### Using KICKS

- **ENTER** - Refresh screen, cycle colors
- **PF1** - Help information
- **CLEAR** - Clear screen to enter transaction
- Type 4-character transaction ID and press **ENTER**

### Shutdown KICKS

```
CLEAR
KSSF
```

> **Note:** After shutdown, you may need to press ENTER and run a command like `TIME` to resync TSO.

---

## Demo Transactions

| Trans ID | Description | Source |
|----------|-------------|--------|
| KSGM | Good Morning (startup) | System |
| KSSF | Sign Off (shutdown) | System |
| INQ1 | Customer Inquiry | Murach |
| MNT1 | Customer Maintenance | Murach |
| ORD1 | Order Entry | Murach |
| MEN1 | Menu Program | Murach |
| ACCT | Account Inquiry | SDB |
| TRAN | Transaction Display | SDB |

Demo source code: `KICKS.KICKS.V1R5M0.COB` (see `$README` member)
Map source: `KICKS.KICKS.V1R5M0.MAPSRC` (see `$README` member)

---

## Making KICKS Easily Accessible

Choose one method to make the KICKS CLIST available to all TSO users:

### Option A: Add to SYSPROC Concatenation
Edit TSO logon procedure to include `KICKS.KICKSSYS.V1R5M0.CLIST` in SYSPROC.

### Option B: Copy to SYS1.CMDPROC
```
COPY 'KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)' 'SYS1.CMDPROC(KICKS)'
```

### Option C: Copy to User CLIST
```
COPY 'KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)' 'userid.CLIST(KICKS)'
```

---

## KICKS Configuration Tables

KICKS operation is controlled through assembled tables, similar to CICS.

### System Initialization Table (SIT)
- **Macro:** KIKSIT
- **JCL:** `KICKS.KICKSSYS.V1R5M0.INSTLIB(KIKSIT1$)`
- Controls: Table suffixes, operator ID, trace settings, region sizes

### Program Control Table (PPT)
- **Macro:** KIKPPT
- **JCL:** `KICKS.KICKSSYS.V1R5M0.INSTLIB(KIKPPT1$)`
- Defines: Programs and mapsets available to KICKS

### Task Control Table (PCT)
- **Macro:** KIKPCT
- **JCL:** `KICKS.KICKSSYS.V1R5M0.INSTLIB(KIKPCT1$)`
- Defines: Transaction IDs and their associated programs

### File Control Table (FCT)
- **Macro:** KIKFCT
- **JCL:** `KICKS.KICKSSYS.V1R5M0.INSTLIB(KIKFCT1$)`
- Defines: VSAM files accessible to KICKS programs

### Destination Control Table (DCT)
- **Macro:** KIKDCT
- **JCL:** `KICKS.KICKSSYS.V1R5M0.INSTLIB(KIKDCT1$)`
- Defines: Transient data destinations (logs, queues)

---

## Compilation Procedures

Copy these PROCs from `KICKS.KICKSSYS.V1R5M0.PROCLIB` to `SYS2.PROCLIB`:

| PROC | Purpose |
|------|---------|
| KIKASM | Assemble BMS maps |
| KIKCOB | Compile COBOL programs with KICKS preprocessor |

---

## Troubleshooting

### READY Prompt Delayed After KSSF
Press ENTER, then run a command like `TIME` or `DATE` to resync.

### TSO Session Hangs
- Check for ENQUEUE conflicts
- Verify DYNAMNBR is set to 64+

### VSAM Open Errors
- Verify catalog (UCKICKS0) is accessible
- Check volume (KICKS0) is mounted
- Ensure VSAM clusters were created successfully

### Program Not Found
- Add program/mapset to PPT
- Reassemble and relink PPT
- Restart KICKS

### Transaction Not Found
- Add transaction to PCT
- Reassemble and relink PCT
- Restart KICKS

### Userid Locked
At Hercules console: `/C U=userid`

---

## Automation Script

Use `install_kicks.py` for automated installation steps:

```bash
python install_kicks.py
```

The script handles:
- TSO login
- Job submission for DASD initialization
- Catalog creation
- XMIT file upload coordination
- Test data creation

---

## JCL Files Reference

All pre-configured JCL files are in `jcl/kicks/`:

| File | Step | Purpose |
|------|------|---------|
| `ICKDSF.jcl` | 2.3 | Initialize KICKS0 volume |
| `DEFCAT.jcl` | 3 | Create user catalog |
| `RECV370.jcl` | 4.2 | Upload XMIT file |
| `RCVKICK2.jcl` | 5 | Unpack all datasets |
| `LOADMUR.jcl` | 8.1 | Create Murach test data |
| `LOADSDB.jcl` | 8.1 | Create SDB test data |
| `LOADTAC.jcl` | 8.1 | Create TAC test data |
| `LODINTRA.jcl` | 8.2 | Create transient data queue |
| `LODTEMP.jcl` | 8.2 | Create temp storage |
| `VATLST.txt` | 2.6 | VATLST00 entry reference |

---

## References

- **Jay Moseley's Guide:** https://www.jaymoseley.com/hercules/kicks/
- **KICKS Website:** http://www.kicksfortso.com/
- **KICKS Forum:** https://groups.io/g/KICKSforTSO
- **GitHub Archive:** https://github.com/moshix/kicks
- **Moshix Video:** https://www.youtube.com/watch?v=u_ZSH9OagTM
