#!/usr/bin/env python3
"""
TN3270 Discovery Engine — Internet-scale mainframe discovery.

Three-phase pipeline:
  1. SWEEP  — Shodan API query, masscan SYN scan, or nmap scan for TN3270 ports
  2. PROBE  — TN3270 protocol negotiation + screen capture on each hit
  3. CLASSIFY — Fingerprint system type (z/OS, z/VM, AS/400, CICS, etc.)

Results stored in SQLite for persistence across sessions.

Usage:
  - Shodan: query existing internet index (fastest, broadest)
  - masscan: raw SYN sweep on IP ranges (fast, requires root)
  - nmap: targeted scan with NSE scripts (deep, slower)
  - probe: our own async TN3270 prober on discovered hosts
"""

import asyncio
import json
import os
import random
import re
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# TN3270 ports to scan
# ---------------------------------------------------------------------------
TN3270_PORTS = [23, 992, 2323, 3270, 3271, 3272, 3273, 3274, 3275]

# Custom NSE scripts directory (mainframed/nmap-scripts)
NMAP_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nmap-scripts")

# ---------------------------------------------------------------------------
# Stealth Profiles — controls timing, concurrency, jitter
# ---------------------------------------------------------------------------
STEALTH_PROFILES = {
    "paranoid": {
        "label": "Paranoid (T0)",
        "description": "1 host at a time, 15-30s random delay between probes. Near-invisible.",
        "probe_concurrency": 1,
        "probe_delay_min": 15.0,
        "probe_delay_max": 30.0,
        "probe_timeout": 15.0,
        "nmap_timing": "-T0",
        "masscan_rate": 10,
        "randomize_order": True,
    },
    "sneaky": {
        "label": "Sneaky (T1)",
        "description": "1 host at a time, 5-15s random delay. Very slow, very quiet.",
        "probe_concurrency": 1,
        "probe_delay_min": 5.0,
        "probe_delay_max": 15.0,
        "probe_timeout": 12.0,
        "nmap_timing": "-T1",
        "masscan_rate": 50,
        "randomize_order": True,
    },
    "polite": {
        "label": "Polite (T2)",
        "description": "3 concurrent, 2-5s jitter. Won't trigger most IDS.",
        "probe_concurrency": 3,
        "probe_delay_min": 2.0,
        "probe_delay_max": 5.0,
        "probe_timeout": 10.0,
        "nmap_timing": "-T2",
        "masscan_rate": 200,
        "randomize_order": True,
    },
    "normal": {
        "label": "Normal (T3)",
        "description": "10 concurrent, 0.5-2s jitter. Default nmap speed.",
        "probe_concurrency": 10,
        "probe_delay_min": 0.5,
        "probe_delay_max": 2.0,
        "probe_timeout": 8.0,
        "nmap_timing": "-T3",
        "masscan_rate": 1000,
        "randomize_order": False,
    },
    "aggressive": {
        "label": "Aggressive (T4)",
        "description": "50 concurrent, no delay. Fast but noisy.",
        "probe_concurrency": 50,
        "probe_delay_min": 0.0,
        "probe_delay_max": 0.0,
        "probe_timeout": 5.0,
        "nmap_timing": "-T4",
        "masscan_rate": 10000,
        "randomize_order": False,
    },
    "insane": {
        "label": "Insane (T5)",
        "description": "100 concurrent, no delay, short timeouts. Research only.",
        "probe_concurrency": 100,
        "probe_delay_min": 0.0,
        "probe_delay_max": 0.0,
        "probe_timeout": 3.0,
        "nmap_timing": "-T5",
        "masscan_rate": 100000,
        "randomize_order": False,
    },
}


def get_stealth_profile(name: str) -> dict:
    """Get a stealth profile by name, default to 'polite'."""
    return STEALTH_PROFILES.get(name, STEALTH_PROFILES["polite"])

# ---------------------------------------------------------------------------
# System fingerprint patterns (screen text -> classification)
# ---------------------------------------------------------------------------
FINGERPRINTS = {
    "z/OS": [
        "Z/OS", "MVS", "VTAM", "TSO/E", "ISPF", "IKJ56", "ICH70",
        "RACF", "JES2", "JES3", "DFSMS", "SYS1.",
    ],
    "z/VM": [
        "Z/VM", "VM/ESA", "VM/CMS", "CP READ", "RUNNING", "VMBLOK",
        "LOGON AT", "VM/SP",
    ],
    "z/VSE": [
        "Z/VSE", "VSE/ESA", "ICCF", "POWER", "VTAM/VSE",
    ],
    "AS/400 (IBM i)": [
        "AS/400", "IBM I", "ISERIES", "SIGN ON", "QSYS", "CPF",
        "DISPLAY SIGN ON", "SYSTEM/36", "S/36",
    ],
    "CICS": [
        "CICS", "DFHCE", "DFH", "CEDA", "CESN", "CESF",
    ],
    "IMS": [
        "IMS/DC", "IMS/TM", "DFS", "/FOR", "/DIS",
    ],
    "TPX": [
        "TPX", "COMPUTER ASSOCIATES", "SESSION MANAGER",
    ],
    "NVAS": [
        "NVAS", "NETVIEW ACCESS", "NETVIEW",
    ],
    "Hercules": [
        "HERCULES", "TK4-", "TK5", "TURNKEY",
    ],
}


