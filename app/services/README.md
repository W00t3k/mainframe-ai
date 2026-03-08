# `app/services/` — Business Logic

Stateless service modules imported by route handlers. Keeps routes thin and logic reusable.

## Modules

### `chat.py`
Singleton `ChatService` — chat processing and conversation management:
- Conversation history (per-session, in-memory, capped at 40 messages)
- RAG context injection from local embeddings
- Slash-command handling (`/connect`, `/disconnect`, `/screen`, `/model`, `/clear`, `/help`)
- Automatic screen context when connected to mainframe

### `ollama.py`
Singleton `OllamaService` — all Ollama LLM communication:
- `generate()` — single-shot prompt completion
- `chat()` — multi-turn chat API with optional tool definitions
- `chat_simple()` — convenience wrapper returning plain text
- `quick_explain()` — fast one-sentence screen explanation (low token, short timeout)
- `check_available()` — health check
- GPU-optimized options merged automatically from `config.py`

### `ftp.py`
Singleton `FTPService` — MVS FTP client over `ftplib`:
- Connect/disconnect to TK5 FTP server (default port 2121)
- List datasets and PDS members
- Download/upload with ASCII↔EBCDIC translation
- Raw FTP command passthrough
- Transfer history log
- Full automated test suite

### `kicks_installer.py`
Singleton `KICKSInstaller` — KICKS (CICS) lifecycle management:
- Check KICKS installation and runtime status
- Start/stop KICKS from TSO

### `rag_context.py`
Shared RAG context builder used by `tutor` and `recon` routes:
- `build_rag_context(query, n_results)` — queries the RAG engine and returns a formatted context block for LLM prompts
