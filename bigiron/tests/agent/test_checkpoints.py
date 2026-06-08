"""Tests for checkpoint management."""
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