# ---------------------------------------------------------------------------
# SQLite Database
# ---------------------------------------------------------------------------

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "discovery.db")
SCREENSHOTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hosts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ip          TEXT NOT NULL,
            port        INTEGER NOT NULL,
            source      TEXT DEFAULT '',
            first_seen  TEXT NOT NULL,
            last_seen   TEXT NOT NULL,
            is_tn3270   INTEGER DEFAULT 0,
            ssl         INTEGER DEFAULT 0,
            system_type TEXT DEFAULT '',
            applications TEXT DEFAULT '[]',
            banner      TEXT DEFAULT '',
            screen_text TEXT DEFAULT '',
            org         TEXT DEFAULT '',
            country     TEXT DEFAULT '',
            isp         TEXT DEFAULT '',
            os_info     TEXT DEFAULT '',
            security_issues TEXT DEFAULT '[]',
            raw_data    TEXT DEFAULT '{}',
            screenshot_txt TEXT DEFAULT '',
            screenshot_png TEXT DEFAULT '',
            UNIQUE(ip, port)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            started     TEXT NOT NULL,
            finished    TEXT,
            source      TEXT NOT NULL,
            query       TEXT DEFAULT '',
            targets     TEXT DEFAULT '',
            status      TEXT DEFAULT 'running',
            hosts_found INTEGER DEFAULT 0,
            error       TEXT DEFAULT ''
        )
    """)
    conn.commit()
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _upsert_host(conn: sqlite3.Connection, host: dict) -> int:
    """Insert or update a discovered host. Returns rowid."""
    now = _now()
    existing = conn.execute(
        "SELECT id, first_seen FROM hosts WHERE ip=? AND port=?",
        (host["ip"], host["port"])
    ).fetchone()

    if existing:
        conn.execute("""
            UPDATE hosts SET
                last_seen=?, source=COALESCE(NULLIF(?,''),(source)),
                is_tn3270=MAX(is_tn3270,?), ssl=MAX(ssl,?),
                system_type=COALESCE(NULLIF(?,''),(system_type)),
                applications=CASE WHEN ?='[]' THEN applications ELSE ? END,
                banner=COALESCE(NULLIF(?,''),(banner)),
                screen_text=COALESCE(NULLIF(?,''),(screen_text)),
                org=COALESCE(NULLIF(?,''),(org)),
                country=COALESCE(NULLIF(?,''),(country)),
                isp=COALESCE(NULLIF(?,''),(isp)),
                os_info=COALESCE(NULLIF(?,''),(os_info)),
                security_issues=CASE WHEN ?='[]' THEN security_issues ELSE ? END,
                raw_data=CASE WHEN ?='{}' THEN raw_data ELSE ? END,
                screenshot_txt=COALESCE(NULLIF(?,''),(screenshot_txt)),
                screenshot_png=COALESCE(NULLIF(?,''),(screenshot_png))
            WHERE id=?
        """, (
            now, host.get("source", ""),
            int(host.get("is_tn3270", False)), int(host.get("ssl", False)),
            host.get("system_type", ""),
            json.dumps(host.get("applications", [])),
            json.dumps(host.get("applications", [])),
            host.get("banner", ""),
            host.get("screen_text", ""),
            host.get("org", ""),
            host.get("country", ""),
            host.get("isp", ""),
            host.get("os_info", ""),
            json.dumps(host.get("security_issues", [])),
            json.dumps(host.get("security_issues", [])),
            json.dumps(host.get("raw_data", {})),
            json.dumps(host.get("raw_data", {})),
            host.get("screenshot_txt", ""),
            host.get("screenshot_png", ""),
            existing["id"],
        ))
        conn.commit()
        return existing["id"]
    else:
        cur = conn.execute("""
            INSERT INTO hosts
                (ip, port, source, first_seen, last_seen, is_tn3270, ssl,
                 system_type, applications, banner, screen_text,
                 org, country, isp, os_info, security_issues, raw_data,
                 screenshot_txt, screenshot_png)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            host["ip"], host["port"], host.get("source", ""),
            now, now,
            int(host.get("is_tn3270", False)), int(host.get("ssl", False)),
            host.get("system_type", ""),
            json.dumps(host.get("applications", [])),
            host.get("banner", ""),
            host.get("screen_text", ""),
            host.get("org", ""),
            host.get("country", ""),
            host.get("isp", ""),
            host.get("os_info", ""),
            json.dumps(host.get("security_issues", [])),
            json.dumps(host.get("raw_data", {})),
            host.get("screenshot_txt", ""),
            host.get("screenshot_png", ""),
        ))
        conn.commit()
        return cur.lastrowid


# ---------------------------------------------------------------------------
# Classify screen text
# ---------------------------------------------------------------------------

def classify_screen(screen_text: str) -> tuple[str, list[str]]:
    """Classify system type and applications from screen text.
    Returns (system_type, [applications]).
    """
    upper = (screen_text or "").upper()
    if not upper.strip():
        return "unknown", []

    system_type = "unknown"
    apps = []
    best_score = 0

    for sys_name, patterns in FINGERPRINTS.items():
        score = sum(1 for p in patterns if p in upper)
        if score > best_score:
            best_score = score
            system_type = sys_name
        if score > 0 and sys_name in ("CICS", "IMS", "TPX", "NVAS"):
            apps.append(sys_name)

    # Also detect specific applications
    if "TSO" in upper and "TSO" not in apps:
        apps.append("TSO")
    if "CICS" in upper and "CICS" not in apps:
        apps.append("CICS")
    if "IMS" in upper and "IMS" not in apps:
        apps.append("IMS")
    if "VTAM" in upper and "VTAM" not in apps:
        apps.append("VTAM")
    if "ISPF" in upper and "ISPF" not in apps:
        apps.append("ISPF")

    return system_type, apps


# ---------------------------------------------------------------------------
# Phase 1a: Shodan Search
# ---------------------------------------------------------------------------

SHODAN_BASE = "https://api.shodan.io"

async def _shodan_get(endpoint: str, api_key: str, params: dict = None) -> dict:
    """Make a GET request to the Shodan REST API (no pip package needed)."""
    import urllib.request
    import urllib.parse
    import urllib.error

    params = params or {}
    params["key"] = api_key
    url = f"{SHODAN_BASE}{endpoint}?{urllib.parse.urlencode(params)}"

    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            err_data = json.loads(body)
            msg = err_data.get("error", body)
        except json.JSONDecodeError:
            msg = body
        raise RuntimeError(f"Shodan API error ({e.code}): {msg}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Shodan connection error: {e.reason}")


async def shodan_search(api_key: str, query: str = None,
                        max_results: int = 500,
                        callback=None) -> list[dict]:
    """Query Shodan for open TN3270 services using raw REST API.

    Default query: all TN3270 ports + mainframe keywords.

    Uses /shodan/host/search with pagination (page=1,2,3...).
    No pip packages required — just stdlib urllib.

    Returns list of host dicts ready for _upsert_host.
    """
    if not query:
        query = 'port:23,3270,2323 product:"TN3270"'

    results = []
    page = 1

    while len(results) < max_results:
        data = await _shodan_get("/shodan/host/search", api_key, {
            "query": query,
            "page": page,
        })

        matches = data.get("matches", [])
        if not matches:
            break

        for banner in matches:
            if len(results) >= max_results:
                break

            screen_text = banner.get("data", "")
            sys_type, apps = classify_screen(screen_text)

            host = {
                "ip": banner.get("ip_str", ""),
                "port": banner.get("port", 0),
                "source": "shodan",
                "is_tn3270": True,
                "ssl": bool(banner.get("ssl")),
                "system_type": sys_type,
                "applications": apps,
                "banner": screen_text[:200],
                "screen_text": screen_text[:2000],
                "org": banner.get("org", ""),
                "country": banner.get("location", {}).get("country_name", ""),
                "isp": banner.get("isp", ""),
                "os_info": banner.get("os", ""),
                "security_issues": [] if banner.get("ssl") else [
                    "NO SSL/TLS - plaintext TN3270"
                ],
                "raw_data": {
                    "shodan_module": banner.get("_shodan", {}).get("module", ""),
                    "hostnames": banner.get("hostnames", []),
                    "domains": banner.get("domains", []),
                    "vulns": list(banner.get("vulns", {}).keys()) if banner.get("vulns") else [],
                    "timestamp": banner.get("timestamp", ""),
                },
            }
            results.append(host)

            if callback:
                callback(len(results), max_results, host)

        # Shodan returns 100 results per page
        if len(matches) < 100:
            break
        page += 1

    return results


async def shodan_count(api_key: str, query: str = None) -> dict:
    """Quick count of Shodan results without consuming query credits."""
    if not query:
        query = 'port:23,3270,2323 product:"TN3270"'

    data = await _shodan_get("/shodan/host/count", api_key, {"query": query})
    return {
        "total": data.get("total", 0),
        "facets": data.get("facets", {}),
        "query": query,
    }


# ---------------------------------------------------------------------------
# Phase 1b: masscan Sweep
# ---------------------------------------------------------------------------

