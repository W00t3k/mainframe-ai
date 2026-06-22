"""Watch folder for new files and process them."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


class FolderWatcher:
    """Watch a directory for new files and move them to seed dirs."""

    SUPPORTED_FORMATS = {".md", ".txt", ".json"}

    def __init__(
        self,
        watch_dir: Path,
        output_dir: Path,
    ):
        self.watch_dir = watch_dir
        self.output_dir = output_dir
        self.processed_dir = watch_dir / ".processed"

    def _get_pending_files(self) -> list[Path]:
        """Get files pending processing."""
        if not self.watch_dir.exists():
            return []

        pending = []
        for path in self.watch_dir.iterdir():
            if path.is_file() and path.suffix.lower() in self.SUPPORTED_FORMATS:
                pending.append(path)

        return sorted(pending)

    def process_file(self, path: Path) -> dict[str, Any]:
        """Process a single file."""
        if path.suffix.lower() == ".json":
            return self._process_json(path)
        else:
            return self._process_text(path)

    def _process_text(self, path: Path) -> dict[str, Any]:
        """Process markdown or text file."""
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            return {"error": str(e)}

        # Copy to output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / path.name
        output_path.write_text(content, encoding="utf-8")

        # Move original to processed
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(self.processed_dir / path.name))

        return {"processed": str(path.name), "output": str(output_path)}

    def _process_json(self, path: Path) -> dict[str, Any]:
        """Process JSON file with term definitions."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            return {"error": str(e)}

        # Convert JSON to markdown
        lines = [f"# Ingested from {path.name}", f"Date: {datetime.now().isoformat()}", ""]

        if isinstance(data, list):
            for item in data:
                term = item.get("term", "Unknown")
                definition = item.get("definition", "")
                aliases = item.get("aliases", [])
                lines.append(f"### {term}")
                if aliases:
                    lines.append(f"Aliases: {'; '.join(aliases)}")
                lines.append(f"Definition: {definition}")
                lines.append("")
        elif isinstance(data, dict):
            term = data.get("term", "Unknown")
            definition = data.get("definition", "")
            lines.append(f"### {term}")
            lines.append(f"Definition: {definition}")
            lines.append("")

        # Write markdown output
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_name = path.stem + ".md"
        output_path = self.output_dir / output_name
        output_path.write_text("\n".join(lines), encoding="utf-8")

        # Move original to processed
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(self.processed_dir / path.name))

        return {"processed": str(path.name), "output": str(output_path)}

    def process_pending(self) -> dict[str, Any]:
        """Process all pending files."""
        files = self._get_pending_files()
        results = []

        for path in files:
            result = self.process_file(path)
            results.append(result)

        return {
            "files_processed": len(results),
            "results": results,
        }
