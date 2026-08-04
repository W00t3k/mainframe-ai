#!/usr/bin/env python3
"""
Interactive z/OS Book Server
A standalone app for learning mainframe concepts with hands-on practice.
"""

import json
import os
import re
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.request
import urllib.parse

PORT = 8888
BOOK_DIR = Path(__file__).parent
CHAPTERS_DIR = BOOK_DIR / "chapters"
BIGIRON_API = "http://localhost:8080/api"  # Main app API
TK5_WS = "ws://localhost:8080/ws/terminal"  # Terminal WebSocket


def load_chapter(slug):
    """Load a chapter markdown file."""
    path = CHAPTERS_DIR / f"{slug}.md"
    if not path.exists():
        return None
    return path.read_text()


def list_chapters():
    """List all available chapters in order."""
    chapters = []
    for f in sorted(CHAPTERS_DIR.glob("*.md")):
        content = f.read_text()
        # Extract title from first # heading
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else f.stem
        chapters.append({
            "slug": f.stem,
            "title": title,
            "path": f"/chapter/{f.stem}"
        })
    return chapters


class BookHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.serve_index()
        elif self.path.startswith("/chapter/"):
            slug = self.path.split("/chapter/")[1].split("?")[0]
            self.serve_chapter(slug)
        elif self.path == "/api/chapters":
            self.serve_json(list_chapters())
        elif self.path.startswith("/static/"):
            super().do_GET()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/ask":
            # Proxy to BigIron AI
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            self.proxy_to_bigiron("/api/chat", body)
        else:
            self.send_error(404)

    def serve_index(self):
        chapters = list_chapters()
        html = self.render_template("index.html", {
            "chapters": chapters,
            "title": "Interactive z/OS Book"
        })
        self.send_html(html)

    def serve_chapter(self, slug):
        content = load_chapter(slug)
        if not content:
            self.send_error(404, f"Chapter '{slug}' not found")
            return

        chapters = list_chapters()
        current_idx = next((i for i, c in enumerate(chapters) if c["slug"] == slug), 0)
        prev_chapter = chapters[current_idx - 1] if current_idx > 0 else None
        next_chapter = chapters[current_idx + 1] if current_idx < len(chapters) - 1 else None

        html = self.render_template("chapter.html", {
            "content": content,
            "chapters": chapters,
            "current": slug,
            "prev": prev_chapter,
            "next": next_chapter,
            "tk5_ws": TK5_WS
        })
        self.send_html(html)

    def serve_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def send_html(self, html):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def render_template(self, name, ctx):
        path = BOOK_DIR / "templates" / name
        if not path.exists():
            return f"<h1>Template {name} not found</h1>"
        template = path.read_text()
        # Simple mustache-style replacement
        for key, val in ctx.items():
            if isinstance(val, (list, dict)):
                template = template.replace(f"{{{{{key}}}}}", json.dumps(val))
            else:
                template = template.replace(f"{{{{{key}}}}}", str(val or ""))
        return template

    def proxy_to_bigiron(self, path, body):
        try:
            req = urllib.request.Request(
                f"{BIGIRON_API}{path}",
                data=body,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(resp.read())
        except Exception as e:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())


def main():
    os.chdir(BOOK_DIR)
    server = HTTPServer(("0.0.0.0", PORT), BookHandler)
    print(f"""
╔══════════════════════════════════════════════════════════╗
║         Interactive z/OS Book                            ║
╠══════════════════════════════════════════════════════════╣
║  Book:     http://localhost:{PORT}                          ║
║  BigIron:  {BIGIRON_API:<43} ║
║  Terminal: {TK5_WS:<43} ║
╚══════════════════════════════════════════════════════════╝
    """)
    server.serve_forever()


if __name__ == "__main__":
    main()
