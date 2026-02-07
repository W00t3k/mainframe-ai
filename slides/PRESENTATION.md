# Mainframe Security Toolkit
## Teaching Presentation Guide

---

# Slide 1: Title

## **Mainframe Security Toolkit**
### AI-Powered z/OS Operations & Security Assessment

**Key Points:**
- Local-first design (no cloud APIs)
- Ollama LLM for AI capabilities
- TN3270 terminal integration
- Red team focused methodology

**Speaker Notes:**
> This toolkit is designed for security professionals learning mainframe operations. Everything runs locally - no data leaves your machine.

---

# Slide 2: The 5 Assessment Questions

## Core Methodology Framework

| # | Question | Focus Area |
|---|----------|------------|
| Q1 | Where is identity bound? | Authentication points |
| Q2 | When is authority evaluated? | Authorization timing |
| Q3 | What executes later than expected? | Deferred execution |
| Q4 | Which subsystem enforces policy? | Security enforcement |
| Q5 | What assumptions are you importing? | Implicit trust |

**Speaker Notes:**
> These 5 questions form the assessment framework. Every screen, every action should be evaluated against these questions. They help identify security gaps in mainframe environments.

---

# Slide 3: Control Planes Overview

## The 5 Control Planes

```
┌─────────┐    ┌─────────┐    ┌─────────┐
│  VTAM   │ → │   TSO   │ → │  ISPF   │
│ Network │    │ Session │    │  Panels │
└─────────┘    └─────────┘    └─────────┘
                    ↓
              ┌─────────┐    ┌─────────┐
              │  RACF   │    │   JES   │
              │Security │    │  Batch  │
              └─────────┘    └─────────┘
                    ↓
              ┌─────────┐
              │  CICS   │
              │  Trans  │
              └─────────┘
```

**Speaker Notes:**
> VTAM handles network entry. TSO provides interactive sessions. RACF enforces security. JES manages batch jobs. CICS handles transactions. Understanding these planes is fundamental.

---

# Slide 4: System Architecture

## Module Overview

```
┌────────────────────────────────────────┐
│            Web UI (FastAPI)            │
├────────────┬───────────┬───────────────┤
│   Chat     │  Terminal │    Tutor      │
├────────────┴───────────┴───────────────┤
│              Core Services              │
├──────┬──────┬──────┬──────┬───────────┤
│ RAG  │Graph │Recon │Agent │  Ollama   │
│Engine│Tools │Engine│Tools │   LLM     │
├──────┴──────┴──────┴──────┴───────────┤
│           TN3270 Connection            │
└────────────────────────────────────────┘
```

**Speaker Notes:**
> The architecture is layered. Web UI on top, core services in the middle, TN3270 at the bottom. All AI goes through Ollama locally.

---

# Slide 5: Module - TN3270 Terminal

## `agent_tools.py` - Terminal Connection

**Purpose:** Manage TN3270 sessions with the mainframe

**Key Functions:**
- `connect_mainframe(host, port)` - Establish session
- `read_screen()` - Get current screen text
- `send_terminal_key(key)` - Send keystrokes
- `capture_screen()` - Save for documentation

**Demo Points:**
1. Connect to TK5 (localhost:3270)
2. Show screen reading
3. Demonstrate key sending
4. Capture a screen

**Speaker Notes:**
> This is the foundation. Without TN3270 connectivity, nothing else works. The module wraps the py3270 library and provides clean abstractions.

---

# Slide 6: Module - Trust Graph

## `trust_graph.py` - Relationship Mapping

**Purpose:** BloodHound-style graph for mainframe trust relationships

**Node Types:**
- EntryPoint, Panel, Job, Program
- Dataset, Loadlib, Transaction
- CICSRegion, ReturnCode

**Edge Types:**
- NAVIGATES_TO, EXECUTES, READS/WRITES
- LOADS_FROM, INVOKES, BOUNDARY_CROSS

**Demo Points:**
1. Load demo data
2. Show node relationships
3. Run path queries
4. Export visualization

**Speaker Notes:**
> Like BloodHound for AD, this maps trust relationships in mainframe. Where can you go from an entry point? What datasets does a job access?

