# Seed Index & Data Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fast, typo-tolerant mainframe knowledge lookup system with automated data ingestion and comprehensive eval coverage.

**Architecture:** Pre-computed fuzzy index for O(1) lookups, three-path data pipeline (feedback, local ingest, external fetch), eval system with regression detection, and prioritized backlog from query misses.

**Tech Stack:** Python 3.11+, PyYAML, jellyfish (phonetic), no external DB

---

## File Structure

### New Files to Create

```
app/services/seed_index/
├── __init__.py              # Module exports
├── fuzzy.py                 # Typo/phonetic/abbrev generation
├── builder.py               # Build fuzzy index from sources
├── lookup.py                # O(1) lookups with confidence scoring
└── tracker.py               # Log query misses for backlog

app/services/data_pipeline/
├── __init__.py              # Module exports
├── feedback_processor.py    # Process feedback JSONL → corrections
├── folder_watcher.py        # Watch data/rag_ingest/ for new files
└── external_fetcher.py      # Fetch from configured URLs

app/services/eval_engine/
├── __init__.py              # Module exports
├── runner.py                # Run eval suites against /api/chat
├── reporter.py              # Generate reports, detect regressions
└── generator.py             # Auto-generate evals from feedback

scripts/rag/
├── process_feedback.py      # CLI for feedback processing
├── watch_ingest.py          # CLI for folder watcher
├── fetch_external.py        # CLI for external fetch
└── generate_backlog.py      # CLI for backlog generation

scripts/eval/
└── generate_evals.py        # CLI for eval auto-generation

configs/
├── seed_config.yaml         # Main configuration
├── fetch_sources.yaml       # External URL allowlist
└── abbreviations.yaml       # Manual abbreviation mappings

data/rag_seed/
├── approved/                # Auto-approved corrections (dir)
├── pending/                 # Awaiting review (dir)
├── ingested/                # From local drops (dir)
└── external/                # From URL fetch (dir)

data/rag_ingest/
└── .processed/              # Processed files moved here

data/evals/
└── results/                 # Historical eval results (dir)

tests/
├── test_fuzzy.py
├── test_lookup.py
├── test_builder.py
├── test_tracker.py
├── test_feedback_processor.py
├── test_folder_watcher.py
├── test_external_fetcher.py
├── test_eval_runner.py
├── test_eval_reporter.py
└── test_eval_generator.py
```

### Existing Files to Modify

```
app/services/chat.py                    # Integrate new lookup module
app/services/mainframe_seed.py          # Deprecate in favor of seed_index/
scripts/rag/build_seed_index.py         # Add --fuzzy flag
scripts/eval/run_chat_evals.py          # Add regression detection
```

---

## Task 1: Configuration Files

**Files:**
- Create: `configs/seed_config.yaml`
- Create: `configs/abbreviations.yaml`
- Create: `configs/fetch_sources.yaml`

- [ ] **Step 1: Create seed_config.yaml**

```yaml
# configs/seed_config.yaml
fuzzy:
  typo_distance: 2
  phonetic_enabled: true
  abbreviations_file: "configs/abbreviations.yaml"

feedback:
  auto_approve_threshold: 3

ingest:
  watch_dir: "data/rag_ingest"
  supported_formats: [".md", ".txt", ".json"]

eval:
  baseline_file: "data/evals/baseline.json"
  regression_threshold_pct: 20

backlog:
  high_priority_min: 10
  medium_priority_min: 5
```

- [ ] **Step 2: Create abbreviations.yaml**

```yaml
# configs/abbreviations.yaml
abbreviations:
  mf: mainframe
  jcl: job control language
  tso: time sharing option
  ispf: interactive system productivity facility
  racf: resource access control facility
  cics: customer information control system
  vsam: virtual storage access method
  sdsf: system display and search facility
  jes: job entry subsystem
  smf: system management facilities
  apf: authorized program facility
  vtam: virtual telecommunications access method
  rexx: restructured extended executor
  cobol: common business oriented language
  ipl: initial program load
  lpar: logical partition
  saf: system authorization facility
  ims: information management system
  hlq: high level qualifier
```

- [ ] **Step 3: Create fetch_sources.yaml**

```yaml
# configs/fetch_sources.yaml
sources: []
# Example entries (commented out until user configures):
# - url: "https://www.ibm.com/docs/en/zos-basic-skills"
#   mode: scheduled
#   schedule: "weekly"
#   review: true
```

- [ ] **Step 4: Create data directories**

```bash
mkdir -p data/rag_seed/approved data/rag_seed/pending data/rag_seed/ingested data/rag_seed/external
mkdir -p data/rag_ingest/.processed
mkdir -p data/evals/results
```

- [ ] **Step 5: Commit configuration files**

```bash
git add configs/seed_config.yaml configs/abbreviations.yaml configs/fetch_sources.yaml
git add data/rag_seed/approved/.gitkeep data/rag_seed/pending/.gitkeep data/rag_seed/ingested/.gitkeep data/rag_seed/external/.gitkeep
git add data/rag_ingest/.processed/.gitkeep data/evals/results/.gitkeep
git commit -m "feat: add configuration files for seed index pipeline"
```

---

## Task 2: Fuzzy Generation Module

**Files:**
- Create: `app/services/seed_index/__init__.py`
- Create: `app/services/seed_index/fuzzy.py`
- Test: `tests/test_fuzzy.py`

- [ ] **Step 1: Write failing test for normalize**

```python
# tests/test_fuzzy.py
import pytest

def test_normalize_basic():
    from app.services.seed_index.fuzzy import normalize
    assert normalize("System/360") == "system360"
    assert normalize("RACF") == "racf"
    assert normalize("  What is JCL?  ") == "what is jcl"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fuzzy.py::test_normalize_basic -v`
Expected: FAIL with "ModuleNotFoundError" or "ImportError"

- [ ] **Step 3: Create module init**

```python
# app/services/seed_index/__init__.py
"""Seed index module for fast fuzzy lookups."""

from app.services.seed_index.fuzzy import (
    normalize,
    generate_typos,
    generate_phonetic,
    generate_abbreviations,
    generate_all_variants,
)

__all__ = [
    "normalize",
    "generate_typos",
    "generate_phonetic",
    "generate_abbreviations",
    "generate_all_variants",
]
```

- [ ] **Step 4: Implement normalize function**

```python
# app/services/seed_index/fuzzy.py
"""Fuzzy matching utilities for typo-tolerant lookups."""

from __future__ import annotations

import re
from typing import Set


def normalize(text: str) -> str:
    """Normalize text: lowercase, strip punctuation, collapse spaces."""
    text = text.lower()
    text = re.sub(r"[/\-_]", "", text)  # Remove slashes, hyphens, underscores
    text = re.sub(r"[^a-z0-9\s]", "", text)  # Remove other punctuation
    text = re.sub(r"\s+", " ", text).strip()  # Collapse whitespace
    return text
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_fuzzy.py::test_normalize_basic -v`
Expected: PASS

- [ ] **Step 6: Write failing test for generate_typos**

```python
# tests/test_fuzzy.py (append)

def test_generate_typos_swap():
    from app.services.seed_index.fuzzy import generate_typos
    variants = generate_typos("mainframe", max_distance=1)
    assert "mainfraem" in variants  # adjacent swap
    assert "mainframe" in variants  # original included


def test_generate_typos_missing():
    from app.services.seed_index.fuzzy import generate_typos
    variants = generate_typos("racf", max_distance=1)
    assert "rac" in variants  # missing letter
    assert "acf" in variants  # missing first letter
```

- [ ] **Step 7: Run test to verify it fails**

Run: `pytest tests/test_fuzzy.py::test_generate_typos_swap -v`
Expected: FAIL with "ImportError" or "AttributeError"

- [ ] **Step 8: Implement generate_typos**

```python
# app/services/seed_index/fuzzy.py (append)

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


def _insert_char(word: str) -> Set[str]:
    """Generate variants by inserting one character."""
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    variants = set()
    for i in range(len(word) + 1):
        for c in alphabet:
            variants.add(word[:i] + c + word[i:])
    return variants


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
```

- [ ] **Step 9: Run test to verify it passes**

Run: `pytest tests/test_fuzzy.py::test_generate_typos_swap tests/test_fuzzy.py::test_generate_typos_missing -v`
Expected: PASS

- [ ] **Step 10: Write failing test for generate_phonetic**

```python
# tests/test_fuzzy.py (append)

def test_generate_phonetic():
    from app.services.seed_index.fuzzy import generate_phonetic
    variants = generate_phonetic("cics")
    # Should include phonetic representations
    assert len(variants) >= 1
    assert "cics" in variants
```

- [ ] **Step 11: Run test to verify it fails**

Run: `pytest tests/test_fuzzy.py::test_generate_phonetic -v`
Expected: FAIL

- [ ] **Step 12: Implement generate_phonetic**

```python
# app/services/seed_index/fuzzy.py (append)

try:
    import jellyfish
    _HAS_JELLYFISH = True
except ImportError:
    _HAS_JELLYFISH = False


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
```

