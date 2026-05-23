"""
RAG API Routes

Endpoints for the Retrieval-Augmented Generation knowledge base.
Includes Redbooks integration for IBM mainframe documentation.
"""

import os
import asyncio
from pathlib import Path
from fastapi import APIRouter, Request, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse

from app.config import get_config

router = APIRouter(tags=["rag"])
config = get_config()

# Import RAG engine
try:
    from tools.rag_engine import get_rag_engine, initialize_builtin_knowledge
    RAG_AVAILABLE = True
except ImportError:
    try:
        from rag_engine import get_rag_engine, initialize_builtin_knowledge
        RAG_AVAILABLE = True
    except ImportError:
        RAG_AVAILABLE = False
        get_rag_engine = None
        initialize_builtin_knowledge = None

# Import Redbooks RAG
try:
    from tools.redbooks_rag import RedbooksScraper, RedbooksDownloader, RedbooksRAG, MANIFEST_FILE, PDFS_DIR
    REDBOOKS_AVAILABLE = True
except ImportError:
    REDBOOKS_AVAILABLE = False
    RedbooksScraper = None
    RedbooksDownloader = None
    RedbooksRAG = None


@router.get("/stats")
async def api_rag_stats():
    """Get RAG system statistics."""
    if not RAG_AVAILABLE:
        return JSONResponse({"error": "RAG not available", "documents": 0, "chunks": 0})
    engine = get_rag_engine()
    return JSONResponse(engine.get_stats())


@router.get("/documents")
async def api_rag_documents():
    """Get list of indexed documents."""
    if not RAG_AVAILABLE:
        return JSONResponse({"documents": []})
    engine = get_rag_engine()
    return JSONResponse({"documents": engine.get_documents()})


@router.post("/init")
async def api_rag_init():
    """Initialize built-in knowledge."""
    if not RAG_AVAILABLE:
        return JSONResponse({"success": False, "error": "RAG not available"})
    result = await initialize_builtin_knowledge()
    return JSONResponse(result)


@router.post("/upload")
async def api_rag_upload(file: UploadFile = File(...)):
    """Upload and index a document."""
    if not RAG_AVAILABLE:
        return JSONResponse({"success": False, "error": "RAG not available"})

    engine = get_rag_engine()

    # Save file temporarily
    docs_dir = os.path.join(config.RAG_DIR, "documents")
    os.makedirs(docs_dir, exist_ok=True)
    temp_path = os.path.join(docs_dir, file.filename)

    content = await file.read()
    with open(temp_path, "wb") as f:
        f.write(content)

    # Process based on file type
    if file.filename.lower().endswith(".pdf"):
        result = await engine.add_pdf(temp_path, file.filename)
    else:
        result = await engine.add_text_file(temp_path, file.filename)

    return JSONResponse(result)


@router.delete("/document/{doc_id}")
async def api_rag_delete(doc_id: str):
    """Delete a document from RAG."""
    if not RAG_AVAILABLE:
        return JSONResponse({"success": False, "error": "RAG not available"})
    engine = get_rag_engine()
    return JSONResponse(engine.delete_document(doc_id))


@router.post("/query")
async def api_rag_query(request: Request):
    """Query the RAG system with enhanced results."""
    if not RAG_AVAILABLE:
        return JSONResponse({
            "results": [],
            "query_time_ms": 0,
            "total_chunks": 0,
            "cache_hit": False
        })

    data = await request.json()
    query = data.get("query", "")
    n_results = data.get("n_results", 3)
    include_highlights = data.get("include_highlights", True)

    if not query:
        return JSONResponse({
            "results": [],
            "query_time_ms": 0,
            "total_chunks": 0,
            "cache_hit": False
        })

    engine = get_rag_engine()
    response = await engine.query(query, n_results, include_highlights)
    return JSONResponse(response)


# =============================================================================
# Redbooks RAG Endpoints
# =============================================================================

@router.get("/redbooks/status")
async def api_redbooks_status():
    """Get Redbooks RAG status."""
    if not REDBOOKS_AVAILABLE:
        return JSONResponse({"available": False, "error": "Redbooks module not available"})

    manifest_count = 0
    if MANIFEST_FILE.exists():
        with open(MANIFEST_FILE) as f:
            manifest_count = sum(1 for _ in f)

    pdf_count = len(list(PDFS_DIR.glob("*.pdf"))) if PDFS_DIR.exists() else 0

    rag = RedbooksRAG()
    stats = rag.get_stats()

    return JSONResponse({
        "available": True,
        "manifest_entries": manifest_count,
        "pdfs_downloaded": pdf_count,
        "documents_indexed": stats.get("documents", 0),
        "chunks": stats.get("chunks", 0)
    })


@router.post("/redbooks/scrape")
async def api_redbooks_scrape(background_tasks: BackgroundTasks):
    """Scrape Redbooks website for document metadata (runs in background)."""
    if not REDBOOKS_AVAILABLE:
        return JSONResponse({"success": False, "error": "Redbooks module not available"})

    def run_scrape():
        scraper = RedbooksScraper()
        records = scraper.scrape_all()
        scraper.save_manifest()
        return len(records)

    # This is a long-running task, ideally would use a task queue
    # For now, just return immediately with info
    return JSONResponse({
        "success": True,
        "message": "Use CLI: python tools/redbooks_rag.py scrape",
        "note": "Web scraping runs via CLI to avoid timeouts"
    })


