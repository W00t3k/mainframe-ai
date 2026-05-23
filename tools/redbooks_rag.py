#!/usr/bin/env python3
"""
IBM Redbooks RAG Builder

Downloads IBM Redbooks PDFs and builds a vector database for RAG queries.
Integrates with the existing rag_engine.py for embeddings and search.

Usage:
    # Scrape and build manifest
    python redbooks_rag.py scrape

    # Download PDFs (filtered by keywords)
    python redbooks_rag.py download [--limit 10]

    # Ingest downloaded PDFs into RAG
    python redbooks_rag.py ingest [--limit 10]

    # Full pipeline: scrape -> download -> ingest
    python redbooks_rag.py build [--limit 10]

    # Query the RAG
    python redbooks_rag.py query "What is RACF?"

    # List indexed documents
    python redbooks_rag.py list

    # Stats
    python redbooks_rag.py stats
"""

import os
import sys
import json
import re
import time
import asyncio
import argparse
import hashlib
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from tools.rag_engine import get_rag_engine, RAGEngine
except ImportError:
    from rag_engine import get_rag_engine, RAGEngine


# =============================================================================
# Configuration
# =============================================================================

BASE_URL = "https://www.redbooks.ibm.com"

# Domain URLs to scrape
DOMAIN_URLS = [
    "https://www.redbooks.ibm.com/domains/zsystems",
    "https://www.redbooks.ibm.com/domains/zsoftware",
    "https://www.redbooks.ibm.com/domains/security",
    "https://www.redbooks.ibm.com/domains/storage",
]

# Directories
DATA_DIR = PROJECT_ROOT / "data" / "redbooks"
PDFS_DIR = DATA_DIR / "pdfs"
MANIFEST_FILE = DATA_DIR / "manifest.jsonl"
DOWNLOAD_LOG = DATA_DIR / "download_log.json"

# Create directories
DATA_DIR.mkdir(parents=True, exist_ok=True)
PDFS_DIR.mkdir(parents=True, exist_ok=True)

# HTTP settings
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
REQUEST_DELAY = 1.0  # Seconds between requests
MAX_RETRIES = 3
DOWNLOAD_TIMEOUT = 120  # seconds

# Keywords for filtering relevant documents
KEYWORDS = [
    # z/OS core
    "z/os", "zos", "ibm z", "mainframe", "mvs", "os/390", "mvs/esa", "mvs/xa",
    # Security
    "racf", "security", "zsecure", "audit", "encryption", "compliance", "saf",
    # Transaction processing
    "cics", "ims", "transaction", "tpns",
    # Job processing
    "jes", "jes2", "jes3", "jcl", "batch", "initiator",
    # Networking & terminals
    "vtam", "tcp/ip", "tn3270", "sna", "ncp", "3270", "lu6.2", "appc",
    # Development
    "tso", "ispf", "cobol", "assembler", "rexx", "clist", "hlasm",
    # Database
    "db2", "vsam", "dataset", "data set", "catalog", "sms",
    # Systems management
    "sysplex", "gdps", "parallel sysplex", "workload", "wlm", "rmf",
    # Storage
    "dasd", "tape", "sms", "dfsms", "dfhsm", "3390", "3380",
    # Classic/Architecture
    "abcs", "system programming", "cross memory", "address space",
    "supervisor", "nucleus", "csect", "linkage editor",
]


# =============================================================================
# Utilities
# =============================================================================

def normalize_text(s: str) -> str:
    """Normalize whitespace in text."""
    return re.sub(r"\s+", " ", s or "").strip()


def safe_filename(name: str, max_len: int = 100) -> str:
    """Create a safe filename from a string."""
    # Remove/replace problematic characters
    safe = re.sub(r'[<>:"/\\|?*]', '', name)
    safe = re.sub(r'\s+', '_', safe)
    safe = safe[:max_len]
    return safe


def fetch_page(url: str, retries: int = MAX_RETRIES) -> Optional[str]:
    """Fetch a page with retry logic."""
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            time.sleep(REQUEST_DELAY)
            return r.text
        except requests.RequestException as e:
            if attempt < retries - 1:
                wait = (attempt + 1) * 2
                print(f"  Retry {attempt + 1}/{retries} in {wait}s: {e}")
                time.sleep(wait)
            else:
                print(f"  Failed after {retries} attempts: {e}")
                return None
    return None


