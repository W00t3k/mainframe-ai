# Architecture

This document describes the architecture of the Mainframe AI Assistant.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         User Interfaces                                  │
├─────────────────────┬─────────────────────┬─────────────────────────────┤
│  Web App (run.py)   │  CLI (mainframe_   │   MCP Server                  │
│  FastAPI + Jinja2   │  assistant.py)     │   (mcp_server.py)             │
│  16 HTML templates  │                    │                               │
└──────────┬──────────┴──────────┬──────────┴──────────────┬──────────────┘
           │                     │                          │
           ▼                     ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      AI / RAG Layer                                      │
├─────────────────────────────────────────────────────────────────────────┤
│  LLM Backend             │  rag_engine.py (RAG)                          │
│  (Ollama default)        │  - Document embedding                         │
│  - Q&A                   │  - Semantic search                            │
│  - Code generation       │  - Context augmentation                       │
│  - Screen analysis       │                                             │
│  - Click-to-analyze      │  methodology_engine.py                       │
│                          │  - F1–F5 findings framework                   │
└─────────────────────┬───────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     TN3270 v2 Modules                                      │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  core    │  │ emulator │  │ security │  │    io    │  │   zos    │  │
│  │ models   │  │ wrapper  │  │ scanner  │  │ exporters│  │ helpers  │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
│       │             │             │             │             │        │
│       └─────────────┴─────────────┴─────────────┴─────────────┘        │
└─────────────────────────────────────┬───────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     TN3270 Layer                                         │
├─────────────────────────────────────────────────────────────────────────┤
│  py3270 library  ──►  x3270/s3270 executable  ──►  Mainframe (z/OS)     │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### User Interfaces

#### run.py → app/ (Primary)

Modular FastAPI web application with Jinja2 templates.

- 14 API route modules
- 16 HTML templates with IBM Plex Mono retro theme
- REST API endpoints
- WebSocket for real-time updates
- Click-to-analyze AI on terminal screens
- Hover hints for contextual descriptions
- Invisible toolbar with scroll-up reveal

#### mainframe_assistant.py (CLI)

Command-line interface for conversational mainframe interaction.

- Natural language queries
- Command parsing (/connect, /screen, etc.)
- Action extraction from LLM responses
- Uses Ollama for LLM inference

#### mcp_server.py (MCP)

Model Context Protocol server for external AI tool integration.

- Exposes mainframe tools via MCP protocol
- Enables Claude Desktop and other MCP clients

### AI / RAG Layer

#### LLM Backend Integration (Ollama default)

Uses an Ollama-compatible `/api/chat` backend for:
- Natural language understanding
- z/OS knowledge queries
- JCL generation
- COBOL code analysis
- ABEND interpretation

#### RAG Engine (rag_engine.py)

Retrieval-Augmented Generation for enhanced responses:
- Document chunking and embedding
- Vector similarity search
- Context augmentation for queries
- Knowledge base management

### TN3270 v2 Modules

#### Core (tn3270v2_modules/core/)

Foundation data models:

```python
Field      # Single 3270 screen field
Screen     # Complete terminal screen
Transaction # Request/response pair
History    # Session history container
```

#### Emulator (tn3270v2_modules/emulator/)

TN3270 terminal wrapper:

```python
WrappedEmulator
├── connect()           # Establish connection
├── exec_command()      # Send x3270 command
├── send_string()       # Type text
├── send_enter()        # Send Enter
├── screen_get()        # Read screen
└── safe_*()            # Timeout-protected variants
```

#### Security (tn3270v2_modules/security/)

Security testing tools:

```
SecurityScanner    # Vulnerability detection
├── scan_screen()
├── scan_history()
├── detect_credentials()
└── check_access_control()

AutomatedCrawler   # Application mapping
FieldFuzzer        # Input validation testing
SessionReplay      # Transaction replay
SecurityReporter   # Report generation
```

#### I/O (tn3270v2_modules/io/)

Data persistence and export:

```
Exporters
├── export_to_json()
├── export_to_csv()
├── export_to_html()
├── export_to_xml()
└── auto_export()

File Operations
├── save_history()
└── load_history()
```

#### Mainframe Helpers

Mainframe subsystem parsers:

```
CICSHelper    # CICS transaction processing
TSOHelper     # TSO/ISPF operations
RACFHelper    # Security/access control
JESParser     # Job management
```

### TN3270 Layer

#### py3270

Python library providing x3270 scripting interface.

#### x3270/s3270

IBM 3270 terminal emulator:
- x3270: GUI version
- s3270: Scripted/headless version
- wc3270: Windows console version

#### Mainframe

Target z/OS system with:
- TN3270 service (port 23)
- TSO/ISPF
- CICS (optional)
- RACF security

## Data Flow

### Query Processing

```
User Query
    │
    ▼
┌─────────────────────┐
│ mainframe_assistant │
│   parse_command()   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐     ┌─────────────────────┐
│   LLM Backend       │◄────│   RAG Engine        │
│  (Ollama default)   │     │ (context retrieval) │
└──────────┬──────────┘     └─────────────────────┘
           │
           ▼
┌─────────────────────┐
│  Response + Actions │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Execute Actions    │
│  (if mainframe cmd) │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  WrappedEmulator    │
│  send to mainframe  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Parse Response     │
│  Update History     │
└─────────────────────┘
```

### Screen Capture Flow

```
WrappedEmulator
    │
    ├── exec_command(b'ReadBuffer(Ascii)')
    │
    ▼
Raw Buffer (hex + field markers)
    │
    ├── Screen(buffer)
    │
    ▼
Screen Object
    ├── .stringbuffer    # Text lines
    ├── .fields          # Field objects
    ├── .input_fields    # Editable fields
    ├── .hidden_fields   # Password fields
    └── .colorbuffer     # Color-coded display
```

## Security Considerations

### Credential Handling

- Never log passwords in plaintext
- Use hidden field detection
- Mask sensitive output

### Connection Security

- TN3270 is unencrypted by default
- Use TN3270E/SSL where available
- Consider VPN tunneling

### Code Injection

- Sanitize all user input
- Validate JCL before submission
- Check for command injection patterns

## Extensibility

### Adding New z/OS Parsers

1. Create new helper in `tn3270v2_modules/zos/`
2. Implement detection method
3. Add parsing methods
4. Export in `__init__.py`

### Adding Export Formats

1. Add function in `tn3270v2_modules/io/exporters.py`
2. Update `auto_export()` extension mapping
3. Document in module README

### Adding Security Checks

1. Add patterns to `SecurityScanner.patterns`
2. Implement detection in `scan_screen()`
3. Add to report generation

## Testing

### Unit Tests

```bash
pytest tests/
```

### Integration Tests

Requires running mainframe:
```bash
pytest tests/integration/ --target localhost:3270
```

### Security Tests

```bash
pytest tests/security/ -m "not requires_mainframe"
```

## Performance

### Optimization Points

- Screen caching for repeated reads
- Batch transaction processing
- Lazy field parsing
- Connection pooling for web app

### Timeouts

Default timeouts:
- Connection: 30 seconds
- Command: 10 seconds
- Screen read: 5 seconds

Configure via `WrappedEmulator(command_timeout=X)`.
