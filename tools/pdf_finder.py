#!/usr/bin/env python3
"""
PDF Finder for Mainframe Documentation

Searches multiple sources for IBM mainframe documentation:
- bitsavers.org (vintage IBM docs)
- archive.org (Internet Archive)
- IBM Redbooks (via existing scraper)

Usage:
    python pdf_finder.py search "MVS 3.8"
    python pdf_finder.py search "RACF administration"
    python pdf_finder.py search "JCL reference"
    python pdf_finder.py download <url> [--output <path>]
    python pdf_finder.py list-sources
"""

import os
import sys
import re
import json
import time
import argparse
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, quote_plus
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Directories
DATA_DIR = PROJECT_ROOT / "data" / "redbooks"
DOWNLOADS_DIR = DATA_DIR / "downloads"
CACHE_DIR = DATA_DIR / ".cache"

# Create directories
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# HTTP settings
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}
REQUEST_DELAY = 0.5


# =============================================================================
# Source Definitions
# =============================================================================

SOURCES = {
    "bitsavers": {
        "name": "Bitsavers.org",
        "description": "Vintage IBM documentation archive (1970s-1990s)",
        "base_url": "https://bitsavers.org/pdf/ibm",
        "categories": {
            "370": "System/370 architecture and MVS",
            "370/MVS": "MVS operating system",
            "370/MVS_XA": "MVS/XA extended architecture",
            "370/MVS_ESA": "MVS/ESA enterprise systems",
            "370/OS_VS2": "OS/VS2 (predecessor to MVS)",
            "370/TSO_Extensions": "TSO extensions",
            "370/ISPF": "ISPF panels and dialogs",
            "370/RACF": "RACF security",
            "370/JES2": "JES2 job entry subsystem",
            "370/JES3": "JES3 job entry subsystem",
            "370/CICS": "CICS transaction processing",
            "370/CICS_MVS": "CICS for MVS",
            "370/VTAM": "VTAM networking",
            "370/SNA": "SNA networking architecture",
            "370/IMS": "IMS database/transaction manager",
            "370/VM": "VM/CMS",
            "370/VSE": "VSE/ESA",
            "mainframe": "General mainframe docs",
            "3270": "3270 terminals",
        }
    },
    "archive_org": {
        "name": "Internet Archive",
        "description": "Archive.org IBM documentation collection",
        "search_url": "https://archive.org/advancedsearch.php",
    },
    "ibm_redbooks": {
        "name": "IBM Redbooks",
        "description": "Official IBM Redbooks (current)",
        "base_url": "https://www.redbooks.ibm.com",
    }
}

# Common search terms mapping
SEARCH_ALIASES = {
    "mvs": ["MVS", "OS/VS2", "OS VS2", "z/OS"],
    "mvs38": ["MVS 3.8", "MVS Release 3.8", "MVS/370", "MVS_SP"],
    "mvs380": ["MVS 3.8", "MVS Release 3.8", "MVS/370"],
    "racf": ["RACF", "Resource Access Control", "Security Server"],
    "jcl": ["JCL", "Job Control Language"],
    "tso": ["TSO", "Time Sharing Option", "TSO Extensions"],
    "ispf": ["ISPF", "Interactive System Productivity"],
    "cics": ["CICS", "Customer Information Control"],
    "vtam": ["VTAM", "Virtual Telecommunications"],
    "jes": ["JES2", "JES3", "Job Entry Subsystem"],
    "cobol": ["COBOL", "VS COBOL", "COBOL II"],
    "assembler": ["Assembler", "HLASM", "BAL"],
    "db2": ["DB2", "Database 2"],
    "ims": ["IMS", "Information Management System"],
    "sna": ["SNA", "Systems Network Architecture"],
    "dasd": ["DASD", "3380", "3390", "Direct Access"],
    "abend": ["ABEND", "abnormal end", "system codes"],
}


