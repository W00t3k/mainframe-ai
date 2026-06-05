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
