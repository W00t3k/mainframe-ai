#!/usr/bin/env python3
"""
Extract training data from IBM Redbooks PDFs.
Creates Q&A pairs from chapter content.

Usage:
    python scripts/extract_redbooks.py data/redbooks/security/*.pdf
    python scripts/extract_redbooks.py --all  # Process all PDFs
"""

import json
import sys
import os
import re
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Install PyMuPDF: pip install pymupdf")
    sys.exit(1)


def extract_chapters(pdf_path):
    """Extract text by chapter from PDF."""
    doc = fitz.open(pdf_path)
    chapters = []
    current_chapter = {"title": "Introduction", "text": ""}

    for page in doc:
        text = page.get_text()

        # Detect chapter headings (common Redbook patterns)
        chapter_match = re.search(
            r'^(?:Chapter\s+)?(\d+)[.\s]+([A-Z][^\n]{10,80})$',
            text, re.MULTILINE
        )

        if chapter_match:
            # Save previous chapter
            if current_chapter["text"].strip():
                chapters.append(current_chapter)

            current_chapter = {
                "title": chapter_match.group(2).strip(),
                "text": text
            }
        else:
            current_chapter["text"] += "\n" + text

    # Save last chapter
    if current_chapter["text"].strip():
        chapters.append(current_chapter)

    doc.close()
    return chapters


def clean_text(text):
    """Clean extracted PDF text."""
    # Remove page numbers, headers, footers
    text = re.sub(r'\n\d+\s*\n', '\n', text)
    text = re.sub(r'©.*?IBM.*?\n', '', text)
    text = re.sub(r'Chapter \d+\..*?\n', '', text)

    # Fix common OCR/extraction issues
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def chunk_text(text, max_chars=2000):
    """Split text into reasonable chunks."""
    paragraphs = text.split('\n\n')
    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) < max_chars:
            current += para + "\n\n"
        else:
            if current:
                chunks.append(current.strip())
            current = para + "\n\n"

    if current:
        chunks.append(current.strip())

    return chunks


def generate_qa_pairs(chapter_title, text_chunk, book_title):
    """Generate Q&A training pairs from text."""
    pairs = []

    # Clean the text
    text = clean_text(text_chunk)

    if len(text) < 100:
        return pairs

    # Generate contextual question
    topic = chapter_title.lower()

    # Create different question styles
    questions = [
        f"Explain {topic} in z/OS.",
        f"How does {topic} work on the mainframe?",
        f"What should I know about {topic}?",
    ]

    for q in questions[:1]:  # Just use first question style
        pairs.append({
            "messages": [
                {"role": "user", "content": q},
                {"role": "assistant", "content": text[:3000]}  # Limit response length
            ]
        })

    return pairs


def process_pdf(pdf_path, output_file):
    """Process a single PDF and append to output."""
    print(f"Processing: {pdf_path}")

    try:
        chapters = extract_chapters(pdf_path)
    except Exception as e:
        print(f"  Error: {e}")
        return 0

    book_title = Path(pdf_path).stem
    count = 0

    with open(output_file, 'a') as f:
        for chapter in chapters:
            chunks = chunk_text(chapter["text"])

            for chunk in chunks:
                pairs = generate_qa_pairs(
                    chapter["title"],
                    chunk,
                    book_title
                )

                for pair in pairs:
                    f.write(json.dumps(pair) + '\n')
                    count += 1

    print(f"  Generated {count} training examples")
    return count


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    # Output file
    script_dir = Path(__file__).parent.parent
    output_file = script_dir / "data/training/examples/redbooks_security.jsonl"

    # Clear output if starting fresh
    if "--fresh" in sys.argv:
        output_file.unlink(missing_ok=True)
        sys.argv.remove("--fresh")

    # Find PDFs
    if "--all" in sys.argv:
        pdf_dir = script_dir / "data/redbooks"
        pdfs = list(pdf_dir.glob("**/*.pdf"))
    else:
        pdfs = [Path(p) for p in sys.argv[1:] if p.endswith('.pdf')]

    if not pdfs:
        print("No PDFs found")
        sys.exit(1)

    print(f"Processing {len(pdfs)} PDFs...")
    print(f"Output: {output_file}")
    print()

    total = 0
    for pdf in pdfs:
        total += process_pdf(str(pdf), str(output_file))

    print()
    print(f"Total training examples: {total}")
    print(f"Output: {output_file}")


if __name__ == "__main__":
    main()
