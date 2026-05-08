"""
LLM Provider Routes

Endpoints for managing Ollama LLM.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["llm"])


@router.get("/llm/status")
async def api_llm_status():
    """Get status of LLM provider."""
    from app.services.llm_provider import get_llm_service
    service = get_llm_service()
    return JSONResponse(await service.get_status())


@router.post("/llm/provider/switch")
async def api_llm_provider_switch(request: Request):
    """Switch the active LLM provider (only ollama supported)."""
    data = await request.json()
    provider = data.get("provider", "").strip().lower()
    if provider != "ollama":
        return JSONResponse({"success": False, "error": f"Only 'ollama' provider is supported"})
    return JSONResponse({"success": True, "provider": "ollama"})
