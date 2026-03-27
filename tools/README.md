# `tools/` — Standalone Python Tools and Engines

Standalone Python modules that power the Mainframe AI Assistant's core capabilities. These are imported lazily by `app/routes/` and `app/services/` at runtime via `sys.path` (configured in `run.py`).

## TN3270 Terminal

### `agent_tools.py`
The TN3270 connection layer — all terminal I/O goes through here:
- `connect_mainframe(target)` — connect via s3270, wait for VTAM logon screen
- `disconnect_mainframe()` — clean disconnect
- `read_screen()` — read current 24x80 screen as text (string_get row-by-row)
- `send_terminal_key(key_type, value)` — send keys, strings, PF keys
- `get_screen_data()` / `get_cached_screen_data()` — screen + HTML color data
- `capture_screen()` — save screenshot to `data/screencaps/`
- Screen update callback for WebSocket push

### `recon_engine.py`
Automated TSO/CICS/VTAM enumeration:
- State machine for navigating TSO login, ISPF, RACF commands
- RACF user/group/dataset profile enumeration
- System inspection (APF libraries, SVC table, PARMLIB)
- Findings-based methodology with severity ratings
- Report generation (markdown + JSON)

### `tn3270_discovery.py`
Internet-scale TN3270 scanner:
- Shodan API integration for mainframe discovery
- Nmap NSE script execution (CICS enum, TPX enum)
- Masscan for fast port sweeping
- s3270 banner grabbing and screenshot capture
- SQLite results database at `data/discovery.db`
- Stealth profiles (paranoid → aggressive timing)

## Trust Graph

### `trust_graph.py`
Graph data structures and persistence:
- Node types: EntryPoint, Identity, Dataset, Job, Transaction, Program, Resource
- Edge types: authenticates, accesses, submits, executes, etc.
- JSON persistence at `data/trust_graph_data/graph.json`
- Query methods: find paths, get neighbors, filter by type

### `graph_tools.py`
Graph analysis and data extraction:
- `parse_jcl(text)` — extract datasets, programs, DD statements from JCL
- `parse_sysout(text)` — extract job info, return codes, messages from sysout
- `update_graph_from_screen(graph, screen, source)` — extract entities from 3270 screens
- `classify_panel(screen)` — identify ISPF/TSO/VTAM panel type
- D3.js, DOT, and JSON export

### `graph_automation.py`
Automated trust graph exploration:
- `TrustGraphAutomation` — drives s3270 to explore and map trust relationships
- `run_session_stack_exploration()` — automated VTAM→TSO→ISPF graph building

## AI and Knowledge

### `rag_engine.py`
Retrieval-Augmented Generation with local Ollama embeddings:
- Document indexing (text, PDF)
- Embedding generation via Ollama API
- Cosine similarity search
- Persistent index at `data/rag_data/`

### `methodology_engine.py`
Control-plane assessment methodology:
- Six control planes: VTAM, TSO, RACF, JES, CICS, PR/SM
- Structured assessment steps with expected findings
- Progress tracking per control plane

### `mcp_server.py`
Model Context Protocol server for IDE integration.

### `ai_bridge.py`
TCP socket bridge between CICS/KICKS transactions and the AI backend. Allows 3270 BMS screens to query the LLM.

### `mainframe_assistant.py`
CLI-based mainframe assistant (predecessor to the web app).

## KICKS (CICS) Installation

### `install_kicks.py`
Multi-step KICKS installation automation:
- DASD volume creation, catalog setup, XMIT upload/unpack
- Drives s3270 for interactive TSO steps

### `install_kicks_auto.py`
Automated KICKS installer via py3270 emulator.

### `kicks_check.py`
Verifies KICKS installation status on TK5.

### `kicks_install/`
KICKS XMIT distribution files for MVS 3.8j.

## Legacy

### `web_app.py`
Original monolithic Flask/FastAPI web app. Superseded by `app/` modular architecture but retained for reference and standalone use.