def download_file(url: str, dest_path: Path, retries: int = MAX_RETRIES) -> Tuple[bool, str]:
    """Download a file with retry logic and progress."""
    for attempt in range(retries):
        try:
            with requests.get(url, headers=HEADERS, stream=True, timeout=DOWNLOAD_TIMEOUT) as r:
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
                                print(f"\r  Downloading: {pct:.1f}% ({downloaded // 1024}KB)", end="", flush=True)

                print()  # newline after progress
                time.sleep(REQUEST_DELAY)
                return True, f"Downloaded {downloaded // 1024}KB"

        except requests.RequestException as e:
            if attempt < retries - 1:
                wait = (attempt + 1) * 2
                print(f"\n  Retry {attempt + 1}/{retries} in {wait}s: {e}")
                time.sleep(wait)
            else:
                return False, str(e)

    return False, "Max retries exceeded"


# =============================================================================
# Scraper
# =============================================================================

class RedbooksScraper:
    """Scrapes IBM Redbooks website for mainframe-related documents."""

    def __init__(self):
        self.seen_urls = set()
        self.records = []

    def extract_abstract_links(self, domain_html: str, domain_url: str) -> List[str]:
        """Extract abstract page links from a domain page."""
        soup = BeautifulSoup(domain_html, "html.parser")
        links = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/abstracts/" in href and href.endswith(".html"):
                full_url = urljoin(domain_url, href)
                links.add(full_url)

        return sorted(links)

    def parse_abstract_page(self, url: str) -> Optional[Dict]:
        """Parse an abstract page for document metadata."""
        html = fetch_page(url)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text("\n")

        # Extract title
        title_el = soup.find(["h1", "h2"])
        title = normalize_text(title_el.get_text()) if title_el else ""

        # Find PDF URL
        pdf_url = None
        for a in soup.find_all("a", href=True):
            href = a["href"]
            label = normalize_text(a.get_text()).lower()
            if href.lower().endswith(".pdf") or ".pdf" in href.lower() or "pdf" in label:
                pdf_url = urljoin(url, href)
                break

        # Extract metadata
        published = None
        m = re.search(r"Published\s+(?:on\s+)?(.+?)(?:,|\n|$)", text, re.IGNORECASE)
        if m:
            published = normalize_text(m.group(1))[:50]

        form_number = None
        m = re.search(r"(?:IBM\s+)?Form\s*#?:?\s*([A-Z0-9\-]+)", text, re.IGNORECASE)
        if m:
            form_number = m.group(1)

        # Extract abstract
        abstract = ""
        h = soup.find(string=re.compile(r"^\s*Abstract\s*$", re.IGNORECASE))
        if h:
            parent = h.parent
            chunks = []
            for sib in parent.find_all_next():
                if sib.name and sib.name.lower() in ["h2", "h3"]:
                    heading_text = sib.get_text(" ").lower()
                    if any(x in heading_text for x in ["table of contents", "authors", "related"]):
                        break
                if sib.name in ["p", "li"]:
                    chunks.append(normalize_text(sib.get_text(" ")))
            abstract = normalize_text(" ".join(chunks))[:2000]  # Limit abstract length

        # Score by keywords
        full_text = normalize_text(soup.get_text(" ")).lower()
        score_blob = f"{title} {abstract} {full_text}".lower()
        matched_keywords = [k for k in KEYWORDS if k in score_blob]

        # Calculate relevance score
        relevance_score = len(matched_keywords)

        return {
            "title": title,
            "abstract_url": url,
            "pdf_url": pdf_url,
            "published": published,
            "form_number": form_number,
            "abstract": abstract,
            "matched_keywords": matched_keywords,
            "relevance_score": relevance_score,
            "should_download": relevance_score >= 2,  # At least 2 keyword matches
            "scraped_at": datetime.now().isoformat(),
        }

    def scrape_all(self, domain_urls: List[str] = None) -> List[Dict]:
        """Scrape all domains for Redbooks metadata."""
        if domain_urls is None:
            domain_urls = DOMAIN_URLS

        self.records = []
        self.seen_urls = set()

        for domain_url in domain_urls:
            print(f"\n[*] Scraping domain: {domain_url}")
            html = fetch_page(domain_url)
            if not html:
                print(f"  Failed to fetch domain page")
                continue

            links = self.extract_abstract_links(html, domain_url)
            print(f"  Found {len(links)} abstract links")

            for i, link in enumerate(links, 1):
                if link in self.seen_urls:
                    continue
                self.seen_urls.add(link)

                print(f"  [{i}/{len(links)}] Parsing: {link}")
                rec = self.parse_abstract_page(link)
                if rec:
                    self.records.append(rec)
                    kw_str = ", ".join(rec["matched_keywords"][:3])
                    dl_mark = "✓" if rec["should_download"] else "✗"
                    print(f"    {dl_mark} {rec['title'][:60]}... ({kw_str})")

        # Sort by relevance
        self.records.sort(key=lambda x: x["relevance_score"], reverse=True)

        return self.records

    def save_manifest(self, filepath: Path = None):
        """Save scraped records to manifest file."""
        if filepath is None:
            filepath = MANIFEST_FILE

        with open(filepath, "w", encoding="utf-8") as f:
            for rec in self.records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        print(f"\n[+] Saved {len(self.records)} records to {filepath}")

    @staticmethod
    def load_manifest(filepath: Path = None) -> List[Dict]:
        """Load manifest from file."""
        if filepath is None:
            filepath = MANIFEST_FILE

        if not filepath.exists():
            return []

        records = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return records


