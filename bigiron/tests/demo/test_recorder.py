# bigiron/tests/demo/test_recorder.py
import pytest
import json
from pathlib import Path
from datetime import datetime, timezone


def test_recording_schema():
    from bigiron.demo.recorder import Recording, RecordingLine

    line = RecordingLine(
        timestamp=0.0,
        text="[*] Starting TSO enumeration...",
        delay=0.1
    )

    recording = Recording(
        id="rec-20260608-tso-enum-001",
        module_path="auxiliary/scanner/mainframe/tso_enum",
        options={"RHOSTS": "10.0.0.1"},
        recorded_at=datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc),
        target_type="z/OS 2.5",
        duration_seconds=5.2,
        output_lines=[line],
        entities=[{"type": "user", "id": "IBMUSER"}],
        success=True
    )

    assert recording.id == "rec-20260608-tso-enum-001"
    assert len(recording.output_lines) == 1
    assert recording.target_type == "z/OS 2.5"


def test_recording_to_json():
    from bigiron.demo.recorder import Recording, RecordingLine

    recording = Recording(
        id="rec-test-001",
        module_path="auxiliary/scanner/mainframe/tso_enum",
        options={"RHOSTS": "10.0.0.1"},
        recorded_at=datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc),
        target_type="TK5",
        duration_seconds=2.0,
        output_lines=[
            RecordingLine(timestamp=0.0, text="[*] Starting...", delay=0.1)
        ],
        entities=[],
        success=True
    )

    data = recording.model_dump()

    assert data["module_path"] == "auxiliary/scanner/mainframe/tso_enum"
    assert data["target_type"] == "TK5"


def test_recording_index():
    from bigiron.demo.recorder import RecordingIndex, RecordingIndexEntry

    entry = RecordingIndexEntry(
        id="rec-001",
        module_path="auxiliary/scanner/mainframe/tso_enum",
        recorded_at=datetime(2026, 6, 8, tzinfo=timezone.utc),
        target_type="z/OS 2.5",
        file_path="auxiliary__scanner__mainframe__tso_enum/rec-001.json"
    )

    index = RecordingIndex(recordings=[entry])

    assert len(index.recordings) == 1
    assert index.get_recording("auxiliary/scanner/mainframe/tso_enum") == entry


def test_recording_index_multiple_per_module():
    from bigiron.demo.recorder import RecordingIndex, RecordingIndexEntry

    older = RecordingIndexEntry(
        id="rec-001",
        module_path="auxiliary/scanner/mainframe/tso_enum",
        recorded_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        target_type="z/OS 2.4",
        file_path="tso_enum/rec-001.json"
    )

    newer = RecordingIndexEntry(
        id="rec-002",
        module_path="auxiliary/scanner/mainframe/tso_enum",
        recorded_at=datetime(2026, 6, 8, tzinfo=timezone.utc),
        target_type="z/OS 2.5",
        file_path="tso_enum/rec-002.json"
    )

    index = RecordingIndex(recordings=[older, newer])

    # Should return most recent
    result = index.get_recording("auxiliary/scanner/mainframe/tso_enum")
    assert result.id == "rec-002"
