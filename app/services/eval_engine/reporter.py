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
