# `data/` — Runtime Data

Runtime data generated and consumed by the application. Some directories are auto-created on first run.

## Contents

### `lab_data/`
Lab exercise definitions in JSON format. Each file defines a lab with steps, expected outputs, and walkthrough metadata. The `index.json` file lists all available labs.

### `rag_data/`
RAG (Retrieval-Augmented Generation) knowledge base:
- `index.json` — document metadata and chunk index
- `embeddings.json` — Ollama-generated embedding vectors
- `documents/` — uploaded source documents (text, PDF)

Auto-created on first run. Populated via the RAG upload UI at `/rag`.

### `screencaps/`
Saved terminal screenshots captured via the web UI. Each file is a timestamped text dump of the 24x80 3270 screen with host and time metadata.

### `trust_graph_data/`
Trust graph persistence:
- `graph.json` — nodes (identities, datasets, programs, etc.) and edges (accesses, submits, executes, etc.)

Auto-created on first run. Populated by walkthroughs, recon engine, and manual graph editing.

### `discovery.db`
SQLite database for the TN3270 network scanner results. Stores discovered hosts, banners, screenshots, and probe metadata. Created on first scanner run.
