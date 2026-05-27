"""LLM provider routes.

Local-only mode: Ollama is the only supported provider.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["llm"])


@router.get("/llm/status")
async def api_llm_status():
    """Get status of all LLM providers."""
    from app.services.llm_provider import get_llm_service
    service = get_llm_service()
    return JSONResponse(await service.get_status())


@router.post("/llm/provider/switch")
async def api_llm_provider_switch(request: Request):
    """Switch the active LLM provider."""
    data = await request.json()
    provider = data.get("provider", "").strip().lower()
    if provider not in ("ollama", "auto"):
        return JSONResponse({"success": False, "error": f"Unknown provider: {provider}"})
    if provider != "ollama":
        return JSONResponse({"success": False, "error": "Cloud providers are disabled in local-only mode"})
    from app.services.llm_provider import get_llm_service
    service = get_llm_service()
    service.configured_provider = "ollama"
    return JSONResponse({"success": True, "provider": "ollama"})


