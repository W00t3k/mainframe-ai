# Mainframe AI Assistant

## See It Running

**[▶ Live Demo & Project Page](https://w00t3k.github.io/mainframe-ai/)**

> Watch the tool connect to a live MVS 3.8j system, navigate control planes, 
> and map trust relationships in real time. No setup required to explore.
**A reference implementation for trust-boundary assessment on mainframe systems.**

This tool operationalizes a mental model I've been applying since 2018 — first to Active Directory and enterprise Windows environments, now to mainframe systems. The model isn't new. The tool is.

## The Problem

Most offensive security methodologies import assumptions from Unix, Windows, and cloud environments. These assumptions fail on mainframe operating systems:

| Assumption | Reality on Mainframe |
|------------|----------------------|
| "Ports define exposure" | VTAM session fabric exists independently of TCP/IP. Sessions outlive connections. |
| "There is a root user" | RACF distributes authority across profiles. No omnipotent account exists. |
| "Processes are short-lived" | Address spaces persist for weeks or months. Identity is bound at startup. |
| "Work executes immediately" | JES queues, schedules, and defers execution. Identity preserved from submission. |
| "There is a filesystem" | Datasets, catalogs, PDS members. No `/etc`, no hierarchy. |

**Assessments that import these assumptions miss the real attack surface.**

This is the same failure mode I wrote about in 2018 regarding Active Directory — attackers succeed not because of exploits, but because defenders misunderstand where authority is actually enforced. ADCS, delegation abuse, service account sprawl — these weren't "new vulnerabilities." They were trust boundaries that existed all along, invisible to teams using the wrong mental model.

Mainframes expose this more clearly because security is explicitly federated across six control planes:

1. **VTAM** — Session fabric
2. **TSO** — Human interaction
3. **RACF** — Authorization engine
4. **JES** — Deferred execution
5. **CICS** — Transaction processing
6. **PR/SM** — Hardware partitioning (LPARs, HMC, Coupling Facilities)

If you bring the wrong mental model, you miss the real attack paths — just like people missed delegation abuse for years.

## What This Tool Does

- **Retro IBM Home Screen** — A Lumon-style CRT terminal image with a live TN3270 overlay. Click any line on the terminal for instant AI analysis. Hover over any UI element for contextual descriptions. Invisible toolbar reveals on hover or scroll-up.

- **Autonomous Walkthroughs** — Watch the tool connect, navigate, and narrate VTAM, TSO, ISPF, JES, and RACF. No keyboard needed. Educational narration explains what's happening at each control plane boundary.

- **Trust Graph** — BloodHound-style visualization of mainframe trust relationships. Map identities, datasets, jobs, and their connections.

- **Red Team Tutor** — AI-guided learning paths for mainframe security assessment. Ask questions, get contextual help on the current screen.

- **Test & Report** — TSO/CICS/VTAM enumeration, hidden field detection, application mapping, and professional pentest report generation with findings-based methodology.

- **Abstract Models** — Interactive mental model explorer. Click terminal lines to map them against six abstract security models (Session Stack, Control Planes, Artifacts & Evidence, Trust Boundaries, Batch vs Interactive, Graph Thinking).

- **Security Labs** — Deterministic walkthroughs you can run offline. Replay VTAM → TSO → ISPF flows and batch execution patterns.

- **RAG Knowledge Base** — Upload and query mainframe documentation with retrieval-augmented generation.

- **Network Scanner** — Discover TN3270 services on target networks.

- **COBOL Development** — Complete compile-link-go walkthrough demonstrating the batch-oriented development lifecycle.

**100% local. No API keys. No cloud dependencies.** Uses Ollama for local LLM inference.

## Quick Start

### Requirements

- Python 3.11+
- [Ollama](https://ollama.com) for local LLM
- s3270 (for web TN3270 terminal)
- TK5 MVS 3.8j emulator (included)

---

### Platform Comparison

| | **macOS** | **Linux** |
|---|---|---|
| **Install** | Manual (brew + pip) | One-command (`./install.sh`) |
| **Hercules binary** | `hercules/darwin/bin` | `hercules/linux/64/bin` |
| **TN3270 client** | `brew install x3270` | `apt install s3270` |
| **Ollama** | Desktop app or `brew install ollama` | `curl -fsSL https://ollama.com/install.sh \| sh` |
| **Python** | System python3 or pyenv | `apt install python3 python3-venv` |
| **RAM model** | 16GB+ → `llama3.1:8b` | Auto-detected by `start.sh` |
| **Tested on** | macOS 14+ (Apple Silicon) | Ubuntu 24.04, Debian 12, Kali, Fedora, Arch |
| **Shared lib path** | `DYLD_LIBRARY_PATH` | `LD_LIBRARY_PATH` |

`start.sh` auto-detects the platform and uses the correct Hercules binary, library paths, and Python environment. No manual configuration needed.

---

### Linux — One-Command Install

The install script handles everything: system deps, Python, Ollama, GitHub CLI auth, repo clone, venv, and TK5.

```bash
# If you already have the repo cloned:
cd mainframe-ai
chmod +x install.sh start.sh mvs.sh
./install.sh

# If starting fresh on a new server (private repo — requires GitHub access):
# Option 1: GitHub CLI
sudo apt install gh -y && gh auth login
gh repo clone W00t3k/mainframe-ai && cd mainframe-ai
chmod +x install.sh start.sh mvs.sh && ./install.sh

# Option 2: Personal Access Token
git clone https://<YOUR_TOKEN>@github.com/W00t3k/mainframe-ai.git
cd mainframe-ai && chmod +x install.sh start.sh mvs.sh && ./install.sh

# Option 3: SSH
git clone git@github.com:W00t3k/mainframe-ai.git
cd mainframe-ai && chmod +x install.sh start.sh mvs.sh && ./install.sh
```

Supported distros: **Ubuntu, Debian, Kali, Fedora, CentOS/RHEL, Arch, openSUSE**.

The install script installs:
- Python 3.11+ with virtual environment
- Ollama + auto-selected model based on RAM
- GitHub CLI (`gh`) with interactive auth
- s3270/x3270/c3270 (TN3270 clients)
- Hercules + TK5 MVS emulator
- All Python dependencies

---

### macOS — Manual Setup

```bash
# Install Ollama
brew install ollama
ollama serve &
ollama pull llama3.1:8b

# Install TN3270 client
brew install x3270

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start everything
./start.sh
```

---

### Start the App (One Command)

```bash
./start.sh                # Start ALL services (Ollama + TK5 + Web App)
./start.sh --no-mvs       # Start without TK5 mainframe
./start.sh --no-ollama    # Start without Ollama AI
./start.sh --kill         # Stop all services
./start.sh --status       # Health check dashboard
```

`start.sh` does everything:
1. **Kills** any existing processes
2. **Starts Ollama** with memory-saving settings (`OLLAMA_KEEP_ALIVE=5m`)
3. **Starts TK5 Hercules** with correct binary for your OS/arch
4. **Starts the web app** with auto-detected Python venv
5. **Health-checks** each service with `curl`
6. **Shows a status dashboard** with green/red indicators
7. **Watchdog** monitors the web app and auto-restarts on crash

#### Auto-Detected Model Based on RAM

| Server RAM | Model Selected | VRAM Usage |
|------------|---------------|------------|
| 16GB+ | `llama3.1:8b` | ~5 GB |
| 8–16GB | `llama3.2:3b` | ~2 GB |
| <8GB | `tinyllama` | ~700 MB |

The model only loads into memory when someone asks an AI question, and unloads after 5 minutes of inactivity.

#### Logs

All logs go to the `logs/` directory:
- `logs/webapp.log` — Web application
- `logs/ollama.log` — Ollama AI backend
- `logs/hercules.log` — TK5 Hercules emulator

---

### Firewall (Remote Servers)

If running on a remote server, open the required ports:

```bash
# Ubuntu/Debian
sudo ufw allow 8080    # Web app
sudo ufw allow 3270    # TN3270 (if connecting directly)

# CentOS/RHEL/Fedora
sudo firewall-cmd --add-port=8080/tcp --permanent
sudo firewall-cmd --add-port=3270/tcp --permanent
sudo firewall-cmd --reload
```

---

### MVS TK5 Management

Three ways to run TK5, depending on your needs:

| Script | Mode | Use Case |
|--------|------|----------|
| `./start.sh` | Background (all services) | Production — starts Ollama + TK5 + Web App with watchdog |
| `./mvs.sh start` | Background (TK5 only) | Manage TK5 independently with start/stop/restart/status |
| `./start_mvs.sh` | Foreground (interactive) | Debug — see Hercules console output directly |

#### `mvs.sh` — TK5 Management

```bash
./mvs.sh start          # Start MVS TK5 (background)
./mvs.sh stop           # Graceful shutdown (SIGTERM, waits 15s)
./mvs.sh kill           # Force kill all Hercules processes
./mvs.sh restart        # Stop + Start
./mvs.sh status         # Show PID, ports, memory, uptime
./mvs.sh log            # Tail the Hercules log
```

#### `start_mvs.sh` — Interactive Mode

```bash
./start_mvs.sh          # Runs Hercules in foreground (Ctrl+C to stop)
```

TK5 defaults:
- **TN3270:** `localhost:3270`
- **Login:** `HERC01` / `CUL8TR`
- **Hercules console:** `http://localhost:8038`
- **Logs:** `logs/hercules.log`

---

### Verify

```bash
curl http://localhost:8080/api/status
```

Open in browser:

| URL | Feature |
|-----|---------|
| `http://localhost:8080/` | Home — retro CRT terminal with live overlay |
| `http://localhost:8080/terminal` | Full-screen TN3270 terminal |
| `http://localhost:8080/walkthrough` | Autonomous walkthroughs |
| `http://localhost:8080/tutor` | Red Team Tutor |
| `http://localhost:8080/graph` | Trust graph visualization |
| `http://localhost:8080/recon` | Test & Report (pentest findings) |
| `http://localhost:8080/labs` | Security labs |
| `http://localhost:8080/chat` | AI Chat |
| `http://localhost:8080/abstract-models` | Abstract mental models |
| `http://localhost:8080/scanner` | Network scanner |
| `http://localhost:8080/rag` | RAG Knowledge Base |
| `http://localhost:8080/architecture` | System architecture |
| `http://localhost:8080/docs` | API documentation |
| `http://localhost:8080/slides` | Presentation slides |
| `http://localhost:8080/presentation` | Teaching presentation |
| `http://localhost:8080/abstract` | Conference abstract |

## Walkthroughs

Thirteen autonomous walkthroughs demonstrate mainframe control planes:

| Walkthrough | What It Teaches |
|-------------|------------------|
| **Quick Demo** | 60-second overview — connect, logon, navigate, logoff |
| **Session Stack** | VTAM → TSO → ISPF layer traversal, identity binding |
| **Deferred Execution** | JCL → JES workflow, jobs run later under submitter identity |
| **System Inspection** | SYS1.PROCLIB, SYS1.PARMLIB — where "config files" live |
| **Authorization Model** | RACF profiles, LISTCAT, how authority is distributed |
| **Dataset Model** | PDS, members, catalogs — no filesystem, just datasets |
| **Address Spaces** | Active jobs, persistent address spaces |
| **COBOL Development** | Compile-link-go lifecycle, batch-oriented programming |
| **System Enumeration** | Full mainframe enumeration — the "nmap" of z/OS |
| **CICS/KICKS** | Transaction processing, BMS maps, COBOL programs |
| **JCL Injection** | Writable PROCLIB exploitation via JCL |
| **Reverse Shell** | MVS-native reverse shell via REXX and WTO |
| **PR/SM & LPARs** | Hardware partitioning, HMC simulation, sysplex (LLM-driven) |

Each walkthrough maps to five core findings areas:

- **F1:** Identity Binding — where is identity bound?
- **F2:** Authority Evaluation — when is authority evaluated?
- **F3:** Deferred Execution — what executes later than expected?
- **F4:** Policy Enforcement — which subsystem enforces policy?
- **F5:** Imported Assumptions — what assumptions are you importing?

The PR/SM walkthrough uses an **LLM-driven HMC simulator** — the AI emulates a production IBM z16 with 6 LPARs, letting you explore hardware partitioning interactively even though TK5 doesn't have real PR/SM.

## The Mental Model

This tool didn't invent the trust-boundary assessment model. It **operationalizes** it.

The same mental model that exposed ADCS abuse, Kerberos delegation attacks, and service account sprawl in Active Directory applies directly to mainframes — but mainframes make the boundaries *explicit*. On a mainframe, you can literally watch identity cross from VTAM to TSO to RACF.

**What changed isn't the model. What changed is that I now have a platform where the same failure modes are even more visible.**

The walkthroughs don't just show you how to navigate ISPF. They show you *where trust decisions happen* and *which assumptions break* at each boundary crossing.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     Web Interface                         │
│     FastAPI + Jinja2 + IBM Plex Mono + Retro IBM UI      │
└─────────────────────────┬────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────┐
│                    app/ (modular)                         │
│  routes/     - API endpoints (14 route modules)           │
│  services/   - Business logic (chat, walkthrough, LLM)    │
│  constants/  - Prompts, paths, walkthrough scripts        │
│  models/     - Pydantic schemas                           │
└──────────┬───────────────────────────┬───────────────────┘
           │                           │
┌──────────▼──────────┐  ┌────────────▼────────────────────┐
│    Ollama (LLM)     │  │   TN3270 Layer (py3270)          │
│  - Q&A              │  │   - Screen reading              │
│  - Narration        │  │   - Command execution           │
│  - Screen analysis  │  │   - Session management          │
│  - Code analysis    │  │   - Click-to-analyze            │
└─────────────────────┘  └─────────────────────────────────┘
```

## Home Screen Features

The home page features a retro IBM Lumon-style CRT terminal with:

- **Live TN3270 overlay** — terminal output rendered directly on the CRT screen image
- **Click-to-analyze** — click any terminal line for instant AI explanation
- **Hover hints** — hover over any button, nav item, or control plane card for contextual descriptions
- **Invisible toolbar** — clean look by default, reveals on hover or scroll-up
- **AI explanation box** — contextual information displayed below the terminal image
- **Collapsible sections** — Control Planes and More Tools expand on click
- **Right panel menu** — hamburger button reveals full navigation

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | Auto-detected by RAM | `llama3.1:8b` (16GB+), `llama3.2:3b` (8-16GB), `tinyllama` (<8GB) |
| `MAINFRAME_HOST` | `localhost:3270` | Default TN3270 target |

## File Structure

```
mainframe-ai/
├── app/                    # Modular FastAPI application
│   ├── routes/             # API endpoints (15 modules)
│   ├── services/           # Business logic (ollama, chat, ftp, kicks, rag_context)
│   ├── constants/          # Prompts, walkthroughs, paths
│   ├── models/             # Pydantic schemas
│   └── websocket/          # Real-time terminal and graph updates
├── templates/              # Jinja2 HTML templates (24 pages)
├── static/                 # CSS, JS, fonts, images
│   ├── css/pages/          # Per-page stylesheets
│   ├── img/                # IBM logos, retro terminal image
│   └── fonts/              # IBM Plex Mono, IBM Plex Sans
├── docs/                   # Extended docs, demo data, media
├── slides/                 # Presentation assets
│   ├── screenshots/        # Slide images
│   └── ocr/                # OCR text from slides
├── lab_data/               # Lab exercise definitions (JSON)
├── jcl/                    # JCL files (FTPD, USS screen, KICKS)
├── kicks/                  # CICS/KICKS BMS maps, COBOL, JCL
├── trust_graph_data/       # Graph persistence
├── tk5/                    # TK5 MVS 3.8j emulator
├── logs/                   # Runtime logs (webapp, ollama, hercules)
├── run.py                  # Application entry point
├── start.sh                # One-script launcher (all services + health checks)
├── start_mvs.sh            # TK5 foreground/interactive mode
├── install.sh              # Linux installer (deps, Ollama, venv, TK5)
├── mvs.sh                  # MVS TK5 management (start/stop/restart/status)
├── kill.sh                 # Stop all services
├── agent_tools.py          # TN3270 connection tools
├── trust_graph.py          # Graph data structures
├── graph_tools.py          # Graph analysis and parsing
├── recon_engine.py         # Enumeration and findings engine
├── rag_engine.py           # RAG with local embeddings
├── methodology_engine.py   # Assessment methodology
├── tn3270_discovery.py     # TN3270 network discovery engine
├── mcp_server.py           # Model Context Protocol server
├── ai_bridge.py            # CICS AI bridge
└── graph_automation.py     # Graph automation utilities
```

## CICS AI Assistant

**"CICS as an interface to modern intelligence"** — not AI on the mainframe, but mainframe as control plane.

A demonstration CICS transaction (`AIMP`) that connects a 3270 terminal to an AI backend:

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│ 3270 Screen │ ───▶ │ KICKS/CICS  │ ───▶ │ AI Bridge   │
│   (BMS)     │      │  (COBOL)    │      │  (Python)   │
└─────────────┘      └─────────────┘      └─────────────┘
```

### Quick Start

```bash
# Start AI Bridge
python ai_bridge.py --port 5000

# In KICKS
AIMP
```

See [CICS_AI_ASSISTANT.md](docs/CICS_AI_ASSISTANT.md) for full documentation.

---

## KICKS (CICS) Installation

KICKS is a CICS-compatible transaction processing system for MVS 3.8j. This project includes complete automation for installing KICKS on TK5.

### Quick Install

```bash
# Check status and run all steps interactively
python install_kicks.py all

# Or run individual steps
python install_kicks.py status    # Check prerequisites
python install_kicks.py dasd      # Create KICKS0 volume
python install_kicks.py catalog   # Create user catalog
python install_kicks.py upload    # Upload XMIT file
python install_kicks.py unpack    # Unpack 26 datasets
python install_kicks.py testdata  # Create test VSAM files
```

### Start KICKS

```
EXEC 'KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)'
```

### Included Resources

| Resource | Location |
|----------|----------|
| Full installation guide | `docs/KICKS_INSTALLATION.md` |
| Pre-configured JCL | `jcl/kicks/` |
| XMIT file | `kicks_install/kicks-master/kicks-tso-v1r5m0/kicks-tso-v1r5m0.xmi` |
| Automation script | `install_kicks.py` |

See [KICKS_INSTALLATION.md](docs/KICKS_INSTALLATION.md) for the complete step-by-step guide.

## Related Work

- [py3270](https://pypi.org/project/py3270/) — Python TN3270 library
- [Mainframed](https://github.com/mainframed) — Mainframe security tools by Soldier of FORTRAN
- [TK5](https://www.prince-webdesign.nl/tk5) — MVS 3.8j Turnkey distribution
- [KICKS](http://www.kicksfortso.com/) — CICS-compatible transaction processing for MVS 3.8j

## Lineage

This work builds on trust-boundary and assessment models I've been writing about since 2018 in the context of Active Directory and enterprise systems. The mainframe environment makes those same failure modes explicit, and this tool serves as a reference implementation of that model.

The insight is durable. I've been applying it across platforms for years. The tooling has simply caught up.

## License

MIT
