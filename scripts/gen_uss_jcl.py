#!/usr/bin/env python3
"""
Generate a proper USS table JCL for TK5 MVS 3.8j.
Creates IBMAI.jcl with USSTAB/USSCMD/USSMSG macros and
the custom AI/OS logon screen as 3270 data stream.
"""

# 3270 buffer address encoding table (6-bit to EBCDIC)
ADDR = [
    0x40,0xC1,0xC2,0xC3,0xC4,0xC5,0xC6,0xC7,
    0xC8,0xC9,0x4A,0x4B,0x4C,0x4D,0x4E,0x4F,
    0x50,0xD1,0xD2,0xD3,0xD4,0xD5,0xD6,0xD7,
    0xD8,0xD9,0x5A,0x5B,0x5C,0x5D,0x5E,0x5F,
    0x60,0xE1,0xE2,0xE3,0xE4,0xE5,0xE6,0xE7,
    0xE8,0xE9,0x6A,0x6B,0x6C,0x6D,0x6E,0x6F,
    0xF0,0xF1,0xF2,0xF3,0xF4,0xF5,0xF6,0xF7,
    0xF8,0xF9,0x7A,0x7B,0x7C,0x7D,0x7E,0x7F,
]

def enc_addr(pos):
    """Encode 12-bit buffer address to 2-byte 3270 format."""
    hi = (pos >> 6) & 0x3F
    lo = pos & 0x3F
    return f'{ADDR[hi]:02X}{ADDR[lo]:02X}'

def sba(row, col=1):
    """SBA order hex for (row, col), 1-indexed."""
    pos = (row - 1) * 80 + (col - 1)
    return f'11{enc_addr(pos)}'

# Attribute bytes (after SF order 1D):
PROT_HI   = 'E8'  # Protected, high intensity
PROT_NORM = '60'  # Protected, normal intensity
UNPROT    = '40'  # Unprotected, normal
ASKIP_HI  = 'F8'  # Auto-skip, high intensity

def dc_sba_sf(row, col, attr):
    """Generate DC X'...' for SBA + SF at given position."""
    return f"         DC    X'{sba(row,col)}1D{attr}'"

def dc_text(text, max_len=44):
    """Generate DC C'...' statements, splitting if needed.
    Escapes single quotes for assembler."""
    text = text.replace("'", "''")
    lines = []
    while text:
        chunk = text[:max_len]
        text = text[max_len:]
        lines.append(f"         DC    C'{chunk}'")
    return lines

# ── Screen content ─────────────────────────────────────────────
# Each row: (row_num, attribute, text)
# Row is 1-24, 80 cols. Text starts at col 2 (col 1 = SF attr byte)

SCREEN = [
    # Row 1: top border
    (1,  PROT_HI,   '+' + '-'*76 + '+'),
    # Row 2-5: ASCII art banner
    (2,  PROT_HI,   '| ___  _____    ___  ____      ____  ____  ____  ____  __                   |'),
    (3,  PROT_HI,   '||   ||_   _|  / _ \\/ ___|   |  _ \\|_  _||  __/|  _ \\                      |'),
    (4,  PROT_HI,   '||  _| | |   | | | |\\___ \\   | |_) | | |  > _> | |_) |                     |'),
    (5,  PROT_HI,   '||_|   |_|    \\___/ |____/   |____/ |_|  |____||____/                      |'),
    # Row 6: tagline (green-ish on real 3270)
    (6,  PROT_NORM, '|   Artificial Intelligence Operating System  v1.0-TK5                      |'),
    # Row 7: pun (yellow-ish)
    (7,  PROT_NORM, "|   Not your grandfather's z/OS. Well, actually...                          |"),
    # Row 8: separator
    (8,  PROT_NORM, '|' + '-'*76 + '|'),
    # Row 9-11: system info
    (9,  PROT_NORM, '|  KERNEL  : MVS 3.8j TK5 (Hercules)          NODE: AIOS                   |'),
    (10, PROT_NORM, '|  AI CORE : OLLAMA LOCAL LLM                  PORT: 8080                   |'),
    (11, PROT_NORM, '|  ARCH    : S/370 ESA   SECURITY: RACF        JES2 ACTIVE                  |'),
    # Row 12: separator
    (12, PROT_NORM, '|' + '-'*76 + '|'),
    # Row 13: warning (red on real 3270)
    (13, PROT_HI,   '|  [ AUTHORIZED ACCESS ONLY ]                                               |'),
    # Row 14: research notice
    (14, PROT_NORM, '|  Research and education platform. Sessions monitored.                      |'),
    # Row 15: capabilities
    (15, PROT_NORM, '|  CAPABILITIES: TN3270 | FTP | JCL/JES | RACF | COBOL | AI TUTOR          |'),
    # Row 16: labs
    (16, PROT_NORM, '|  LABS: Buffer Overflow | APF Privesc | RACF Hashes | FTP RCE              |'),
    # Row 17: separator
    (17, PROT_NORM, '|' + '-'*76 + '|'),
    # Row 18: commands
    (18, PROT_NORM, '|  CMD: TSO | CICS/KICKS | FTP:2121 | USS-EDIT | web:8080                  |'),
    # Row 19: blank
    (19, PROT_NORM, '|' + ' '*76 + '|'),
    # Row 20: logon prompt (special - has input field)
    # Handled separately below
    # Row 21: blank
    (21, PROT_NORM, '|' + ' '*76 + '|'),
    # Row 22: footer
    (22, PROT_NORM, '|  github.com/W00t3k/mainframe-ai    AI/OS on MVS 3.8j / TK5              |'),
    # Row 23: bottom border
    (23, PROT_HI,   '+' + '-'*76 + '+'),
    # Row 24: input area
    (24, PROT_NORM, ' ==>'),
]


