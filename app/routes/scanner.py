"""
Scanner API Routes

Endpoints for network scanning and port discovery.
"""

import asyncio
import ipaddress
import re
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["scanner"])

# Telnet protocol constants
IAC = 0xFF   # Interpret As Command
DONT = 0xFE
DO = 0xFD
WONT = 0xFC
WILL = 0xFB
SB = 0xFA    # Subnegotiation Begin
SE = 0xF0    # Subnegotiation End
TN3270E = 0x28

# EBCDIC to ASCII conversion table (common printable characters)
EBCDIC_TO_ASCII = {
    0x40: ' ', 0x4B: '.', 0x4C: '<', 0x4D: '(', 0x4E: '+', 0x4F: '|',
    0x50: '&', 0x5A: '!', 0x5B: '$', 0x5C: '*', 0x5D: ')', 0x5E: ';',
    0x60: '-', 0x61: '/', 0x6B: ',', 0x6C: '%', 0x6D: '_', 0x6E: '>',
    0x6F: '?', 0x7A: ':', 0x7B: '#', 0x7C: '@', 0x7D: "'", 0x7E: '=',
    0x7F: '"', 0x81: 'a', 0x82: 'b', 0x83: 'c', 0x84: 'd', 0x85: 'e',
    0x86: 'f', 0x87: 'g', 0x88: 'h', 0x89: 'i', 0x91: 'j', 0x92: 'k',
    0x93: 'l', 0x94: 'm', 0x95: 'n', 0x96: 'o', 0x97: 'p', 0x98: 'q',
    0x99: 'r', 0xA2: 's', 0xA3: 't', 0xA4: 'u', 0xA5: 'v', 0xA6: 'w',
    0xA7: 'x', 0xA8: 'y', 0xA9: 'z', 0xC1: 'A', 0xC2: 'B', 0xC3: 'C',
    0xC4: 'D', 0xC5: 'E', 0xC6: 'F', 0xC7: 'G', 0xC8: 'H', 0xC9: 'I',
    0xD1: 'J', 0xD2: 'K', 0xD3: 'L', 0xD4: 'M', 0xD5: 'N', 0xD6: 'O',
    0xD7: 'P', 0xD8: 'Q', 0xD9: 'R', 0xE2: 'S', 0xE3: 'T', 0xE4: 'U',
    0xE5: 'V', 0xE6: 'W', 0xE7: 'X', 0xE8: 'Y', 0xE9: 'Z', 0xF0: '0',
    0xF1: '1', 0xF2: '2', 0xF3: '3', 0xF4: '4', 0xF5: '5', 0xF6: '6',
    0xF7: '7', 0xF8: '8', 0xF9: '9',
}


# Reverse table: ASCII to EBCDIC
ASCII_TO_EBCDIC = {v: k for k, v in EBCDIC_TO_ASCII.items()}


def ebcdic_encode(text: str) -> list[int]:
    """Convert ASCII text to EBCDIC byte values."""
    result = []
    for ch in text:
        if ch in ASCII_TO_EBCDIC:
            result.append(ASCII_TO_EBCDIC[ch])
        elif ch == '\n':
            result.append(0x15)  # EBCDIC newline
        else:
            result.append(0x6F)  # EBCDIC '?'
    return result


def ebcdic_decode(data: list[int]) -> str:
    """Convert EBCDIC byte values to ASCII text."""
    result = []
    for b in data:
        if b in EBCDIC_TO_ASCII:
            result.append(EBCDIC_TO_ASCII[b])
        elif b == 0x15:
            result.append('\n')
        elif b == 0x00:
            result.append(' ')
        else:
            result.append('.')
    return ''.join(result)


def parse_scan_targets(target: str, max_hosts: int = 256) -> list[str]:
    hosts: list[str] = []
    for token in target.split(","):
        token = token.strip()
        if not token:
            continue
        if token.lower() == "localhost":
            hosts.append("localhost")
            continue
        if "/" in token:
            try:
                network = ipaddress.ip_network(token, strict=False)
            except ValueError as exc:
                raise ValueError(f"Invalid CIDR target: {token}") from exc
            if network.num_addresses <= 2:
                hosts.append(str(network.network_address))
            else:
                hosts.extend(str(ip) for ip in network.hosts())
        else:
            hosts.append(token)

    deduped = []
    seen = set()
    for host in hosts:
        if host not in seen:
            deduped.append(host)
            seen.add(host)

    if len(deduped) > max_hosts:
        raise ValueError(f"Target expands to {len(deduped)} hosts (max {max_hosts}).")
    return deduped


