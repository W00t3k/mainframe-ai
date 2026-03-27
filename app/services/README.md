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

### `grok.py`
Singleton `GrokService` — xAI/Grok cloud LLM client:
- `generate()` — single-shot prompt completion via OpenAI-compatible API
- `chat_simple()` — multi-turn chat returning plain text
- `quick_explain()` — fast screen explanation
- `check_available()` — API key + endpoint health check
- `list_models()` — fetch available models from the API
- Supports any OpenAI-compatible endpoint (Groq, Together, etc.)

### `llm_provider.py`
Singleton `UnifiedLLMService` — routes requests to the best available LLM:
- Auto mode: prefers local Ollama, falls back to Grok if Ollama is down
- Explicit mode: force Ollama or Grok via `LLM_PROVIDER` env var
- `get_status()` — returns availability of all providers for UI
- All `generate()`, `chat_simple()`, `quick_explain()` calls route through this

### `bof_lab.py`
Buffer overflow lab service:
- De Bruijn pattern generation and offset calculation
- ASCII ↔ EBCDIC conversion
- ABEND dump analysis (register extraction, pattern matching)
- Lab data loading from `data/lab_data/bof_demo.json`
- Exploit narrative steps for guided walkthrough

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
