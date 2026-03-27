# `app/` — FastAPI Application Core

Modular FastAPI backend powering the Mainframe AI Assistant. All HTTP routes, business logic, LLM prompts, and walkthrough definitions live here.

## Layout

```
app/
├── __init__.py          # Package init
├── config.py            # Runtime configuration (Ollama URL, model, paths, GPU)
├── main.py              # FastAPI app factory, lifespan, static/template mounts
├── constants/           # Prompts, walkthrough scripts, learning paths
│   ├── prompts.py       # System prompts, tutor prompts, HMC simulator, control planes
│   ├── walkthrough_scripts.py  # 13 autonomous walkthrough step definitions
│   └── paths.py         # 9 guided learning paths with fallback steps
├── models/              # Pydantic request/response schemas
├── routes/              # API route handlers (19 modules)
│   ├── pages.py         # HTML rendering (24+ templates), /api/status, /api/sysinfo
│   ├── terminal.py      # TN3270 connect/disconnect/key/screen
│   ├── chat.py          # AI chat, screen explain, model management, pull progress
│   ├── walkthrough.py   # Autonomous walkthrough engine with error recovery
│   ├── tutor.py         # Red Team Tutor (analyze, ask, suggest, event, paths)
│   ├── system.py        # Mainframe start/stop/restart, JCL submit, USS editor, GPU
│   ├── graph.py         # Trust graph CRUD, queries, D3/DOT/JSON export
│   ├── recon.py         # TSO/CICS/VTAM enumeration, hidden fields, reports
│   ├── scanner.py       # Port scanning, TN3270 banner grab, Shodan/nmap/masscan
│   ├── methodology.py   # Control-plane assessment methodology engine
│   ├── kicks.py         # KICKS (CICS) status, start, stop
│   ├── ftp.py           # MVS FTP client, card reader submit
│   ├── llm.py           # LLM provider switch (Ollama/Grok/auto), API key config
│   ├── bof_lab.py       # Buffer overflow lab (De Bruijn, EBCDIC, dump analysis)
│   ├── rakf.py          # RAKF security manager (users, profiles, rules)
│   ├── labs.py          # Lab index and detail endpoints
│   ├── rag.py           # RAG knowledge base (query, upload, stats)
│   └── screencaps.py    # Terminal screenshot capture and management
├── services/            # Business logic
│   ├── ollama.py        # Ollama LLM client (generate, chat, quick_explain)
│   ├── grok.py          # Grok/xAI cloud LLM client
│   ├── llm_provider.py  # Unified LLM router (Ollama ↔ Grok with auto-fallback)
│   ├── chat.py          # Chat processing, conversation history, slash commands
│   ├── ftp.py           # MVS FTP client over ftplib
│   ├── bof_lab.py       # Buffer overflow lab logic (De Bruijn, dump analysis)
│   ├── kicks_installer.py  # KICKS lifecycle management
│   └── rag_context.py   # Shared RAG context builder
└── websocket/           # Real-time terminal and graph updates
```

## Key Design Decisions

- **6 control planes** — VTAM, TSO, RACF, JES, CICS, PR/SM. All prompts and analysis use this framework.
- **LLM-driven simulation** — The PR/SM walkthrough uses the LLM to emulate an IBM z16 HMC with 6 LPARs.
- **Walkthrough engine** — 13 scripted walkthroughs drive s3270 autonomously with per-step narration.
- **Shared helpers** — Card reader submission and VTAM restart are centralized in `system.py`. RAG context building is in `services/rag_context.py`.
- **Dual LLM support** — Ollama for local inference (default), Grok/xAI for cloud. Auto-fallback between providers.

## Entry Point

```bash
python run.py --host 0.0.0.0 --port 8080 --model llama3.1:8b
```