def parse_scan_ports(ports: str, max_ports: int = 32) -> list[int]:
    if not ports:
        return [23, 3270, 2323]

    parsed: list[int] = []
    for part in ports.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_str, end_str = part.split("-", 1)
            try:
                start = int(start_str)
                end = int(end_str)
            except ValueError as exc:
                raise ValueError(f"Invalid port range: {part}") from exc
            if start > end:
                start, end = end, start
            parsed.extend(range(start, end + 1))
        else:
            try:
                parsed.append(int(part))
            except ValueError as exc:
                raise ValueError(f"Invalid port: {part}") from exc

    parsed = [p for p in parsed if 1 <= p <= 65535]
    parsed = sorted(set(parsed))

    if len(parsed) > max_ports:
        raise ValueError(f"Too many ports ({len(parsed)}). Limit to {max_ports}.")
    return parsed


async def check_tcp_port(host: str, port: int, timeout: float = 1.5) -> bool:
    """Check if a TCP port is open."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        if hasattr(writer, "wait_closed"):
            await writer.wait_closed()
        return True
    except Exception:
        return False


async def grab_tn3270_banner(host: str, port: int, timeout: float = 5.0) -> dict:
    """
    Connect to a TN3270 port and grab the banner/screen content.
    TN3270 is plaintext - all data including credentials is visible.
    """
    result = {
        "host": host,
        "port": port,
        "banner": "",
        "screen_text": "",
        "applids": [],
        "is_tn3270": False,
        "ssl": False,
        "raw_bytes": ""
    }
    
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        
        # Read initial telnet negotiation and respond
        all_data = b""
        screen_data = b""
        try:
            for round_num in range(15):  # Multiple rounds of negotiation
                chunk = await asyncio.wait_for(reader.read(4096), timeout=1.5)
                if not chunk:
                    break
                all_data += chunk
                
                # Parse and respond to telnet commands
                response = b""
                i = 0
                data_portion = b""
                while i < len(chunk):
                    if chunk[i] == IAC and i + 1 < len(chunk):
                        cmd = chunk[i + 1]
                        if cmd in (DO, DONT, WILL, WONT) and i + 2 < len(chunk):
                            opt = chunk[i + 2]
                            # Respond appropriately
                            if cmd == DO:
                                # Accept terminal type, EOR, binary
                                if opt in (0x18, 0x19, 0x00):  # TERMINAL-TYPE, EOR, BINARY
                                    response += bytes([IAC, WILL, opt])
                                else:
                                    response += bytes([IAC, WONT, opt])
                            elif cmd == WILL:
                                if opt in (0x18, 0x19, 0x00, TN3270E):
                                    response += bytes([IAC, DO, opt])
                                else:
                                    response += bytes([IAC, DONT, opt])
                            i += 3
                            continue
                        elif cmd == SB:
                            # Handle subnegotiation
                            sb_start = i
                            while i < len(chunk) - 1:
                                if chunk[i] == IAC and chunk[i + 1] == SE:
                                    # Check if terminal type request
                                    if i > sb_start + 2 and chunk[sb_start + 2] == 0x18 and chunk[sb_start + 3] == 0x01:
                                        # Send terminal type IBM-3278-2
                                        response += bytes([IAC, SB, 0x18, 0x00]) + b'IBM-3278-2' + bytes([IAC, SE])
                                    i += 2
                                    break
                                i += 1
                            continue
                        elif cmd == IAC:
                            data_portion += bytes([IAC])
                            i += 2
                            continue
                    else:
                        data_portion += bytes([chunk[i]])
                    i += 1
                
                screen_data += data_portion
                
                if response:
                    writer.write(response)
                    await writer.drain()
                    
        except asyncio.TimeoutError:
            pass
        
        writer.close()
        if hasattr(writer, "wait_closed"):
            await writer.wait_closed()
        
        if all_data:
            result["raw_bytes"] = all_data.hex()[:200]
            result["is_tn3270"] = True
            
            # Extract printable text from 3270 data stream
            text = extract_3270_text(screen_data if screen_data else all_data)
            result["screen_text"] = text[:1000]
            result["banner"] = text[:200]
            
            # Look for VTAM APPLIDs
            applids = re.findall(r'\b([A-Z][A-Z0-9]{2,7})\b', text)
            common_applids = ['TSO', 'CICS', 'IMS', 'NVAS', 'VTAM', 'USS', 'ISPF']
            result["applids"] = [a for a in applids if a in common_applids or len(a) >= 4][:10]
            
    except Exception as e:
        result["error"] = str(e)
    
    return result


def extract_3270_text(data: bytes) -> str:
    """Extract readable text from TN3270 data stream (EBCDIC to ASCII)."""
    text_chars = []
    i = 0
    while i < len(data):
        b = data[i]
        # Skip IAC sequences
        if b == IAC and i + 1 < len(data):
            if data[i + 1] in (DO, DONT, WILL, WONT):
                i += 3
                continue
            elif data[i + 1] == SB:
                # Skip subnegotiation
                while i < len(data) and not (data[i] == IAC and i + 1 < len(data) and data[i + 1] == SE):
                    i += 1
                i += 2
                continue
            elif data[i + 1] == IAC:
                i += 2
                continue
        
        # Skip 3270 command/order bytes
        if b in (0x05, 0x11, 0x12, 0x13, 0x1D, 0x28, 0x29, 0x2C, 0x3C, 0xF1, 0xF5, 0x7D, 0x6E):
            i += 1
            # Some orders have additional bytes
            if b == 0x11 and i + 1 < len(data):  # SBA (Set Buffer Address)
                i += 2
            elif b == 0x1D and i < len(data):  # SF (Start Field)
                i += 1
            elif b == 0x29 and i < len(data):  # SFE (Start Field Extended)
                pairs = data[i] if i < len(data) else 0
                i += 1 + (pairs * 2)
            continue
        
        # Convert EBCDIC to ASCII
        if b in EBCDIC_TO_ASCII:
            text_chars.append(EBCDIC_TO_ASCII[b])
        elif b == 0x00:  # Null
            text_chars.append(' ')
        elif 0x20 <= b <= 0x7E:  # Already ASCII printable
            text_chars.append(chr(b))
        
        i += 1
    
    # Convert to string and clean up
    text = ''.join(text_chars)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


async def sniff_credentials(host: str, port: int, duration: float = 10.0) -> dict:
    """
    Monitor a TN3270 connection for plaintext credentials.
    WARNING: This captures actual login attempts - use responsibly!
    """
    result = {
        "host": host,
        "port": port,
        "captured_data": [],
        "potential_userids": [],
        "warning": "TN3270 transmits credentials in PLAINTEXT - no encryption!"
    }
    
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=5.0
        )
        
        all_data = b""
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < duration:
            try:
                chunk = await asyncio.wait_for(reader.read(4096), timeout=1.0)
                if not chunk:
                    break
                all_data += chunk
                
                # Extract any text that looks like userids
                text = extract_3270_text(chunk)
                if text:
                    result["captured_data"].append({
                        "time": asyncio.get_event_loop().time() - start_time,
                        "text": text[:200]
                    })
                    
                    # Look for potential userids (typically 1-8 chars, alphanumeric)
                    userid_patterns = re.findall(r'\b([A-Z][A-Z0-9]{0,7})\b', text.upper())
                    for uid in userid_patterns:
                        if uid not in result["potential_userids"] and len(uid) >= 4:
                            result["potential_userids"].append(uid)
                
            except asyncio.TimeoutError:
                continue
        
        writer.close()
        if hasattr(writer, "wait_closed"):
            await writer.wait_closed()
            
    except Exception as e:
        result["error"] = str(e)
    
    return result


@router.post("/scan")
async def api_scanner_scan(request: Request):
    """Run a port scan."""
    data = await request.json()
    target = (data.get("target") or "").strip()
    ports_input = (data.get("ports") or "").strip()

    if not target:
        return JSONResponse({"error": "Target is required"}, status_code=400)

    try:
        targets = parse_scan_targets(target)
        ports = parse_scan_ports(ports_input)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    results = []
    semaphore = asyncio.Semaphore(128)

    async def scan_host_port(host: str, port: int):
        async with semaphore:
            if await check_tcp_port(host, port):
                service = "TN3270" if port in (23, 3270, 2323) else "TCP"
                results.append({
                    "host": host,
                    "port": port,
                    "type": service,
                    "details": "Open port detected"
                })

    tasks = [scan_host_port(host, port) for host in targets for port in ports]
    if tasks:
        await asyncio.gather(*tasks)

    results.sort(key=lambda item: (item["host"], item["port"]))
    return JSONResponse({"results": results})


@router.post("/banner")
async def api_scanner_banner(request: Request):
    """Grab TN3270 banner and screen content from a target."""
    data = await request.json()
    host = (data.get("host") or "").strip()
    port = int(data.get("port", 3270))
    
    if not host:
        return JSONResponse({"error": "Host is required"}, status_code=400)
    
    result = await grab_tn3270_banner(host, port)
    return JSONResponse(result)


@router.post("/sniff")
async def api_scanner_sniff(request: Request):
    """
    Monitor TN3270 connection for plaintext credentials.
    WARNING: TN3270 has NO encryption - all data is plaintext!
    """
    data = await request.json()
    host = (data.get("host") or "").strip()
    port = int(data.get("port", 3270))
    duration = min(float(data.get("duration", 10)), 30)  # Max 30 seconds
    
    if not host:
        return JSONResponse({"error": "Host is required"}, status_code=400)
    
    result = await sniff_credentials(host, port, duration)
    return JSONResponse(result)


@router.post("/fingerprint")
async def api_scanner_fingerprint(request: Request):
    """
    Fingerprint a TN3270 service - detect VTAM, TSO, CICS, etc.
    Also checks if connection uses SSL/TLS.
    """
    data = await request.json()
    host = (data.get("host") or "").strip()
    port = int(data.get("port", 3270))
    
    if not host:
        return JSONResponse({"error": "Host is required"}, status_code=400)
    
    result = {
        "host": host,
        "port": port,
        "service": "unknown",
        "ssl": False,
        "vtam": False,
        "applications": [],
        "security_issues": []
    }
    
    # First check if SSL/TLS
    try:
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, ssl=ssl_context),
            timeout=5.0
        )
        writer.close()
        if hasattr(writer, "wait_closed"):
            await writer.wait_closed()
        result["ssl"] = True
        result["service"] = "TN3270-SSL"
    except Exception:
        result["ssl"] = False
        result["security_issues"].append("NO SSL/TLS - credentials transmitted in PLAINTEXT")
    
    # Grab banner
    banner_result = await grab_tn3270_banner(host, port)
    
    if banner_result.get("is_tn3270"):
        result["service"] = "TN3270"
        result["banner"] = banner_result.get("banner", "")
        result["screen_text"] = banner_result.get("screen_text", "")
        
        text = banner_result.get("screen_text", "").upper()
        
        # Detect VTAM
        if "VTAM" in text or "USS" in text or "APPLICATION" in text:
            result["vtam"] = True
            result["applications"].append("VTAM")
        
        # Detect available applications
        if "TSO" in text:
            result["applications"].append("TSO")
        if "CICS" in text:
            result["applications"].append("CICS")
        if "IMS" in text:
            result["applications"].append("IMS")
        if "NVAS" in text:
            result["applications"].append("NVAS")
        
        # Security observations
        if not result["ssl"]:
            result["security_issues"].append("TN3270 session can be intercepted")
            result["security_issues"].append("Login credentials visible on network")
    
    return JSONResponse(result)


@router.post("/ebcdic/encode")
async def api_ebcdic_encode(request: Request):
    """Convert ASCII text to EBCDIC hex representation."""
    data = await request.json()
    text = data.get("text", "")
    if not text:
        return JSONResponse({"error": "Text is required"}, status_code=400)

    ebcdic_bytes = ebcdic_encode(text)
    hex_str = ' '.join(f'{b:02X}' for b in ebcdic_bytes)
    return JSONResponse({
        "ascii": text,
        "ebcdic_hex": hex_str,
        "ebcdic_bytes": ebcdic_bytes,
        "length": len(ebcdic_bytes)
    })


@router.post("/ebcdic/decode")
async def api_ebcdic_decode(request: Request):
    """Convert EBCDIC hex string to ASCII text."""
    data = await request.json()
    hex_input = (data.get("hex", "") or "").strip()
    if not hex_input:
        return JSONResponse({"error": "Hex input is required"}, status_code=400)

    try:
        cleaned = hex_input.replace(' ', '').replace(',', '').replace('0x', '')
        byte_vals = [int(cleaned[i:i+2], 16) for i in range(0, len(cleaned), 2)]
    except (ValueError, IndexError):
        return JSONResponse({"error": "Invalid hex input"}, status_code=400)

    ascii_text = ebcdic_decode(byte_vals)
    return JSONResponse({
        "ebcdic_hex": ' '.join(f'{b:02X}' for b in byte_vals),
        "ascii": ascii_text,
        "length": len(byte_vals)
    })


@router.get("/ebcdic/table")
async def api_ebcdic_table():
    """Return the full EBCDIC-to-ASCII mapping table."""
    table = []
    for eb, asc in sorted(EBCDIC_TO_ASCII.items()):
        table.append({
            "ebcdic_hex": f'{eb:02X}',
            "ebcdic_dec": eb,
            "ascii_char": asc,
            "ascii_dec": ord(asc)
        })
    return JSONResponse({"table": table, "total": len(table)})
