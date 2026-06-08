"""Executor service for running MSF modules with authorization."""
import re
import time
from datetime import datetime, timezone

from .client import MsfClient
from .catalog import CatalogService
from .models import ModuleSummary, ExecutionPreview, ExecutionResult
from .authorization import Authorization, AuthorizationGate
from .demo_data import DEMO_EXECUTION_OUTPUT
from ..core.graph import ProvenanceGraph
from ..core.schema import Node, Edge, NodeType, EdgeType, Provenance


class ExecutorService:
    """Executes MSF modules with authorization gates and provenance tracking.

    All executions are recorded in the provenance graph with full audit trail.
    """

    def __init__(
        self,
        client: MsfClient,
        graph: ProvenanceGraph,
        catalog: CatalogService
    ):
        """Initialize executor.

        Args:
            client: MSF RPC client
            graph: Provenance graph for recording executions
            catalog: Catalog service for module lookup
        """
        self.client = client
        self.graph = graph
        self.catalog = catalog

    def preview(
        self,
        mtype: str,
        path: str,
        options: dict[str, str]
    ) -> ExecutionPreview:
        """Preview what will be executed (no authorization required).

        Args:
            mtype: Module type
            path: Module path
            options: Module options

        Returns:
            Preview of the execution
        """
        module = self.catalog.get_module(mtype, path)
        if not module:
            module = ModuleSummary(mtype=mtype, path=path, name=path, rank="normal")

        # Build the command that would be run
        full_path = f"{mtype}/{path}"
        command_lines = [f"use {full_path}"]

        for key, value in options.items():
            command_lines.append(f"set {key} {value}")

        command_lines.append("run")
        command = "\n".join(command_lines)

        target = options.get("RHOSTS", options.get("RHOST", "unknown"))

        return ExecutionPreview(
            module=ModuleSummary(
                mtype=mtype,
                path=path,
                name=module.name if hasattr(module, 'name') else path,
                rank=module.rank if hasattr(module, 'rank') else "normal"
            ),
            options=options,
            command=command,
            target_description=f"Target: {target}"
        )

    def run(
        self,
        mtype: str,
        path: str,
        options: dict[str, str],
        authorization: Authorization | None = None
    ) -> ExecutionResult:
        """Execute a module with authorization.

        Args:
            mtype: Module type
            path: Module path
            options: Module options
            authorization: Authorization for this execution

        Returns:
            Execution result

        Raises:
            PermissionError: If not authorized
        """
        full_path = f"{mtype}/{path}"
        target = options.get("RHOSTS", options.get("RHOST", ""))

        # Require authorization
        if authorization is None:
            raise PermissionError("No authorization provided for execution")

        # Validate authorization
        gate = AuthorizationGate(authorization)
        gate.require(full_path, target)

        # Ensure authorization is in graph
        auth_node = self.graph.get_node(authorization.id)
        if not auth_node:
            self.graph.add_node(authorization.to_node())

        # Execute
        start_time = time.time()

        if self.client.is_demo_mode:
            result = self._run_demo(full_path, options)
        else:
            result = self._run_live(mtype, path, options)

        duration_ms = int((time.time() - start_time) * 1000)
        result.duration_ms = duration_ms

        # Record in graph
        self._record_execution(full_path, options, result, authorization)

        return result

    def _run_demo(self, full_path: str, options: dict[str, str]) -> ExecutionResult:
        """Run in demo mode with canned output."""
        output = DEMO_EXECUTION_OUTPUT.get(
            full_path,
            f"[*] Running {full_path}...\n[+] Module completed (demo mode)"
        )

        # Extract job ID if present
        job_id = None
        job_match = re.search(r'JOB(?:ID)?[:\s]*(\w+)', output)
        if job_match:
            job_id = job_match.group(1)

        return ExecutionResult(
            module_path=full_path,
            success=True,
            output=output,
            job_id=job_id
        )

    def _run_live(self, mtype: str, path: str, options: dict[str, str]) -> ExecutionResult:
        """Run against live MSF instance."""
        if not self.client.is_connected:
            self.client.connect()

        try:
            # Create console
            console = self.client.client.consoles.console()

            # Execute module
            full_path = f"{mtype}/{path}"
            console.write(f"use {full_path}")

            for key, value in options.items():
                console.write(f"set {key} {value}")

            console.write("run")

            # Wait for completion and gather output
            output_lines = []
            timeout = 90  # seconds
            start = time.time()

            while time.time() - start < timeout:
                data = console.read()
                if data.get("data"):
                    output_lines.append(data["data"])
                if data.get("busy") is False:
                    break
                time.sleep(0.5)

            output = "".join(output_lines)

            # Extract job ID if present
            job_id = None
            job_match = re.search(r'JOB(?:ID)?[:\s]*(\w+)', output)
            if job_match:
                job_id = job_match.group(1)

            # Destroy console
            console.destroy()

            return ExecutionResult(
                module_path=full_path,
                success=True,
                output=output,
                job_id=job_id
            )

        except Exception as e:
            return ExecutionResult(
                module_path=f"{mtype}/{path}",
                success=False,
                output="",
                error=str(e)
            )

    def _record_execution(
        self,
        full_path: str,
        options: dict[str, str],
        result: ExecutionResult,
        authorization: Authorization
    ):
        """Record execution in the provenance graph."""
        # Create ModuleRun node
        run_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"

        run_node = Node(
            id=run_id,
            node_type=NodeType.MODULE_RUN,
            label=f"Run: {full_path}",
            properties={
                "module_path": full_path,
                "options": options,
                "success": result.success,
                "job_id": result.job_id,
                "duration_ms": result.duration_ms,
                "error": result.error
            },
            provenance=Provenance(
                authorization_ref=authorization.id,
                raw_output=result.output
            )
        )
        self.graph.add_node(run_node)

        # Link to authorization
        self.graph.add_edge(Edge(
            source_id=run_id,
            target_id=authorization.id,
            edge_type=EdgeType.AUTHORIZED_BY
        ))

        # Link to module node if it exists
        module_node_id = f"msf-{full_path.replace('/', '-')}"
        if self.graph.get_node(module_node_id):
            self.graph.add_edge(Edge(
                source_id=run_id,
                target_id=module_node_id,
                edge_type=EdgeType.EXECUTES
            ))

        # Create target node if RHOSTS specified
        target = options.get("RHOSTS", options.get("RHOST"))
        if target:
            target_id = f"host-{target.replace('.', '-')}"
            if not self.graph.get_node(target_id):
                self.graph.add_node(Node(
                    id=target_id,
                    node_type=NodeType.HOST,
                    label=target,
                    properties={"ip": target}
                ))

            self.graph.add_edge(Edge(
                source_id=run_id,
                target_id=target_id,
                edge_type=EdgeType.TARGETS
            ))