def generate_buffer():
    """Generate the 3270 data stream as DC statements."""
    lines = []
    lines.append("*")
    lines.append("* AI/OS LOGON SCREEN (MSG=0)")
    lines.append("*")
    lines.append("LOGSCR   DS    0F")
    lines.append("         DC    X'F5C3'              ERASE/WRITE + WCC")

    for row_num, attr, text in SCREEN:
        lines.append(f"*                                  ROW {row_num}")
        lines.append(dc_sba_sf(row_num, 1, attr))
        # Split text into chunks that fit in DC C'...' (max ~44 chars)
        for dc in dc_text(text, 44):
            lines.append(dc)

    # Row 20: Logon prompt with input field
    lines.append("*                                  ROW 20 (LOGON)")
    lines.append(dc_sba_sf(20, 1, PROT_HI))
    lines.extend(dc_text('|  Logon ===> ', 44))
    # Unprotected input field (where user types)
    lines.append(f"         DC    X'1D{UNPROT}'        SF UNPROTECTED")
    lines.append(f"         DC    X'13'                IC (INSERT CURSOR)")
    # Pad rest of input area to col 77 (about 60 chars)
    lines.extend(dc_text(' ' * 58, 44))
    # Close the border
    lines.append(f"         DC    X'1D{PROT_HI}'       SF PROT END INPUT")
    lines.extend(dc_text('|', 44))

    return '\n'.join(lines)


def generate_msg_buffer(label, text):
    """Generate a simple single-line message buffer."""
    lines = []
    lines.append(f"{label:8s} DS    0F")
    lines.append(f"         DC    X'F5C3'              ERASE/WRITE + WCC")
    lines.append(f"         DC    X'{sba(12,1)}1D{PROT_HI}'")
    for dc in dc_text(text, 44):
        lines.append(dc)
    return '\n'.join(lines)


