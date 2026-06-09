# bigiron/tests/demo/test_hybrid.py
import pytest
from pathlib import Path
from datetime import datetime, timezone


def test_hybrid_executor_creation():
    from bigiron.demo.hybrid import HybridExecutor
    from bigiron.demo.mode import ExecutionMode
    from bigiron.msf import MsfClient, CatalogService, ExecutorService
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)
    executor = ExecutorService(client=client, graph=graph, catalog=catalog)

    hybrid = HybridExecutor(
        graph=graph,
        live_executor=executor,
        recordings_dir=Path("data/recordings"),
        mode=ExecutionMode.HYBRID
    )

    assert hybrid.mode == ExecutionMode.HYBRID

    graph.close()


def test_hybrid_executor_selects_live_for_tk5_module():
    from bigiron.demo.hybrid import HybridExecutor
    from bigiron.demo.mode import ExecutionMode
    from bigiron.msf import MsfClient, CatalogService, ExecutorService
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)
    executor = ExecutorService(client=client, graph=graph, catalog=catalog)

    hybrid = HybridExecutor(
        graph=graph,
        live_executor=executor,
        recordings_dir=Path("data/recordings"),
        mode=ExecutionMode.HYBRID
    )

    strategy = hybrid.get_execution_strategy("auxiliary/admin/mainframe/tk5_jcl_submit")

    assert strategy == "live"

    graph.close()


def test_hybrid_executor_selects_recorded_for_modern_module():
    from bigiron.demo.hybrid import HybridExecutor
    from bigiron.demo.mode import ExecutionMode
    from bigiron.demo.recorder import RecordingIndex, RecordingIndexEntry
    from bigiron.msf import MsfClient, CatalogService, ExecutorService
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)
    executor = ExecutorService(client=client, graph=graph, catalog=catalog)

    hybrid = HybridExecutor(
        graph=graph,
        live_executor=executor,
        recordings_dir=Path("data/recordings"),
        mode=ExecutionMode.HYBRID
    )

    # Add a recording for the module
    hybrid.recorded_executor.index = RecordingIndex(recordings=[
        RecordingIndexEntry(
            id="rec-001",
            module_path="auxiliary/scanner/mainframe/db2_enum",
            recorded_at=datetime(2026, 6, 8, tzinfo=timezone.utc),
            target_type="z/OS 2.5",
            file_path="db2_enum/rec-001.json"
        )
    ])

    strategy = hybrid.get_execution_strategy("auxiliary/scanner/mainframe/db2_enum")

    assert strategy == "recorded"

    graph.close()


def test_hybrid_executor_falls_back_to_live_without_recording():
    from bigiron.demo.hybrid import HybridExecutor
    from bigiron.demo.mode import ExecutionMode
    from bigiron.msf import MsfClient, CatalogService, ExecutorService
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)
    executor = ExecutorService(client=client, graph=graph, catalog=catalog)

    hybrid = HybridExecutor(
        graph=graph,
        live_executor=executor,
        recordings_dir=Path("data/recordings"),
        mode=ExecutionMode.HYBRID
    )

    # DB2 requires recording but none exists
    strategy = hybrid.get_execution_strategy("auxiliary/scanner/mainframe/db2_enum")

    # Falls back to live (will fail at execution but strategy is live)
    assert strategy == "live"

    graph.close()


def test_hybrid_executor_respects_mode_override():
    from bigiron.demo.hybrid import HybridExecutor
    from bigiron.demo.mode import ExecutionMode
    from bigiron.msf import MsfClient, CatalogService, ExecutorService
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)
    executor = ExecutorService(client=client, graph=graph, catalog=catalog)

    hybrid = HybridExecutor(
        graph=graph,
        live_executor=executor,
        recordings_dir=Path("data/recordings"),
        mode=ExecutionMode.LIVE  # Force live mode
    )

    # Even for a module that prefers recording
    strategy = hybrid.get_execution_strategy("auxiliary/scanner/mainframe/db2_enum")

    assert strategy == "live"

    graph.close()
