#!/usr/bin/env python3
"""Build the fast direct-answer seed index from data/rag_seed files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.mainframe_seed import get_seed_index_stats, write_seed_index  # noqa: E402


def load_abbreviations(config_path: Path) -> dict[str, str]:
    """Load abbreviations from YAML config."""
    if not _HAS_YAML:
        return {}
    if not config_path.exists():
        return {}
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        return data.get("abbreviations", {})
    except Exception:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build data/reference/seed_index.json from RAG seed docs.")
    parser.add_argument(
        "--output",
        default="data/reference/seed_index.json",
        help="Output JSON index path.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check whether the existing index is present and current.",
    )
    parser.add_argument(
        "--fuzzy",
        action="store_true",
        help="Build the fuzzy index (seed_index_fuzzy.json) with typo tolerance.",
    )
    parser.add_argument(
        "--config",
        default="configs/seed_config.yaml",
        help="Path to seed config YAML.",
    )
    args = parser.parse_args()

    if args.fuzzy:
        # Build fuzzy index
        from app.services.seed_index.builder import write_fuzzy_index

        abbrev_path = ROOT / "configs" / "abbreviations.yaml"
        abbreviations = load_abbreviations(abbrev_path)

        seed_dir = ROOT / "data" / "rag_seed"
        output_path = ROOT / "data" / "reference" / "seed_index_fuzzy.json"

        result = write_fuzzy_index(seed_dir, output_path, abbreviations)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if args.check:
        stats = get_seed_index_stats()
        print(json.dumps(stats, indent=2, sort_keys=True))
        return 0 if stats["exists"] and stats["current"] else 1

    result = write_seed_index(ROOT / args.output)
    stats = get_seed_index_stats()
    print(json.dumps({**result, "current": stats["current"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
