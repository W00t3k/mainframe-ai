# CICS AI Assistant for MVS 3.8j

> "CICS as an interface to modern intelligence" — not AI on the mainframe, but mainframe as control plane.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER WORKSTATION                               │
│                         ┌─────────────────┐                              │
│                         │  3270 Terminal  │                              │
│                         │   (c3270/x3270) │                              │
│                         └────────┬────────┘                              │
└──────────────────────────────────┼──────────────────────────────────────┘
                                   │ TN3270 (port 3270)
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         HERCULES / MVS 3.8j                              │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                          KICKS (CICS)                            │    │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │    │
│  │  │  AIMP (BMS)  │───▶│ AIPGM (COBOL)│───▶│  TCP Socket  │       │    │
│  │  │  Screen Map  │    │  Transaction │    │  Interface   │       │    │
│  │  └──────────────┘    └──────────────┘    └──────┬───────┘       │    │
│  └─────────────────────────────────────────────────┼───────────────┘    │
└────────────────────────────────────────────────────┼────────────────────┘
                                                     │ TCP (port 5000)
                                                     │ via CTCA/TCP bridge
                                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           HOST MACHINE                                   │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      AI Bridge (Python)                          │    │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │    │
│  │  │  FastAPI     │───▶│  Ollama LLM  │───▶│  Response    │       │    │
│  │  │  /api/ask    │    │  (local)     │    │  Formatter   │       │    │
│  │  └──────────────┘    └──────────────┘    └──────────────┘       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

## Transaction Flow

```
1. User enters transaction: AIMP
2. KICKS displays BMS screen (AIMAPS)
3. User types question, presses ENTER
4. COBOL program (AIPGM) receives input
5. Program formats request, opens TCP socket
6. Sends query to AI Bridge (host:5000)
7. AI Bridge calls Ollama, gets response
8. Response sent back via TCP
9. COBOL program formats response
10. BMS screen updated with answer
11. User can ask another question or PF3 to exit
```

## Components

### 1. BMS Screen Map (AIMAPS)

Location: `kicks/bms/AIMAPS.bms`

```
┌────────────────────────────────────────────────────────────────────────────┐
│ AI MAINFRAME ASSISTANT                                      DATE: MM/DD/YY │
│ ══════════════════════════════════════════════════════════════════════════ │
│                                                                            │
│ Enter your question:                                                       │
│ > ________________________________________________________________________ │
│                                                                            │
│ Response:                                                                  │
│ ┌────────────────────────────────────────────────────────────────────────┐ │
│ │                                                                        │ │
│ │                                                                        │ │
│ │                                                                        │ │
│ │                                                                        │ │
│ │                                                                        │ │
│ │                                                                        │ │
│ │                                                                        │ │
│ │                                                                        │ │
│ └────────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│ Status: READY                                                              │
│ ══════════════════════════════════════════════════════════════════════════ │
│ PF3=Exit  PF12=Clear  ENTER=Submit                                         │
└────────────────────────────────────────────────────────────────────────────┘
```

### 2. COBOL Program (AIPGM)

Location: `kicks/cobol/AIPGM.cob`

Transaction ID: `AIMP`

### 3. Python AI Bridge

Location: `ai_bridge.py`

Endpoint: `POST /api/ask`

### 4. Table Entries Required

**PCT (Program Control Table):**
```
KIKPCT TRANSID=AIMP,PROGRAM=AIPGM,TWASIZE=0
```

**PPT (Processing Program Table):**
```
KIKPPT PROGRAM=AIPGM,PGMLANG=COBOL
KIKPPT MAPSET=AIMAPS
```

---

## Networking Approach

### Option A: Simple HTTP via TSO Batch (Recommended for Demo)

Since MVS 3.8j doesn't have native TCP sockets in CICS, we use a simpler approach:

1. CICS writes query to a dataset
2. Background job reads dataset, calls API
3. Response written to another dataset
4. CICS reads response

This is **synchronous enough** for demo purposes with a short polling interval.

### Option B: Direct Socket (Advanced)

Use Hercules CTCA (Channel-to-Channel Adapter) for TCP/IP:

1. Configure CTCA in Hercules
2. Use MVS TCP/IP stack (if installed)
3. Direct socket calls from COBOL

For demo purposes, **Option A is recommended**.

---

## Installation Steps

### 1. Copy BMS Source to KICKS
```
Copy kicks/bms/AIMAPS.bms to KICKS.KICKS.V1R5M0.MAPSRC(AIMAPS)
```

### 2. Assemble BMS Map
```
Submit KICKS.KICKSSYS.V1R5M0.PROCLIB(KIKASM) with AIMAPS
```

### 3. Copy COBOL Source to KICKS
```
Copy kicks/cobol/AIPGM.cob to KICKS.KICKS.V1R5M0.COB(AIPGM)
```

### 4. Compile COBOL Program
```
Submit KICKS.KICKSSYS.V1R5M0.PROCLIB(KIKCOB) with AIPGM
```

### 5. Update PCT Table
Add AIMP transaction to PCT, reassemble

### 6. Update PPT Table
Add AIPGM and AIMAPS to PPT, reassemble

### 7. Start AI Bridge
```bash
python ai_bridge.py
```

### 8. Start KICKS and Test
```
EXEC 'KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)'
CLEAR
AIMP
```

---

## Security Considerations

| Concern | Mitigation |
|---------|------------|
| Input injection | Limit input to 72 chars, sanitize special chars |
| Response overflow | Truncate AI response to 800 chars (10 lines × 80) |
| Timeout | 10-second timeout on TCP calls |
| DoS | Rate limit at AI Bridge (1 req/sec) |
| Data exposure | No sensitive data in prompts, local LLM only |

---

## Demo Script

```
1. Show TK5/MVS running
2. Start KICKS: EXEC 'KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)'
3. Press CLEAR
4. Enter: AIMP
5. Screen shows AI Assistant interface
6. Type: "What is a JCL job?"
7. Press ENTER
8. AI response appears in response area
9. Show Trust Graph integration
10. Show Tutor cross-reference
```

---

## Conference Positioning

### Strong Narrative

"This isn't AI running on the mainframe. This is the mainframe as a **control plane** for modern intelligence. The same interface operators have used for 50 years, now connected to AI that understands their context."

### Combined with Trust Graph

"When you ask a question, the AI doesn't just answer — it references the Trust Graph to understand your current security posture. It knows which datasets you have access to, which jobs are running under your identity, and what RACF profiles govern your actions."

### Why This Matters

1. **Enterprise Pattern** — This is exactly how modern mainframe shops integrate AI
2. **Visual** — 3270 green screen + AI is visually striking
3. **Authentic** — Uses real CICS patterns, not a hack
4. **Defensible** — "This is how you'd actually do it"

---

## File Locations

| Component | Path |
|-----------|------|
| Architecture Doc | `docs/CICS_AI_ASSISTANT.md` |
| BMS Map Source | `kicks/bms/AIMAPS.bms` |
| COBOL Program | `kicks/cobol/AIPGM.cob` |
| AI Bridge | `ai_bridge.py` |
| JCL for Assembly | `kicks/jcl/ASMMAP.jcl` |
| JCL for Compile | `kicks/jcl/COBCOMP.jcl` |