---

# Slide 7: Module - Graph Tools

## `graph_tools.py` - Analysis Utilities

**Purpose:** Parse and analyze mainframe artifacts

**Parsers:**
- `parse_jcl()` - Extract jobs, steps, datasets from JCL
- `parse_sysout()` - Parse job output
- `classify_panel()` - Identify ISPF panel types

**AI Agents:**
- `ScreenMapperAgent` - AI screen classification
- `BatchTrustAgent` - Job relationship analysis
- `CICSRelationshipAgent` - Transaction mapping

**Speaker Notes:**
> These tools automatically extract information and feed it into the trust graph. JCL is particularly rich - job names, programs executed, datasets accessed.

---

# Slide 8: Module - RAG Engine

## `rag_engine.py` - Knowledge Retrieval

**Purpose:** Retrieval-Augmented Generation for mainframe documentation

**How It Works:**
1. Documents chunked into segments
2. Embeddings generated via Ollama
3. Stored in local vector store
4. Similar chunks retrieved for context

**Built-in Knowledge:**
- JCL syntax and patterns
- ABEND codes and meanings
- ISPF navigation
- RACF concepts

**Speaker Notes:**
> The LLM alone doesn't know mainframe specifics. RAG injects relevant documentation into the prompt, making responses accurate and contextual.

---

# Slide 9: Module - Recon Engine

## `recon_engine.py` - Enumeration

**Purpose:** Native Python TN3270 enumeration

**Enumerators:**
| Class | Target | Method |
|-------|--------|--------|
| `TSOEnumerator` | TSO userids | Logon probing |
| `CICSEnumerator` | Transactions | CESN/CEMT |
| `VTAMEnumerator` | APPLIDs | LOGON attempts |

**Detectors:**
- `HiddenFieldDetector` - Find hidden screen fields
- `ScreenAnalyzer` - AI-assisted analysis
- `ApplicationMapper` - Map application paths

**Speaker Notes:**
> This reimplements classic mainframe enumeration in Python. No external tools needed. All I/O goes through our TN3270 connection.

---

# Slide 10: Module - Red Team Tutor

## Guided Learning System

**Purpose:** Step-by-step security learning

**Features:**
- Live terminal integration
- AI-powered explanations
- Quick question chips
- Screen context analysis

**Learning Flow:**
1. Connect to TK5
2. Follow guided steps
3. Ask questions about screens
4. Practice enumeration

**Speaker Notes:**
> The tutor watches what you're doing and provides contextual help. It's like having an expert looking over your shoulder, explaining each screen.

---

# Slide 11: Module - Walkthrough

## Autonomous Demonstrations

**Purpose:** Self-driving mainframe navigation

**Available Walkthroughs:**
- Session Stack (VTAM → TSO → ISPF)
- Deferred Execution (JCL → JES)
- Authorization Model (RACF)
- COBOL Development

**How It Works:**
1. Auto-connects to mainframe
2. Sends keystrokes automatically
3. Narrates each step
4. Tracks Q1-Q5 coverage

**Speaker Notes:**
> Great for demonstrations. The system drives itself through the mainframe while explaining what's happening. Audience just watches and learns.

---

# Slide 12: Module - Security Labs

## Hands-on Exercises

**Purpose:** Offline practice exercises

**Lab Categories:**
- RACF Basics - Profile inspection
- TSO Enumeration - User discovery
- Dataset Recon - Permission analysis
- JCL Analysis - Batch job review
- SDSF Inspection - Output analysis

**Each Lab Includes:**
- Step-by-step instructions
- Expected outcomes
- Hints for stuck points

**Speaker Notes:**
> Labs don't require live mainframe connection initially. They teach concepts before moving to the live system. Reduces risk of accidental issues.

---

# Slide 13: Data Flow

## Request Processing Pipeline

```
User Action
    ↓
FastAPI Router
    ↓
┌─────────────────────────────────┐
│         Service Layer           │
│  ┌─────┐ ┌─────┐ ┌──────────┐  │
│  │ RAG │ │Graph│ │TN3270    │  │
│  │     │ │     │ │Connection│  │
│  └─────┘ └─────┘ └──────────┘  │
└─────────────────────────────────┘
    ↓
Ollama LLM (local)
    ↓
Response to User
```

