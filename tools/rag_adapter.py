#!/usr/bin/env python3
"""Unified RAG adapter - bridges web app to production RAG system.

This module provides the same interface as rag_engine.py but uses
the production ChromaDB + BM25 + cross-encoder reranker RAG system.

The adapter maintains API compatibility so existing web app routes
(rag.py, tutor.py, recon.py) can use either implementation.
"""

import os
import re
import sys
import time
import hashlib
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

# Add production RAG to path
RAG_SRC = Path(__file__).parent.parent / "rag" / "src"
if str(RAG_SRC) not in sys.path:
    sys.path.insert(0, str(RAG_SRC))

# Import production RAG components
try:
    from rag.retrieve import Retriever
    from rag.store import VectorStore
    from rag.ingest import Ingester
    from rag.config import get_settings
    from rag.parse import parse_document
    PRODUCTION_RAG_AVAILABLE = True
except ImportError as e:
    PRODUCTION_RAG_AVAILABLE = False
    print(f"Warning: Production RAG not available: {e}")


@dataclass
class Document:
    """Document info for compatibility with rag_engine.py."""
    id: str
    name: str
    source: str
    doc_type: str
    chunks: int
    added: str


def highlight_query_terms(content: str, query: str, tag: str = "mark") -> str:
    """Highlight query terms in content for display."""
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for",
        "of", "and", "or", "but", "with", "what", "how", "why", "when", "where", "which"
    }
    query_words = [
        w for w in re.findall(r'\b\w+\b', query.lower())
        if w not in stop_words and len(w) > 2
    ]

    if not query_words:
        return content

    highlighted = content
    for word in query_words:
        pattern = re.compile(r'\b(' + re.escape(word) + r')\b', re.IGNORECASE)
        highlighted = pattern.sub(f'<{tag}>\\1</{tag}>', highlighted)

    return highlighted


