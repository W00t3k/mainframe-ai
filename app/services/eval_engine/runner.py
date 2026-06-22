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