# =============================================================================
# Downloader
# =============================================================================

class RedbooksDownloader:
    """Downloads Redbooks PDFs based on manifest."""

    def __init__(self):
        self.download_log = self._load_log()

    def _load_log(self) -> Dict:
        """Load download log."""
        if DOWNLOAD_LOG.exists():
            with open(DOWNLOAD_LOG, "r") as f:
                return json.load(f)
        return {"downloaded": {}, "failed": {}}

    def _save_log(self):
        """Save download log."""
        with open(DOWNLOAD_LOG, "w") as f:
            json.dump(self.download_log, f, indent=2)

    def get_pdf_path(self, record: Dict) -> Path:
        """Generate local PDF path for a record."""
        # Use form number or hash of URL for filename
        if record.get("form_number"):
            name = record["form_number"]
        else:
            name = hashlib.md5(record["abstract_url"].encode()).hexdigest()[:12]

        # Add title snippet
        title_snippet = safe_filename(record.get("title", "")[:40])
        if title_snippet:
            name = f"{name}_{title_snippet}"

        return PDFS_DIR / f"{name}.pdf"

    def download_pdfs(self, records: List[Dict], limit: int = None, force: bool = False) -> Dict:
        """Download PDFs for records marked for download."""
        # Filter to downloadable records
        to_download = [r for r in records if r.get("should_download") and r.get("pdf_url")]

        if limit:
            to_download = to_download[:limit]

        print(f"\n[*] Downloading {len(to_download)} PDFs")

        stats = {"success": 0, "failed": 0, "skipped": 0}

        for i, rec in enumerate(to_download, 1):
            pdf_url = rec["pdf_url"]
            pdf_path = self.get_pdf_path(rec)

            # Skip if already downloaded
            if not force and pdf_path.exists() and pdf_url in self.download_log.get("downloaded", {}):
                print(f"[{i}/{len(to_download)}] Skipped (exists): {rec['title'][:50]}...")
                stats["skipped"] += 1
                continue

            print(f"[{i}/{len(to_download)}] Downloading: {rec['title'][:50]}...")
            print(f"  URL: {pdf_url}")

            success, msg = download_file(pdf_url, pdf_path)

            if success:
                self.download_log["downloaded"][pdf_url] = {
                    "path": str(pdf_path),
                    "title": rec["title"],
                    "downloaded_at": datetime.now().isoformat()
                }
                stats["success"] += 1
                print(f"  ✓ Saved to {pdf_path.name}")
            else:
                self.download_log["failed"][pdf_url] = {
                    "error": msg,
                    "title": rec["title"],
                    "failed_at": datetime.now().isoformat()
                }
                stats["failed"] += 1
                print(f"  ✗ Failed: {msg}")

            self._save_log()

        print(f"\n[+] Download complete: {stats['success']} success, {stats['failed']} failed, {stats['skipped']} skipped")
        return stats


# =============================================================================
# Bitsavers Classic IBM Documentation
# =============================================================================

BITSAVERS_BASE = "https://bitsavers.org/pdf/ibm/370"

