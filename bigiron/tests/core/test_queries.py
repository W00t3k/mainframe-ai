import pytest
from bigiron.core.graph import ProvenanceGraph
from bigiron.core.schema import Node, Edge, NodeType, EdgeType


def test_get_nodes_by_type():
    graph = ProvenanceGraph(":memory:")

    graph.add_node(Node(node_type=NodeType.USER, label="USER1"))
    graph.add_node(Node(node_type=NodeType.USER, label="USER2"))
    graph.add_node(Node(node_type=NodeType.HOST, label="HOST1"))

    users = list(graph.get_nodes_by_type(NodeType.USER))

    assert len(users) == 2
    labels = {u.label for u in users}
    assert labels == {"USER1", "USER2"}

    graph.close()


def test_get_nodes_by_type_empty():
    graph = ProvenanceGraph(":memory:")

    graph.add_node(Node(node_type=NodeType.HOST, label="HOST1"))

    users = list(graph.get_nodes_by_type(NodeType.USER))
    assert len(users) == 0

    graph.close()


def test_get_neighbors_outgoing():
    graph = ProvenanceGraph(":memory:")

    run = Node(id="run", node_type=NodeType.MODULE_RUN, label="Run")
    u1 = Node(id="u1", node_type=NodeType.USER, label="U1")
    u2 = Node(id="u2", node_type=NodeType.USER, label="U2")

    graph.add_node(run)
    graph.add_node(u1)
    graph.add_node(u2)

    graph.add_edge(Edge(source_id="run", target_id="u1", edge_type=EdgeType.DISCOVERED))
    graph.add_edge(Edge(source_id="run", target_id="u2", edge_type=EdgeType.DISCOVERED))

    neighbors = list(graph.get_neighbors("run"))

    assert len(neighbors) == 2
    neighbor_ids = {n.id for n in neighbors}
    assert neighbor_ids == {"u1", "u2"}

    graph.close()


def test_get_neighbors_incoming():
    graph = ProvenanceGraph(":memory:")

    auth = Node(id="auth", node_type=NodeType.AUTHORIZATION, label="Auth")
    r1 = Node(id="r1", node_type=NodeType.MODULE_RUN, label="R1")
    r2 = Node(id="r2", node_type=NodeType.MODULE_RUN, label="R2")

    graph.add_node(auth)
    graph.add_node(r1)
    graph.add_node(r2)

    graph.add_edge(Edge(source_id="r1", target_id="auth", edge_type=EdgeType.AUTHORIZED_BY))
    graph.add_edge(Edge(source_id="r2", target_id="auth", edge_type=EdgeType.AUTHORIZED_BY))

    neighbors = list(graph.get_neighbors("auth", direction="incoming"))

    assert len(neighbors) == 2

    graph.close()


def test_get_neighbors_both_directions():
    graph = ProvenanceGraph(":memory:")

    middle = Node(id="m", node_type=NodeType.USER, label="M")
    left = Node(id="l", node_type=NodeType.HOST, label="L")
    right = Node(id="r", node_type=NodeType.DATASET, label="R")

    graph.add_node(middle)
    graph.add_node(left)
    graph.add_node(right)

    graph.add_edge(Edge(source_id="l", target_id="m", edge_type=EdgeType.DISCOVERED))
    graph.add_edge(Edge(source_id="m", target_id="r", edge_type=EdgeType.READS))

    neighbors = list(graph.get_neighbors("m", direction="both"))

    assert len(neighbors) == 2
    neighbor_ids = {n.id for n in neighbors}
    assert neighbor_ids == {"l", "r"}

    graph.close()


def test_find_paths_direct():
    graph = ProvenanceGraph(":memory:")

    a = Node(id="a", node_type=NodeType.HOST, label="A")
    b = Node(id="b", node_type=NodeType.USER, label="B")

    graph.add_node(a)
    graph.add_node(b)
    graph.add_edge(Edge(source_id="a", target_id="b", edge_type=EdgeType.DISCOVERED))

    paths = list(graph.find_paths("a", "b"))

    assert len(paths) == 1
    assert paths[0] == ["a", "b"]

    graph.close()


def test_find_paths_multi_hop():
    graph = ProvenanceGraph(":memory:")

    # Create chain: a -> b -> c -> d
    nodes = [
        Node(id="a", node_type=NodeType.HOST, label="A"),
        Node(id="b", node_type=NodeType.USER, label="B"),
        Node(id="c", node_type=NodeType.DATASET, label="C"),
        Node(id="d", node_type=NodeType.PROGRAM, label="D"),
    ]
    for n in nodes:
        graph.add_node(n)

    graph.add_edge(Edge(source_id="a", target_id="b", edge_type=EdgeType.DISCOVERED))
    graph.add_edge(Edge(source_id="b", target_id="c", edge_type=EdgeType.READS))
    graph.add_edge(Edge(source_id="c", target_id="d", edge_type=EdgeType.LOADS_FROM))

    paths = list(graph.find_paths("a", "d"))

    assert len(paths) == 1
    assert paths[0] == ["a", "b", "c", "d"]

    graph.close()


def test_find_paths_no_path():
    graph = ProvenanceGraph(":memory:")

    a = Node(id="a", node_type=NodeType.HOST, label="A")
    b = Node(id="b", node_type=NodeType.USER, label="B")

    graph.add_node(a)
    graph.add_node(b)
    # No edge between them

    paths = list(graph.find_paths("a", "b"))

    assert len(paths) == 0

    graph.close()


def test_find_paths_multiple():
    graph = ProvenanceGraph(":memory:")

    # Create diamond: a -> b -> d, a -> c -> d
    a = Node(id="a", node_type=NodeType.HOST, label="A")
    b = Node(id="b", node_type=NodeType.USER, label="B")
    c = Node(id="c", node_type=NodeType.USER, label="C")
    d = Node(id="d", node_type=NodeType.DATASET, label="D")

    for n in [a, b, c, d]:
        graph.add_node(n)

    graph.add_edge(Edge(source_id="a", target_id="b", edge_type=EdgeType.DISCOVERED))
    graph.add_edge(Edge(source_id="a", target_id="c", edge_type=EdgeType.DISCOVERED))
    graph.add_edge(Edge(source_id="b", target_id="d", edge_type=EdgeType.READS))
    graph.add_edge(Edge(source_id="c", target_id="d", edge_type=EdgeType.READS))

    paths = list(graph.find_paths("a", "d"))

    assert len(paths) == 2
    path_sets = {tuple(p) for p in paths}
    assert ("a", "b", "d") in path_sets
    assert ("a", "c", "d") in path_sets

    graph.close()
