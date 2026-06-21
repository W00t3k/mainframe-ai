"""Fuzzy matching utilities for typo-tolerant lookups."""

from __future__ import annotations

import re
from typing import Set

try:
    import jellyfish
    _HAS_JELLYFISH = True
except ImportError:
    _HAS_JELLYFISH = False


def normalize(text: str) -> str:
    """Normalize text: lowercase, strip punctuation, collapse spaces."""
    text = text.lower()
    text = re.sub(r"[/\-_]", "", text)  # Remove slashes, hyphens, underscores
    text = re.sub(r"[^a-z0-9\s]", "", text)  # Remove other punctuation
    text = re.sub(r"\s+", " ", text).strip()  # Collapse whitespace
    return text


def _swap_adjacent(word: str) -> Set[str]:
    """Generate variants by swapping adjacent characters."""
    variants = set()
    for i in range(len(word) - 1):
        swapped = word[:i] + word[i + 1] + word[i] + word[i + 2:]
        variants.add(swapped)
    return variants


def _delete_char(word: str) -> Set[str]:
    """Generate variants by deleting one character."""
    return {word[:i] + word[i + 1:] for i in range(len(word))}


def _double_char(word: str) -> Set[str]:
    """Generate variants by doubling one character."""
    return {word[:i] + word[i] + word[i:] for i in range(len(word))}


def generate_typos(term: str, max_distance: int = 2) -> Set[str]:
    """Generate typo variants within Levenshtein distance."""
    term = normalize(term)
    if not term:
        return set()

    variants = {term}  # Include original

    # Distance 1
    variants.update(_swap_adjacent(term))
    variants.update(_delete_char(term))
    variants.update(_double_char(term))

    if max_distance >= 2:
        # Distance 2: apply distance-1 operations to distance-1 results
        distance_1 = set(variants)
        for v in distance_1:
            if len(v) >= 2:
                variants.update(_swap_adjacent(v))
                variants.update(_delete_char(v))

    # Filter out empty strings and very short results
    return {v for v in variants if len(v) >= 2}


def generate_phonetic(term: str) -> Set[str]:
    """Generate phonetic variants using Soundex and Metaphone."""
    term = normalize(term)
    if not term:
        return set()

    variants = {term}

    if _HAS_JELLYFISH:
        try:
            soundex = jellyfish.soundex(term)
            if soundex:
                variants.add(soundex.lower())
        except Exception:
            pass

        try:
            metaphone = jellyfish.metaphone(term)
            if metaphone:
                variants.add(metaphone.lower())
        except Exception:
            pass

    return variants


def generate_abbreviations(
    term: str,
    abbreviations: dict[str, str],
) -> Set[str]:
    """Generate abbreviation variants from config mapping."""
    normalized = normalize(term)
    if not normalized:
        return set()

    variants = {normalized}

    # Add no-spaces variant for multi-word terms
    no_spaces = normalized.replace(" ", "")
    if no_spaces != normalized:
        variants.add(no_spaces)

    # Check if term matches any abbreviation expansion
    for abbrev, expansion in abbreviations.items():
        normalized_expansion = normalize(expansion)
        if normalized == normalized_expansion:
            variants.add(normalize(abbrev))
        elif normalized == normalize(abbrev):
            variants.add(normalized_expansion)

    # Auto-generate acronym from multi-word terms
    words = normalized.split()
    if len(words) > 1:
        acronym = "".join(w[0] for w in words if w)
        if len(acronym) >= 2:
            variants.add(acronym)

    return variants


def generate_all_variants(
    term: str,
    abbreviations: dict[str, str],
    typo_distance: int = 2,
    phonetic_enabled: bool = True,
) -> Set[str]:
    """Generate all fuzzy variants for a term."""
    variants = set()

    # Layer 1: Typo variants
    variants.update(generate_typos(term, max_distance=typo_distance))

    # Layer 2: Normalization variants
    normalized = normalize(term)
    variants.add(normalized)
    variants.add(normalized.replace(" ", ""))
    if "/" in term:
        variants.add(normalize(term.replace("/", " ")))
        variants.add(normalize(term.replace("/", "")))

    # Layer 3: Phonetic variants
    if phonetic_enabled:
        variants.update(generate_phonetic(term))

    # Layer 4: Abbreviation variants
    variants.update(generate_abbreviations(term, abbreviations))

    return {v for v in variants if v}
