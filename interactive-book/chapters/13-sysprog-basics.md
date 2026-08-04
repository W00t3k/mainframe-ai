# System Programming Basics

**System programmers** (sysprogs) install, configure, and maintain z/OS. They're the architects and caretakers of the mainframe.

## What Sysprogs Do

- Install z/OS and products
- Configure system parameters (PARMLIB)
- Manage storage (SMS)
- Performance tuning
- Problem diagnosis
- Apply maintenance (PTFs)

## Key System Datasets

### SYS1.PARMLIB
System configuration parameters. Searched at IPL.

| Member | Purpose |
|--------|---------|
| `IEASYSxx` | System parameters |
| `SMFPRMxx` | SMF recording options |
| `PROGxx` | APF/LINKLIST definitions |
| `COMMNDxx` | IPL commands |
| `LOADxx` | System load parameters |

### SYS1.PROCLIB
JCL procedures for started tasks:
- `JES2` - Job entry subsystem
- `VTAM` - Network
- `RACF` - Security
- `TCPIP` - TCP/IP stack

### SYS1.LINKLIB
System programs and utilities.

### SYS1.LPALIB
Link Pack Area - shared modules loaded at IPL.

## IPL Process

**IPL** (Initial Program Load) boots z/OS:

```
1. Hardware loads IPL text from IODF
2. Nucleus loaded from SYS1.NUCLEUS
3. Master Scheduler initializes
4. IEASYSxx parameters processed
5. Started tasks begin (JES2, VTAM, RACF)
6. System ready for work
```

### IPL Parameters

```
SYSP=xx    - Use IEASYSxx member
LOAD=xx    - Use LOADxx member
CLPA       - Create new LPA
```

## Console Commands

### Display Commands

| Command | Shows |
|---------|-------|
| `D IPLINFO` | IPL information |
| `D SYMBOLS` | System symbols |
| `D M=CPU` | CPU status |
| `D A,L` | Active address spaces |
| `D PROG,APF` | APF authorized libraries |
| `D PROG,LNK` | LINKLIST |
| `D SMS` | SMS configuration |

### System Control

| Command | Action |
|---------|--------|
| `S procname` | Start a task |
| `P procname` | Stop a task |
| `C jobname` | Cancel a job |
| `VARY dev,ONLINE` | Bring device online |
| `SETPROG` | Dynamic APF/LINKLIST |

## APF Authorization

**APF** (Authorized Program Facility) allows programs to use privileged services.

### Display APF List
```
D PROG,APF
```

### Dynamic APF Update (PROGxx)
```
APF ADD DSNAME(MY.LOADLIB) VOLUME(VOL001)
```

### SETPROG Command
```
SETPROG APF,ADD,DSNAME=MY.LOADLIB,VOLUME=VOL001
```

## LINKLIST

**LINKLIST** is the search path for program loads.

### Display LINKLIST
```
D PROG,LNK
```

### Dynamic Update
```
SETPROG LNKLST,ADD,NAME=LNKNAME,DSNAME=MY.LINKLIB
SETPROG LNKLST,ACTIVATE,NAME=LNKNAME
```

## SMS: Storage Management Subsystem

SMS automates dataset allocation:

| Class | Controls |
|-------|----------|
| **Data Class** | DCB attributes, space |
| **Storage Class** | Performance, availability |
| **Management Class** | Migration, backup |
| **Storage Group** | Volume pools |

### ACS Routines
Automatic Class Selection - rules that assign classes based on dataset name, user, etc.

## SMP/E: System Modification Program

SMP/E installs and maintains software:

| Command | Purpose |
|---------|---------|
| `RECEIVE` | Load PTF from tape/network |
| `APPLY` | Install to target libraries |
| `ACCEPT` | Make permanent |
| `RESTORE` | Back out changes |

### PTF Flow
```
IBM ships PTF → RECEIVE → APPLY (test) → ACCEPT (permanent)
```

## Problem Diagnosis

### Dumps
- **SYSUDUMP** - User dumps
- **SYSMDUMP** - Machine-readable
- **SYSABEND** - Full dump

### IPCS (Interactive Problem Control System)
Tool for analyzing dumps:
```
IPCS
SELECT DUMP
SUMMARY
WHERE
```

### LOGREC
Error recording dataset for hardware/software errors.

### SMF Records
System Management Facilities - audit and performance data.

## Try It: Display Commands

Connect to TK5 console (port 8038) and try:
```
/D IPLINFO
/D SYMBOLS
/D A,L
/D PROG,APF
```

Or from TSO (SDSF), enter these on the command line prefixed with `/`.
