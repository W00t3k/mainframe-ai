"""
RAG Context Builder

Shared utility for building RAG context strings used by tutor and recon routes.
"""


async def build_rag_context(query: str, n_results: int = 3) -> str:
    """Query the RAG engine and return a formatted context block.

    Returns an empty string when the RAG engine is unavailable or the
    query yields no results.
    """
    try:
        from tools.rag_engine import get_rag_engine
        engine = get_rag_engine()
        results = await engine.query_simple(query, n_results=n_results)
        if results:
            context = "\n\n" + "=" * 50 + "\n"
            context += "REFERENCE INFORMATION (USE THIS TO ANSWER):\n"
            context += "=" * 50 + "\n"
            for r in results:
                context += f"---\n{r['content']}\n"
            context += "=" * 50 + "\n"
            return context
    except ImportError:
        print("[RAG Context] tools.rag_engine not found")
    except Exception as e:
        print(f"[RAG Context] Error: {e}")
    return ""
