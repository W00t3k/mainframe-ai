#!/usr/bin/env python3
"""
Generate training data from downloaded IBM Redbooks PDFs.

Extracts Q&A pairs from the PDFs in data/redbooks/archive_pdfs/
and outputs to data/training/examples/redbooks_extracted.jsonl

Usage:
    python generate_redbooks_training.py
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Installing PyMuPDF...")
    os.system("pip install pymupdf")
    import fitz

# Directories
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent.parent
PDF_DIR = PROJECT_DIR / "data" / "redbooks" / "archive_pdfs"
OUTPUT_DIR = PROJECT_DIR / "data" / "training" / "examples"

# Topic mapping based on Redbook form numbers
TOPIC_MAP = {
    "sg244170": ["z/OS", "UNIX System Services"],
    "sg244530": ["WebSphere", "z/OS"],
    "sg244563": ["CICS", "Web Services"],
    "sg244564": ["DB2", "z/OS", "performance"],
    "sg244584": ["CICS", "Web Services", "SOA"],
    "sg244589": ["DB2", "z/OS", "application development"],
    "sg244624": ["z/OS", "security", "cryptography"],
    "sg244630": ["z/OS", "network security"],
    "sg244680": ["DB2", "z/OS", "utilities"],
    "sg244721": ["RACF", "security", "z/OS"],
    "sg244726": ["z/OS", "system management"],
    "sg244781": ["z/OS", "UNIX System Services"],
    "sg244803": ["Parallel Sysplex", "clustering", "z/OS"],
    "sg244808": ["JES2", "batch", "spool management"],
    "sg244810": ["z/OS", "system programming"],
    "sg244815": ["DFSMS", "storage management", "SMS"],
    "sg244818": ["IMS", "database", "transactions"],
    "sg244820": ["CICS", "performance", "tuning"],
    "sg244824": ["TCP/IP", "z/OS", "networking"],
    "sg244825": ["VTAM", "SNA", "networking"],
    "sg244828": ["Assembler", "HLASM", "system programming"],
    "sg244829": ["COBOL", "Enterprise COBOL", "programming"],
    "sg244830": ["PL/I", "programming", "z/OS"],
    "sg244831": ["REXX", "programming", "z/OS"],
    "sg244832": ["z/OS", "batch", "JCL"],
    "sg244834": ["JCL", "batch", "utilities"],
    "sg244835": ["VSAM", "IDCAMS", "datasets"],
    "sg244840": ["DB2", "SQL", "stored procedures"],
    "sg244841": ["DB2", "utilities", "administration"],
    "sg244843": ["z/OS", "system programming", "exits"],
    "sg244845": ["CICS", "COBOL", "programming"],
    "sg244846": ["CICS", "administration", "system programming"],
    "sg244847": ["IMS", "administration", "database"],
    "sg244848": ["MQ Series", "messaging", "middleware"],
    "sg244856": ["z/OS", "automation", "operations"],
    "sg244864": ["z/OS", "migration", "upgrade"],
    "sg244867": ["z/OS", "performance", "tuning"],
    "sg244871": ["z/OS", "security", "compliance"],
    "sg244874": ["z/OS", "storage", "management"],
    "sg244877": ["z/OS", "networking", "communications"],
    "sg244881": ["z/OS", "system programming", "SVC"],
    "sg244895": ["z/OS", "debugging", "problem determination"],
    "sg244896": ["z/OS", "recovery", "backup"],
    "sg244898": ["z/OS", "operations", "console"],
    "sg246100": ["z/OS", "containers", "modernization"],
    "sg246915": ["z/OS", "system programming", "fundamentals"],
    "sg249000": ["z/OS", "DevOps", "automation"],
    "sg249119": ["z/OS", "cloud", "integration"],
    "sg249406": ["z/OS", "AI", "machine learning"],
}


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
        print(f"  Error extracting {pdf_path.name}: {e}")
        return ""


def clean_text(text: str) -> str:
    """Clean extracted PDF text."""
    # Remove excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    # Remove page numbers
    text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)
    # Remove common PDF artifacts
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    return text.strip()


def extract_sections(text: str) -> List[Tuple[str, str]]:
    """Extract titled sections from text."""
    sections = []

    # Chapter/Section patterns
    patterns = [
        r'Chapter\s+\d+[.:]\s*([^\n]+)\n((?:(?!Chapter\s+\d).)+)',
        r'\n(\d+\.\d+\s+[A-Z][^\n]+)\n((?:(?!\n\d+\.\d+\s+[A-Z]).){200,3000})',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
        for title, content in matches:
            title = title.strip()
            content = content.strip()
            if 100 < len(content) < 3000:
                sections.append((title, content))

    return sections[:100]  # Limit per book


def extract_definitions(text: str) -> List[Tuple[str, str]]:
    """Extract definitions from text."""
    definitions = []

    patterns = [
        r'\b([A-Z][A-Za-z\s]{2,30})\s+is\s+(a|an|the)\s+([^.]+\.[^.]*\.?)',
        r'\b([A-Z]{2,8})\s*[-:]\s*([^.]+\.[^.]*\.?)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches[:30]:
            if len(match) >= 2:
                term = match[0].strip()
                if isinstance(match, tuple) and len(match) > 2:
                    definition = ' '.join(match[1:]).strip()
                else:
                    definition = match[1].strip() if len(match) > 1 else ""

                if len(term) > 2 and 30 < len(definition) < 500:
                    definitions.append((term, definition))

    return definitions


def extract_commands(text: str) -> List[Tuple[str, str]]:
    """Extract command examples from text."""
    commands = []

    # Look for JCL, TSO commands, operator commands
    patterns = [
        r'//(\w+)\s+(?:JOB|EXEC|DD)\s+([^\n]+(?:\n//[^\n]+)*)',
        r'(?:TSO|ISPF|operator)\s+command[:\s]+([A-Z][A-Z0-9\s]+)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches[:20]:
            if isinstance(match, tuple):
                cmd = match[0]
                context = match[1] if len(match) > 1 else ""
            else:
                cmd = match
                context = ""

            # Get surrounding context
            idx = text.find(cmd)
            if idx > 0:
                start = max(0, idx - 100)
                end = min(len(text), idx + len(cmd) + 400)
                context = text[start:end].strip()

            if len(context) > 50:
                commands.append((cmd, context))

    return commands


def generate_qa_pairs(pdf_path: Path) -> List[Dict]:
    """Generate Q&A pairs from a PDF."""
    qa_pairs = []

    # Get topics for this book
    book_id = pdf_path.stem.lower().split('-')[0]  # Handle sg246915-3th.pdf etc
    topics = TOPIC_MAP.get(book_id, ["z/OS", "mainframe"])
    primary_topic = topics[0]

    # Extract text
    text = extract_text_from_pdf(pdf_path)
    if not text:
        return []

    text = clean_text(text)

    # Method 1: Sections
    sections = extract_sections(text)
    for title, content in sections:
        question = f"Explain {title.lower()} in the context of {primary_topic}."
        qa_pairs.append({
            "messages": [
                {"role": "user", "content": question},
                {"role": "assistant", "content": content}
            ]
        })

    # Method 2: Definitions
    definitions = extract_definitions(text)
    for term, definition in definitions:
        qa_pairs.append({
            "messages": [
                {"role": "user", "content": f"What is {term}?"},
                {"role": "assistant", "content": definition}
            ]
        })

    # Method 3: Commands
    commands = extract_commands(text)
    for cmd, context in commands:
        qa_pairs.append({
            "messages": [
                {"role": "user", "content": f"Explain the {cmd} command or statement."},
                {"role": "assistant", "content": context}
            ]
        })

    return qa_pairs


def main():
    print("=" * 60)
    print("Redbooks Training Data Generator")
    print("=" * 60)

    if not PDF_DIR.exists():
        print(f"PDF directory not found: {PDF_DIR}")
        print("Run download_and_rag_redbooks.py --download first")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pdfs = list(PDF_DIR.glob("*.pdf"))
    print(f"Found {len(pdfs)} PDFs to process")

    all_qa = []

    for i, pdf in enumerate(pdfs, 1):
        print(f"\n[{i}/{len(pdfs)}] {pdf.name}")
        qa_pairs = generate_qa_pairs(pdf)
        print(f"  Generated {len(qa_pairs)} Q&A pairs")
        all_qa.extend(qa_pairs)

    # Deduplicate by question
    seen = set()
    unique_qa = []
    for item in all_qa:
        key = item["messages"][0]["content"][:80]
        if key not in seen:
            seen.add(key)
            unique_qa.append(item)

    print(f"\n{'=' * 60}")
    print(f"Total Q&A pairs: {len(all_qa)}")
    print(f"After deduplication: {len(unique_qa)}")

    # Save
    output_path = OUTPUT_DIR / "redbooks_extracted.jsonl"
    with open(output_path, 'w') as f:
        for item in unique_qa:
            f.write(json.dumps(item) + '\n')

    print(f"Saved to: {output_path}")
    return len(unique_qa)


if __name__ == "__main__":
    main()
