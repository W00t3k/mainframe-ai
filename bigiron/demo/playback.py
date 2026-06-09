"""Recorded execution playback."""
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from pydantic import BaseModel, Field

from ..core.graph import ProvenanceGraph
from ..core.schema import Edge, EdgeType, Node, NodeType, Provenance
from .recorder import Recording, RecordingIndex


class PlaybackResult(BaseModel):
    """Result of a recorded playback."""
    module_path: str
    recording_id: str
    success: bool
    output: str
    entities: list[dict[str, Any]]
    simulated: bool = True
    recording_date: datetime
    original_target_type: str

    @property
    def display_badge(self) -> str:
        """Get display badge for UI."""
        date_str = self.recording_date.strftime("%Y-%m-%d")
        return f"[SIMULATED] Recorded {date_str} on {self.original_target_type}"

    def to_node(self) -> Node:
        """Convert to graph node for persistence."""
        node_id = f"run-{self.recording_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        return Node(
            id=node_id,
            node_type=NodeType.MODULE_RUN,
            label=f"Playback: {self.module_path}",
            properties={
                "module_path": self.module_path,
                "success": self.success,
                "output": self.output,
                "simulated": self.simulated,
                "recording_id": self.recording_id,
                "recording_date": self.recording_date.isoformat(),
                "original_target_type": self.original_target_type
            },
            provenance=Provenance()
        )


class RecordedExecutor:
    """Executor that plays back recorded module runs."""

    def __init__(
        self,
        graph: ProvenanceGraph,
        recordings_dir: Path
    ):
        self.graph = graph
        self.recordings_dir = Path(recordings_dir)
        self.index = RecordingIndex.load(self.recordings_dir / "index.json")

    def has_recording(self, module_path: str) -> bool:
        """Check if a recording exists for a module."""
        return self.index.get_recording(module_path) is not None

    def get_available_recordings(self, module_path: str) -> list[str]:
        """Get all available recordings for a module."""
        return [
            r.id for r in self.index.recordings
            if r.module_path == module_path
        ]

    async def playback(
        self,
        module_path: str,
        options: dict[str, str] | None = None,
        output_callback: Callable[[str], None] | None = None,
        speed_multiplier: float = 1.0
    ) -> PlaybackResult:
        """Play back a recorded execution with timing."""
        entry = self.index.get_recording(module_path)
        if not entry:
            raise ValueError(f"No recording found for {module_path}")

        recording_path = self.recordings_dir / entry.file_path
        recording = Recording.load(recording_path)

        output_lines = []
        for line in recording.output_lines:
            delay = line.delay / speed_multiplier
            if delay > 0:
                await asyncio.sleep(delay)

            output_lines.append(line.text)
            if output_callback:
                output_callback(line.text)

        output = "\n".join(output_lines)

        result = PlaybackResult(
            module_path=module_path,
            recording_id=recording.id,
            success=recording.success,
            output=output,
            entities=recording.entities,
            simulated=True,
            recording_date=recording.recorded_at,
            original_target_type=recording.target_type
        )

        node = result.to_node()
        self.graph.add_node(node)

        for entity_data in recording.entities:
            entity_node = Node(
                id=f"entity-sim-{entity_data.get('id', 'unknown')}-{datetime.now(timezone.utc).strftime('%f')}",
                node_type=NodeType(entity_data.get("type", "finding")),
                label=entity_data.get("label", entity_data.get("id", "Unknown")),
                properties={
                    **entity_data,
                    "simulated": True,
                    "recording_id": recording.id
                },
                provenance=Provenance(simulated=True)
            )
            self.graph.add_node(entity_node)
            self.graph.add_edge(Edge(
                source_id=node.id,
                target_id=entity_node.id,
                edge_type=EdgeType.DISCOVERED
            ))

        return result

    def playback_sync(
        self,
        module_path: str,
        options: dict[str, str] | None = None,
        output_callback: Callable[[str], None] | None = None,
        speed_multiplier: float = 1.0
    ) -> PlaybackResult:
        """Synchronous wrapper for playback."""
        return asyncio.run(self.playback(
            module_path=module_path,
            options=options,
            output_callback=output_callback,
            speed_multiplier=speed_multiplier
        ))
