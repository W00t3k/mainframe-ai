import pytest
from bigiron.core.schema import NodeType


def test_node_type_has_target_types():
    assert NodeType.HOST.value == "host"
    assert NodeType.SERVICE.value == "service"
    assert NodeType.CREDENTIAL.value == "credential"


def test_node_type_has_mainframe_types():
    assert NodeType.USER.value == "user"
    assert NodeType.DATASET.value == "dataset"
    assert NodeType.JOB.value == "job"
    assert NodeType.TRANSACTION.value == "transaction"
    assert NodeType.PROGRAM.value == "program"


def test_node_type_has_module_types():
    assert NodeType.MSF_MODULE.value == "msf_module"
    assert NodeType.CUSTOM_MODULE.value == "custom_module"
    assert NodeType.RECON_TOOL.value == "recon_tool"


def test_node_type_has_execution_types():
    assert NodeType.MODULE_RUN.value == "module_run"
    assert NodeType.CHECKPOINT.value == "checkpoint"
    assert NodeType.AUTHORIZATION.value == "authorization"


def test_node_type_has_finding_types():
    assert NodeType.VULNERABILITY.value == "vulnerability"
    assert NodeType.MISCONFIGURATION.value == "misconfiguration"
    assert NodeType.ACCESS_PATH.value == "access_path"


def test_edge_type_has_execution_edges():
    from bigiron.core.schema import EdgeType
    assert EdgeType.TARGETS.value == "targets"
    assert EdgeType.DISCOVERED.value == "discovered"
    assert EdgeType.AUTHORIZED_BY.value == "authorized_by"


def test_edge_type_has_relationship_edges():
    from bigiron.core.schema import EdgeType
    assert EdgeType.GRANTED_ACCESS.value == "granted_access"
    assert EdgeType.ATTACK_PATH.value == "attack_path"
    assert EdgeType.MAPS_TO.value == "maps_to"
    assert EdgeType.PART_OF.value == "part_of"


def test_provenance_model_creation():
    from datetime import datetime, timezone
    from bigiron.core.schema import Provenance

    prov = Provenance(
        timestamp=datetime(2026, 6, 5, 14, 23, 1, tzinfo=timezone.utc),
        authorization_ref="ENG-2026-0042",
        agent_turn=7,
        raw_output="[+] Job submitted",
        simulated=False
    )

    assert prov.authorization_ref == "ENG-2026-0042"
    assert prov.agent_turn == 7
    assert prov.simulated is False


def test_provenance_defaults():
    from bigiron.core.schema import Provenance

    prov = Provenance()

    assert prov.timestamp is not None
    assert prov.authorization_ref is None
    assert prov.agent_turn is None
    assert prov.raw_output is None
    assert prov.simulated is False
    assert prov.recording_id is None


def test_node_model_creation():
    from bigiron.core.schema import Node, NodeType

    node = Node(
        id="host-192.168.1.100",
        node_type=NodeType.HOST,
        label="192.168.1.100",
        properties={"ip": "192.168.1.100", "port": 23}
    )

    assert node.id == "host-192.168.1.100"
    assert node.node_type == NodeType.HOST
    assert node.label == "192.168.1.100"
    assert node.properties["port"] == 23


def test_node_auto_generates_id():
    from bigiron.core.schema import Node, NodeType

    node = Node(
        node_type=NodeType.USER,
        label="HERC01"
    )

    assert node.id is not None
    assert len(node.id) > 0


def test_node_has_provenance():
    from bigiron.core.schema import Node, NodeType, Provenance

    node = Node(
        node_type=NodeType.JOB,
        label="JOB12345",
        provenance=Provenance(authorization_ref="ENG-001")
    )

    assert node.provenance.authorization_ref == "ENG-001"


def test_edge_model_creation():
    from bigiron.core.schema import Edge, EdgeType

    edge = Edge(
        source_id="run-001",
        target_id="user-HERC01",
        edge_type=EdgeType.DISCOVERED,
        properties={"parser": "TSOEnumParser"}
    )

    assert edge.source_id == "run-001"
    assert edge.target_id == "user-HERC01"
    assert edge.edge_type == EdgeType.DISCOVERED


def test_edge_has_provenance():
    from bigiron.core.schema import Edge, EdgeType, Provenance

    edge = Edge(
        source_id="a",
        target_id="b",
        edge_type=EdgeType.ATTACK_PATH,
        provenance=Provenance(agent_turn=3)
    )

    assert edge.provenance.agent_turn == 3
