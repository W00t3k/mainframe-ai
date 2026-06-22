"""Tests for data pipeline components."""

import pytest
import json
from pathlib import Path
import tempfile


class TestFeedbackProcessor:
    def test_process_extracts_corrections(self):
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

    def test_process_empty_file(self):
        from app.services.data_pipeline.feedback_processor import FeedbackProcessor

        with tempfile.TemporaryDirectory() as tmpdir:
            feedback_path = Path(tmpdir) / "feedback.jsonl"
            output_dir = Path(tmpdir) / "output"
            feedback_path.touch()

            processor = FeedbackProcessor(feedback_path, output_dir)
            result = processor.process()

            assert result["corrections_found"] == 0


class TestFolderWatcher:
    def test_processes_markdown(self):
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

    def test_processes_json(self):
        from app.services.data_pipeline.folder_watcher import FolderWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            ingest_dir = Path(tmpdir) / "ingest"
            output_dir = Path(tmpdir) / "output"

            ingest_dir.mkdir()

            # Create a test JSON file
            test_file = ingest_dir / "terms.json"
            test_file.write_text(json.dumps([
                {"term": "TestTerm", "definition": "A test definition"}
            ]))

            watcher = FolderWatcher(ingest_dir, output_dir)
            result = watcher.process_pending()

            assert result["files_processed"] == 1
            assert (output_dir / "terms.md").exists()

    def test_empty_directory(self):
        from app.services.data_pipeline.folder_watcher import FolderWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            ingest_dir = Path(tmpdir) / "ingest"
            output_dir = Path(tmpdir) / "output"
            ingest_dir.mkdir()

            watcher = FolderWatcher(ingest_dir, output_dir)
            result = watcher.process_pending()

            assert result["files_processed"] == 0


class TestExternalFetcher:
    def test_parses_config(self):
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

    def test_empty_config(self):
        from app.services.data_pipeline.external_fetcher import ExternalFetcher

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "fetch_sources.yaml"
            output_dir = Path(tmpdir) / "output"

            # No config file exists
            fetcher = ExternalFetcher(config_path, output_dir)
            sources = fetcher.get_sources()

            assert sources == []
