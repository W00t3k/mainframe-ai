# JES and Batch Processing

**JES** (Job Entry Subsystem) manages batch job execution on z/OS. Most mainframe workloads are batch—scheduled jobs that run without user interaction.

## What is Batch Processing?

Batch processing runs jobs in sequence, typically:
- Overnight payroll runs
- End-of-day bank reconciliation
- Monthly billing cycles
- Data warehouse loads

Unlike interactive work, batch jobs:
- Run unattended
- Process large volumes of data
- Are scheduled to run at specific times
- Produce output to spool or datasets

## JES2 vs JES3

z/OS supports two job entry subsystems:

| Feature | JES2 | JES3 |
|---------|------|------|
| Job scheduling | Decentralized | Centralized |
| Complexity | Simpler | More complex |
| Control | Per-system | Sysplex-wide |
| Usage | More common | Large shops |

Most installations use **JES2**.

## Job Flow

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  INPUT  │───>│ EXECUTE │───>│ OUTPUT  │───>│  PURGE  │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
   JCL read      Job runs      SYSOUT to      Job removed
   Job queued                   spool          from system
```

1. **Input**: JES reads JCL, assigns job number
2. **Execute**: Job runs in an initiator
3. **Output**: SYSOUT written to spool
4. **Purge**: Job removed after output processed

## JES2 Commands

JES2 commands start with `$`:

| Command | Description |
|---------|-------------|
| `$D A` | Display active jobs |
| `$D Q` | Display job queues |
| `$D INITDEF` | Display initiator definitions |
| `$D PROCLIB` | Display procedure libraries |
| `$P Jnnnnn` | Purge a job |
| `$C Jnnnnn` | Cancel a job |

## Initiators

**Initiators** are address spaces that execute batch jobs. Each initiator:
- Handles one job at a time
- Is assigned to specific job classes
- Runs jobs in priority order

```
$D INIT,INIT1
INIT1 - CLASS=A,B,C  STATUS=ACTIVE  JOB=PAYROLL1
```

## Job Classes

Jobs are assigned to **classes** (A-Z, 0-9). Classes control:
- Which initiators can run the job
- Priority relative to other jobs
- Resource limits

```jcl
//MYJOB JOB (ACCT),'DESC',CLASS=A
```

## Output Classes (MSGCLASS/SYSOUT)

Output classes control where job output goes:

```jcl
//MYJOB JOB (ACCT),'DESC',MSGCLASS=X
//STEP1 EXEC PGM=MYPROG
//SYSOUT DD SYSOUT=A
```

| Class | Typical Use |
|-------|-------------|
| A | Print to printer |
| H | Hold for viewing |
| X | Delete after job |

## Viewing Job Output in SDSF

1. Enter `ST` (status) in SDSF
2. Find your job in the list
3. Type `?` next to it to see output datasets
4. Type `S` next to a dataset to view it

## Try It: Submit and Monitor a Job

Create this JCL:
```jcl
//TESTJOB JOB (ACCT),'TEST',MSGCLASS=H,NOTIFY=&SYSUID
//STEP1 EXEC PGM=IEFBR14
//SYSPRINT DD SYSOUT=*
```

Submit it:
```
SUBMIT 'HERC01.JCL.CNTL(TESTJOB)'
```

Check status in SDSF:
```
=S
ST
```

Look for your job and view its output.
