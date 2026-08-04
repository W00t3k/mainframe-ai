# JCL Basics

**JCL** (Job Control Language) tells z/OS what to run and how to run it. Every batch job needs JCL.

## JCL Structure

JCL has three main statement types:

```jcl
//MYJOB   JOB  (ACCT),'MY JOB',CLASS=A,MSGCLASS=X
//STEP1   EXEC PGM=IEFBR14
//DD1     DD   DSN=MY.NEW.FILE,DISP=(NEW,CATLG)
```

### JOB Statement
Identifies the job and sets job-level parameters:
```jcl
//MYJOB JOB (ACCT),'DESCRIPTION',
//          CLASS=A,          Job class
//          MSGCLASS=X,       Output class
//          NOTIFY=&SYSUID    Notify when done
```

### EXEC Statement
Executes a program or procedure:
```jcl
//STEP1 EXEC PGM=IEFBR14      Run a program
//STEP2 EXEC PROC=MYPROC      Run a procedure
```

### DD Statement
Defines data—connects datasets to program I/O:
```jcl
//INPUT  DD DSN=MY.INPUT.FILE,DISP=SHR
//OUTPUT DD DSN=MY.OUTPUT.FILE,DISP=(NEW,CATLG),
//          SPACE=(CYL,(10,5)),UNIT=SYSDA
//SYSOUT DD SYSOUT=*
```

## The DISP Parameter

DISP (disposition) controls what happens to datasets:

```
DISP=(status,normal-end,abnormal-end)
```

| Status | Meaning |
|--------|---------|
| NEW | Create new dataset |
| OLD | Exclusive access to existing |
| SHR | Shared access to existing |
| MOD | Append to existing (or create) |

| Normal End | Meaning |
|------------|---------|
| KEEP | Keep the dataset |
| DELETE | Delete the dataset |
| CATLG | Catalog the dataset |
| UNCATLG | Remove from catalog |

Example: `DISP=(NEW,CATLG,DELETE)` means:
- Create new dataset
- Catalog it if job succeeds
- Delete it if job fails

## Your First Job

Here's a simple job that does nothing (IEFBR14 is a "do nothing" program):

```jcl
//TESTJOB JOB (ACCT),'TEST',MSGCLASS=X,NOTIFY=&SYSUID
//*
//* This job allocates a new dataset
//*
//STEP1   EXEC PGM=IEFBR14
//NEWFILE DD  DSN=HERC01.TEST.DATA,
//            DISP=(NEW,CATLG,DELETE),
//            SPACE=(TRK,(5,1)),
//            DCB=(RECFM=FB,LRECL=80,BLKSIZE=3200)
```

## Try It: Submit a Job

1. Connect to TK5 and log in
2. Go to ISPF option 3.4 (Dataset List)
3. Edit a member in your JCL library
4. Type `SUBMIT` on the command line

Or from TSO:
```
SUBMIT 'HERC01.JCL.CNTL(TESTJOB)'
```

Check job output with:
```
STATUS TESTJOB
```

## Common Programs

| Program | Purpose |
|---------|---------|
| IEFBR14 | Do nothing (allocate datasets) |
| IEBGENER | Copy sequential datasets |
| IEBCOPY | Copy PDS members |
| IDCAMS | VSAM utility |
| SORT | Sort/merge data |