def normalize_search(query: str) -> List[str]:
    """Expand search query with aliases"""
    terms = [query]
    query_lower = query.lower().replace(" ", "")

    for alias, expansions in SEARCH_ALIASES.items():
        if alias in query_lower or query_lower in alias:
            terms.extend(expansions)

    return list(set(terms))


# =============================================================================
# Bitsavers Search
# =============================================================================

class BitsaversSearch:
    """Search bitsavers.org for IBM documentation"""

    BASE_URL = "https://bitsavers.org/pdf/ibm"

    def __init__(self):
        self.cache = {}

    def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch page with caching"""
        cache_key = hashlib.md5(url.encode()).hexdigest()
        cache_file = CACHE_DIR / f"bitsavers_{cache_key}.html"

        # Check cache (24h TTL)
        if cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age < 86400:  # 24 hours
                return cache_file.read_text()

        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            time.sleep(REQUEST_DELAY)

            # Save to cache
            cache_file.write_text(r.text)
            return r.text
        except Exception as e:
            print(f"  Error fetching {url}: {e}")
            return None

    def list_directory(self, path: str = "") -> List[Dict]:
        """List files and directories in a bitsavers path"""
        url = f"{self.BASE_URL}/{path}" if path else self.BASE_URL
        if not url.endswith("/"):
            url += "/"

        html = self._fetch_page(url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        items = []

        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Skip parent directory and non-relevant links
            if href in ["../", "/", "?"] or href.startswith("http"):
                continue

            is_dir = href.endswith("/")
            name = href.rstrip("/")

            items.append({
                "name": name,
                "href": href,
                "url": urljoin(url, href),
                "is_dir": is_dir,
                "is_pdf": href.lower().endswith(".pdf"),
                "path": f"{path}/{name}" if path else name
            })

        return items

    def search(self, query: str, max_results: int = 50) -> List[Dict]:
        """Search for PDFs matching query"""
        results = []
        search_terms = normalize_search(query)

        # Categories to search based on query
        categories_to_search = ["370", "370/MVS", "370/MVS_XA", "370/MVS_ESA",
                                "370/TSO_Extensions", "370/ISPF", "370/RACF",
                                "370/JES2", "370/JES3", "370/CICS", "370/VTAM"]

        # Add specific categories based on query
        query_lower = query.lower()
        if "racf" in query_lower:
            categories_to_search.insert(0, "370/RACF")
        if "cics" in query_lower:
            categories_to_search.insert(0, "370/CICS")
            categories_to_search.insert(1, "370/CICS_MVS")
        if "vtam" in query_lower or "sna" in query_lower:
            categories_to_search.insert(0, "370/VTAM")
            categories_to_search.insert(1, "370/SNA")
        if "jes" in query_lower:
            categories_to_search.insert(0, "370/JES2")
            categories_to_search.insert(1, "370/JES3")
        if "tso" in query_lower:
            categories_to_search.insert(0, "370/TSO_Extensions")
        if "ispf" in query_lower:
            categories_to_search.insert(0, "370/ISPF")

        print(f"Searching bitsavers.org for: {query}")
        print(f"  Search terms: {', '.join(search_terms[:5])}")

        for category in categories_to_search:
            if len(results) >= max_results:
                break

            print(f"  Scanning {category}...")
            items = self.list_directory(category)

            for item in items:
                if not item["is_pdf"]:
                    continue

                # Check if filename matches any search term
                name_lower = item["name"].lower().replace("_", " ")
                matched = False
                match_score = 0

                for term in search_terms:
                    term_lower = term.lower()
                    if term_lower in name_lower:
                        matched = True
                        match_score += 10
                    # Partial match
                    elif any(t in name_lower for t in term_lower.split()):
                        matched = True
                        match_score += 5

                if matched:
                    results.append({
                        "source": "bitsavers",
                        "title": item["name"].replace("_", " ").replace(".pdf", ""),
                        "filename": item["name"],
                        "url": item["url"],
                        "category": category,
                        "score": match_score
                    })

        # Sort by relevance
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:max_results]


# =============================================================================
# Archive.org Search
# =============================================================================

class ArchiveOrgSearch:
    """Search archive.org for IBM mainframe documentation"""

    SEARCH_URL = "https://archive.org/advancedsearch.php"

    def search(self, query: str, max_results: int = 30) -> List[Dict]:
        """Search archive.org for IBM mainframe docs"""
        results = []

        # Build search query - focus on IBM mainframe docs
        search_query = f'({query}) AND (IBM OR mainframe OR MVS OR "z/OS") AND mediatype:texts'

        params = {
            "q": search_query,
            "fl[]": ["identifier", "title", "description", "year", "format"],
            "rows": max_results,
            "page": 1,
            "output": "json"
        }

        print(f"Searching archive.org for: {query}")

        try:
            r = requests.get(self.SEARCH_URL, params=params, headers=HEADERS, timeout=30)
            r.raise_for_status()
            data = r.json()

            for doc in data.get("response", {}).get("docs", []):
                identifier = doc.get("identifier", "")
                title = doc.get("title", identifier)
                year = doc.get("year", "")

                # Filter to likely relevant results
                title_lower = title.lower()
                if not any(kw in title_lower for kw in
                          ["ibm", "mvs", "mainframe", "z/os", "cobol", "jcl",
                           "racf", "cics", "vsam", "tso", "ispf", "jes"]):
                    continue

                results.append({
                    "source": "archive.org",
                    "title": title,
                    "identifier": identifier,
                    "url": f"https://archive.org/details/{identifier}",
                    "download_url": f"https://archive.org/download/{identifier}",
                    "year": year,
                    "description": doc.get("description", "")[:200] if doc.get("description") else ""
                })

        except Exception as e:
            print(f"  Error searching archive.org: {e}")

        return results


# =============================================================================
# Download Manager
# =============================================================================

class DownloadManager:
    """Download and manage PDF files"""

    def __init__(self):
        self.log_file = DATA_DIR / "downloads_log.json"
        self.log = self._load_log()

    def _load_log(self) -> Dict:
        if self.log_file.exists():
            return json.loads(self.log_file.read_text())
        return {"downloads": {}, "failed": {}}

    def _save_log(self):
        self.log_file.write_text(json.dumps(self.log, indent=2))

    def download(self, url: str, filename: str = None) -> Tuple[bool, str]:
        """Download a PDF file"""
        if not filename:
            filename = url.split("/")[-1]
            if not filename.endswith(".pdf"):
                filename += ".pdf"

        # Sanitize filename
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        dest_path = DOWNLOADS_DIR / filename

        # Check if already downloaded
        if url in self.log.get("downloads", {}):
            existing_path = self.log["downloads"][url].get("path")
            if existing_path and Path(existing_path).exists():
                return True, f"Already downloaded: {existing_path}"

        print(f"Downloading: {filename}")
        print(f"  From: {url}")

        try:
            with requests.get(url, headers=HEADERS, stream=True, timeout=120) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))

                with open(dest_path, 'wb') as f:
                    downloaded = 0
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                pct = (downloaded / total_size) * 100
                                print(f"\r  Progress: {pct:.1f}% ({downloaded // 1024}KB)", end="", flush=True)

                print()  # newline

                self.log["downloads"][url] = {
                    "path": str(dest_path),
                    "filename": filename,
                    "size": downloaded,
                    "downloaded_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                self._save_log()

                return True, str(dest_path)

        except Exception as e:
            self.log["failed"][url] = {
                "error": str(e),
                "attempted_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            self._save_log()
            return False, str(e)


# =============================================================================
# Combined Search
# =============================================================================

def search_all_sources(query: str, max_per_source: int = 20) -> Dict[str, List[Dict]]:
    """Search all sources for a query"""
    results = {}

    # Bitsavers
    bs = BitsaversSearch()
    results["bitsavers"] = bs.search(query, max_results=max_per_source)

    # Archive.org
    ao = ArchiveOrgSearch()
    results["archive_org"] = ao.search(query, max_results=max_per_source)

    return results


def print_search_results(results: Dict[str, List[Dict]]):
    """Pretty print search results"""
    total = sum(len(r) for r in results.values())
    print(f"\n{'='*60}")
    print(f"Found {total} results")
    print('='*60)

    for source, items in results.items():
        if not items:
            continue

        source_info = SOURCES.get(source, {"name": source})
        print(f"\n[{source_info.get('name', source)}] ({len(items)} results)")
        print("-" * 40)

        for i, item in enumerate(items[:10], 1):
            title = item.get("title", "Unknown")[:60]
            url = item.get("url", "")
            year = item.get("year", "")
            category = item.get("category", "")

            print(f"  {i}. {title}")
            if year:
                print(f"     Year: {year}")
            if category:
                print(f"     Category: {category}")
            print(f"     URL: {url}")

        if len(items) > 10:
            print(f"  ... and {len(items) - 10} more")


# =============================================================================
# CLI
# =============================================================================

def cmd_search(args):
    """Search for PDFs"""
    query = " ".join(args.query)
    results = search_all_sources(query, max_per_source=args.limit)
    print_search_results(results)

    # Optionally save results
    if args.output:
        output_file = Path(args.output)
        output_file.write_text(json.dumps(results, indent=2))
        print(f"\nResults saved to: {output_file}")


def cmd_download(args):
    """Download a PDF"""
    dm = DownloadManager()
    success, msg = dm.download(args.url, args.output)
    if success:
        print(f"Success: {msg}")
    else:
        print(f"Failed: {msg}")


def cmd_list_sources(args):
    """List available sources"""
    print("\nAvailable PDF Sources:")
    print("=" * 60)

    for key, source in SOURCES.items():
        print(f"\n[{key}] {source['name']}")
        print(f"  {source['description']}")

        if "categories" in source:
            print("  Categories:")
            for cat, desc in list(source["categories"].items())[:5]:
                print(f"    - {cat}: {desc}")
            if len(source["categories"]) > 5:
                print(f"    ... and {len(source['categories']) - 5} more")


def cmd_browse(args):
    """Browse bitsavers categories"""
    bs = BitsaversSearch()
    path = args.path or ""

    print(f"\nBrowsing: bitsavers.org/pdf/ibm/{path}")
    print("-" * 60)

    items = bs.list_directory(path)

    dirs = [i for i in items if i["is_dir"]]
    pdfs = [i for i in items if i["is_pdf"]]

    if dirs:
        print("\nDirectories:")
        for d in dirs[:20]:
            print(f"  [DIR] {d['name']}")
        if len(dirs) > 20:
            print(f"  ... and {len(dirs) - 20} more")

    if pdfs:
        print(f"\nPDF Files ({len(pdfs)}):")
        for p in pdfs[:20]:
            print(f"  {p['name']}")
        if len(pdfs) > 20:
            print(f"  ... and {len(pdfs) - 20} more")


def main():
    parser = argparse.ArgumentParser(
        description="Search and download mainframe documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Search command
    sp_search = subparsers.add_parser("search", help="Search for PDFs")
    sp_search.add_argument("query", nargs="+", help="Search query")
    sp_search.add_argument("--limit", "-l", type=int, default=20, help="Max results per source")
    sp_search.add_argument("--output", "-o", help="Save results to JSON file")

    # Download command
    sp_download = subparsers.add_parser("download", help="Download a PDF")
    sp_download.add_argument("url", help="URL to download")
    sp_download.add_argument("--output", "-o", help="Output filename")

    # List sources
    sp_sources = subparsers.add_parser("list-sources", help="List available sources")

    # Browse bitsavers
    sp_browse = subparsers.add_parser("browse", help="Browse bitsavers directories")
    sp_browse.add_argument("path", nargs="?", default="", help="Path to browse (e.g., 370/MVS)")

    args = parser.parse_args()

    if args.command == "search":
        cmd_search(args)
    elif args.command == "download":
        cmd_download(args)
    elif args.command == "list-sources":
        cmd_list_sources(args)
    elif args.command == "browse":
        cmd_browse(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
