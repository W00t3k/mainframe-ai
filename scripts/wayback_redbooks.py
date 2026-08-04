#!/usr/bin/env python3
"""
Find and download IBM Redbooks from the Wayback Machine.
No Go required - pure Python.

Usage:
    python scripts/wayback_redbooks.py
"""

import json
import os
import re
import time
import urllib.request
from pathlib import Path

OUTDIR = Path(__file__).parent.parent / "data/redbooks/wayback"
OUTDIR.mkdir(parents=True, exist_ok=True)


def get_wayback_urls(domain):
    """Query Wayback Machine CDX API for archived URLs."""
    print(f"Querying Wayback Machine for {domain}...")

    url = f"https://web.archive.org/cdx/search/cdx?url={domain}/*&output=json&fl=original&collapse=urlkey"

    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            data = json.loads(response.read().decode())
            # Skip header row
            urls = [row[0] for row in data[1:] if row]
            return urls
    except Exception as e:
        print(f"Error querying Wayback: {e}")
        return []


def filter_redbook_pdfs(urls):
    """Filter for Redbook PDF URLs."""
    pdf_pattern = re.compile(r'(sg\d{6}|redp\d{4}|tips\d{4}).*\.pdf$', re.IGNORECASE)

    pdfs = set()
    for url in urls:
        if pdf_pattern.search(url):
            pdfs.add(url)

    return sorted(pdfs)


def get_wayback_download_url(original_url):
    """Get the Wayback Machine download URL for an archived page."""
    return f"https://web.archive.org/web/2/{original_url}"


def download_pdf(url, outdir):
    """Download a PDF from Wayback Machine."""
    # Extract filename from URL
    filename = re.search(r'(sg\d{6}|redp\d{4}|tips\d{4})', url, re.IGNORECASE)
    if not filename:
        return False

    outfile = outdir / f"{filename.group(1).lower()}_wayback.pdf"

    if outfile.exists():
        print(f"  [skip] {outfile.name} - already exists")
        return True

    wayback_url = get_wayback_download_url(url)
    print(f"  [download] {outfile.name}")

    try:
        req = urllib.request.Request(
            wayback_url,
            headers={'User-Agent': 'Mozilla/5.0 (Mainframe Research)'}
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            content = response.read()

            # Verify it's actually a PDF
            if content[:4] == b'%PDF':
                with open(outfile, 'wb') as f:
                    f.write(content)
                size = len(content) / 1024 / 1024
                print(f"    ✓ Downloaded ({size:.1f} MB)")
                return True
            else:
                print(f"    ✗ Not a valid PDF")
                return False

    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False


def main():
    print("=" * 60)
    print("Wayback Machine Redbook Downloader")
    print("=" * 60)
    print()

    # Search multiple IBM domains
    domains = [
        "redbooks.ibm.com",
        "www.redbooks.ibm.com",
        "publib.boulder.ibm.com",
    ]

    all_urls = []
    for domain in domains:
        urls = get_wayback_urls(domain)
        print(f"  Found {len(urls)} URLs from {domain}")
        all_urls.extend(urls)
        time.sleep(1)

    # Filter for Redbook PDFs
    pdfs = filter_redbook_pdfs(all_urls)
    print(f"\nFound {len(pdfs)} unique Redbook PDFs in archive")
    print()

    # Download each
    downloaded = 0
    for url in pdfs[:50]:  # Limit to 50 for safety
        if download_pdf(url, OUTDIR):
            downloaded += 1
        time.sleep(2)  # Be nice to archive.org

    print()
    print("=" * 60)
    print(f"Downloaded {downloaded} PDFs to {OUTDIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
