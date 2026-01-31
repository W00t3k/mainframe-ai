# Mainframe AI Assistant

A comprehensive, locally-hosted AI-powered platform for mainframe operations, security education, and trust relationship analysis. Built for security professionals who need to understand IBM mainframe systems.

## Features

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **TN3270 Terminal** | Full 3270 terminal emulation via BIRP v2 |
| **AI Chat** | Local LLM (Ollama default, pluggable backend) for mainframe Q&A |
| **Red Team Tutor** | Guided learning paths for security professionals |
| **Trust Graph** | BloodHound-inspired relationship visualization |
| **RAG Knowledge Base** | Retrieval-augmented generation with mainframe docs |
| **MCP Server** | Model Context Protocol for Claude Desktop (optional) |
| **Network Scanner** | Discover TN3270 services on networks |

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
│  BIRP v2      │ │  LLM       │ │ Trust      │ │  RAG Engine        │
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
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Optional: Install MCP for Claude Desktop integration
pip install mcp

# Start Ollama (in another terminal)
ollama serve

# Pull the model (first time only)
ollama pull llama3.1:8b

# Start the web app
python web_app.py
```

### Access Points

| URL | Description |
|-----|-------------|
| http://127.0.0.1:8080 | Landing page |
| http://127.0.0.1:8080/tutor | Red Team Tutor |
| http://127.0.0.1:8080/terminal | TN3270 Terminal |
| http://127.0.0.1:8080/chat | AI Chat |
| http://127.0.0.1:8080/graph | Trust Graph |
| http://127.0.0.1:8080/rag | Knowledge Base |

### Demo Without a Mainframe

You can use `/chat`, `/tutor`, `/graph`, and `/rag` without a live TN3270 connection.
The `/terminal` page requires a TN3270 target (TK5 or a real mainframe).

### Screenshots / Demo Media

Add 2–4 visuals before publishing a blog post. Suggested captures:

- `/terminal` with the floating chat panel
- `/tutor` learning path screen
- `/graph` trust graph view
- `/chat` answer explaining an ABEND

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
- z/OS concepts
- ABEND code database
- JCL templates
- TSO/ISPF guides

### 6. MCP Server (`mcp_server.py`)

Model Context Protocol server for Claude Desktop integration.

**Setup (Claude Desktop):**

Add to `~/.config/claude/claude_desktop_config.json`:
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
├── web_app.py              # FastAPI main application
├── agent_tools.py          # Shared tool definitions
├── trust_graph.py          # Graph data model + queries
├── graph_tools.py          # Parsers + agent loops
├── rag_engine.py           # RAG with file-based embeddings
├── mcp_server.py           # MCP server for Claude Desktop
├── mainframe_assistant.py  # CLI interface (alternative)
│
├── birpv2_modules/         # BIRP v2 TN3270 toolkit
│   ├── emulator/           # WrappedEmulator
│   ├── core/               # Screen, Field models
│   └── zos/                # TSO, CICS, JES helpers
│
├── templates/              # Jinja2 HTML templates
│   ├── base.html
│   ├── index.html          # Landing page
│   ├── tutor.html          # Red Team Tutor
│   ├── terminal.html       # TN3270 Terminal
│   ├── chat.html           # AI Chat
│   ├── graph.html          # Trust Graph
│   └── rag.html            # Knowledge Base
│
├── static/
│   ├── css/pages/          # Page-specific styles
│   └── js/                 # JavaScript utilities
│
├── rag_data/               # RAG storage
│   ├── documents/          # Uploaded docs
│   └── embeddings/         # Vector store
│
├── trust_graph_data/       # Graph persistence
│   └── graph.json
│
└── screencaps/             # Captured screens
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

This system is designed for TK5 (MVS 3.8J under Hercules).

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

- **BIRP v2** - TN3270 terminal emulation framework
- **TK5/Hercules** - MVS 3.8J emulation
- **Ollama** - Local LLM inference
- **D3.js** - Graph visualization
- **BloodHound** - Inspiration for trust graph concept
