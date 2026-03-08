# Mainframe AI Assistant

A comprehensive, locally-hosted AI-powered platform for mainframe operations, security education, and trust relationship analysis. Built for security professionals who need to understand IBM mainframe systems. Features a retro IBM Lumon-style CRT interface with live TN3270 terminal overlay, click-to-analyze AI, and hover-reveal contextual hints.

## Features

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **TN3270 Terminal** | Full 3270 terminal emulation with AI-powered screen analysis |
| **AI Chat** | Local LLM (Ollama default, pluggable backend) for mainframe Q&A |
| **Red Team Tutor** | Guided learning paths for security professionals |
| **Trust Graph** | BloodHound-inspired relationship visualization |
| **Test & Report** | Pentest findings engine with professional report generation |
| **Abstract Models** | Interactive mental model explorer with click-to-map |
| **RAG Knowledge Base** | Retrieval-augmented generation with mainframe docs |
| **Security Labs** | Hands-on exercises for mainframe security skills |
| **Network Scanner** | Discover TN3270 services on networks |
| **MCP Server** | Model Context Protocol for Ollama Desktop (optional) |
| **Presentation Slides** | Built-in slide deck for talks and training |

### What Makes This Different

- **Local by Default**: No API keys required unless you choose a cloud backend. Ollama runs locally.
- **Security-Focused**: Designed for understanding trust boundaries, not exploitation.
- **Educational**: Every feature teaches mainframe mental models.
- **Graph-Based**: Visualize relationships like BloodHound does for AD.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Web Interface (FastAPI)                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ Terminal │ │   Chat   │ │  Tutor   │ │  Graph   │ │   RAG    │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘  │
└───────┼────────────┼────────────┼────────────┼────────────┼────────┘
        │            │            │            │            │
        ▼            ▼            ▼            ▼            ▼
┌───────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────────────┐
│  TN3270 v2      │ │  LLM       │ │ Trust      │ │  RAG Engine        │
│  (TN3270)     │ │  (Ollama)  │ │ Graph      │ │  (Embeddings)      │
│               │ │            │ │            │ │                    │
│ WrappedEmulator │ llama3.1:8b │ │ Nodes/Edges│ │ File-based vectors │
└───────┬───────┘ └────────────┘ └────────────┘ └────────────────────┘
        │
        ▼
┌───────────────┐
│  TK5 / MVS    │
│  (Hercules)   │
│  Port 3270    │
└───────────────┘
```

---

## Installation

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai) with `llama3.1:8b` model
- [TK5](http://wotho.ethz.ch/tk4-/) for MVS 3.8J emulation (optional but recommended)

### Quick Start

```bash
# Clone/navigate to the project
cd mainframe_ai_assistant

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Optional: Install MCP for Ollama Desktop integration
pip install mcp

# Start Ollama (in another terminal)
ollama serve

# Pull the model (first time only)
ollama pull llama3.1:8b

