import pytest
import tempfile
from pathlib import Path


def test_graph_initializes_database():
    from bigiron.core.graph import ProvenanceGraph

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "graph.db"
        graph = ProvenanceGraph(db_path)

        assert graph.db is not None
        assert db_path.exists()

        graph.close()


def test_graph_in_memory():
    from bigiron.core.graph import ProvenanceGraph

    graph = ProvenanceGraph(":memory:")
    assert graph.db is not None
    graph.close()


def test_add_node():
    from bigiron.core.graph import ProvenanceGraph
    from bigiron.core.schema import Node, NodeType

    graph = ProvenanceGraph(":memory:")

    node = Node(
        id="host-1",
        node_type=NodeType.HOST,
        label="192.168.1.100",
        properties={"port": 23}
    )

    graph.add_node(node)

    # Retrieve and verify
    retrieved = graph.get_node("host-1")
    assert retrieved is not None
    assert retrieved.label == "192.168.1.100"
    assert retrieved.properties["port"] == 23

    graph.close()


def test_add_node_with_provenance():
    from bigiron.core.graph import ProvenanceGraph
    from bigiron.core.schema import Node, NodeType, Provenance

    graph = ProvenanceGraph(":memory:")

    node = Node(
        node_type=NodeType.MODULE_RUN,
        label="ftp_enum run",
        provenance=Provenance(
            authorization_ref="ENG-2026-001",
            agent_turn=5
        )
    )

    graph.add_node(node)
    retrieved = graph.get_node(node.id)

    assert retrieved.provenance.authorization_ref == "ENG-2026-001"
    assert retrieved.provenance.agent_turn == 5

    graph.close()


def test_update_node():
    from bigiron.core.graph import ProvenanceGraph
    from bigiron.core.schema import Node, NodeType

    graph = ProvenanceGraph(":memory:")

    node = Node(
        id="user-1",
        node_type=NodeType.USER,
        label="HERC01",
        properties={"group": "SYS1"}
    )
    graph.add_node(node)

    # Update properties
    node.properties["group"] = "ADMIN"
    node.label = "HERC01-ADMIN"
    graph.update_node(node)

    retrieved = graph.get_node("user-1")
    assert retrieved.label == "HERC01-ADMIN"
    assert retrieved.properties["group"] == "ADMIN"

    graph.close()


def test_delete_node():
    from bigiron.core.graph import ProvenanceGraph
    from bigiron.core.schema import Node, NodeType

    graph = ProvenanceGraph(":memory:")

    node = Node(node_type=NodeType.HOST, label="test")
    graph.add_node(node)

    assert graph.get_node(node.id) is not None

    graph.delete_node(node.id)

    assert graph.get_node(node.id) is None

    graph.close()


def test_add_edge():
    from bigiron.core.graph import ProvenanceGraph
    from bigiron.core.schema import Node, NodeType, Edge, EdgeType

    graph = ProvenanceGraph(":memory:")

    # Create source and target nodes
    src = Node(id="run-1", node_type=NodeType.MODULE_RUN, label="TSO Enum")
    tgt = Node(id="user-1", node_type=NodeType.USER, label="HERC01")
    graph.add_node(src)
    graph.add_node(tgt)

    # Create edge
    edge = Edge(
        source_id="run-1",
        target_id="user-1",
        edge_type=EdgeType.DISCOVERED,
        properties={"parser": "TSOEnumParser"}
    )
    graph.add_edge(edge)

    # Retrieve and verify
    retrieved = graph.get_edge(edge.id)
    assert retrieved is not None
    assert retrieved.source_id == "run-1"
    assert retrieved.target_id == "user-1"
    assert retrieved.edge_type == EdgeType.DISCOVERED

    graph.close()


