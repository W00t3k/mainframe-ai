"""Tests for eval engine components."""

import pytest
import json
from pathlib import Path
import tempfile


class TestEvalRunner:
    def test_loads_evals(self):
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


class TestEvalReporter:
    def test_generates_summary(self):
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

    def test_detects_regressions(self):
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
        assert regressions[0]["type"] == "new_failure"

    def test_detects_mode_regression(self):
        from app.services.eval_engine.reporter import EvalReporter

        results = [
            {"id": "1", "passed": True, "ms": 500, "mode": "rag_llm"},
        ]
        baseline = {
            "results": [
                {"id": "1", "passed": True, "mode": "rag_seed_direct"},
            ]
        }

        reporter = EvalReporter(results)
        regressions = reporter.detect_regressions(baseline)

        assert len(regressions) == 1
        assert regressions[0]["type"] == "mode_regression"

    def test_writes_report(self):
        from app.services.eval_engine.reporter import EvalReporter

        with tempfile.TemporaryDirectory() as tmpdir:
            results = [{"id": "1", "passed": True, "ms": 10}]
            output_path = Path(tmpdir) / "report.json"

            reporter = EvalReporter(results)
            reporter.write_report(output_path)

            assert output_path.exists()
            data = json.loads(output_path.read_text())
            assert "summary" in data
            assert "results" in data


class TestEvalGenerator:
    def test_creates_evals_from_feedback(self):
        from app.services.eval_engine.generator import EvalGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            feedback_path = Path(tmpdir) / "feedback.jsonl"

            feedback_data = [
                {"question": "What is a mainframe computer?", "rating": "right", "answer": "A mainframe is a large computer with features and capabilities"},
                {"question": "Explain RACF security system", "rating": "wrong", "correction": "RACF is the security manager that controls access permissions"},
            ]
            with feedback_path.open("w") as f:
                for item in feedback_data:
                    f.write(json.dumps(item) + "\n")

            generator = EvalGenerator(feedback_path)
            evals = generator.generate()

            assert len(evals) == 2
            assert evals[0]["source"] == "feedback_right"
            assert evals[1]["source"] == "feedback_wrong"

    def test_deduplicates_similar_questions(self):
        from app.services.eval_engine.generator import EvalGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            feedback_path = Path(tmpdir) / "feedback.jsonl"

            feedback_data = [
                {"question": "What is mainframe?", "rating": "right", "answer": "A large computer system"},
                {"question": "What is a mainframe?", "rating": "right", "answer": "An enterprise system"},
            ]
            with feedback_path.open("w") as f:
                for item in feedback_data:
                    f.write(json.dumps(item) + "\n")

            generator = EvalGenerator(feedback_path)
            evals = generator.generate()

            # Should dedupe similar questions
            assert len(evals) == 1

    def test_writes_evals(self):
        from app.services.eval_engine.generator import EvalGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            feedback_path = Path(tmpdir) / "feedback.jsonl"
            output_path = Path(tmpdir) / "evals.jsonl"

            feedback_data = [
                {"question": "What is test?", "rating": "right", "answer": "Test is a verification method"},
            ]
            with feedback_path.open("w") as f:
                for item in feedback_data:
                    f.write(json.dumps(item) + "\n")

            generator = EvalGenerator(feedback_path)
            result = generator.write_evals(output_path)

            assert output_path.exists()
            assert result["count"] == 1