**Speaker Notes:**
> Every request follows this flow. The service layer coordinates between RAG context, graph data, and terminal state before calling the LLM.

---

# Slide 14: Technology Stack

## What Powers This

| Layer | Technology |
|-------|------------|
| Web Framework | FastAPI + Jinja2 |
| Frontend | Vanilla JS + CSS |
| LLM | Ollama (local) |
| Embeddings | Ollama (nomic-embed) |
| Terminal | py3270 / TN3270 |
| Visualization | D3.js |

**Key Design Decisions:**
- No cloud APIs = air-gapped capable
- File-based storage = portable
- Modular architecture = extensible

**Speaker Notes:**
> Everything runs locally. You can use this on a disconnected network. The only external requirement is the mainframe itself (TK5 for learning).

---

# Slide 15: Demo Sequence

## Suggested Demo Flow

1. **Landing Page** (2 min)
   - Show control planes
   - Explain card categories

2. **Terminal Connection** (3 min)
   - Connect to TK5
   - Navigate to TSO logon

3. **Walkthrough** (5 min)
   - Run Session Stack walkthrough
   - Show Q1-Q5 tracking

4. **Trust Graph** (3 min)
   - Load demo data
   - Run path queries

5. **Recon** (5 min)
   - TSO enumeration demo
   - Show AI analysis

**Speaker Notes:**
> This 18-minute demo hits all major features. Adjust timing based on audience questions and interest areas.

---

# Slide 16: Hands-On Exercise

## Audience Activity

**Task:** Find the shortest path from VTAM to dataset access

**Steps:**
1. Open Trust Graph
2. Load demo data
3. Run "Paths to Job Submit" query
4. Identify which panels lead to dataset operations

**Discussion Points:**
- How many clicks from logon to data?
- Where are the authorization checks?
- What could an attacker abuse?

**Speaker Notes:**
> Get the audience hands-on. This exercise connects the graph visualization to real security thinking.

---

# Slide 17: Extending the Toolkit

## How to Customize

**Add New Walkthroughs:**
- Edit `app/constants/walkthrough_scripts.py`
- Define steps, narration, expected screens

**Add RAG Knowledge:**
- Drop documents in `rag_data/`
- Run ingestion endpoint

**Add Recon Patterns:**
- Extend enumerator classes
- Add pattern matching rules

**Speaker Notes:**
> The toolkit is designed for extension. Your organization's specific knowledge can be added to make it more relevant.

---

# Slide 18: Summary

## Key Takeaways

1. **5 Questions** - Framework for every assessment
2. **5 Control Planes** - VTAM, TSO, RACF, JES, CICS
3. **Trust Graph** - Visualize relationships
4. **Local AI** - No data leaves your machine
5. **Hands-On** - Learn by doing

## Resources

- `/docs` - API documentation
- `/architecture` - System design
- `README.md` - Quick start guide
- `MODULES.md` - Code documentation

**Speaker Notes:**
> Wrap up with the key concepts. Direct them to resources for continued learning.

---

# Appendix: File Structure

```
mainframe_ai_assistant/
├── run.py                 # Entry point
├── app/                   # FastAPI application
│   ├── routes/            # API endpoints
│   ├── services/          # Business logic
│   └── constants/         # Config & prompts
├── agent_tools.py         # TN3270 connection
├── trust_graph.py         # Graph data model
├── graph_tools.py         # Graph analysis
├── rag_engine.py          # Knowledge retrieval
├── recon_engine.py        # Enumeration tools
├── templates/             # HTML templates
├── static/                # CSS & JS
└── docs/                  # Documentation
```

---

# Appendix: Running the Demo

## Quick Start Commands

```bash
# Start TK5 mainframe
./start_mvs.sh

# Start the toolkit
python run.py --port 8080

# Open in browser
open http://localhost:8080
```

## Requirements
- Python 3.10+
- Ollama with llama3.1:8b
- TK5 mainframe (for live demos)