# Classic MVS/TSO directories to scrape
BITSAVERS_DIRS = [
    "MVS",
    "MVS_ESA",
    "MVS_XA",
    "ISPF",
    "RACF",
    "TSO_Extensions",
    "OS_VS2",
    "CICS",
    "CICS_MVS",
    "VTAM",
    "SNA",
    "JES2",
    "JES3",
]

CLASSICS_DIR = DATA_DIR / "classics"
CLASSICS_DIR.mkdir(parents=True, exist_ok=True)


class ClassicsDownloader:
    """Downloads classic IBM documentation from bitsavers.org"""

    def __init__(self):
        self.download_log = self._load_log()

    def _load_log(self) -> Dict:
        log_file = DATA_DIR / "classics_log.json"
        if log_file.exists():
            with open(log_file, "r") as f:
                return json.load(f)
        return {"downloaded": {}, "failed": {}}

    def _save_log(self):
        log_file = DATA_DIR / "classics_log.json"
        with open(log_file, "w") as f:
            json.dump(self.download_log, f, indent=2)

    def list_available(self, directories: List[str] = None) -> List[Dict]:
        """List available PDFs from bitsavers."""
        if directories is None:
            directories = BITSAVERS_DIRS

        all_pdfs = []

        for dir_name in directories:
            url = f"{BITSAVERS_BASE}/{dir_name}/"
            print(f"[*] Scanning {dir_name}...")

            try:
                html = fetch_page(url)
                if not html:
                    continue

                soup = BeautifulSoup(html, "html.parser")

                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if href.endswith(".pdf"):
                        pdf_url = f"{BITSAVERS_BASE}/{dir_name}/{href}"
                        title = href.replace("_", " ").replace(".pdf", "")

                        all_pdfs.append({
                            "title": title,
                            "pdf_url": pdf_url,
                            "category": dir_name,
                            "filename": href,
                            "source": "bitsavers"
                        })

            except Exception as e:
                print(f"  Error scanning {dir_name}: {e}")

        print(f"\n[+] Found {len(all_pdfs)} classic PDFs")
        return all_pdfs

    def download(self, limit: int = None, categories: List[str] = None, force: bool = False) -> Dict:
        """Download classic PDFs."""
        pdfs = self.list_available(categories)

        if limit:
            pdfs = pdfs[:limit]

        print(f"\n[*] Downloading {len(pdfs)} classic PDFs")

        stats = {"success": 0, "failed": 0, "skipped": 0}

        for i, pdf in enumerate(pdfs, 1):
            pdf_url = pdf["pdf_url"]
            filename = f"classic_{pdf['category']}_{pdf['filename']}"
            pdf_path = CLASSICS_DIR / filename

            # Skip if exists
            if not force and pdf_path.exists():
                print(f"[{i}/{len(pdfs)}] Skipped (exists): {pdf['title'][:50]}...")
                stats["skipped"] += 1
                continue

            print(f"[{i}/{len(pdfs)}] Downloading: {pdf['title'][:50]}...")

            success, msg = download_file(pdf_url, pdf_path)

            if success:
                self.download_log["downloaded"][pdf_url] = {
                    "path": str(pdf_path),
                    "title": pdf["title"],
                    "category": pdf["category"],
                    "downloaded_at": datetime.now().isoformat()
                }
                stats["success"] += 1
                print(f"  ✓ Saved")
            else:
                self.download_log["failed"][pdf_url] = {
                    "error": msg,
                    "title": pdf["title"],
                    "failed_at": datetime.now().isoformat()
                }
                stats["failed"] += 1
                print(f"  ✗ Failed: {msg}")

            self._save_log()

        print(f"\n[+] Complete: {stats['success']} success, {stats['failed']} failed, {stats['skipped']} skipped")
        return stats


# =============================================================================
# RAG Integration
# =============================================================================

