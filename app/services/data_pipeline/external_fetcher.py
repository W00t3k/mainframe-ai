"""Fetch content from external URLs."""

from __future__ import annotations

import hashlib
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


class ExternalFetcher:
    """Fetch and process content from configured external URLs."""

    def __init__(
        self,
        config_path: Path,
        output_dir: Path,
        pending_dir: Path | None = None,
    ):
        self.config_path = config_path
        self.output_dir = output_dir
        self.pending_dir = pending_dir or (output_dir.parent / "pending" / "external")

    def _load_config(self) -> dict[str, Any]:
        """Load fetch sources config."""
        if not _HAS_YAML:
            return {"sources": []}
        if not self.config_path.exists():
            return {"sources": []}
        try:
            return yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        except Exception:
            return {"sources": []}

    def get_sources(self) -> list[dict[str, Any]]:
        """Get list of configured sources."""
        config = self._load_config()
        return config.get("sources", [])

    def fetch_url(self, url: str, review: bool = True) -> dict[str, Any]:
        """Fetch content from a URL."""
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                content = response.read().decode("utf-8", errors="replace")
        except Exception as e:
            return {"error": str(e), "url": url}

        # Extract text content (basic HTML stripping)
        text = self._strip_html(content)

        # Generate filename from URL
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        filename = f"external_{url_hash}.md"

        # Format as markdown
        lines = [
            f"# External Content",
            f"Source URL: {url}",
            f"Fetch Date: {datetime.now().isoformat()}",
            "",
            "---",
            "",
            text[:10000],  # Limit content length
        ]
        content_md = "\n".join(lines)

        # Write to appropriate directory
        if review:
            self.pending_dir.mkdir(parents=True, exist_ok=True)
            output_path = self.pending_dir / filename
        else:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            output_path = self.output_dir / filename

        output_path.write_text(content_md, encoding="utf-8")

        return {
            "url": url,
            "output": str(output_path),
            "review_required": review,
            "content_length": len(text),
        }

    def _strip_html(self, html: str) -> str:
        """Basic HTML to text conversion."""
        # Remove script and style elements
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.I)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.I)
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Decode common entities
        text = text.replace("&nbsp;", " ").replace("&amp;", "&")
        text = text.replace("&lt;", "<").replace("&gt;", ">")
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def fetch_all_scheduled(self) -> list[dict[str, Any]]:
        """Fetch all sources marked as 'scheduled' or 'auto'."""
        sources = self.get_sources()
        results = []

        for source in sources:
            mode = source.get("mode", "on-demand")
            if mode in ("scheduled", "auto"):
                review = source.get("review", True)
                result = self.fetch_url(source["url"], review=review)
                results.append(result)

        return results
