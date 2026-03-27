"""
Buffer Overflow Lab Service

Provides utilities for the MVS 3.8j buffer overflow demonstration:
- De Bruijn pattern generation and offset lookup
- EBCDIC/ASCII translation tables
- Memory layout visualization
- Exploit payload analysis
"""

import json
import os
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# EBCDIC ↔ ASCII translation (subset relevant to patterns)
ASCII_TO_EBCDIC = {
    'A': 0xC1, 'B': 0xC2, 'C': 0xC3, 'D': 0xC4, 'E': 0xC5,
    'F': 0xC6, 'G': 0xC7, 'H': 0xC8, 'I': 0xC9, 'J': 0xD1,
    'K': 0xD2, 'L': 0xD3, 'M': 0xD4, 'N': 0xD5, 'O': 0xD6,
    'P': 0xD7, 'Q': 0xD8, 'R': 0xD9, 'S': 0xE2, 'T': 0xE3,
    'U': 0xE4, 'V': 0xE5, 'W': 0xE6, 'X': 0xE7, 'Y': 0xE8,
    'Z': 0xE9, 'a': 0x81, 'b': 0x82, 'c': 0x83, 'd': 0x84,
    'e': 0x85, 'f': 0x86, 'g': 0x87, 'h': 0x88, 'i': 0x89,
    'j': 0x91, 'k': 0x92, 'l': 0x93, 'm': 0x94, 'n': 0x95,
    'o': 0x96, 'p': 0x97, 'q': 0x98, 'r': 0x99, 's': 0xA2,
    't': 0xA3, 'u': 0xA4, 'v': 0xA5, 'w': 0xA6, 'x': 0xA7,
    'y': 0xA8, 'z': 0xA9, '0': 0xF0, '1': 0xF1, '2': 0xF2,
    '3': 0xF3, '4': 0xF4, '5': 0xF5, '6': 0xF6, '7': 0xF7,
    '8': 0xF8, '9': 0xF9, ' ': 0x40,
}

EBCDIC_TO_ASCII = {v: k for k, v in ASCII_TO_EBCDIC.items()}


def generate_debruijn(length: int = 80, n: int = 4) -> str:
    """
    Generate a De Bruijn sequence for offset discovery.

    Each n-character substring is unique in the sequence.
    Default n=4 matches the 4-byte fullword size on S/370.

    Args:
        length: Total length of pattern to generate (max 80 for MVS card)
        n: Substring length (4 for fullword addresses)

    Returns:
        ASCII pattern string
    """
    # Use a 3-character alphabet to keep patterns readable
    # With k=3, n=4 we get 3^4 = 81 unique 4-byte substrings
    k = 3
    alphabet = "Aa0"

    # De Bruijn sequence via Martin's algorithm
    a = [0] * (k * n)
    sequence = []

    def db(t, p):
        if t > n:
            if n % p == 0:
                sequence.extend(a[1:p + 1])
        else:
            a[t] = a[t - p]
            db(t + 1, p)
            for j in range(a[t - p] + 1, k):
                a[t] = j
                db(t + 1, t)

    db(1, 1)

    # Convert to characters
    pattern = ''.join(alphabet[c] for c in sequence)

    # Extend if needed by repeating with offset markers
    while len(pattern) < length:
        pattern += pattern

    return pattern[:length]


def find_debruijn_offset(pattern: str, search_bytes: str, n: int = 4) -> int:
    """
    Find the offset of a byte sequence within a De Bruijn pattern.

    Args:
        pattern: The generated De Bruijn pattern
        search_bytes: Hex string of bytes found in register dump (e.g. 'C1C1C1C1')
        n: Substring length

    Returns:
        Offset in bytes, or -1 if not found
    """
    # Convert hex EBCDIC bytes to ASCII characters
    search_ascii = ""
    for i in range(0, len(search_bytes), 2):
        byte_val = int(search_bytes[i:i + 2], 16)
        char = EBCDIC_TO_ASCII.get(byte_val, '?')
        search_ascii += char

    idx = pattern.find(search_ascii)
    return idx


def ascii_to_ebcdic_hex(text: str) -> str:
    """Convert ASCII text to EBCDIC hex string."""
    result = []
    for ch in text:
        ebcdic = ASCII_TO_EBCDIC.get(ch, 0x40)  # default to space
        result.append(f"{ebcdic:02X}")
    return ''.join(result)


