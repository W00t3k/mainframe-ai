"""Tests for authorization model and gate."""
import pytest
from datetime import datetime, timezone, timedelta


def test_authorization_creation():
    from bigiron.msf.authorization import Authorization

    auth = Authorization(
        engagement_ref="ENG-2026-001",
        operator="w00t3k",
        approved_modules=["auxiliary/admin/mainframe/*"],
        scope=["127.0.0.1", "10.0.0.0/24"]
    )

    assert auth.engagement_ref == "ENG-2026-001"
    assert auth.operator == "w00t3k"
    assert auth.is_valid is True


def test_authorization_expired():
    from bigiron.msf.authorization import Authorization

    auth = Authorization(
        engagement_ref="ENG-2026-001",
        operator="w00t3k",
        approved_modules=["*"],
        scope=["*"],
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
    )

    assert auth.is_valid is False
    assert auth.is_expired is True


def test_authorization_module_approved():
    from bigiron.msf.authorization import Authorization

    auth = Authorization(
        engagement_ref="ENG-2026-001",
        operator="w00t3k",
        approved_modules=[
            "auxiliary/admin/mainframe/*",
            "auxiliary/scanner/mainframe/tso_enum"
        ],
        scope=["*"]
    )

    assert auth.is_module_approved("auxiliary/scanner/mainframe/tso_enum") is True
    assert auth.is_module_approved("auxiliary/admin/mainframe/tk5_jcl_submit") is True
    assert auth.is_module_approved("exploit/mainframe/dangerous") is False


def test_authorization_target_in_scope():
    from bigiron.msf.authorization import Authorization

    auth = Authorization(
        engagement_ref="ENG-2026-001",
        operator="w00t3k",
        approved_modules=["*"],
        scope=["127.0.0.1", "10.0.0.0/24"]
    )

    assert auth.is_target_in_scope("127.0.0.1") is True
    assert auth.is_target_in_scope("10.0.0.5") is True
    assert auth.is_target_in_scope("192.168.1.1") is False


def test_authorization_wildcard_scope():
    from bigiron.msf.authorization import Authorization

    auth = Authorization(
        engagement_ref="ENG-2026-001",
        operator="w00t3k",
        approved_modules=["*"],
        scope=["*"]
    )

    assert auth.is_target_in_scope("192.168.1.1") is True
    assert auth.is_target_in_scope("any.host.com") is True


def test_authorization_to_graph_node():
    from bigiron.msf.authorization import Authorization
    from bigiron.core.schema import NodeType

    auth = Authorization(
        engagement_ref="ENG-2026-001",
        operator="w00t3k",
        approved_modules=["*"],
        scope=["*"]
    )

    node = auth.to_node()

    assert node.node_type == NodeType.AUTHORIZATION
    assert node.properties["engagement_ref"] == "ENG-2026-001"
    assert node.properties["operator"] == "w00t3k"
