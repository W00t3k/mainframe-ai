"""Demo/Hybrid mode for live and recorded execution."""
from .mode import (
    ExecutionMode,
    ModuleCompatibility,
    COMPATIBILITY_MATRIX,
    get_compatibility,
    should_use_recording,
)
from .recorder import (
    Recording,
    RecordingLine,
    RecordingIndex,
    RecordingIndexEntry,
    Recorder,
    RecordingSession,
)
from .playback import (
    PlaybackResult,
    RecordedExecutor,
)
from .hybrid import HybridExecutor

__all__ = [
    # Mode
    "ExecutionMode",
    "ModuleCompatibility",
    "COMPATIBILITY_MATRIX",
    "get_compatibility",
    "should_use_recording",
    # Recording
    "Recording",
    "RecordingLine",
    "RecordingIndex",
    "RecordingIndexEntry",
    "Recorder",
    "RecordingSession",
    # Playback
    "PlaybackResult",
    "RecordedExecutor",
    # Hybrid
    "HybridExecutor",
]
