"""Tests for agent tools."""
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