async def masscan_sweep(targets: str, ports: str = None,
                        rate: int = 10000, stealth: str = None,
                        callback=None, log_cb=None) -> list[dict]:
    """Run masscan on target ranges for TN3270 ports.

    Args:
        targets: IP range(s), e.g. "0.0.0.0/0" or "192.168.0.0/16"
        ports: Comma-separated ports (default: TN3270_PORTS)
        rate: Packets per second (overridden by stealth profile if set)
        stealth: Stealth profile name (paranoid/sneaky/polite/normal/aggressive)
        log_cb: Optional callable(str) for real-time console output

    Requires: masscan installed and root/sudo for raw sockets.
    Returns list of host dicts (ip + port only, not yet probed).
    """
    if stealth:
        profile = get_stealth_profile(stealth)
        rate = profile["masscan_rate"]

    port_str = ports or ",".join(str(p) for p in TN3270_PORTS)

    cmd = [
        "masscan", targets,
        "-p", port_str,
        "--rate", str(rate),
        "--open-only",
        "--randomize-hosts",
        "-oJ", "-",  # JSON to stdout
    ]

    # Auto-prepend sudo if not running as root
    if os.geteuid() != 0:
        cmd = ["sudo", "-n"] + cmd  # -n = non-interactive (no password prompt)

    if log_cb:
        log_cb(f"$ {' '.join(cmd)}")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        raise RuntimeError("masscan not found. Install: brew install masscan (macOS) or apt install masscan (Linux)")

    # Stream stderr byte-by-byte — masscan uses \r for progress updates, not \n
    stderr_lines = []
    stdout_chunks = []

    async def _read_stderr():
        buf = b""
        while True:
            byte = await proc.stderr.read(1)
            if not byte:
                # Flush remaining buffer
                if buf:
                    text = buf.decode(errors="replace").strip()
                    if text:
                        stderr_lines.append(text)
                        if log_cb:
                            log_cb(f"[masscan] {text}")
                break
            if byte in (b"\n", b"\r"):
                text = buf.decode(errors="replace").strip()
                if text:
                    stderr_lines.append(text)
                    if log_cb:
                        log_cb(f"[masscan] {text}")
                buf = b""
            else:
                buf += byte

    async def _read_stdout():
        while True:
            chunk = await proc.stdout.read(8192)
            if not chunk:
                break
            stdout_chunks.append(chunk)

    await asyncio.gather(_read_stderr(), _read_stdout())
    await proc.wait()

    if log_cb:
        log_cb(f"[masscan] Process exited with code {proc.returncode}")

    results = []

    if proc.returncode != 0:
        err = "\n".join(stderr_lines)
        if "permission" in err.lower() or "root" in err.lower():
            raise RuntimeError("masscan requires root privileges. Run with sudo.")
        raise RuntimeError(f"masscan failed: {err}")

    # Parse JSON output (masscan outputs JSON array with trailing comma issues)
    raw = b"".join(stdout_chunks).decode(errors="replace").strip()
    # Fix masscan JSON: remove trailing commas and wrap in array if needed
    raw = re.sub(r',\s*\]', ']', raw)
    raw = re.sub(r',\s*$', '', raw)
    if not raw.startswith('['):
        raw = '[' + raw + ']'

    try:
        entries = json.loads(raw)
    except json.JSONDecodeError:
        # Try line-by-line
        entries = []
        for line in raw.splitlines():
            line = line.strip().rstrip(',')
            if line.startswith('{'):
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    for entry in entries:
        ip = entry.get("ip", "")
        for port_info in entry.get("ports", []):
            port = port_info.get("port", 0)
            host = {
                "ip": ip,
                "port": port,
                "source": "masscan",
                "is_tn3270": False,  # Not yet confirmed
            }
            results.append(host)

            if callback:
                callback(len(results), -1, host)

    return results


# ---------------------------------------------------------------------------
# Phase 1c: nmap Targeted Scan
# ---------------------------------------------------------------------------

async def nmap_scan(targets: str, ports: str = None,
                    nse_scripts: bool = True, stealth: str = None,
                    callback=None, log_cb=None) -> list[dict]:
    """Run nmap with TN3270 NSE scripts for deep fingerprinting.

    Args:
        targets: IP/range/hostname
        ports: Port list (default: TN3270_PORTS)
        nse_scripts: Run tn3270-screen and tn3270-info NSE scripts
        stealth: Stealth profile name (uses nmap -T flag)
        log_cb: Optional callable(str) for real-time console output

    Returns list of host dicts with fingerprint data.
    """
    port_str = ports or ",".join(str(p) for p in TN3270_PORTS)

    cmd = [
        "nmap", "-sV",
        "-p", port_str,
        "--open",
        "--randomize-hosts",
        "-oX", "-",  # XML to stdout
    ]

    # Apply timing template from stealth profile
    if stealth:
        profile = get_stealth_profile(stealth)
        cmd.append(profile["nmap_timing"])
    else:
        cmd.append("-T3")

    if nse_scripts:
        cmd.extend(["--script", "tn3270-screen,tn3270-info,ssl-cert"])

    # Handle multiple targets
    cmd.extend(targets.split())

    # Auto-prepend sudo if not running as root (needed for SYN scan)
    if os.geteuid() != 0:
        cmd = ["sudo", "-n"] + cmd

    if log_cb:
        log_cb(f"$ {' '.join(cmd)}")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        raise RuntimeError("nmap not found. Install: brew install nmap (macOS) or apt install nmap (Linux)")

    # Stream stderr byte-by-byte — nmap uses \r for ETA/progress updates
    stdout_chunks = []

    async def _read_stderr():
        buf = b""
        while True:
            byte = await proc.stderr.read(1)
            if not byte:
                if buf:
                    text = buf.decode(errors="replace").strip()
                    if text and log_cb:
                        log_cb(f"[nmap] {text}")
                break
            if byte in (b"\n", b"\r"):
                text = buf.decode(errors="replace").strip()
                if text and log_cb:
                    log_cb(f"[nmap] {text}")
                buf = b""
            else:
                buf += byte

    async def _read_stdout():
        while True:
            chunk = await proc.stdout.read(8192)
            if not chunk:
                break
            stdout_chunks.append(chunk)

    await asyncio.gather(_read_stderr(), _read_stdout())
    await proc.wait()

    if log_cb:
        log_cb(f"[nmap] Process exited with code {proc.returncode}")

    xml_output = b"".join(stdout_chunks).decode(errors="replace")

    results = []

    # Parse nmap XML output
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_output)

        for host_elem in root.findall('.//host'):
            addr_elem = host_elem.find('.//address[@addrtype="ipv4"]')
            if addr_elem is None:
                continue
            ip = addr_elem.get("addr", "")

            for port_elem in host_elem.findall('.//port'):
                state = port_elem.find('state')
                if state is None or state.get("state") != "open":
                    continue

                port = int(port_elem.get("portid", 0))
                protocol = port_elem.get("protocol", "tcp")

                service_elem = port_elem.find('service')
                service_name = service_elem.get("name", "") if service_elem else ""
                service_product = service_elem.get("product", "") if service_elem else ""
                os_info = service_elem.get("ostype", "") if service_elem else ""

                # Extract NSE script output
                screen_text = ""
                nse_data = {}
                for script in port_elem.findall('script'):
                    sid = script.get("id", "")
                    output = script.get("output", "")
                    nse_data[sid] = output
                    if "tn3270-screen" in sid:
                        screen_text = output
                    elif "tn3270-info" in sid:
                        screen_text += "\n" + output

                ssl_detected = any("ssl" in s.get("id", "").lower()
                                   for s in port_elem.findall('script'))

                sys_type, apps = classify_screen(screen_text or service_product)

                host = {
                    "ip": ip,
                    "port": port,
                    "source": "nmap",
                    "is_tn3270": "tn3270" in service_name.lower() or
                                "telnet" in service_name.lower() or
                                bool(screen_text),
                    "ssl": ssl_detected or "ssl" in service_name.lower(),
                    "system_type": sys_type,
                    "applications": apps,
                    "banner": (screen_text or service_product)[:200],
                    "screen_text": screen_text[:2000],
                    "os_info": os_info or service_product,
                    "security_issues": [] if ssl_detected else [
                        "NO SSL/TLS - plaintext TN3270"
                    ],
                    "raw_data": {
                        "nse_scripts": nse_data,
                        "service_name": service_name,
                        "service_product": service_product,
                        "protocol": protocol,
                    },
                }
                results.append(host)

                if callback:
                    callback(len(results), -1, host)

    except ET.ParseError:
        raise RuntimeError("Failed to parse nmap XML output")

    return results


