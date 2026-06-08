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
