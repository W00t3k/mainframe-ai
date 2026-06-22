"""Tests for seed index lookup."""

import pytest


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


def test_lookup_no_match():
    from app.services.seed_index.lookup import SeedIndexLookup

    index = {
        "version": "1.0",
        "canonical": {
            "mainframe": {"title": "Mainframe", "definition": "A large computer"},
        },
        "fuzzy_map": {
            "mainframe": "mainframe",
        }
    }

    lookup = SeedIndexLookup(index)
    result = lookup.lookup("completely unknown term xyz")

    assert result is None


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


def test_lookup_with_suggestions_high_confidence():
    from app.services.seed_index.lookup import SeedIndexLookup

    index = {
        "version": "1.0",
        "canonical": {
            "mainframe": {"title": "Mainframe", "definition": "A large computer"},
        },
        "fuzzy_map": {
            "mainframe": "mainframe",
        }
    }

    lookup = SeedIndexLookup(index)
    result = lookup.lookup_with_suggestions("mainframe")

    assert result["match"] is not None
    assert result["confidence"] >= 0.9
    assert result["match"]["title"] == "Mainframe"


def test_get_all_terms():
    from app.services.seed_index.lookup import SeedIndexLookup

    index = {
        "version": "1.0",
        "canonical": {
            "mainframe": {"title": "Mainframe"},
            "racf": {"title": "RACF"},
            "vsam": {"title": "VSAM"},
        },
        "fuzzy_map": {}
    }

    lookup = SeedIndexLookup(index)
    terms = lookup.get_all_terms()

    assert len(terms) == 3
    assert "mainframe" in terms
    assert "racf" in terms
    assert "vsam" in terms