- [ ] **Step 13: Run test to verify it passes**

Run: `pytest tests/test_fuzzy.py::test_generate_phonetic -v`
Expected: PASS

- [ ] **Step 14: Write failing test for generate_abbreviations**

```python
# tests/test_fuzzy.py (append)

def test_generate_abbreviations():
    from app.services.seed_index.fuzzy import generate_abbreviations

    abbrevs = {"mf": "mainframe", "jcl": "job control language"}
    variants = generate_abbreviations("mainframe", abbrevs)
    assert "mf" in variants
    assert "mainframe" in variants


def test_generate_abbreviations_multiword():
    from app.services.seed_index.fuzzy import generate_abbreviations

    abbrevs = {"jcl": "job control language"}
    variants = generate_abbreviations("job control language", abbrevs)
    assert "jcl" in variants
    assert "jobcontrollanguage" in variants  # normalized
```

- [ ] **Step 15: Run test to verify it fails**

Run: `pytest tests/test_fuzzy.py::test_generate_abbreviations -v`
Expected: FAIL

- [ ] **Step 16: Implement generate_abbreviations**

```python
# app/services/seed_index/fuzzy.py (append)

def generate_abbreviations(
    term: str,
    abbreviations: dict[str, str],
) -> Set[str]:
    """Generate abbreviation variants from config mapping."""
    normalized = normalize(term)
    if not normalized:
        return set()

    variants = {normalized}

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
```

- [ ] **Step 17: Run test to verify it passes**

Run: `pytest tests/test_fuzzy.py::test_generate_abbreviations tests/test_fuzzy.py::test_generate_abbreviations_multiword -v`
Expected: PASS

- [ ] **Step 18: Write failing test for generate_all_variants**

```python
# tests/test_fuzzy.py (append)

def test_generate_all_variants():
    from app.services.seed_index.fuzzy import generate_all_variants

    abbrevs = {"mf": "mainframe"}
    variants = generate_all_variants("mainframe", abbrevs, typo_distance=1)

    assert "mainframe" in variants
    assert "mf" in variants
    assert "mainfraem" in variants  # typo
```

- [ ] **Step 19: Run test to verify it fails**

Run: `pytest tests/test_fuzzy.py::test_generate_all_variants -v`
Expected: FAIL

- [ ] **Step 20: Implement generate_all_variants**

```python
# app/services/seed_index/fuzzy.py (append)

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

    # Layer 2: Normalization variants (already in typos via normalize)
    normalized = normalize(term)
    variants.add(normalized)

    # Also add with/without spaces for compound terms
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
```

- [ ] **Step 21: Run test to verify it passes**

Run: `pytest tests/test_fuzzy.py::test_generate_all_variants -v`
Expected: PASS

- [ ] **Step 22: Run all fuzzy tests**

Run: `pytest tests/test_fuzzy.py -v`
Expected: All PASS

- [ ] **Step 23: Commit fuzzy module**

```bash
git add app/services/seed_index/__init__.py app/services/seed_index/fuzzy.py tests/test_fuzzy.py
git commit -m "feat: add fuzzy generation module with typo/phonetic/abbreviation support"
```

---

## Task 3: Index Builder Module

**Files:**
- Create: `app/services/seed_index/builder.py`
- Modify: `app/services/seed_index/__init__.py`
- Test: `tests/test_builder.py`

- [ ] **Step 1: Write failing test for build_fuzzy_index**

```python
# tests/test_builder.py
import pytest
import json
from pathlib import Path
import tempfile


def test_build_fuzzy_index_structure():
    from app.services.seed_index.builder import build_fuzzy_index

    with tempfile.TemporaryDirectory() as tmpdir:
        seed_dir = Path(tmpdir) / "rag_seed"
        seed_dir.mkdir()

        # Create minimal seed file
        (seed_dir / "test.md").write_text("""
### TestTerm
Definition: A test definition for unit testing.
""")

        index = build_fuzzy_index(seed_dir, abbreviations={})

        assert "version" in index
        assert "built_at" in index
        assert "sources_hash" in index
        assert "canonical" in index
        assert "fuzzy_map" in index
        assert "testterm" in index["canonical"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_builder.py::test_build_fuzzy_index_structure -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Implement build_fuzzy_index**

```python
# app/services/seed_index/builder.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_builder.py::test_build_fuzzy_index_structure -v`
Expected: PASS

- [ ] **Step 5: Write test for fuzzy map generation**

```python
# tests/test_builder.py (append)

def test_build_fuzzy_index_fuzzy_map():
    from app.services.seed_index.builder import build_fuzzy_index

    with tempfile.TemporaryDirectory() as tmpdir:
        seed_dir = Path(tmpdir) / "rag_seed"
        seed_dir.mkdir()

        (seed_dir / "test.md").write_text("""
### Mainframe
Definition: A large enterprise computer.
""")

        abbrevs = {"mf": "mainframe"}
        index = build_fuzzy_index(seed_dir, abbrevs)

        fuzzy_map = index["fuzzy_map"]
        assert fuzzy_map.get("mainframe") == "mainframe"
        assert fuzzy_map.get("mf") == "mainframe"
        assert fuzzy_map.get("mainfraem") == "mainframe"  # typo
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_builder.py::test_build_fuzzy_index_fuzzy_map -v`
Expected: PASS

- [ ] **Step 7: Update module init**

```python
# app/services/seed_index/__init__.py
"""Seed index module for fast fuzzy lookups."""

from app.services.seed_index.fuzzy import (
    normalize,
    generate_typos,
    generate_phonetic,
    generate_abbreviations,
    generate_all_variants,
)
from app.services.seed_index.builder import (
    build_fuzzy_index,
    write_fuzzy_index,
)

__all__ = [
    "normalize",
    "generate_typos",
    "generate_phonetic",
    "generate_abbreviations",
    "generate_all_variants",
    "build_fuzzy_index",
    "write_fuzzy_index",
]
```

- [ ] **Step 8: Run all builder tests**

Run: `pytest tests/test_builder.py -v`
Expected: All PASS

- [ ] **Step 9: Commit builder module**

```bash
git add app/services/seed_index/builder.py app/services/seed_index/__init__.py tests/test_builder.py
git commit -m "feat: add fuzzy index builder with multi-layer variant generation"
```

---

## Task 4: Lookup Module

**Files:**
- Create: `app/services/seed_index/lookup.py`
- Modify: `app/services/seed_index/__init__.py`
- Test: `tests/test_lookup.py`

- [ ] **Step 1: Write failing test for lookup**

```python
# tests/test_lookup.py
import pytest
import json
from pathlib import Path
import tempfile


def test_lookup_exact_match():
    from app.services.seed_index.lookup import SeedIndexLookup

    index = {
        "version": "1.0",
        "canonical": {
            "mainframe": {
                "title": "Mainframe",
                "definition": "A large computer",
                "kind": "definition",
            }
        },
        "fuzzy_map": {
            "mainframe": "mainframe",
            "mf": "mainframe",
        }
    }

    lookup = SeedIndexLookup(index)
    result = lookup.lookup("mainframe")

    assert result is not None
    assert result["match"]["title"] == "Mainframe"
    assert result["confidence"] > 0.9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_lookup.py::test_lookup_exact_match -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Implement SeedIndexLookup class**

```python
# app/services/seed_index/lookup.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_lookup.py::test_lookup_exact_match -v`
Expected: PASS

- [ ] **Step 5: Write test for suggestions**

```python
# tests/test_lookup.py (append)

def test_lookup_with_suggestions():
    from app.services.seed_index.lookup import SeedIndexLookup

    index = {
        "version": "1.0",
        "canonical": {
            "mainframe": {"title": "Mainframe", "definition": "A large computer"},
            "racf": {"title": "RACF", "definition": "Security manager"},
            "vsam": {"title": "VSAM", "definition": "Access method"},
        },
        "fuzzy_map": {
            "mainframe": "mainframe",
            "racf": "racf",
            "vsam": "vsam",
        }
    }

    lookup = SeedIndexLookup(index)
    result = lookup.lookup_with_suggestions("rvam")  # typo for VSAM

    # Should get suggestions since no exact match
    assert "suggestions" in result
    assert len(result["suggestions"]) > 0
    # VSAM should be in suggestions
    titles = [s["title"] for s in result["suggestions"]]
    assert "VSAM" in titles


def test_lookup_abbreviation():
    from app.services.seed_index.lookup import SeedIndexLookup

    index = {
        "version": "1.0",
        "canonical": {
            "mainframe": {"title": "Mainframe", "definition": "A large computer"},
        },
        "fuzzy_map": {
            "mainframe": "mainframe",
            "mf": "mainframe",
        }
    }

    lookup = SeedIndexLookup(index)
    result = lookup.lookup("mf")

    assert result is not None
    assert result["match"]["title"] == "Mainframe"
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_lookup.py -v`
Expected: All PASS

- [ ] **Step 7: Update module init**

