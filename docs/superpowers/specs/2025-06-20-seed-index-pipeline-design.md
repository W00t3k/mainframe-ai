# Mainframe Assistant Seed Index & Data Pipeline Design

**Date:** 2025-06-20
**Status:** Approved
**Branch:** feature/apple-silicon-bigiron

## Overview

This design improves the Mainframe Assistant to be fast, accurate, and mainframe-native for local macOS/Apple Silicon use. The core principle: **facts live in data, not hardcoded Python**.

### Goals

- Direct answers from seed data in <50ms for common mainframe questions
- Typo tolerance via pre-computed fuzzy index
- Automated data ingestion from feedback, local files, and external sources
- Eval system with regression detection and auto-generated tests
- Prioritized backlog driven by real query misses

### Non-Goals

- CUDA/GPU training (Apple Silicon branch is for inference, RAG, evals, dataset prep)
- Committing copyrighted IBM content, Redbooks, PDFs, model files, or checkpoints
- Hardcoding factual mainframe content into Python

---

## Architecture

### Module Structure

```
app/services/
├── chat.py                    # orchestrator (slimmed down)
├── seed_index/
│   ├── __init__.py
│   ├── builder.py             # build index from sources
│   ├── fuzzy.py               # typo/phonetic/abbrev generation
│   ├── lookup.py              # O(1) lookups
│   └── tracker.py             # log misses for backlog
├── data_pipeline/
│   ├── __init__.py
│   ├── feedback_processor.py
│   ├── folder_watcher.py
│   └── external_fetcher.py
├── eval_engine/
│   ├── __init__.py
│   ├── runner.py
│   ├── reporter.py
│   └── generator.py

scripts/rag/
├── build_seed_index.py        # build index with fuzzy
├── process_feedback.py        # process feedback corrections
├── watch_ingest.py            # folder watcher daemon
├── fetch_external.py          # external URL fetcher
└── generate_backlog.py        # prioritized TODO generator

scripts/eval/
├── run_chat_evals.py          # run evals
└── generate_evals.py          # auto-generate from feedback

configs/
├── seed_config.yaml           # main config
├── fetch_sources.yaml         # external URLs
└── abbreviations.yaml         # manual abbrev mappings

data/
├── rag_seed/                  # source markdown (truth)
│   ├── mainframe_basics.md
│   ├── approved/              # auto-approved feedback corrections
│   ├── pending/               # awaiting manual review
│   ├── ingested/              # from local folder drops
│   └── external/              # auto-indexed external content
├── reference/                 # generated indices
│   ├── seed_index_fuzzy.json
│   └── query_misses.jsonl
├── feedback/                  # user feedback
├── evals/                     # eval files + results
└── rag_ingest/                # drop folder for ingestion
```

---

## Component 1: Pre-Computed Fuzzy Index

### Index Structure

File: `data/reference/seed_index_fuzzy.json`

```json
{
  "version": "1.0",
  "built_at": "2025-06-19T10:30:00Z",
  "sources_hash": "sha256:abc123...",
  "canonical": {
    "mainframe": {
      "title": "Mainframe",
      "definition": "A large-scale computer system...",
      "kind": "definition",
      "source": "data/rag_seed/mainframe_basics.md"
    }
  },
  "fuzzy_map": {
    "mainfraem": "mainframe",
    "mainframme": "mainframe",
    "mf": "mainframe",
    "maynfraym": "mainframe",
    "MAINFRAME": "mainframe",
    "cics": "cics",
    "seeseeks": "cics",
    "customer information control system": "cics"
  }
}
```

### Fuzzy Generation Layers

At build time, for each canonical term:

1. **Typo variants** — adjacent key swaps, doubled letters, missing letters (Levenshtein distance ≤2)
2. **Normalization** — lowercase, strip punctuation, collapse spaces ("System/360" → "system360", "system 360", "s360")
3. **Phonetic** — Soundex + Metaphone codes mapped back to canonical
4. **Abbreviations** — manually curated in `configs/abbreviations.yaml` + auto-detected (first letters of multi-word terms)

### Lookup Flow

