# Mainframe AI Assistant

**A reference implementation for trust-boundary assessment on z/OS.**

This tool operationalizes a mental model I've been applying since 2018 — first to Active Directory and enterprise Windows environments, now to mainframe systems. The model isn't new. The tool is.

## The Problem

Most offensive security methodologies import assumptions from Unix, Windows, and cloud environments. These assumptions fail on mainframe operating systems:

| Assumption | Reality on z/OS |
|------------|-----------------|
| "Ports define exposure" | VTAM session fabric exists independently of TCP/IP. Sessions outlive connections. |
| "There is a root user" | RACF distributes authority across profiles. No omnipotent account exists. |
| "Processes are short-lived" | Address spaces persist for weeks or months. Identity is bound at startup. |
| "Work executes immediately" | JES queues, schedules, and defers execution. Identity preserved from submission. |
| "There is a filesystem" | Datasets, catalogs, PDS members. No `/etc`, no hierarchy. |

**Assessments that import these assumptions miss the real attack surface.**

This is the same failure mode I wrote about in 2018 regarding Active Directory — attackers succeed not because of exploits, but because defenders misunderstand where authority is actually enforced. ADCS, delegation abuse, service account sprawl — these weren't "new vulnerabilities." They were trust boundaries that existed all along, invisible to teams using the wrong mental model.

Mainframes expose this more clearly because security is explicitly federated across five control planes:

1. **VTAM** — Session fabric (purple)
2. **TSO** — Human interaction (blue)
3. **RACF** — Authorization engine (amber)
4. **JES** — Deferred execution (pink)
5. **CICS** — Transaction processing (green)

If you bring the wrong mental model, you miss the real attack paths — just like people missed delegation abuse for years.

## What This Tool Does

- **Autonomous Walkthroughs** — Watch the tool connect, navigate, and narrate VTAM, TSO, ISPF, JES, and RACF. No keyboard needed. Educational narration explains what's happening at each control plane boundary.

- **Trust Graph** — BloodHound-style visualization of mainframe trust relationships. Map identities, datasets, jobs, and their connections.

- **Red Team Tutor** — AI-guided learning paths for mainframe security assessment. Ask questions, get contextual help on the current screen.

- **Recon Engine** — TSO/CICS/VTAM enumeration, hidden field detection, application mapping.

- **Security Labs** — Deterministic walkthroughs you can run offline. Replay VTAM → TSO → ISPF flows and batch execution patterns.

- **COBOL Development** — Complete compile-link-go walkthrough demonstrating the batch-oriented development lifecycle.

**100% local. No API keys. No cloud dependencies.** Uses Ollama for local LLM inference.

## Quick Start

### Requirements

