"""
RAG API Routes

Endpoints for the Retrieval-Augmented Generation knowledge base.
"""

import os
from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import JSONResponse

from app.config import get_config

router = APIRouter(tags=["rag"])
config = get_config()

# Import RAG engine
try:
    from rag_engine import get_rag_engine, initialize_builtin_knowledge
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    get_rag_engine = None
    initialize_builtin_knowledge = None


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