```
query → normalize(query) → fuzzy_map[normalized] → canonical[term] → answer
                                    ↓
                            not found? → score against all canonicals
                                    ↓
                            top 3 suggestions + LLM fallback
```

### Confidence Thresholds

- **>90%**: Auto-correct silently, return direct answer
- **70-90%**: Return answer with note "Assuming you meant X..."
- **<70%**: Return suggestions + LLM fallback attempt

### Files

| File | Purpose |
|------|---------|
| `app/services/seed_index/builder.py` | `build_fuzzy_index(sources_dir) → JSON` |
| `app/services/seed_index/fuzzy.py` | `generate_typos()`, `generate_phonetic()`, `normalize()` |
| `app/services/seed_index/lookup.py` | `lookup(query) → (match, confidence)` or `(suggestions, None)` |
| `scripts/rag/build_seed_index.py` | CLI: `python scripts/rag/build_seed_index.py --fuzzy` |

---

## Component 2: Data Pipeline

Three ingestion paths feed into the seed index.

### 2.1 Feedback Auto-Incorporation

When users mark answers WRONG with a correction, those accumulate in `data/feedback/chat_feedback.jsonl`.

**Flow:**
```
data/feedback/chat_feedback.jsonl
        ↓
feedback_processor.py (filter: rating=wrong, has correction)
        ↓
data/rag_seed/approved/corrections.md  (if auto-approved)
   or
data/rag_seed/pending/corrections.md   (if below threshold)
        ↓
rebuild index
```

**Approval modes:**
- **Auto-approve**: Same correction appears N times (configurable, default=3) → auto-merge
- **Review queue**: Below threshold → write to pending/ for manual review

### 2.2 Local Folder Watching

Drop files into `data/rag_ingest/` for automatic indexing.

**Flow:**
```
data/rag_ingest/*.md, *.txt, *.json
        ↓
folder_watcher.py (on startup or --watch daemon mode)
        ↓
parse → extract terms/definitions
        ↓
data/rag_seed/ingested/
        ↓
rebuild index
        ↓
move original to data/rag_ingest/.processed/
```

**Supported formats:** `.md`, `.txt`, `.json` (with schema `{term, definition, aliases?}`)

### 2.3 External Fetch

Configured via `configs/fetch_sources.yaml`:

```yaml
sources:
  - url: "https://www.ibm.com/docs/en/zos-basic-skills"
    mode: scheduled      # on-demand | scheduled | auto
    schedule: "weekly"
    review: true         # gate through pending/ if true
  - url: "https://en.wikipedia.org/wiki/Mainframe_computer"
    mode: auto
    review: false        # index immediately, track source
```

**Modes:**
- **on-demand**: Manual trigger via `python scripts/rag/fetch_external.py --url <url>`
- **scheduled**: Runs on schedule (daily/weekly), content goes to pending/ for review
- **auto**: Fetches from allowlist automatically, indexes immediately with source tracking

**Source tracking:** Every entry tagged with `source_url` and `fetch_date` for audit/rollback.

### Files

| File | Purpose |
|------|---------|
| `app/services/data_pipeline/feedback_processor.py` | `process_feedback(threshold=3)` |
| `app/services/data_pipeline/folder_watcher.py` | `watch(dir)`, `process_file(path)` |
| `app/services/data_pipeline/external_fetcher.py` | `fetch(url)`, `fetch_all_scheduled()` |
| `scripts/rag/process_feedback.py` | CLI for feedback processing |
| `scripts/rag/watch_ingest.py` | CLI for folder watcher daemon |
| `scripts/rag/fetch_external.py` | CLI for external fetching |

---

## Component 3: Eval System

### Eval File Format

Evals live in `data/evals/` as JSONL files:

```jsonl
{"id": "mf-001", "question": "What is a mainframe?", "ideal_keywords": ["large-scale", "computer", "enterprise"], "expect_mode": "rag_seed_direct", "max_ms": 50}
{"id": "mf-002", "question": "What is ABEND S0C7?", "ideal_keywords": ["data exception", "decimal", "numeric"], "expect_mode": "memory_direct", "max_ms": 50}
{"id": "mf-003", "question": "What is mainfraem?", "ideal_keywords": ["mainframe"], "expect_mode": "rag_seed_direct", "max_ms": 100, "note": "typo test"}
```

