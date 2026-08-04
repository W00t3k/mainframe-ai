# Assembler Language

**Assembler** (also called BAL - Basic Assembly Language) is the low-level language of the mainframe. It gives direct control over hardware and is used for system programming.

## Why Learn Assembler?

- **System exits** - Customize z/OS behavior
- **Performance** - Fastest possible code
- **Debugging** - Understand dumps and traces
- **Legacy code** - Millions of lines still in production

## Assembler Basics

### Program Structure

```asm
MYPROG   CSECT                    Control section
         USING *,12               Establish base register
         STM   14,12,12(13)       Save registers
         LR    12,15              Load base address
*
         LA    1,MESSAGE          Load message address
         WTO   MF=(E,(1))         Write to operator
*
         LM    14,12,12(13)       Restore registers
         SR    15,15              Set return code 0
         BR    14                 Return to caller
*
MESSAGE  WTO   'HELLO FROM ASSEMBLER',MF=L
         END   MYPROG
```

### Registers

The mainframe has 16 **general purpose registers** (R0-R15):

| Register | Common Use |
|----------|------------|
| R0 | Parameter passing |
| R1 | Parameter list pointer |
| R12 | Base register |
| R13 | Save area pointer |
| R14 | Return address |
| R15 | Entry point / return code |

### Instructions

Instructions operate on registers and memory:

```asm
         L     5,VALUE      Load R5 from VALUE
         A     5,=F'10'     Add 10 to R5
         ST    5,RESULT     Store R5 to RESULT
```

## Common Instructions

### Load/Store

| Instruction | Meaning |
|-------------|---------|
| `L R,addr` | Load fullword into register |
| `LR R1,R2` | Load register from register |
| `LA R,addr` | Load address |
| `ST R,addr` | Store fullword |
| `LM R1,R2,addr` | Load multiple registers |
| `STM R1,R2,addr` | Store multiple registers |

### Arithmetic

| Instruction | Meaning |
|-------------|---------|
| `A R,addr` | Add |
| `S R,addr` | Subtract |
| `M R,addr` | Multiply |
| `D R,addr` | Divide |
| `AR R1,R2` | Add registers |

### Compare/Branch

| Instruction | Meaning |
|-------------|---------|
| `C R,addr` | Compare |
| `CR R1,R2` | Compare registers |
| `BC mask,addr` | Branch on condition |
| `BE addr` | Branch if equal |
| `BNE addr` | Branch if not equal |
| `BH addr` | Branch if high |
| `BL addr` | Branch if low |

### Character Operations

| Instruction | Meaning |
|-------------|---------|
| `MVC to,from` | Move characters |
| `CLC addr1,addr2` | Compare characters |
| `CLI addr,char` | Compare immediate |

## Data Definitions

### Constants

```asm
FULLWORD DC    F'100'        Fullword (4 bytes)
HALFWORD DC    H'50'         Halfword (2 bytes)
PACKED   DC    P'12345'      Packed decimal
CHAR     DC    C'HELLO'      Character string
HEX      DC    X'FF00'       Hexadecimal
ADDRESS  DC    A(ROUTINE)    Address constant
```

### Storage

```asm
BUFFER   DS    CL80          80-byte area
COUNTER  DS    F             Fullword
SAVEAREA DS    18F           18 fullwords
```

## Macros

Macros generate multiple instructions:

```asm
         WTO   'MESSAGE'      Write to operator
         OPEN  (MYFILE,INPUT) Open a file
         GET   MYFILE,RECORD  Read a record
         PUT   MYFILE,RECORD  Write a record
         CLOSE MYFILE         Close file
```

## System Services

### WTO - Write to Operator

```asm
         WTO   'JOB STARTING'
```

### GETMAIN - Allocate Storage

```asm
         GETMAIN R,LV=1024    Get 1024 bytes
         LR    10,1           Save address in R10
```

### FREEMAIN - Release Storage

```asm
         FREEMAIN R,LV=1024,A=(10)
```

## Compile and Link

### Assemble

```jcl
//ASM     EXEC PGM=ASMA90
//SYSLIB  DD DSN=SYS1.MACLIB,DISP=SHR
//SYSIN   DD DSN=HERC01.ASM.SOURCE(MYPROG),DISP=SHR
//SYSLIN  DD DSN=&&OBJ,DISP=(,PASS)
//SYSPRINT DD SYSOUT=*
```

### Link-Edit

```jcl
//LKED    EXEC PGM=IEWL
//SYSLIN  DD DSN=&&OBJ,DISP=(OLD,DELETE)
//SYSLMOD DD DSN=HERC01.LOAD(MYPROG),DISP=SHR
//SYSPRINT DD SYSOUT=*
```

## Try It: Hello World

```asm
HELLO    CSECT
         STM   14,12,12(13)
         LR    12,15
         USING HELLO,12
         WTO   'HELLO FROM ASSEMBLER'
         LM    14,12,12(13)
         SR    15,15
         BR    14
         END   HELLO
```

Assemble, link, and run. Check SYSLOG for your message!