# Start the web app
python run.py
```

### Access Points

| URL | Description |
|-----|-------------|
| http://127.0.0.1:8080 | Home — retro CRT terminal with live overlay |
| http://127.0.0.1:8080/terminal | Full-screen TN3270 terminal |
| http://127.0.0.1:8080/walkthrough | Autonomous walkthroughs |
| http://127.0.0.1:8080/tutor | Red Team Tutor |
| http://127.0.0.1:8080/graph | Trust Graph |
| http://127.0.0.1:8080/recon | Test & Report |
| http://127.0.0.1:8080/labs | Security Labs |
| http://127.0.0.1:8080/chat | AI Chat |
| http://127.0.0.1:8080/abstract-models | Abstract Models |
| http://127.0.0.1:8080/scanner | Network Scanner |
| http://127.0.0.1:8080/rag | Knowledge Base |
| http://127.0.0.1:8080/architecture | Architecture |
| http://127.0.0.1:8080/docs | API Docs |
| http://127.0.0.1:8080/slides | Presentation Slides |

### Demo Without a Mainframe

You can use `/chat`, `/tutor`, `/graph`, and `/rag` without a live TN3270 connection.
The `/terminal` page requires a TN3270 target (TK5 or a real mainframe).

### Screenshots / Demo Media

Suggested captures for blog posts and presentations:

- `/` — retro CRT home screen with live terminal overlay
- `/terminal` — full-screen TN3270 with AI chat panel
- `/tutor` — Red Team Tutor learning path
- `/graph` — trust graph visualization
- `/recon` — Test & Report findings view
- `/abstract-models` — mental model mapping

Place assets under `docs/assets/` (see `docs/assets/README.md` for naming).

---

## Components

### 1. Red Team Tutor (`/tutor`)

Guided learning system for security professionals new to mainframes.

**Learning Paths:**

| Path | What You Learn |
|------|----------------|
| Session Stack | VTAM → TSO → ISPF layers, how sessions differ from SSH |
| Batch Execution | JCL → JES → Initiator trust model, delayed execution |
| Dataset Trust | DISP parameters, access patterns, blast radius |
| Panel Navigation | Implicit access control through menu structure |
| Job Tracing | Execution chains, program loading, STEPLIB |

**Teaching Philosophy:**
- Never skip steps for speed
- Correct Unix/cloud assumptions explicitly
- Explain trust boundaries at every transition
- Relate to modern security concepts (control planes, blast radius)

### 2. Trust Graph (`/graph`)

BloodHound-inspired visualization of mainframe relationships.

**Node Types:**

| Type | Description | Example |
|------|-------------|---------|
| EntryPoint | VTAM logon screen | TSO, CICS applid |
| Panel | ISPF/TSO panel | ISR@PRIM, ISRUDSL |
| Job | Batch job | MYJOB01 |
| Program | Executable module | IEBGENER, IKJEFT01 |
| Dataset | MVS dataset | SYS1.PARMLIB |
| Loadlib | Load library | SYS1.LINKLIB |
| Proc | JCL procedure | ASMHCL |
| ReturnCode | Observed RC/ABEND | RC=0000, S0C7 |

**Edge Types:**

| Edge | Meaning |
|------|---------|
| NAVIGATES_TO | Panel transition (PF key/command) |
| EXECUTES | Job runs program |
| READS | Job reads dataset |
| WRITES | Job writes dataset |
| LOADS_FROM | Program loaded from library |
| CALLS_PROC | Job invokes procedure |
| RETURNED | Job completion code |

**Built-in Queries:**

1. `paths_to_job_submit` - Interactive paths to job submission
2. `library_load_chain` - Job → Program → Loadlib chains
3. `shared_datasets` - Datasets with multiple accessors
4. `dataset_conflicts` - Read/write conflicts
5. `boundary_crossings` - Environment transitions
6. `abend_chains` - Failed execution paths

### 3. AI Chat (`/chat`)

Conversational interface powered by Ollama by default (pluggable backend).

**Capabilities:**
- Explain ABEND codes (S0C7, S0C4, S913, etc.)
- Generate JCL templates
- Debug batch jobs
- Explain screen content
- Navigate TSO/ISPF

**Slash Commands:**

| Command | Action |
|---------|--------|
| `/connect host:port` | Connect to mainframe |
| `/disconnect` | Disconnect |
| `/screen` | Show current screen |
| `/model name` | Change LLM model |
| `/clear` | Clear history |
| `/help` | Show help |

### 4. TN3270 Terminal (`/terminal`)

Full terminal emulation with floating AI chat panel.

**Keyboard Shortcuts:**
- Enter, Tab, Escape (Clear)
- F1-F12 (PF1-PF12)
- Shift+F1-F12 (PF13-PF24)
- Ctrl+R (Reset)

**Features:**
- Draggable/resizable chat panel
- Screen capture
- WebSocket real-time updates

### 5. RAG Knowledge Base (`/rag`)

File-based retrieval-augmented generation.

**Supported Sources:**
- Text files (.txt)
- PDF documents (.pdf)
- Markdown (.md)

**Built-in Knowledge:**
- Mainframe concepts
- ABEND code database
- JCL templates
- TSO/ISPF guides

### 6. MCP Server (`mcp_server.py`)

Model Context Protocol server for Ollama Desktop integration.

**Setup (Ollama Desktop):**

Add to `~/.config/ollama/ollama_desktop_config.json`:
```json
{
  "mcpServers": {
    "mainframe-assistant": {
      "command": "python",
      "args": ["/path/to/mainframe_ai_assistant/mcp_server.py"]
    }
  }
}
```

**Exposed Tools:**
- `connect_mainframe` / `disconnect_mainframe`
- `read_screen` / `send_text` / `send_enter` / `send_pf_key`
- `query_knowledge_base`
- `classify_panel` / `extract_identifiers`
- `parse_jcl` / `ingest_to_graph` / `query_graph`

**Exposed Resources:**
- `mainframe://screen` - Current terminal screen
- `mainframe://status` - Connection status
- `mainframe://graph/stats` - Graph statistics
- `mainframe://graph/export` - Full graph export

---

## File Structure

```
mainframe_ai_assistant/
├── run.py                  # Application entry point
├── app/                    # Modular FastAPI application
│   ├── routes/             # API endpoints (14 modules)
│   ├── services/           # Business logic
│   ├── constants/          # Prompts, walkthroughs, paths
│   └── models/             # Pydantic schemas
├── agent_tools.py          # TN3270 connection tools
├── trust_graph.py          # Graph data model + queries
├── graph_tools.py          # Parsers + agent loops
├── rag_engine.py           # RAG with file-based embeddings
├── recon_engine.py         # Enumeration and findings engine
├── methodology_engine.py   # Assessment methodology
├── mcp_server.py           # MCP server for Ollama Desktop
├── ai_bridge.py            # CICS AI bridge
├── mainframe_assistant.py  # CLI interface (alternative)
│
├── templates/              # Jinja2 HTML templates (16 pages)
│   ├── base.html           # Base template
│   ├── index.html          # Home — retro CRT terminal
│   ├── terminal.html       # Full-screen TN3270
│   ├── tutor.html          # Red Team Tutor
│   ├── chat.html           # AI Chat
│   ├── graph.html          # Trust Graph
│   ├── recon.html          # Test & Report
│   ├── abstract_models.html # Abstract Models
│   ├── scanner.html        # Network Scanner
│   ├── rag.html            # Knowledge Base
│   └── slides.html         # Presentation Slides
│
├── static/
│   ├── css/pages/          # Per-page stylesheets
│   ├── img/                # IBM logos, retro terminal image
│   ├── fonts/              # IBM Plex Mono, IBM Plex Sans
│   └── js/                 # JavaScript utilities
│
├── slides/                 # Presentation assets
│   ├── screenshots/        # Slide images
│   └── ocr/                # OCR text from slides
│
├── lab_data/               # Lab exercise definitions (JSON)
├── trust_graph_data/       # Graph persistence
├── kicks/                  # CICS/KICKS BMS, COBOL, JCL
└── tk5/                    # TK5 MVS 3.8j emulator
```