```python
# app/services/seed_index/__init__.py
"""Seed index module for fast fuzzy lookups."""

from app.services.seed_index.fuzzy import (
    normalize,
    generate_typos,
    generate_phonetic,
    generate_abbreviations,
    generate_all_variants,
)
from app.services.seed_index.builder import (
    build_fuzzy_index,
    write_fuzzy_index,
)
from app.services.seed_index.lookup import (
    SeedIndexLookup,
    LookupResult,
)

__all__ = [
    "normalize",
    "generate_typos",
    "generate_phonetic",
    "generate_abbreviations",
    "generate_all_variants",
    "build_fuzzy_index",
    "write_fuzzy_index",
    "SeedIndexLookup",
    "LookupResult",
]
```

- [ ] **Step 8: Commit lookup module**

```bash
git add app/services/seed_index/lookup.py app/services/seed_index/__init__.py tests/test_lookup.py
git commit -m "feat: add O(1) lookup with confidence scoring and suggestions"
```

---

## Task 5: Query Miss Tracker

**Files:**
- Create: `app/services/seed_index/tracker.py`
- Modify: `app/services/seed_index/__init__.py`
- Test: `tests/test_tracker.py`

- [ ] **Step 1: Write failing test for log_miss**

```python
# tests/test_tracker.py
import pytest
import json
from pathlib import Path
import tempfile


def test_log_miss_creates_file():
    from app.services.seed_index.tracker import QueryMissTracker

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "query_misses.jsonl"
        tracker = QueryMissTracker(log_path)

        tracker.log_miss("what is xyz", "unknown_guard", ["xyx", "xyz1"])

        assert log_path.exists()
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 1

        entry = json.loads(lines[0])
        assert entry["query"] == "what is xyz"
        assert entry["mode"] == "unknown_guard"
        assert "ts" in entry
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tracker.py::test_log_miss_creates_file -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Implement QueryMissTracker**

```python
# app/services/seed_index/tracker.py
"""Track query misses for backlog prioritization."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class QueryMissTracker:
    """Log query misses for backlog generation."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_miss(
        self,
        query: str,
        mode: str,
        suggestions: list[str] | None = None,
    ) -> None:
        """Append a query miss to the log."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "mode": mode,
            "suggestions": suggestions or [],
        }

        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_misses(self) -> list[dict[str, Any]]:
        """Read all logged misses."""
        if not self.log_path.exists():
            return []

        misses = []
        for line in self.log_path.read_text(encoding="utf-8").strip().split("\n"):
            if line:
                try:
                    misses.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return misses

    def clear(self) -> None:
        """Clear the miss log."""
        if self.log_path.exists():
            self.log_path.unlink()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tracker.py::test_log_miss_creates_file -v`
Expected: PASS

- [ ] **Step 5: Write test for get_misses**

```python
# tests/test_tracker.py (append)

def test_get_misses():
    from app.services.seed_index.tracker import QueryMissTracker

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "query_misses.jsonl"
        tracker = QueryMissTracker(log_path)

        tracker.log_miss("query1", "rag_llm", [])
        tracker.log_miss("query2", "unknown_guard", ["suggestion"])

        misses = tracker.get_misses()
        assert len(misses) == 2
        assert misses[0]["query"] == "query1"
        assert misses[1]["query"] == "query2"
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_tracker.py -v`
Expected: All PASS

- [ ] **Step 7: Update module init**

```python
# app/services/seed_index/__init__.py
"""Seed index module for fast fuzzy lookups."""

from app.services.seed_index.fuzzy import (
    normalize,
    generate_typos,
    generate_phonetic,
    generate_abbreviations,
    generate_all_variants,
)
from app.services.seed_index.builder import (
    build_fuzzy_index,
    write_fuzzy_index,
)
from app.services.seed_index.lookup import (
    SeedIndexLookup,
    LookupResult,
)
from app.services.seed_index.tracker import (
    QueryMissTracker,
)

__all__ = [
    "normalize",
    "generate_typos",
    "generate_phonetic",
    "generate_abbreviations",
    "generate_all_variants",
    "build_fuzzy_index",
    "write_fuzzy_index",
    "SeedIndexLookup",
    "LookupResult",
    "QueryMissTracker",
]
```

- [ ] **Step 8: Commit tracker module**

```bash
git add app/services/seed_index/tracker.py app/services/seed_index/__init__.py tests/test_tracker.py
git commit -m "feat: add query miss tracker for backlog prioritization"
```

---

## Task 6: Backlog Generator Script

**Files:**
- Create: `scripts/rag/generate_backlog.py`

- [ ] **Step 1: Implement generate_backlog.py**

```python
#!/usr/bin/env python3
"""Generate prioritized backlog from query misses."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.seed_index.tracker import QueryMissTracker
from app.services.seed_index.fuzzy import normalize


