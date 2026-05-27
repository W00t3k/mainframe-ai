"""
RAKF API Routes

Endpoints for RAKF (Resource Access Control Facility for MVS 3.8j) management.

IMPORTANT: TK5's FTP server cannot access PDS members (like SYS1.SECURE.CNTL(USERS)).
The "Fetch from MVS" feature requires either:
1. A different FTP server that supports PDS member access
2. Using TN3270/ISPF to extract the data
3. Or the page will show default RAKF configuration

The reload commands work via Hercules console API.
"""

import re
import urllib.request
import urllib.parse
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["rakf"])

# Hercules HTTP API
HERC_HTTP = "http://localhost:8038"

# RAKF table datasets (PDS members - NOT accessible via TK5 FTP)
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


@router.get("/rakf/tables")
async def api_rakf_tables():
    """Fetch RAKF users and profiles tables from MVS.

    NOTE: TK5's FTP server cannot access PDS members like SYS1.SECURE.CNTL(USERS).
    This endpoint returns an informative error - the UI falls back to default data.

    To get live RAKF data, use ISPF 3.4 to browse SYS1.SECURE.CNTL members.
    """
    return JSONResponse({
        "users": [],
        "profiles_raw": "",
        "users_raw": "",
        "error": "TK5 FTP cannot access PDS members. Use ISPF (option 3.4) to browse "
                 "SYS1.SECURE.CNTL(USERS) and SYS1.SECURE.CNTL(PROFILES). "
                 "The page shows default TK5 RAKF configuration."
    })


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
