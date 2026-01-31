# Mainframe AI Assistant

Natural language interface for z/OS mainframe operations. Uses a local LLM by default (Ollama), with a pluggable backend.

## Features

- **Conversational Interface**: Ask questions in plain English about z/OS, JCL, COBOL, ABEND codes
- **Live Connection**: Connect to real mainframes via TN3270 (uses BIRP modules)
- **Screen Analysis**: LLM can read and explain 3270 terminal screens
- **JCL Generation**: Generate JCL for common tasks from natural language descriptions
- **ABEND Debugging**: Get explanations and fix suggestions for system abends
- **Offline Mode**: Works without mainframe connection for Q&A and code generation

## Quick Start (Web UI, Ollama default)

```bash
# 1. Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start Ollama (in another terminal)
ollama serve
ollama pull llama3.1:8b

# 4. Run the web app
python web_app.py
```

Open:

- `http://127.0.0.1:8080/chat` (AI chat)
- `http://127.0.0.1:8080/tutor` (red team tutor)
- `http://127.0.0.1:8080/graph` (trust graph)

### CLI (Optional)

The CLI uses Anthropic by default. If you want the CLI:

```bash
export ANTHROPIC_API_KEY="your-key-here"
python mainframe_assistant.py

# Or connect directly to a mainframe
python mainframe_assistant.py -t localhost:3270
```

### TK5 Bundle (Local MVS)

The TK5 distribution zip is not included in this repo. Download it from your
custom MVS docs and unzip into `tk5/mvs-tk5` so the emulator assets are present.

## Usage

### Interactive Mode

```
$ python mainframe_assistant.py

╭─ Welcome ─────────────────────────────────────────────╮
│ Mainframe AI Assistant                                │
│ Natural language interface for z/OS operations        │
│                                                       │
│ Commands:                                             │
│   /connect <host:port> - Connect to mainframe         │
│   /screen             - Show current screen           │
│   /disconnect         - Disconnect                    │
│   /clear              - Clear conversation            │
│   /quit               - Exit                          │
╰───────────────────────────────────────────────────────╯

○ You: What does ABEND S0C7 mean?

╭─ Assistant ───────────────────────────────────────────╮
│ S0C7 is a **Data Exception** - one of the most common │
│ ABEND codes in COBOL programs.                        │
│                                                       │
│ **Common causes:**                                    │
│ - Invalid data in a packed decimal field              │
│ - Moving non-numeric data to a numeric field          │
│ - Uninitialized working storage                       │
│ ...                                                   │
╰───────────────────────────────────────────────────────╯
```

### Example Queries

**General z/OS:**
- "What does ABEND S0C7 mean?"
- "Explain the difference between PDS and PDSE"
- "How do I check if a dataset exists in JCL?"

**JCL Generation:**
- "Generate JCL to copy PROD.DATA.FILE to TEST.DATA.FILE"
- "Write JCL for a COBOL compile and link"
- "Create JCL to run IEBGENER with SORTOUT"

**Connected Mode:**
- "/connect mainframe.example.com:23"
- "What's on the current screen?"
- "Navigate to ISPF option 3.4"
- "Submit the JCL on this screen"

**Demo Without a Mainframe:**
- Start Ollama (`ollama serve`)
- Run the web app (`python web_app.py`)
- Open `/chat`, `/tutor`, and `/graph`
- `/terminal` requires a TN3270 target (TK5 or a real mainframe)

**COBOL/Code:**
- "Explain this COBOL paragraph: [paste code]"
- "How do I read a VSAM file in COBOL?"
- "Convert this PERFORM VARYING to a modern loop"

### Screenshots / Demo Media

Add 2–4 visuals before publishing a blog post. Suggested captures:

- `/terminal` with the floating chat panel
- `/tutor` learning path screen
- `/graph` trust graph view
- `/chat` answer explaining an ABEND

Place assets under `docs/assets/` (see `docs/assets/README.md` for naming).

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    User Interface                    │
│              (rich CLI / prompt_toolkit)             │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│              MainframeAssistant                      │
│  - Conversation management                           │
│  - Command parsing                                   │
│  - Action extraction from LLM responses              │
└──────────┬────────────────────────┬─────────────────┘
           │                        │
┌──────────▼──────────┐  ┌─────────▼─────────────────┐
│   LLM Backend       │  │   BIRP TN3270 Layer       │
│   (Ollama default)  │  │   - Screen reading        │
│   - Q&A             │  │   - Command execution     │
│   - Code generation │  │   - Session history       │
│   - Analysis        │  │   - Field parsing         │
└─────────────────────┘  └───────────────────────────┘
```

## Integration with BIRP

This assistant can use [BIRP v2](../STuFF%20/birp/) modules for mainframe connectivity:

```python
# Automatically detected if BIRP is at ~/Desktop/STuFF /birp/
from birpv2_modules.emulator.wrapper import WrappedEmulator
from birpv2_modules.core.models import Screen, History
```

Without BIRP, the assistant runs in offline mode (Q&A only, no live connection).

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OLLAMA_URL` | Ollama API endpoint (default: `http://localhost:11434`) |
| `OLLAMA_MODEL` | Default Ollama model (default: `llama3.1:8b`) |
| `MAINFRAME_HOST` | Default mainframe target |
| `MAINFRAME_USER` | Default TSO userid |
| `ANTHROPIC_API_KEY` | Optional. Only needed for CLI usage |

### CLI Options

```
-t, --target HOST:PORT   Connect to mainframe on startup
-k, --api-key KEY        Anthropic API key (or use env var)
--model MODEL            Claude model (default: claude-sonnet-4-20250514)
```

## Roadmap

- [ ] RAG with z/OS documentation corpus
- [ ] Web UI (FastAPI + HTMX)
- [ ] JCL syntax validation
- [ ] SYSOUT analysis and explanation
- [ ] Multi-mainframe session support
- [ ] Voice input/output
- [ ] Integration with VS Code extension

## Related Projects

- [BIRP v2](https://github.com/w00t3k/birpv2) - Big Iron Recon & Pwnage toolkit
- [IBM watsonx Code Assistant for Z](https://www.ibm.com/products/watsonx-code-assistant-z) - IBM's commercial offering
- [Mainframed](https://github.com/mainframed) - Mainframe security tools by Soldier of FORTRAN

## License

MIT
