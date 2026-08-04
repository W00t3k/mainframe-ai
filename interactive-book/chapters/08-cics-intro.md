# Introduction to CICS

**CICS** (Customer Information Control System) is the mainframe's transaction processing monitor. It handles online, real-time workloads—the opposite of batch.

## What is CICS?

When you use an ATM, book a flight, or check your bank balance, CICS is often processing that transaction. CICS provides:

- **Transaction management** - Handle thousands of concurrent users
- **Terminal handling** - Manage 3270 screens
- **Data access** - Connect to VSAM, DB2, IMS
- **Security** - Integrate with RACF
- **Recovery** - Ensure transaction integrity

## CICS Architecture

```
┌─────────────────────────────────────────┐
│              CICS Region                │
│  ┌──────────┐  ┌──────────┐            │
│  │ Terminal │  │ Terminal │  ...       │
│  │  Task    │  │  Task    │            │
│  └────┬─────┘  └────┬─────┘            │
│       │             │                   │
│  ┌────┴─────────────┴────┐             │
│  │   Transaction Manager  │             │
│  └────────────┬──────────┘             │
│               │                         │
│  ┌────────────┴──────────┐             │
│  │    Application Pool    │             │
│  │  (COBOL, Assembler)   │             │
│  └────────────┬──────────┘             │
│               │                         │
│  ┌────────────┴──────────┐             │
│  │   File/DB Access      │             │
│  │  (VSAM, DB2, IMS)     │             │
│  └───────────────────────┘             │
└─────────────────────────────────────────┘
```

## Key CICS Concepts

### Transactions
A **transaction** is a unit of work identified by a 4-character code:
```
INQU  - Inquiry transaction
MENU  - Menu transaction
XFER  - Transfer transaction
```

Users invoke transactions by typing the code at a terminal.

### Programs
Transactions run **programs** written in COBOL, Assembler, C, or other languages. The transaction-to-program mapping is defined in the CSD (CICS System Definition).

### Tasks
When a user enters a transaction, CICS creates a **task**—an instance of the transaction running for that user.

## CICS Commands

CICS has its own command language. In COBOL:
```cobol
EXEC CICS
    RECEIVE MAP('MENUMAP')
            MAPSET('MENUSET')
            INTO(WS-INPUT-DATA)
END-EXEC.

EXEC CICS
    SEND MAP('MENUMAP')
         MAPSET('MENUSET')
         FROM(WS-OUTPUT-DATA)
         ERASE
END-EXEC.
```

### Common EXEC CICS Commands

| Command | Purpose |
|---------|---------|
| `RECEIVE` | Get input from terminal |
| `SEND` | Send output to terminal |
| `READ` | Read a file record |
| `WRITE` | Write a file record |
| `LINK` | Call another program |
| `XCTL` | Transfer to another program |
| `RETURN` | End the task |

## CICS Master Terminal (CEMT)

**CEMT** is the operator interface to CICS:

```
CEMT I TASK          - Inquire on tasks
CEMT I TRAN          - Inquire on transactions
CEMT I PROG          - Inquire on programs
CEMT I FILE          - Inquire on files
CEMT S TRAN(xxxx) DI - Disable a transaction
CEMT S FILE(xxxx) OP - Open a file
```

## CICS Security

CICS integrates with RACF for security:

| RACF Class | Protects |
|------------|----------|
| `TCICSTRN` | Transactions |
| `PCICSPSB` | PSBs (IMS) |
| `FCICSFCT` | Files |
| `JCICSJCT` | Journals |

Example: Protect transaction XFER:
```
RDEFINE TCICSTRN XFER UACC(NONE)
PERMIT XFER CLASS(TCICSTRN) ID(TELLERS) ACCESS(READ)
```

## BMS: Basic Mapping Support

**BMS** handles screen formatting. Maps define screen layouts:

```
MENUMAP  DFHMSD TYPE=&SYSPARM,MODE=INOUT,LANG=COBOL
MENU     DFHMDI SIZE=(24,80),LINE=1,COLUMN=1
         DFHMDF POS=(1,30),LENGTH=20,INITIAL='MAIN MENU'
         DFHMDF POS=(5,10),LENGTH=30,ATTRB=(UNPROT,IC)
         DFHMSD TYPE=FINAL
```

## Try It: CICS on TK5

TK5 includes **KICKS**—a CICS-like environment. From TSO:
```
CICS
```

This starts a CICS session. Try:
- `CESN` - Sign on
- `CEMT I TRAN` - List transactions
- `CESF` - Sign off