# ---------------------------------------------------------------------------
# Phase 1d: CICS Transaction ID Enumeration (mainframed/nmap-scripts)
# ---------------------------------------------------------------------------

async def nmap_cics_enum(targets: str, ports: str = None,
                         commands: str = None, user: str = None,
                         password: str = None, stealth: str = None,
                         log_cb=None) -> dict:
    """Run cics-enum.nse to enumerate CICS transaction IDs.

    Args:
        targets: IP/range/hostname
        ports: Port list (default: 23,992,3270)
        commands: Commands to reach CICS (default: 'cics')
        user: CICS username for authenticated enumeration
        password: CICS password for authenticated enumeration
        stealth: Stealth profile name
        log_cb: Optional callable(str) for real-time console output

    Returns dict with enumeration results.
    """
    nse_path = os.path.join(NMAP_SCRIPTS_DIR, "cics-enum.nse")
    if not os.path.isfile(nse_path):
        raise RuntimeError(f"cics-enum.nse not found at {nse_path}")

    port_str = ports or "23,992,3270"
    cmd = ["nmap", "-sV", "-p", port_str, "--open", "-oX", "-"]

    if stealth:
        profile = get_stealth_profile(stealth)
        cmd.append(profile["nmap_timing"])
    else:
        cmd.append("-T3")

    # Build script args
    script_args = []
    if commands:
        script_args.append(f"cics-enum.commands={commands}")
    if user:
        script_args.append(f"cics-enum.user={user}")
    if password:
        script_args.append(f"cics-enum.pass={password}")

    cmd.extend(["--script", nse_path])
    if script_args:
        cmd.extend(["--script-args", ",".join(script_args)])

    cmd.extend(targets.split())

    # No sudo needed — these are connect scans, not SYN scans

    if log_cb:
        log_cb(f"$ {' '.join(cmd)}")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        raise RuntimeError("nmap not found. Install: brew install nmap (macOS) or apt install nmap (Linux)")

    stdout_chunks = []
    stderr_chunks = []

    async def _read_stderr():
        buf = b""
        while True:
            byte = await proc.stderr.read(1)
            if not byte:
                if buf:
                    text = buf.decode(errors="replace").strip()
                    if text:
                        stderr_chunks.append(text)
                        if log_cb:
                            log_cb(f"[cics-enum] {text}")
                break
            if byte in (b"\n", b"\r"):
                text = buf.decode(errors="replace").strip()
                if text:
                    stderr_chunks.append(text)
                    if log_cb:
                        log_cb(f"[cics-enum] {text}")
                buf = b""
            else:
                buf += byte

    async def _read_stdout():
        while True:
            chunk = await proc.stdout.read(8192)
            if not chunk:
                break
            stdout_chunks.append(chunk)

    await asyncio.gather(_read_stderr(), _read_stdout())
    await proc.wait()

    if log_cb:
        log_cb(f"[cics-enum] Process exited with code {proc.returncode}")

    output = b"".join(stdout_chunks).decode(errors="replace")
    stderr_output = "\n".join(stderr_chunks)

    # Parse nmap output for cics-enum results
    result = {
        "targets": targets,
        "script": "cics-enum",
        "raw_output": output or stderr_output,
        "exit_code": proc.returncode,
        "stderr": stderr_output,
        "script_output": "",
        "transactions": [],
        "hosts": [],
    }

    # Parse XML output
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(output)
        script_outputs = []
        for host_elem in root.findall('.//host'):
            addr_elem = host_elem.find('.//address[@addrtype="ipv4"]')
            if addr_elem is None:
                continue
            ip = addr_elem.get("addr", "")
            for port_elem in host_elem.findall('.//port'):
                port_num = int(port_elem.get("portid", 0))
                # Collect ALL script outputs for this port (including service detection)
                for script in port_elem.findall('script'):
                    sid = script.get("id", "")
                    sout = script.get("output", "")
                    if sout:
                        script_outputs.append(f"[{sid}] {ip}:{port_num}\n{sout}")
                    if "cics-enum" in sid:
                        host_result = {
                            "ip": ip,
                            "port": port_num,
                            "cics_output": sout,
                            "transactions": [],
                        }
                        # Parse transaction IDs from tables
                        for tbl in script.findall('.//table'):
                            region = tbl.get("key", "")
                            for elem in tbl.findall('.//elem'):
                                tid = elem.text or ""
                                host_result["transactions"].append({
                                    "region": region,
                                    "id": tid.strip(),
                                })
                                result["transactions"].append({
                                    "ip": ip,
                                    "port": port_num,
                                    "region": region,
                                    "id": tid.strip(),
                                })
                        result["hosts"].append(host_result)
        # Build human-readable summary from all script outputs
        if script_outputs:
            result["script_output"] = "\n\n".join(script_outputs)
        # If no script output but scan completed, note that
        if not script_outputs and proc.returncode == 0:
            # Extract summary from runstats
            summary_elem = root.find('.//finished')
            if summary_elem is not None:
                result["script_output"] = summary_elem.get("summary", "Scan completed — no CICS service detected on target")
    except Exception as e:
        result["script_output"] = f"XML parse error: {e}\n\n{stderr_output}"

    return result


# ---------------------------------------------------------------------------
# Phase 1e: TPX User ID Enumeration (mainframed/nmap-scripts)
# ---------------------------------------------------------------------------

