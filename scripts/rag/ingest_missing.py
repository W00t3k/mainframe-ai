#!/usr/bin/env python3
"""
Ingest every PDF under data/ that isn't already in the RAG index.

The RAG store (data/rag_data/embeddings.json) is machine-local and gitignored,
so run this on each machine to bring the local index up to date with the
redbook PDFs committed in the repo.

Usage:
    .venv/bin/python scripts/rag/ingest_missing.py
"""
import os
import sys
import glob
import asyncio

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.chdir(ROOT)

from rag_engine import get_rag_engine  # noqa: E402


async def main():
    engine = get_rag_engine()

    ingested_src = set()
    ingested_names = set()
    for d in engine.documents.values():
        src = getattr(d, "source", "") or ""
        ingested_src.add(os.path.abspath(src))
        ingested_names.add(os.path.basename(src))

    all_pdfs = sorted(set(glob.glob("data/**/*.pdf", recursive=True)))
    missing = [
        p for p in all_pdfs
        if os.path.abspath(p) not in ingested_src
        and os.path.basename(p) not in ingested_names
    ]

    print(f"Total PDFs: {len(all_pdfs)} | already ingested: {len(ingested_src)} "
          f"| to ingest: {len(missing)}", flush=True)
    if not missing:
        print("Nothing to do.")
        return

    # The embeddings store is one large JSON file; rewriting it after every PDF
    # is slow. Suppress add_document's per-doc embeddings save and checkpoint
    # the (atomic) save every CHECKPOINT docs and at the end instead. The index
    # (small) still saves per doc.
    CHECKPOINT = 10
    real_save = engine._save_embeddings
    engine._save_embeddings = lambda: None  # no-op during the loop

    ok = skipped = failed = 0
    for i, pdf in enumerate(missing, 1):
        name = os.path.basename(pdf)
        print(f"[{i}/{len(missing)}] {name}", flush=True)
        try:
            res = await engine.add_pdf(pdf, name)
            if res.get("success"):
                ok += 1
                print(f"    OK — {res.get('chunks', '?')} chunks", flush=True)
            else:
                skipped += 1
                print(f"    skipped — {res.get('error')}", flush=True)
        except Exception as e:
            failed += 1
            print(f"    FAILED — {e}", flush=True)
        if i % CHECKPOINT == 0:
            real_save()  # atomic checkpoint
            print(f"    ...checkpoint saved ({len(engine.chunks)} chunks)", flush=True)

    engine._save_embeddings = real_save
    engine._save_embeddings()  # final atomic save
    print(f"\nDone. ingested={ok} skipped={skipped} failed={failed} "
          f"| total docs now: {len(engine.documents)} chunks: {len(engine.chunks)}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
