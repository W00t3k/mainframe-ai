"""
Page Routes

HTML page rendering routes for the web interface.
"""

import os
import platform
import psutil
import httpx

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.config import get_config

router = APIRouter(tags=["pages"])
config = get_config()
templates = Jinja2Templates(directory=config.TEMPLATES_DIR)


@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    """Landing page."""
    return templates.TemplateResponse(request, "index.html")


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """Chat interface page."""
    embed = request.query_params.get("embed") == "1"
    return templates.TemplateResponse(request, "chat.html", {"embed": embed})


@router.get("/connect", response_class=HTMLResponse)
async def connect_page(request: Request):
    """Connection page (alias for chat)."""
    return templates.TemplateResponse(request, "chat.html")


@router.get("/terminal", response_class=HTMLResponse)
async def terminal_page(request: Request):
    """Terminal emulator page."""
    return templates.TemplateResponse(request, "terminal.html")


@router.get("/labs", response_class=HTMLResponse)
async def labs_page(request: Request):
    """Labs page."""
    return templates.TemplateResponse(request, "labs.html")


@router.get("/scanner", response_class=HTMLResponse)
async def scanner_page(request: Request):
    """Scanner page."""
    return templates.TemplateResponse(request, "scanner.html")


@router.get("/screencaps")
async def screencaps_page():
    """Redirect to recon page (captures tab is now merged there)."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/recon", status_code=302)


@router.get("/rag", response_class=HTMLResponse)
async def rag_page(request: Request):
    """RAG knowledge base page."""
    return templates.TemplateResponse(request, "rag.html")


@router.get("/architecture", response_class=HTMLResponse)
async def architecture_page(request: Request):
    """Architecture documentation page."""
    return templates.TemplateResponse(request, "architecture.html")


@router.get("/docs", response_class=HTMLResponse)
async def docs_page(request: Request):
    """Documentation page."""
    return templates.TemplateResponse(request, "docs.html")


@router.get("/deck")
async def deck_download():
    """Redirect to the PowerPoint deck."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/Mainframe-Talk-WIP.pptx", status_code=302)


@router.get("/video", response_class=HTMLResponse)
async def video_page(request: Request):
    """Video demo page."""
    return templates.TemplateResponse(request, "video.html")


@router.get("/video/file")
async def video_file():
    """Serve the IBM-AI demo video file."""
    from fastapi.responses import FileResponse
    video_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "IBM-AI.mp4")
    return FileResponse(video_path, media_type="video/mp4", filename="IBM-AI.mp4")


@router.get("/abstract", response_class=HTMLResponse)
async def abstract_page(request: Request):
    """Conference abstract page."""
    return templates.TemplateResponse(request, "abstract.html")


@router.get("/abstract-models", response_class=HTMLResponse)
async def abstract_models_page(request: Request):
    """Abstract models documentation page."""
    return templates.TemplateResponse(request, "abstract_models.html")


@router.get("/tutor", response_class=HTMLResponse)
async def tutor_page(request: Request):
    """Red Team Tutor page."""
    return templates.TemplateResponse(request, "tutor.html")


@router.get("/recon", response_class=HTMLResponse)
async def recon_page(request: Request):
    """Recon & Assessment dashboard."""
    return templates.TemplateResponse(request, "recon.html")


@router.get("/walkthrough", response_class=HTMLResponse)
async def walkthrough_page(request: Request):
    """Autonomous walkthrough page."""
    return templates.TemplateResponse(request, "walkthrough.html")


@router.get("/slides", response_class=HTMLResponse)
async def slides_page(request: Request):
    """Conference slide deck."""
    return templates.TemplateResponse(request, "slides.html")


@router.get("/graph", response_class=HTMLResponse)
async def graph_page(request: Request):
    """Trust Graph visualization page."""
    return templates.TemplateResponse(request, "graph.html")


@router.get("/presentation", response_class=HTMLResponse)
async def presentation_page(request: Request):
    """Teaching presentation slide deck."""
    return templates.TemplateResponse(request, "presentation.html")


@router.get("/ftp", response_class=HTMLResponse)
async def ftp_page(request: Request):
    """FTP client page."""
    return templates.TemplateResponse(request, "ftp.html")


@router.get("/rakf", response_class=HTMLResponse)
async def rakf_page(request: Request):
    """RAKF security page."""
    return templates.TemplateResponse(request, "rakf.html")


@router.get("/notes", response_class=HTMLResponse)
async def notes_page(request: Request):
    """Notes page."""
    return templates.TemplateResponse(request, "notes.html")


@router.get("/tutorials", response_class=HTMLResponse)
async def tutorials_page(request: Request):
    """Tutorials page."""
    return templates.TemplateResponse(request, "tutorials.html")


@router.get("/uss-editor", response_class=HTMLResponse)
async def uss_editor_page(request: Request):
    """USS editor page."""
    return templates.TemplateResponse(request, "uss_editor.html")


@router.get("/api/sysinfo")
async def sysinfo():
    """System info for sidebar panel."""
    # Ollama status
    ollama_ok = False
    ollama_model = config.OLLAMA_MODEL
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{config.OLLAMA_URL}/api/tags")
            if r.status_code == 200:
                ollama_ok = True
    except Exception:
        pass

    # Mainframe status
    mf_ok = False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get("http://localhost:8038/")
            mf_ok = r.status_code == 200
    except Exception:
        pass

    # RAG status
    rag_status = "empty"
    rag_dir = getattr(config, 'RAG_DIR', None)
    if rag_dir and os.path.isdir(rag_dir):
        rag_files = [f for f in os.listdir(rag_dir) if not f.startswith('.')]
        rag_status = f"{len(rag_files)} docs" if rag_files else "empty"

    # Memory
    try:
        proc = psutil.Process()
        mem_mb = proc.memory_info().rss / (1024 * 1024)
        memory = f"{mem_mb:.0f}MB"
    except Exception:
        memory = "—"

    # Active agents (count background tasks / walkthroughs)
    agents = 0
    try:
        for p in psutil.process_iter(['name', 'cmdline']):
            cmdline = ' '.join(p.info.get('cmdline') or [])
            if 's3270' in cmdline or 'walkthrough' in cmdline:
                agents += 1
    except Exception:
        pass

    return JSONResponse({
        "os": f"{platform.system()} {platform.machine()}",
        "python": platform.python_version(),
        "ollama": "online" if ollama_ok else "offline",
        "model": ollama_model,
        "mainframe": "online" if mf_ok else "offline",
        "port": str(config.PORT),
        "rag": rag_status,
        "agents": str(agents),
        "memory": memory,
    })