def generate_backlog(
    misses: list[dict],
    high_min: int = 10,
    med_min: int = 5,
) -> str:
    """Generate markdown backlog from misses."""
    # Normalize and count queries
    counter: Counter[str] = Counter()
    samples: dict[str, list[str]] = {}

    for miss in misses:
        query = miss.get("query", "")
        normalized = normalize(query)
        if not normalized:
            continue

        counter[normalized] += 1
        if normalized not in samples:
            samples[normalized] = []
        if len(samples[normalized]) < 3 and query not in samples[normalized]:
            samples[normalized].append(query)

    # Build markdown
    lines = [
        "# Seed Content Backlog",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d')}",
        "",
    ]

    # High priority
    high = [(term, count) for term, count in counter.items() if count >= high_min]
    high.sort(key=lambda x: -x[1])

    lines.append(f"## High Priority ({high_min}+ queries)")
    lines.append("")
    if high:
        lines.append("| Term | Query Count | Sample Queries |")
        lines.append("|------|-------------|----------------|")
        for term, count in high:
            sample_str = ", ".join(f'"{s}"' for s in samples.get(term, [])[:2])
            lines.append(f"| {term} | {count} | {sample_str} |")
    else:
        lines.append("No high-priority terms.")
    lines.append("")

    # Medium priority
    med = [(term, count) for term, count in counter.items() if med_min <= count < high_min]
    med.sort(key=lambda x: -x[1])

    lines.append(f"## Medium Priority ({med_min}-{high_min-1} queries)")
    lines.append("")
    if med:
        lines.append("| Term | Query Count | Sample Queries |")
        lines.append("|------|-------------|----------------|")
        for term, count in med:
            sample_str = ", ".join(f'"{s}"' for s in samples.get(term, [])[:2])
            lines.append(f"| {term} | {count} | {sample_str} |")
    else:
        lines.append("No medium-priority terms.")
    lines.append("")

    # Low priority
    low = [(term, count) for term, count in counter.items() if 2 <= count < med_min]
    low.sort(key=lambda x: -x[1])

    lines.append(f"## Low Priority (2-{med_min-1} queries)")
    lines.append("")
    if low:
        lines.append("| Term | Query Count | Sample Queries |")
        lines.append("|------|-------------|----------------|")
        for term, count in low[:20]:  # Limit to 20
            sample_str = ", ".join(f'"{s}"' for s in samples.get(term, [])[:2])
            lines.append(f"| {term} | {count} | {sample_str} |")
    else:
        lines.append("No low-priority terms.")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate backlog from query misses.")
    parser.add_argument(
        "--input",
        default="data/reference/query_misses.jsonl",
        help="Query misses log file.",
    )
    parser.add_argument(
        "--output",
        default="data/rag_seed/TODO.md",
        help="Output backlog file.",
    )
    parser.add_argument("--high-min", type=int, default=10)
    parser.add_argument("--med-min", type=int, default=5)
    args = parser.parse_args()

    log_path = ROOT / args.input
    if not log_path.exists():
        print(f"No query misses log found at {log_path}")
        return 0

    tracker = QueryMissTracker(log_path)
    misses = tracker.get_misses()

    if not misses:
        print("No query misses to process.")
        return 0

    backlog = generate_backlog(misses, args.high_min, args.med_min)

    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(backlog, encoding="utf-8")

    print(f"Backlog written to {output_path}")
    print(f"Processed {len(misses)} query misses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Make script executable and commit**

```bash
chmod +x scripts/rag/generate_backlog.py
git add scripts/rag/generate_backlog.py
git commit -m "feat: add backlog generator script from query misses"
```

---

## Task 7: Update Build Script with Fuzzy Flag

**Files:**
- Modify: `scripts/rag/build_seed_index.py`

- [ ] **Step 1: Read current build script**

The current script at `scripts/rag/build_seed_index.py` uses the old `mainframe_seed` module.

- [ ] **Step 2: Update build script**

```python
#!/usr/bin/env python3
"""Build the fast direct-answer seed index from data/rag_seed files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.mainframe_seed import get_seed_index_stats, write_seed_index  # noqa: E402


def load_abbreviations(config_path: Path) -> dict[str, str]:
    """Load abbreviations from YAML config."""
    if not config_path.exists():
        return {}
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        return data.get("abbreviations", {})
    except Exception:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build data/reference/seed_index.json from RAG seed docs.")
    parser.add_argument(
        "--output",
        default="data/reference/seed_index.json",
        help="Output JSON index path.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check whether the existing index is present and current.",
    )
    parser.add_argument(
        "--fuzzy",
        action="store_true",
        help="Build the fuzzy index (seed_index_fuzzy.json) with typo tolerance.",
    )
    parser.add_argument(
        "--config",
        default="configs/seed_config.yaml",
        help="Path to seed config YAML.",
    )
    args = parser.parse_args()

    if args.fuzzy:
        # Build fuzzy index
        from app.services.seed_index.builder import write_fuzzy_index

        config_path = ROOT / args.config
        abbrev_path = ROOT / "configs" / "abbreviations.yaml"
        abbreviations = load_abbreviations(abbrev_path)

        seed_dir = ROOT / "data" / "rag_seed"
        output_path = ROOT / "data" / "reference" / "seed_index_fuzzy.json"

        result = write_fuzzy_index(seed_dir, output_path, abbreviations)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if args.check:
        stats = get_seed_index_stats()
        print(json.dumps(stats, indent=2, sort_keys=True))
        return 0 if stats["exists"] and stats["current"] else 1

    result = write_seed_index(ROOT / args.output)
    stats = get_seed_index_stats()
    print(json.dumps({**result, "current": stats["current"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Commit updated build script**

```bash
git add scripts/rag/build_seed_index.py
git commit -m "feat: add --fuzzy flag to build script for typo-tolerant index"
```

---

## Task 8: Data Pipeline - Feedback Processor

**Files:**
- Create: `app/services/data_pipeline/__init__.py`
- Create: `app/services/data_pipeline/feedback_processor.py`
- Test: `tests/test_feedback_processor.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_feedback_processor.py
import pytest
import json
from pathlib import Path
import tempfile


def test_process_feedback_extracts_corrections():
    from app.services.data_pipeline.feedback_processor import FeedbackProcessor

    with tempfile.TemporaryDirectory() as tmpdir:
        feedback_path = Path(tmpdir) / "feedback.jsonl"
        output_dir = Path(tmpdir) / "output"

        # Write test feedback
        feedback_data = [
            {"question": "what is xyz", "rating": "wrong", "correction": "XYZ is a test term"},
            {"question": "what is abc", "rating": "right"},
            {"question": "what is xyz", "rating": "wrong", "correction": "XYZ is a test term"},
            {"question": "what is xyz", "rating": "wrong", "correction": "XYZ is a test term"},
        ]
        with feedback_path.open("w") as f:
            for item in feedback_data:
                f.write(json.dumps(item) + "\n")

        processor = FeedbackProcessor(feedback_path, output_dir, threshold=3)
        result = processor.process()

        assert result["corrections_found"] == 3
        assert result["auto_approved"] == 1  # xyz meets threshold
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_feedback_processor.py::test_process_feedback_extracts_corrections -v`
Expected: FAIL

- [ ] **Step 3: Create module init**

```python
# app/services/data_pipeline/__init__.py
"""Data pipeline module for automated ingestion."""

from app.services.data_pipeline.feedback_processor import FeedbackProcessor

__all__ = [
    "FeedbackProcessor",
]
```

- [ ] **Step 4: Implement FeedbackProcessor**

```python
# app/services/data_pipeline/feedback_processor.py
"""Process feedback JSONL to extract corrections."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.seed_index.fuzzy import normalize


class FeedbackProcessor:
    """Process user feedback to extract and approve corrections."""

    def __init__(
        self,
        feedback_path: Path,
        output_dir: Path,
        threshold: int = 3,
    ):
        self.feedback_path = feedback_path
        self.output_dir = output_dir
        self.threshold = threshold
        self.approved_dir = output_dir / "approved"
        self.pending_dir = output_dir / "pending"

    def _load_feedback(self) -> list[dict[str, Any]]:
        """Load feedback entries from JSONL."""
        if not self.feedback_path.exists():
            return []

        entries = []
        for line in self.feedback_path.read_text(encoding="utf-8").strip().split("\n"):
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries

    def process(self) -> dict[str, Any]:
        """Process feedback and generate correction files."""
        entries = self._load_feedback()

        # Extract corrections (rating=wrong with correction text)
        corrections: list[dict[str, str]] = []
        for entry in entries:
            if entry.get("rating") == "wrong" and entry.get("correction"):
                corrections.append({
                    "question": entry.get("question", ""),
                    "correction": entry["correction"],
                })

        if not corrections:
            return {
                "corrections_found": 0,
                "auto_approved": 0,
                "pending": 0,
            }

        # Group by normalized question + correction
        grouped: dict[str, list[dict]] = {}
        for c in corrections:
            key = normalize(c["question"]) + "||" + normalize(c["correction"])
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(c)

        # Separate into auto-approved and pending
        auto_approved = []
        pending = []

        for key, items in grouped.items():
            if len(items) >= self.threshold:
                auto_approved.append(items[0])
            else:
                pending.append(items[0])

        # Write approved corrections
        if auto_approved:
            self.approved_dir.mkdir(parents=True, exist_ok=True)
            approved_file = self.approved_dir / "corrections.md"
            lines = self._format_corrections(auto_approved, "Auto-Approved")
            self._append_to_file(approved_file, lines)

        # Write pending corrections
        if pending:
            self.pending_dir.mkdir(parents=True, exist_ok=True)
            pending_file = self.pending_dir / "corrections.md"
            lines = self._format_corrections(pending, "Pending Review")
            self._append_to_file(pending_file, lines)

        return {
            "corrections_found": len(corrections),
            "auto_approved": len(auto_approved),
            "pending": len(pending),
        }

    def _format_corrections(
        self,
        corrections: list[dict[str, str]],
        section_title: str,
    ) -> str:
        """Format corrections as markdown."""
        lines = [
            f"# {section_title} Corrections",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
        ]

        for c in corrections:
            question = c.get("question", "Unknown")
            correction = c.get("correction", "")
            lines.append(f"### {question}")
            lines.append(f"Definition: {correction}")
            lines.append("")

        return "\n".join(lines)

    def _append_to_file(self, path: Path, content: str) -> None:
        """Append content to file, creating if needed."""
        mode = "a" if path.exists() else "w"
        with path.open(mode, encoding="utf-8") as f:
            f.write(content + "\n")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_feedback_processor.py::test_process_feedback_extracts_corrections -v`
Expected: PASS

- [ ] **Step 6: Commit feedback processor**

```bash
git add app/services/data_pipeline/__init__.py app/services/data_pipeline/feedback_processor.py tests/test_feedback_processor.py
git commit -m "feat: add feedback processor for auto-incorporating corrections"
```

---

## Task 9: Data Pipeline - Folder Watcher

**Files:**
- Create: `app/services/data_pipeline/folder_watcher.py`
- Modify: `app/services/data_pipeline/__init__.py`
- Test: `tests/test_folder_watcher.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_folder_watcher.py
import pytest
from pathlib import Path
import tempfile


def test_folder_watcher_processes_markdown():
    from app.services.data_pipeline.folder_watcher import FolderWatcher

    with tempfile.TemporaryDirectory() as tmpdir:
        ingest_dir = Path(tmpdir) / "ingest"
        output_dir = Path(tmpdir) / "output"
        processed_dir = ingest_dir / ".processed"

        ingest_dir.mkdir()

        # Create a test file
        test_file = ingest_dir / "test.md"
        test_file.write_text("""
### NewTerm
Definition: A new test definition.
""")

        watcher = FolderWatcher(ingest_dir, output_dir)
        result = watcher.process_pending()

        assert result["files_processed"] == 1
        assert not test_file.exists()  # Moved to processed
        assert (processed_dir / "test.md").exists()
        assert (output_dir / "test.md").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_folder_watcher.py::test_folder_watcher_processes_markdown -v`
Expected: FAIL

- [ ] **Step 3: Implement FolderWatcher**

```python
# app/services/data_pipeline/folder_watcher.py
"""Watch folder for new files and process them."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


class FolderWatcher:
    """Watch a directory for new files and move them to seed dirs."""

    SUPPORTED_FORMATS = {".md", ".txt", ".json"}

    def __init__(
        self,
        watch_dir: Path,
        output_dir: Path,
    ):
        self.watch_dir = watch_dir
        self.output_dir = output_dir
        self.processed_dir = watch_dir / ".processed"

    def _get_pending_files(self) -> list[Path]:
        """Get files pending processing."""
        if not self.watch_dir.exists():
            return []

        pending = []
        for path in self.watch_dir.iterdir():
            if path.is_file() and path.suffix.lower() in self.SUPPORTED_FORMATS:
                pending.append(path)

        return sorted(pending)

    def process_file(self, path: Path) -> dict[str, Any]:
        """Process a single file."""
        if path.suffix.lower() == ".json":
            return self._process_json(path)
        else:
            return self._process_text(path)

    def _process_text(self, path: Path) -> dict[str, Any]:
        """Process markdown or text file."""
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            return {"error": str(e)}

        # Copy to output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / path.name
        output_path.write_text(content, encoding="utf-8")

        # Move original to processed
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(self.processed_dir / path.name))

        return {"processed": str(path.name), "output": str(output_path)}

    def _process_json(self, path: Path) -> dict[str, Any]:
        """Process JSON file with term definitions."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            return {"error": str(e)}

        # Convert JSON to markdown
        lines = [f"# Ingested from {path.name}", f"Date: {datetime.now().isoformat()}", ""]

        if isinstance(data, list):
            for item in data:
                term = item.get("term", "Unknown")
                definition = item.get("definition", "")
                aliases = item.get("aliases", [])
                lines.append(f"### {term}")
                if aliases:
                    lines.append(f"Aliases: {'; '.join(aliases)}")
                lines.append(f"Definition: {definition}")
                lines.append("")
        elif isinstance(data, dict):
            term = data.get("term", "Unknown")
            definition = data.get("definition", "")
            lines.append(f"### {term}")
            lines.append(f"Definition: {definition}")
            lines.append("")

        # Write markdown output
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_name = path.stem + ".md"
        output_path = self.output_dir / output_name
        output_path.write_text("\n".join(lines), encoding="utf-8")

        # Move original to processed
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(self.processed_dir / path.name))

        return {"processed": str(path.name), "output": str(output_path)}

    def process_pending(self) -> dict[str, Any]:
        """Process all pending files."""
        files = self._get_pending_files()
        results = []

        for path in files:
            result = self.process_file(path)
            results.append(result)

        return {
            "files_processed": len(results),
            "results": results,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_folder_watcher.py::test_folder_watcher_processes_markdown -v`
Expected: PASS

- [ ] **Step 5: Update module init**

```python
# app/services/data_pipeline/__init__.py
"""Data pipeline module for automated ingestion."""

from app.services.data_pipeline.feedback_processor import FeedbackProcessor
from app.services.data_pipeline.folder_watcher import FolderWatcher

__all__ = [
    "FeedbackProcessor",
    "FolderWatcher",
]
```

- [ ] **Step 6: Commit folder watcher**

```bash
git add app/services/data_pipeline/folder_watcher.py app/services/data_pipeline/__init__.py tests/test_folder_watcher.py
git commit -m "feat: add folder watcher for local file ingestion"
```

---

## Task 10: Data Pipeline - External Fetcher

**Files:**
- Create: `app/services/data_pipeline/external_fetcher.py`
- Modify: `app/services/data_pipeline/__init__.py`
- Test: `tests/test_external_fetcher.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_external_fetcher.py
import pytest
from pathlib import Path
import tempfile


def test_external_fetcher_parses_config():
    from app.services.data_pipeline.external_fetcher import ExternalFetcher

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "fetch_sources.yaml"
        output_dir = Path(tmpdir) / "output"

        config_path.write_text("""
