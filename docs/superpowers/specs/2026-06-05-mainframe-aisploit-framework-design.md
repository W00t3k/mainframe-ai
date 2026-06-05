# mainframe-aisploit Framework Design

**Date**: 2026-06-05
**Status**: Approved
**Branch**: `mainframe-aisploit`

## Overview

A graph-centric mainframe security assessment framework that orchestrates Metasploit modules with AI-powered explainability, checkpoint-gated autonomous execution, and full engagement provenance.

**Core Thesis**: "Metasploit tells you what happened, BigIron explains why it matters."

## Use Case

Both a real authorized pentest tool AND a training/demo platform for conferences (Arsenal, CypherCon, Security Fest).

## Design Approach

**Graph-Centric**: The provenance graph is the core data model. Everything reads from and writes to it. The graph IS the engagement record.

---

## 1. Core Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      PROVENANCE GRAPH                               │
│  (Single source of truth - all components read/write here)         │
│                                                                     │
│  Nodes: Targets, Modules, Findings, Users, Datasets, Jobs, etc.   │
│  Edges: DISCOVERED_BY, EXECUTED_AGAINST, GRANTED_ACCESS_TO, etc.  │
│  Metadata: timestamp, authorization_ref, raw_output, agent_turn    │
└────────────────────────────┬────────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  MSF LAYER    │    │  AGENT LAYER  │    │  REPORT LAYER │
│               │    │               │    │               │
│ • Catalog     │    │ • Reads graph │    │ • Queries     │
│ • RPC client  │    │ • Proposes    │    │   graph       │
│ • Execution   │    │   actions     │    │ • Templates   │
│ • Output      │    │ • Checkpoints │    │ • Exports     │
│   parsing     │    │ • Explains    │    │ • Compliance  │
└───────┬───────┘    └───────┬───────┘    └───────────────┘
        │                    │
        ▼                    ▼
┌─────────────────────────────────────┐
│         AUTHORIZATION GATE          │
│  (Human approves before execution)  │
│  • Preview what will run            │
│  • Engagement reference required    │
│  • Logged to graph as AUTHORIZED    │
└─────────────────────────────────────┘
```

**Key Principle**: Nothing executes without going through the graph.

**Persistence**: SQLite for the graph (not JSON files) - supports concurrent access, complex queries, and scales to real engagements.

---

## 2. Provenance Graph Schema

### Node Types

| Category | Node Types | Description |
|----------|------------|-------------|
| **Target** | `Host`, `Service`, `Credential` | What you're assessing |
| **Mainframe** | `User`, `Dataset`, `Job`, `Transaction`, `Program`, `Loadlib`, `CICSRegion`, `Panel` | Discovered mainframe entities |
| **Module** | `MsfModule`, `CustomModule`, `ReconTool` | Available tools (imported from MSF + built-in) |
| **Execution** | `ModuleRun`, `Checkpoint`, `Authorization` | What happened during the engagement |
| **Finding** | `Vulnerability`, `Misconfiguration`, `AccessPath` | Assessment results |

### Edge Types

| Edge | From → To | Provenance Metadata |
|------|-----------|---------------------|
| `TARGETS` | ModuleRun → Host/Service | timestamp, options |
| `DISCOVERED` | ModuleRun → User/Dataset/etc | raw_output, parser |
| `AUTHORIZED_BY` | ModuleRun → Authorization | operator, engagement_ref |
| `CHECKPOINT_AT` | ModuleRun → Checkpoint | state, agent_reasoning |
| `GRANTED_ACCESS` | Credential → User/Service | privilege_level |
| `ATTACK_PATH` | ModuleRun → ModuleRun | sequence, dependency |
| `MAPS_TO` | Finding → ComplianceControl | framework (NIST/PCI), control_id |

### Provenance Metadata on Every Edge

```python
{
    "timestamp": "2026-06-05T14:23:01Z",
    "authorization_ref": "ENG-2026-0042",
    "agent_turn": 7,
    "raw_output": "...",
    "parsed_entities": [...],
    "recording_id": null  # If from playback
}
```

### Module Import Flow

```
MSF RPC (live)                    Graph
     │                              │
     ▼                              ▼
search("mainframe") ──────► MsfModule nodes created
     │                       (type, path, rank, description)
     │