class RedbooksRAG:
    """Integrates downloaded Redbooks with the RAG engine."""

    def __init__(self):
        self.engine = get_rag_engine()

    async def ingest_pdfs(self, limit: int = None, force: bool = False, include_classics: bool = True) -> Dict:
        """Ingest downloaded PDFs into RAG."""
        # Find all PDFs from both directories
        pdf_files = sorted(PDFS_DIR.glob("*.pdf"))

        # Also include classics if available
        if include_classics and CLASSICS_DIR.exists():
            pdf_files.extend(sorted(CLASSICS_DIR.glob("*.pdf")))

        if limit:
            pdf_files = pdf_files[:limit]

        print(f"\n[*] Ingesting {len(pdf_files)} PDFs into RAG")

        stats = {"success": 0, "failed": 0, "skipped": 0}

        for i, pdf_path in enumerate(pdf_files, 1):
            name = pdf_path.stem

            # Check if already indexed
            existing = [d for d in self.engine.documents.values() if d.source == str(pdf_path)]
            if existing and not force:
                print(f"[{i}/{len(pdf_files)}] Skipped (indexed): {name}")
                stats["skipped"] += 1
                continue

            print(f"[{i}/{len(pdf_files)}] Ingesting: {name}")

            try:
                result = await self.engine.add_pdf(str(pdf_path), name)
                if result.get("success"):
                    stats["success"] += 1
                    print(f"  ✓ Added {result.get('chunks', 0)} chunks")
                else:
                    stats["failed"] += 1
                    print(f"  ✗ Failed: {result.get('error', 'Unknown error')}")
            except Exception as e:
                stats["failed"] += 1
                print(f"  ✗ Error: {e}")

        print(f"\n[+] Ingestion complete: {stats['success']} success, {stats['failed']} failed, {stats['skipped']} skipped")
        return stats

    async def query(self, question: str, n_results: int = 5) -> Dict:
        """Query the RAG for mainframe information."""
        result = await self.engine.query(question, n_results=n_results)
        return result

    def list_documents(self) -> List[Dict]:
        """List all indexed documents."""
        return self.engine.get_documents()

    def get_stats(self) -> Dict:
        """Get RAG statistics."""
        stats = self.engine.get_stats()

        # Add Redbooks-specific stats
        pdf_count = len(list(PDFS_DIR.glob("*.pdf")))
        manifest_count = 0
        if MANIFEST_FILE.exists():
            with open(MANIFEST_FILE) as f:
                manifest_count = sum(1 for _ in f)

        stats["redbooks"] = {
            "pdfs_downloaded": pdf_count,
            "manifest_entries": manifest_count,
            "pdfs_dir": str(PDFS_DIR),
        }

        return stats


# =============================================================================
# CLI Interface
# =============================================================================

def cmd_scrape(args):
    """Scrape Redbooks website for document metadata."""
    scraper = RedbooksScraper()
    records = scraper.scrape_all()
    scraper.save_manifest()

    # Summary
    downloadable = sum(1 for r in records if r.get("should_download"))
    print(f"\nSummary:")
    print(f"  Total documents: {len(records)}")
    print(f"  Matching keywords: {downloadable}")
    print(f"  Manifest: {MANIFEST_FILE}")


def cmd_download(args):
    """Download PDFs from manifest."""
    records = RedbooksScraper.load_manifest()
    if not records:
        print("No manifest found. Run 'scrape' first.")
        return

    downloader = RedbooksDownloader()
    downloader.download_pdfs(records, limit=args.limit, force=args.force)


def cmd_ingest(args):
    """Ingest downloaded PDFs into RAG."""
    rag = RedbooksRAG()
    asyncio.run(rag.ingest_pdfs(limit=args.limit, force=args.force))


def cmd_build(args):
    """Full pipeline: scrape -> download -> ingest."""
    print("=" * 60)
    print("STEP 1: Scraping Redbooks website")
    print("=" * 60)
    cmd_scrape(args)

    print("\n" + "=" * 60)
    print("STEP 2: Downloading PDFs")
    print("=" * 60)
    cmd_download(args)

    print("\n" + "=" * 60)
    print("STEP 3: Ingesting into RAG")
    print("=" * 60)
    cmd_ingest(args)

    print("\n" + "=" * 60)
    print("BUILD COMPLETE")
    print("=" * 60)
    cmd_stats(args)


def cmd_query(args):
    """Query the RAG."""
    rag = RedbooksRAG()
    result = asyncio.run(rag.query(args.question, n_results=args.num))

    print(f"\nQuery: {args.question}")
    print(f"Time: {result.get('query_time_ms', 0)}ms | Chunks searched: {result.get('total_chunks', 0)}")
    print("-" * 60)

    for i, r in enumerate(result.get("results", []), 1):
        print(f"\n[{i}] Score: {r['score']:.3f} | Source: {r['doc_name']}")
        print("-" * 40)
        content = r.get("highlighted_content", r["content"])
        # Truncate for display
        if len(content) > 500:
            content = content[:500] + "..."
        print(content)