sources:
  - url: "https://example.com/docs"
    mode: on-demand
    review: true
""")

        fetcher = ExternalFetcher(config_path, output_dir)
        sources = fetcher.get_sources()

        assert len(sources) == 1
        assert sources[0]["url"] == "https://example.com/docs"
        assert sources[0]["mode"] == "on-demand"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_external_fetcher.py::test_external_fetcher_parses_config -v`
Expected: FAIL

- [ ] **Step 3: Implement ExternalFetcher**

```python
# app/services/data_pipeline/external_fetcher.py
"""Fetch content from external URLs."""

from __future__ import annotations

import hashlib
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


class ExternalFetcher:
    """Fetch and process content from configured external URLs."""

    def __init__(
        self,
        config_path: Path,
        output_dir: Path,
        pending_dir: Path | None = None,
    ):
        self.config_path = config_path
        self.output_dir = output_dir
        self.pending_dir = pending_dir or (output_dir.parent / "pending" / "external")

    def _load_config(self) -> dict[str, Any]:
        """Load fetch sources config."""
        if not self.config_path.exists():
            return {"sources": []}
        try:
            return yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        except Exception:
            return {"sources": []}

    def get_sources(self) -> list[dict[str, Any]]:
        """Get list of configured sources."""
        config = self._load_config()
        return config.get("sources", [])

    def fetch_url(self, url: str, review: bool = True) -> dict[str, Any]:
        """Fetch content from a URL."""
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                content = response.read().decode("utf-8", errors="replace")
        except Exception as e:
            return {"error": str(e), "url": url}

        # Extract text content (basic HTML stripping)
        text = self._strip_html(content)

        # Generate filename from URL
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        filename = f"external_{url_hash}.md"

        # Format as markdown
        lines = [
            f"# External Content",
            f"Source URL: {url}",
            f"Fetch Date: {datetime.now().isoformat()}",
            "",
            "---",
            "",
            text[:10000],  # Limit content length
        ]
        content_md = "\n".join(lines)

        # Write to appropriate directory
        if review:
            self.pending_dir.mkdir(parents=True, exist_ok=True)
            output_path = self.pending_dir / filename
        else:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            output_path = self.output_dir / filename

        output_path.write_text(content_md, encoding="utf-8")

        return {
            "url": url,
            "output": str(output_path),
            "review_required": review,
            "content_length": len(text),
        }

    def _strip_html(self, html: str) -> str:
        """Basic HTML to text conversion."""
        # Remove script and style elements
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.I)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.I)
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Decode common entities
        text = text.replace("&nbsp;", " ").replace("&amp;", "&")
        text = text.replace("&lt;", "<").replace("&gt;", ">")
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def fetch_all_scheduled(self) -> list[dict[str, Any]]:
        """Fetch all sources marked as 'scheduled' or 'auto'."""
        sources = self.get_sources()
        results = []

        for source in sources:
            mode = source.get("mode", "on-demand")
            if mode in ("scheduled", "auto"):
                review = source.get("review", True)
                result = self.fetch_url(source["url"], review=review)
                results.append(result)

        return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_external_fetcher.py::test_external_fetcher_parses_config -v`
Expected: PASS

- [ ] **Step 5: Update module init**

```python
# app/services/data_pipeline/__init__.py
"""Data pipeline module for automated ingestion."""

from app.services.data_pipeline.feedback_processor import FeedbackProcessor
from app.services.data_pipeline.folder_watcher import FolderWatcher
from app.services.data_pipeline.external_fetcher import ExternalFetcher

__all__ = [
    "FeedbackProcessor",
    "FolderWatcher",
    "ExternalFetcher",
]
```

- [ ] **Step 6: Commit external fetcher**

```bash
git add app/services/data_pipeline/external_fetcher.py app/services/data_pipeline/__init__.py tests/test_external_fetcher.py
git commit -m "feat: add external fetcher for URL content ingestion"
```

---

## Task 11: Eval Engine - Runner

**Files:**
- Create: `app/services/eval_engine/__init__.py`
- Create: `app/services/eval_engine/runner.py`
- Test: `tests/test_eval_runner.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_eval_runner.py
import pytest
import json
from pathlib import Path
import tempfile


def test_eval_runner_loads_evals():
    from app.services.eval_engine.runner import EvalRunner

    with tempfile.TemporaryDirectory() as tmpdir:
        eval_path = Path(tmpdir) / "test.jsonl"
        eval_path.write_text("""
{"id": "test-001", "question": "What is X?", "ideal_keywords": ["keyword1"]}
{"id": "test-002", "question": "What is Y?", "ideal_keywords": ["keyword2"]}
""".strip())

        runner = EvalRunner(eval_path, "http://localhost:8080")
        evals = runner.load_evals()

        assert len(evals) == 2
        assert evals[0]["id"] == "test-001"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_eval_runner.py::test_eval_runner_loads_evals -v`
Expected: FAIL

- [ ] **Step 3: Create module init**

```python
# app/services/eval_engine/__init__.py
"""Eval engine for testing chat quality."""

from app.services.eval_engine.runner import EvalRunner

__all__ = [
    "EvalRunner",
]
```

- [ ] **Step 4: Implement EvalRunner**

```python
# app/services/eval_engine/runner.py
"""Run eval suites against the chat API."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


FAST_MODES = {"rag_seed_direct", "memory_direct", "rag_direct", "unknown_guard"}


