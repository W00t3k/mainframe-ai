"""Recording schema and recorder for capturing live executions."""
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field
import json


class RecordingLine(BaseModel):
    """A single line of output with timing info."""
    timestamp: float  # Seconds since start
    text: str
    delay: float  # Delay before this line (for playback)


class Recording(BaseModel):
    """A recorded module execution."""
    id: str
    module_path: str
    options: dict[str, str]
    recorded_at: datetime
    target_type: str  # e.g., "z/OS 2.5", "TK5", "z/OS 3.1"
    duration_seconds: float
    output_lines: list[RecordingLine]
    entities: list[dict[str, Any]]  # Parsed entities
    success: bool
    notes: str = ""

    def save(self, base_dir: Path) -> Path:
        """Save recording to file."""
        safe_path = self.module_path.replace("/", "__")
        module_dir = base_dir / safe_path
        module_dir.mkdir(parents=True, exist_ok=True)

        file_path = module_dir / f"{self.id}.json"
        with open(file_path, "w") as f:
            json.dump(self.model_dump(mode="json"), f, indent=2, default=str)

        return file_path

    @classmethod
    def load(cls, file_path: Path) -> "Recording":
        """Load recording from file."""
        with open(file_path) as f:
            data = json.load(f)

        if isinstance(data.get("recorded_at"), str):
            data["recorded_at"] = datetime.fromisoformat(data["recorded_at"])

        return cls(**data)


class RecordingIndexEntry(BaseModel):
    """Entry in the recording index."""
    id: str
    module_path: str
    recorded_at: datetime
    target_type: str
    file_path: str


class RecordingIndex(BaseModel):
    """Index of all available recordings."""
    recordings: list[RecordingIndexEntry] = Field(default_factory=list)

    def get_recording(
        self,
        module_path: str,
        target_type: str | None = None
    ) -> RecordingIndexEntry | None:
        """Get the most recent recording for a module."""
        matches = [r for r in self.recordings if r.module_path == module_path]

        if target_type:
            matches = [r for r in matches if r.target_type == target_type]

        if not matches:
            return None

        return max(matches, key=lambda r: r.recorded_at)

    def add_recording(self, entry: RecordingIndexEntry):
        """Add a recording to the index."""
        self.recordings.append(entry)

    def save(self, file_path: Path):
        """Save index to file."""
        with open(file_path, "w") as f:
            json.dump(self.model_dump(mode="json"), f, indent=2, default=str)

    @classmethod
    def load(cls, file_path: Path) -> "RecordingIndex":
        """Load index from file."""
        if not file_path.exists():
            return cls()

        with open(file_path) as f:
            data = json.load(f)

        for rec in data.get("recordings", []):
            if isinstance(rec.get("recorded_at"), str):
                rec["recorded_at"] = datetime.fromisoformat(rec["recorded_at"])

        return cls(**data)


class Recorder:
    """Records live module executions for later playback."""

    def __init__(self, recordings_dir: Path):
        self.recordings_dir = Path(recordings_dir)
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.recordings_dir / "index.json"
        self.index = RecordingIndex.load(self.index_path)

    def start_recording(
        self,
        module_path: str,
        options: dict[str, str],
        target_type: str
    ) -> "RecordingSession":
        recording_id = f"rec-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        return RecordingSession(
            recorder=self,
            recording_id=recording_id,
            module_path=module_path,
            options=options,
            target_type=target_type
        )


class RecordingSession:
    """Active recording session for capturing output."""

    def __init__(
        self,
        recorder: Recorder,
        recording_id: str,
        module_path: str,
        options: dict[str, str],
        target_type: str
    ):
        self.recorder = recorder
        self.recording_id = recording_id
        self.module_path = module_path
        self.options = options
        self.target_type = target_type
        self.start_time = datetime.now(timezone.utc)
        self.lines: list[RecordingLine] = []
        self.entities: list[dict[str, Any]] = []
        self._last_timestamp = 0.0

    def add_line(self, text: str):
        now = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        delay = now - self._last_timestamp

        self.lines.append(RecordingLine(
            timestamp=now,
            text=text,
            delay=delay
        ))
        self._last_timestamp = now

    def add_entities(self, entities: list[dict[str, Any]]):
        self.entities.extend(entities)

    def finish(self, success: bool = True, notes: str = "") -> Recording:
        duration = (datetime.now(timezone.utc) - self.start_time).total_seconds()

        recording = Recording(
            id=self.recording_id,
            module_path=self.module_path,
            options=self.options,
            recorded_at=self.start_time,
            target_type=self.target_type,
            duration_seconds=duration,
            output_lines=self.lines,
            entities=self.entities,
            success=success,
            notes=notes
        )

        file_path = recording.save(self.recorder.recordings_dir)

        relative_path = file_path.relative_to(self.recorder.recordings_dir)
        entry = RecordingIndexEntry(
            id=recording.id,
            module_path=recording.module_path,
            recorded_at=recording.recorded_at,
            target_type=recording.target_type,
            file_path=str(relative_path)
        )
        self.recorder.index.add_recording(entry)
        self.recorder.index.save(self.recorder.index_path)

        return recording
