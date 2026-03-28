"""
KICKS Installation API Routes
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.kicks_installer import get_installer

router = APIRouter(tags=["kicks"])


@router.get("/kicks/status")
async def kicks_status():
    """Get KICKS installation status."""
    installer = get_installer()
    return JSONResponse(installer.get_installation_status())


@router.post("/kicks/install")
async def kicks_install():
    """Start KICKS config installation (updates Hercules config)."""
    installer = get_installer()
    result = await installer.start_installation()
    return JSONResponse(result)


@router.post("/kicks/install-full")
async def kicks_install_full():
    """Run full KICKS installation via terminal commands."""
    installer = get_installer()
    result = await installer.run_full_installation()
    return JSONResponse(result)


@router.get("/kicks/commands")
async def kicks_commands():
    """Get Hercules and MVS commands for KICKS installation."""
    installer = get_installer()
    return JSONResponse({
        "hercules_commands": installer.get_hercules_commands(),
        "mvs_commands": installer.get_mvs_commands(),
    })