def cmd_list(args):
    """List indexed documents."""
    rag = RedbooksRAG()
    docs = rag.list_documents()

    print(f"\nIndexed Documents ({len(docs)}):")
    print("-" * 60)

    for doc in docs:
        print(f"  [{doc['id']}] {doc['name']}")
        print(f"      Type: {doc['type']} | Chunks: {doc['chunks']} | Added: {doc['added']}")


def cmd_classics(args):
    """Download classic IBM documentation from bitsavers."""
    downloader = ClassicsDownloader()

    if args.list_only:
        pdfs = downloader.list_available()
        print("\nAvailable Classic PDFs:")
        for cat in BITSAVERS_DIRS:
            cat_pdfs = [p for p in pdfs if p["category"] == cat]
            if cat_pdfs:
                print(f"\n{cat} ({len(cat_pdfs)} PDFs):")
                for p in cat_pdfs[:5]:
                    print(f"  - {p['title'][:60]}")
                if len(cat_pdfs) > 5:
                    print(f"  ... and {len(cat_pdfs) - 5} more")
        return

    downloader.download(limit=args.limit, force=args.force)


def cmd_stats(args):
    """Show RAG statistics."""
    rag = RedbooksRAG()
    stats = rag.get_stats()

    print("\nRAG Statistics:")
    print("-" * 40)
    print(f"  Documents indexed: {stats['documents']}")
    print(f"  Total chunks: {stats['chunks']}")
    print(f"  Embedding model: {stats['embedding_model']}")
    print(f"  PDF support: {stats['pdf_support']}")
    print(f"  Chunking: {stats['chunking_strategy']}")

    if "redbooks" in stats:
        rb = stats["redbooks"]
        print(f"\nRedbooks:")
        print(f"  PDFs downloaded: {rb['pdfs_downloaded']}")
        print(f"  Manifest entries: {rb['manifest_entries']}")
        print(f"  PDFs directory: {rb['pdfs_dir']}")

    # Classics stats
    classics_count = len(list(CLASSICS_DIR.glob("*.pdf"))) if CLASSICS_DIR.exists() else 0
    print(f"\nClassics (bitsavers):")
    print(f"  PDFs downloaded: {classics_count}")
    print(f"  Directory: {CLASSICS_DIR}")


def main():
    parser = argparse.ArgumentParser(
        description="IBM Redbooks RAG Builder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Scrape command
    sp_scrape = subparsers.add_parser("scrape", help="Scrape Redbooks website")

    # Download command
    sp_download = subparsers.add_parser("download", help="Download PDFs")
    sp_download.add_argument("--limit", type=int, help="Max PDFs to download")
    sp_download.add_argument("--force", action="store_true", help="Re-download existing")

    # Ingest command
    sp_ingest = subparsers.add_parser("ingest", help="Ingest PDFs into RAG")
    sp_ingest.add_argument("--limit", type=int, help="Max PDFs to ingest")
    sp_ingest.add_argument("--force", action="store_true", help="Re-ingest existing")

    # Build command (full pipeline)
    sp_build = subparsers.add_parser("build", help="Full pipeline: scrape->download->ingest")
    sp_build.add_argument("--limit", type=int, help="Max PDFs to process")
    sp_build.add_argument("--force", action="store_true", help="Force re-processing")

    # Query command
    sp_query = subparsers.add_parser("query", help="Query the RAG")
    sp_query.add_argument("question", help="Question to ask")
    sp_query.add_argument("--num", "-n", type=int, default=5, help="Number of results")

    # List command
    sp_list = subparsers.add_parser("list", help="List indexed documents")

    # Stats command
    sp_stats = subparsers.add_parser("stats", help="Show RAG statistics")

    # Classics command (bitsavers)
    sp_classics = subparsers.add_parser("classics", help="Download classic IBM docs from bitsavers")
    sp_classics.add_argument("--limit", type=int, help="Max PDFs to download")
    sp_classics.add_argument("--force", action="store_true", help="Re-download existing")
    sp_classics.add_argument("--list", dest="list_only", action="store_true", help="List available only")

    args = parser.parse_args()

    if args.command == "scrape":
        cmd_scrape(args)
    elif args.command == "download":
        cmd_download(args)
    elif args.command == "ingest":
        cmd_ingest(args)
    elif args.command == "build":
        cmd_build(args)
    elif args.command == "query":
        cmd_query(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "classics":
        cmd_classics(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
