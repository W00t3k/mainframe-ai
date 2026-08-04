#!/usr/bin/env python3
"""
Download IBM Redbooks from archive.org and convert to training data.

Sources:
- https://archive.org/details/bunch-of-ibm-redbooks/
- https://archive.org/details/IBMSoftwareRedbooks/

Usage:
    python download_archive_redbooks.py
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import List, Dict, Tuple

try:
    import requests
except ImportError:
    os.system("pip install requests")
    import requests

# Directories
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent.parent
DATA_DIR = PROJECT_DIR / "data"
REDBOOKS_DIR = DATA_DIR / "redbooks" / "archive_org"
OUTPUT_DIR = DATA_DIR / "training" / "examples"

# Archive.org Redbook collections
ARCHIVE_COLLECTIONS = {
    "bunch-of-ibm-redbooks": [
        "sg244170", "sg244171", "sg244237", "sg244239", "sg244249-4th",
        "sg244270", "sg244277", "sg244295", "sg244356", "sg244409",
        "sg244446", "sg244530", "sg244563", "sg244564", "sg244584",
        "sg244589", "sg244624", "sg244630", "sg244680", "sg244721",
        "sg244726", "sg244781", "sg244803", "sg244805", "sg244808",
        "sg244810", "sg244815", "sg244818", "sg244820", "sg244824",
        "sg244825", "sg244828", "sg244829", "sg244830", "sg244831",
        "sg244832", "sg244834", "sg244835", "sg244840", "sg244841",
        "sg244843", "sg244845", "sg244846", "sg244847", "sg244848",
        "sg244856", "sg244864", "sg244867", "sg244871", "sg244874",
        "sg244877", "sg244881", "sg244895", "sg244896", "sg244898",
    ],
}

# Redbook topics mapping (manual curation for key books)
REDBOOK_TOPICS = {
    "sg244170": ["z/OS", "UNIX System Services", "shell"],
    "sg244584": ["CICS", "Web Services", "transactions"],
    "sg244680": ["DB2", "z/OS", "database"],
    "sg244721": ["RACF", "security", "z/OS"],
    "sg244803": ["Parallel Sysplex", "clustering"],
    "sg244808": ["JES2", "batch", "spool"],
    "sg244815": ["DFSMS", "storage", "SMS"],
    "sg244818": ["IMS", "database", "transactions"],
    "sg244820": ["CICS", "performance", "tuning"],
    "sg244824": ["TCP/IP", "z/OS", "networking"],
    "sg244825": ["VTAM", "SNA", "networking"],
    "sg244828": ["Assembler", "HLASM", "system programming"],
    "sg244829": ["COBOL", "programming", "Enterprise COBOL"],
    "sg244830": ["PL/I", "programming"],
    "sg244831": ["REXX", "programming", "z/OS"],
    "sg244834": ["JCL", "batch", "utilities"],
    "sg244835": ["VSAM", "datasets", "IDCAMS"],
    "sg244840": ["DB2", "SQL", "stored procedures"],
    "sg244841": ["DB2", "utilities", "administration"],
    "sg244845": ["CICS", "COBOL", "programming"],
    "sg244846": ["CICS", "administration", "system programming"],
    "sg244847": ["IMS", "administration", "database"],
    "sg244848": ["MQ Series", "messaging", "middleware"],
}


def setup_directories():
    """Create necessary directories."""
    REDBOOKS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def download_text(collection: str, book_id: str) -> str:
    """Download djvu text from archive.org."""
    url = f"https://archive.org/stream/{collection}/{book_id}_djvu.txt"

    cache_path = REDBOOKS_DIR / f"{book_id}.txt"
    if cache_path.exists():
        print(f"  Using cached: {book_id}")
        return cache_path.read_text(errors='ignore')

    print(f"  Downloading: {book_id}")
    try:
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            text = response.text
            cache_path.write_text(text)
            return text
    except Exception as e:
        print(f"    Error: {e}")

    return ""


def clean_ocr_text(text: str) -> str:
    """Clean OCR artifacts from text."""
    # Remove excessive whitespace
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    text = re.sub(r' {3,}', '  ', text)

    # Remove page numbers and headers
    text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)

    # Remove common OCR artifacts
    text = re.sub(r'[|}{]', '', text)

    # Fix common OCR mistakes
    text = text.replace('0CBOl', 'COBOL')
    text = text.replace('z/0S', 'z/OS')
    text = text.replace('JCi', 'JCL')

    return text.strip()


def extract_sections(text: str) -> List[Tuple[str, str]]:
    """Extract titled sections from text."""
    sections = []

    # Look for chapter/section patterns
    patterns = [
        r'(?:Chapter|Section)\s+\d+[.:]\s*([^\n]+)\n((?:(?!Chapter|Section\s+\d).)+)',
        r'\n([A-Z][A-Za-z\s]{5,50})\n\n((?:(?!\n[A-Z][A-Za-z\s]{5,50}\n\n).){200,2000})',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for title, content in matches:
            title = title.strip()
            content = content.strip()
            if len(content) > 200 and len(content) < 3000:
                sections.append((title, content))

    return sections


def generate_qa_pairs(text: str, book_id: str, topics: List[str]) -> List[Dict]:
    """Generate Q&A training pairs from text."""
    qa_pairs = []
    text = clean_ocr_text(text)

    # Method 1: Extract from sections
    sections = extract_sections(text)
    for title, content in sections[:50]:  # Limit per book
        # Skip if too short or too long
        if len(content) < 100 or len(content) > 2000:
            continue

        # Generate question from title
        question = f"Explain {title.lower()} in the context of {topics[0] if topics else 'mainframe'}."

        qa_pairs.append({
            "messages": [
                {"role": "user", "content": question},
                {"role": "assistant", "content": content}
            ],
            "source": f"redbook-{book_id}"
        })

    # Method 2: Look for definition patterns
    def_patterns = [
        r'([A-Z][A-Za-z\s]+)\s+is\s+(a|an|the)\s+([^.]+\.(?:\s+[^.]+\.){0,2})',
        r'([A-Z]{2,})\s*[-:]\s*([^.]+\.(?:\s+[^.]+\.){0,2})',
    ]

    for pattern in def_patterns:
        matches = re.findall(pattern, text)
        for match in matches[:20]:
            if len(match) >= 2:
                term = match[0].strip()
                definition = ' '.join(match[1:]).strip() if isinstance(match, tuple) else match[1]

                if len(term) > 2 and len(definition) > 30:
                    qa_pairs.append({
                        "messages": [
                            {"role": "user", "content": f"What is {term}?"},
                            {"role": "assistant", "content": definition}
                        ],
                        "source": f"redbook-{book_id}"
                    })

    # Method 3: Command/syntax extraction
    cmd_patterns = [
        r'(?:command|syntax)[:\s]+([A-Z][A-Z0-9/]+(?:\s+[A-Z0-9=,()]+)*)',
    ]

    for pattern in cmd_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for cmd in matches[:10]:
            # Get surrounding context
            idx = text.find(cmd)
            if idx > 0:
                context = text[max(0, idx-200):idx+len(cmd)+500]
                if len(context) > 100:
                    qa_pairs.append({
                        "messages": [
                            {"role": "user", "content": f"Explain the {cmd.split()[0]} command."},
                            {"role": "assistant", "content": context.strip()}
                        ],
                        "source": f"redbook-{book_id}"
                    })

    return qa_pairs


def process_all_books():
    """Download and process all archive.org Redbooks."""
    print("=" * 60)
    print("Archive.org IBM Redbooks Processor")
    print("=" * 60)

    setup_directories()

    all_qa = []
    processed = 0

    for collection, books in ARCHIVE_COLLECTIONS.items():
        print(f"\nCollection: {collection}")
        print("-" * 40)

        for book_id in books:
            text = download_text(collection, book_id)
            if not text:
                continue

            topics = REDBOOK_TOPICS.get(book_id, ["mainframe", "z/OS"])
            qa_pairs = generate_qa_pairs(text, book_id, topics)

            print(f"    Generated {len(qa_pairs)} Q&A pairs")
            all_qa.extend(qa_pairs)
            processed += 1

            time.sleep(0.5)  # Be nice to archive.org

    # Deduplicate
    seen = set()
    unique_qa = []
    for item in all_qa:
        key = item["messages"][0]["content"][:100]
        if key not in seen:
            seen.add(key)
            unique_qa.append(item)

    print(f"\n{'=' * 60}")
    print(f"Processed: {processed} books")
    print(f"Total Q&A: {len(all_qa)}")
    print(f"Unique Q&A: {len(unique_qa)}")

    # Save to JSONL
    output_path = OUTPUT_DIR / "archive_redbooks.jsonl"
    with open(output_path, 'w') as f:
        for item in unique_qa:
            # Remove source field for training
            clean_item = {"messages": item["messages"]}
            f.write(json.dumps(clean_item) + '\n')

    print(f"Saved to: {output_path}")
    return len(unique_qa)


def main():
    process_all_books()


if __name__ == "__main__":
    main()
