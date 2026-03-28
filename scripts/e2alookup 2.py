#!/usr/bin/env python3
"""
e2alookup.py — EBCDIC to ASCII lookup and shellcode builder.
Source: DC30_Workshop/extra/e2alookup.py (adapted)

Usage:
  python scripts/e2alookup.py C1 C2 C3        # look up EBCDIC bytes
  python scripts/e2alookup.py --text HELLO     # convert EBCDIC text to ASCII hex
  python scripts/e2alookup.py --char A         # show EBCDIC code for a character

Output: ASCII hex equivalents + writes shellcode.bin
"""

import sys

EBCDIC = "010203372D2E2F16050B0C0D0E0F101112133C3D322618193F271C1D1E1F405A7F7B5B6C507D4D5D5C4E6B604B61F0F1F2F3F4F5F6F7F8F97A5E4C7E6E6F7CC1C2C3C4C5C6C7C8C9D1D2D3D4D5D6D7D8D9E2E3E4E5E6E7E8E9ADE0BD5F6D79818283848586878889919293949596979899A2A3A4A5A6A7A8A9C04FD0A107202122232425061728292A2B2C090A1B30311A333435360838393A3B04143EFF41AA4AB19FB26AB5BBB49A8AB0CAAFBC908FEAFABEA0B6B39DDA9B8BB7B8B9AB6465626663679E687471727378757677AC69EDEEEBEFECBF80FDFEFBFCBAAE594445424643479C4854515253585556578C49CDCECBCFCCE170DDDEDBDC8D8EDF"
ASCII  = "0102030405060708090B0C0D0E0F101112131415161718191A1B1C1D1E1F202122232425262728292A2B2C2D2E2F303132333435363738393A3B3C3D3E3F404142434445464748494A4B4C4D4E4F505152535455565758595A5B5C5D5E5F606162636465666768696A6B6C6D6E6F707172737475767778797A7B7C7D7E7F808182838485868788898A8B8C8D8E8F909192939495969798999A9B9C9D9E9FA0A1A2A3A4A5A6A7A8A9AAABACADAEAFB0B1B2B3B4B5B6B7B8B9BABBBCBDBEBFC0C1C2C3C4C5C6C7C8C9CACBCCCDCECFD0D1D2D3D4D5D6D7D8D9DADBDCDDDEDFE0E1E2E3E4E5E6E7E8E9EAEBECEDEEEFF0F1F2F3F4F5F6F7F8F9FAFBFCFDFEFF"

n = 2
aline = [ASCII[i:i+n]  for i in range(0, len(ASCII),  n)]
eline = [EBCDIC[i:i+n] for i in range(0, len(EBCDIC), n)]


def e2a(ebcdic_hex: str) -> str:
    h = ebcdic_hex.upper()
    if h in eline:
        return aline[eline.index(h)]
    raise ValueError(f"No translation for EBCDIC {h}")


def a2e(ascii_hex: str) -> str:
    h = ascii_hex.upper()
    if h in aline:
        return eline[aline.index(h)]
    raise ValueError(f"No translation for ASCII {h}")


def char_to_ebcdic(c: str) -> str:
    return a2e(f"{ord(c):02X}")


def text_to_ebcdic(text: str) -> str:
    return " ".join(a2e(f"{ord(c):02X}") for c in text)


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        print("Usage:")
        print("  python e2alookup.py C1 C2 C3        # EBCDIC hex -> ASCII hex")
        print("  python e2alookup.py --text HELLO     # text -> EBCDIC hex")
        print("  python e2alookup.py --char A         # char -> EBCDIC code")
        sys.exit(0)

    if args[0] == "--text":
        text = " ".join(args[1:])
        result = text_to_ebcdic(text)
        print(f"Text   : {text}")
        print(f"EBCDIC : {result}")
        sys.exit(0)

    if args[0] == "--char":
        for c in " ".join(args[1:]):
            try:
                e = char_to_ebcdic(c)
                print(f"'{c}' (ASCII {ord(c):02X}) -> EBCDIC {e}")
            except ValueError as ex:
                print(ex)
        sys.exit(0)

    final_form = ""
    for arg in args:
        try:
            result = e2a(arg)
            print(f"{arg} --> {result}")
            final_form += result
        except ValueError as ex:
            print(ex)
            sys.exit(1)

    if final_form:
        print(f"\nFinal String: {final_form}")
        out = "shellcode.bin"
        with open(out, "wb") as f:
            f.write(bytes.fromhex(final_form))
        print(f"Written to {out}")