async def nmap_tpx_enum(targets: str, ports: str = None,
                        commands: str = None, stealth: str = None,
                        log_cb=None) -> dict:
    """Run tpx-enum.nse to enumerate TPX user IDs.

    Args:
        targets: IP/range/hostname
        ports: Port list (default: 23,992,3270)
        commands: Commands to reach TPX (default: 'tpx')
        stealth: Stealth profile name
        log_cb: Optional callable(str) for real-time console output

    Returns dict with enumeration results.
    """
    nse_path = os.path.join(NMAP_SCRIPTS_DIR, "tpx-enum.nse")
    if not os.path.isfile(nse_path):
        raise RuntimeError(f"tpx-enum.nse not found at {nse_path}")

    port_str = ports or "23,992,3270"
    cmd = ["nmap", "-sV", "-p", port_str, "--open", "-oX", "-"]

    if stealth:
        profile = get_stealth_profile(stealth)
        cmd.append(profile["nmap_timing"])
    else:
        cmd.append("-T3")

    script_args = []
    if commands:
        script_args.append(f"tpx-enum.commands={commands}")

    cmd.extend(["--script", nse_path])
    if script_args:
        cmd.extend(["--script-args", ",".join(script_args)])

    cmd.extend(targets.split())

    # No sudo needed — these are connect scans, not SYN scans

    if log_cb:
        log_cb(f"$ {' '.join(cmd)}")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        raise RuntimeError("nmap not found. Install: brew install nmap (macOS) or apt install nmap (Linux)")

    stdout_chunks = []
    stderr_chunks = []

    async def _read_stderr():
        buf = b""
        while True:
            byte = await proc.stderr.read(1)
            if not byte:
                if buf:
                    text = buf.decode(errors="replace").strip()
                    if text:
                        stderr_chunks.append(text)
                        if log_cb:
                            log_cb(f"[tpx-enum] {text}")
                break
            if byte in (b"\n", b"\r"):
                text = buf.decode(errors="replace").strip()
                if text:
                    stderr_chunks.append(text)
                    if log_cb:
                        log_cb(f"[tpx-enum] {text}")
                buf = b""
            else:
                buf += byte

    async def _read_stdout():
        while True:
            chunk = await proc.stdout.read(8192)
            if not chunk:
                break
            stdout_chunks.append(chunk)

    await asyncio.gather(_read_stderr(), _read_stdout())
    await proc.wait()

    if log_cb:
        log_cb(f"[tpx-enum] Process exited with code {proc.returncode}")

    output = b"".join(stdout_chunks).decode(errors="replace")
    stderr_output = "\n".join(stderr_chunks)

    result = {
        "targets": targets,
        "script": "tpx-enum",
        "raw_output": output or stderr_output,
        "exit_code": proc.returncode,
        "stderr": stderr_output,
        "script_output": "",
        "users": [],
        "hosts": [],
    }

    # Parse XML output
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(output)
        script_outputs = []
        for host_elem in root.findall('.//host'):
            addr_elem = host_elem.find('.//address[@addrtype="ipv4"]')
            if addr_elem is None:
                continue
            ip = addr_elem.get("addr", "")
            for port_elem in host_elem.findall('.//port'):
                port_num = int(port_elem.get("portid", 0))
                for script in port_elem.findall('script'):
                    sid = script.get("id", "")
                    sout = script.get("output", "")
                    if sout:
                        script_outputs.append(f"[{sid}] {ip}:{port_num}\n{sout}")
                    if "tpx-enum" in sid:
                        host_result = {
                            "ip": ip,
                            "port": port_num,
                            "tpx_output": sout,
                            "users": [],
                        }
                        for elem in script.findall('.//elem'):
                            uid = elem.text or ""
                            host_result["users"].append(uid.strip())
                            result["users"].append({
                                "ip": ip,
                                "port": port_num,
                                "user": uid.strip(),
                            })
                        result["hosts"].append(host_result)
        if script_outputs:
            result["script_output"] = "\n\n".join(script_outputs)
        if not script_outputs and proc.returncode == 0:
            summary_elem = root.find('.//finished')
            if summary_elem is not None:
                result["script_output"] = summary_elem.get("summary", "Scan completed — no TPX service detected on target")
    except Exception as e:
        result["script_output"] = f"XML parse error: {e}\n\n{stderr_output}"

    return result


# ---------------------------------------------------------------------------
# Phase 2: Async TN3270 Prober (our own protocol handler)
# ---------------------------------------------------------------------------

# Telnet constants
IAC = 0xFF
DONT = 0xFE
DO = 0xFD
WONT = 0xFC
WILL = 0xFB
SB = 0xFA
SE = 0xF0
TN3270E = 0x28

# EBCDIC to ASCII
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


SCREEN_ROWS = 24
SCREEN_COLS = 80
SCREEN_SIZE = SCREEN_ROWS * SCREEN_COLS


def _decode_buffer_address(b1: int, b2: int) -> int:
    """Decode a 3270 buffer address from two bytes (12-bit or 14-bit)."""
    if b1 & 0xC0 == 0x00:
        return ((b1 & 0x3F) << 8) | b2
    else:
        return ((b1 & 0x3F) << 6) | (b2 & 0x3F)


def _render_screen_grid(data: bytes) -> list[str]:
    """Parse 3270 data stream into an 80x24 screen buffer.

    Handles SBA, SF, SFE, RA, IC orders to place characters at correct positions.
    Returns list of 24 strings, each 80 chars wide.
    """
    buf = [' '] * SCREEN_SIZE
    pos = 0
    i = 0

    while i < len(data):
        b = data[i]

        # Skip telnet IAC sequences
        if b == IAC and i + 1 < len(data):
            cmd = data[i + 1]
            if cmd in (DO, DONT, WILL, WONT):
                i += 3; continue
            elif cmd == SB:
                while i < len(data) - 1:
                    if data[i] == IAC and data[i + 1] == SE:
                        i += 2; break
                    i += 1
                continue
            elif cmd == IAC:
                i += 2; continue
            else:
                i += 2; continue

        # Write/Erase commands (skip the command byte, data follows)
        if b in (0xF1, 0xF5, 0x7E, 0x6E, 0xF6):
            i += 1
            if b in (0xF5, 0x7E):
                buf = [' '] * SCREEN_SIZE
                pos = 0
            continue

        # WCC byte after write command
        if b in (0xC3, 0xC2, 0xC1, 0xC0, 0x40):
            i += 1; continue

        # SBA — Set Buffer Address
        if b == 0x11:
            if i + 2 < len(data):
                pos = _decode_buffer_address(data[i + 1], data[i + 2]) % SCREEN_SIZE
                i += 3
            else:
                i += 1
            continue

        # SF — Start Field (1 attribute byte)
        if b == 0x1D:
            if pos < SCREEN_SIZE:
                buf[pos] = ' '
            pos = (pos + 1) % SCREEN_SIZE
            i += 2
            continue

        # SFE — Start Field Extended
        if b == 0x29:
            if i + 1 < len(data):
                pairs = data[i + 1]
                skip = 2 + (pairs * 2)
                if pos < SCREEN_SIZE:
                    buf[pos] = ' '
                pos = (pos + 1) % SCREEN_SIZE
                i += skip
            else:
                i += 1
            continue

        # SA — Set Attribute (skip 2 bytes)
        if b == 0x28:
            i += 3; continue

        # RA — Repeat to Address
        if b == 0x3C:
            if i + 3 < len(data):
                end_pos = _decode_buffer_address(data[i + 1], data[i + 2]) % SCREEN_SIZE
                fill_byte = data[i + 3]
                fill_char = EBCDIC_TO_ASCII.get(fill_byte, ' ') if fill_byte != 0x00 else ' '
                while pos != end_pos:
                    if pos < SCREEN_SIZE:
                        buf[pos] = fill_char
                    pos = (pos + 1) % SCREEN_SIZE
                i += 4
            else:
                i += 1
            continue

        # IC — Insert Cursor (no data)
        if b == 0x13:
            i += 1; continue

        # PT — Program Tab
        if b == 0x05:
            i += 1; continue

        # MF — Modify Field
        if b == 0x2C:
            if i + 1 < len(data):
                pairs = data[i + 1]
                i += 2 + (pairs * 2)
            else:
                i += 1
            continue

        # GE — Graphic Escape (skip next byte, treat as char)
        if b == 0x08:
            i += 2; continue

        # Regular data — EBCDIC character
        ch = EBCDIC_TO_ASCII.get(b)
        if ch is None:
            ch = ' ' if b == 0x00 else (chr(b) if 0x20 <= b <= 0x7E else ' ')
        if pos < SCREEN_SIZE:
            buf[pos] = ch
        pos = (pos + 1) % SCREEN_SIZE
        i += 1

    # Convert buffer to 24 rows of 80 chars
    rows = []
    for r in range(SCREEN_ROWS):
        row = ''.join(buf[r * SCREEN_COLS:(r + 1) * SCREEN_COLS])
        rows.append(row)
    return rows


