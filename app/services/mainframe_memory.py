"""Lightweight local reference memory for mainframe concept Q&A."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_config


STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "does", "for",
    "from", "how", "i", "in", "is", "it", "me", "of", "on", "or", "the",
    "this", "to", "what", "whats", "what's", "when", "where", "why", "with",
}


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9/]+", " ", value.lower()).strip()


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in _normalize(value).split()
        if token not in STOP_WORDS and len(token) > 1
    }


def _contains_phrase(haystack: str, needle: str) -> bool:
    if not needle:
        return False
    return f" {needle} " in f" {haystack} "


@lru_cache(maxsize=1)
def _load_entries() -> list[dict[str, Any]]:
    path = Path(get_config().BASE_DIR) / "data" / "reference" / "mainframe_memory.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def retrieve_mainframe_memory(query: str, limit: int = 3) -> str:
    """Return compact snippets relevant to a short mainframe question."""
    entries = find_mainframe_memory_entries(query, limit)
    return "\n".join(f"- {entry['title']}: {entry['summary']}" for entry in entries)


def find_mainframe_memory_entries(query: str, limit: int = 3) -> list[dict[str, Any]]:
    """Return scored reference entries relevant to a short mainframe question."""
    normalized_query = _normalize(query)
    query_tokens = _tokens(query)
    if not query_tokens:
        return []

    scored: list[tuple[int, int, dict[str, Any]]] = []

    for entry in _load_entries():
        aliases = [_normalize(alias) for alias in entry.get("aliases", [])]
        title = _normalize(entry.get("title", ""))
        title_tokens = _tokens(title)

        score = 0
        position = 10_000
        for alias in aliases:
            alias_tokens = _tokens(alias)
            if _contains_phrase(normalized_query, alias):
                score += 100 + len(alias_tokens) * 5
                position = min(position, normalized_query.find(alias))
            elif alias_tokens and alias_tokens.issubset(query_tokens):
                score += len(alias_tokens) * 8
                positions = [normalized_query.find(token) for token in alias_tokens if normalized_query.find(token) >= 0]
                if positions:
                    position = min(position, min(positions))

        if title and _contains_phrase(normalized_query, title):
            score += 60 + len(title_tokens) * 4
            position = min(position, normalized_query.find(title))
        elif title_tokens and title_tokens.issubset(query_tokens):
            score += len(title_tokens) * 6
            positions = [normalized_query.find(token) for token in title_tokens if normalized_query.find(token) >= 0]
            if positions:
                position = min(position, min(positions))

        if score > 0:
            scored.append((score, position, entry))

    if not scored:
        return []

    return [entry for _, _, entry in sorted(scored, key=lambda item: (-item[0], item[1]))[:limit]]


def get_known_mainframe_terms() -> list[str]:
    """Return normalized aliases and titles known to the local glossary."""
    terms: set[str] = set()
    for entry in _load_entries():
        title = _normalize(entry.get("title", ""))
        if title:
            terms.add(title)
        for alias in entry.get("aliases", []):
            normalized = _normalize(alias)
            if normalized:
                terms.add(normalized)
    return sorted(terms)
