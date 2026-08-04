#!/usr/bin/env python3
"""
IBM Redbooks Scraper and Training Data Generator

Downloads IBM Redbooks PDFs and converts them to training data format.
Focuses on z/OS, CICS, DB2, RACF, JES2/JES3, Sysplex, and related topics.

Usage:
    python scrape_redbooks.py --download    # Download PDFs
    python scrape_redbooks.py --convert     # Convert to training data
    python scrape_redbooks.py --all         # Both
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

# Check for required libraries
try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Installing required packages...")
    os.system("pip install requests beautifulsoup4")
    import requests
    from bs4 import BeautifulSoup

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Installing PyMuPDF for PDF extraction...")
    os.system("pip install pymupdf")
    import fitz

# Directories
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent.parent
DATA_DIR = PROJECT_DIR / "data"
REDBOOKS_DIR = DATA_DIR / "redbooks"
PDF_DIR = REDBOOKS_DIR / "pdfs"
OUTPUT_DIR = DATA_DIR / "training" / "examples"

# IBM Redbooks base URL
REDBOOKS_BASE = "https://www.redbooks.ibm.com"
REDBOOKS_SEARCH = "https://www.redbooks.ibm.com/cgi-bin/searchsite.cgi"

# Key Redbooks for mainframe training (manually curated list)
# Format: (form_number, title, topics)
PRIORITY_REDBOOKS = [
    # z/OS Fundamentals
    ("sg24-6366", "ABCs of z/OS System Programming Volume 1", ["z/OS", "system programming", "IPL"]),
    ("sg24-6367", "ABCs of z/OS System Programming Volume 2", ["z/OS", "JES2", "VTAM"]),
    ("sg24-6368", "ABCs of z/OS System Programming Volume 3", ["z/OS", "DFSMS", "catalog"]),
    ("sg24-6369", "ABCs of z/OS System Programming Volume 4", ["z/OS", "communications", "TCP/IP"]),
    ("sg24-6370", "ABCs of z/OS System Programming Volume 5", ["z/OS", "base services"]),

    # RACF and Security
    ("sg24-7312", "Security on z/OS", ["RACF", "security", "z/OS"]),
    ("sg24-6680", "RACF Implementation Guide", ["RACF", "security"]),

    # CICS
    ("sg24-8401", "CICS Performance Guide", ["CICS", "performance"]),
    ("sg24-7603", "CICS Transaction Server for z/OS", ["CICS", "transactions"]),

    # DB2
    ("sg24-6893", "DB2 for z/OS Performance", ["DB2", "performance", "SQL"]),
    ("sg24-8124", "DB2 11 for z/OS Technical Overview", ["DB2", "z/OS"]),

    # JES2/JES3
    ("sg24-8252", "JES2 Implementation", ["JES2", "batch", "spool"]),
    ("sg24-8280", "JES3 Introduction", ["JES3", "batch", "DJC"]),

    # Parallel Sysplex
    ("sg24-5697", "Parallel Sysplex Overview", ["sysplex", "coupling facility"]),
    ("sg24-2563", "z/OS Parallel Sysplex Configuration", ["sysplex", "configuration"]),
    ("sg24-6400", "System Programmer's Guide to z/OS Parallel Sysplex", ["sysplex", "system programming"]),

    # DFSMS and Storage
    ("sg24-6839", "DFSMS Implementation Guide", ["DFSMS", "SMS", "storage"]),
    ("sg24-5665", "DFSMShsm Implementation and Customization", ["HSM", "storage management"]),

    # VSAM
    ("sg24-6105", "VSAM Demystified", ["VSAM", "datasets", "IDCAMS"]),

    # IMS
    ("sg24-8243", "IMS Database Administration", ["IMS", "database"]),

    # z/VM and Linux
    ("sg24-8232", "z/VM Getting Started with Linux", ["z/VM", "Linux"]),

    # Operations
    ("sg24-6451", "z/OS Operations and Automation", ["operations", "automation"]),

    # Assembler
    ("sg24-7302", "Assembler Language Programming for IBM z", ["assembler", "HLASM"]),

    # COBOL
    ("sg24-7869", "Enterprise COBOL for z/OS", ["COBOL", "programming"]),

    # Networking
    ("sg24-5227", "TCP/IP for z/OS Implementation", ["TCP/IP", "networking"]),
]


def setup_directories():
    """Create necessary directories."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REDBOOKS_DIR.mkdir(parents=True, exist_ok=True)