def _save_screenshot(ip: str, port: int, rows: list[str], raw_bytes: bytes = None) -> dict:
    """Save screen capture as .txt and .png files.

    Returns dict with relative paths: {"txt": "...", "png": "..."} or empty if nothing to save.
    """
    if not rows or all(r.strip() == '' for r in rows):
        return {"txt": "", "png": ""}

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_ip = ip.replace(".", "-").replace(":", "-")
    basename = f"{safe_ip}_{port}_{ts}"

    # Save text file
    txt_filename = f"{basename}.txt"
    txt_path = os.path.join(SCREENSHOTS_DIR, txt_filename)
    header = f"{'=' * 80}\n  TN3270 Screen Capture: {ip}:{port}\n  Captured: {datetime.now(timezone.utc).isoformat()}\n{'=' * 80}\n"
    with open(txt_path, 'w') as f:
        f.write(header)
        f.write('+' + '-' * 80 + '+\n')
        for row in rows:
            f.write('|' + row + '|\n')
        f.write('+' + '-' * 80 + '+\n')

    txt_rel = f"/static/screenshots/{txt_filename}"

    # Render PNG
    png_rel = ""
    try:
        from PIL import Image, ImageDraw, ImageFont

        char_w, char_h = 9, 18
        padding = 20
        header_h = 40
        img_w = (SCREEN_COLS * char_w) + (padding * 2)
        img_h = (SCREEN_ROWS * char_h) + (padding * 2) + header_h

        img = Image.new('RGB', (img_w, img_h), '#0a0e14')
        draw = ImageDraw.Draw(img)

        # Try monospace font
        font = None
        for font_name in [
            '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
            '/usr/share/fonts/TTF/DejaVuSansMono.ttf',
            '/System/Library/Fonts/Menlo.ttc',
            '/System/Library/Fonts/Monaco.dfont',
        ]:
            try:
                font = ImageFont.truetype(font_name, 14)
                break
            except (OSError, IOError):
                continue
        if not font:
            font = ImageFont.load_default()

        # Header bar
        draw.rectangle([0, 0, img_w, header_h], fill='#1a2a3a')
        draw.text((padding, 10), f"  {ip}:{port}", fill='#4af', font=font)

        # Screen content
        y = padding + header_h
        for row in rows:
            x = padding
            for ch in row:
                color = '#00ff41' if ch.strip() else '#0a0e14'
                draw.text((x, y), ch, fill=color, font=font)
                x += char_w
            y += char_h

        # Border
        bx = padding - 2
        by = padding + header_h - 2
        bw = SCREEN_COLS * char_w + 4
        bh = SCREEN_ROWS * char_h + 4
        draw.rectangle([bx, by, bx + bw, by + bh], outline='#2a3a5a', width=1)

        png_filename = f"{basename}.png"
        png_path = os.path.join(SCREENSHOTS_DIR, png_filename)
        img.save(png_path, 'PNG')
        png_rel = f"/static/screenshots/{png_filename}"
    except ImportError:
        pass  # Pillow not installed, skip PNG
    except Exception:
        pass  # Font/rendering error, skip PNG

    return {"txt": txt_rel, "png": png_rel}


def _extract_3270_text(data: bytes) -> str:
    """Extract readable text from TN3270 data stream."""
    chars = []
    i = 0
    while i < len(data):
        b = data[i]
        if b == IAC and i + 1 < len(data):
            if data[i + 1] in (DO, DONT, WILL, WONT):
                i += 3; continue
            elif data[i + 1] == SB:
                while i < len(data) and not (data[i] == IAC and i + 1 < len(data) and data[i + 1] == SE):
                    i += 1
                i += 2; continue
            elif data[i + 1] == IAC:
                i += 2; continue
        if b in (0x05, 0x11, 0x12, 0x13, 0x1D, 0x28, 0x29, 0x2C, 0x3C, 0xF1, 0xF5, 0x7D, 0x6E):
            i += 1
            if b == 0x11 and i + 1 < len(data): i += 2
            elif b == 0x1D and i < len(data): i += 1
            elif b == 0x29 and i < len(data):
                pairs = data[i] if i < len(data) else 0
                i += 1 + (pairs * 2)
            continue
        if b in EBCDIC_TO_ASCII:
            chars.append(EBCDIC_TO_ASCII[b])
        elif b == 0x00:
            chars.append(' ')
        elif 0x20 <= b <= 0x7E:
            chars.append(chr(b))
        i += 1
    text = ''.join(chars)
    return re.sub(r'\s+', ' ', text).strip()


async def probe_host(ip: str, port: int, timeout: float = 8.0) -> dict:
    """Connect to a single host, do TN3270 negotiation, capture screen.

    Returns a host dict with fingerprint data.
    """
    result = {
        "ip": ip,
        "port": port,
        "source": "probe",
        "is_tn3270": False,
        "ssl": False,
        "system_type": "unknown",
        "applications": [],
        "banner": "",
        "screen_text": "",
        "security_issues": [],
    }

    # First check SSL
    try:
        import ssl as ssl_mod
        ctx = ssl_mod.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl_mod.CERT_NONE
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port, ssl=ctx), timeout=5.0
        )
        writer.close()
        if hasattr(writer, "wait_closed"):
            await writer.wait_closed()
        result["ssl"] = True
    except Exception:
        result["ssl"] = False
        result["security_issues"].append("NO SSL/TLS - plaintext TN3270")

    # Now do TN3270 negotiation
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port), timeout=timeout
        )

        all_data = b""
        screen_data = b""

        try:
            for _ in range(15):
                chunk = await asyncio.wait_for(reader.read(4096), timeout=2.0)
                if not chunk:
                    break
                all_data += chunk

                response = b""
                i = 0
                data_portion = b""
                while i < len(chunk):
                    if chunk[i] == IAC and i + 1 < len(chunk):
                        cmd = chunk[i + 1]
                        if cmd in (DO, DONT, WILL, WONT) and i + 2 < len(chunk):
                            opt = chunk[i + 2]
                            if cmd == DO:
                                if opt in (0x18, 0x19, 0x00):
                                    response += bytes([IAC, WILL, opt])
                                else:
                                    response += bytes([IAC, WONT, opt])
                            elif cmd == WILL:
                                if opt in (0x18, 0x19, 0x00, TN3270E):
                                    response += bytes([IAC, DO, opt])
                                else:
                                    response += bytes([IAC, DONT, opt])
                            i += 3; continue
                        elif cmd == SB:
                            sb_start = i
                            while i < len(chunk) - 1:
                                if chunk[i] == IAC and chunk[i + 1] == SE:
                                    if i > sb_start + 2 and chunk[sb_start + 2] == 0x18 and chunk[sb_start + 3] == 0x01:
                                        response += bytes([IAC, SB, 0x18, 0x00]) + b'IBM-3278-2' + bytes([IAC, SE])
                                    i += 2; break
                                i += 1
                            continue
                        elif cmd == IAC:
                            data_portion += bytes([IAC])
                            i += 2; continue
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
            result["is_tn3270"] = True
            raw = screen_data if screen_data else all_data
            text = _extract_3270_text(raw)
            result["screen_text"] = text[:2000]
            result["banner"] = text[:200]
            sys_type, apps = classify_screen(text)
            result["system_type"] = sys_type
            result["applications"] = apps

            # Render 80x24 grid and save screenshot
            try:
                rows = _render_screen_grid(raw)
                result["screen_rows"] = rows
                shots = _save_screenshot(ip, port, rows, raw)
                result["screenshot_txt"] = shots.get("txt", "")
                result["screenshot_png"] = shots.get("png", "")
            except Exception:
                pass  # Don't fail probe on screenshot error

    except Exception as e:
        result["error"] = str(e)

    return result