**Fields:**
- `id`: Unique identifier
- `question`: The query to test
- `ideal_keywords`: Must appear in response (case-insensitive)
- `expect_mode`: Expected `answer_mode` (optional)
- `max_ms`: Maximum acceptable response time (optional)
- `source`: `manual`, `feedback_right`, `feedback_wrong`

### Runner Output

File: `data/evals/results/YYYY-MM-DD-HHMMSS.json`

```json
{
  "run_id": "2025-06-19-103000",
  "summary": {
    "total": 50,
    "passed": 47,
    "failed": 3,
    "avg_ms": 32,
    "p95_ms": 78
  },
  "regressions": [
    {"id": "mf-012", "reason": "previously passed, now missing keyword 'VSAM'"}
  ],
  "results": [
    {"id": "mf-001", "passed": true, "ms": 12, "mode": "rag_seed_direct", "keywords_found": ["large-scale", "computer", "enterprise"]},
    {"id": "mf-003", "passed": false, "ms": 210, "mode": "rag_llm", "reason": "exceeded max_ms 100"}
  ]
}
```

### Regression Detection

Compares current run against baseline (`data/evals/baseline.json`):

- **New failure**: Test passed in baseline, fails now → regression
- **Time regression**: avg_ms increased >20% from baseline → warning
- **Mode regression**: Expected `rag_seed_direct`, got `rag_llm` → flagged

Update baseline: `python scripts/eval/run_chat_evals.py --set-baseline`

### Auto-Generated Evals

From feedback data:

```
data/feedback/chat_feedback.jsonl
        ↓
generator.py
        ↓
data/evals/auto_generated.jsonl
```

**Logic:**
- `rating=right` → Create passing test with response keywords as `ideal_keywords`
- `rating=wrong` + `correction` → Create test where `ideal_keywords` come from the correction
- Dedupe by question similarity (fuzzy match)

### Files

| File | Purpose |
|------|---------|
| `app/services/eval_engine/runner.py` | `run_evals(eval_file, base_url) → results` |
| `app/services/eval_engine/reporter.py` | `generate_report(results)`, `detect_regressions(results, baseline)` |
| `app/services/eval_engine/generator.py` | `generate_from_feedback(feedback_file) → evals` |
| `scripts/eval/run_chat_evals.py` | CLI: `python scripts/eval/run_chat_evals.py --input X --base-url Y` |
| `scripts/eval/generate_evals.py` | CLI: `python scripts/eval/generate_evals.py` |

---

## Component 4: Prioritized Backlog

### Query Miss Tracking

Every query that hits `unknown_guard` or falls back to LLM gets logged:

File: `data/reference/query_misses.jsonl`

```jsonl
{"ts": "2025-06-19T10:30:00Z", "query": "what is sdsf", "mode": "rag_llm", "suggestions": ["sds", "ispf"]}
{"ts": "2025-06-19T10:31:00Z", "query": "explain initiators", "mode": "unknown_guard", "suggestions": []}
```

### Backlog Generator Output

File: `data/rag_seed/TODO.md`

```markdown
# Seed Content Backlog

Generated: 2025-06-19

## High Priority (10+ queries)

| Term | Query Count | Sample Queries |
|------|-------------|----------------|
| SDSF | 23 | "what is sdsf", "sdsf commands" |
| Initiators | 15 | "explain initiators", "what are initiators" |

## Medium Priority (5-9 queries)

| Term | Query Count | Sample Queries |
|------|-------------|----------------|
| STEPLIB | 7 | "steplib vs joblib", "what is steplib" |

## Low Priority (2-4 queries)

| Term | Query Count | Sample Queries |
|------|-------------|----------------|
| HLQ | 3 | "what is hlq" |

## Coverage Check

Core terms from TODO list still missing definitions:
- [ ] SDSF
- [ ] Initiators
- [ ] STEPLIB
- [x] RACF (covered)
- [x] JCL (covered)
```

### Files

| File | Purpose |
|------|---------|
| `app/services/seed_index/tracker.py` | `log_miss(query, mode, suggestions)` |
| `scripts/rag/generate_backlog.py` | CLI: `python scripts/rag/generate_backlog.py` |

