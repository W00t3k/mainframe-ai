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
