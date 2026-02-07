# Core Python Modules

This document describes the main Python modules in the project root.

## Module Overview

| Module | Lines | Description |
|--------|-------|-------------|
| `run.py` | 53 | Application entry point |
| `agent_tools.py` | 748 | TN3270 connection and tool definitions |
| `trust_graph.py` | 884 | BloodHound-style trust relationship graph |
| `graph_tools.py` | 1185 | Graph analysis and parsing utilities |
| `rag_engine.py` | 801 | Retrieval-Augmented Generation engine |
| `recon_engine.py` | 1193 | TN3270 enumeration and reconnaissance |
| `mcp_server.py` | 610 | Model Context Protocol server |
| `mainframe_assistant.py` | 403 | CLI assistant interface |

---

## `run.py`
**Entry Point**

Starts the FastAPI application server via Uvicorn.

```bash
python run.py --host 127.0.0.1 --port 8080 --model llama3.1:8b
```

---

## `agent_tools.py`
**TN3270 Connection & Tools**

Manages the TN3270 terminal connection and defines tools for the agentic loop:
- `connect_mainframe()` - Establish TN3270 session
- `disconnect_mainframe()` - Close session
- `read_screen()` - Get current screen text
- `send_terminal_key()` - Send keystrokes (Enter, PF keys, text)
- `capture_screen()` - Save screen to file
- `TOOL_DEFINITIONS` - OpenAI-style tool schemas for LLM

---

## `trust_graph.py`
**Trust Relationship Graph**

BloodHound-inspired graph for mainframe trust relationships:
- **Node Types**: EntryPoint, Panel, Job, Program, Dataset, Transaction, etc.
- **Edge Types**: NAVIGATES_TO, EXECUTES, READS, WRITES, LOADS_FROM, etc.
- **Queries**: Shortest paths, shared datasets, boundary crossings
- **Export**: JSON, DOT (Graphviz), D3.js format

---

## `graph_tools.py`
**Graph Analysis Utilities**

Parsing and analysis tools for populating the trust graph:
- `parse_jcl()` - Extract jobs, steps, datasets from JCL
- `parse_sysout()` - Parse job output for execution details
- `classify_panel()` - Identify ISPF panel types
- `update_graph_from_*()` - Ingest data into graph
- `ScreenMapperAgent` - AI-assisted screen classification
- `BatchTrustAgent` - Batch job relationship analysis

---

## `rag_engine.py`
**Retrieval-Augmented Generation**

Local vector store for mainframe documentation:
- Document chunking and embedding
- Similarity search for context retrieval
- Built-in knowledge base initialization
- File-based persistence (no external DB)

---

## `recon_engine.py`
**TN3270 Reconnaissance**

Native Python implementation of mainframe enumeration:
- `TSOEnumerator` - TSO userid enumeration
- `CICSEnumerator` - CICS transaction enumeration
- `VTAMEnumerator` - VTAM APPLID discovery
- `HiddenFieldDetector` - Find hidden screen fields
- `ScreenAnalyzer` - AI-assisted screen analysis
- `ApplicationMapper` - Map application paths

---

## `mcp_server.py`
**Model Context Protocol Server**

MCP server for external AI tool integration:
- Exposes mainframe tools via MCP protocol
- Enables Claude Desktop and other MCP clients
- Tool definitions for connect, read, send, capture

---

## `mainframe_assistant.py`
**CLI Interface**

Command-line chat interface for the assistant:
- Interactive REPL for mainframe questions
- Direct terminal without web UI
- Useful for scripting and automation

---

## Legacy File

### `web_app.py` (3762 lines)
**⚠️ Legacy monolithic application**

This file contains an older, monolithic version of the application. The modular `app/` directory structure is now the primary codebase. This file is retained for reference but should not be modified.

Use `run.py` → `app.main:app` for the current application.