class EvalRunner:
    """Run evaluation tests against the chat API."""

    def __init__(
        self,
        eval_path: Path,
        base_url: str,
        timeout: float = 12.0,
    ):
        self.eval_path = eval_path
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def load_evals(self) -> list[dict[str, Any]]:
        """Load eval records from JSONL file."""
        records = []
        with self.eval_path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return records

    def run_single(self, eval_record: dict[str, Any]) -> dict[str, Any]:
        """Run a single eval and return result."""
        question = eval_record.get("question", "")
        keywords = eval_record.get("ideal_keywords", [])
        expect_mode = eval_record.get("expect_mode")
        max_ms = eval_record.get("max_ms")

        # Call API
        data, elapsed_ms = self._post_chat(question)

        if "error" in data:
            return {
                "id": eval_record.get("id", ""),
                "passed": False,
                "reason": f"API error: {data['error']}",
                "ms": elapsed_ms,
            }

        answer = str(data.get("response", ""))
        mode = str(data.get("answer_mode", ""))

        # Check keywords
        found, missing = self._check_keywords(answer, keywords)

        # Determine pass/fail
        passed = True
        reasons = []

        if missing:
            passed = False
            reasons.append(f"missing keywords: {missing}")

        if expect_mode and mode != expect_mode:
            passed = False
            reasons.append(f"expected mode {expect_mode}, got {mode}")

        if max_ms and elapsed_ms > max_ms:
            passed = False
            reasons.append(f"exceeded {max_ms}ms (took {elapsed_ms:.1f}ms)")

        return {
            "id": eval_record.get("id", ""),
            "passed": passed,
            "reason": "; ".join(reasons) if reasons else None,
            "ms": round(elapsed_ms, 1),
            "mode": mode,
            "keywords_found": found,
            "keywords_missing": missing,
        }

    def run_all(self) -> list[dict[str, Any]]:
        """Run all evals and return results."""
        evals = self.load_evals()
        return [self.run_single(e) for e in evals]

    def _post_chat(self, question: str) -> tuple[dict[str, Any], float]:
        """POST to /api/chat and return response with timing."""
        body = json.dumps({"message": question}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read().decode("utf-8")
        except urllib.error.URLError as e:
            elapsed_ms = (time.perf_counter() - started) * 1000
            return {"error": str(e)}, elapsed_ms

        elapsed_ms = (time.perf_counter() - started) * 1000
        try:
            return json.loads(payload), elapsed_ms
        except json.JSONDecodeError:
            return {"error": "invalid JSON response"}, elapsed_ms

    def _check_keywords(
        self, answer: str, keywords: list[str]
    ) -> tuple[list[str], list[str]]:
        """Check which keywords are present in answer."""
        answer_lower = answer.lower()
        found = [k for k in keywords if k.lower() in answer_lower]
        missing = [k for k in keywords if k.lower() not in answer_lower]
        return found, missing
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_eval_runner.py::test_eval_runner_loads_evals -v`
Expected: PASS

- [ ] **Step 6: Commit eval runner**

```bash
git add app/services/eval_engine/__init__.py app/services/eval_engine/runner.py tests/test_eval_runner.py
git commit -m "feat: add eval runner for chat API testing"
```

---

## Task 12: Eval Engine - Reporter

**Files:**
- Create: `app/services/eval_engine/reporter.py`
- Modify: `app/services/eval_engine/__init__.py`
- Test: `tests/test_eval_reporter.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_eval_reporter.py
import pytest
import json
from pathlib import Path
import tempfile


def test_reporter_generates_summary():
    from app.services.eval_engine.reporter import EvalReporter

    results = [
        {"id": "1", "passed": True, "ms": 10},
        {"id": "2", "passed": True, "ms": 20},
        {"id": "3", "passed": False, "ms": 30, "reason": "missing keyword"},
    ]

    reporter = EvalReporter(results)
    summary = reporter.generate_summary()

    assert summary["total"] == 3
    assert summary["passed"] == 2
    assert summary["failed"] == 1
    assert summary["avg_ms"] == 20.0


def test_reporter_detects_regressions():
    from app.services.eval_engine.reporter import EvalReporter

    results = [
        {"id": "1", "passed": False, "ms": 10},
        {"id": "2", "passed": True, "ms": 20},
    ]
    baseline = {
        "results": [
            {"id": "1", "passed": True},  # Was passing, now failing
            {"id": "2", "passed": True},
        ]
    }

    reporter = EvalReporter(results)
    regressions = reporter.detect_regressions(baseline)

    assert len(regressions) == 1
    assert regressions[0]["id"] == "1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_eval_reporter.py -v`
Expected: FAIL

- [ ] **Step 3: Implement EvalReporter**

```python
# app/services/eval_engine/reporter.py
"""Generate reports and detect regressions."""

from __future__ import annotations

import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any


class EvalReporter:
    """Generate eval reports and detect regressions."""

    def __init__(self, results: list[dict[str, Any]]):
        self.results = results

    def generate_summary(self) -> dict[str, Any]:
        """Generate summary statistics."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.get("passed"))
        failed = total - passed

        times = [r.get("ms", 0) for r in self.results if r.get("ms")]
        avg_ms = statistics.mean(times) if times else 0
        p95_ms = (
            sorted(times)[int(len(times) * 0.95)] if len(times) >= 5 else max(times, default=0)
        )

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "avg_ms": round(avg_ms, 1),
            "p95_ms": round(p95_ms, 1),
        }

    def detect_regressions(
        self,
        baseline: dict[str, Any],
        time_threshold_pct: float = 20.0,
    ) -> list[dict[str, Any]]:
        """Detect regressions compared to baseline."""
        regressions = []

        # Build lookup of baseline results by id
        baseline_results = {
            r.get("id"): r for r in baseline.get("results", [])
        }

        for result in self.results:
            result_id = result.get("id")
            baseline_result = baseline_results.get(result_id)

            if not baseline_result:
                continue

            # Check for new failure
            if baseline_result.get("passed") and not result.get("passed"):
                regressions.append({
                    "id": result_id,
                    "type": "new_failure",
                    "reason": result.get("reason", "now failing"),
                })

            # Check for mode regression
            baseline_mode = baseline_result.get("mode")
            current_mode = result.get("mode")
            if baseline_mode and current_mode and baseline_mode != current_mode:
                # Regression if we went from fast mode to slow mode
                fast_modes = {"rag_seed_direct", "memory_direct", "rag_direct"}
                if baseline_mode in fast_modes and current_mode not in fast_modes:
                    regressions.append({
                        "id": result_id,
                        "type": "mode_regression",
                        "reason": f"{baseline_mode} -> {current_mode}",
                    })

        # Check overall time regression
        baseline_summary = baseline.get("summary", {})
        current_summary = self.generate_summary()

        baseline_avg = baseline_summary.get("avg_ms", 0)
        current_avg = current_summary.get("avg_ms", 0)

        if baseline_avg > 0:
            pct_change = ((current_avg - baseline_avg) / baseline_avg) * 100
            if pct_change > time_threshold_pct:
                regressions.append({
                    "id": "_overall",
                    "type": "time_regression",
                    "reason": f"avg_ms increased {pct_change:.1f}% ({baseline_avg:.1f} -> {current_avg:.1f})",
                })

        return regressions

    def generate_report(
        self,
        baseline: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate full report with optional regression detection."""
        summary = self.generate_summary()
        regressions = []

        if baseline:
            regressions = self.detect_regressions(baseline)

        return {
            "run_id": datetime.now().strftime("%Y-%m-%d-%H%M%S"),
            "summary": summary,
            "regressions": regressions,
            "results": self.results,
        }

    def write_report(self, output_path: Path, baseline: dict[str, Any] | None = None) -> None:
        """Write report to JSON file."""
        report = self.generate_report(baseline)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, indent=2) + "\n",
            encoding="utf-8",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_eval_reporter.py -v`
Expected: All PASS

- [ ] **Step 5: Update module init**

```python
# app/services/eval_engine/__init__.py
"""Eval engine for testing chat quality."""

from app.services.eval_engine.runner import EvalRunner
from app.services.eval_engine.reporter import EvalReporter

__all__ = [
    "EvalRunner",
    "EvalReporter",
]
```

- [ ] **Step 6: Commit eval reporter**

```bash
git add app/services/eval_engine/reporter.py app/services/eval_engine/__init__.py tests/test_eval_reporter.py
git commit -m "feat: add eval reporter with regression detection"
```

---

## Task 13: Eval Engine - Generator

**Files:**
- Create: `app/services/eval_engine/generator.py`
- Modify: `app/services/eval_engine/__init__.py`
- Test: `tests/test_eval_generator.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_eval_generator.py
import pytest
import json
from pathlib import Path
import tempfile


def test_generator_creates_evals_from_feedback():
    from app.services.eval_engine.generator import EvalGenerator

    with tempfile.TemporaryDirectory() as tmpdir:
        feedback_path = Path(tmpdir) / "feedback.jsonl"

        feedback_data = [
            {"question": "What is X?", "rating": "right", "answer": "X is a thing with features"},
            {"question": "What is Y?", "rating": "wrong", "correction": "Y is something else entirely"},
        ]
        with feedback_path.open("w") as f:
            for item in feedback_data:
                f.write(json.dumps(item) + "\n")

        generator = EvalGenerator(feedback_path)
        evals = generator.generate()

        assert len(evals) == 2
        assert evals[0]["source"] == "feedback_right"
        assert evals[1]["source"] == "feedback_wrong"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_eval_generator.py::test_generator_creates_evals_from_feedback -v`
Expected: FAIL

- [ ] **Step 3: Implement EvalGenerator**

```python
# app/services/eval_engine/generator.py
"""Auto-generate eval cases from feedback."""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from app.services.seed_index.fuzzy import normalize


class EvalGenerator:
    """Generate eval cases from user feedback."""

    def __init__(self, feedback_path: Path):
        self.feedback_path = feedback_path

    def _load_feedback(self) -> list[dict[str, Any]]:
        """Load feedback entries."""
        if not self.feedback_path.exists():
            return []

        entries = []
        for line in self.feedback_path.read_text(encoding="utf-8").strip().split("\n"):
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries

    def _extract_keywords(self, text: str, max_keywords: int = 5) -> list[str]:
        """Extract significant keywords from text."""
        # Simple extraction: words longer than 3 chars, not common
        stop_words = {
            "the", "and", "for", "are", "but", "not", "you", "all",
            "can", "had", "her", "was", "one", "our", "out", "has",
            "have", "been", "will", "more", "when", "what", "this",
            "that", "with", "from", "they", "which", "about", "into",
        }

        words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
        keywords = [w for w in words if w not in stop_words]

        # Dedupe while preserving order
        seen = set()
        unique = []
        for w in keywords:
            if w not in seen:
                seen.add(w)
                unique.append(w)

        return unique[:max_keywords]

    def _is_duplicate(
        self,
        question: str,
        existing: list[dict[str, Any]],
        threshold: float = 0.85,
    ) -> bool:
        """Check if question is too similar to existing."""
        normalized = normalize(question)
        for e in existing:
            existing_normalized = normalize(e.get("question", ""))
            ratio = SequenceMatcher(None, normalized, existing_normalized).ratio()
            if ratio >= threshold:
                return True
        return False

    def generate(self) -> list[dict[str, Any]]:
        """Generate eval cases from feedback."""
        feedback = self._load_feedback()
        evals = []
        id_counter = 1

        for entry in feedback:
            question = entry.get("question", "")
            rating = entry.get("rating", "")

            if not question:
                continue

            # Skip duplicates
            if self._is_duplicate(question, evals):
                continue

            if rating == "right":
                # Use answer keywords for expected output
                answer = entry.get("answer", "")
                keywords = self._extract_keywords(answer)
                if keywords:
                    evals.append({
                        "id": f"auto-{id_counter:03d}",
                        "question": question,
                        "ideal_keywords": keywords,
                        "source": "feedback_right",
                    })
                    id_counter += 1

            elif rating == "wrong" and entry.get("correction"):
                # Use correction keywords for expected output
                correction = entry.get("correction", "")
                keywords = self._extract_keywords(correction)
                if keywords:
                    evals.append({
                        "id": f"auto-{id_counter:03d}",
                        "question": question,
                        "ideal_keywords": keywords,
                        "source": "feedback_wrong",
                    })
                    id_counter += 1

        return evals

    def write_evals(self, output_path: Path) -> dict[str, Any]:
        """Generate and write evals to JSONL file."""
        evals = self.generate()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            for e in evals:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

        return {
            "path": str(output_path),
            "count": len(evals),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_eval_generator.py::test_generator_creates_evals_from_feedback -v`
Expected: PASS

- [ ] **Step 5: Update module init**

```python
# app/services/eval_engine/__init__.py
"""Eval engine for testing chat quality."""

from app.services.eval_engine.runner import EvalRunner
from app.services.eval_engine.reporter import EvalReporter
from app.services.eval_engine.generator import EvalGenerator

__all__ = [
    "EvalRunner",
    "EvalReporter",
    "EvalGenerator",
]
```

- [ ] **Step 6: Commit eval generator**

```bash
git add app/services/eval_engine/generator.py app/services/eval_engine/__init__.py tests/test_eval_generator.py
git commit -m "feat: add eval generator from user feedback"
```

---

## Task 14: CLI Scripts for Pipeline

**Files:**
- Create: `scripts/rag/process_feedback.py`
- Create: `scripts/rag/watch_ingest.py`
- Create: `scripts/rag/fetch_external.py`
- Create: `scripts/eval/generate_evals.py`

- [ ] **Step 1: Create process_feedback.py**

```python
#!/usr/bin/env python3
"""Process feedback corrections into seed files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.data_pipeline.feedback_processor import FeedbackProcessor


def main() -> int:
    parser = argparse.ArgumentParser(description="Process feedback corrections.")
    parser.add_argument(
        "--input",
        default="data/feedback/chat_feedback.jsonl",
        help="Feedback JSONL file.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/rag_seed",
        help="Output directory for corrections.",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=3,
        help="Corrections needed for auto-approval.",
    )
    args = parser.parse_args()

    processor = FeedbackProcessor(
        ROOT / args.input,
        ROOT / args.output_dir,
        threshold=args.threshold,
    )
    result = processor.process()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Create watch_ingest.py**

```python
#!/usr/bin/env python3
"""Watch ingest folder for new files."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.data_pipeline.folder_watcher import FolderWatcher


def main() -> int:
    parser = argparse.ArgumentParser(description="Watch folder for new files to ingest.")
    parser.add_argument(
        "--watch-dir",
        default="data/rag_ingest",
        help="Directory to watch.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/rag_seed/ingested",
        help="Directory for processed files.",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run continuously, polling every 10 seconds.",
    )
    args = parser.parse_args()

    watcher = FolderWatcher(
        ROOT / args.watch_dir,
        ROOT / args.output_dir,
    )

    if args.daemon:
        print(f"Watching {args.watch_dir} for new files...")
        while True:
            result = watcher.process_pending()
            if result["files_processed"] > 0:
                print(json.dumps(result, indent=2))
            time.sleep(10)
    else:
        result = watcher.process_pending()
        print(json.dumps(result, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Create fetch_external.py**

```python
#!/usr/bin/env python3
"""Fetch content from external URLs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.data_pipeline.external_fetcher import ExternalFetcher


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch external content.")
    parser.add_argument(
        "--config",
        default="configs/fetch_sources.yaml",
        help="Fetch sources config.",
    )
    parser.add_argument(
        "--url",
        help="Fetch a specific URL (overrides config).",
    )
    parser.add_argument(
        "--scheduled",
        action="store_true",
        help="Fetch all scheduled/auto sources from config.",
    )
    parser.add_argument(
        "--no-review",
        action="store_true",
        help="Index immediately without review.",
    )
    args = parser.parse_args()

    fetcher = ExternalFetcher(
        ROOT / args.config,
        ROOT / "data" / "rag_seed" / "external",
    )

    if args.url:
        result = fetcher.fetch_url(args.url, review=not args.no_review)
        print(json.dumps(result, indent=2))
    elif args.scheduled:
        results = fetcher.fetch_all_scheduled()
        print(json.dumps(results, indent=2))
    else:
        print("Specify --url or --scheduled")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Create generate_evals.py**

```python
#!/usr/bin/env python3
"""Generate eval cases from feedback."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.eval_engine.generator import EvalGenerator


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate evals from feedback.")
    parser.add_argument(
        "--input",
        default="data/feedback/chat_feedback.jsonl",
        help="Feedback JSONL file.",
    )
    parser.add_argument(
        "--output",
        default="data/evals/auto_generated.jsonl",
        help="Output eval file.",
    )
    args = parser.parse_args()

    generator = EvalGenerator(ROOT / args.input)
    result = generator.write_evals(ROOT / args.output)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Make scripts executable and commit**

```bash
chmod +x scripts/rag/process_feedback.py scripts/rag/watch_ingest.py scripts/rag/fetch_external.py scripts/eval/generate_evals.py
git add scripts/rag/process_feedback.py scripts/rag/watch_ingest.py scripts/rag/fetch_external.py scripts/eval/generate_evals.py
git commit -m "feat: add CLI scripts for data pipeline and eval generation"
```

---

## Task 15: Integrate Lookup into Chat Service

**Files:**
- Modify: `app/services/chat.py`

- [ ] **Step 1: Add fuzzy index loading to ChatService**

At the top of `app/services/chat.py`, add imports:

```python
from pathlib import Path
from app.services.seed_index.lookup import SeedIndexLookup
from app.services.seed_index.tracker import QueryMissTracker
```

- [ ] **Step 2: Add index initialization in ChatService.__init__**

In the `__init__` method, after existing initialization:

```python
        # Load fuzzy seed index
        self._seed_index = None
        self._miss_tracker = None
        self._load_seed_index()

    def _load_seed_index(self):
        """Load the fuzzy seed index if available."""
        index_path = Path(self.config.BASE_DIR) / "data" / "reference" / "seed_index_fuzzy.json"
        if index_path.exists():
            try:
                self._seed_index = SeedIndexLookup.from_file(index_path)
            except Exception as e:
                print(f"Failed to load fuzzy index: {e}")
                self._seed_index = None

        miss_log_path = Path(self.config.BASE_DIR) / "data" / "reference" / "query_misses.jsonl"
        self._miss_tracker = QueryMissTracker(miss_log_path)
```

- [ ] **Step 3: Add fuzzy lookup method**

Add this method to `ChatService`:

```python
    def _lookup_fuzzy_seed(self, query: str) -> Optional[dict]:
        """Look up query in fuzzy seed index."""
        if not self._seed_index:
            return None

        result = self._seed_index.lookup_with_suggestions(query)

        if result.get("match") and result.get("confidence", 0) >= 0.7:
            return result
        return None
```

- [ ] **Step 4: Update _answer_fast_mainframe_qa to use fuzzy lookup first**

In the `_answer_fast_mainframe_qa` method (or `process_message`), add fuzzy lookup before existing logic:

```python
        # Try fuzzy seed index first (fastest path)
        fuzzy_result = self._lookup_fuzzy_seed(user_message)
        if fuzzy_result and fuzzy_result.get("match"):
            match = fuzzy_result["match"]
            confidence = fuzzy_result.get("confidence", 1.0)

            # Format response
            response = format_seed_definition(match)

            if confidence < 0.9 and fuzzy_result.get("assumed_term"):
                response = f"(Assuming you meant {fuzzy_result['assumed_term']})\n\n{response}"

            return {
                "response": response,
                "answer_mode": "rag_seed_direct",
                "confidence": confidence,
                "rag_used": False,
            }
```

- [ ] **Step 5: Add miss tracking when falling back to LLM**

Before LLM fallback, add:

```python
        # Log query miss for backlog
        if self._miss_tracker:
            suggestions = []
            if fuzzy_result and fuzzy_result.get("suggestions"):
                suggestions = [s["title"] for s in fuzzy_result["suggestions"]]
            self._miss_tracker.log_miss(user_message, "rag_llm", suggestions)
```

- [ ] **Step 6: Test the integration manually**

```bash
# Build the fuzzy index first
python scripts/rag/build_seed_index.py --fuzzy

# Start the app and test queries
# - "what is mainframe" should return rag_seed_direct
# - "mainfraem" should auto-correct and return rag_seed_direct
# - "what is mf" should use abbreviation and return rag_seed_direct
```

- [ ] **Step 7: Commit integration**

```bash
git add app/services/chat.py
git commit -m "feat: integrate fuzzy seed index lookup into chat service"
```

---

## Task 16: Update Eval Runner with Regression Detection

**Files:**
- Modify: `scripts/eval/run_chat_evals.py`

- [ ] **Step 1: Update run_chat_evals.py with regression support**

```python
#!/usr/bin/env python3
"""Run chat evals against the local Mainframe AI API."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.eval_engine.runner import EvalRunner
from app.services.eval_engine.reporter import EvalReporter


def main() -> int:
    parser = argparse.ArgumentParser(description="Run chat evals against a local /api/chat endpoint.")
    parser.add_argument("--input", default="data/evals/mainframe_eval_sample.jsonl", help="Eval JSONL path.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080", help="Base URL for the app.")
    parser.add_argument("--timeout", type=float, default=12.0, help="Per-request timeout in seconds.")
    parser.add_argument("--output", default="", help="Optional JSON report output path.")
    parser.add_argument("--baseline", default="data/evals/baseline.json", help="Baseline for regression detection.")
    parser.add_argument("--set-baseline", action="store_true", help="Set current results as new baseline.")
    parser.add_argument("--fail-on-regression", action="store_true", help="Exit nonzero if regressions detected.")
    args = parser.parse_args()

    eval_path = ROOT / args.input
    runner = EvalRunner(eval_path, args.base_url, timeout=args.timeout)

    print(f"Running evals from {args.input}...")
    results = runner.run_all()

    # Print individual results
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"{status} {r['id']} {r.get('ms', 0):.1f}ms mode={r.get('mode', '')} {r.get('reason', '')}")

    # Generate report
    reporter = EvalReporter(results)
    summary = reporter.generate_summary()
    print(f"\nSummary: {summary['passed']}/{summary['total']} passed, avg {summary['avg_ms']:.1f}ms")

    # Check for regressions
    baseline_path = ROOT / args.baseline
    regressions = []
    if baseline_path.exists() and not args.set_baseline:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        regressions = reporter.detect_regressions(baseline)
        if regressions:
            print(f"\nRegressions detected ({len(regressions)}):")
            for reg in regressions:
                print(f"  - {reg['id']}: {reg['type']} - {reg['reason']}")

    # Write output
    if args.output:
        output_path = ROOT / args.output
        reporter.write_report(output_path, baseline if baseline_path.exists() else None)
        print(f"\nReport written to {output_path}")

    # Set baseline if requested
    if args.set_baseline:
        report = reporter.generate_report()
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"\nBaseline set at {baseline_path}")

    # Exit code
    if summary["failed"] > 0:
        return 1
    if args.fail_on_regression and regressions:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Commit updated eval runner**

```bash
git add scripts/eval/run_chat_evals.py
git commit -m "feat: update eval runner with regression detection and baseline support"
```

---

## Task 17: Add PyYAML and Jellyfish Dependencies

**Files:**
- Modify: `requirements.txt` (or `pyproject.toml` if used)

- [ ] **Step 1: Check for requirements file**

```bash
ls -la requirements*.txt pyproject.toml 2>/dev/null || echo "No requirements file found"
```

- [ ] **Step 2: Add dependencies**

If `requirements.txt` exists, append:
```
pyyaml>=6.0
jellyfish>=1.0.0
```

If `pyproject.toml` exists, add to dependencies section.

- [ ] **Step 3: Install dependencies**

```bash
pip install pyyaml jellyfish
```

- [ ] **Step 4: Commit dependency update**

```bash
git add requirements.txt  # or pyproject.toml
git commit -m "feat: add pyyaml and jellyfish dependencies for fuzzy matching"
```

---

## Task 18: Create .gitkeep Files for Empty Directories

**Files:**
- Create: Multiple `.gitkeep` files

- [ ] **Step 1: Create .gitkeep files**

```bash
touch data/rag_seed/approved/.gitkeep
touch data/rag_seed/pending/.gitkeep
touch data/rag_seed/ingested/.gitkeep
touch data/rag_seed/external/.gitkeep
touch data/rag_ingest/.processed/.gitkeep
touch data/evals/results/.gitkeep
```

- [ ] **Step 2: Commit**

```bash
git add data/rag_seed/approved/.gitkeep data/rag_seed/pending/.gitkeep data/rag_seed/ingested/.gitkeep data/rag_seed/external/.gitkeep data/rag_ingest/.processed/.gitkeep data/evals/results/.gitkeep
git commit -m "chore: add .gitkeep for empty pipeline directories"
```

---

## Task 19: Run Full Test Suite

- [ ] **Step 1: Run all tests**

```bash
pytest tests/ -v
```
Expected: All PASS

- [ ] **Step 2: Build fuzzy index**

```bash
python scripts/rag/build_seed_index.py --fuzzy
```

- [ ] **Step 3: Run evals to establish baseline**

```bash
# Start the app first, then:
python scripts/eval/run_chat_evals.py --set-baseline
```

- [ ] **Step 4: Commit any fixes if needed**

---

## Task 20: Final Integration Test

- [ ] **Step 1: Test typo tolerance**

```bash
# With app running:
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "what is mainfraem"}' | jq
```
Expected: `answer_mode: "rag_seed_direct"`, response about mainframes

- [ ] **Step 2: Test abbreviation**

```bash
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "what is mf"}' | jq
```
Expected: `answer_mode: "rag_seed_direct"`, response about mainframes

- [ ] **Step 3: Test suggestions for unknown term**

```bash
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "what is vtma"}' | jq
```
Expected: Suggestions including "VTAM", plus LLM fallback attempt

- [ ] **Step 4: Verify query miss logged**

```bash
cat data/reference/query_misses.jsonl
```
Expected: Entry with the "vtma" query

- [ ] **Step 5: Generate backlog**

```bash
python scripts/rag/generate_backlog.py
cat data/rag_seed/TODO.md
```

---

## Summary

This plan creates:

1. **Fuzzy Index Module** (`app/services/seed_index/`)
   - `fuzzy.py` - typo/phonetic/abbreviation generation
   - `builder.py` - builds pre-computed index
   - `lookup.py` - O(1) lookups with confidence
   - `tracker.py` - logs misses for backlog

2. **Data Pipeline** (`app/services/data_pipeline/`)
   - `feedback_processor.py` - extracts corrections from feedback
   - `folder_watcher.py` - processes dropped files
   - `external_fetcher.py` - fetches from URLs

3. **Eval Engine** (`app/services/eval_engine/`)
   - `runner.py` - runs eval suites
   - `reporter.py` - generates reports, detects regressions
   - `generator.py` - auto-generates evals from feedback

4. **CLI Scripts** (`scripts/`)
   - Updated `build_seed_index.py` with `--fuzzy`
   - New pipeline scripts
   - Updated `run_chat_evals.py` with regression detection

5. **Configuration** (`configs/`)
   - `seed_config.yaml` - main config
   - `abbreviations.yaml` - abbreviation mappings
   - `fetch_sources.yaml` - external URL allowlist

6. **Integration** - Updated `chat.py` to use fuzzy lookup first
