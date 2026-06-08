"""Tests for agent loop."""
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
