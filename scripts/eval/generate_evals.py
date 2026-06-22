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
