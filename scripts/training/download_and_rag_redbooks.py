#!/usr/bin/env python3
"""
Download IBM Redbooks from archive.org and add to RAG system.

Source: https://archive.org/details/a-bunch-of-ibm-redbooks-pdfs/

Usage:
    python download_and_rag_redbooks.py --download   # Download PDFs
    python download_and_rag_redbooks.py --rag        # Add to RAG system
    python download_and_rag_redbooks.py --all        # Both
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import List, Dict, Optional

try:
    import requests
except ImportError:
    os.system("pip install requests")
    import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    os.system("pip install beautifulsoup4")
    from bs4 import BeautifulSoup

# Directories
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent.parent
DATA_DIR = PROJECT_DIR / "data"
REDBOOKS_DIR = DATA_DIR / "redbooks" / "archive_pdfs"
RAG_DOCS_DIR = DATA_DIR / "rag_data" / "documents"

# Archive.org collection
ARCHIVE_COLLECTION = "a-bunch-of-ibm-redbooks-pdfs"
ARCHIVE_BASE = f"https://archive.org/details/{ARCHIVE_COLLECTION}"
ARCHIVE_DOWNLOAD_BASE = f"https://archive.org/download/{ARCHIVE_COLLECTION}"

# Add project root to path for RAG imports
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(PROJECT_DIR / "tools"))


def setup_directories():
    """Create necessary directories."""
    REDBOOKS_DIR.mkdir(parents=True, exist_ok=True)
    RAG_DOCS_DIR.mkdir(parents=True, exist_ok=True)


def get_pdf_list() -> List[str]:
    """Get list of PDFs from archive.org collection."""
    print(f"Fetching PDF list from {ARCHIVE_BASE}...")

    # Archive.org provides file listings in JSON format
    files_url = f"https://archive.org/metadata/{ARCHIVE_COLLECTION}/files"

    try:
        response = requests.get(files_url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            pdfs = []
            for file_info in data.get("result", []):
                name = file_info.get("name", "")
                if name.lower().endswith(".pdf"):
                    pdfs.append(name)
            print(f"Found {len(pdfs)} PDF files")
            return pdfs
    except Exception as e:
        print(f"Error fetching file list: {e}")

    # Fallback: scrape the HTML page
    try:
        response = requests.get(ARCHIVE_BASE, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')

        pdfs = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.endswith('.pdf'):
                # Extract filename from URL
                filename = href.split('/')[-1]
                if filename:
                    pdfs.append(filename)

        pdfs = list(set(pdfs))  # Deduplicate
        print(f"Found {len(pdfs)} PDF files (via HTML)")
        return pdfs
    except Exception as e:
        print(f"Error scraping page: {e}")

    return []


def download_pdf(filename: str) -> Optional[Path]:
    """Download a single PDF from archive.org."""
    pdf_path = REDBOOKS_DIR / filename

    if pdf_path.exists():
        print(f"  [CACHED] {filename}")
        return pdf_path

    url = f"{ARCHIVE_DOWNLOAD_BASE}/{filename}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    try:
        print(f"  [DOWNLOADING] {filename}")
        response = requests.get(url, headers=headers, timeout=120, stream=True)

        if response.status_code == 200:
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(pdf_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        pct = (downloaded / total_size) * 100
                        print(f"\r    Progress: {pct:.1f}%", end="", flush=True)

            print(f"\r    Downloaded: {pdf_path.stat().st_size // 1024:,} KB")
            return pdf_path
        else:
            print(f"    Error: HTTP {response.status_code}")
    except Exception as e:
        print(f"    Error: {e}")

    return None


def download_all_pdfs(max_pdfs: int = 0) -> int:
    """Download all PDFs from archive.org collection."""
    print("=" * 60)
    print("Archive.org IBM Redbooks PDF Downloader")
    print("=" * 60)

    setup_directories()

    pdfs = get_pdf_list()
    if not pdfs:
        print("No PDFs found!")
        return 0

    if max_pdfs > 0:
        pdfs = pdfs[:max_pdfs]
        print(f"Limiting to {max_pdfs} PDFs")

    downloaded = 0
    failed = 0

    for i, pdf in enumerate(pdfs, 1):
        print(f"\n[{i}/{len(pdfs)}] {pdf}")
        if download_pdf(pdf):
            downloaded += 1
        else:
            failed += 1

        # Be nice to archive.org
        time.sleep(1)

    print(f"\n{'=' * 60}")
    print(f"Downloaded: {downloaded}, Failed: {failed}")
    print(f"PDFs stored in: {REDBOOKS_DIR}")

    return downloaded


async def add_pdfs_to_rag():
    """Add downloaded PDFs to the RAG system."""
    print("=" * 60)
    print("Adding Redbooks to RAG System")
    print("=" * 60)

    # Import RAG engine
    try:
        from rag_engine import get_rag_engine
    except ImportError:
        print("Error: Could not import RAG engine")
        print("Make sure you're in the project directory")
        return 0

    engine = get_rag_engine()

    # Get list of PDFs
    pdfs = list(REDBOOKS_DIR.glob("*.pdf"))
    if not pdfs:
        print("No PDFs found in download directory!")
        print(f"Run with --download first: {REDBOOKS_DIR}")
        return 0

    print(f"Found {len(pdfs)} PDFs to process")

    # Check which are already indexed
    existing_docs = {d.source for d in engine.documents.values()}

    added = 0
    skipped = 0
    failed = 0

    for i, pdf_path in enumerate(pdfs, 1):
        pdf_str = str(pdf_path)
        name = pdf_path.name

        print(f"\n[{i}/{len(pdfs)}] {name}")

        if pdf_str in existing_docs:
            print("  [SKIPPED] Already indexed")
            skipped += 1
            continue

        try:
            result = await engine.add_pdf(pdf_str, name)
            if result.get("success"):
                print(f"  [ADDED] {result.get('chunks', 0)} chunks")
                added += 1
            else:
                print(f"  [FAILED] {result.get('error', 'Unknown error')}")
                failed += 1
        except Exception as e:
            print(f"  [ERROR] {e}")
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"Added: {added}, Skipped: {skipped}, Failed: {failed}")

    # Show stats
    stats = engine.get_stats()
    print(f"\nRAG Stats:")
    print(f"  Documents: {stats.get('documents', 0)}")
    print(f"  Chunks: {stats.get('chunks', 0)}")

    return added


def main():
    parser = argparse.ArgumentParser(description="Download IBM Redbooks and add to RAG")
    parser.add_argument("--download", action="store_true", help="Download PDFs from archive.org")
    parser.add_argument("--rag", action="store_true", help="Add PDFs to RAG system")
    parser.add_argument("--all", action="store_true", help="Download and add to RAG")
    parser.add_argument("--max", type=int, default=0, help="Max PDFs to download (0 = all)")

    args = parser.parse_args()

    if args.all:
        args.download = True
        args.rag = True

    if not (args.download or args.rag):
        parser.print_help()
        return

    if args.download:
        download_all_pdfs(args.max)

    if args.rag:
        asyncio.run(add_pdfs_to_rag())


if __name__ == "__main__":
    main()
