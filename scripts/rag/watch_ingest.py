#!/usr/bin/env python3
"""Watch ingest folder for new files."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.data_pipeline.folder_watcher import FolderWatcher


def main() -> int:
    parser = argparse.ArgumentParser(description="Watch folder for new files to ingest.")
    parser.add_argument(
        "--watch-dir",
        default="data/rag_ingest",
        help="Directory to watch.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/rag_seed/ingested",
        help="Directory for processed files.",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run continuously, polling every 10 seconds.",
    )
    args = parser.parse_args()

    watcher = FolderWatcher(
        ROOT / args.watch_dir,
        ROOT / args.output_dir,
    )

    if args.daemon:
        print(f"Watching {args.watch_dir} for new files...")
        while True:
            result = watcher.process_pending()
            if result["files_processed"] > 0:
                print(json.dumps(result, indent=2))
            time.sleep(10)
    else:
        result = watcher.process_pending()
        print(json.dumps(result, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
