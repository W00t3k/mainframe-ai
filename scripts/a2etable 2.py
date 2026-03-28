#!/usr/bin/env python3
"""
a2etable.py — Print ASCII <-> EBCDIC translation table.
Source: DC30_Workshop/extra/a2etable.py (adapted)
Usage: python scripts/a2etable.py
"""

EBCDIC = "010203372D2E2F16050B0C0D0E0F101112133C3D322618193F271C1D1E1F405A7F7B5B6C507D4D5D5C4E6B604B61F0F1F2F3F4F5F6F7F8F97A5E4C7E6E6F7CC1C2C3C4C5C6C7C8C9D1D2D3D4D5D6D7D8D9E2E3E4E5E6E7E8E9ADE0BD5F6D79818283848586878889919293949596979899A2A3A4A5A6A7A8A9C04FD0A107202122232425061728292A2B2C090A1B30311A333435360838393A3B04143EFF41AA4AB19FB26AB5BBB49A8AB0CAAFBC908FEAFABEA0B6B39DDA9B8BB7B8B9AB6465626663679E687471727378757677AC69EDEEEBEFECBF80FDFEFBFCBAAE594445424643479C4854515253585556578C49CDCECBCFCCE170DDDEDBDC8D8EDF"
ASCII  = "0102030405060708090B0C0D0E0F101112131415161718191A1B1C1D1E1F202122232425262728292A2B2C2D2E2F303132333435363738393A3B3C3D3E3F404142434445464748494A4B4C4D4E4F505152535455565758595A5B5C5D5E5F606162636465666768696A6B6C6D6E6F707172737475767778797A7B7C7D7E7F808182838485868788898A8B8C8D8E8F909192939495969798999A9B9C9D9E9FA0A1A2A3A4A5A6A7A8A9AAABACADAEAFB0B1B2B3B4B5B6B7B8B9BABBBCBDBEBFC0C1C2C3C4C5C6C7C8C9CACBCCCDCECFD0D1D2D3D4D5D6D7D8D9DADBDCDDDEDFE0E1E2E3E4E5E6E7E8E9EAEBECEDEEEFF0F1F2F3F4F5F6F7F8F9FAFBFCFDFEFF"

n = 2
aline = [ASCII[i:i+n]  for i in range(0, len(ASCII),  n)]
eline = [EBCDIC[i:i+n] for i in range(0, len(EBCDIC), n)]

print(f"ASCII Entries: {len(aline)}  EBCDIC Entries: {len(eline)}\n")
L = 16
for i in range(0, 254, L):
    print("ascii : {}".format(' '.join(aline[i:i+L])))
    print("ebcdic: {}\n".format(' '.join(eline[i:i+L])))


def ascii_to_ebcdic(hex_str: str) -> str:
    """Convert ASCII hex string to EBCDIC hex string."""
    result = []
    for i in range(0, len(hex_str), 2):
        byte = hex_str[i:i+2].upper()
        if byte in aline:
            result.append(eline[aline.index(byte)])
        else:
            result.append("??")
    return " ".join(result)


def ebcdic_to_ascii(hex_str: str) -> str:
    """Convert EBCDIC hex string to ASCII hex string."""
    result = []
    for i in range(0, len(hex_str), 2):
        byte = hex_str[i:i+2].upper()
        if byte in eline:
            result.append(aline[eline.index(byte)])
        else:
            result.append("??")
    return " ".join(result)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        data = sys.argv[2] if len(sys.argv) > 2 else ""
        if mode == "a2e":
            print(f"ASCII  {data} -> EBCDIC {ascii_to_ebcdic(data)}")
        elif mode == "e2a":
            print(f"EBCDIC {data} -> ASCII  {ebcdic_to_ascii(data)}")
