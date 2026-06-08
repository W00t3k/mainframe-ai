"""Agent tools for reading graph state and proposing actions."""
from typing import Any

from ..core.graph import ProvenanceGraph
from ..core.schema import NodeType
from ..msf import CatalogService
from .schema import ProposedAction


class AgentTools:
    """Tools available to the agent.

    Read-only tools query the graph and MSF catalog.
    Propose tools create proposals that require human authorization.
    """

    def __init__(self, graph: ProvenanceGraph, catalog: CatalogService):
        """Initialize agent tools.

        Args:
            graph: Provenance graph for state queries
            catalog: MSF catalog for module lookup
        """
        self.graph = graph
        self.catalog = catalog
        self._pending_proposals: list[ProposedAction] = []

    # --- Read-only tools ---

    def search_modules(
        self,
        query: str,
        mtype: str | None = None
    ) -> list[dict[str, Any]]:
        """Search for modules matching criteria.

        Args:
            query: Search query string
            mtype: Optional module type filter

        Returns:
            List of module summaries
        """
        results = self.catalog.search(query, mtype)
        return [
            {
                "mtype": m.mtype,
                "path": m.path,
                "name": m.name,
                "full_path": m.full_path,
                "rank": m.rank
            }
            for m in results
        ]

    def inspect_module(
        self,
        mtype: str,
        path: str
    ) -> dict[str, Any] | None:
        """Get full details for a specific module.

        Args:
            mtype: Module type
            path: Module path

        Returns:
            Module details or None if not found
        """
        detail = self.catalog.get_module(mtype, path)
        if not detail:
            return None

        return {
            "mtype": detail.mtype,
            "path": detail.path,
            "name": detail.name,
            "full_path": detail.full_path,
            "description": detail.description,
            "authors": detail.authors,
            "options": [
                {
                    "name": opt.name,
                    "required": opt.required,
                    "description": opt.description,
                    "default": opt.default
                }
                for opt in detail.options
            ],
            "targets": detail.targets,
            "tk5_compatible": detail.tk5_compatible,
            "requires_modern_zos": detail.requires_modern_zos
        }

    def query_graph_stats(self) -> dict[str, Any]:
        """Get graph statistics.

        Returns:
            Statistics about the current graph state
        """
        stats = self.graph.stats()

        # Get counts by node type
        node_counts = {}
        for node_type in NodeType:
            nodes = list(self.graph.get_nodes_by_type(node_type))
            if nodes:
                node_counts[node_type.value] = len(nodes)

        return {
            **stats,
            "node_counts": node_counts
        }

    def query_graph_nodes(
        self,
        node_type: str,
        limit: int = 20
    ) -> list[dict[str, Any]]:
        """Query nodes of a specific type.

        Args:
            node_type: Node type to query
            limit: Maximum nodes to return

        Returns:
            List of node summaries
        """
        try:
            nt = NodeType(node_type)
        except ValueError:
            return []

        nodes = list(self.graph.get_nodes_by_type(nt))[:limit]
        return [
            {
                "id": n.id,
                "label": n.label,
                "properties": n.properties
            }
            for n in nodes
        ]

    def get_findings(self) -> list[dict[str, Any]]:
        """Get all findings from the graph.

        Returns:
            List of finding summaries
        """
        findings = list(self.graph.get_nodes_by_type(NodeType.VULNERABILITY))
        return [
            {
                "id": f.id,
                "label": f.label,
                "severity": f.properties.get("severity", "unknown"),
                "description": f.properties.get("description", "")
            }
            for f in findings
        ]

    # --- Proposal tools ---

    def propose_execution(
        self,
        module_path: str,
        options: dict[str, str],
        reasoning: str,
        risk_level: str = "low"
    ) -> dict[str, Any]:
        """Propose a module execution for human approval.

        This does NOT execute anything - it creates a proposal
        that the human operator must approve.

        Args:
            module_path: Full module path
            options: Module options
            reasoning: Why this action is recommended
            risk_level: low/medium/high/critical

        Returns:
            Proposal status
        """
        # Parse module path
        parts = module_path.split("/", 1)
        mtype = parts[0] if len(parts) > 1 else "auxiliary"
        path = parts[1] if len(parts) > 1 else module_path

        # Get target description
        target_desc = f"Target: {options.get('RHOSTS', options.get('RHOST', 'unknown'))}"

        action = ProposedAction(
            module_path=module_path,
            options=options,
            reasoning=reasoning,
            risk_level=risk_level,
            target_description=target_desc
        )

        self._pending_proposals.append(action)

        return {
            "status": "proposed",
            "action": action.model_dump(),
            "message": "Action proposed. Awaiting authorization from operator."
        }

    def get_pending_proposals(self) -> list[ProposedAction]:
        """Get all pending action proposals.

        Returns:
            List of proposed actions awaiting approval
        """
        return self._pending_proposals.copy()

    def clear_proposals(self):
        """Clear pending proposals after authorization decision."""
        self._pending_proposals.clear()

    # --- Tool definitions for LLM ---

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get tool definitions for LLM function calling.

        Returns:
            List of tool definitions in OpenAI function format
        """
        return [
            {
                "name": "search_modules",
                "description": "Search for MSF modules matching criteria",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "mtype": {"type": "string", "description": "Module type filter"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "inspect_module",
                "description": "Get detailed information about a specific module",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mtype": {"type": "string", "description": "Module type"},
                        "path": {"type": "string", "description": "Module path"}
                    },
                    "required": ["mtype", "path"]
                }
            },
            {
                "name": "query_graph_stats",
                "description": "Get statistics about the current graph state",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "query_graph_nodes",
                "description": "Query nodes of a specific type from the graph",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "node_type": {"type": "string", "description": "Node type to query"},
                        "limit": {"type": "integer", "description": "Maximum nodes to return"}
                    },
                    "required": ["node_type"]
                }
            },
            {
                "name": "propose_execution",
                "description": "Propose a module execution for human approval. Does NOT execute.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "module_path": {"type": "string", "description": "Full module path"},
                        "options": {"type": "object", "description": "Module options"},
                        "reasoning": {"type": "string", "description": "Why this action is recommended"},
                        "risk_level": {"type": "string", "enum": ["low", "medium", "high", "critical"]}
                    },
                    "required": ["module_path", "options", "reasoning"]
                }
            }
        ]

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a tool by name.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool result

        Raises:
            ValueError: If tool not found
        """
        tool_map = {
            "search_modules": self.search_modules,
            "inspect_module": self.inspect_module,
            "query_graph_stats": self.query_graph_stats,
            "query_graph_nodes": self.query_graph_nodes,
            "get_findings": self.get_findings,
            "propose_execution": self.propose_execution
        }

        if name not in tool_map:
            raise ValueError(f"Unknown tool: {name}")

        return tool_map[name](**arguments)