---

## API Reference

### Terminal API

```
POST /api/terminal/connect   {"target": "localhost:3270"}
POST /api/terminal/disconnect
POST /api/terminal/key       {"key_type": "enter|pf|string", "value": "..."}
GET  /api/screen
GET  /api/status
```

### Chat API

```
POST /api/chat               {"message": "What is ABEND S0C7?"}
```

### Graph API

```
GET  /api/graph/stats
GET  /api/graph/nodes
GET  /api/graph/edges
GET  /api/graph/query/{name}
POST /api/graph/ingest-jcl   {"jcl": "//JOB..."}
POST /api/graph/ingest-sysout {"sysout": "..."}
POST /api/graph/ingest-screen
GET  /api/graph/export/json
GET  /api/graph/export/dot
GET  /api/graph/export/d3
```

### Tutor API

```
POST /api/tutor/analyze      {"goal": "session-stack"}
POST /api/tutor/suggest      {"goal": "batch-execution"}
POST /api/tutor/ask          {"question": "...", "goal": "..."}
```

### RAG API

```
GET  /api/rag/stats
GET  /api/rag/documents
POST /api/rag/init
POST /api/rag/upload         (multipart file)
POST /api/rag/query          {"query": "...", "n_results": 3}
DELETE /api/rag/document/{id}
```

---

## Trust Graph Schema

### Node Properties

```python
@dataclass
class GraphNode:
    id: str               # Deterministic hash of type+key
    node_type: str        # EntryPoint, Panel, Job, Program, Dataset, etc.
    label: str            # Human-readable name
    properties: dict      # Type-specific fields
    source_evidence: list # [{screen_hash, timestamp, raw_text}]
    first_seen: str
    last_seen: str
```

### Edge Properties

```python
@dataclass
class GraphEdge:
    id: str
    edge_type: str        # NAVIGATES_TO, EXECUTES, READS, WRITES, etc.
    source_id: str
    target_id: str
    properties: dict      # {pf_key, command, disp, etc.}
    evidence: list
    confidence: float     # 0.0-1.0
```

---

## Red Team Tutor Philosophy

The tutor operates on these principles:

1. **Legibility over Speed**: Make mainframe concepts understandable, not automated.

2. **Mental Model Correction**: Explicitly address assumptions from Unix/cloud backgrounds:
   - "Mainframes don't have filesystems like Unix"
   - "Batch jobs are not background processes"
   - "Logon is not SSH"

3. **Trust Boundary Awareness**: Every screen transition crosses a boundary:
   - VTAM → TSO (authentication boundary)
   - TSO → ISPF (subsystem boundary)
   - Interactive → Batch (execution model boundary)

4. **Historical Context**: Explain WHY designs exist, not just what they do.

5. **Red Team Relevance**: Relate concepts to modern security thinking:
   - Control planes vs data planes
   - Blast radius of access
   - Delayed execution implications
   - Implicit vs explicit access control

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `llama3.1:8b` | Default LLM model |

You can point `OLLAMA_URL` to any Ollama-compatible `/api/chat` server. For non-Ollama backends, add a small adapter in `web_app.py`.

---

## TK5 Integration

This system is designed for TK5 (MVS 3.8j under Hercules).

**Starting TK5:**
```bash
cd /path/to/tk5/mvs-tk5
./mvs_osx  # or ./mvs on Linux
```

**Default Connection:** `localhost:3270`

**What's Available in TK5:**
- TSO/ISPF
- JES2
- Batch execution
- Dataset management

**What's NOT in TK5:**
- DB2
- CICS
- IMS
- Modern z/OS features

---

## Contributing

This is a defensive security education tool. Contributions should:

1. Enhance understanding of mainframe systems
2. Improve trust boundary visualization
3. Add educational content
4. NOT add exploitation capabilities

---

## License

Educational use. See LICENSE file.

---

## Acknowledgments

- **py3270** - TN3270 terminal emulation
- **TK5/Hercules** - MVS 3.8J emulation
- **Ollama** - Local LLM inference
- **D3.js** - Graph visualization
- **BloodHound** - Inspiration for trust graph concept
