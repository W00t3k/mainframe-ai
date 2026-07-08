"""Fast direct answers sourced from repo-managed RAG seed documents."""

from __future__ import annotations

import hashlib
import json
import re
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_config


STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "define", "do",
    "does", "explain", "for", "from", "how", "i", "in", "is", "it",
    "me", "of", "on", "or", "the", "this", "to", "what", "whats",
    "what's", "when", "where", "why", "with",
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
    return bool(needle) and f" {needle} " in f" {haystack} "


def _seed_dir() -> Path:
    return Path(get_config().BASE_DIR) / "data" / "rag_seed"


def _seed_index_path() -> Path:
    return Path(get_config().BASE_DIR) / "data" / "reference" / "seed_index.json"


def _field(label: str, body: str) -> str:
    labels = (
        "Aliases",
        "Definition",
        "Security impact",
        "Assessment angle",
        "Lab-safe example",
        "Question intent",
        "Answer",
    )
    stop_labels = [candidate for candidate in labels if candidate.lower() != label.lower()]
    stop_pattern = "|".join(re.escape(candidate) for candidate in stop_labels)
    match = re.search(
        rf"(?is)(?:^|\s){re.escape(label)}:\s*(.*?)(?=(?:^|\s)(?:{stop_pattern}):|\Z)",
        body,
    )
    return " ".join(match.group(1).split()) if match else ""


def _seed_paths() -> list[Path]:
    seed_dir = _seed_dir()
    try:
        return sorted(seed_dir.glob("*.md")) + sorted(seed_dir.glob("*.txt"))
    except OSError:
        return []


def build_seed_index() -> dict[str, Any]:
    """Parse seed documents into a compact deterministic index."""
    paths = _seed_paths()
    documents: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []

    base_dir = Path(get_config().BASE_DIR)
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue

        relative_path = str(path.relative_to(base_dir))
        documents.append({
            "source": relative_path,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        })

        sections = re.split(r"(?m)^###\s+", text)
        for section in sections[1:]:
            title_line, _, body = section.partition("\n")
            title = title_line.strip()
            if not title:
                continue

            aliases = [title, title.replace("/", " ")]
            if not title.lower().endswith("s"):
                aliases.append(f"{title}s")
            alias_text = _field("Aliases", body)
            if alias_text:
                aliases.extend(alias.strip() for alias in alias_text.split(";") if alias.strip())

            definition = _field("Definition", body)
            answer = _field("Answer", body)
            entry = {
                "title": title,
                "aliases": sorted(set(alias for alias in aliases if alias)),
                "definition": definition,
                "security_impact": _field("Security impact", body),
                "assessment_angle": _field("Assessment angle", body),
                "lab_safe_example": _field("Lab-safe example", body),
                "question_intent": _field("Question intent", body),
                "answer": answer,
                "kind": "definition" if definition else "answer" if answer else "section",
                "source": relative_path,
            }
            if entry["definition"] or entry["answer"]:
                entries.append(entry)

    return {
        "version": 1,
        "documents": documents,
        "entries": sorted(entries, key=lambda item: (item["title"].lower(), item["source"])),
    }


