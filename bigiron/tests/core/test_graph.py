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
