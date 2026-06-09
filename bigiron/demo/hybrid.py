# bigiron/demo/hybrid.py
"""Hybrid executor that auto-selects live or recorded execution."""
from pathlib import Path
from typing import Any, Callable, Literal

from ..core.graph import ProvenanceGraph
from ..msf import ExecutorService, Authorization
from ..msf.executor import ExecutionResult
from .mode import ExecutionMode, get_compatibility, should_use_recording
from .playback import RecordedExecutor, PlaybackResult
from .recorder import Recorder


class HybridExecutor:
    """Executor that automatically selects live or recorded execution."""

    def __init__(
        self,
        graph: ProvenanceGraph,
        live_executor: ExecutorService,
        recordings_dir: Path,
        mode: ExecutionMode = ExecutionMode.HYBRID
    ):
        self.graph = graph
        self.live_executor = live_executor
        self.recorded_executor = RecordedExecutor(
            graph=graph,
            recordings_dir=recordings_dir
        )
        self.recorder = Recorder(recordings_dir)
        self.mode = mode

    @property
    def is_live_available(self) -> bool:
        """Check if live MSF is available."""
        return not self.live_executor.client.is_demo_mode

    def get_execution_strategy(
        self,
        module_path: str
    ) -> Literal["live", "recorded"]:
        """Determine execution strategy for a module."""
        if self.mode == ExecutionMode.LIVE:
            return "live"

        if self.mode == ExecutionMode.RECORDED:
            if self.recorded_executor.has_recording(module_path):
                return "recorded"
            return "live"

        # Hybrid mode: use compatibility matrix
        compat = get_compatibility(module_path)

        if compat.demo_strategy == "recorded":
            if self.recorded_executor.has_recording(module_path):
                return "recorded"

        return "live"

    def preview(
        self,
        module_path: str,
        options: dict[str, str]
    ) -> dict[str, Any]:
        """Preview execution without running."""
        strategy = self.get_execution_strategy(module_path)
        compat = get_compatibility(module_path)

        preview = {
            "module_path": module_path,
            "options": options,
            "strategy": strategy,
            "compatibility": {
                "works_on_tk5": compat.works_on_tk5,
                "requires_modern_zos": compat.requires_modern_zos,
                "notes": compat.notes
            }
        }

        if strategy == "recorded":
            entry = self.recorded_executor.index.get_recording(module_path)
            if entry:
                preview["recording"] = {
                    "id": entry.id,
                    "recorded_at": entry.recorded_at.isoformat(),
                    "target_type": entry.target_type
                }

        return preview

    def run(
        self,
        module_path: str,
        options: dict[str, str],
        authorization: Authorization | None = None,
        output_callback: Callable[[str], None] | None = None,
        record_execution: bool = False,
        target_type: str = "TK5"
    ) -> ExecutionResult | PlaybackResult:
        """Execute module using appropriate strategy."""
        strategy = self.get_execution_strategy(module_path)

        if strategy == "recorded":
            return self.recorded_executor.playback_sync(
                module_path=module_path,
                options=options,
                output_callback=output_callback
            )

        # Live execution
        if authorization is None:
            raise ValueError("Authorization required for live execution")

        parts = module_path.split("/", 1)
        mtype = parts[0]
        path = parts[1] if len(parts) > 1 else module_path

        session = None
        if record_execution:
            session = self.recorder.start_recording(
                module_path=module_path,
                options=options,
                target_type=target_type
            )

        def capturing_callback(line: str):
            if session:
                session.add_line(line)
            if output_callback:
                output_callback(line)

        result = self.live_executor.run(
            mtype=mtype,
            path=path,
            options=options,
            authorization=authorization
        )

        if session:
            for line in result.output.split("\n"):
                session.add_line(line)

            session.add_entities([
                e.model_dump() for e in result.entities
            ])

            session.finish(success=result.success)

        return result

    async def run_async(
        self,
        module_path: str,
        options: dict[str, str],
        authorization: Authorization | None = None,
        output_callback: Callable[[str], None] | None = None
    ) -> ExecutionResult | PlaybackResult:
        """Async execution for recorded playback with timing."""
        strategy = self.get_execution_strategy(module_path)

        if strategy == "recorded":
            return await self.recorded_executor.playback(
                module_path=module_path,
                options=options,
                output_callback=output_callback
            )

        return self.run(
            module_path=module_path,
            options=options,
            authorization=authorization,
            output_callback=output_callback
        )
