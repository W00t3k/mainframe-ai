# COBOL Basics

**COBOL** (Common Business-Oriented Language) is the primary programming language of the mainframe. Written in 1959, it still processes trillions of dollars in transactions daily.

## Why COBOL?

- **95%** of ATM transactions use COBOL
- **80%** of in-person retail transactions
- **Over 200 billion lines** of COBOL in production
- Banks, insurance, government all depend on it

COBOL was designed to be readable—like English.

## COBOL Program Structure

Every COBOL program has four **divisions**:

```cobol
       IDENTIFICATION DIVISION.
       PROGRAM-ID. HELLO.
      *
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       INPUT-OUTPUT SECTION.
      *
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-MESSAGE    PIC X(20) VALUE 'HELLO MAINFRAME'.
      *
       PROCEDURE DIVISION.
           DISPLAY WS-MESSAGE.
           STOP RUN.
```

### The Four Divisions

| Division | Purpose |
|----------|---------|
| `IDENTIFICATION` | Program name and metadata |
| `ENVIRONMENT` | Hardware and file definitions |
| `DATA` | Variables and data structures |
| `PROCEDURE` | Executable code (the logic) |

## Column Layout

COBOL uses fixed columns (from punch card days):

| Columns | Purpose |
|---------|---------|
| 1-6 | Sequence numbers (optional) |
| 7 | Indicator (`*` = comment, `-` = continuation) |
| 8-11 | Area A (division/section/paragraph names) |
| 12-72 | Area B (statements) |
| 73-80 | Identification (ignored) |

## Data Definitions

Variables are defined with **PICTURE** clauses:

```cobol
       01 WS-CUSTOMER-RECORD.
          05 WS-CUST-ID      PIC 9(5).
          05 WS-CUST-NAME    PIC X(30).
          05 WS-BALANCE      PIC S9(7)V99.
          05 WS-ACTIVE       PIC X VALUE 'Y'.
```

### PICTURE Symbols

| Symbol | Meaning |
|--------|---------|
| `9` | Numeric digit |
| `X` | Alphanumeric character |
| `A` | Alphabetic character |
| `V` | Implied decimal point |
| `S` | Sign (positive/negative) |
| `(n)` | Repeat n times |

Examples:
- `PIC 9(5)` = 5 digits (00000-99999)
- `PIC X(20)` = 20 characters
- `PIC S9(5)V99` = Signed, 5 digits, 2 decimal places

## Basic Statements

### MOVE
```cobol
MOVE 'JOHN DOE' TO WS-CUST-NAME.
MOVE 12345 TO WS-CUST-ID.
```

### COMPUTE
```cobol
COMPUTE WS-TOTAL = WS-PRICE * WS-QUANTITY.
COMPUTE WS-TAX = WS-TOTAL * 0.08.
```

### IF/ELSE
```cobol
IF WS-BALANCE > 1000
    DISPLAY 'HIGH BALANCE'
ELSE
    DISPLAY 'NORMAL BALANCE'
END-IF.
```

### PERFORM
```cobol
PERFORM PROCESS-RECORD.
PERFORM PROCESS-RECORD 10 TIMES.
PERFORM PROCESS-RECORD UNTIL WS-EOF = 'Y'.
```

## File Handling

### File Definition (DATA DIVISION)
```cobol
       FILE SECTION.
       FD CUSTOMER-FILE.
       01 CUSTOMER-RECORD.
          05 CUST-ID        PIC 9(5).
          05 CUST-NAME      PIC X(30).
          05 CUST-BALANCE   PIC S9(7)V99.
```

### File Operations (PROCEDURE DIVISION)
```cobol
       OPEN INPUT CUSTOMER-FILE.
       READ CUSTOMER-FILE INTO WS-RECORD
           AT END SET WS-EOF TO TRUE
       END-READ.
       CLOSE CUSTOMER-FILE.
```

## Compile and Run

### JCL to Compile COBOL
```jcl
//COMPILE JOB (ACCT),'COMPILE COBOL'
//STEP1   EXEC IGYWCL
//COBOL.SYSIN DD DSN=HERC01.COBOL.SOURCE(MYPROG),DISP=SHR
//LKED.SYSLMOD DD DSN=HERC01.LOAD(MYPROG),DISP=SHR
```

### JCL to Run
```jcl
//RUN     JOB (ACCT),'RUN PROGRAM'
//STEP1   EXEC PGM=MYPROG
//STEPLIB DD DSN=HERC01.LOAD,DISP=SHR
//CUSTFILE DD DSN=HERC01.CUSTOMER.DATA,DISP=SHR
//SYSOUT  DD SYSOUT=*
```

## Try It: Your First COBOL Program

1. Create a new member in your source library
2. Enter this code:
```cobol
       IDENTIFICATION DIVISION.
       PROGRAM-ID. HELLO.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-MSG PIC X(30) VALUE 'HELLO FROM COBOL'.
       PROCEDURE DIVISION.
           DISPLAY WS-MSG.
           STOP RUN.
```
3. Submit the compile JCL
4. Check for errors in SDSF
5. Run the program and view output

Ask BigIron if you get stuck with compiler errors!