- Python 3.10+
- [Ollama](https://ollama.com) for local LLM
- TK5 MVS 3.8j emulator (optional, for live terminal)

### macOS

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start Ollama
brew install ollama
ollama serve
ollama pull llama3.1:8b

# Start TK5 (optional)
cd tk5/mvs-tk5 && ./mvs

# Run the web app
python run.py
# Or: uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### Linux

```bash
# Install Python
sudo apt install python3 python3-venv python3-pip

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &
ollama pull llama3.1:8b

# Run
python run.py
```

### Verify

```bash
curl http://localhost:8080/api/status
```

Open in browser:

| URL | Feature |
|-----|---------|
| `http://localhost:8080/` | Dashboard |
| `http://localhost:8080/walkthrough` | Autonomous walkthroughs |
| `http://localhost:8080/tutor` | Red team tutor |
| `http://localhost:8080/graph` | Trust graph |
| `http://localhost:8080/terminal` | 3270 terminal (requires TK5) |
| `http://localhost:8080/recon` | Recon engine |
| `http://localhost:8080/labs` | Security labs |

## Walkthroughs

Seven autonomous walkthroughs demonstrate mainframe control planes:

| Walkthrough | What It Teaches |
|-------------|-----------------|
| **Session Stack** | VTAM → TSO → ISPF layer traversal, identity binding |
| **Deferred Execution** | JCL → JES workflow, jobs run later under submitter identity |
| **System Inspection** | SYS1.PROCLIB, SYS1.PARMLIB — where "config files" live |
| **Authorization Model** | RACF profiles, LISTCAT, how authority is distributed |
| **Dataset Model** | PDS, members, catalogs — no filesystem, just datasets |
| **Address Spaces** | SDSF, active jobs, persistent address spaces |
| **COBOL Development** | Compile-link-go lifecycle, batch-oriented programming |

Each walkthrough narrates five assessment questions:

- **Q1:** Where is identity bound?
- **Q2:** When is authority evaluated?
- **Q3:** What executes later than expected?
- **Q4:** Which subsystem enforces policy?
- **Q5:** What assumptions are you importing?

## The Mental Model

This tool didn't invent the trust-boundary assessment model. It **operationalizes** it.

The same mental model that exposed ADCS abuse, Kerberos delegation attacks, and service account sprawl in Active Directory applies directly to mainframes — but mainframes make the boundaries *explicit*. On z/OS, you can literally watch identity cross from VTAM to TSO to RACF.

**What changed isn't the model. What changed is that I now have a platform where the same failure modes are even more visible.**

The walkthroughs don't just show you how to navigate ISPF. They show you *where trust decisions happen* and *which assumptions break* at each boundary crossing.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     Web Interface                         │
│         FastAPI + HTMX + IBM Plex typography              │
└─────────────────────────┬────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────┐
│                    app/ (modular)                         │
│  routes/     - API endpoints                              │
│  services/   - Business logic (chat, walkthrough, LLM)    │
│  constants/  - Prompts, paths, walkthrough scripts        │
│  models/     - Pydantic schemas                           │
│  websocket/  - Real-time handlers                         │
└──────────┬───────────────────────────┬───────────────────┘
           │                           │
┌──────────▼──────────┐  ┌────────────▼────────────────────┐
│    Ollama (LLM)     │  │   TN3270 Layer (py3270)          │
│  - Q&A              │  │   - Screen reading              │
│  - Narration        │  │   - Command execution           │
│  - Code analysis    │  │   - Session management          │
└─────────────────────┘  └─────────────────────────────────┘
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `llama3.1:8b` | Model for inference |
| `MAINFRAME_HOST` | `localhost:3270` | Default TN3270 target |

## File Structure

```
mainframe_ai_assistant/
├── app/                    # Modular FastAPI application
│   ├── routes/             # API endpoints by feature
│   ├── services/           # Business logic
│   ├── constants/          # Prompts, walkthroughs, paths
│   └── models/             # Pydantic schemas
├── templates/              # Jinja2 HTML templates
├── static/                 # CSS, JS, fonts
├── lab_data/               # Lab exercise definitions
├── trust_graph_data/       # Graph persistence
├── tk5/                    # TK5 MVS 3.8j emulator (not included)
├── run.py                  # Application entry point
├── agent_tools.py          # TN3270 connection tools
├── trust_graph.py          # Graph data structures
├── recon_engine.py         # Enumeration engines
└── rag_engine.py           # RAG with local embeddings
```

## Related Work

- [py3270](https://pypi.org/project/py3270/) — Python TN3270 library
- [Mainframed](https://github.com/mainframed) — Mainframe security tools by Soldier of FORTRAN
- [TK5](https://www.prince-webdesign.nl/tk5) — MVS 3.8j Turnkey distribution

## Lineage

This work builds on trust-boundary and assessment models I've been writing about since 2018 in the context of Active Directory and enterprise systems. The mainframe environment makes those same failure modes explicit, and this tool serves as a reference implementation of that model.

The insight is durable. I've been applying it across platforms for years. The tooling has simply caught up.

## License

MIT
