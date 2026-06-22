"""Tests for fuzzy index builder."""

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


def test_build_fuzzy_index_parses_aliases():
    from app.services.seed_index.builder import build_fuzzy_index

    with tempfile.TemporaryDirectory() as tmpdir:
        seed_dir = Path(tmpdir) / "rag_seed"
        seed_dir.mkdir()

        (seed_dir / "test.md").write_text("""
### RACF
Aliases: Resource Access Control Facility; SAF
Definition: The mainframe security manager.
""")

        index = build_fuzzy_index(seed_dir, {})

        # Check canonical entry has aliases
        assert "racf" in index["canonical"]
        aliases = index["canonical"]["racf"]["aliases"]
        assert "Resource Access Control Facility" in aliases
        assert "SAF" in aliases


def test_build_fuzzy_index_subdirectories():
    from app.services.seed_index.builder import build_fuzzy_index

    with tempfile.TemporaryDirectory() as tmpdir:
        seed_dir = Path(tmpdir) / "rag_seed"
        seed_dir.mkdir()
        (seed_dir / "approved").mkdir()

        # Main file
        (seed_dir / "main.md").write_text("""
### MainTerm
Definition: In the main directory.
""")

        # Approved subdirectory
        (seed_dir / "approved" / "approved.md").write_text("""
### ApprovedTerm
Definition: In the approved directory.
""")

        index = build_fuzzy_index(seed_dir, {})

        assert "mainterm" in index["canonical"]
        assert "approvedterm" in index["canonical"]


def test_write_fuzzy_index():
    from app.services.seed_index.builder import write_fuzzy_index

    with tempfile.TemporaryDirectory() as tmpdir:
        seed_dir = Path(tmpdir) / "rag_seed"
        seed_dir.mkdir()
        output_path = Path(tmpdir) / "output" / "index.json"

        (seed_dir / "test.md").write_text("""
### TestTerm
Definition: A test.
""")

        result = write_fuzzy_index(seed_dir, output_path, {})

        assert output_path.exists()
        assert result["canonical_count"] == 1
        assert result["fuzzy_map_count"] > 0

        # Verify JSON is valid
        data = json.loads(output_path.read_text())
        assert data["version"] == "1.0"
