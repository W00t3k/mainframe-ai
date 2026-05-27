"""
RAKF API Routes

Endpoints for RAKF (Resource Access Control Facility for MVS 3.8j) management.
Fetches security tables via FTP and sends reload commands via Hercules console.
"""

import re
import urllib.request
import urllib.parse
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["rakf"])

# Hercules HTTP API
HERC_HTTP = "http://localhost:8038"

# FTP credentials for MVS
FTP_HOST = "localhost"
FTP_PORT = 2121
FTP_USER = "HERC01"
FTP_PASS = "CUL8TR"

# RAKF table datasets
USERS_DATASET = "SYS1.SECURE.CNTL(USERS)"
PROFILES_DATASET = "SYS1.SECURE.CNTL(PROFILES)"


def herc_cmd(cmd: str) -> str:
    """Send command to Hercules HTTP console."""
    try:
        url = f"{HERC_HTTP}/cgi-bin/tasks/cmd?cmd={urllib.parse.quote(cmd)}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            return re.sub(r'<[^>]+>', '', resp.read().decode('utf-8', errors='replace')).strip()
    except Exception as e:
        return f"ERROR: {e}"


def ftp_get_dataset(dataset: str) -> str:
    """Fetch a dataset from MVS via FTP."""
    import ftplib
    try:
        ftp = ftplib.FTP()
        ftp.connect(FTP_HOST, FTP_PORT, timeout=15)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.voidcmd("SITE FILETYPE=SEQ")

        lines = []
        def callback(line):
            lines.append(line)

        # Quote the dataset name for MVS
        ftp.retrlines(f"RETR '{dataset}'", callback)
        ftp.quit()
        return "\n".join(lines)
    except ftplib.error_perm as e:
        return f"FTP_ERROR: {e}"
    except Exception as e:
        return f"ERROR: {e}"


def parse_users_table(raw: str) -> list:
    """Parse RAKF users table into structured data."""
    users = []
    for line in raw.split("\n"):
        line = line.rstrip()
        if not line or line.startswith("*") or line.startswith("/"):
            continue
        # Format: USERNAME GROUP    *PASSWORD O
        # Positions: 0-7 username, 9-16 group, 18-26 password (with * prefix if non-expiring), 28 ops flag
        parts = line.split()
        if len(parts) >= 3:
            username = parts[0]
            group = parts[1]
            password_field = parts[2] if len(parts) > 2 else ""
            ops = parts[3] if len(parts) > 3 else ""

            non_expiring = password_field.startswith("*")
            password = password_field[1:] if non_expiring else password_field

            # Calculate risk
            risk = "low"
            if password.upper() == username.upper():
                risk = "critical"
            elif len(password) < 4:
                risk = "high"
            elif password.upper() in ["PASSWORD", "PASS", "SECRET", "ADMIN", "TEST"]:
                risk = "high"
            elif ops == "Y":
                risk = "medium"

            users.append({
                "username": username,
                "group": group,
                "password": password,
                "non_expiring": non_expiring,
                "operations": ops == "Y",
                "risk": risk
            })
    return users


@router.get("/rakf/tables")
async def api_rakf_tables():
    """Fetch RAKF users and profiles tables from MVS via FTP."""
    result = {
        "users": [],
        "profiles_raw": "",
        "users_raw": "",
        "error": None
    }

    # Fetch users table
    users_raw = ftp_get_dataset(USERS_DATASET)
    if users_raw.startswith("ERROR") or users_raw.startswith("FTP_ERROR"):
        result["error"] = f"Could not fetch users table: {users_raw}"
    else:
        result["users_raw"] = users_raw
        result["users"] = parse_users_table(users_raw)

    # Fetch profiles table
    profiles_raw = ftp_get_dataset(PROFILES_DATASET)
    if profiles_raw.startswith("ERROR") or profiles_raw.startswith("FTP_ERROR"):
        if result["error"]:
            result["error"] += f"; Could not fetch profiles: {profiles_raw}"
        else:
            result["error"] = f"Could not fetch profiles table: {profiles_raw}"
    else:
        result["profiles_raw"] = profiles_raw

    return JSONResponse(result)


@router.post("/rakf/reload")
async def api_rakf_reload(request: Request):
    """Send RAKF reload command to MVS via Hercules console."""
    try:
        data = await request.json()
    except:
        data = {}

    table = data.get("table", "users").lower()

    if table == "users":
        cmd = "S RAKFUSER"
    elif table == "profiles":
        cmd = "S RAKFPROF"
    else:
        return JSONResponse({"success": False, "error": f"Unknown table: {table}"})

    # Send command to Hercules console
    response = herc_cmd(cmd)

    if "ERROR" in response:
        return JSONResponse({"success": False, "error": response})

    return JSONResponse({"success": True, "command": cmd, "response": response})


@router.get("/rakf/status")
async def api_rakf_status():
    """Check if RAKF is active on MVS."""
    # Try to query Hercules
    response = herc_cmd("qd 390")

    if "ERROR" in response:
        return JSONResponse({"active": False, "error": response})

    return JSONResponse({"active": True, "hercules": "online"})


@router.post("/rakf/submit-jcl")
async def api_rakf_submit_jcl(request: Request):
    """Submit JCL to add/modify RAKF entries."""
    try:
        data = await request.json()
    except:
        return JSONResponse({"success": False, "error": "Invalid JSON"})

    jcl = data.get("jcl", "")
    if not jcl:
        return JSONResponse({"success": False, "error": "No JCL provided"})

    # Write JCL to temp file and submit via card reader
    import tempfile
    import os

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jcl', delete=False) as f:
            f.write(jcl)
            jcl_path = f.name

        # Submit via Hercules card reader
        response = herc_cmd(f"devinit 00c {jcl_path} ascii eof")

        # Clean up
        os.unlink(jcl_path)

        if "ERROR" in response:
            return JSONResponse({"success": False, "error": response})

        return JSONResponse({"success": True, "message": "JCL submitted to card reader"})

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})