def ebcdic_hex_to_ascii(hex_str: str) -> str:
    """Convert EBCDIC hex string to ASCII text."""
    result = []
    for i in range(0, len(hex_str), 2):
        byte_val = int(hex_str[i:i + 2], 16)
        char = EBCDIC_TO_ASCII.get(byte_val, '.')
        result.append(char)
    return ''.join(result)


def get_memory_layout() -> List[str]:
    """Get the memory layout diagram for the vulnerable program."""
    return [
        "┌─────────────────────────────────┐ Low Address",
        "│ SAVEAREA (72 bytes / 18F)       │ ← R13",
        "│   +0:  unused                   │",
        "│   +4:  backward chain ptr       │",
        "│   +8:  forward chain ptr        │",
        "│   +12: saved R14 (RET ADDR) ★   │ ← TARGET",
        "│   +16: saved R15                │",
        "│   +20: saved R0-R12             │",
        "├─────────────────────────────────┤",
        "│ SMALLBUF (24 bytes)             │ ← OVERFLOW START",
        "├─────────────────────────────────┤",
        "│ CANARY 'DEADBEEF' (8 bytes)     │ ← Corruption sentinel",
        "├─────────────────────────────────┤",
        "│ ADJDATA (48 bytes)              │",
        "├─────────────────────────────────┤",
        "│ INBUF (80 bytes)                │ ← Input lands here",
        "├─────────────────────────────────┤",
        "│ OUTMSG (80 bytes)               │",
        "├─────────────────────────────────┤",
        "│ DCBs (I/O control blocks)       │",
        "└─────────────────────────────────┘ High Address",
    ]


def analyze_abend_dump(dump_text: str) -> Dict[str, Any]:
    """
    Analyze an S0C4 ABEND dump for buffer overflow indicators.

    Looks for:
    - Corrupted register values (repeated patterns)
    - PSW at time of error
    - Completion code
    - Save area chain corruption
    """
    analysis = {
        "abend_code": "",
        "psw": "",
        "registers": {},
        "overflow_detected": False,
        "corrupted_registers": [],
        "canary_status": "unknown",
        "interpretation": [],
    }

    lines = dump_text.upper().split('\n')

    for line in lines:
        # Find completion code
        if 'COMPLETION CODE' in line or 'SYSTEM' in line:
            if 'S0C4' in line or '0C4' in line:
                analysis["abend_code"] = "S0C4"
                analysis["interpretation"].append(
                    "S0C4 = Protection Exception (equivalent to SIGSEGV)"
                )

        # Find PSW
        if 'PSW' in line and ('AT' in line or 'ENTRY' in line):
            analysis["psw"] = line.strip()

        # Look for register dumps
        if line.strip().startswith('REGS AT'):
            analysis["interpretation"].append(
                "Register contents at time of ABEND — check R14 for corruption"
            )

        # Check for repeated byte patterns (overflow signature)
        for pattern in ['C1C1C1C1', 'C2C2C2C2', 'C3C3C3C3', 'C4C4C4C4']:
            if pattern in line:
                char = EBCDIC_TO_ASCII.get(int(pattern[:2], 16), '?')
                analysis["overflow_detected"] = True
                analysis["corrupted_registers"].append({
                    "pattern": pattern,
                    "ascii_char": char,
                    "meaning": f"Register contains repeated '{char}' — overflow reached here"
                })

        # Check for DEADBEEF canary
        if 'DEADBEEF' in line or 'C4C5C1C4' in line:
            analysis["canary_status"] = "present (not yet overwritten at this point)"
        if 'C1C1C1C1' in line and 'DEADBEEF' not in dump_text.upper():
            analysis["canary_status"] = "corrupted — overflow confirmed"

    if analysis["overflow_detected"]:
        analysis["interpretation"].append(
            "Repeated EBCDIC characters in registers confirm buffer overflow"
        )
        analysis["interpretation"].append(
            "R14 corruption = return address hijacked = controlled execution possible"
        )
    elif analysis["abend_code"] == "S0C4":
        analysis["interpretation"].append(
            "S0C4 without obvious pattern — may need De Bruijn sequence for offset"
        )

    return analysis