@router.post("/redbooks/ingest")
async def api_redbooks_ingest(request: Request):
    """Ingest downloaded PDFs into RAG."""
    if not REDBOOKS_AVAILABLE:
        return JSONResponse({"success": False, "error": "Redbooks module not available"})

    data = await request.json() if request.headers.get("content-type") == "application/json" else {}
    limit = data.get("limit", 5)  # Default to 5 to avoid timeout
    force = data.get("force", False)

    rag = RedbooksRAG()
    result = await rag.ingest_pdfs(limit=limit, force=force)

    return JSONResponse({
        "success": True,
        "ingested": result.get("success", 0),
        "failed": result.get("failed", 0),
        "skipped": result.get("skipped", 0)
    })


@router.post("/redbooks/query")
async def api_redbooks_query(request: Request):
    """Query Redbooks RAG."""
    if not REDBOOKS_AVAILABLE or not RAG_AVAILABLE:
        return JSONResponse({"results": [], "error": "Redbooks RAG not available"})

    data = await request.json()
    question = data.get("query", data.get("question", ""))
    n_results = data.get("n_results", 5)

    if not question:
        return JSONResponse({"results": [], "error": "No query provided"})

    rag = RedbooksRAG()
    result = await rag.query(question, n_results=n_results)

    return JSONResponse(result)


@router.get("/redbooks/manifest")
async def api_redbooks_manifest():
    """Get the scraped manifest of available Redbooks."""
    if not REDBOOKS_AVAILABLE:
        return JSONResponse({"entries": [], "error": "Redbooks module not available"})

    entries = RedbooksScraper.load_manifest()
    return JSONResponse({
        "total": len(entries),
        "downloadable": sum(1 for e in entries if e.get("should_download")),
        "entries": entries[:100]  # Limit response size
    })


@router.post("/redbooks/download")
async def api_redbooks_download(request: Request, background_tasks: BackgroundTasks):
    """Download Redbooks PDFs (runs in background for large downloads)."""
    if not REDBOOKS_AVAILABLE:
        return JSONResponse({"success": False, "error": "Redbooks module not available"})

    data = await request.json() if request.headers.get("content-type") == "application/json" else {}
    limit = min(data.get("limit", 5), 50)  # Cap at 50 to avoid very long downloads
    force = data.get("force", False)

    # Load manifest
    records = RedbooksScraper.load_manifest()
    if not records:
        return JSONResponse({
            "success": False,
            "error": "No manifest found. Run scrape first via CLI: python tools/redbooks_rag.py scrape"
        })

    # For small downloads, run synchronously
    if limit <= 3:
        downloader = RedbooksDownloader()
        result = downloader.download_pdfs(records, limit=limit, force=force)
        return JSONResponse({
            "success": True,
            "downloaded": result.get("success", 0),
            "failed": result.get("failed", 0),
            "skipped": result.get("skipped", 0)
        })

    # For larger downloads, provide CLI instructions
    return JSONResponse({
        "success": True,
        "message": f"For {limit} PDFs, use CLI to avoid timeout",
        "command": f"python tools/redbooks_rag.py download --limit {limit}",
        "then_ingest": f"python tools/redbooks_rag.py ingest --limit {limit}"
    })


def clean_pdf_name(filename: str) -> str:
    """Clean up PDF filename for display."""
    import re
    name = filename.replace(".pdf", "")
    # Remove common prefixes
    name = re.sub(r"^(ation_|classic_\w+_|Applying_|Starter_)", "", name)
    # Replace underscores with spaces
    name = name.replace("_", " ")
    # Remove form numbers like GC26-4056-1
    name = re.sub(r"^[A-Z]{1,3}[0-9]{2}-[0-9]{4}-[0-9]\s*", "", name)
    # Capitalize properly
    name = name.strip()
    return name if name else filename


@router.get("/redbooks/pdfs")
async def api_redbooks_list_pdfs():
    """List downloaded PDF files."""
    if not REDBOOKS_AVAILABLE:
        return JSONResponse({"pdfs": [], "error": "Redbooks module not available"})

    pdfs = []

    # Get Redbooks PDFs
    if PDFS_DIR.exists():
        for pdf in sorted(PDFS_DIR.glob("*.pdf")):
            pdfs.append({
                "name": clean_pdf_name(pdf.name),
                "filename": pdf.name,
                "size_mb": round(pdf.stat().st_size / (1024 * 1024), 2),
                "source": "redbooks"
            })

    # Also include classics if available
    try:
        from tools.redbooks_rag import CLASSICS_DIR
        if CLASSICS_DIR.exists():
            for pdf in sorted(CLASSICS_DIR.glob("*.pdf")):
                pdfs.append({
                    "name": clean_pdf_name(pdf.name),
                    "filename": pdf.name,
                    "size_mb": round(pdf.stat().st_size / (1024 * 1024), 2),
                    "source": "classics"
                })
    except ImportError:
        pass

    return JSONResponse({"pdfs": pdfs, "total": len(pdfs)})