async def probe_batch(hosts: list[dict], concurrency: int = 50,
                      timeout: float = 8.0, stealth: str = None,
                      callback=None, log_cb=None) -> list[dict]:
    """Probe a batch of hosts concurrently with rate control.

    Args:
        hosts: List of {"ip": ..., "port": ...} dicts
        concurrency: Max concurrent connections (overridden by stealth)
        timeout: Per-host timeout (overridden by stealth)
        stealth: Stealth profile name for rate control
        callback: Optional callable(completed, total, result)
        log_cb: Optional callable(str) for real-time console output

    Returns list of probed host dicts.
    """
    delay_min = 0.0
    delay_max = 0.0
    randomize = False

    if stealth:
        profile = get_stealth_profile(stealth)
        concurrency = profile["probe_concurrency"]
        timeout = profile["probe_timeout"]
        delay_min = profile["probe_delay_min"]
        delay_max = profile["probe_delay_max"]
        randomize = profile["randomize_order"]

    # Shuffle host order to avoid sequential IP scanning
    work = list(hosts)
    if randomize:
        random.shuffle(work)

    sem = asyncio.Semaphore(concurrency)
    results = []
    total = len(work)
    completed = 0

    if log_cb:
        log_cb(f"[probe] Starting batch: {total} hosts, concurrency={concurrency}, "
               f"delay={delay_min:.1f}-{delay_max:.1f}s" +
               (", randomized order" if randomize else ""))

    async def _probe_one(h):
        nonlocal completed
        async with sem:
            # Random jitter delay before each probe
            if delay_max > 0:
                jitter = random.uniform(delay_min, delay_max)
                if log_cb:
                    log_cb(f"[probe] Waiting {jitter:.1f}s jitter before {h['ip']}:{h['port']}")
                await asyncio.sleep(jitter)

            if log_cb:
                log_cb(f"[probe] Connecting {h['ip']}:{h['port']}...")
            result = await probe_host(h["ip"], h["port"], timeout)

            # Log result
            if log_cb:
                status = "TN3270" if result.get("is_tn3270") else "no-tn3270"
                sys_t = result.get("system_type", "?")
                err = result.get("error", "")
                if err:
                    log_cb(f"[probe] {h['ip']}:{h['port']} → ERROR: {err}")
                else:
                    shot = result.get("screenshot_txt", "")
                    shot_info = f" | 📷 {shot.split('/')[-1]}" if shot else ""
                    log_cb(f"[probe] {h['ip']}:{h['port']} → {status} | {sys_t}{shot_info}")

            # Merge source info from original
            if h.get("source") and h["source"] != "probe":
                result["source"] = h["source"] + "+probe"
            # Carry forward metadata
            for key in ("org", "country", "isp", "raw_data"):
                if key in h and h[key]:
                    result[key] = h[key]
            results.append(result)
            completed += 1
            if callback:
                callback(completed, total, result)
            return result

    tasks = [_probe_one(h) for h in work]
    await asyncio.gather(*tasks, return_exceptions=True)
    return results


# ---------------------------------------------------------------------------
# Orchestrator: Run full discovery pipeline
# ---------------------------------------------------------------------------

