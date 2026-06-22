"""Fast O(1) lookups against the pre-computed fuzzy index."""

from __future__ import annotations

import json
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional

from app.services.seed_index.fuzzy import normalize


@dataclass
class LookupResult:
    """Result of a seed index lookup."""
    match: dict[str, Any]
    confidence: float
    canonical_key: str
    assumed_term: Optional[str] = None


class SeedIndexLookup:
    """Fast lookup against a pre-computed fuzzy index."""

    def __init__(self, index: dict[str, Any]):
        self.version = index.get("version", "1.0")
        self.canonical = index.get("canonical", {})
        self.fuzzy_map = index.get("fuzzy_map", {})

    @classmethod
    def from_file(cls, path: Path) -> "SeedIndexLookup":
        """Load index from a JSON file."""
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(data)

    def lookup(self, query: str) -> Optional[dict[str, Any]]:
        """
        Look up a query and return match with confidence.

        Returns dict with:
        - match: the canonical entry
        - confidence: 0.0-1.0 score
        - canonical_key: the normalized key
        - assumed_term: original term if auto-corrected
        """
        normalized = normalize(query)
        if not normalized:
            return None

        # Try exact fuzzy_map lookup first
        canonical_key = self.fuzzy_map.get(normalized)
        if canonical_key and canonical_key in self.canonical:
            return {
                "match": self.canonical[canonical_key],
                "confidence": 1.0,
                "canonical_key": canonical_key,
                "assumed_term": None,
            }

        # Try without spaces
        no_space = normalized.replace(" ", "")
        canonical_key = self.fuzzy_map.get(no_space)
        if canonical_key and canonical_key in self.canonical:
            return {
                "match": self.canonical[canonical_key],
                "confidence": 0.95,
                "canonical_key": canonical_key,
                "assumed_term": None,
            }

        # No exact match found
        return None

    def lookup_with_suggestions(
        self,
        query: str,
        suggestion_limit: int = 3,
        suggestion_cutoff: float = 0.6,
    ) -> dict[str, Any]:
        """
        Look up with fallback to suggestions.

        Returns dict with:
        - match: the canonical entry (if found)
        - confidence: 0.0-1.0 score
        - suggestions: list of close matches (if no high-confidence match)
        """
        result = self.lookup(query)
        if result and result["confidence"] >= 0.9:
            return result

        # Find suggestions via fuzzy scoring
        normalized = normalize(query)
        suggestions = []

        for key, entry in self.canonical.items():
            # Score against canonical key
            score = SequenceMatcher(None, normalized, key).ratio()

            # Also score against title
            title_score = SequenceMatcher(
                None, normalized, normalize(entry.get("title", ""))
            ).ratio()
            score = max(score, title_score)

            # Score against aliases
            for alias in entry.get("aliases", []):
                alias_score = SequenceMatcher(
                    None, normalized, normalize(alias)
                ).ratio()
                score = max(score, alias_score)

            if score >= suggestion_cutoff:
                suggestions.append({
                    "entry": entry,
                    "canonical_key": key,
                    "score": score,
                })

        # Sort by score descending
        suggestions.sort(key=lambda x: -x["score"])
        suggestions = suggestions[:suggestion_limit]

        # If we have a medium-confidence match from exact lookup
        if result and result["confidence"] >= 0.7:
            return {
                "match": result["match"],
                "confidence": result["confidence"],
                "canonical_key": result["canonical_key"],
                "assumed_term": result.get("assumed_term"),
                "suggestions": [],
            }

        # Check if top suggestion is high confidence
        if suggestions and suggestions[0]["score"] >= 0.85:
            top = suggestions[0]
            return {
                "match": top["entry"],
                "confidence": top["score"],
                "canonical_key": top["canonical_key"],
                "assumed_term": top["entry"].get("title"),
                "suggestions": [],
            }

        # Return suggestions only
        return {
            "match": None,
            "confidence": 0.0,
            "canonical_key": None,
            "suggestions": [
                {
                    "title": s["entry"].get("title", ""),
                    "score": s["score"],
                }
                for s in suggestions
            ],
        }

    def get_all_terms(self) -> list[str]:
        """Return all normalized canonical terms."""
        return list(self.canonical.keys())
