# KICKS Installation Guide for MVS 3.8j TK5

KICKS is a CICS-compatible transaction processing system for MVS 3.8j. This guide covers installation on TK5.

## Prerequisites

- MVS 3.8j TK5 running on Hercules
- Access to Hercules console
- TSO access with HERC01 or similar privileged userid

## Quick Reference

| Item | Value |
|------|-------|
| KICKS Version | 1.5.0 |
| DASD Volume | KICKS0 |
| User Catalog | UCKICKS0 |
| HLQ | KICKS |
| Download | https://github.com/moshix/kicks |

## Step 1: Download KICKS

```bash
wget https://github.com/moshix/kicks/archive/master.zip
unzip master.zip
# Extract kicks-tso-v1r5m0 folder
```

## Step 2: Prepare DASD Volume

### Create 3350 DASD image
```
dasdinit -a kicks0.3350 3350 111111
```

### Attach to Hercules
```
attach 351 3350 dasd/kicks0.3350
```

### Initialize with ICKDSF
Submit `jcl/kicks/ICKDSF.jcl`

### Mount volume
```
v 351,online
m 351,vol=(sl,kicks0),use=private
```

### Add to VATLST00
Edit `SYS1.PARMLIB(VATLST00)`:
```
KICKS0,0,2,3350    ,N        KICKS LIBRARIES/DATA (PRIVATE)
```

## Step 3: Create User Catalog

Submit `jcl/kicks/DEFCAT.jcl` to create UCKICKS0 user catalog with KICKS alias.

## Step 4: Upload XMIT File

Use RECV370 to upload `kicks-tso-v1r5m0.xmi`:

```
devinit 01c /path/to/kicks-tso-v1r5m0.xmi ebcdic
```

Submit `jcl/kicks/RECV370.jcl`

## Step 5: Unpack Installation Datasets

Edit and submit `KICKS.V1R5M0.INSTALL(V1R5M0)` with these changes:
- Change CLASS=A, MSGCLASS=X
- Add JOBLIB for SYSC.LINKLIB
- Change UID=KICKS
- Change DSN to KICKS.V1R5M0.INSTALL
- Add VOL=SER=KICKS0

## Step 6: Customize KICKS

### Increase DYNAMNBR
Edit `SYS1.PROCLIB(IKJACCNT)`:
```
DYNAMNBR=64
```

### Run KFIX CLIST
```
PROFILE PREFIX(KICKS)
EXEC 'KICKS.KICKSSYS.V1R5M0.CLIST(KFIX)'
```
Select HLQ: KICKS

## Step 7: Create Test Data

Submit these jobs from `KICKS.KICKS.V1R5M0.INSTLIB`:
- LOADMUR
- LOADSDB  
- LOADTAC

Submit these jobs from `KICKS.KICKSSYS.V1R5M0.INSTLIB`:
- LODINTRA
- LODTEMP

## Step 8: Fix KICKS CLIST

Edit `KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)` line 145:
Remove the line `'&KIKID..KICKS.&VER..SKIKLOAD' +`

Optionally change TCP parameter to `TCP(1$)` for better terminal support.

## Step 9: Start KICKS

```
EXEC 'KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)'
```

Press ENTER to see the KICKS banner. Use:
- **CLEAR** then transaction code to run transactions
- **KSSF** to sign off and shutdown KICKS

## Demo Transactions

| Trans | Description |
|-------|-------------|
| KSGM | Good morning (startup) |
| KSSF | Sign off |
| INQ1 | Customer inquiry |
| MNT1 | Customer maintenance |
| ORD1 | Order entry |

## Troubleshooting

- **READY prompt delayed**: Press ENTER, run TIME command
- **Userid locked**: Use `/C U=userid` at Hercules console
- **VSAM errors**: Check catalog and volume assignments
