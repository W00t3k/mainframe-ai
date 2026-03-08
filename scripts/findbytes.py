#!/usr/bin/env python3
"""
findbytes.py — Find XOR-encodable byte sequences for MVS shellcode.
Source: DC30_Workshop/extra/findbytes.py (adapted)

When crafting shellcode for MVS/EBCDIC environments, certain bytes
are invalid (null bytes, FTP control chars, etc.). This tool finds
which bytes can be XOR-encoded with key 0x99 to produce valid EBCDIC.

Usage:
  python scripts/findbytes.py 90 B8 47        # check if bytes are XOR-encodable
  python scripts/findbytes.py --scan file.bin # scan a binary for bad bytes
  python scripts/findbytes.py --encode 90     # encode a byte with XOR key

Output: XOR-encoded bytes + the XOR key sequence for the decoder stub
"""

import sys

EBCDIC = "010203372D2E2F16050B0C0D0E0F101112133C3D322618193F271C1D1E1F405A7F7B5B6C507D4D5D5C4E6B604B61F0F1F2F3F4F5F6F7F8F97A5E4C7E6E6F7CC1C2C3C4C5C6C7C8C9D1D2D3D4D5D6D7D8D9E2E3E4E5E6E7E8E9ADE0BD5F6D79818283848586878889919293949596979899A2A3A4A5A6A7A8A9C04FD0A107202122232425061728292A2B2C090A1B30311A333435360838393A3B04143EFF41AA4AB19FB26AB5BBB49A8AB0CAAFBC908FEAFABEA0B6B39DDA9B8BB7B8B9AB6465626663679E687471727378757677AC69EDEEEBEFECBF80FDFEFBFCBAAE594445424643479C4854515253585556578C49CDCECBCFCCE170DDDEDBDC8D8EDF"
ASCII  = "0102030405060708090B0C0D0E0F101112131415161718191A1B1C1D1E1F202122232425262728292A2B2C2D2E2F303132333435363738393A3B3C3D3E3F404142434445464748494A4B4C4D4E4F505152535455565758595A5B5C5D5E5F606162636465666768696A6B6C6D6E6F707172737475767778797A7B7C7D7E7F808182838485868788898A8B8C8D8E8F909192939495969798999A9B9C9D9E9FA0A1A2A3A4A5A6A7A8A9AAABACADAEAFB0B1B2B3B4B5B6B7B8B9BABBBCBDBEBFC0C1C2C3C4C5C6C7C8C9CACBCCCDCECFD0D1D2D3D4D5D6D7D8D9DADBDCDDDEDFE0E1E2E3E4E5E6E7E8E9EAEBECEDEEEFF0F1F2F3F4F5F6F7F8F9FAFBFCFDFEFF"

n = 2
aline = [ASCII[i:i+n]  for i in range(0, len(ASCII),  n)]
eline = [EBCDIC[i:i+n] for i in range(0, len(EBCDIC), n)]

XOR_KEY = b'\x99'


def is_valid_ebcdic(hex_byte: str) -> bool:
    return hex_byte.upper() in eline


def xor_encode(hex_byte: str) -> tuple:
    """XOR a byte with 0x99. Returns (original, xored, xored_hex)."""
    val  = int(hex_byte, 16)
    key  = int.from_bytes(XOR_KEY, "big")
    xord = val ^ key
    xstr = f"{xord:02X}"
    return hex_byte.upper(), xstr, is_valid_ebcdic(xstr)


def scan_file(path: str):
    """Scan a binary file for bytes that are not valid EBCDIC."""
    with open(path, "rb") as f:
        data = f.read()
    bad = []
    for i, b in enumerate(data):
        h = f"{b:02X}"
        if not is_valid_ebcdic(h):
            bad.append((i, h))
    if bad:
        print(f"Found {len(bad)} invalid EBCDIC bytes in {path}:")
        for offset, h in bad:
            orig, xored, ok = xor_encode(h)
            status = "XOR-encodable" if ok else "PROBLEMATIC"
            print(f"  offset {offset:04X}: {h} -> XOR(0x99)={xored} [{status}]")
    else:
        print(f"All bytes in {path} are valid EBCDIC.")


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        print("Usage:")
        print("  python findbytes.py 90 B8 47        # check XOR-encodability")
        print("  python findbytes.py --scan file.bin # scan binary for bad bytes")
        print("  python findbytes.py --encode 90     # encode single byte")
        sys.exit(0)

    if args[0] == "--scan":
        scan_file(args[1])
        sys.exit(0)

    if args[0] == "--encode":
        for h in args[1:]:
            orig, xored, ok = xor_encode(h)
            print(f"0x{orig} XOR 0x99 = 0x{xored} ({'valid EBCDIC' if ok else 'still invalid'})")
        sys.exit(0)

    final_form = ""
    xored_seq  = ""
    for arg in args:
        orig, xored, ok = xor_encode(arg)
        status = "OK" if ok else "WARN"
        print(f"{arg} ^ {XOR_KEY.hex()} = {xored} [{status}]")
        final_form += XOR_KEY.hex()
        xored_seq  += xored

    print(f"\nShellcode (XOR'd) : {xored_seq}")
    print(f"XOR Key sequence  : {final_form}")
    print("\nDecoder stub (S/370 assembler):")
    print("  LA  R2,SHELLCODE     point to encoded shellcode")
    print("  LA  R3,LENGTH        length of shellcode")
    print("LOOP XC 0(1,R2),XORKEY XOR each byte with 0x99")
    print("  LA  R2,1(R2)         advance pointer")
    print("  BCT R3,LOOP          loop")
    print("XORKEY DC X'99'")