class UnifiedRAGEngine:
    """Unified RAG engine wrapping the production system.

    Maintains API compatibility with the original rag_engine.py
    while using the full ChromaDB + BM25 + cross-encoder reranker stack.
    """

    def __init__(self):
        if not PRODUCTION_RAG_AVAILABLE:
            raise ImportError("Production RAG system not available")

        self._settings = get_settings()
        self._store = VectorStore()
        self._retriever = Retriever(store=self._store)
        self._ingester = Ingester(store=self._store)

    async def query(
        self,
        question: str,
        n_results: int = 3,
        include_highlights: bool = True,
    ) -> Dict[str, Any]:
        """Query with full hybrid search + reranking.

        Returns same structure as rag_engine.py for compatibility.
        """
        start_time = time.time()

        # Use hybrid retrieval with reranking
        results = self._retriever.retrieve(question, top_k=n_results, use_rerank=True)

        formatted = []
        for r in results:
            score = r.get("rerank_score", r.get("rrf_score", r.get("score", 0)))

            item = {
                "content": r["text"],
                "score": round(float(score), 4),
                "doc_id": r["metadata"].get("doc_id", ""),
                "doc_name": Path(r["metadata"].get("doc_path", "Unknown")).name,
                "doc_type": r["metadata"].get("doc_type", "unknown"),
            }

            if include_highlights:
                item["highlighted_content"] = highlight_query_terms(r["text"], question)

            formatted.append(item)

        stats = self._store.get_stats()

        return {
            "results": formatted,
            "query_time_ms": int((time.time() - start_time) * 1000),
            "total_chunks": stats["total_chunks"],
            "cache_hit": False,  # Production RAG uses ChromaDB's internal caching
        }

    async def query_simple(self, question: str, n_results: int = 3) -> List[Dict]:
        """Simplified query for backward compatibility.

        Returns list of results in old format.
        """
        response = await self.query(question, n_results, include_highlights=False)
        return [
            {
                "content": r["content"],
                "metadata": {
                    "doc_id": r["doc_id"],
                    "doc_name": r["doc_name"],
                },
                "distance": 1 - r["score"],
            }
            for r in response.get("results", [])
        ]

    async def add_pdf(self, pdf_path: str, name: str = "") -> Dict:
        """Add a PDF document to the RAG system."""
        try:
            path = Path(pdf_path)
            if not path.exists():
                return {"success": False, "error": f"File not found: {pdf_path}"}

            chunks_added = self._ingester.ingest_file(path)
            return {
                "success": True,
                "id": str(path),
                "chunks": chunks_added,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def add_text_file(self, file_path: str, name: str = "") -> Dict:
        """Add a text file to the RAG system."""
        try:
            path = Path(file_path)
            if not path.exists():
                return {"success": False, "error": f"File not found: {file_path}"}

            chunks_added = self._ingester.ingest_file(path)
            return {
                "success": True,
                "id": str(path),
                "chunks": chunks_added,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def add_document(
        self,
        name: str,
        content: str,
        source: str = "",
        doc_type: str = "txt",
    ) -> Dict:
        """Add raw text content as a document.

        For raw content, we save to a temp file and ingest it.
        """
        doc_id = hashlib.md5(f"{name}{source}".encode()).hexdigest()[:12]

        # Determine file extension
        ext_map = {
            "txt": ".txt",
            "md": ".md",
            "markdown": ".md",
            "builtin": ".txt",
        }
        ext = ext_map.get(doc_type, ".txt")

        # Save to temp file
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix=ext,
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(content)
            temp_path = f.name

        try:
            chunks = self._ingester.ingest_file(Path(temp_path))
            return {"success": True, "id": doc_id, "chunks": chunks}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    def get_documents(self) -> List[Dict]:
        """Get list of indexed documents."""
        results = self._store._collection.get(include=["metadatas"])

        docs: Dict[str, Dict] = {}
        for meta in results["metadatas"]:
            path = meta.get("doc_path", "unknown")
            if path not in docs:
                docs[path] = {
                    "id": meta.get("doc_id", path),
                    "name": Path(path).name,
                    "source": path,
                    "type": meta.get("doc_type", "unknown"),
                    "chunks": 0,
                    "added": meta.get("ingested_at", ""),
                }
            docs[path]["chunks"] += 1

        return list(docs.values())

    def delete_document(self, doc_id: str) -> Dict:
        """Delete a document by ID or path."""
        # Try matching by doc_path
        results = self._store._collection.get(
            where={"doc_path": doc_id},
            include=["metadatas"],
        )

        if not results["ids"]:
            # Try matching by doc_id field
            results = self._store._collection.get(
                where={"doc_id": doc_id},
                include=["metadatas"],
            )

        if not results["ids"]:
            return {"success": False, "error": "Document not found"}

        # Delete chunks
        self._store._collection.delete(ids=results["ids"])
        self._store._rebuild_bm25()

        return {"success": True, "chunks_deleted": len(results["ids"])}

    def get_stats(self) -> Dict:
        """Get system statistics."""
        store_stats = self._store.get_stats()
        return {
            "documents": store_stats["unique_documents"],
            "chunks": store_stats["total_chunks"],
            "embedding_model": self._settings.embed_model,
            "rerank_model": self._settings.rerank_model,
            "pdf_support": True,
            "chunking_strategy": "semantic",
            "bm25_indexed": store_stats["bm25_indexed"],
            "query_cache": {"size": 0, "max_size": 0, "ttl_seconds": 0},  # Compatibility
        }

    def clear_cache(self):
        """Clear cache (no-op for production RAG)."""
        pass


# Global instance
_unified_engine: Optional[UnifiedRAGEngine] = None


def get_rag_engine() -> UnifiedRAGEngine:
    """Get or create the unified RAG engine.

    This function has the same signature as rag_engine.get_rag_engine().
    """
    global _unified_engine
    if _unified_engine is None:
        _unified_engine = UnifiedRAGEngine()
    return _unified_engine


async def initialize_builtin_knowledge() -> Dict:
    """Initialize builtin knowledge.

    For the unified system, this is mostly a no-op since we use the
    corpus directory with proper ingested documents. However, we can
    add basic built-in knowledge if needed.
    """
    # The unified system relies on the corpus being ingested
    # No built-in knowledge string needed
    return {
        "success": True,
        "message": "Using unified RAG system with corpus directory"
    }


# For backward compatibility, export the same names
__all__ = ['get_rag_engine', 'initialize_builtin_knowledge', 'UnifiedRAGEngine']
