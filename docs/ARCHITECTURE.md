# Architecture

This document describes the architecture of the Mainframe AI Assistant and BIRP v2 modules.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         User Interfaces                                  │
├─────────────────────┬─────────────────────┬─────────────────────────────┤
│  mainframe_assistant│    web_app.py       │   BIRP GUI/CLI              │
│      (CLI)          │    (FastAPI)        │   (tkinter/console)         │
└──────────┬──────────┴──────────┬──────────┴──────────────┬──────────────┘
           │                     │                          │
           ▼                     ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      AI / RAG Layer                                      │
├─────────────────────────────────────────────────────────────────────────┤
│  Claude API (Anthropic)  │  rag_engine.py (RAG)                          │
│  - Q&A                   │  - Document embedding                         │
│  - Code generation       │  - Semantic search                            │
│  - Screen analysis       │  - Context augmentation                       │
└─────────────────────┬───────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     BIRP v2 Modules                                      │
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

#### mainframe_assistant.py

Command-line interface for conversational mainframe interaction.

- Natural language queries
- Command parsing (/connect, /screen, etc.)
- Action extraction from Claude responses
- Rich terminal output

#### web_app.py

FastAPI-based web application with HTMX frontend.

- REST API endpoints
- WebSocket for real-time updates
- Template-based UI
- RAG integration

#### BIRP GUI/CLI

Native Python interfaces for direct mainframe interaction.

- tkinter GUI terminal (TN3270Terminal)
- Console mode (ConsoleMode)
- History browser
- Python REPL integration

### AI / RAG Layer

#### Claude API Integration

Uses Anthropic's Claude for:
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

### BIRP v2 Modules

#### Core (birpv2_modules/core/)

Foundation data models:

```python
Field      # Single 3270 screen field
Screen     # Complete terminal screen
Transaction # Request/response pair
History    # Session history container
```

#### Emulator (birpv2_modules/emulator/)

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

#### Security (birpv2_modules/security/)

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

#### I/O (birpv2_modules/io/)

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

#### z/OS (birpv2_modules/zos/)

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
│    Claude API       │◄────│   RAG Engine        │
│   (if knowledge Q)  │     │ (context retrieval) │
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

1. Create new helper in `birpv2_modules/zos/`
2. Implement detection method
3. Add parsing methods
4. Export in `__init__.py`

### Adding Export Formats

1. Add function in `birpv2_modules/io/exporters.py`
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
