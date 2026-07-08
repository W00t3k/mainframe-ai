"""Data-backed mainframe timeline answers sourced from RAG seed files."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_config


HISTORY_TERMS = (
    "when", "date", "release", "released", "announce", "announced",
    "introduced", "come out", "came out", "coming out",
)


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9/]+", " ", value.lower()).strip()


def _contains_phrase(haystack: str, needle: str) -> bool:
    return bool(needle) and f" {needle} " in f" {haystack} "


def _seed_path() -> Path:
    return Path(get_config().BASE_DIR) / "data" / "rag_seed" / "mainframe_timeline.md"


@lru_cache(maxsize=1)
def _load_timeline_entries() -> list[dict[str, Any]]:
    path = _seed_path()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    entries: list[dict[str, Any]] = []
    sections = re.split(r"(?m)^###\s+", text)
    for section in sections[1:]:
        title_line, _, body = section.partition("\n")
        title = title_line.strip()
        aliases_match = re.search(r"(?m)^Aliases:\s*(.+)$", body)
        answer_match = re.search(r"(?ms)^Answer:\s*(.+?)(?=\n###\s+|\Z)", body)
        if not title or not aliases_match or not answer_match:
            continue

        aliases = [
            alias.strip()
            for alias in aliases_match.group(1).split(";")
            if alias.strip()
        ]
        entries.append({
            "title": title,
            "aliases": aliases,
            "answer": answer_match.group(1).strip(),
        })

    return entries


def answer_timeline_question(question: str) -> str | None:
    """Return a direct answer for known mainframe date/history questions."""
    normalized = _normalize(question)
    if not any(term in normalized for term in HISTORY_TERMS):
        return None

    matches: list[tuple[int, dict[str, Any]]] = []
    for entry in _load_timeline_entries():
        aliases = [_normalize(alias) for alias in entry["aliases"]]
        aliases.append(_normalize(entry["title"]))
        positions = [
            normalized.find(alias)
            for alias in aliases
            if _contains_phrase(normalized, alias)
        ]
        if positions:
            matches.append((min(positions), entry))

    if not matches:
        return None

    return sorted(matches, key=lambda item: item[0])[0][1]["answer"]
