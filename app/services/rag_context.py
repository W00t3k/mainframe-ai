"""
RAG Context Builder

Shared utility for building RAG context strings used by tutor and recon routes.
"""


async def build_rag_context(query: str, n_results: int = 2) -> str:
    """Query the RAG engine and return a formatted context block.

    Returns an empty string when the RAG engine is unavailable or the
    query yields no results.
    """
    try:
        from rag_engine import get_rag_engine
        engine = get_rag_engine()
        results = await engine.query_simple(query, n_results=n_results)
        if results:
            context = "\n\n[Relevant Knowledge Base Information]\n"
            for r in results:
                context += f"---\n{r['content']}\n"
            return context
    except Exception:
        pass
    return ""
