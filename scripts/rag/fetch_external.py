#!/usr/bin/env python3
"""Fetch content from external URLs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.data_pipeline.external_fetcher import ExternalFetcher


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch external content.")
    parser.add_argument(
        "--config",
        default="configs/fetch_sources.yaml",
        help="Fetch sources config.",
    )
    parser.add_argument(
        "--url",
        help="Fetch a specific URL (overrides config).",
    )
    parser.add_argument(
        "--scheduled",
        action="store_true",
        help="Fetch all scheduled/auto sources from config.",
    )
    parser.add_argument(
        "--no-review",
        action="store_true",
        help="Index immediately without review.",
    )
    args = parser.parse_args()

    fetcher = ExternalFetcher(
        ROOT / args.config,
        ROOT / "data" / "rag_seed" / "external",
    )

    if args.url:
        result = fetcher.fetch_url(args.url, review=not args.no_review)
        print(json.dumps(result, indent=2))
    elif args.scheduled:
        results = fetcher.fetch_all_scheduled()
        print(json.dumps(results, indent=2))
    else:
        print("Specify --url or --scheduled")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
