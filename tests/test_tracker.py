"""Tests for query miss tracker."""

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


def test_log_miss_appends():
    from app.services.seed_index.tracker import QueryMissTracker

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "query_misses.jsonl"
        tracker = QueryMissTracker(log_path)

        tracker.log_miss("query1", "rag_llm", [])
        tracker.log_miss("query2", "unknown_guard", ["suggestion"])

        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 2


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


def test_get_misses_empty():
    from app.services.seed_index.tracker import QueryMissTracker

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "query_misses.jsonl"
        tracker = QueryMissTracker(log_path)

        misses = tracker.get_misses()
        assert misses == []


def test_clear():
    from app.services.seed_index.tracker import QueryMissTracker

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "query_misses.jsonl"
        tracker = QueryMissTracker(log_path)

        tracker.log_miss("query1", "rag_llm", [])
        assert log_path.exists()

        tracker.clear()
        assert not log_path.exists()
