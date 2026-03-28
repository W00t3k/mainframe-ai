//BOFDEMO  JOB (ACCT),'BOF DEMO',CLASS=A,MSGCLASS=A,
//         USER=HERC01,PASSWORD=CUL8TR,MSGLEVEL=(1,1)
//*
//* ================================================================
//* BUFFER OVERFLOW DEMONSTRATION - MVS 3.8j
//* ================================================================
//* This JCL assembles and link-edits a vulnerable program that
//* demonstrates a classic stack buffer overflow on a mainframe.
//*
//* The program:
//*   1. Reads input from SYSIN (up to 256 bytes)
//*   2. Copies it into a 24-byte buffer WITHOUT length checking
//*   3. Prints "HELLO <input>"
//*
//* When input exceeds 24 bytes, the save area (registers) get
//* overwritten — the MVS equivalent of smashing the stack.
//*
//* S0C4 (protection exception) = the mainframe SIGSEGV
//*
//* SAFE: This runs in a batch job address space. It cannot damage
//* the system — the ABEND is caught by MVS and the job terminates.
//* ================================================================
//*
//* STEP 1: ASSEMBLE THE VULNERABLE PROGRAM
//*
//ASM      EXEC PGM=IFOX00,PARM='DECK,LOAD'
//SYSLIB   DD DSN=SYS1.MACLIB,DISP=SHR
//SYSUT1   DD UNIT=SYSDA,SPACE=(CYL,(5,5))
//SYSUT2   DD UNIT=SYSDA,SPACE=(CYL,(5,5))
//SYSUT3   DD UNIT=SYSDA,SPACE=(CYL,(5,5))
//SYSPUNCH DD DSN=&&OBJMOD,DISP=(,PASS),UNIT=SYSDA,
//         SPACE=(TRK,(5,5))
//SYSGO    DD DSN=&&LOADMOD,DISP=(,PASS),UNIT=SYSDA,
//         SPACE=(TRK,(5,5))
//SYSPRINT DD SYSOUT=*
//SYSIN    DD *
***********************************************************************
* BOFVULN - BUFFER OVERFLOW VULNERABLE PROGRAM                       *
*                                                                     *
* THIS PROGRAM DEMONSTRATES A CLASSIC BUFFER OVERFLOW.                *
* IT READS INPUT INTO A 24-BYTE BUFFER WITHOUT LENGTH CHECKING.       *
*                                                                     *
* ON MVS, THE SAVE AREA CHAIN REPLACES THE STACK:                     *
*   - R13 POINTS TO THE CURRENT SAVE AREA (72 BYTES)                  *
*   - R14 = RETURN ADDRESS                                            *
*   - R15 = ENTRY POINT                                               *
*   - R0-R12 = SAVED REGISTERS                                        *
*                                                                     *
* WHEN THE BUFFER OVERFLOWS, IT OVERWRITES THE SAVE AREA,             *
* CORRUPTING R14 (RETURN ADDRESS) AND OTHER REGISTERS.                *
*                                                                     *
* THE RESULT: S0C4 (PROTECTION EXCEPTION) WHEN THE FUNCTION           *
* TRIES TO RETURN - IDENTICAL CONCEPT TO A MODERN STACK OVERFLOW.     *
***********************************************************************
         SPACE 2
BOFVULN  CSECT
         SPACE 1
* STANDARD MVS ENTRY LINKAGE
         STM   R14,R12,12(R13)     SAVE CALLER REGISTERS
         LR    R12,R15             SET BASE REGISTER
         USING BOFVULN,R12         ESTABLISH ADDRESSABILITY
         LA    R11,SAVEAREA        POINT TO OUR SAVE AREA
         ST    R13,4(R11)          CHAIN BACKWARD
         ST    R11,8(R13)          CHAIN FORWARD
         LR    R13,R11             R13 -> OUR SAVE AREA
         SPACE 1
* OPEN INPUT AND OUTPUT FILES
         OPEN  (INDCB,(INPUT))
         OPEN  (OUTDCB,(OUTPUT))
         SPACE 1
* READ INPUT - THIS IS WHERE THE VULNERABILITY IS
* WE READ UP TO 256 BYTES BUT OUR BUFFER IS ONLY 24 BYTES
         GET   INDCB,INBUF         READ FULL 80-BYTE CARD
         SPACE 1
* VULNERABLE COPY: MOVE INPUT INTO SMALL BUFFER
* MVC COPIES EXACTLY THE LENGTH SPECIFIED - NO BOUNDS CHECK
* THIS COPIES 80 BYTES INTO A 24-BYTE AREA
* BYTES 25-80 OVERWRITE WHATEVER IS ADJACENT IN MEMORY
         MVC   SMALLBUF(80),INBUF  *** OVERFLOW: 80 INTO 24 ***
         SPACE 1
* BUILD OUTPUT MESSAGE
         MVC   OUTMSG(6),=C'HELLO '
         MVC   OUTMSG+6(24),SMALLBUF  COPY (SAFE) PORTION
         PUT   OUTDCB,OUTMSG       WRITE OUTPUT
         SPACE 1
