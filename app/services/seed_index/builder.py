"""Build the pre-computed fuzzy index from seed documents."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.seed_index.fuzzy import generate_all_variants, normalize


def _parse_field(label: str, body: str) -> str:
    """Extract a labeled field from section body."""
    labels = (
        "Aliases", "Definition", "Security impact", "Assessment angle",
        "Lab-safe example", "Question intent", "Answer",
    )
    stop_labels = [c for c in labels if c.lower() != label.lower()]
    stop_pattern = "|".join(re.escape(c) for c in stop_labels)
    match = re.search(
        rf"(?is)(?:^|\s){re.escape(label)}:\s*(.*?)(?=(?:^|\s)(?:{stop_pattern}):|\Z)",
        body,
    )
    return " ".join(match.group(1).split()) if match else ""


def _parse_seed_file(path: Path) -> list[dict[str, Any]]:
    """Parse a seed markdown file into entries."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    entries = []
    sections = re.split(r"(?m)^###\s+", text)

    for section in sections[1:]:
        title_line, _, body = section.partition("\n")
        title = title_line.strip()
        if not title:
            continue

        # Parse aliases
        aliases = [title, title.replace("/", " ")]
        if not title.lower().endswith("s"):
            aliases.append(f"{title}s")
        alias_text = _parse_field("Aliases", body)
        if alias_text:
            aliases.extend(a.strip() for a in alias_text.split(";") if a.strip())

        definition = _parse_field("Definition", body)
        answer = _parse_field("Answer", body)

        if definition or answer:
            entries.append({
                "title": title,
                "aliases": sorted(set(a for a in aliases if a)),
                "definition": definition,
                "answer": answer,
                "security_impact": _parse_field("Security impact", body),
                "assessment_angle": _parse_field("Assessment angle", body),
                "lab_safe_example": _parse_field("Lab-safe example", body),
                "kind": "definition" if definition else "answer",
                "source": str(path),
            })

    return entries


def _compute_sources_hash(paths: list[Path]) -> str:
    """Compute combined hash of all source files."""
    hasher = hashlib.sha256()
    for path in sorted(paths):
        try:
            content = path.read_bytes()
            hasher.update(path.name.encode())
            hasher.update(content)
        except OSError:
            continue
    return hasher.hexdigest()


def build_fuzzy_index(
    seed_dir: Path,
    abbreviations: dict[str, str],
    typo_distance: int = 2,
    phonetic_enabled: bool = True,
) -> dict[str, Any]:
    """Build the complete fuzzy index from seed documents."""
    # Find all seed files
    paths = sorted(seed_dir.glob("*.md")) + sorted(seed_dir.glob("*.txt"))

    # Also check subdirectories (approved, ingested, external)
    for subdir in ["approved", "ingested", "external"]:
        subpath = seed_dir / subdir
        if subpath.exists():
            paths.extend(sorted(subpath.glob("*.md")))
            paths.extend(sorted(subpath.glob("*.txt")))

    # Parse all entries
    all_entries = []
    for path in paths:
        all_entries.extend(_parse_seed_file(path))

    # Build canonical map
    canonical: dict[str, dict[str, Any]] = {}
    for entry in all_entries:
        key = normalize(entry["title"])
        if key and key not in canonical:
            canonical[key] = {
                "title": entry["title"],
                "definition": entry.get("definition", ""),
                "answer": entry.get("answer", ""),
                "security_impact": entry.get("security_impact", ""),
                "assessment_angle": entry.get("assessment_angle", ""),
                "lab_safe_example": entry.get("lab_safe_example", ""),
                "kind": entry.get("kind", "definition"),
                "source": entry.get("source", ""),
                "aliases": entry.get("aliases", []),
            }

    # Build fuzzy map
    fuzzy_map: dict[str, str] = {}
    for key, entry in canonical.items():
        # Generate variants for the title
        variants = generate_all_variants(
            entry["title"],
            abbreviations,
            typo_distance=typo_distance,
            phonetic_enabled=phonetic_enabled,
        )
        for variant in variants:
            if variant not in fuzzy_map:
                fuzzy_map[variant] = key

        # Also generate variants for all aliases
        for alias in entry.get("aliases", []):
            alias_variants = generate_all_variants(
                alias,
                abbreviations,
                typo_distance=typo_distance,
                phonetic_enabled=phonetic_enabled,
            )
            for variant in alias_variants:
                if variant not in fuzzy_map:
                    fuzzy_map[variant] = key

    return {
        "version": "1.0",
        "built_at": datetime.now(timezone.utc).isoformat(),
        "sources_hash": _compute_sources_hash(paths),
        "canonical": canonical,
        "fuzzy_map": fuzzy_map,
    }


def write_fuzzy_index(
    seed_dir: Path,
    output_path: Path,
    abbreviations: dict[str, str],
    typo_distance: int = 2,
    phonetic_enabled: bool = True,
) -> dict[str, Any]:
    """Build and write the fuzzy index to a JSON file."""
    index = build_fuzzy_index(
        seed_dir,
        abbreviations,
        typo_distance=typo_distance,
        phonetic_enabled=phonetic_enabled,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return {
        "path": str(output_path),
        "canonical_count": len(index["canonical"]),
        "fuzzy_map_count": len(index["fuzzy_map"]),
        "sources_hash": index["sources_hash"],
    }
