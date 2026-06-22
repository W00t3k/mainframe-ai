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


FAST_MODES = {"rag_seed_direct", "memory_direct", "rag_direct", "unknown_guard"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run chat evals against a local /api/chat endpoint.")
    parser.add_argument("--input", default="data/evals/mainframe_eval_sample.jsonl", help="Eval JSONL path.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080", help="Base URL for the app.")
    parser.add_argument("--timeout", type=float, default=12.0, help="Per-request timeout in seconds.")
    parser.add_argument("--slow-ms", type=float, default=1000.0, help="Latency threshold for SLOW.")
    parser.add_argument("--output", default="", help="Optional JSON report output path.")
    parser.add_argument("--id", action="append", default=[], help="Run only a specific eval id. May be repeated.")
    parser.add_argument("--question-contains", default="", help="Run only evals whose question contains this text.")
    parser.add_argument("--baseline", default="data/evals/baseline.json", help="Baseline for regression detection.")
    parser.add_argument("--set-baseline", action="store_true", help="Set current results as new baseline.")
    parser.add_argument("--fail-on-slow", action="store_true", help="Exit nonzero if any eval is slow.")
    parser.add_argument("--fail-on-llm", action="store_true", help="Exit nonzero if any eval falls through to LLM mode.")
    parser.add_argument("--fail-on-regression", action="store_true", help="Exit nonzero if regressions detected.")
    args = parser.parse_args()

    eval_path = ROOT / args.input
    runner = EvalRunner(eval_path, args.base_url, timeout=args.timeout)

    # Load and filter evals
    evals = runner.load_evals()
    if args.id:
        selected_ids = set(args.id)
        evals = [e for e in evals if str(e.get("id", "")) in selected_ids]
    if args.question_contains:
        needle = args.question_contains.lower()
        evals = [e for e in evals if needle in str(e.get("question", "")).lower()]

    print(f"Running {len(evals)} evals from {args.input}...")

    # Run evals
    results = [runner.run_single(e) for e in evals]

    # Print individual results
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        mode = r.get("mode", "")
        slow = r.get("ms", 0) > args.slow_ms
        speed = "SLOW" if slow else "FAST"
        llm_path = mode not in FAST_MODES
        path = "LLM" if llm_path else "DIRECT"
        ms = r.get("ms", 0)
        missing = r.get("keywords_missing", [])
        reason = r.get("reason", "")
        error = f" reason={reason}" if reason else ""
        print(f"{status} {speed} {path} {r['id']} {ms:.1f}ms mode={mode} missing={missing}{error}")

    # Generate report
    reporter = EvalReporter(results)
    summary = reporter.generate_summary()

    # Track slow and LLM results for exit code
    slow_results = [r for r in results if r.get("ms", 0) > args.slow_ms]
    llm_results = [r for r in results if r.get("mode", "") not in FAST_MODES]

    extended_summary = {
        **summary,
        "slow": len(slow_results),
        "llm_path": len(llm_results),
        "slow_ms": args.slow_ms,
    }
    print(f"\nSummary: {summary['passed']}/{summary['total']} passed, avg {summary['avg_ms']:.1f}ms, p95 {summary['p95_ms']:.1f}ms")
    print(json.dumps(extended_summary, indent=2, sort_keys=True))

    # Check for regressions
    baseline_path = ROOT / args.baseline
    regressions = []
    baseline = None
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
        reporter.write_report(output_path, baseline)
        print(f"\nReport written to {output_path}")

    # Set baseline if requested
    if args.set_baseline:
        report = reporter.generate_report()
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"\nBaseline set at {baseline_path}")

    # Exit code
    failures = [r for r in results if not r["passed"]]
    if failures:
        return 1
    if args.fail_on_slow and slow_results:
        return 1
    if args.fail_on_llm and llm_results:
        return 1
    if args.fail_on_regression and regressions:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
