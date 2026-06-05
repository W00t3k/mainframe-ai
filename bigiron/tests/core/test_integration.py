"""Integration tests for the provenance graph core."""
import pytest
import tempfile
from pathlib import Path

from bigiron import (
    ProvenanceGraph,
    Node,
    Edge,
    NodeType,
    EdgeType,
    Provenance,
)


def test_full_engagement_workflow():
    """Test a complete engagement workflow through the graph."""

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "engagement.db"

        with ProvenanceGraph(db_path) as graph:
            # 1. Create engagement
            engagement = Node(
                id="eng-2026-001",
                node_type=NodeType.ENGAGEMENT,
                label="Mainframe Assessment Q2 2026",
                properties={
                    "client": "ACME Corp",
                    "scope": ["10.0.0.0/24"],
                    "start_date": "2026-06-01"
                }
            )
            graph.add_node(engagement)

            # 2. Create authorization
            auth = Node(
                id="auth-001",
                node_type=NodeType.AUTHORIZATION,
                label="Initial Recon Authorization",
                properties={
                    "operator": "w00t3k",
                    "approved_modules": ["tso_enum", "vtam_enum"]
                }
            )
            graph.add_node(auth)
            graph.add_edge(Edge(
                source_id="auth-001",
                target_id="eng-2026-001",
                edge_type=EdgeType.PART_OF
            ))

            # 3. Simulate module run
            module_run = Node(
                id="run-001",
                node_type=NodeType.MODULE_RUN,
                label="tso_enum execution",
                provenance=Provenance(
                    authorization_ref="auth-001",
                    raw_output="[*] Enumerating TSO users...\n[+] Found: HERC01, IBMUSER"
                )
            )
            graph.add_node(module_run)
            graph.add_edge(Edge(
                source_id="run-001",
                target_id="auth-001",
                edge_type=EdgeType.AUTHORIZED_BY
            ))

            # 4. Add discovered entities
            for username in ["HERC01", "IBMUSER"]:
                user = Node(
                    id=f"user-{username}",
                    node_type=NodeType.USER,
                    label=username,
                    properties={"source": "tso_enum"}
                )
                graph.add_node(user)
                graph.add_edge(Edge(
                    source_id="run-001",
                    target_id=f"user-{username}",
                    edge_type=EdgeType.DISCOVERED,
                    provenance=Provenance(
                        parsed_entities=[username]
                    )
                ))

            # 5. Verify graph state
            stats = graph.stats()
            assert stats["total_nodes"] == 5  # engagement, auth, run, 2 users
            assert stats["total_edges"] == 4  # part_of, authorized_by, 2 discovered

            # 6. Find attack path
            paths = list(graph.find_paths("run-001", "user-HERC01"))
            assert len(paths) == 1
            assert paths[0] == ["run-001", "user-HERC01"]

            # 7. Export and verify
            export = graph.to_dict()
            assert len(export["nodes"]) == 5

            # 8. Search
            users = list(graph.search_nodes("HERC"))
            assert len(users) == 1
            assert users[0].label == "HERC01"

        # 9. Verify persistence - reopen and check
        with ProvenanceGraph(db_path) as graph:
            stats = graph.stats()
            assert stats["total_nodes"] == 5

            herc = graph.get_node("user-HERC01")
            assert herc is not None
            assert herc.properties["source"] == "tso_enum"


def test_import_from_top_level():
    """Verify all exports are accessible from bigiron package."""
    from bigiron import ProvenanceGraph, Node, Edge, NodeType, EdgeType, Provenance

    assert ProvenanceGraph is not None
    assert Node is not None
    assert Edge is not None
    assert NodeType.HOST.value == "host"
    assert EdgeType.DISCOVERED.value == "discovered"
    assert Provenance is not None