---

## Component 5: Integration & Query Flow

### Updated Chat Routing

`chat.py` becomes a thin orchestrator:

```
User Query
    ↓
normalize(query)
    ↓
seed_index.lookup(query)
    ├─ exact match in fuzzy_map? → return answer
    │   (mode: rag_seed_direct, <10ms)
    │
    ├─ high confidence fuzzy (>90%)? → return answer
    │   (mode: rag_seed_direct, <20ms)
    │
    ├─ medium confidence (70-90%)? → return answer
    │   + "Assuming you meant X..." note
    │   (mode: rag_seed_direct, <30ms)
    │
    └─ low confidence (<70%)? → continue
    ↓
Get top 3 suggestions + log miss
tracker.log_miss(query, suggestions)
    ↓
LLM fallback (Ollama)
    - Include suggestions in prompt context
    - "User asked about X. Similar terms: A, B, C"
    (mode: rag_llm, ~500-2000ms)
    ↓
Return response with:
  - answer
  - answer_mode
  - suggestions (if any)
  - confidence_score
```

### Startup Sequence

```python
def on_startup():
    # Check if index needs rebuild (source files changed)
    if needs_rebuild():
        rebuild_index()

    # Process any pending feedback corrections (auto-approve threshold)
    process_pending_feedback(threshold=3)

    # Process any files dropped in ingest folder
    process_ingest_folder()

    # Load index into memory for fast lookups
    load_index()
```

---

## Configuration

### Main Config: `configs/seed_config.yaml`

```yaml
fuzzy:
  typo_distance: 2              # max Levenshtein distance
  phonetic_enabled: true
  abbreviations_file: "configs/abbreviations.yaml"

feedback:
  auto_approve_threshold: 3     # corrections needed for auto-merge

ingest:
  watch_dir: "data/rag_ingest"
  supported_formats: [".md", ".txt", ".json"]

eval:
  baseline_file: "data/evals/baseline.json"
  regression_threshold_pct: 20  # warn if avg_ms increases by this %

backlog:
  high_priority_min: 10
  medium_priority_min: 5
```

### External Sources: `configs/fetch_sources.yaml`

```yaml
sources:
  - url: "https://www.ibm.com/docs/en/zos-basic-skills"
    mode: scheduled
    schedule: "weekly"
    review: true
  - url: "https://en.wikipedia.org/wiki/Mainframe_computer"
    mode: auto
    review: false
```

### Abbreviations: `configs/abbreviations.yaml`

```yaml
abbreviations:
  mf: mainframe
  jcl: job control language
  tso: time sharing option
  ispf: interactive system productivity facility
  racf: resource access control facility
  cics: customer information control system
  vsam: virtual storage access method
  sdsf: system display and search facility
```

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Direct answer response time | <50ms for seed/memory lookups |
| Typo tolerance | Handle Levenshtein distance ≤2 |
| Unknown handling | Suggest top 3 + LLM attempt (no dead ends) |
| Eval pass rate | >95% on core mainframe terms |
| Regression detection | Flag any newly failing tests |

---

## Future Considerations (Out of Scope)

- LoRA fine-tuning on collected feedback (separate phase)
- Extracting hardcoded facts from `chat.py` (deferred for training prep)
- Streaming responses
- Multi-turn context summarization

---

## Appendix: Core Terms Checklist

Terms that must have definitions (from TODO):

- [ ] Mainframe
- [ ] System/360
- [ ] System/370
- [ ] System/390
- [ ] MVS
- [ ] z/OS
- [ ] TSO
- [ ] ISPF
- [ ] RACF
- [ ] JES
- [ ] JCL
- [ ] Datasets
- [ ] APF
- [ ] VTAM
- [ ] CICS
- [ ] SMF
- [ ] REXX
- [ ] COBOL
- [ ] VSAM
- [ ] SDSF
- [ ] IPL
- [ ] LPAR
- [ ] SAF
- [ ] Db2
- [ ] IMS
- [ ] STEPLIB
- [ ] JOBLIB
- [ ] HLQ
- [ ] Catalog
- [ ] Spool
- [ ] SYSOUT