def get_lab_data() -> Dict[str, Any]:
    """Load the buffer overflow lab data from JSON."""
    lab_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data", "lab_data", "bof_demo.json"
    )
    try:
        with open(lab_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load BOF lab data: {e}")
        return {"error": str(e)}


def get_exploit_narrative(step: int) -> str:
    """Get AI tutor narrative for a specific exploit demo step."""
    narratives = {
        1: """**The Vulnerability: No Bounds Checking**

On MVS, the `MVC` (Move Characters) instruction copies a fixed number of bytes.
There is no runtime check — if you specify `MVC SMALLBUF(80),INBUF`, it copies
exactly 80 bytes regardless of the destination size.

This is identical to `memcpy()` or `strcpy()` in C — the instruction does what
you tell it, even if it destroys adjacent memory.

The save area chain (R13 → 72-byte block) replaces the stack frame on S/370.
R14 in the save area = return address. Corrupt it and you control execution.""",

        2: """**Assembly and Link-Edit**

The vulnerable program is assembled with IFOX00 (the MVS assembler) and linked
with IEWL (the linkage editor). RC=0000 on both means the program is ready.

Note: there are no compiler warnings about the overflow. The assembler sees
`MVC SMALLBUF(80),INBUF` as a perfectly valid instruction. This is by design —
the programmer is responsible for bounds checking.""",

        3: """**Safe Execution Baseline**

With input shorter than 24 bytes, the program works normally.
The `MVC` still copies 80 bytes, but the excess writes into our own data areas
(CANARY, ADJDATA) which we control. No crash because the save area is untouched.

This establishes the baseline: the program works when given expected input.""",

        4: """**The Crash: S0C4**

When 68+ bytes of input are sent, the overflow reaches the save area.
At function return, `LM R14,R12,12(R13)` loads corrupted values into registers.
`BR R14` then jumps to whatever address was written into R14.

If R14 now contains `C1C1C1C1` (EBCDIC 'AAAA'), MVS tries to execute at
address `0xC1C1C1C1` — which is not allocated to this address space.

**S0C4: Protection Exception.** The mainframe equivalent of SIGSEGV.
The room goes quiet because nobody expects a mainframe buffer overflow.""",

        5: """**Reading the ABEND Dump**

The dump shows:
- **PSW**: The instruction address where the exception occurred
- **Registers**: R0-R15 at the time of the ABEND
- **Save Area**: The 72-byte block showing the corruption pattern

Look for R14 specifically. If it contains `C1C1C1C1` (hex for EBCDIC 'A'),
that means our input 'AAAA...' reached the return address.

This is exactly like reading a core dump after a segfault on Linux.""",

        6: """**De Bruijn Pattern: Finding the Exact Offset**

Instead of 'AAAA...', send a De Bruijn sequence where every 4-byte substring
is unique: `Aa0Aa1Aa2Aa3Aa4...`

When the crash occurs, check what 4 bytes landed in R14.
Convert from EBCDIC hex back to ASCII and look up the offset in the pattern.

That offset = exact number of padding bytes before the return address.
Now you know precisely where to place your redirect address.""",

        7: """**Proof of Controlled Execution: WTO**

The WTO (Write To Operator) payload writes messages to the operator console.
In a real exploit, this code would be injected into the input buffer and
the return address would be redirected to it.

When `*** HELLO FROM EXPLOIT ***` appears on the Hercules console,
it proves: **User input → Memory corruption → Controlled execution.**

This is the same primitive used in every buffer overflow exploit since 1988.""",

        8: """**Why Mainframes Are Actually Easier to Exploit (In Theory)**

Modern systems have multiple mitigations:
- **ASLR**: Randomizes memory layout → harder to predict addresses
- **Stack Canaries**: Detect overflow before return → blocks exploitation
- **DEP/NX**: Mark stack non-executable → can't run injected code
- **PIE**: Position-independent executables → no fixed addresses

**MVS 3.8j has NONE of these.**

Addresses are fixed. Memory is executable. No canaries. No randomization.
The only protection is RACF access control and the fact that batch jobs run
in isolated address spaces.

The real defense: don't let untrusted users run untrusted programs.
On modern z/OS, hardware features (keys, DAT) provide additional protection."""
    }
    return narratives.get(step, "Step not found.")