def download_redbook(form_number: str, title: str) -> Optional[Path]:
    """
    Download a Redbook PDF by form number.

    IBM Redbooks are typically at:
    https://www.redbooks.ibm.com/redbooks/pdfs/{form_number}.pdf
    """
    pdf_path = PDF_DIR / f"{form_number}.pdf"

    if pdf_path.exists():
        print(f"  Already downloaded: {form_number}")
        return pdf_path

    # Try different URL patterns
    urls = [
        f"https://www.redbooks.ibm.com/redbooks/pdfs/{form_number}.pdf",
        f"https://www.redbooks.ibm.com/redpieces/pdfs/{form_number}.pdf",
        f"https://www.redbooks.ibm.com/abstracts/{form_number}.pdf",
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    for url in urls:
        try:
            print(f"  Trying: {url}")
            response = requests.get(url, headers=headers, timeout=60, stream=True)

            if response.status_code == 200 and 'pdf' in response.headers.get('content-type', '').lower():
                with open(pdf_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"  Downloaded: {form_number} ({pdf_path.stat().st_size // 1024} KB)")
                return pdf_path
        except Exception as e:
            print(f"  Error with {url}: {e}")
            continue

    print(f"  Failed to download: {form_number}")
    return None


def download_all_redbooks():
    """Download all priority Redbooks."""
    print("=" * 60)
    print("IBM Redbooks Downloader")
    print("=" * 60)

    setup_directories()

    downloaded = 0
    failed = 0

    for form_number, title, topics in PRIORITY_REDBOOKS:
        print(f"\n[{form_number}] {title}")
        if download_redbook(form_number, title):
            downloaded += 1
        else:
            failed += 1
        time.sleep(1)  # Be nice to the server

    print(f"\n{'=' * 60}")
    print(f"Downloaded: {downloaded}, Failed: {failed}")
    return downloaded


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from a PDF file."""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        print(f"  Error extracting {pdf_path}: {e}")
        return ""


def clean_text(text: str) -> str:
    """Clean extracted PDF text."""
    # Remove excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)

    # Remove page numbers and headers/footers
    text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'Chapter \d+\..*?(?=\n)', '', text)

    # Remove common PDF artifacts
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)

    return text.strip()


def chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> List[str]:
    """Split text into overlapping chunks for processing."""
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # Try to break at paragraph
        if end < len(text):
            para_break = text.rfind('\n\n', start, end)
            if para_break > start + chunk_size // 2:
                end = para_break

        chunks.append(text[start:end].strip())
        start = end - overlap

    return [c for c in chunks if len(c) > 100]


def generate_qa_from_chunk(chunk: str, topics: List[str], title: str) -> List[Dict]:
    """
    Generate Q&A pairs from a text chunk.

    This uses heuristics to identify potential Q&A material:
    - Sections that explain concepts
    - Command examples
    - Configuration examples
    - Best practices
    """
    qa_pairs = []

    # Look for definition patterns
    definition_patterns = [
        r'(?:^|\n)([A-Z][A-Za-z\s]+)\s+is\s+(.+?)(?:\n\n|\n[A-Z])',
        r'(?:^|\n)([A-Z]{2,})\s*[-:]\s*(.+?)(?:\n\n|\n[A-Z])',
    ]

    for pattern in definition_patterns:
        matches = re.findall(pattern, chunk, re.DOTALL)
        for term, definition in matches:
            term = term.strip()
            definition = definition.strip()
            if len(definition) > 50 and len(definition) < 1000:
                qa_pairs.append({
                    "messages": [
                        {"role": "user", "content": f"What is {term}?"},
                        {"role": "assistant", "content": definition}
                    ]
                })

    # Look for "how to" content
    howto_patterns = [
        r'(?:To|In order to)\s+([a-z][^.]+),\s+([^.]+\.(?:\s+[^.]+\.){0,3})',
    ]

    for pattern in howto_patterns:
        matches = re.findall(pattern, chunk)
        for action, steps in matches:
            if len(steps) > 50:
                qa_pairs.append({
                    "messages": [
                        {"role": "user", "content": f"How do I {action}?"},
                        {"role": "assistant", "content": steps.strip()}
                    ]
                })

    # Look for command examples
    command_patterns = [
        r'(?:command|syntax):\s*\n\s*([A-Z][A-Z0-9/]+(?:\s+[A-Z0-9=,()]+)*)',
    ]

    for pattern in command_patterns:
        matches = re.findall(pattern, chunk, re.IGNORECASE)
        for cmd in matches:
            # Find surrounding context
            cmd_idx = chunk.find(cmd)
            context_start = max(0, cmd_idx - 200)
            context_end = min(len(chunk), cmd_idx + len(cmd) + 500)
            context = chunk[context_start:context_end]

            if len(context) > 100:
                qa_pairs.append({
                    "messages": [
                        {"role": "user", "content": f"Explain the {cmd.split()[0]} command."},
                        {"role": "assistant", "content": context.strip()}
                    ]
                })

    return qa_pairs


def convert_redbook_to_training(pdf_path: Path, topics: List[str], title: str) -> List[Dict]:
    """Convert a single Redbook PDF to training data."""
    print(f"  Extracting text...")
    text = extract_text_from_pdf(pdf_path)

    if not text:
        return []

    text = clean_text(text)
    print(f"  Extracted {len(text):,} characters")

    chunks = chunk_text(text)
    print(f"  Split into {len(chunks)} chunks")

    all_qa = []
    for chunk in chunks:
        qa_pairs = generate_qa_from_chunk(chunk, topics, title)
        all_qa.extend(qa_pairs)

    print(f"  Generated {len(all_qa)} Q&A pairs")
    return all_qa


def convert_all_redbooks():
    """Convert all downloaded Redbooks to training data."""
    print("=" * 60)
    print("Redbooks to Training Data Converter")
    print("=" * 60)

    all_training_data = []

    for form_number, title, topics in PRIORITY_REDBOOKS:
        pdf_path = PDF_DIR / f"{form_number}.pdf"

        if not pdf_path.exists():
            print(f"\n[{form_number}] Not downloaded, skipping")
            continue

        print(f"\n[{form_number}] {title}")
        qa_pairs = convert_redbook_to_training(pdf_path, topics, title)
        all_training_data.extend(qa_pairs)

    # Deduplicate
    seen = set()
    unique_data = []
    for item in all_training_data:
        key = item["messages"][0]["content"]
        if key not in seen:
            seen.add(key)
            unique_data.append(item)

    print(f"\n{'=' * 60}")
    print(f"Total Q&A pairs: {len(all_training_data)}")
    print(f"After deduplication: {len(unique_data)}")

    # Save to JSONL
    output_path = OUTPUT_DIR / "redbooks_extracted.jsonl"
    with open(output_path, 'w') as f:
        for item in unique_data:
            f.write(json.dumps(item) + '\n')

    print(f"Saved to: {output_path}")

    # Update index
    index_path = REDBOOKS_DIR / "redbooks_index.json"
    index = {
        "total_redbooks": len(PRIORITY_REDBOOKS),
        "downloaded": len(list(PDF_DIR.glob("*.pdf"))),
        "training_examples": len(unique_data),
        "redbooks": [
            {
                "form_number": fn,
                "title": t,
                "topics": tp,
                "downloaded": (PDF_DIR / f"{fn}.pdf").exists()
            }
            for fn, t, tp in PRIORITY_REDBOOKS
        ]
    }
    with open(index_path, 'w') as f:
        json.dump(index, f, indent=2)

    return len(unique_data)


def search_redbooks(query: str, max_results: int = 10) -> List[Dict]:
    """
    Search IBM Redbooks website for additional books.

    Note: IBM's search interface may change. This is a basic implementation.
    """
    print(f"Searching for: {query}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    params = {
        "q": query,
        "count": max_results
    }

    try:
        response = requests.get(REDBOOKS_SEARCH, params=params, headers=headers, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')

        results = []
        # Parse results (structure depends on IBM's website)
        for link in soup.find_all('a', href=True):
            href = link['href']
            if 'abstracts' in href or 'redbooks' in href:
                # Extract form number from URL
                match = re.search(r'(sg\d{2}-\d{4})', href, re.IGNORECASE)
                if match:
                    results.append({
                        "form_number": match.group(1).lower(),
                        "title": link.get_text(strip=True),
                        "url": urljoin(REDBOOKS_BASE, href)
                    })

        return results[:max_results]
    except Exception as e:
        print(f"Search error: {e}")
        return []


def main():
    parser = argparse.ArgumentParser(description="IBM Redbooks Scraper")
    parser.add_argument("--download", action="store_true", help="Download Redbook PDFs")
    parser.add_argument("--convert", action="store_true", help="Convert PDFs to training data")
    parser.add_argument("--all", action="store_true", help="Download and convert")
    parser.add_argument("--search", type=str, help="Search for Redbooks by keyword")

    args = parser.parse_args()

    if args.search:
        results = search_redbooks(args.search)
        for r in results:
            print(f"  {r['form_number']}: {r['title']}")
        return

    if args.all:
        args.download = True
        args.convert = True

    if not (args.download or args.convert):
        parser.print_help()
        return

    if args.download:
        download_all_redbooks()

    if args.convert:
        convert_all_redbooks()


if __name__ == "__main__":
    main()