def generate_jcl():
    """Generate the complete IBMAI.jcl."""
    buf = generate_buffer()

    # Standard VTAM messages
    msg01 = generate_msg_buffer("MSG01", "VTAM IS TERMINATING")
    msg02 = generate_msg_buffer("MSG02", "INVALID COMMAND SYNTAX")
    msg03 = generate_msg_buffer("MSG03", "REQUESTED APPLICATION NOT AVAILABLE")
    msg04 = generate_msg_buffer("MSG04", "LOGON/LOGOFF IN PROGRESS")
    msg05 = generate_msg_buffer("MSG05", "UNABLE TO ESTABLISH SESSION - TRY AGAIN")
    msg06 = generate_msg_buffer("MSG06", "SESSION ENDED")
    msg07 = generate_msg_buffer("MSG07", "LOGON ACCEPTED - ESTABLISHING SESSION")
    msg10 = generate_msg_buffer("MSG10", "ENTER LOGON COMMAND OR USERID")

    jcl = f"""//IBMAIUS  JOB (1),'IBM AI USS',CLASS=A,MSGCLASS=X,MSGLEVEL=(1,1),
//             NOTIFY=IBMUSER
//*
//* IBM Mainframe AI - Custom VTAM USS Logon Screen
//* Generates ISTNSC00 with USSTAB macros + custom screen
//*
//* After submit, restart VTAM from Hercules console:
//*   /Z NET,QUICK
//*   /S NET
//*
//*==================================================================
//*
//* STEP 1: Assemble USS table
//*
//ASM      EXEC PGM=IFOX00,REGION=1024K
//SYSLIB   DD  DISP=SHR,DSN=SYS1.MACLIB
//         DD  DISP=SHR,DSN=SYS1.AMACLIB
//         DD  DISP=SHR,DSN=SYS2.MACLIB
//         DD  DISP=SHR,DSN=SYS1.AMODGEN
//SYSUT1   DD  UNIT=VIO,SPACE=(1700,(600,100))
//SYSUT2   DD  UNIT=VIO,SPACE=(1700,(300,50))
//SYSUT3   DD  UNIT=VIO,SPACE=(1700,(300,50))
//SYSPRINT DD  SYSOUT=*
//SYSPUNCH DD  DISP=(NEW,PASS,DELETE),
//             UNIT=VIO,SPACE=(TRK,(2,2)),
//             DCB=(BLKSIZE=80,LRECL=80,RECFM=F)
//SYSIN    DD  *
ISTNSC00 CSECT
         USSTAB TABLE=STDTRANS,FORMAT=DYNAMIC
*
         USSCMD CMD=LOGON,REP=LOGON,FORMAT=PL1
         USSPARM PARM=APPLID,DEFAULT=TSO
         USSPARM PARM=DATA
*
         USSCMD CMD=LOGOFF,REP=LOGOFF,FORMAT=BAL
*
         USSCMD CMD=IBMTEST,REP=IBMTEST,FORMAT=BAL
*
         USSMSG MSG=0,BUFFER=LOGSCR
         USSMSG MSG=1,BUFFER=MSG01
         USSMSG MSG=2,BUFFER=MSG02
         USSMSG MSG=3,BUFFER=MSG03
         USSMSG MSG=4,BUFFER=MSG04
         USSMSG MSG=5,BUFFER=MSG05
         USSMSG MSG=6,BUFFER=MSG06
         USSMSG MSG=7,BUFFER=MSG07
         USSMSG MSG=10,BUFFER=MSG10
*
         USSEND
*
{buf}
*
{msg01}
*
{msg02}
*
{msg03}
*
{msg04}
*
{msg05}
*
{msg06}
*
{msg07}
*
{msg10}
*
         END
/*
//*
//* STEP 2: Link into SYS1.VTAMLIB as ISTNSC00
//*
//LKED     EXEC PGM=IEWL,PARM='XREF,LIST,LET,NCAL',
//              REGION=1024K,COND=(12,LT,ASM)
//SYSPRINT DD  SYSOUT=*
//SYSLIN   DD  DISP=(OLD,DELETE),DSN=*.ASM.SYSPUNCH
//SYSLMOD  DD  DISP=SHR,DSN=SYS1.VTAMLIB(ISTNSC00)
//SYSUT1   DD  UNIT=VIO,SPACE=(1024,(200,20))
//*
"""
    return jcl


if __name__ == '__main__':
    import sys
    from pathlib import Path

    jcl = generate_jcl()

    # Ensure all lines fit in 80 columns
    final_lines = []
    for line in jcl.splitlines():
        if len(line) > 80:
            print(f"WARNING: Line too long ({len(line)}): {line[:80]}...", file=sys.stderr)
            line = line[:80]
        final_lines.append(line)

    output = '\n'.join(final_lines)

    # Write to jcl/IBMAI.jcl
    out_path = Path(__file__).parent.parent / "jcl" / "IBMAI.jcl"
    out_path.write_text(output)
    print(f"Generated {out_path} ({len(final_lines)} lines, {len(output)} bytes)")
