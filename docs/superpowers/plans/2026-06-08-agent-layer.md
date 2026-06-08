# Agent Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the AI agent layer with tool schema, Think/Act/Observe loop, checkpoint system, and graph-based state persistence.

**Architecture:** Agent reads graph state, proposes actions via tools, human authorizes at checkpoints. Agent state persists as nodes in the graph. Agent PROPOSES but never EXECUTES directly.

**Tech Stack:** Python 3.11+, Pydantic v2, existing bigiron.core and bigiron.msf, pytest

**Depends on:** Plan 1 (Provenance Graph Core) - COMPLETE, Plan 2 (MSF Integration Layer) - COMPLETE

---

## File Structure

```
bigiron/
├── agent/
│   ├── __init__.py
│   ├── schema.py         # Tool definitions, AgentTurn, Checkpoint
│   ├── tools.py          # Tool implementations (read-only + propose)
│   ├── loop.py           # AgentLoop class with think/act/observe
│   └── checkpoints.py    # Checkpoint management
└── tests/
    └── agent/
        ├── __init__.py
        ├── test_schema.py
        ├── test_tools.py
        ├── test_loop.py
        └── test_checkpoints.py
```

---

## Task 1: Agent Schema and Models

**Files:**
- Create: `bigiron/agent/__init__.py`
- Create: `bigiron/agent/schema.py`
- Create: `bigiron/tests/agent/__init__.py`
- Create: `bigiron/tests/agent/test_schema.py`

- [ ] **Step 1: Create package structure**

```bash
mkdir -p bigiron/agent bigiron/tests/agent
touch bigiron/agent/__init__.py bigiron/tests/agent/__init__.py
```

- [ ] **Step 2: Write failing test for agent schema**

```python
# bigiron/tests/agent/test_schema.py
import pytest
from datetime import datetime, timezone


def test_checkpoint_enum():
    from bigiron.agent.schema import Checkpoint

    assert Checkpoint.RECON_COMPLETE.value == "recon_complete"
    assert Checkpoint.INITIAL_ACCESS.value == "initial_access"
    assert Checkpoint.PRIVILEGE_ESCALATION.value == "priv_esc"


def test_tool_call_creation():
    from bigiron.agent.schema import ToolCall

    call = ToolCall(
        tool_name="search_modules",
        arguments={"query": "mainframe", "mtype": "auxiliary"}
    )

    assert call.tool_name == "search_modules"
    assert call.arguments["query"] == "mainframe"


def test_proposed_action_creation():
    from bigiron.agent.schema import ProposedAction

    action = ProposedAction(
        module_path="auxiliary/scanner/mainframe/tso_enum",
        options={"RHOSTS": "127.0.0.1"},
        reasoning="TSO enumeration to discover valid users",
        risk_level="low"
    )

    assert action.module_path == "auxiliary/scanner/mainframe/tso_enum"
    assert action.risk_level == "low"


def test_agent_turn_creation():
    from bigiron.agent.schema import AgentTurn, ToolCall, Checkpoint

    turn = AgentTurn(
        turn_number=1,
        reasoning="Starting reconnaissance phase",
        tool_calls=[
            ToolCall(tool_name="search_modules", arguments={"query": "enum"})
        ],
        checkpoint=Checkpoint.RECON_COMPLETE
    )

    assert turn.turn_number == 1
    assert len(turn.tool_calls) == 1
    assert turn.checkpoint == Checkpoint.RECON_COMPLETE


def test_agent_turn_to_node():
    from bigiron.agent.schema import AgentTurn, Checkpoint
    from bigiron.core.schema import NodeType

    turn = AgentTurn(
        turn_number=3,
        reasoning="Analyzing discovered users",
        tool_calls=[],
        checkpoint=None
    )

    node = turn.to_node()

    assert node.node_type == NodeType.AGENT_TURN
    assert node.properties["turn_number"] == 3
    assert "Analyzing" in node.properties["reasoning"]


def test_agent_state_creation():
    from bigiron.agent.schema import AgentState, Checkpoint

    state = AgentState(
        engagement_ref="ENG-2026-001",
        goal="Assess mainframe for JCL injection vulnerabilities",
        current_turn=0,
        current_checkpoint=None,
        completed_checkpoints=[]
    )

    assert state.engagement_ref == "ENG-2026-001"
    assert state.current_turn == 0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/agent/test_schema.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 4: Implement agent schema**

```python
# bigiron/agent/schema.py
"""Agent schema and models."""
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

from ..core.schema import Node, NodeType, Provenance


class Checkpoint(str, Enum):
    """Checkpoint types for agent execution phases."""
    RECON_COMPLETE = "recon_complete"
    INITIAL_ACCESS = "initial_access"
    PRIVILEGE_ESCALATION = "priv_esc"
    LATERAL_MOVEMENT = "lateral"
    OBJECTIVE_REACHED = "objective"
    CUSTOM = "custom"


