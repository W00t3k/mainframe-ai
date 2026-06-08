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
