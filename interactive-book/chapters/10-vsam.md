# VSAM: Virtual Storage Access Method

**VSAM** is the primary file management system for z/OS applications. It provides high-performance, indexed access to data.

## Why VSAM?

Unlike sequential files, VSAM provides:
- **Indexed access** - Read records by key
- **Random access** - Jump directly to any record
- **High performance** - Optimized for disk I/O
- **Data integrity** - Built-in protection

Most CICS applications use VSAM files.

## VSAM Dataset Types

### KSDS (Key-Sequenced Data Set)
Records accessed by a **primary key**. Most common type.

```
┌─────────────────────────────────────┐
│ KEY    │ DATA                       │
├────────┼────────────────────────────┤
│ 00001  │ SMITH, JOHN, 123 MAIN ST   │
│ 00002  │ JONES, MARY, 456 OAK AVE   │
│ 00003  │ BROWN, BOB, 789 ELM DR     │
└────────┴────────────────────────────┘
```

- Records stored in key sequence
- Can read sequentially or by key
- Supports alternate indexes

### ESDS (Entry-Sequenced Data Set)
Records in **arrival order** only. Like an append-only log.

```
Record 1 ──► Record 2 ──► Record 3 ──► Record 4
```

- No keys—records accessed by relative byte address (RBA)
- Good for logs, journals, audit trails
- Cannot delete individual records

### RRDS (Relative Record Data Set)
Records accessed by **slot number**. Fixed slots.

```
┌──────┬──────┬──────┬──────┬──────┐
│ [1]  │ [2]  │ [3]  │ [4]  │ [5]  │
│ DATA │ empty│ DATA │ DATA │ empty│
└──────┴──────┴──────┴──────┴──────┘
```

- Slots can be empty or occupied
- Good for table lookups by position

### LDS (Linear Data Set)
Raw byte-addressable storage. Used for special applications like DB2.

## VSAM Components

A KSDS has three components:

| Component | Purpose |
|-----------|---------|
| **Cluster** | The logical dataset name |
| **Data** | Contains the actual records |
| **Index** | Contains keys for lookup |

```
MY.VSAM.CLUSTER
  ├── MY.VSAM.CLUSTER.DATA
  └── MY.VSAM.CLUSTER.INDEX
```

## Creating VSAM with IDCAMS

**IDCAMS** is the utility for VSAM operations:

```jcl
//DEFVSAM  JOB (ACCT),'CREATE VSAM'
//STEP1    EXEC PGM=IDCAMS
//SYSPRINT DD SYSOUT=*
//SYSIN    DD *
  DEFINE CLUSTER(                          -
           NAME(HERC01.CUSTOMER.VSAM)      -
           INDEXED                          -
           KEYS(5 0)                        -
           RECORDSIZE(100 100)             -
           CYLINDERS(1 1)                  -
         )                                  -
         DATA(NAME(HERC01.CUSTOMER.DATA)) -
         INDEX(NAME(HERC01.CUSTOMER.INDEX))
/*
```

### Key Parameters

| Parameter | Meaning |
|-----------|---------|
| `INDEXED` | Create a KSDS |
| `KEYS(5 0)` | 5-byte key starting at position 0 |
| `RECORDSIZE(100 100)` | Average and max record size |
| `CYLINDERS(1 1)` | Primary and secondary allocation |

## IDCAMS Commands

### DEFINE - Create VSAM
```
DEFINE CLUSTER(NAME(MY.VSAM) INDEXED KEYS(5 0))
```

### DELETE - Remove VSAM
```
DELETE MY.VSAM.CLUSTER CLUSTER
```

### REPRO - Copy Data
```
REPRO INFILE(INPUT) OUTFILE(OUTPUT)
```

### LISTCAT - Show Catalog Info
```
LISTCAT ENTRIES(MY.VSAM.CLUSTER) ALL
```

### PRINT - Display Records
```
PRINT INFILE(VSAMIN) CHARACTER
```

## VSAM in COBOL

### File Definition
```cobol
       SELECT CUSTOMER-FILE ASSIGN TO CUSTVSAM
              ORGANIZATION IS INDEXED
              ACCESS MODE IS DYNAMIC
              RECORD KEY IS CUST-ID
              FILE STATUS IS WS-FILE-STATUS.
```

### Reading by Key
```cobol
MOVE '00001' TO CUST-ID.
READ CUSTOMER-FILE INTO WS-RECORD
    INVALID KEY DISPLAY 'NOT FOUND'
END-READ.
```

### Writing a Record
```cobol
WRITE CUSTOMER-RECORD FROM WS-RECORD
    INVALID KEY DISPLAY 'DUPLICATE KEY'
END-WRITE.
```

### Updating a Record
```cobol
REWRITE CUSTOMER-RECORD FROM WS-RECORD
    INVALID KEY DISPLAY 'UPDATE FAILED'
END-REWRITE.
```

## Try It: Create and Load VSAM

1. Define the VSAM cluster with IDCAMS
2. Create a sequential file with test data
3. Use REPRO to load the data
4. Use PRINT to verify the contents

```jcl
//LOADVSAM JOB (ACCT),'LOAD VSAM'
//STEP1    EXEC PGM=IDCAMS
//INPUT    DD DSN=HERC01.TEST.DATA,DISP=SHR
//OUTPUT   DD DSN=HERC01.CUSTOMER.VSAM,DISP=SHR
//SYSPRINT DD SYSOUT=*
//SYSIN    DD *
  REPRO INFILE(INPUT) OUTFILE(OUTPUT)
/*
```

Ask BigIron about VSAM errors—they can be cryptic!