def test_add_edge_with_provenance():
    from bigiron.core.graph import ProvenanceGraph
    from bigiron.core.schema import Node, NodeType, Edge, EdgeType, Provenance

    graph = ProvenanceGraph(":memory:")

    src = Node(id="a", node_type=NodeType.HOST, label="A")
    tgt = Node(id="b", node_type=NodeType.SERVICE, label="B")
    graph.add_node(src)
    graph.add_node(tgt)

    edge = Edge(
        source_id="a",
        target_id="b",
        edge_type=EdgeType.TARGETS,
        provenance=Provenance(
            authorization_ref="ENG-001",
            raw_output="[*] Targeting host..."
        )
    )
    graph.add_edge(edge)

    retrieved = graph.get_edge(edge.id)
    assert retrieved.provenance.authorization_ref == "ENG-001"
    assert "[*] Targeting" in retrieved.provenance.raw_output

    graph.close()


def test_get_edges_from_node():
    from bigiron.core.graph import ProvenanceGraph
    from bigiron.core.schema import Node, NodeType, Edge, EdgeType

    graph = ProvenanceGraph(":memory:")

    # Create nodes
    run = Node(id="run-1", node_type=NodeType.MODULE_RUN, label="Scan")
    user1 = Node(id="u1", node_type=NodeType.USER, label="USER1")
    user2 = Node(id="u2", node_type=NodeType.USER, label="USER2")
    graph.add_node(run)
    graph.add_node(user1)
    graph.add_node(user2)

    # Create edges from run to users
    graph.add_edge(Edge(source_id="run-1", target_id="u1", edge_type=EdgeType.DISCOVERED))
    graph.add_edge(Edge(source_id="run-1", target_id="u2", edge_type=EdgeType.DISCOVERED))

    # Get outgoing edges
    edges = list(graph.get_edges_from("run-1"))

    assert len(edges) == 2
    target_ids = {e.target_id for e in edges}
    assert target_ids == {"u1", "u2"}

    graph.close()


def test_get_edges_to_node():
    from bigiron.core.graph import ProvenanceGraph
    from bigiron.core.schema import Node, NodeType, Edge, EdgeType

    graph = ProvenanceGraph(":memory:")

    # Create nodes
    auth = Node(id="auth-1", node_type=NodeType.AUTHORIZATION, label="Auth")
    run1 = Node(id="r1", node_type=NodeType.MODULE_RUN, label="Run1")
    run2 = Node(id="r2", node_type=NodeType.MODULE_RUN, label="Run2")
    graph.add_node(auth)
    graph.add_node(run1)
    graph.add_node(run2)

    # Create edges pointing to auth
    graph.add_edge(Edge(source_id="r1", target_id="auth-1", edge_type=EdgeType.AUTHORIZED_BY))
    graph.add_edge(Edge(source_id="r2", target_id="auth-1", edge_type=EdgeType.AUTHORIZED_BY))

    # Get incoming edges
    edges = list(graph.get_edges_to("auth-1"))

    assert len(edges) == 2
    source_ids = {e.source_id for e in edges}
    assert source_ids == {"r1", "r2"}

    graph.close()


def test_get_edges_filtered_by_type():
    from bigiron.core.graph import ProvenanceGraph
    from bigiron.core.schema import Node, NodeType, Edge, EdgeType

    graph = ProvenanceGraph(":memory:")

    a = Node(id="a", node_type=NodeType.HOST, label="A")
    b = Node(id="b", node_type=NodeType.USER, label="B")
    c = Node(id="c", node_type=NodeType.DATASET, label="C")
    graph.add_node(a)
    graph.add_node(b)
    graph.add_node(c)

    graph.add_edge(Edge(source_id="a", target_id="b", edge_type=EdgeType.DISCOVERED))
    graph.add_edge(Edge(source_id="a", target_id="c", edge_type=EdgeType.TARGETS))

    # Filter by type
    discovered = list(graph.get_edges_from("a", edge_type=EdgeType.DISCOVERED))
    assert len(discovered) == 1
    assert discovered[0].target_id == "b"

    graph.close()