use("auxiliary/...") ─────► Options, references, targets
                             added as node properties
```

Custom modules in `~/.msf4/modules/` or BigIron's `modules/` dir get the same treatment.

---

## 3. MSF Integration Layer

### Components

```
┌─────────────────────────────────────────────────────────────────┐
│                     MSF INTEGRATION LAYER                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Catalog    │    │   Executor   │    │   Parser     │      │
│  │   Service    │    │   Service    │    │   Registry   │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  • Connect to msfrpcd  • Authorization gate  • Module-specific │
│  • Search/filter       • Set options           output parsers  │
│  • Import to graph     • Run in console      • Entity          │
│  • Watch for new       • Capture output        extraction      │
│    modules             • Stream to graph     • Finding         │
│                                                classification  │
└─────────────────────────────────────────────────────────────────┘
```

### Catalog Service

```python
class CatalogService:
    def sync_from_msf(self) -> int:
        """Pull all mainframe modules from live MSF instance"""

    def sync_from_directory(self, path: str) -> int:
        """Import custom .rb modules from local directory"""

    def get_module(self, mtype: str, path: str) -> MsfModule:
        """Fetch full module detail (options, refs, targets)"""

    def search(self, query: str, filters: dict) -> list[MsfModule]:
        """Search graph for modules matching criteria"""
```

### Executor Service

```python
class ExecutorService:
    def preview(self, module: MsfModule, options: dict) -> ExecutionPreview:
        """Show exactly what will run - no execution"""

    def execute(self,
                module: MsfModule,
                options: dict,
                authorization: Authorization) -> ModuleRun:
        """
        Execute with full provenance:
        1. Validate authorization exists and is current
        2. Create ModuleRun node in graph
        3. Link AUTHORIZED_BY edge
        4. Run module via MSF RPC console
        5. Stream output, parse entities
        6. Create DISCOVERED edges for each entity
        7. Return completed ModuleRun
        """

    def execute_chain(self,
                      chain: list[ModuleRun],
                      checkpoints: list[Checkpoint]) -> ChainResult:
        """Execute multiple modules with checkpoint pauses"""
```

### Parser Registry

| Module Pattern | Parser | Extracts |
|----------------|--------|----------|
| `ftp_jcl_*` | `JCLOutputParser` | Job ID, return codes, datasets accessed |
| `tso_enum` | `TSOEnumParser` | Usernames, groups, attributes |
| `cics_*` | `CICSParser` | Transactions, regions, programs |
| `vtam_*` | `VTAMParser` | APPLIDs, network topology |
| `racf_*` | `RACFParser` | Profiles, permissions, access levels |
| `*` (fallback) | `GenericParser` | Regex-based entity extraction |

Parsers register via decorator:

```python
@parser_for("auxiliary/admin/mainframe/tk5_jcl_submit")
class TK5JCLParser(OutputParser):
    def parse(self, raw_output: str) -> list[Entity]:
        # Extract JOB ID, status, etc.
```

---

## 4. Agent Architecture

### Agent Loop with Graph State

```
┌─────────────────────────────────────────────────────────────────┐
│                        AGENT LOOP                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────┐      ┌─────────┐      ┌─────────┐                │
│   │  THINK  │ ───► │  ACT    │ ───► │ OBSERVE │ ───┐           │
│   └─────────┘      └─────────┘      └─────────┘    │           │
│        ▲                                            │           │
│        └────────────────────────────────────────────┘           │
│                                                                  │
│   State = Graph snapshot + Goal + Constraints                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Tools Available to Agent

| Tool | Category | Description |
|------|----------|-------------|
| `search_modules` | Read | Query graph for modules matching criteria |
| `inspect_module` | Read | Get full module detail + AI explanation |
| `query_graph` | Read | Run graph queries (paths, neighbors, findings) |
| `search_redbooks` | Read | RAG query against IBM documentation |
| `read_screen` | Read | Current 3270 terminal state |
| `propose_execution` | Propose | Suggest module + options - does NOT execute |
| `propose_chain` | Propose | Suggest multi-step attack path |
| `explain_finding` | Read | Generate explanation for a graph node |
| `check_checkpoint` | Read | Get current checkpoint status |

**Critical**: No `execute` tool. Agent proposes, human authorizes.