* CLOSE FILES
         CLOSE (INDCB)
         CLOSE (OUTDCB)
         SPACE 1
* STANDARD MVS EXIT LINKAGE
* IF SAVE AREA WAS CORRUPTED, THIS IS WHERE S0C4 OCCURS
         L     R13,4(R13)          RESTORE CALLER SAVE AREA
         LM    R14,R12,12(R13)     RESTORE REGISTERS (CORRUPTED!)
         SR    R15,R15             SET RC=0
         BR    R14                 RETURN (TO CORRUPTED ADDRESS!)
         SPACE 2
***********************************************************************
* DATA AREAS                                                          *
***********************************************************************
         SPACE 1
SAVEAREA DS    18F                 OUR SAVE AREA (72 BYTES)
         SPACE 1
* THE VULNERABLE BUFFER - ONLY 24 BYTES
SMALLBUF DS    CL24               *** ONLY 24 BYTES ***
         SPACE 1
* OVERFLOW CANARY - IF WE SEE THIS CORRUPTED, OVERFLOW OCCURRED
CANARY   DC    C'DEADBEEF'        CANARY VALUE (8 BYTES)
         SPACE 1
* ADJACENT MEMORY THAT GETS OVERWRITTEN
ADJDATA  DS    CL48               ADJACENT DATA AREA
         SPACE 1
* FULL INPUT BUFFER (80 BYTES - MVS CARD IMAGE)
INBUF    DS    CL80               FULL 80-BYTE INPUT BUFFER
         SPACE 1
* OUTPUT MESSAGE BUFFER
OUTMSG   DS    CL80               OUTPUT BUFFER
         SPACE 1
* INPUT DCB
INDCB    DCB   DDNAME=SYSIN,DSORG=PS,MACRF=GM,                        X
               RECFM=FB,LRECL=80,BLKSIZE=800,EODAD=EOF
         SPACE 1
* OUTPUT DCB
OUTDCB   DCB   DDNAME=SYSPRINT,DSORG=PS,MACRF=PM,                     X
               RECFM=FBA,LRECL=133,BLKSIZE=1330
         SPACE 1
EOF      CLOSE (INDCB)
         CLOSE (OUTDCB)
         L     R13,4(R13)
         LM    R14,R12,12(R13)
         SR    R15,R15
         BR    R14
         SPACE 1
* REGISTER EQUATES
R0       EQU   0
R1       EQU   1
R2       EQU   2
R3       EQU   3
R4       EQU   4
R5       EQU   5
R6       EQU   6
R7       EQU   7
R8       EQU   8
R9       EQU   9
R10      EQU   10
R11      EQU   11
R12      EQU   12
R13      EQU   13
R14      EQU   14
R15      EQU   15
         END   BOFVULN
/*
//*
//* STEP 2: LINK-EDIT INTO A LOAD MODULE
//*
//LKED     EXEC PGM=IEWL,PARM='LIST,XREF',COND=(8,LT,ASM)
//SYSLIN   DD DSN=&&LOADMOD,DISP=(OLD,DELETE)
//SYSLMOD  DD DSN=HERC01.LOADLIB(BOFVULN),DISP=SHR
//SYSUT1   DD UNIT=SYSDA,SPACE=(CYL,(5,5))
//SYSPRINT DD SYSOUT=*
//*
//* ================================================================
//* STEP 3: RUN WITH SAFE INPUT (SHOULD WORK NORMALLY)
//* ================================================================
//*
//SAFE     EXEC PGM=BOFVULN,COND=(8,LT,LKED)
//STEPLIB  DD DSN=HERC01.LOADLIB,DISP=SHR
//SYSPRINT DD SYSOUT=*
//SYSIN    DD *
SHORT INPUT - SAFE
/*
//*
//* ================================================================
//* STEP 4: RUN WITH OVERFLOW INPUT (WILL CAUSE S0C4 ABEND)
//* ================================================================
//*
//CRASH    EXEC PGM=BOFVULN,COND=(8,LT,LKED)
//STEPLIB  DD DSN=HERC01.LOADLIB,DISP=SHR
//SYSPRINT DD SYSOUT=*
//SYSIN    DD *
AAAAAAAAAAAAAAAAAAAAAAAABBBBBBBBBBBBBBBBCCCCCCCCCCCCCCCCDDDDDDDDDDDDDDDD
/*
//*
//* ================================================================
//* EXPECTED RESULTS:
//*
//* STEP SAFE:  RC=0000, Output: "HELLO SHORT INPUT - SAFE"
//* STEP CRASH: S0C4 ABEND - Protection Exception
//*
//* The S0C4 occurs because:
//*   1. 80 bytes copied into 24-byte SMALLBUF
//*   2. Bytes 25-80 overwrite CANARY, ADJDATA, and beyond
//*   3. On function return, corrupted R14 points to invalid memory
//*   4. MVS raises S0C4 (equivalent to SIGSEGV on Unix)
//*
//* EXAMINE THE DUMP:
//*   - Look for 'DEADBEEF' canary - if corrupted, overflow confirmed
//*   - Check PSW address - shows where execution went wrong
//*   - Check register contents at ABEND - R14 will be corrupted
//* ================================================================
