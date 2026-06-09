"""Integration tests for demo/hybrid mode."""
import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from bigiron.core.graph import ProvenanceGraph
from bigiron.core.schema import NodeType
from bigiron.msf import MsfClient, CatalogService, ExecutorService, Authorization
from bigiron.demo import (
    ExecutionMode,
    HybridExecutor,
    Recorder,
    RecordingIndex,
    RecordingIndexEntry,
    Recording,
    RecordingLine,
    get_compatibility,
)


def test_full_recording_and_playback_cycle():
    """Test recording a live execution and playing it back."""

    with tempfile.TemporaryDirectory() as tmpdir:
        recordings_dir = Path(tmpdir)

        # Setup
        client = MsfClient(password=None)
        graph = ProvenanceGraph(":memory:")
        catalog = CatalogService(client=client, graph=graph)

        # Create a recording manually (simulating captured output)
        recording = Recording(
            id="rec-test-001",
            module_path="auxiliary/scanner/mainframe/tso_enum",
            options={"RHOSTS": "10.0.0.1"},
            recorded_at=datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc),
            target_type="z/OS 2.5",
            duration_seconds=3.5,
            output_lines=[
                RecordingLine(timestamp=0.0, text="[*] Starting TSO enumeration...", delay=0.0),
                RecordingLine(timestamp=0.5, text="[*] Connecting to FTP...", delay=0.5),
                RecordingLine(timestamp=1.0, text="[+] Found user: IBMUSER", delay=0.5),
                RecordingLine(timestamp=1.5, text="[+] Found user: SYSADM", delay=0.5),
                RecordingLine(timestamp=2.0, text="[*] Enumeration complete", delay=0.5),
            ],
            entities=[
                {"type": "user", "id": "IBMUSER", "label": "IBMUSER"},
                {"type": "user", "id": "SYSADM", "label": "SYSADM"},
            ],
            success=True
        )

        # Save recording
        recording.save(recordings_dir)

        # Create index
        index = RecordingIndex(recordings=[
            RecordingIndexEntry(
                id=recording.id,
                module_path=recording.module_path,
                recorded_at=recording.recorded_at,
                target_type=recording.target_type,
                file_path=f"auxiliary__scanner__mainframe__tso_enum/{recording.id}.json"
            )
        ])
        index.save(recordings_dir / "index.json")

        # Create hybrid executor in RECORDED mode
        executor = ExecutorService(client=client, graph=graph, catalog=catalog)
        hybrid = HybridExecutor(
            graph=graph,
            live_executor=executor,
            recordings_dir=recordings_dir,
            mode=ExecutionMode.RECORDED
        )

        # Playback
        output_lines = []
        result = hybrid.run(
            module_path="auxiliary/scanner/mainframe/tso_enum",
            options={"RHOSTS": "10.0.0.1"},
            output_callback=lambda line: output_lines.append(line)
        )

        assert result.simulated is True
        assert result.success is True
        assert "IBMUSER" in result.output
        assert len(result.entities) == 2
        assert "[SIMULATED]" in result.display_badge

        # Verify graph persistence
        runs = list(graph.get_nodes_by_type(NodeType.MODULE_RUN))
        assert len(runs) == 1
        assert runs[0].properties["simulated"] is True

        graph.close()


def test_hybrid_mode_with_live_and_recorded():
    """Test hybrid mode selecting appropriate strategy."""

    with tempfile.TemporaryDirectory() as tmpdir:
        recordings_dir = Path(tmpdir)

        # Setup
        client = MsfClient(password=None)  # Demo mode
        graph = ProvenanceGraph(":memory:")
        catalog = CatalogService(client=client, graph=graph)
        executor = ExecutorService(client=client, graph=graph, catalog=catalog)

        # Create recording for a modern z/OS module
        recording = Recording(
            id="rec-db2-001",
            module_path="auxiliary/scanner/mainframe/db2_enum",
            options={"RHOSTS": "10.0.0.1"},
            recorded_at=datetime(2026, 6, 8, tzinfo=timezone.utc),
            target_type="z/OS 2.5",
            duration_seconds=5.0,
            output_lines=[
                RecordingLine(timestamp=0.0, text="[*] DB2 enumeration starting", delay=0.0),
                RecordingLine(timestamp=1.0, text="[+] Found database: MAINDB", delay=1.0),
            ],
            entities=[{"type": "database", "id": "MAINDB"}],
            success=True
        )
        recording.save(recordings_dir)

        # Create index
        index = RecordingIndex(recordings=[
            RecordingIndexEntry(
                id=recording.id,
                module_path=recording.module_path,
                recorded_at=recording.recorded_at,
                target_type=recording.target_type,
                file_path=f"auxiliary__scanner__mainframe__db2_enum/{recording.id}.json"
            )
        ])
        index.save(recordings_dir / "index.json")

        hybrid = HybridExecutor(
            graph=graph,
            live_executor=executor,
            recordings_dir=recordings_dir,
            mode=ExecutionMode.HYBRID
        )

        # TK5-compatible module should select live
        tk5_strategy = hybrid.get_execution_strategy(
            "auxiliary/admin/mainframe/tk5_jcl_submit"
        )
        assert tk5_strategy == "live"

        # Modern z/OS module with recording should select recorded
        db2_strategy = hybrid.get_execution_strategy(
            "auxiliary/scanner/mainframe/db2_enum"
        )
        assert db2_strategy == "recorded"

        graph.close()


def test_compatibility_matrix_coverage():
    """Verify compatibility matrix has expected modules."""

    # TK5-compatible
    tk5_compat = get_compatibility("auxiliary/admin/mainframe/tk5_jcl_submit")
    assert tk5_compat.works_on_tk5 is True
    assert tk5_compat.demo_strategy == "live"

    tso_compat = get_compatibility("auxiliary/scanner/mainframe/tso_enum")
    assert tso_compat.works_on_tk5 is True

    # Modern z/OS only
    db2_compat = get_compatibility("auxiliary/scanner/mainframe/db2_enum")
    assert db2_compat.works_on_tk5 is False
    assert db2_compat.requires_modern_zos is True
    assert db2_compat.demo_strategy == "recorded"

    # Partial support
    racf_compat = get_compatibility("auxiliary/scanner/mainframe/racf_profile_check")
    assert racf_compat.works_on_tk5 == "partial"
