# bigiron/tests/demo/test_playback.py
import pytest
import asyncio
from pathlib import Path
from datetime import datetime, timezone


def test_recorded_executor_creation():
    from bigiron.demo.playback import RecordedExecutor
    from bigiron.core.graph import ProvenanceGraph

    graph = ProvenanceGraph(":memory:")
    executor = RecordedExecutor(
        graph=graph,
        recordings_dir=Path("data/recordings")
    )

    assert executor.recordings_dir == Path("data/recordings")

    graph.close()


def test_recorded_executor_has_recording():
    from bigiron.demo.playback import RecordedExecutor
    from bigiron.demo.recorder import RecordingIndex, RecordingIndexEntry
    from bigiron.core.graph import ProvenanceGraph

    graph = ProvenanceGraph(":memory:")
    executor = RecordedExecutor(
        graph=graph,
        recordings_dir=Path("data/recordings")
    )

    # Manually add an index entry for testing
    executor.index = RecordingIndex(recordings=[
        RecordingIndexEntry(
            id="rec-001",
            module_path="auxiliary/scanner/mainframe/racf_enum",
            recorded_at=datetime(2026, 6, 8, tzinfo=timezone.utc),
            target_type="z/OS 2.5",
            file_path="racf_enum/rec-001.json"
        )
    ])

    assert executor.has_recording("auxiliary/scanner/mainframe/racf_enum") is True
    assert executor.has_recording("auxiliary/scanner/mainframe/unknown") is False

    graph.close()


def test_playback_result_structure():
    from bigiron.demo.playback import PlaybackResult

    result = PlaybackResult(
        module_path="auxiliary/scanner/mainframe/racf_enum",
        recording_id="rec-001",
        success=True,
        output="[*] RACF enumeration complete\n[+] Found 5 profiles",
        entities=[{"type": "racf_profile", "id": "IBMUSER"}],
        simulated=True,
        recording_date=datetime(2026, 6, 8, tzinfo=timezone.utc),
        original_target_type="z/OS 2.5"
    )

    assert result.simulated is True
    assert result.recording_id == "rec-001"
    assert "[SIMULATED]" in result.display_badge


def test_playback_to_module_run():
    from bigiron.demo.playback import PlaybackResult
    from bigiron.core.schema import NodeType

    result = PlaybackResult(
        module_path="auxiliary/scanner/mainframe/racf_enum",
        recording_id="rec-001",
        success=True,
        output="[*] RACF enumeration complete",
        entities=[],
        simulated=True,
        recording_date=datetime(2026, 6, 8, tzinfo=timezone.utc),
        original_target_type="z/OS 2.5"
    )

    node = result.to_node()

    assert node.node_type == NodeType.MODULE_RUN
    assert node.properties["simulated"] is True
    assert node.properties["recording_id"] == "rec-001"