def write_seed_index(path: Path | None = None) -> dict[str, Any]:
    """Build and write the seed index JSON."""
    output_path = path or _seed_index_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    index = build_seed_index()
    output_path.write_text(json.dumps(index, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return {
        "path": str(output_path),
        "documents": len(index["documents"]),
        "entries": len(index["entries"]),
    }


def _index_is_current(index: dict[str, Any]) -> bool:
    documents = index.get("documents", [])
    expected = {
        str(path.relative_to(Path(get_config().BASE_DIR))): hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        for path in _seed_paths()
        if path.exists()
    }
    actual = {
        str(document.get("source", "")): str(document.get("sha256", ""))
        for document in documents
    }
    return expected == actual


def _load_index_entries() -> list[dict[str, Any]]:
    path = _seed_index_path()
    try:
        index = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if not _index_is_current(index):
        return []

    return [
        entry
        for entry in index.get("entries", [])
        if isinstance(entry, dict) and entry.get("kind") == "definition"
    ]


def _parse_seed_definitions() -> list[dict[str, Any]]:
    index = build_seed_index()
    return [entry for entry in index["entries"] if entry.get("kind") == "definition"]


@lru_cache(maxsize=1)
def _load_seed_definitions() -> list[dict[str, Any]]:
    indexed_entries = _load_index_entries()
    if indexed_entries:
        return indexed_entries

    return _parse_seed_definitions()


def get_seed_index_stats() -> dict[str, Any]:
    """Return stats for the generated seed index."""
    path = _seed_index_path()
    exists = path.exists()
    current = False
    entries = 0
    documents = 0
    if exists:
        try:
            index = json.loads(path.read_text(encoding="utf-8"))
            current = _index_is_current(index)
            entries = len(index.get("entries", []))
            documents = len(index.get("documents", []))
        except (OSError, json.JSONDecodeError):
            pass

    return {
        "path": str(path),
        "exists": exists,
        "current": current,
        "documents": documents,
        "entries": entries,
    }


def format_seed_definition(entry: dict[str, Any], display_title: str | None = None) -> str:
    """Format one seed definition in BigIron.ai answer style."""
    title = display_title or entry.get("title") or "Mainframe concept"
    parts = [f"**{title}**"]
    if entry.get("definition"):
        parts.append(f"- Concept: {entry['definition']}")
    if entry.get("security_impact"):
        parts.append(f"- Security impact: {entry['security_impact']}")
    if entry.get("assessment_angle"):
        parts.append(f"- Assessment angle: {entry['assessment_angle']}")
    if entry.get("lab_safe_example"):
        parts.append(f"- Lab-safe example: {entry['lab_safe_example']}")
    return "\n".join(parts)


def get_seed_definition_by_title(title: str) -> dict[str, Any] | None:
    """Return a seed definition whose title matches exactly after normalization."""
    normalized_title = _normalize(title)
    normalized_space_title = _normalize(title.replace("/", " "))
    for entry in _load_seed_definitions():
        candidates = {_normalize(entry["title"]), _normalize(entry["title"].replace("/", " "))}
        if normalized_title in candidates or normalized_space_title in candidates:
            return entry
    return None


def find_seed_definition_entries(query: str, limit: int = 6) -> list[dict[str, Any]]:
    """Find seed definitions directly from titles or aliases, without embeddings."""
    normalized_query = _normalize(query)
    query_tokens = _tokens(query)
    if not query_tokens:
        return []

    scored: list[tuple[int, int, dict[str, Any]]] = []
    for entry in _load_seed_definitions():
        score = 0
        position = 10_000
        for alias in entry.get("aliases", []):
            normalized_alias = _normalize(alias)
            alias_tokens = _tokens(alias)
            if _contains_phrase(normalized_query, normalized_alias):
                score += 100 + len(alias_tokens) * 5
                position = min(position, normalized_query.find(normalized_alias))
            elif alias_tokens and alias_tokens.issubset(query_tokens):
                score += len(alias_tokens) * 8
                positions = [
                    normalized_query.find(token)
                    for token in alias_tokens
                    if normalized_query.find(token) >= 0
                ]
                if positions:
                    position = min(position, min(positions))

        if score > 0:
            scored.append((score, position, entry))

    return [entry for _, _, entry in sorted(scored, key=lambda item: (-item[0], item[1]))[:limit]]


def get_known_seed_terms() -> list[str]:
    """Return normalized seed titles and aliases."""
    terms: set[str] = set()
    for entry in _load_seed_definitions():
        terms.add(_normalize(entry.get("title", "")))
        for alias in entry.get("aliases", []):
            terms.add(_normalize(alias))
    return sorted(term for term in terms if term)


def find_seed_definition_suggestions(query: str, limit: int = 3, cutoff: float = 0.68) -> list[dict[str, Any]]:
    """Return likely seed definitions for typo-tolerant concept matching."""
    normalized_query = _normalize(query)
    if not normalized_query:
        return []

    scored: list[tuple[float, dict[str, Any]]] = []
    for entry in _load_seed_definitions():
        aliases = [_normalize(entry.get("title", ""))]
        aliases.extend(_normalize(alias) for alias in entry.get("aliases", []))
        best = 0.0
        for alias in aliases:
            if not alias:
                continue
            score = SequenceMatcher(None, normalized_query, alias).ratio()
            if normalized_query.endswith(" a"):
                score = max(score, SequenceMatcher(None, normalized_query[:-2], alias).ratio())
            best = max(best, score)
        if best >= cutoff:
            scored.append((best, entry))

    return [entry for _, entry in sorted(scored, key=lambda item: (-item[0], item[1].get("title", "")))[:limit]]
