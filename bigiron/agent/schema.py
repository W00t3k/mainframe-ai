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