### Checkpoint System

```python
class Checkpoint(Enum):
    RECON_COMPLETE = "recon_complete"
    INITIAL_ACCESS = "initial_access"
    PRIVILEGE_ESCALATION = "priv_esc"
    LATERAL_MOVEMENT = "lateral"
    OBJECTIVE_REACHED = "objective"
    CUSTOM = "custom"
```

### Agent Flow with Checkpoints

```
User: "Assess this mainframe for JCL injection vulnerabilities"
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1: RECON                                              │
│ Agent proposes: [ftp_enum, jes_enum, tso_enum]             │
│ ──► Human authorizes phase ◄──                             │
│ Agent executes, findings populate graph                     │
│ ──► CHECKPOINT: RECON_COMPLETE ◄──                         │
│ Agent summarizes findings, human decides: Continue/Stop     │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ PHASE 2: INITIAL ACCESS                                     │
│ Agent proposes: [ftp_jcl_submit against discovered target] │
│ ──► Human authorizes with engagement ref ◄──               │
│ Agent executes, graph updated with attack path              │
│ ──► CHECKPOINT: INITIAL_ACCESS ◄──                         │
└─────────────────────────────────────────────────────────────┘
```

### Agent State Persistence

Agent state lives in the graph:

```python
agent_turn = AgentTurn(
    turn_number=7,
    reasoning="FTP enumeration revealed JES mode enabled...",
    tool_calls=[...],
    proposed_actions=[...],
    checkpoint="recon_complete"
)
graph.add_node(agent_turn)
graph.add_edge(agent_turn, engagement, "PART_OF")
```

Benefits:
- Resume engagement after closing app
- Review agent reasoning in graph
- Include reasoning in reports

---

## 5. Demo/Hybrid Mode

### Mode Detection

```python
class ExecutionMode(Enum):
    LIVE = "live"
    RECORDED = "recorded"
    HYBRID = "hybrid"  # Auto-select per module
```

### Module Compatibility Matrix

| Module | Works on TK5 | Requires Modern z/OS | Demo Strategy |
|--------|--------------|----------------------|---------------|
| `tk5_jcl_submit` | Yes | - | Live |
| `ftp_jcl_creds` | Yes (if FTP+JES) | - | Live |
| `tso_enum` | Yes | - | Live |
| `vtam_enum` | Yes | - | Live |
| `cics_enum` | Yes (KICKS) | - | Live |
| `racf_*` | Partial (RAKF) | Full RACF | Recorded |
| `db2_*` | No | DB2 | Recorded |
| `mq_*` | No | MQ Series | Recorded |
| `zos_*` | No | z/OS specific | Recorded |

### Recording Structure

```
data/recordings/
├── index.json
├── auxiliary__scanner__ftp_jcl_creds/
│   ├── metadata.json
│   ├── output.txt
│   ├── entities.json
│   └── screenshots/
```

### Playback Flow

```python
class RecordedExecutor:
    def playback(self, module: MsfModule, options: dict) -> ModuleRun:
        recording = self.load_recording(module.path)

        run = ModuleRun(
            module=module,
            options=options,
            simulated=True,
            recording_ref=recording.id
        )

        # Replay with realistic timing
        for line in recording.output_lines:
            await asyncio.sleep(line.delay)
            self.stream_output(line.text)

        # Load pre-parsed entities with simulated flag
        for entity in recording.entities:
            entity.provenance.simulated = True
            graph.add_node(entity)
            graph.add_edge(run, entity, "DISCOVERED")

        return run
```

### UI Indication

Simulated executions display clear `[SIMULATED]` badge with recording date and original target type.

---

## 6. Report Generation

### Report Architecture

```
Graph ──► Queries ──► Data ──► Templates ──► Output
```

### Report Data Model

```python
@dataclass
class EngagementReport:
    engagement_ref: str
    client_name: str
    assessment_dates: tuple[date, date]
    scope: list[str]

    executive_summary: str           # AI-generated
    findings: list[Finding]          # Severity-sorted
    attack_paths: list[AttackPath]   # Graph traversals
    timeline: list[TimelineEvent]    # Chronological execution

    compliance_mappings: dict[str, list[ControlMapping]]

    module_runs: list[ModuleRun]
    screenshots: list[Screenshot]
    graph_export: GraphExport

@dataclass
class Finding:
    id: str
    title: str
    severity: Severity
    description: str
    evidence: list[Evidence]
    affected_assets: list[Node]
    attack_path: AttackPath | None
    remediation: str                # AI-generated
    compliance: list[ControlMapping]
```