class DiscoveryEngine:
    """Orchestrates the full discovery pipeline."""

    LOG_MAX = 2000  # max log lines to keep in memory

    def __init__(self, stealth: str = "polite"):
        self.running = False
        self.stealth = stealth
        self.progress = {"phase": "", "completed": 0, "total": 0, "current": "",
                         "stealth": stealth}
        self.results = []
        self._log: list[dict] = []
        self._log_seq = 0

    def log_line(self, text: str):
        """Append a timestamped line to the in-memory console log."""
        self._log_seq += 1
        entry = {"seq": self._log_seq, "ts": _now(), "text": text}
        self._log.append(entry)
        if len(self._log) > self.LOG_MAX:
            self._log = self._log[-self.LOG_MAX:]

    def get_log(self, since_seq: int = 0) -> list[dict]:
        """Return log lines with seq > since_seq."""
        return [e for e in self._log if e["seq"] > since_seq]

    async def run_shodan(self, api_key: str, query: str = None,
                         max_results: int = 500, probe: bool = True,
                         stealth: str = None) -> dict:
        """Full Shodan discovery: search + optional probe."""
        stealth = stealth or self.stealth
        self.running = True
        self.progress = {"phase": "shodan_search", "completed": 0,
                         "total": max_results, "current": "Querying Shodan..."}
        self.log_line(f"=== Shodan Discovery (stealth={stealth}) ===")
        self.log_line(f"Query: {query or 'default TN3270 ports'}  |  Max: {max_results}")
        conn = _get_db()

        scan_id = conn.execute(
            "INSERT INTO scans (started, source, query, status) VALUES (?,?,?,?)",
            (_now(), "shodan", query or "default", "running")
        ).lastrowid
        conn.commit()

        try:
            def on_result(done, total, host):
                self.progress["completed"] = done
                self.progress["current"] = f"{host['ip']}:{host['port']}"
                self.log_line(f"[shodan] {done}/{total} — {host['ip']}:{host['port']} ({host.get('org','')})")

            hosts = await shodan_search(api_key, query, max_results, on_result)

            # Store raw Shodan results
            for h in hosts:
                _upsert_host(conn, h)

            # Phase 2: Probe each hit with our TN3270 handler
            if probe and hosts:
                self.progress["phase"] = "probe"
                self.progress["completed"] = 0
                self.progress["total"] = len(hosts)

                def on_probe(done, total, result):
                    self.progress["completed"] = done
                    self.progress["current"] = f"{result['ip']}:{result['port']} → {result.get('system_type', '?')}"

                probed = await probe_batch(hosts, stealth=stealth, callback=on_probe, log_cb=self.log_line)

                for h in probed:
                    _upsert_host(conn, h)

                hosts = probed

            self.log_line(f"=== Shodan complete: {len(hosts)} hosts found ===")
            conn.execute(
                "UPDATE scans SET finished=?, status=?, hosts_found=? WHERE id=?",
                (_now(), "done", len(hosts), scan_id)
            )
            conn.commit()

            self.results = hosts
            self.running = False
            return {"scan_id": scan_id, "hosts_found": len(hosts), "hosts": hosts}

        except Exception as e:
            self.log_line(f"ERROR: {e}")
            conn.execute(
                "UPDATE scans SET finished=?, status=?, error=? WHERE id=?",
                (_now(), "error", str(e), scan_id)
            )
            conn.commit()
            self.running = False
            raise

    async def run_masscan(self, targets: str, ports: str = None,
                          rate: int = 10000, probe: bool = True,
                          stealth: str = None) -> dict:
        """Full masscan discovery: sweep + probe."""
        stealth = stealth or self.stealth
        self.running = True
        self.progress = {"phase": "masscan_sweep", "completed": 0,
                         "total": -1, "current": f"Scanning {targets}..."}
        # Show effective rate after stealth override
        effective_rate = rate
        if stealth:
            effective_rate = get_stealth_profile(stealth)["masscan_rate"]
        self.log_line(f"=== masscan Discovery (stealth={stealth}) ===")
        self.log_line(f"Targets: {targets}  |  Effective rate: {effective_rate} pps")
        self.log_line(f"Ports: {ports or ','.join(str(p) for p in TN3270_PORTS)}")
        conn = _get_db()

        scan_id = conn.execute(
            "INSERT INTO scans (started, source, targets, status) VALUES (?,?,?,?)",
            (_now(), "masscan", targets, "running")
        ).lastrowid
        conn.commit()

        try:
            hosts = await masscan_sweep(targets, ports, rate, stealth=stealth, log_cb=self.log_line)

            self.log_line(f"[masscan] Sweep done: {len(hosts)} open ports found")
            for h in hosts:
                _upsert_host(conn, h)

            if probe and hosts:
                self.progress["phase"] = "probe"
                self.progress["completed"] = 0
                self.progress["total"] = len(hosts)

                def on_probe(done, total, result):
                    self.progress["completed"] = done
                    self.progress["current"] = f"{result['ip']}:{result['port']} → {result.get('system_type', '?')}"

                probed = await probe_batch(hosts, stealth=stealth, callback=on_probe, log_cb=self.log_line)
                for h in probed:
                    _upsert_host(conn, h)
                hosts = probed

            self.log_line(f"=== masscan complete: {len(hosts)} hosts ===")
            conn.execute(
                "UPDATE scans SET finished=?, status=?, hosts_found=? WHERE id=?",
                (_now(), "done", len(hosts), scan_id)
            )
            conn.commit()

            self.results = hosts
            self.running = False
            return {"scan_id": scan_id, "hosts_found": len(hosts), "hosts": hosts}

        except Exception as e:
            self.log_line(f"ERROR: {e}")
            conn.execute(
                "UPDATE scans SET finished=?, status=?, error=? WHERE id=?",
                (_now(), "error", str(e), scan_id)
            )
            conn.commit()
            self.running = False
            raise

    async def run_nmap(self, targets: str, ports: str = None,
                       nse: bool = True, probe: bool = True,
                       stealth: str = None) -> dict:
        """Full nmap discovery with NSE scripts + probe for screenshots."""
        stealth = stealth or self.stealth
        self.running = True
        self.progress = {"phase": "nmap_scan", "completed": 0,
                         "total": -1, "current": f"nmap scanning {targets}..."}
        self.log_line(f"=== nmap Discovery (stealth={stealth}) ===")
        self.log_line(f"Targets: {targets}")
        conn = _get_db()

        scan_id = conn.execute(
            "INSERT INTO scans (started, source, targets, status) VALUES (?,?,?,?)",
            (_now(), "nmap", targets, "running")
        ).lastrowid
        conn.commit()

        try:
            hosts = await nmap_scan(targets, ports, nse, stealth=stealth, log_cb=self.log_line)

            self.log_line(f"[nmap] Scan done: {len(hosts)} hosts found")
            for h in hosts:
                _upsert_host(conn, h)

            # Probe phase: TN3270 negotiation + screenshot capture
            if probe and hosts:
                tn_hosts = [h for h in hosts if h.get("is_tn3270")]
                if tn_hosts:
                    self.progress["phase"] = "probe"
                    self.progress["completed"] = 0
                    self.progress["total"] = len(tn_hosts)
                    self.log_line(f"[nmap] Probing {len(tn_hosts)} TN3270 hosts for screenshots...")

                    def on_probe(done, total, result):
                        self.progress["completed"] = done
                        self.progress["current"] = f"{result['ip']}:{result['port']} → {result.get('system_type', '?')}"

                    probed = await probe_batch(tn_hosts, stealth=stealth, callback=on_probe, log_cb=self.log_line)
                    for h in probed:
                        _upsert_host(conn, h)
                    # Merge probed results back
                    probed_ips = {(h["ip"], h["port"]) for h in probed}
                    hosts = [h for h in hosts if (h["ip"], h["port"]) not in probed_ips] + probed

            conn.execute(
                "UPDATE scans SET finished=?, status=?, hosts_found=? WHERE id=?",
                (_now(), "done", len(hosts), scan_id)
            )
            conn.commit()

            self.results = hosts
            self.running = False
            self.log_line(f"=== nmap complete: {len(hosts)} hosts ===")
            return {"scan_id": scan_id, "hosts_found": len(hosts), "hosts": hosts}

        except Exception as e:
            self.log_line(f"ERROR: {e}")
            conn.execute(
                "UPDATE scans SET finished=?, status=?, error=? WHERE id=?",
                (_now(), "error", str(e), scan_id)
            )
            conn.commit()
            self.running = False
            raise

    def stop(self):
        self.log_line("=== Discovery stopped by user ===")
        self.running = False


# ---------------------------------------------------------------------------
# Database query helpers (for API/UI)
# ---------------------------------------------------------------------------

def get_all_hosts(limit: int = 500, offset: int = 0,
                  system_type: str = None, no_ssl_only: bool = False) -> list[dict]:
    """Get all discovered hosts from the database."""
    conn = _get_db()
    query = "SELECT * FROM hosts WHERE 1=1"
    params = []

    if system_type:
        query += " AND system_type=?"
        params.append(system_type)
    if no_ssl_only:
        query += " AND ssl=0"

    query += " ORDER BY last_seen DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_host_count() -> dict:
    """Get summary counts."""
    conn = _get_db()
    total = conn.execute("SELECT COUNT(*) FROM hosts").fetchone()[0]
    tn3270 = conn.execute("SELECT COUNT(*) FROM hosts WHERE is_tn3270=1").fetchone()[0]
    no_ssl = conn.execute("SELECT COUNT(*) FROM hosts WHERE ssl=0 AND is_tn3270=1").fetchone()[0]

    by_type = {}
    for row in conn.execute("SELECT system_type, COUNT(*) as cnt FROM hosts WHERE is_tn3270=1 GROUP BY system_type"):
        by_type[row["system_type"]] = row["cnt"]

    by_country = {}
    for row in conn.execute("SELECT country, COUNT(*) as cnt FROM hosts WHERE country != '' GROUP BY country ORDER BY cnt DESC LIMIT 20"):
        by_country[row["country"]] = row["cnt"]

    return {
        "total": total,
        "tn3270_confirmed": tn3270,
        "no_ssl": no_ssl,
        "by_system_type": by_type,
        "by_country": by_country,
    }


def get_scan_history(limit: int = 20) -> list[dict]:
    """Get recent scan history."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT * FROM scans ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def delete_host(host_id: int) -> bool:
    conn = _get_db()
    conn.execute("DELETE FROM hosts WHERE id=?", (host_id,))
    conn.commit()
    return True


def clear_all_hosts() -> int:
    conn = _get_db()
    count = conn.execute("SELECT COUNT(*) FROM hosts").fetchone()[0]
    conn.execute("DELETE FROM hosts")
    conn.commit()
    return count
