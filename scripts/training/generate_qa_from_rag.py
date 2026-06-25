#!/usr/bin/env python3
"""
Generate synthetic Q&A pairs from RAG-indexed documents.
Uses Ollama to create training data from redbooks chunks.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Iterator

import httpx

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

OLLAMA_URL = "http://localhost:11434"
EMBEDDINGS_FILE = PROJECT_ROOT / "data" / "rag_data" / "embeddings.json"
OUTPUT_DIR = PROJECT_ROOT / "data" / "training" / "generated"

SYSTEM_PROMPT = (
    "You are BigIron.ai, a mainframe security assistant. "
    "Use mainframe-native reasoning and avoid Unix/Linux assumptions unless explicitly comparing them."
)

QA_GENERATION_PROMPT = """Based on the following technical content about mainframes/IBM Z systems, generate 2-3 question-answer pairs that would help someone learn from this material.

Rules:
- Questions should be specific and answerable from the content
- Answers should be concise but complete (2-4 sentences)
- Focus on practical knowledge, not trivia
- Use natural language questions a mainframe professional would ask
- Do NOT include questions about page numbers, document structure, or metadata

Content:
{chunk}

Output format (JSON array):
[
  {{"question": "...", "answer": "..."}},
  {{"question": "...", "answer": "..."}}
]

Generate the Q&A pairs:"""


def load_chunks() -> list[dict]:
    """Load embedded chunks from RAG index."""
    if not EMBEDDINGS_FILE.exists():
        raise SystemExit(f"Embeddings file not found: {EMBEDDINGS_FILE}")

    with open(EMBEDDINGS_FILE, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    return chunks


def generate_qa_from_chunk(chunk_text: str, model: str = "llama3.2") -> list[dict]:
    """Use Ollama to generate Q&A pairs from a chunk."""
    prompt = QA_GENERATION_PROMPT.format(chunk=chunk_text)

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.7}
                }
            )

            if response.status_code != 200:
                print(f"  Error: Ollama returned {response.status_code}")
                return []

            result = response.json()
            generated = result.get("response", "")

            # Parse the JSON from the response
            # Find JSON array in the response
            start = generated.find("[")
            end = generated.rfind("]") + 1

            if start == -1 or end == 0:
                print(f"  Warning: No JSON array found in response")
                return []

            qa_pairs = json.loads(generated[start:end])
            return qa_pairs

    except json.JSONDecodeError as e:
        print(f"  Warning: Failed to parse Q&A JSON: {e}")
        return []
    except Exception as e:
        print(f"  Error generating Q&A: {e}")
        return []


def iter_chunks_for_qa(chunks: list[dict], min_length: int = 200) -> Iterator[dict]:
    """Filter and yield chunks suitable for Q&A generation."""
    seen_texts = set()

    for chunk in chunks:
        text = chunk.get("text", "").strip()

        # Skip short chunks
        if len(text) < min_length:
            continue

        # Skip duplicates
        text_hash = hash(text[:500])  # Use first 500 chars for dedup
        if text_hash in seen_texts:
            continue
        seen_texts.add(text_hash)

        # Skip chunks that look like metadata/boilerplate
        lower_text = text.lower()
        if any(skip in lower_text for skip in [
            "table of contents",
            "copyright ibm",
            "all rights reserved",
            "printed in",
            "page intentionally left blank",
        ]):
            continue

        yield chunk


def format_training_sample(question: str, answer: str) -> dict:
    """Format Q&A pair as training sample."""
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ]
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate synthetic Q&A training data from RAG-indexed documents."
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_DIR / "rag_synthetic_qa.jsonl"),
        help="Output JSONL path.",
    )
    parser.add_argument(
        "--model",
        default="llama3.2",
        help="Ollama model to use for generation (default: llama3.2).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of chunks to process (0 = all).",
    )
    parser.add_argument(
        "--min-chunk-length",
        type=int,
        default=200,
        help="Minimum chunk length in characters.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip if output file exists.",
    )
    args = parser.parse_args()

    output_path = Path(args.output)

    if args.skip_existing and output_path.exists():
        print(f"Output file already exists, skipping: {output_path}")
        return 0

    # Check Ollama is running
    try:
        with httpx.Client() as client:
            r = client.get(f"{OLLAMA_URL}/api/tags", timeout=5.0)
            if r.status_code != 200:
                raise SystemExit("Ollama is not responding. Start it with: ollama serve")
    except Exception:
        raise SystemExit("Cannot connect to Ollama. Start it with: ollama serve")

    print(f"Loading RAG chunks from {EMBEDDINGS_FILE}...")
    chunks = load_chunks()
    print(f"Loaded {len(chunks)} total chunks")

    # Filter chunks
    eligible_chunks = list(iter_chunks_for_qa(chunks, args.min_chunk_length))
    print(f"Found {len(eligible_chunks)} chunks eligible for Q&A generation")

    if args.limit > 0:
        eligible_chunks = eligible_chunks[:args.limit]
        print(f"Limited to {args.limit} chunks")

    # Generate Q&A pairs
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_qa = 0
    processed = 0
    start_time = time.time()

    with output_path.open("w", encoding="utf-8") as out:
        for i, chunk in enumerate(eligible_chunks):
            doc_name = chunk.get("doc_name", "Unknown")
            text = chunk.get("text", "")

            print(f"[{i+1}/{len(eligible_chunks)}] Processing chunk from: {doc_name[:50]}...")

            qa_pairs = generate_qa_from_chunk(text, model=args.model)

            for pair in qa_pairs:
                question = pair.get("question", "").strip()
                answer = pair.get("answer", "").strip()

                if question and answer and len(question) > 10 and len(answer) > 20:
                    sample = format_training_sample(question, answer)
                    out.write(json.dumps(sample, ensure_ascii=True) + "\n")
                    total_qa += 1

            processed += 1

            # Progress update every 10 chunks
            if (i + 1) % 10 == 0:
                elapsed = time.time() - start_time
                rate = processed / elapsed
                remaining = (len(eligible_chunks) - processed) / rate if rate > 0 else 0
                print(f"  Progress: {processed} chunks, {total_qa} Q&A pairs, ~{remaining:.0f}s remaining")

    elapsed = time.time() - start_time
    print(f"\nDone!")
    print(f"  Processed: {processed} chunks")
    print(f"  Generated: {total_qa} Q&A pairs")
    print(f"  Output: {output_path}")
    print(f"  Time: {elapsed:.1f}s")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
