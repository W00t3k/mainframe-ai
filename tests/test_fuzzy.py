"""Tests for fuzzy matching utilities."""

import pytest


def test_normalize_basic():
    from app.services.seed_index.fuzzy import normalize
    assert normalize("System/360") == "system360"
    assert normalize("RACF") == "racf"
    assert normalize("  What is JCL?  ") == "what is jcl"


def test_generate_typos_swap():
    from app.services.seed_index.fuzzy import generate_typos
    variants = generate_typos("mainframe", max_distance=1)
    assert "mainfraem" in variants
    assert "mainframe" in variants


def test_generate_typos_missing():
    from app.services.seed_index.fuzzy import generate_typos
    variants = generate_typos("racf", max_distance=1)
    assert "rac" in variants
    assert "acf" in variants


def test_generate_phonetic():
    from app.services.seed_index.fuzzy import generate_phonetic
    variants = generate_phonetic("cics")
    assert len(variants) >= 1
    assert "cics" in variants


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
    assert "jobcontrollanguage" in variants


def test_generate_all_variants():
    from app.services.seed_index.fuzzy import generate_all_variants
    abbrevs = {"mf": "mainframe"}
    variants = generate_all_variants("mainframe", abbrevs, typo_distance=1)
    assert "mainframe" in variants
    assert "mf" in variants
    assert "mainfraem" in variants