### Compliance Frameworks

```python
COMPLIANCE_MAPPINGS = {
    "NIST_800_53": {
        "jcl_injection": ["AC-3", "AC-6", "CM-7", "SI-10"],
        "weak_racf_profile": ["AC-2", "AC-3", "IA-5"],
        "unencrypted_ftp": ["SC-8", "SC-13"],
        "excess_apf_auth": ["AC-6", "CM-5"],
    },
    "PCI_DSS_4": {
        "jcl_injection": ["6.5.1", "7.1", "7.2"],
        "weak_racf_profile": ["7.1", "8.2", "8.3"],
    },
    "DISA_STIG": {
        # Populated from DISA z/OS STIG during implementation
        # See: https://public.cyber.mil/stigs/
    }
}
```

### Template Structure

```
templates/reports/
├── base/
│   ├── executive_summary.md.j2
│   ├── findings.md.j2
│   ├── timeline.md.j2
│   ├── attack_paths.md.j2
│   └── appendix.md.j2
├── clients/
│   ├── default/
│   │   └── config.yaml
│   └── {client_name}/
│       ├── config.yaml
│       ├── logo.png
│       └── overrides/
├── compliance/
│   ├── nist_800_53.md.j2
│   ├── pci_dss_4.md.j2
│   └── disa_stig.md.j2
└── formats/
    ├── markdown.j2
    ├── html.j2
    └── pdf_styles.css
```

### Output Package

```
exports/ENG-2026-0042/
├── report.md
├── report.pdf
├── executive_summary.pdf
├── findings.json                # SARIF-like
├── compliance/
│   ├── nist_800_53.md
│   └── pci_dss_4.md
├── evidence/
│   ├── screenshots/
│   ├── module_outputs/
│   └── terminal_captures/
├── graph/
│   ├── full_graph.json
│   ├── attack_paths.dot
│   └── attack_paths.svg
└── timeline.json
```

### API Endpoints

```
POST /api/report/generate
{
    "engagement_ref": "ENG-2026-0042",
    "template": "default",
    "formats": ["markdown", "pdf", "json"],
    "compliance_frameworks": ["NIST_800_53", "PCI_DSS_4"],
    "include_evidence": true
}

GET /api/report/{engagement_ref}/download
→ ZIP of complete package
```

---

## 7. Component Summary

| Component | Purpose | Key Files |
|-----------|---------|-----------|
| **Provenance Graph** | SQLite-backed graph storing all entities, executions, findings | `core/graph.py`, `core/schema.py` |
| **MSF Layer** | Catalog import, RPC execution, output parsing | `msf/catalog.py`, `msf/executor.py`, `msf/parsers/` |
| **Agent** | Autonomous reasoning with checkpoint pauses | `agent/loop.py`, `agent/tools.py`, `agent/checkpoints.py` |
| **Authorization Gate** | Human-in-the-loop before any execution | `core/authorization.py` |
| **Demo Mode** | Hybrid live/recorded execution | `demo/recorder.py`, `demo/playback.py` |
| **Reports** | Template-driven compliance-mapped outputs | `reports/engine.py`, `templates/reports/` |

---

## 8. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Graph as single source of truth | Everything derives from graph - no scattered state |
| Agent proposes, never executes | Structural safety, not prompt-based |
| Checkpoints at phase boundaries | Human stays in control of escalation |
| Module import from live MSF | Always current, custom modules auto-discovered |
| Hybrid demo mode | Honest about TK5 limits, recorded for modern z/OS |
| Provenance on every edge | Engagement record writes itself |
| Template-driven reports | Client branding, compliance mapping |

---

## 9. Out of Scope (For Now)

- Multi-user collaboration / session sharing
- Cloud deployment / horizontal scaling
- Real-time SIEM integration
- Automated remediation execution
- Mobile/tablet interface

---

## 10. Next Steps

Transition to implementation planning via `writing-plans` skill.
