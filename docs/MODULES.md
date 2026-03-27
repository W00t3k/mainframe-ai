# Core Python Modules

Python modules in `tools/` that power core capabilities. These are imported lazily by `app/` at runtime via `sys.path` (configured in `run.py`).

## Module Overview

| Module | Location | Purpose |
|--------|----------|---------|
| `run.py` | root | Uvicorn launcher — starts FastAPI on configurable host/port/model |
| `agent_tools.py` | `tools/` | TN3270 connection, screen reading, keystroke sending, tool definitions for LLM |
| `trust_graph.py` | `tools/` | BloodHound-style graph — nodes (users, datasets, jobs) + edges (reads, writes, executes) |
| `graph_tools.py` | `tools/` | JCL/SYSOUT parsers, screen classifiers, graph population utilities |
| `graph_automation.py` | `tools/` | Auto-populate graph from live terminal navigation |
| `rag_engine.py` | `tools/` | Local RAG — document chunking, embedding, similarity search (no external DB) |
| `recon_engine.py` | `tools/` | TSO/CICS/VTAM enumeration, hidden field detection, pentest report generation |
| `methodology_engine.py` | `tools/` | F1–F5 findings framework, 6 control planes (TSO, JES, RACF, CICS, VTAM, PR/SM) |
| `mcp_server.py` | `tools/` | Model Context Protocol server for Claude Desktop / external AI clients |
| `ai_bridge.py` | `tools/` | TCP bridge: KICKS/CICS COBOL transactions ↔ Ollama LLM |
| `mainframe_assistant.py` | `tools/` | CLI REPL — interactive mainframe Q&A without web UI |
| `tn3270_discovery.py` | `tools/` | Internet-scale TN3270 scanner (Shodan, nmap, masscan) |
| `install_kicks.py` | `tools/` | Multi-step KICKS installation automation |
| `web_app.py` | `tools/` | Legacy monolithic web app (superseded by `app/`) |

---

## `run.py`
**Entry Point**

Starts the FastAPI application server via Uvicorn.

```bash
python run.py --host 127.0.0.1 --port 8080 --model llama3.1:8b
```

---

## `tools/agent_tools.py`
**TN3270 Connection & Tools**

Manages the TN3270 terminal connection and defines tools for the agentic loop:
- `connect_mainframe()` - Establish TN3270 session
- `disconnect_mainframe()` - Close session
- `read_screen()` - Get current screen text
- `send_terminal_key()` - Send keystrokes (Enter, PF keys, text)
- `capture_screen()` - Save screen to file
- `TOOL_DEFINITIONS` - OpenAI-style tool schemas for LLM

---

## `tools/trust_graph.py`
**Trust Relationship Graph**

BloodHound-inspired graph for mainframe trust relationships:
- **Node Types**: EntryPoint, Panel, Job, Program, Dataset, Transaction, etc.
- **Edge Types**: NAVIGATES_TO, EXECUTES, READS, WRITES, LOADS_FROM, etc.
- **Queries**: Shortest paths, shared datasets, boundary crossings
- **Export**: JSON, DOT (Graphviz), D3.js format

---

## `tools/graph_tools.py`
**Graph Analysis Utilities**

Parsing and analysis tools for populating the trust graph:
- `parse_jcl()` - Extract jobs, steps, datasets from JCL
- `parse_sysout()` - Parse job output for execution details
- `classify_panel()` - Identify ISPF panel types
- `update_graph_from_*()` - Ingest data into graph
- `ScreenMapperAgent` - AI-assisted screen classification
- `BatchTrustAgent` - Batch job relationship analysis

---

## `tools/rag_engine.py`
**Retrieval-Augmented Generation**

Local vector store for mainframe documentation:
- Document chunking and embedding
- Similarity search for context retrieval
- Built-in knowledge base initialization
- File-based persistence (no external DB)

---

## `tools/recon_engine.py`
**Test & Report Engine**

Native Python implementation of mainframe enumeration and findings:
- `TSOEnumerator` - TSO userid enumeration
- `CICSEnumerator` - CICS transaction enumeration
- `VTAMEnumerator` - VTAM APPLID discovery
- `HiddenFieldDetector` - Find hidden screen fields
- `ScreenAnalyzer` - Security findings detection (regex-based)
- `ApplicationMapper` - Map application paths
- Report generation in JSON, Markdown, and HTML formats

---

## `tools/mcp_server.py`
**Model Context Protocol Server**

MCP server for external AI tool integration:
- Exposes mainframe tools via MCP protocol
- Enables Claude Desktop and other MCP clients
- Tool definitions for connect, read, send, capture

---

## `tools/mainframe_assistant.py`
**CLI Interface**

Command-line chat interface for the assistant:
- Interactive REPL for mainframe questions
- Direct terminal without web UI
- Useful for scripting and automation

---

## `tools/methodology_engine.py`
**Assessment Methodology**

Findings-based assessment framework:
- Five core findings areas (F1–F5): Identity Binding, Authority Evaluation, Deferred Execution, Policy Enforcement, Imported Assumptions
- Maps screen observations to findings categories
- Supports report generation organized by findings

---

## `tools/ai_bridge.py`
**CICS AI Bridge**

Python bridge connecting KICKS/CICS transactions to the AI backend:
- Listens for requests from COBOL programs via TCP
- Routes queries to Ollama for LLM inference
- Returns responses formatted for 3270 screen display

---

## `tools/graph_automation.py`
**Graph Automation**

Automated graph population from live terminal sessions:
- Screen-to-graph ingestion
- Automatic node/edge creation from navigation
- Batch processing of captured screens

---

## Legacy File

### `tools/web_app.py`
**⚠️ Legacy monolithic application**

This file contains an older, monolithic version of the application. The modular `app/` directory structure is now the primary codebase. This file is retained for reference but should not be modified.

Use `run.py` → `app.main:app` for the current application.
