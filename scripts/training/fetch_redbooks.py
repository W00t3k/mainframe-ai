#!/usr/bin/env python3
"""
IBM Redbooks Fetcher

Downloads IBM Redbooks PDFs for mainframe/z/OS topics.
Redbooks are FREE from IBM - this just automates the download.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REDBOOKS_DIR = PROJECT_ROOT / "data" / "redbooks"
INDEX_FILE = REDBOOKS_DIR / "redbooks_index.json"

# IBM Redbooks search API
REDBOOKS_SEARCH_URL = "https://www.redbooks.ibm.com/redbooks.nsf/searchsite"
REDBOOKS_BASE_URL = "https://www.redbooks.ibm.com"

# Topics to search for
MAINFRAME_TOPICS = [
    "z/OS",
    "RACF",
    "CICS",
    "DB2 z/OS",
    "JES2",
    "JES3",
    "VSAM",
    "IMS",
    "MQ z/OS",
    "Parallel Sysplex",
    "z/OS security",
    "z/OS encryption",
    "DFSMS",
    "SMF",
    "TSO ISPF",
    "COBOL z/OS",
    "Assembler z/OS",
    "z/OS UNIX",
    "zFS",
    "HCD",
    "WLM workload manager",
    "RMF",
    "z/OS networking",
    "VTAM",
    "TCP/IP z/OS",
    "z/OS containers",
    "IBM Z security",
    "pervasive encryption",
    "z16",
    "z15",
    "LinuxONE",
]


def load_index() -> dict:
    """Load existing redbooks index."""
    if INDEX_FILE.exists():
        with open(INDEX_FILE) as f:
            return json.load(f)
    return {"redbooks": [], "downloaded": []}


def save_index(index: dict):
    """Save redbooks index."""
    REDBOOKS_DIR.mkdir(parents=True, exist_ok=True)
    with open(INDEX_FILE, "w") as f:
        json.dump(index, f, indent=2)


async def search_redbooks(topic: str, client: httpx.AsyncClient) -> list[dict]:
    """Search IBM Redbooks for a topic."""
    results = []

    # Try the Redbooks site search
    search_url = f"https://www.redbooks.ibm.com/cgi-bin/searchsite.cgi?query={topic.replace(' ', '+')}"

    try:
        response = await client.get(search_url, timeout=30.0, follow_redirects=True)
        if response.status_code != 200:
            print(f"  Search failed for '{topic}': {response.status_code}")
            return results

        html = response.text

        # Parse PDF links from search results
        # Pattern: href="/redbooks/pdfs/XXXXX.pdf" or similar
        pdf_pattern = re.compile(r'href="(/redbooks/pdfs/[^"]+\.pdf)"', re.IGNORECASE)
        title_pattern = re.compile(r'<a[^>]*href="/redbooks/pdfs/([^"]+)\.pdf"[^>]*>([^<]+)</a>', re.IGNORECASE)

        for match in pdf_pattern.finditer(html):
            pdf_path = match.group(1)
            pdf_url = urljoin(REDBOOKS_BASE_URL, pdf_path)

            # Extract form number from URL
            form_number = Path(pdf_path).stem.upper()

            # Try to find title
            title = form_number
            for tmatch in title_pattern.finditer(html):
                if tmatch.group(1).upper() == form_number:
                    title = tmatch.group(2).strip()
                    break

            results.append({
                "form_number": form_number,
                "title": title,
                "url": pdf_url,
                "topic": topic,
            })

        # Also try direct abstract pages pattern
        abstract_pattern = re.compile(r'href="(/abstracts/[^"]+)"', re.IGNORECASE)
        for match in abstract_pattern.finditer(html):
            abstract_path = match.group(1)
            abstract_url = urljoin(REDBOOKS_BASE_URL, abstract_path)

            # Fetch abstract page to get PDF link
            try:
                abs_response = await client.get(abstract_url, timeout=15.0)
                if abs_response.status_code == 200:
                    abs_html = abs_response.text
                    pdf_match = pdf_pattern.search(abs_html)
                    if pdf_match:
                        pdf_url = urljoin(REDBOOKS_BASE_URL, pdf_match.group(1))
                        form_number = Path(pdf_match.group(1)).stem.upper()

                        # Extract title from abstract page
                        title_match = re.search(r'<title>([^<]+)</title>', abs_html, re.IGNORECASE)
                        title = title_match.group(1).strip() if title_match else form_number

                        results.append({
                            "form_number": form_number,
                            "title": title,
                            "url": pdf_url,
                            "topic": topic,
                        })
            except Exception:
                pass

    except Exception as e:
        print(f"  Error searching '{topic}': {e}")

    return results


async def download_pdf(url: str, output_path: Path, client: httpx.AsyncClient) -> bool:
    """Download a PDF file."""
    try:
        response = await client.get(url, timeout=120.0, follow_redirects=True)
        if response.status_code == 200 and len(response.content) > 10000:  # Minimum 10KB
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(response.content)
            return True
        else:
            print(f"  Bad response: {response.status_code}, size: {len(response.content)}")
    except Exception as e:
        print(f"  Download error: {e}")
    return False


async def fetch_all_redbooks(max_per_topic: int = 20, download: bool = True):
    """Fetch and optionally download Redbooks for all topics."""
    index = load_index()
    existing_forms = {rb["form_number"] for rb in index["redbooks"]}
    downloaded_forms = set(index["downloaded"])

    all_results = []

    async with httpx.AsyncClient() as client:
        print(f"Searching {len(MAINFRAME_TOPICS)} mainframe topics...")

        for i, topic in enumerate(MAINFRAME_TOPICS):
            print(f"[{i+1}/{len(MAINFRAME_TOPICS)}] Searching: {topic}")
            results = await search_redbooks(topic, client)

            # Dedupe
            new_results = [r for r in results if r["form_number"] not in existing_forms]
            for r in new_results[:max_per_topic]:
                existing_forms.add(r["form_number"])
                all_results.append(r)

            print(f"  Found {len(results)} results, {len(new_results)} new")
            await asyncio.sleep(1)  # Rate limit

        print(f"\nTotal new Redbooks found: {len(all_results)}")

        # Add to index
        index["redbooks"].extend(all_results)
        save_index(index)

        if download and all_results:
            print(f"\nDownloading PDFs...")
            pdf_dir = REDBOOKS_DIR / "pdfs"
            pdf_dir.mkdir(parents=True, exist_ok=True)

            downloaded = 0
            for i, rb in enumerate(all_results):
                if rb["form_number"] in downloaded_forms:
                    continue

                output_path = pdf_dir / f"{rb['form_number']}.pdf"
                if output_path.exists():
                    downloaded_forms.add(rb["form_number"])
                    continue

                print(f"[{i+1}/{len(all_results)}] Downloading: {rb['form_number']} - {rb['title'][:50]}")

                if await download_pdf(rb["url"], output_path, client):
                    downloaded += 1
                    downloaded_forms.add(rb["form_number"])
                    index["downloaded"].append(rb["form_number"])
                    save_index(index)
                    print(f"  OK ({output_path.stat().st_size // 1024} KB)")
                else:
                    print(f"  FAILED")

                await asyncio.sleep(2)  # Rate limit downloads

            print(f"\nDownloaded {downloaded} new PDFs")

    return all_results


async def index_new_pdfs():
    """Index newly downloaded PDFs into RAG."""
    sys.path.insert(0, str(PROJECT_ROOT))
    from tools.rag_engine import get_rag_engine

    pdf_dir = REDBOOKS_DIR / "pdfs"
    if not pdf_dir.exists():
        print("No PDFs to index")
        return

    engine = get_rag_engine()
    existing_docs = {d.source for d in engine.documents.values()}

    pdfs = list(pdf_dir.glob("*.pdf"))
    print(f"Found {len(pdfs)} PDFs, checking for new ones...")

    indexed = 0
    for pdf_path in pdfs:
        if str(pdf_path) in existing_docs:
            continue

        print(f"Indexing: {pdf_path.name}")
        result = await engine.add_pdf(str(pdf_path), pdf_path.stem)

        if result.get("success"):
            indexed += 1
            print(f"  OK - {result.get('chunks', 0)} chunks")
        else:
            print(f"  Failed: {result.get('error', 'unknown')}")

    print(f"\nIndexed {indexed} new PDFs")


def main():
    parser = argparse.ArgumentParser(description="Fetch IBM Redbooks for mainframe topics")
    parser.add_argument("--search-only", action="store_true", help="Only search, don't download")
    parser.add_argument("--index-only", action="store_true", help="Only index existing PDFs")
    parser.add_argument("--max-per-topic", type=int, default=20, help="Max PDFs per topic")
    args = parser.parse_args()

    REDBOOKS_DIR.mkdir(parents=True, exist_ok=True)

    if args.index_only:
        asyncio.run(index_new_pdfs())
    else:
        asyncio.run(fetch_all_redbooks(
            max_per_topic=args.max_per_topic,
            download=not args.search_only
        ))

        if not args.search_only:
            print("\nIndexing downloaded PDFs into RAG...")
            asyncio.run(index_new_pdfs())

    print("\nDone!")


if __name__ == "__main__":
    main()
