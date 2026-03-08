#!/usr/bin/env python3
"""
upload_to_mvs.py — Upload files to MVS datasets via JCL + port 3505.

Generates IEBUPDTE JCL to create/update PDS members on the mainframe,
then submits via the card reader socket (port 3505).

Source: DC30_Workshop/upload.py pattern (adapted for TK5)

Usage:
  python scripts/upload_to_mvs.py --file myrexx.rex --dsn SYS2.EXEC --member MYREXX
  python scripts/upload_to_mvs.py --file hello.c    --dsn HERC01.C  --member HELLO --binary
  python scripts/upload_to_mvs.py --list-members SYS2.EXEC

Examples:
  # Upload a REXX script to SYS2.EXEC
  python scripts/upload_to_mvs.py --file jcl/rexx/DEBRUIJN.rex --dsn SYS2.EXEC --member DEBRUIJN

  # Upload binary shellcode
  python scripts/upload_to_mvs.py --file shellcode.bin --dsn HERC01.LOAD --member SHELL --binary
"""

import sys
import socket
import argparse
from pathlib import Path

ROOT      = Path(__file__).parent.parent
CARD_PORT = 3505
CARD_HOST = "localhost"


def submit_jcl(jcl: str, host=CARD_HOST, port=CARD_PORT) -> bool:
    """Submit JCL string to Hercules card reader via TCP socket."""
    clean = "\n".join(
        "".join(c if ord(c) < 128 else " " for c in line)[:80]
        for line in jcl.splitlines()
    ) + "\n"
    try:
        s = socket.socket()
        s.settimeout(10)
        s.connect((host, port))
        s.sendall(clean.encode("ascii"))
        s.close()
        return True
    except Exception as e:
        print(f"Submit failed: {e}", file=sys.stderr)
        return False


def make_upload_jcl(dsn: str, member: str, lines: list[str],
                    user="IBMUSER", password="SYS1") -> str:
    """Generate IEBUPDTE JCL to upload text lines to a PDS member."""
    jcl = [
        f"//UPLOAD   JOB (1),'UPLOAD {member}',CLASS=A,MSGCLASS=X,",
        f"//             NOTIFY={user},USER={user},PASSWORD={password}",
        "//*",
        f"//* Upload {member} to {dsn}",
        "//*",
        "//STEP01   EXEC PGM=IEBUPDTE,PARM=NEW",
        "//SYSPRINT DD  SYSOUT=*",
        f"//SYSUT2   DD  DSN={dsn},DISP=SHR",
        "//SYSIN    DD  DATA,DLM=@@",
        f"./ ADD NAME={member[:8].upper()}",
    ]
    for line in lines:
        safe = "".join(c if ord(c) < 128 else " " for c in line)[:72]
        jcl.append(safe)
    jcl.append("@@")
    return "\n".join(jcl)


def make_binary_upload_jcl(dsn: str, member: str, data: bytes,
                            user="IBMUSER", password="SYS1") -> str:
    """Generate JCL to upload binary data as hex via IEBGENER."""
    hex_lines = []
    for i in range(0, len(data), 32):
        chunk = data[i:i+32].hex().upper()
        hex_lines.append(chunk)

    jcl = [
        f"//BINUPLD  JOB (1),'BIN UPLOAD',CLASS=A,MSGCLASS=X,",
        f"//             USER={user},PASSWORD={password}",
        "//*",
        f"//* Binary upload of {member} to {dsn}",
        "//* NOTE: Binary uploads require FTP in binary mode for accuracy.",
        "//* This JCL method is for text-safe hex-encoded data only.",
        "//*",
        "//STEP01   EXEC PGM=IEBGENER",
        "//SYSPRINT DD  SYSOUT=*",
        f"//SYSUT2   DD  DSN={dsn}({member[:8].upper()}),DISP=SHR",
        "//SYSIN    DD  DUMMY",
        "//SYSUT1   DD  DATA,DLM=@@",
    ]
    jcl.extend(hex_lines)
    jcl.append("@@")
    return "\n".join(jcl)


def upload_file(file_path: str, dsn: str, member: str,
                binary: bool = False, host=CARD_HOST, port=CARD_PORT) -> bool:
    p = Path(file_path)
    if not p.exists():
        print(f"File not found: {p}", file=sys.stderr)
        return False

    if binary:
        data = p.read_bytes()
        jcl  = make_binary_upload_jcl(dsn, member, data)
        print(f"Binary upload: {p.name} ({len(data)} bytes) -> {dsn}({member})")
        print("NOTE: For reliable binary uploads, use FTP in binary mode instead.")
    else:
        lines = p.read_text(errors="replace").splitlines()
        jcl   = make_upload_jcl(dsn, member, lines)
        print(f"Text upload: {p.name} ({len(lines)} lines) -> {dsn}({member})")

    ok = submit_jcl(jcl, host, port)
    if ok:
        print(f"Submitted to card reader {host}:{port}")
    return ok


def upload_rexx_tools(host=CARD_HOST, port=CARD_PORT):
    """Upload all REXX tools from jcl/rexx/ to SYS2.EXEC on the mainframe."""
    rexx_dir = ROOT / "jcl" / "rexx"
    for rex_file in rexx_dir.glob("*.rex"):
        member = rex_file.stem[:8].upper()
        print(f"\nUploading {rex_file.name} -> SYS2.EXEC({member})")
        upload_file(str(rex_file), "SYS2.EXEC", member, host=host, port=port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload files to MVS via port 3505")
    parser.add_argument("--file",    help="Local file to upload")
    parser.add_argument("--dsn",     help="Target MVS dataset (e.g. SYS2.EXEC)")
    parser.add_argument("--member",  help="PDS member name (max 8 chars)")
    parser.add_argument("--binary",  action="store_true", help="Binary upload mode")
    parser.add_argument("--rexx",    action="store_true", help="Upload all REXX tools to SYS2.EXEC")
    parser.add_argument("--host",    default=CARD_HOST)
    parser.add_argument("--port",    type=int, default=CARD_PORT)
    args = parser.parse_args()

    if args.rexx:
        upload_rexx_tools(args.host, args.port)
    elif args.file and args.dsn and args.member:
        ok = upload_file(args.file, args.dsn, args.member, args.binary, args.host, args.port)
        sys.exit(0 if ok else 1)
    else:
        parser.print_help()
        sys.exit(1)
