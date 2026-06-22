#!/usr/bin/env python3
"""Generate prioritized backlog from query misses."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.seed_index.tracker import QueryMissTracker
from app.services.seed_index.fuzzy import normalize


def generate_backlog(
    misses: list[dict],
    high_min: int = 10,
    med_min: int = 5,
) -> str:
    """Generate markdown backlog from misses."""
    # Normalize and count queries
    counter: Counter[str] = Counter()
    samples: dict[str, list[str]] = {}

    for miss in misses:
        query = miss.get("query", "")
        normalized = normalize(query)
        if not normalized:
            continue

        counter[normalized] += 1
        if normalized not in samples:
            samples[normalized] = []
        if len(samples[normalized]) < 3 and query not in samples[normalized]:
            samples[normalized].append(query)

    # Build markdown
    lines = [
        "# Seed Content Backlog",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d')}",
        "",
    ]

    # High priority
    high = [(term, count) for term, count in counter.items() if count >= high_min]
    high.sort(key=lambda x: -x[1])

    lines.append(f"## High Priority ({high_min}+ queries)")
    lines.append("")
    if high:
        lines.append("| Term | Query Count | Sample Queries |")
        lines.append("|------|-------------|----------------|")
        for term, count in high:
            sample_str = ", ".join(f'"{s}"' for s in samples.get(term, [])[:2])
            lines.append(f"| {term} | {count} | {sample_str} |")
    else:
        lines.append("No high-priority terms.")
    lines.append("")

    # Medium priority
    med = [(term, count) for term, count in counter.items() if med_min <= count < high_min]
    med.sort(key=lambda x: -x[1])

    lines.append(f"## Medium Priority ({med_min}-{high_min-1} queries)")
    lines.append("")
    if med:
        lines.append("| Term | Query Count | Sample Queries |")
        lines.append("|------|-------------|----------------|")
        for term, count in med:
            sample_str = ", ".join(f'"{s}"' for s in samples.get(term, [])[:2])
            lines.append(f"| {term} | {count} | {sample_str} |")
    else:
        lines.append("No medium-priority terms.")
    lines.append("")

    # Low priority
    low = [(term, count) for term, count in counter.items() if 2 <= count < med_min]
    low.sort(key=lambda x: -x[1])

    lines.append(f"## Low Priority (2-{med_min-1} queries)")
    lines.append("")
    if low:
        lines.append("| Term | Query Count | Sample Queries |")
        lines.append("|------|-------------|----------------|")
        for term, count in low[:20]:  # Limit to 20
            sample_str = ", ".join(f'"{s}"' for s in samples.get(term, [])[:2])
            lines.append(f"| {term} | {count} | {sample_str} |")
    else:
        lines.append("No low-priority terms.")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate backlog from query misses.")
    parser.add_argument(
        "--input",
        default="data/reference/query_misses.jsonl",
        help="Query misses log file.",
    )
    parser.add_argument(
        "--output",
        default="data/rag_seed/TODO.md",
        help="Output backlog file.",
    )
    parser.add_argument("--high-min", type=int, default=10)
    parser.add_argument("--med-min", type=int, default=5)
    args = parser.parse_args()

    log_path = ROOT / args.input
    if not log_path.exists():
        print(f"No query misses log found at {log_path}")
        return 0

    tracker = QueryMissTracker(log_path)
    misses = tracker.get_misses()

    if not misses:
        print("No query misses to process.")
        return 0

    backlog = generate_backlog(misses, args.high_min, args.med_min)

    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(backlog, encoding="utf-8")

    print(f"Backlog written to {output_path}")
    print(f"Processed {len(misses)} query misses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
