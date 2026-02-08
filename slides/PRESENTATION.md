# Mainframe Security Toolkit
## Teaching Presentation Guide

---

# Slide 1: Title

## **Mainframe Security Toolkit**
### AI-Powered Mainframe Operations & Security Assessment

**Key Points:**
- Local-first design (no cloud APIs, no data leaves your machine)
- Ollama LLM for AI capabilities
- Live TN3270 terminal with click-to-analyze
- Retro IBM Lumon-style CRT interface
- Red team focused methodology
- 14+ integrated tools in one platform

**Speaker Notes:**
> This toolkit is designed for security professionals learning mainframe operations. Everything runs locally - no data leaves your machine. The retro IBM interface isn't just aesthetic — it reinforces the mental model of interacting with a real mainframe terminal.

---

# Slide 2: The 5 Findings Areas

## Core Methodology Framework

| # | Finding | Focus Area |
|---|---------|------------|
| F1 | Identity Binding | Where is identity bound? |
| F2 | Authority Evaluation | When is authority evaluated? |
| F3 | Deferred Execution | What executes later than expected? |
| F4 | Policy Enforcement | Which subsystem enforces policy? |
| F5 | Imported Assumptions | What assumptions are you importing? |

**Speaker Notes:**
> These 5 findings areas form the assessment framework. Every screen, every action should be evaluated against these areas. They help identify security gaps in mainframe environments. This is the same model that exposed ADCS abuse and Kerberos delegation attacks in Active Directory.

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

# Slide 9: Module - Test & Report

## `recon_engine.py` - Enumeration & Findings

**Purpose:** Native Python TN3270 enumeration and pentest reporting

**Enumerators:**
| Class | Target | Method |
|-------|--------|--------|
| `TSOEnumerator` | TSO userids | Logon probing |
| `CICSEnumerator` | Transactions | CESN/CEMT |
| `VTAMEnumerator` | APPLIDs | LOGON attempts |

**Detectors & Reporting:**
- `HiddenFieldDetector` - Find hidden screen fields
- `ScreenAnalyzer` - Security findings detection
- `ApplicationMapper` - Map application paths
- Report generation in JSON, Markdown, and HTML
- Findings organized by F1–F5 areas

**Speaker Notes:**
> This reimplements classic mainframe enumeration in Python. No external tools needed. All I/O goes through our TN3270 connection. Reports are organized by findings areas, not questions.

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
- System Inspection, Dataset Model, Address Spaces

**How It Works:**
1. Auto-connects to mainframe
2. Sends keystrokes automatically
3. Narrates each step with AI
4. Maps to F1–F5 findings areas

**Speaker Notes:**
> Great for demonstrations. The system drives itself through the mainframe while explaining what's happening. Audience just watches and learns. Seven walkthroughs cover all five control planes.

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
| Frontend | Vanilla JS + IBM Plex Mono + Retro IBM CSS |
| LLM | Ollama (local) |
| Embeddings | Ollama (nomic-embed) |
| Terminal | py3270 / TN3270 |
| Visualization | D3.js (trust graph) |
| UI Theme | IBM Retro / Lumon CRT aesthetic |

**Key Design Decisions:**
- No cloud APIs = air-gapped capable
- File-based storage = portable
- Modular architecture = extensible (14 route modules)
- Click-to-analyze = instant AI on any terminal line
- Hover hints = contextual help everywhere

**Speaker Notes:**
> Everything runs locally. You can use this on a disconnected network. The retro IBM aesthetic with IBM Plex Mono font reinforces the mainframe mental model. The click-to-analyze feature means every line on screen becomes a teaching moment.

---

# Slide 15: Demo Sequence

## Suggested Demo Flow

1. **Home Screen** (2 min)
   - Show retro CRT terminal with live overlay
   - Click a terminal line → AI analysis appears
   - Hover over control plane cards → descriptions appear
   - Show invisible toolbar reveal on hover

2. **Terminal Connection** (3 min)
   - Connect to TK5 via toolbar CONNECT button
   - Navigate to TSO logon
   - Click lines to explain what's on screen

3. **Walkthrough** (5 min)
   - Run Session Stack walkthrough
   - Show F1–F5 findings tracking
   - AI narrates each control plane boundary

4. **Abstract Models** (3 min)
   - Click terminal lines to map against mental models
   - Show Session Stack, Control Planes, Trust Boundaries

5. **Trust Graph** (3 min)
   - Load demo data
   - Run path queries
   - Show BloodHound-style visualization

6. **Test & Report** (4 min)
   - Run TSO enumeration
   - Show findings (not questions)
   - Generate pentest report

**Speaker Notes:**
> This 20-minute demo hits all major features. Start with the home screen — the retro CRT visual is a strong opener. Click-to-analyze is the most impressive feature for live demos. Adjust timing based on audience questions.

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

1. **5 Findings Areas** - F1–F5 framework for every assessment
2. **5 Control Planes** - VTAM, TSO, RACF, JES, CICS
3. **Click-to-Analyze** - Every terminal line is a learning moment
4. **Trust Graph** - Visualize relationships like BloodHound for AD
5. **Local AI** - No data leaves your machine
6. **Hands-On** - 14+ tools, labs, walkthroughs, and reports

## Resources

- `/` - Home screen with live terminal
- `/abstract-models` - Mental model explorer
- `/docs` - API documentation
- `/architecture` - System design
- `README.md` - Quick start guide
- `MODULES.md` - Code documentation

**Speaker Notes:**
> Wrap up with the key concepts. The click-to-analyze feature is the most memorable demo moment — use it throughout. Direct them to the abstract models page for continued self-study.

---

# Appendix: File Structure

```
mainframe_ai_assistant/
├── run.py                 # Entry point
├── app/                   # FastAPI application
│   ├── routes/            # API endpoints (14 modules)
│   ├── services/          # Business logic
│   └── constants/         # Config & prompts
├── agent_tools.py         # TN3270 connection
├── trust_graph.py         # Graph data model
├── graph_tools.py         # Graph analysis
├── rag_engine.py          # Knowledge retrieval
├── recon_engine.py        # Enumeration & findings
├── methodology_engine.py  # Assessment methodology
├── ai_bridge.py           # CICS AI bridge
├── templates/             # HTML templates (16 pages)
├── static/                # CSS, JS, fonts, images
├── slides/                # Presentation assets
├── lab_data/              # Lab exercises (JSON)
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
