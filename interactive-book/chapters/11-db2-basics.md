# DB2 for z/OS

**DB2** is IBM's relational database for z/OS. It's the backbone of enterprise data management on the mainframe.

## Why DB2?

- **SQL** - Standard query language
- **ACID compliance** - Guaranteed data integrity
- **Massive scale** - Petabytes of data, thousands of users
- **Integration** - Works with CICS, IMS, batch

## DB2 Architecture

```
┌─────────────────────────────────────────┐
│              DB2 Subsystem              │
│  ┌─────────────┐  ┌─────────────┐      │
│  │   MSTR      │  │   DBM1      │      │
│  │ (System)    │  │ (Database)  │      │
│  └─────────────┘  └─────────────┘      │
│  ┌─────────────┐  ┌─────────────┐      │
│  │   DIST      │  │   IRLM      │      │
│  │ (Network)   │  │ (Locking)   │      │
│  └─────────────┘  └─────────────┘      │
└─────────────────────────────────────────┘
```

### Address Spaces

| Name | Purpose |
|------|---------|
| **MSTR** | System services, logging |
| **DBM1** | Database engine, SQL processing |
| **DIST** | Distributed connections |
| **IRLM** | Lock manager |

## SQL on z/OS

DB2 uses standard SQL:

```sql
SELECT CUST_ID, CUST_NAME, BALANCE
FROM CUSTOMER
WHERE BALANCE > 1000
ORDER BY CUST_NAME;
```

### Common SQL Statements

| Statement | Purpose |
|-----------|---------|
| `SELECT` | Query data |
| `INSERT` | Add rows |
| `UPDATE` | Modify rows |
| `DELETE` | Remove rows |
| `CREATE TABLE` | Define table |
| `GRANT` | Assign permissions |

## Embedded SQL in COBOL

COBOL programs use **embedded SQL**:

```cobol
       WORKING-STORAGE SECTION.
           EXEC SQL INCLUDE SQLCA END-EXEC.
       01 WS-CUST-ID    PIC X(5).
       01 WS-CUST-NAME  PIC X(30).
       01 WS-BALANCE    PIC S9(7)V99 COMP-3.

       PROCEDURE DIVISION.
           MOVE '00001' TO WS-CUST-ID.

           EXEC SQL
               SELECT CUST_NAME, BALANCE
               INTO :WS-CUST-NAME, :WS-BALANCE
               FROM CUSTOMER
               WHERE CUST_ID = :WS-CUST-ID
           END-EXEC.

           IF SQLCODE = 0
               DISPLAY 'CUSTOMER: ' WS-CUST-NAME
           ELSE
               DISPLAY 'NOT FOUND'
           END-IF.
```

### Host Variables

Variables prefixed with `:` are **host variables**—they exchange data between COBOL and SQL.

### SQLCA

The **SQL Communication Area** contains return codes:

| SQLCODE | Meaning |
|---------|---------|
| 0 | Success |
| 100 | Not found |
| < 0 | Error |

## DB2 Objects

### Tables
```sql
CREATE TABLE CUSTOMER (
    CUST_ID     CHAR(5) NOT NULL,
    CUST_NAME   VARCHAR(30),
    BALANCE     DECIMAL(9,2),
    PRIMARY KEY (CUST_ID)
);
```

### Indexes
```sql
CREATE INDEX CUST_NAME_IX ON CUSTOMER (CUST_NAME);
```

### Views
```sql
CREATE VIEW HIGH_BALANCE AS
    SELECT * FROM CUSTOMER WHERE BALANCE > 10000;
```

### Tablespaces
Physical storage containers for tables:
```sql
CREATE TABLESPACE CUSTTS
    IN DATABASE CUSTDB
    USING STOGROUP SYSDEFLT;
```

## DB2 Utilities

| Utility | Purpose |
|---------|---------|
| `LOAD` | Bulk load data |
| `UNLOAD` | Extract data |
| `REORG` | Reorganize tablespace |
| `RUNSTATS` | Update statistics |
| `COPY` | Image copy backup |
| `RECOVER` | Restore from backup |

### Running a Utility

```jcl
//RUNUTIL JOB (ACCT),'DB2 UTILITY'
//UTIL    EXEC DSNUPROC,SYSTEM=DB2P
//SYSIN   DD *
  LOAD DATA REPLACE
  INTO TABLE CUSTOMER
/*
//SYSREC  DD DSN=HERC01.LOAD.DATA,DISP=SHR
```

## SPUFI: SQL Processor Using File Input

**SPUFI** lets you run SQL interactively:

1. Go to DB2I (DB2 Interactive)
2. Select SPUFI
3. Enter your SQL in a dataset
4. Execute and view results

## DB2 Security

DB2 uses **GRANT/REVOKE** for permissions:

```sql
GRANT SELECT ON CUSTOMER TO PUBLIC;
GRANT UPDATE ON CUSTOMER TO USER01;
REVOKE ALL ON CUSTOMER FROM USER02;
```

DB2 also integrates with RACF for authentication.

## Try It: Query a Table

In SPUFI or a COBOL program:
```sql
SELECT * FROM SYSIBM.SYSTABLES
WHERE CREATOR = 'HERC01'
FETCH FIRST 10 ROWS ONLY;
```

This shows tables owned by HERC01.
