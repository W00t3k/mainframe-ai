"""
FTP API Routes — wires frontend to FTPService.

Endpoints:
  GET  /ftp/status       - connection status
  POST /ftp/connect      - connect to MVS FTP server
  POST /ftp/disconnect   - disconnect
  POST /ftp/list         - list datasets (prefix filter or PDS members)
  POST /ftp/download     - download dataset content
  POST /ftp/test-ebcdic  - compare ASCII vs binary download
  POST /ftp/test-all     - run automated test suite
  POST /ftp/submit-card  - submit JCL via card reader (port 3505)
  GET  /ftp/transfers    - get transfer log
"""

import socket
import logging
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from app.services.ftp import get_ftp_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ftp"])


# ── Request Models ────────────────────────────────────────────────────


class ConnectRequest(BaseModel):
    host: str = "localhost"
    port: int = 2121
    user: str = "HERC01"
    password: str = "CUL8TR"


class ListRequest(BaseModel):
    prefix: Optional[str] = ""
    pds: Optional[str] = None


class DownloadRequest(BaseModel):
    dataset: str
    mode: str = "ascii"


class EbcdicTestRequest(BaseModel):
    dataset: str


class TestAllRequest(BaseModel):
    host: str = "localhost"
    port: int = 2121
    user: str = "HERC01"
    password: str = "CUL8TR"


class SubmitCardRequest(BaseModel):
    content: str


# ── Endpoints ─────────────────────────────────────────────────────────


@router.get("/ftp/status")
async def ftp_status():
    """Get current FTP connection status."""
    svc = get_ftp_service()
    return svc.get_status()


@router.post("/ftp/connect")
async def ftp_connect(req: ConnectRequest):
    """Connect to MVS FTP server."""
    svc = get_ftp_service()
    return svc.connect(
        host=req.host,
        port=req.port,
        user=req.user,
        password=req.password,
    )


@router.post("/ftp/disconnect")
async def ftp_disconnect():
    """Disconnect from FTP server."""
    svc = get_ftp_service()
    return svc.disconnect()


@router.post("/ftp/list")
async def ftp_list(req: ListRequest):
    """List datasets or PDS members."""
    svc = get_ftp_service()

    # If PDS specified, try to list members (will return limitation message)
    if req.pds:
        return svc.list_members(req.pds)

    # Otherwise list datasets with optional prefix filter
    return svc.list_datasets(prefix=req.prefix or "")


@router.post("/ftp/download")
async def ftp_download(req: DownloadRequest):
    """Download a sequential dataset."""
    svc = get_ftp_service()
    return svc.download(dataset=req.dataset, mode=req.mode)


@router.post("/ftp/test-ebcdic")
async def ftp_test_ebcdic(req: EbcdicTestRequest):
    """Test EBCDIC translation by downloading in both modes."""
    svc = get_ftp_service()
    return svc.test_ebcdic(dataset=req.dataset)


@router.post("/ftp/test-all")
async def ftp_test_all(req: TestAllRequest):
    """Run automated FTP test suite."""
    svc = get_ftp_service()
    return svc.run_all_tests(
        host=req.host,
        port=req.port,
        user=req.user,
        password=req.password,
    )


@router.post("/ftp/submit-card")
async def ftp_submit_card(req: SubmitCardRequest):
    """Submit JCL to MVS via card reader (port 3505).

    TK5 FTP server is read-only, so we use the card reader instead.
    Lines are truncated to 80 columns (MVS card image format).
    """
    content = req.content
    if not content.strip():
        return {"success": False, "error": "No content to submit"}

    # Prepare card images (80 columns each)
    lines = content.replace("\r\n", "\n").split("\n")
    card_data = ""
    for line in lines:
        # Truncate/pad to 80 columns
        card_data += (line[:80].ljust(80) + "\n")

    # Send to card reader on port 3505
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect(("localhost", 3505))
        sock.sendall(card_data.encode("ascii", errors="replace"))
        sock.close()
        logger.info(f"Submitted {len(lines)} cards to MVS card reader")
        return {
            "success": True,
            "message": f"Submitted {len(lines)} cards to MVS",
            "cards": len(lines),
        }
    except ConnectionRefusedError:
        return {"success": False, "error": "Card reader not available (port 3505)"}
    except socket.timeout:
        return {"success": False, "error": "Card reader timeout"}
    except Exception as e:
        logger.error(f"Card submit failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/ftp/transfers")
async def ftp_transfers():
    """Get the transfer log."""
    svc = get_ftp_service()
    return {"transfers": svc.get_transfer_log()}
