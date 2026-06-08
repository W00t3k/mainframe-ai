"""Tests for executor service."""
import pytest
from datetime import datetime, timezone


def test_executor_preview():
    from bigiron.msf.executor import ExecutorService
    from bigiron.msf.client import MsfClient
    from bigiron.msf.catalog import CatalogService
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)  # Demo mode
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)

    executor = ExecutorService(client=client, graph=graph, catalog=catalog)

    preview = executor.preview(
        mtype="auxiliary",
        path="admin/mainframe/tk5_jcl_submit",
        options={"RHOSTS": "127.0.0.1"}
    )

    assert preview is not None
    assert "use auxiliary/admin/mainframe/tk5_jcl_submit" in preview.command
    assert "set RHOSTS 127.0.0.1" in preview.command

    graph.close()


def test_executor_run_requires_authorization():
    from bigiron.msf.executor import ExecutorService
    from bigiron.msf.client import MsfClient
    from bigiron.msf.catalog import CatalogService
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)

    executor = ExecutorService(client=client, graph=graph, catalog=catalog)

    # Try to run without authorization
    with pytest.raises(PermissionError, match="No authorization provided"):
        executor.run(
            mtype="auxiliary",
            path="admin/mainframe/tk5_jcl_submit",
            options={"RHOSTS": "127.0.0.1"}
        )

    graph.close()


def test_executor_run_with_authorization_demo():
    from bigiron.msf.executor import ExecutorService
    from bigiron.msf.client import MsfClient
    from bigiron.msf.catalog import CatalogService
    from bigiron.msf.authorization import Authorization
    from bigiron.core.graph import ProvenanceGraph
    from bigiron.core.schema import NodeType

    client = MsfClient(password=None)  # Demo mode
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)

    executor = ExecutorService(client=client, graph=graph, catalog=catalog)

    auth = Authorization(
        engagement_ref="ENG-2026-001",
        operator="w00t3k",
        approved_modules=["auxiliary/admin/mainframe/*"],
        scope=["127.0.0.1"]
    )

    result = executor.run(
        mtype="auxiliary",
        path="admin/mainframe/tk5_jcl_submit",
        options={"RHOSTS": "127.0.0.1"},
        authorization=auth
    )

    assert result.success is True
    assert "JOB" in result.output  # Should have job ID in output
    assert result.job_id is not None

    # Verify ModuleRun node was created
    runs = list(graph.get_nodes_by_type(NodeType.MODULE_RUN))
    assert len(runs) == 1
    assert runs[0].provenance.authorization_ref == auth.id

    graph.close()


def test_executor_run_unauthorized_module():
    from bigiron.msf.executor import ExecutorService
    from bigiron.msf.client import MsfClient
    from bigiron.msf.catalog import CatalogService
    from bigiron.msf.authorization import Authorization
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)

    executor = ExecutorService(client=client, graph=graph, catalog=catalog)

    auth = Authorization(
        engagement_ref="ENG-2026-001",
        operator="w00t3k",
        approved_modules=["auxiliary/scanner/*"],  # Only scanners approved
        scope=["127.0.0.1"]
    )

    with pytest.raises(PermissionError, match="not in approved list"):
        executor.run(
            mtype="auxiliary",
            path="admin/mainframe/tk5_jcl_submit",  # admin module not approved
            options={"RHOSTS": "127.0.0.1"},
            authorization=auth
        )

    graph.close()


def test_executor_run_target_out_of_scope():
    from bigiron.msf.executor import ExecutorService
    from bigiron.msf.client import MsfClient
    from bigiron.msf.catalog import CatalogService
    from bigiron.msf.authorization import Authorization
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)

    executor = ExecutorService(client=client, graph=graph, catalog=catalog)

    auth = Authorization(
        engagement_ref="ENG-2026-001",
        operator="w00t3k",
        approved_modules=["*"],
        scope=["10.0.0.0/24"]  # Only 10.0.0.x in scope
    )

    with pytest.raises(PermissionError, match="not in authorized scope"):
        executor.run(
            mtype="auxiliary",
            path="admin/mainframe/tk5_jcl_submit",
            options={"RHOSTS": "192.168.1.1"},  # Out of scope
            authorization=auth
        )

    graph.close()
