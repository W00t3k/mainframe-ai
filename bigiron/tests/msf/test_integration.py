"""Integration tests for MSF layer."""
import pytest
from bigiron.core.graph import ProvenanceGraph
from bigiron.core.schema import NodeType, EdgeType
from bigiron.msf import (
    MsfClient,
    CatalogService,
    ExecutorService,
    Authorization,
    get_parser,
)


def test_full_execution_workflow():
    """Test complete workflow: catalog -> authorize -> execute -> parse."""

    # Setup
    client = MsfClient(password=None)  # Demo mode
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)
    executor = ExecutorService(client=client, graph=graph, catalog=catalog)

    # 1. Sync modules to graph
    count = catalog.sync_to_graph("mainframe")
    assert count >= 5

    # 2. Search for a module
    results = catalog.search("tso_enum")
    assert len(results) >= 1
    module = results[0]

    # 3. Preview execution
    preview = executor.preview(
        mtype=module.mtype,
        path=module.path,
        options={"RHOSTS": "127.0.0.1"}
    )
    assert "use" in preview.command
    assert "RHOSTS" in preview.command

    # 4. Create authorization
    auth = Authorization(
        engagement_ref="ENG-TEST-001",
        operator="test_user",
        approved_modules=["auxiliary/scanner/mainframe/*"],
        scope=["127.0.0.1"]
    )

    # 5. Execute with authorization
    result = executor.run(
        mtype=module.mtype,
        path=module.path,
        options={"RHOSTS": "127.0.0.1"},
        authorization=auth
    )
    assert result.success is True

    # 6. Parse output
    parser = get_parser(f"{module.mtype}/{module.path}")
    entities = parser.parse(result.output)
    assert len(entities) >= 1  # Should find some users

    # 7. Verify graph state
    stats = graph.stats()

    # Should have: modules + auth + run + host
    assert stats["total_nodes"] >= 7

    # Should have edges: run->auth, run->host
    assert stats["total_edges"] >= 2

    # Verify module run was recorded
    runs = list(graph.get_nodes_by_type(NodeType.MODULE_RUN))
    assert len(runs) == 1
    assert runs[0].provenance.authorization_ref == auth.id

    # Verify authorization edge
    auth_edges = list(graph.get_edges_from(runs[0].id, EdgeType.AUTHORIZED_BY))
    assert len(auth_edges) == 1

    graph.close()


def test_parser_integration_with_graph():
    """Test parsing module output and adding entities to graph."""

    graph = ProvenanceGraph(":memory:")

    # Simulate TSO enum output
    output = """
[*] Enumerating TSO users...
[+] Valid user found: HERC01
[+] Valid user found: IBMUSER
[*] Enumeration complete
"""

    # Parse
    parser = get_parser("auxiliary/scanner/mainframe/tso_enum")
    entities = parser.parse(output)

    # Add to graph
    from bigiron.core.schema import Node, NodeType
    for entity in entities:
        node = Node(
            node_type=NodeType(entity["node_type"]),
            label=entity["label"],
            properties=entity["properties"]
        )
        graph.add_node(node)

    # Verify
    users = list(graph.get_nodes_by_type(NodeType.USER))
    assert len(users) == 2

    labels = {u.label for u in users}
    assert labels == {"HERC01", "IBMUSER"}

    graph.close()


def test_catalog_module_detail_to_graph_properties():
    """Verify module details are properly stored in graph nodes."""

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)

    # Sync one module
    catalog.sync_to_graph("tk5_jcl_submit")

    # Get the module node
    nodes = list(graph.get_nodes_by_type(NodeType.MSF_MODULE))

    # Find the tk5 module
    tk5_node = None
    for node in nodes:
        if "tk5" in node.properties.get("path", ""):
            tk5_node = node
            break

    assert tk5_node is not None
    assert tk5_node.properties["tk5_compatible"] is True
    assert len(tk5_node.properties["options"]) >= 4

    graph.close()