class RiskLevel(str, Enum):
    """Risk level for proposed actions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolCall(BaseModel):
    """A tool call made by the agent."""
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    error: str | None = None


class ProposedAction(BaseModel):
    """An action proposed by the agent for human approval."""
    module_path: str
    options: dict[str, str]
    reasoning: str
    risk_level: str = "low"
    target_description: str = ""


class AgentTurn(BaseModel):
    """A single turn in the agent loop."""
    id: str = Field(default_factory=lambda: f"turn-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}")
    turn_number: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reasoning: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    checkpoint: Checkpoint | None = None

    def to_node(self) -> Node:
        """Convert to a graph node for persistence."""
        return Node(
            id=self.id,
            node_type=NodeType.AGENT_TURN,
            label=f"Turn {self.turn_number}",
            properties={
                "turn_number": self.turn_number,
                "reasoning": self.reasoning,
                "tool_calls": [tc.model_dump() for tc in self.tool_calls],
                "proposed_actions": [pa.model_dump() for pa in self.proposed_actions],
                "checkpoint": self.checkpoint.value if self.checkpoint else None
            },
            provenance=Provenance(agent_turn=self.turn_number)
        )


class AgentState(BaseModel):
    """Current state of the agent."""
    engagement_ref: str
    goal: str
    constraints: list[str] = Field(default_factory=list)
    current_turn: int = 0
    current_checkpoint: Checkpoint | None = None
    completed_checkpoints: list[Checkpoint] = Field(default_factory=list)
    awaiting_authorization: bool = False
    pending_actions: list[ProposedAction] = Field(default_factory=list)
```

- [ ] **Step 5: Add AGENT_TURN to NodeType enum**

Update `bigiron/core/schema.py` to add:
```python
AGENT_TURN = "agent_turn"
```

- [ ] **Step 6: Run tests**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/agent/test_schema.py -v`
Expected: All 7 tests PASS

- [ ] **Step 7: Commit**

```bash
git add bigiron/agent/ bigiron/tests/agent/ bigiron/core/schema.py
git commit -m "feat(agent): add agent schema and models

Agent models:
- Checkpoint: Phase boundaries (RECON_COMPLETE, etc.)
- ToolCall: Agent tool invocations
- ProposedAction: Actions awaiting human approval
- AgentTurn: Single turn with reasoning and calls
- AgentState: Current agent state"
```

---

## Task 2: Agent Tools (Read-Only)

**Files:**
- Create: `bigiron/agent/tools.py`
- Create: `bigiron/tests/agent/test_tools.py`

- [ ] **Step 1: Write failing test for tools**

```python
# bigiron/tests/agent/test_tools.py
import pytest


def test_search_modules_tool():
    from bigiron.agent.tools import AgentTools
    from bigiron.msf import MsfClient, CatalogService
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)

    tools = AgentTools(graph=graph, catalog=catalog)

    result = tools.search_modules(query="mainframe", mtype="auxiliary")

    assert len(result) >= 5
    assert all("mainframe" in m["path"] for m in result)

    graph.close()


def test_inspect_module_tool():
    from bigiron.agent.tools import AgentTools
    from bigiron.msf import MsfClient, CatalogService
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)

    tools = AgentTools(graph=graph, catalog=catalog)

    result = tools.inspect_module(
        mtype="auxiliary",
        path="admin/mainframe/tk5_jcl_submit"
    )

    assert result is not None
    assert result["name"] == "TK5 JCL Job Submission"
    assert len(result["options"]) >= 4

    graph.close()


def test_query_graph_stats():
    from bigiron.agent.tools import AgentTools
    from bigiron.msf import MsfClient, CatalogService
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)
    catalog.sync_to_graph()

    tools = AgentTools(graph=graph, catalog=catalog)

    result = tools.query_graph_stats()

    assert result["total_nodes"] >= 5
    assert "node_counts" in result

    graph.close()


def test_propose_execution_tool():
    from bigiron.agent.tools import AgentTools
    from bigiron.msf import MsfClient, CatalogService
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)

    tools = AgentTools(graph=graph, catalog=catalog)

    result = tools.propose_execution(
        module_path="auxiliary/scanner/mainframe/tso_enum",
        options={"RHOSTS": "127.0.0.1"},
        reasoning="Enumerate TSO users to find valid accounts"
    )

    assert result["status"] == "proposed"
    assert result["action"]["module_path"] == "auxiliary/scanner/mainframe/tso_enum"
    assert "awaiting authorization" in result["message"].lower()

    graph.close()


def test_get_tool_definitions():
    from bigiron.agent.tools import AgentTools
    from bigiron.msf import MsfClient, CatalogService
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)

    tools = AgentTools(graph=graph, catalog=catalog)

    definitions = tools.get_tool_definitions()

    assert len(definitions) >= 4
    tool_names = [t["name"] for t in definitions]
    assert "search_modules" in tool_names
    assert "propose_execution" in tool_names

    graph.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/agent/test_tools.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Implement agent tools**

```python
# bigiron/agent/tools.py
"""Agent tools for reading graph state and proposing actions."""
from typing import Any

from ..core.graph import ProvenanceGraph
from ..core.schema import NodeType
from ..msf import CatalogService
from .schema import ProposedAction, RiskLevel


class AgentTools:
    """Tools available to the agent.

    Read-only tools query the graph and MSF catalog.
    Propose tools create proposals that require human authorization.
    """

    def __init__(self, graph: ProvenanceGraph, catalog: CatalogService):
        """Initialize agent tools.

        Args:
            graph: Provenance graph for state queries
            catalog: MSF catalog for module lookup
        """
        self.graph = graph
        self.catalog = catalog
        self._pending_proposals: list[ProposedAction] = []

    # --- Read-only tools ---

    def search_modules(
        self,
        query: str,
        mtype: str | None = None
    ) -> list[dict[str, Any]]:
        """Search for modules matching criteria.

        Args:
            query: Search query string
            mtype: Optional module type filter

        Returns:
            List of module summaries
        """
        results = self.catalog.search(query, mtype)
        return [
            {
                "mtype": m.mtype,
                "path": m.path,
                "name": m.name,
                "full_path": m.full_path,
                "rank": m.rank
            }
            for m in results
        ]

    def inspect_module(
        self,
        mtype: str,
        path: str
    ) -> dict[str, Any] | None:
        """Get full details for a specific module.

        Args:
            mtype: Module type
            path: Module path

        Returns:
            Module details or None if not found
        """
        detail = self.catalog.get_module(mtype, path)
        if not detail:
            return None

        return {
            "mtype": detail.mtype,
            "path": detail.path,
            "name": detail.name,
            "full_path": detail.full_path,
            "description": detail.description,
            "authors": detail.authors,
            "options": [
                {
                    "name": opt.name,
                    "required": opt.required,
                    "description": opt.description,
                    "default": opt.default
                }
                for opt in detail.options
            ],
            "targets": detail.targets,
            "tk5_compatible": detail.tk5_compatible,
            "requires_modern_zos": detail.requires_modern_zos
        }

    def query_graph_stats(self) -> dict[str, Any]:
        """Get graph statistics.

        Returns:
            Statistics about the current graph state
        """
        stats = self.graph.stats()

        # Get counts by node type
        node_counts = {}
        for node_type in NodeType:
            nodes = list(self.graph.get_nodes_by_type(node_type))
            if nodes:
                node_counts[node_type.value] = len(nodes)

        return {
            **stats,
            "node_counts": node_counts
        }

    def query_graph_nodes(
        self,
        node_type: str,
        limit: int = 20
    ) -> list[dict[str, Any]]:
        """Query nodes of a specific type.

        Args:
            node_type: Node type to query
            limit: Maximum nodes to return

        Returns:
            List of node summaries
        """
        try:
            nt = NodeType(node_type)
        except ValueError:
            return []

        nodes = list(self.graph.get_nodes_by_type(nt))[:limit]
        return [
            {
                "id": n.id,
                "label": n.label,
                "properties": n.properties
            }
            for n in nodes
        ]

    def get_findings(self) -> list[dict[str, Any]]:
        """Get all findings from the graph.

        Returns:
            List of finding summaries
        """
        findings = list(self.graph.get_nodes_by_type(NodeType.FINDING))
        return [
            {
                "id": f.id,
                "label": f.label,
                "severity": f.properties.get("severity", "unknown"),
                "description": f.properties.get("description", "")
            }
            for f in findings
        ]

    # --- Proposal tools ---

    def propose_execution(
        self,
        module_path: str,
        options: dict[str, str],
        reasoning: str,
        risk_level: str = "low"
    ) -> dict[str, Any]:
        """Propose a module execution for human approval.

        This does NOT execute anything - it creates a proposal
        that the human operator must approve.

        Args:
            module_path: Full module path
            options: Module options
            reasoning: Why this action is recommended
            risk_level: low/medium/high/critical

        Returns:
            Proposal status
        """
        # Parse module path
        parts = module_path.split("/", 1)
        mtype = parts[0] if len(parts) > 1 else "auxiliary"
        path = parts[1] if len(parts) > 1 else module_path

        # Get module details for target description
        detail = self.catalog.get_module(mtype, path)
        target_desc = f"Target: {options.get('RHOSTS', options.get('RHOST', 'unknown'))}"

        action = ProposedAction(
            module_path=module_path,
            options=options,
            reasoning=reasoning,
            risk_level=risk_level,
            target_description=target_desc
        )

        self._pending_proposals.append(action)

        return {
            "status": "proposed",
            "action": action.model_dump(),
            "message": "Action proposed. Awaiting authorization from operator."
        }

    def get_pending_proposals(self) -> list[ProposedAction]:
        """Get all pending action proposals.

        Returns:
            List of proposed actions awaiting approval
        """
        return self._pending_proposals.copy()

    def clear_proposals(self):
        """Clear pending proposals after authorization decision."""
        self._pending_proposals.clear()

    # --- Tool definitions for LLM ---

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get tool definitions for LLM function calling.

        Returns:
            List of tool definitions in OpenAI function format
        """
        return [
            {
                "name": "search_modules",
                "description": "Search for MSF modules matching criteria",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "mtype": {
                            "type": "string",
                            "description": "Module type filter (auxiliary, exploit, etc.)"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "inspect_module",
                "description": "Get detailed information about a specific module",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mtype": {
                            "type": "string",
                            "description": "Module type"
                        },
                        "path": {
                            "type": "string",
                            "description": "Module path"
                        }
                    },
                    "required": ["mtype", "path"]
                }
            },
            {
                "name": "query_graph_stats",
                "description": "Get statistics about the current graph state",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "query_graph_nodes",
                "description": "Query nodes of a specific type from the graph",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "node_type": {
                            "type": "string",
                            "description": "Node type to query"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum nodes to return"
                        }
                    },
                    "required": ["node_type"]
                }
            },
            {
                "name": "propose_execution",
                "description": "Propose a module execution for human approval. Does NOT execute.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "module_path": {
                            "type": "string",
                            "description": "Full module path"
                        },
                        "options": {
                            "type": "object",
                            "description": "Module options"
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Why this action is recommended"
                        },
                        "risk_level": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "critical"],
                            "description": "Risk level of the action"
                        }
                    },
                    "required": ["module_path", "options", "reasoning"]
                }
            }
        ]

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a tool by name.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool result

        Raises:
            ValueError: If tool not found
        """
        tool_map = {
            "search_modules": self.search_modules,
            "inspect_module": self.inspect_module,
            "query_graph_stats": self.query_graph_stats,
            "query_graph_nodes": self.query_graph_nodes,
            "get_findings": self.get_findings,
            "propose_execution": self.propose_execution
        }

        if name not in tool_map:
            raise ValueError(f"Unknown tool: {name}")

        return tool_map[name](**arguments)
```

- [ ] **Step 4: Run tool tests**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/agent/test_tools.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add bigiron/agent/tools.py bigiron/tests/agent/test_tools.py
git commit -m "feat(agent): add agent tools

Agent tools:
- search_modules: Query MSF catalog
- inspect_module: Get module details
- query_graph_stats: Graph statistics
- query_graph_nodes: Query by node type
- propose_execution: Propose action (no execution)
- Tool definitions for LLM function calling"
```

---

## Task 3: Checkpoint Management

**Files:**
- Create: `bigiron/agent/checkpoints.py`
- Create: `bigiron/tests/agent/test_checkpoints.py`

- [ ] **Step 1: Write failing test for checkpoints**

```python
# bigiron/tests/agent/test_checkpoints.py
import pytest


def test_checkpoint_manager_creation():
    from bigiron.agent.checkpoints import CheckpointManager
    from bigiron.agent.schema import Checkpoint
    from bigiron.core.graph import ProvenanceGraph

    graph = ProvenanceGraph(":memory:")
    manager = CheckpointManager(graph=graph, engagement_ref="ENG-2026-001")

    assert manager.engagement_ref == "ENG-2026-001"
    assert manager.current_checkpoint is None

    graph.close()


def test_checkpoint_reach():
    from bigiron.agent.checkpoints import CheckpointManager
    from bigiron.agent.schema import Checkpoint
    from bigiron.core.graph import ProvenanceGraph
    from bigiron.core.schema import NodeType

    graph = ProvenanceGraph(":memory:")
    manager = CheckpointManager(graph=graph, engagement_ref="ENG-2026-001")

    result = manager.reach_checkpoint(
        checkpoint=Checkpoint.RECON_COMPLETE,
        summary="Reconnaissance phase complete. Found 3 valid TSO users."
    )

    assert result["checkpoint"] == "recon_complete"
    assert result["status"] == "reached"

    # Verify checkpoint node was created
    checkpoints = list(graph.get_nodes_by_type(NodeType.CHECKPOINT))
    assert len(checkpoints) == 1
    assert checkpoints[0].properties["checkpoint"] == "recon_complete"

    graph.close()


def test_checkpoint_sequence():
    from bigiron.agent.checkpoints import CheckpointManager
    from bigiron.agent.schema import Checkpoint
    from bigiron.core.graph import ProvenanceGraph

    graph = ProvenanceGraph(":memory:")
    manager = CheckpointManager(graph=graph, engagement_ref="ENG-2026-001")

    # Complete recon
    manager.reach_checkpoint(Checkpoint.RECON_COMPLETE, "Recon done")
    manager.approve_checkpoint(Checkpoint.RECON_COMPLETE)

    # Complete initial access
    manager.reach_checkpoint(Checkpoint.INITIAL_ACCESS, "Got JCL access")
    manager.approve_checkpoint(Checkpoint.INITIAL_ACCESS)

    assert Checkpoint.RECON_COMPLETE in manager.completed_checkpoints
    assert Checkpoint.INITIAL_ACCESS in manager.completed_checkpoints
    assert manager.current_checkpoint == Checkpoint.INITIAL_ACCESS

    graph.close()


def test_checkpoint_requires_approval():
    from bigiron.agent.checkpoints import CheckpointManager
    from bigiron.agent.schema import Checkpoint
    from bigiron.core.graph import ProvenanceGraph

    graph = ProvenanceGraph(":memory:")
    manager = CheckpointManager(graph=graph, engagement_ref="ENG-2026-001")

    manager.reach_checkpoint(Checkpoint.RECON_COMPLETE, "Recon done")

    assert manager.awaiting_approval is True
    assert manager.pending_checkpoint == Checkpoint.RECON_COMPLETE

    graph.close()


def test_checkpoint_deny():
    from bigiron.agent.checkpoints import CheckpointManager
    from bigiron.agent.schema import Checkpoint
    from bigiron.core.graph import ProvenanceGraph

    graph = ProvenanceGraph(":memory:")
    manager = CheckpointManager(graph=graph, engagement_ref="ENG-2026-001")

    manager.reach_checkpoint(Checkpoint.RECON_COMPLETE, "Recon done")
    manager.deny_checkpoint(Checkpoint.RECON_COMPLETE, reason="Need more enumeration")

    assert manager.awaiting_approval is False
    assert Checkpoint.RECON_COMPLETE not in manager.completed_checkpoints

    graph.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/agent/test_checkpoints.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Implement checkpoint manager**

```python
# bigiron/agent/checkpoints.py
"""Checkpoint management for agent execution phases."""
from datetime import datetime, timezone
from typing import Any

from ..core.graph import ProvenanceGraph
from ..core.schema import Node, NodeType, Provenance
from .schema import Checkpoint


class CheckpointManager:
    """Manages checkpoint state and transitions.

    Checkpoints are phase boundaries where the agent pauses
    for human review before proceeding.
    """

    def __init__(self, graph: ProvenanceGraph, engagement_ref: str):
        """Initialize checkpoint manager.

        Args:
            graph: Provenance graph for persistence
            engagement_ref: Engagement reference
        """
        self.graph = graph
        self.engagement_ref = engagement_ref
        self.current_checkpoint: Checkpoint | None = None
        self.completed_checkpoints: list[Checkpoint] = []
        self.pending_checkpoint: Checkpoint | None = None
        self.awaiting_approval: bool = False

    def reach_checkpoint(
        self,
        checkpoint: Checkpoint,
        summary: str
    ) -> dict[str, Any]:
        """Signal that a checkpoint has been reached.

        Args:
            checkpoint: The checkpoint reached
            summary: Summary of what was accomplished

        Returns:
            Checkpoint status
        """
        # Create checkpoint node
        node_id = f"checkpoint-{checkpoint.value}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        node = Node(
            id=node_id,
            node_type=NodeType.CHECKPOINT,
            label=f"Checkpoint: {checkpoint.value}",
            properties={
                "checkpoint": checkpoint.value,
                "summary": summary,
                "engagement_ref": self.engagement_ref,
                "status": "pending"
            },
            provenance=Provenance()
        )
        self.graph.add_node(node)

        self.pending_checkpoint = checkpoint
        self.awaiting_approval = True

        return {
            "checkpoint": checkpoint.value,
            "status": "reached",
            "message": f"Checkpoint {checkpoint.value} reached. Awaiting operator approval to continue.",
            "summary": summary
        }

    def approve_checkpoint(self, checkpoint: Checkpoint) -> dict[str, Any]:
        """Approve a checkpoint to allow the agent to proceed.

        Args:
            checkpoint: The checkpoint to approve

        Returns:
            Approval status
        """
        if checkpoint != self.pending_checkpoint:
            return {
                "status": "error",
                "message": f"Checkpoint {checkpoint.value} is not pending"
            }

        self.completed_checkpoints.append(checkpoint)
        self.current_checkpoint = checkpoint
        self.pending_checkpoint = None
        self.awaiting_approval = False

        # Update checkpoint node status
        for node in self.graph.get_nodes_by_type(NodeType.CHECKPOINT):
            if (node.properties.get("checkpoint") == checkpoint.value and
                node.properties.get("status") == "pending"):
                node.properties["status"] = "approved"
                node.properties["approved_at"] = datetime.now(timezone.utc).isoformat()
                self.graph.update_node(node)
                break

        return {
            "status": "approved",
            "checkpoint": checkpoint.value,
            "message": f"Checkpoint {checkpoint.value} approved. Agent may proceed."
        }

    def deny_checkpoint(
        self,
        checkpoint: Checkpoint,
        reason: str
    ) -> dict[str, Any]:
        """Deny a checkpoint, preventing the agent from proceeding.

        Args:
            checkpoint: The checkpoint to deny
            reason: Reason for denial

        Returns:
            Denial status
        """
        if checkpoint != self.pending_checkpoint:
            return {
                "status": "error",
                "message": f"Checkpoint {checkpoint.value} is not pending"
            }

        self.pending_checkpoint = None
        self.awaiting_approval = False

        # Update checkpoint node status
        for node in self.graph.get_nodes_by_type(NodeType.CHECKPOINT):
            if (node.properties.get("checkpoint") == checkpoint.value and
                node.properties.get("status") == "pending"):
                node.properties["status"] = "denied"
                node.properties["denial_reason"] = reason
                node.properties["denied_at"] = datetime.now(timezone.utc).isoformat()
                self.graph.update_node(node)
                break

        return {
            "status": "denied",
            "checkpoint": checkpoint.value,
            "reason": reason,
            "message": f"Checkpoint {checkpoint.value} denied. Agent should reassess."
        }

    def get_status(self) -> dict[str, Any]:
        """Get current checkpoint status.

        Returns:
            Current checkpoint state
        """
        return {
            "engagement_ref": self.engagement_ref,
            "current_checkpoint": self.current_checkpoint.value if self.current_checkpoint else None,
            "completed_checkpoints": [c.value for c in self.completed_checkpoints],
            "pending_checkpoint": self.pending_checkpoint.value if self.pending_checkpoint else None,
            "awaiting_approval": self.awaiting_approval
        }

    def can_proceed(self) -> bool:
        """Check if the agent can proceed (no pending approval).

        Returns:
            True if agent can continue
        """
        return not self.awaiting_approval
```

- [ ] **Step 4: Add CHECKPOINT to NodeType enum**

Update `bigiron/core/schema.py` to add:
```python
CHECKPOINT = "checkpoint"
```

- [ ] **Step 5: Run checkpoint tests**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/agent/test_checkpoints.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add bigiron/agent/checkpoints.py bigiron/tests/agent/test_checkpoints.py bigiron/core/schema.py
git commit -m "feat(agent): add checkpoint management

CheckpointManager provides:
- reach_checkpoint: Signal phase completion
- approve_checkpoint: Allow agent to proceed
- deny_checkpoint: Block agent with reason
- Status tracking in graph nodes
- Checkpoint sequence validation"
```

---

## Task 4: Agent Loop

**Files:**
- Create: `bigiron/agent/loop.py`
- Create: `bigiron/tests/agent/test_loop.py`

- [ ] **Step 1: Write failing test for agent loop**

```python
# bigiron/tests/agent/test_loop.py
import pytest


def test_agent_loop_creation():
    from bigiron.agent.loop import AgentLoop
    from bigiron.msf import MsfClient, CatalogService
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)

    loop = AgentLoop(
        graph=graph,
        catalog=catalog,
        engagement_ref="ENG-2026-001",
        goal="Assess mainframe security"
    )

    assert loop.state.engagement_ref == "ENG-2026-001"
    assert loop.state.goal == "Assess mainframe security"
    assert loop.state.current_turn == 0

    graph.close()


def test_agent_loop_execute_tool():
    from bigiron.agent.loop import AgentLoop
    from bigiron.msf import MsfClient, CatalogService
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)

    loop = AgentLoop(
        graph=graph,
        catalog=catalog,
        engagement_ref="ENG-2026-001",
        goal="Assess mainframe security"
    )

    result = loop.execute_tool("search_modules", {"query": "mainframe"})

    assert len(result) >= 5

    graph.close()


def test_agent_loop_record_turn():
    from bigiron.agent.loop import AgentLoop
    from bigiron.agent.schema import ToolCall
    from bigiron.msf import MsfClient, CatalogService
    from bigiron.core.graph import ProvenanceGraph
    from bigiron.core.schema import NodeType

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)

    loop = AgentLoop(
        graph=graph,
        catalog=catalog,
        engagement_ref="ENG-2026-001",
        goal="Assess mainframe security"
    )

    # Record a turn
    loop.record_turn(
        reasoning="Starting reconnaissance",
        tool_calls=[
            ToolCall(tool_name="search_modules", arguments={"query": "mainframe"})
        ]
    )

    assert loop.state.current_turn == 1

    # Verify turn was recorded in graph
    turns = list(graph.get_nodes_by_type(NodeType.AGENT_TURN))
    assert len(turns) == 1
    assert turns[0].properties["turn_number"] == 1

    graph.close()


def test_agent_loop_propose_and_get_pending():
    from bigiron.agent.loop import AgentLoop
    from bigiron.msf import MsfClient, CatalogService
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)

    loop = AgentLoop(
        graph=graph,
        catalog=catalog,
        engagement_ref="ENG-2026-001",
        goal="Assess mainframe security"
    )

    # Propose an action
    loop.execute_tool("propose_execution", {
        "module_path": "auxiliary/scanner/mainframe/tso_enum",
        "options": {"RHOSTS": "127.0.0.1"},
        "reasoning": "Enumerate users"
    })

    pending = loop.get_pending_actions()

    assert len(pending) == 1
    assert pending[0].module_path == "auxiliary/scanner/mainframe/tso_enum"

    graph.close()


def test_agent_loop_checkpoint_flow():
    from bigiron.agent.loop import AgentLoop
    from bigiron.agent.schema import Checkpoint
    from bigiron.msf import MsfClient, CatalogService
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)

    loop = AgentLoop(
        graph=graph,
        catalog=catalog,
        engagement_ref="ENG-2026-001",
        goal="Assess mainframe security"
    )

    # Reach checkpoint
    loop.reach_checkpoint(Checkpoint.RECON_COMPLETE, "Found 3 users")

    assert loop.can_proceed() is False
    assert loop.checkpoint_manager.awaiting_approval is True

    # Approve
    loop.approve_checkpoint(Checkpoint.RECON_COMPLETE)

    assert loop.can_proceed() is True

    graph.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/agent/test_loop.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Implement agent loop**

```python
# bigiron/agent/loop.py
"""Agent loop with think/act/observe cycle."""
from typing import Any

from ..core.graph import ProvenanceGraph
from ..msf import CatalogService
from .schema import AgentState, AgentTurn, ToolCall, ProposedAction, Checkpoint
from .tools import AgentTools
from .checkpoints import CheckpointManager


class AgentLoop:
    """Main agent loop coordinating tools, state, and checkpoints.

    The agent operates in a Think/Act/Observe loop:
    - Think: Analyze current state and decide next action
    - Act: Execute read-only tools or propose actions
    - Observe: Update state based on results

    The agent NEVER executes offensive actions directly.
    It proposes actions that humans must authorize.
    """

    def __init__(
        self,
        graph: ProvenanceGraph,
        catalog: CatalogService,
        engagement_ref: str,
        goal: str,
        constraints: list[str] | None = None
    ):
        """Initialize agent loop.

        Args:
            graph: Provenance graph
            catalog: MSF catalog
            engagement_ref: Engagement reference
            goal: Assessment goal
            constraints: Optional constraints on agent behavior
        """
        self.graph = graph
        self.catalog = catalog
        self.tools = AgentTools(graph=graph, catalog=catalog)
        self.checkpoint_manager = CheckpointManager(
            graph=graph,
            engagement_ref=engagement_ref
        )

        self.state = AgentState(
            engagement_ref=engagement_ref,
            goal=goal,
            constraints=constraints or []
        )

        self._turns: list[AgentTurn] = []

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a tool and return the result.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool result
        """
        return self.tools.execute_tool(name, arguments)

    def record_turn(
        self,
        reasoning: str,
        tool_calls: list[ToolCall],
        proposed_actions: list[ProposedAction] | None = None,
        checkpoint: Checkpoint | None = None
    ) -> AgentTurn:
        """Record an agent turn.

        Args:
            reasoning: Agent's reasoning for this turn
            tool_calls: Tools called during this turn
            proposed_actions: Actions proposed
            checkpoint: Checkpoint reached (if any)

        Returns:
            The recorded turn
        """
        self.state.current_turn += 1

        turn = AgentTurn(
            turn_number=self.state.current_turn,
            reasoning=reasoning,
            tool_calls=tool_calls,
            proposed_actions=proposed_actions or [],
            checkpoint=checkpoint
        )

        # Persist to graph
        node = turn.to_node()
        self.graph.add_node(node)

        self._turns.append(turn)
        return turn

    def get_pending_actions(self) -> list[ProposedAction]:
        """Get pending action proposals.

        Returns:
            List of proposed actions awaiting approval
        """
        return self.tools.get_pending_proposals()

    def clear_pending_actions(self):
        """Clear pending proposals after authorization."""
        self.tools.clear_proposals()
        self.state.pending_actions.clear()
        self.state.awaiting_authorization = False

    def reach_checkpoint(
        self,
        checkpoint: Checkpoint,
        summary: str
    ) -> dict[str, Any]:
        """Signal that a checkpoint has been reached.

        Args:
            checkpoint: The checkpoint reached
            summary: Summary of accomplishments

        Returns:
            Checkpoint status
        """
        result = self.checkpoint_manager.reach_checkpoint(checkpoint, summary)
        self.state.current_checkpoint = checkpoint
        return result

    def approve_checkpoint(self, checkpoint: Checkpoint) -> dict[str, Any]:
        """Approve a checkpoint.

        Args:
            checkpoint: The checkpoint to approve

        Returns:
            Approval status
        """
        result = self.checkpoint_manager.approve_checkpoint(checkpoint)
        if result["status"] == "approved":
            self.state.completed_checkpoints.append(checkpoint)
        return result

    def deny_checkpoint(
        self,
        checkpoint: Checkpoint,
        reason: str
    ) -> dict[str, Any]:
        """Deny a checkpoint.

        Args:
            checkpoint: The checkpoint to deny
            reason: Reason for denial

        Returns:
            Denial status
        """
        return self.checkpoint_manager.deny_checkpoint(checkpoint, reason)

    def can_proceed(self) -> bool:
        """Check if agent can proceed (no pending approvals).

        Returns:
            True if agent can continue
        """
        return self.checkpoint_manager.can_proceed()

    def get_state_summary(self) -> dict[str, Any]:
        """Get summary of current agent state.

        Returns:
            State summary for LLM context
        """
        return {
            "engagement_ref": self.state.engagement_ref,
            "goal": self.state.goal,
            "constraints": self.state.constraints,
            "current_turn": self.state.current_turn,
            "checkpoint_status": self.checkpoint_manager.get_status(),
            "pending_actions": len(self.get_pending_actions()),
            "graph_stats": self.tools.query_graph_stats()
        }

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get tool definitions for LLM.

        Returns:
            Tool definitions
        """
        return self.tools.get_tool_definitions()
```

- [ ] **Step 4: Run loop tests**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/agent/test_loop.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add bigiron/agent/loop.py bigiron/tests/agent/test_loop.py
git commit -m "feat(agent): add agent loop

AgentLoop provides:
- Tool execution (read-only + propose)
- Turn recording with graph persistence
- Checkpoint flow management
- State summary for LLM context
- Pending action tracking"
```

---

## Task 5: Agent Package Exports and Integration Test

**Files:**
- Modify: `bigiron/agent/__init__.py`
- Create: `bigiron/tests/agent/test_integration.py`

- [ ] **Step 1: Update agent package exports**

```python
# bigiron/agent/__init__.py
"""AI agent layer for autonomous assessment with checkpoints."""
from .schema import (
    Checkpoint,
    RiskLevel,
    ToolCall,
    ProposedAction,
    AgentTurn,
    AgentState,
)
from .tools import AgentTools
from .checkpoints import CheckpointManager
from .loop import AgentLoop

__all__ = [
    "Checkpoint",
    "RiskLevel",
    "ToolCall",
    "ProposedAction",
    "AgentTurn",
    "AgentState",
    "AgentTools",
    "CheckpointManager",
    "AgentLoop",
]
```

- [ ] **Step 2: Write integration test**

```python
# bigiron/tests/agent/test_integration.py
"""Integration tests for agent layer."""
import pytest
from bigiron.core.graph import ProvenanceGraph
from bigiron.core.schema import NodeType
from bigiron.msf import MsfClient, CatalogService, ExecutorService, Authorization
from bigiron.agent import (
    AgentLoop,
    Checkpoint,
    ToolCall,
)


def test_full_agent_workflow():
    """Test complete agent workflow: think -> propose -> authorize -> execute."""

    # Setup
    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)
    executor = ExecutorService(client=client, graph=graph, catalog=catalog)

    # Sync modules
    catalog.sync_to_graph()

    # Create agent
    loop = AgentLoop(
        graph=graph,
        catalog=catalog,
        engagement_ref="ENG-TEST-001",
        goal="Enumerate TSO users on target mainframe"
    )

    # Turn 1: Search for modules
    modules = loop.execute_tool("search_modules", {"query": "tso_enum"})
    assert len(modules) >= 1

    loop.record_turn(
        reasoning="Searched for TSO enumeration modules",
        tool_calls=[
            ToolCall(tool_name="search_modules", arguments={"query": "tso_enum"})
        ]
    )

    # Turn 2: Propose execution
    loop.execute_tool("propose_execution", {
        "module_path": "auxiliary/scanner/mainframe/tso_enum",
        "options": {"RHOSTS": "127.0.0.1"},
        "reasoning": "Enumerate TSO users to identify valid accounts"
    })

    pending = loop.get_pending_actions()
    assert len(pending) == 1

    # Human authorization
    auth = Authorization(
        engagement_ref="ENG-TEST-001",
        operator="test_user",
        approved_modules=["auxiliary/scanner/mainframe/*"],
        scope=["127.0.0.1"]
    )

    # Execute approved action
    action = pending[0]
    parts = action.module_path.split("/", 1)
    result = executor.run(
        mtype=parts[0],
        path=parts[1],
        options=action.options,
        authorization=auth
    )

    assert result.success is True
    loop.clear_pending_actions()

    # Reach checkpoint
    loop.reach_checkpoint(Checkpoint.RECON_COMPLETE, "TSO enumeration complete")
    assert loop.can_proceed() is False

    loop.approve_checkpoint(Checkpoint.RECON_COMPLETE)
    assert loop.can_proceed() is True

    # Verify graph state
    turns = list(graph.get_nodes_by_type(NodeType.AGENT_TURN))
    assert len(turns) == 1

    checkpoints = list(graph.get_nodes_by_type(NodeType.CHECKPOINT))
    assert len(checkpoints) == 1
    assert checkpoints[0].properties["status"] == "approved"

    runs = list(graph.get_nodes_by_type(NodeType.MODULE_RUN))
    assert len(runs) == 1

    graph.close()


def test_agent_state_persistence():
    """Verify agent state is fully persisted in graph."""

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)

    loop = AgentLoop(
        graph=graph,
        catalog=catalog,
        engagement_ref="ENG-TEST-002",
        goal="Test persistence"
    )

    # Record multiple turns
    for i in range(3):
        loop.record_turn(
            reasoning=f"Turn {i+1} reasoning",
            tool_calls=[
                ToolCall(tool_name="query_graph_stats", arguments={})
            ]
        )

    # Verify all turns persisted
    turns = list(graph.get_nodes_by_type(NodeType.AGENT_TURN))
    assert len(turns) == 3

    turn_numbers = sorted([t.properties["turn_number"] for t in turns])
    assert turn_numbers == [1, 2, 3]

    graph.close()
```

- [ ] **Step 3: Run integration tests**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/agent/test_integration.py -v`
Expected: All 2 tests PASS

- [ ] **Step 4: Run full test suite**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add bigiron/agent/__init__.py bigiron/tests/agent/test_integration.py
git commit -m "feat(agent): finalize agent layer with integration tests

Complete agent layer:
- Package exports from bigiron.agent
- Full workflow integration test
- State persistence verification
- Checkpoint approval flow test"
```

- [ ] **Step 6: Push and tag**

```bash
git push
git tag -a v0.3.0-agent-layer -m "Agent layer complete"
git push --tags
```

---

## Summary

This plan implements the **Agent Layer** - the AI-powered autonomous assessment component. After completing these 5 tasks, you'll have:

- **Schema** - Checkpoint, ToolCall, ProposedAction, AgentTurn, AgentState
- **Tools** - Read-only tools + propose_execution (no direct execution)
- **Checkpoints** - Phase boundary management with approval flow
- **Loop** - Think/Act/Observe coordination with state persistence

**Key Safety Principle**: Agent PROPOSES actions, human AUTHORIZES execution.

**Next plan**: Demo/Hybrid Mode (recorded playback for modern z/OS features)
