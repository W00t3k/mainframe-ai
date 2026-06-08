"""Catalog service for MSF module discovery and import."""
from bigiron.msf.client import MsfClient
from bigiron.msf.models import ModuleSummary, ModuleDetail
from bigiron.msf.demo_data import DEMO_MODULES, get_demo_module_detail
from bigiron.core.graph import ProvenanceGraph
from bigiron.core.schema import Node, NodeType, Provenance


class CatalogService:
    """Service for discovering and importing MSF modules.

    In demo mode, uses built-in demo module data.
    In live mode, queries the MSF RPC for module information.
    """

    def __init__(self, client: MsfClient, graph: ProvenanceGraph):
        """Initialize the catalog service.

        Args:
            client: MsfClient instance (demo or live mode)
            graph: ProvenanceGraph for storing module nodes
        """
        self.client = client
        self.graph = graph

    def search(self, query: str, mtype: str | None = None) -> list[ModuleSummary]:
        """Search for modules matching the query.

        Args:
            query: Search query string
            mtype: Optional module type filter (auxiliary, exploit, etc.)

        Returns:
            List of matching ModuleSummary objects
        """
        if self.client.is_demo_mode:
            return self._search_demo(query, mtype)
        return self._search_live(query, mtype)

    def _search_demo(self, query: str, mtype: str | None = None) -> list[ModuleSummary]:
        """Search demo modules."""
        results = []
        query_lower = query.lower()

        for module in DEMO_MODULES:
            # Check if query matches path or name
            if query_lower in module.path.lower() or query_lower in module.name.lower():
                if mtype is None or module.mtype == mtype:
                    results.append(module)

        return results

    def _search_live(self, query: str, mtype: str | None = None) -> list[ModuleSummary]:
        """Search live MSF instance."""
        # Ensure connected
        if not self.client.is_connected:
            self.client.connect()

        results = []
        msf_results = self.client.client.modules.search(query)

        for item in msf_results:
            module_type = item.get("type", "")
            if mtype is None or module_type == mtype:
                results.append(ModuleSummary(
                    mtype=module_type,
                    path=item.get("fullname", "").replace(f"{module_type}/", "", 1),
                    name=item.get("name", ""),
                    rank=item.get("rank", "normal"),
                ))

        return results

    def get_module(self, mtype: str, path: str) -> ModuleDetail | None:
        """Get full details for a specific module.

        Args:
            mtype: Module type (auxiliary, exploit, etc.)
            path: Module path without type prefix

        Returns:
            ModuleDetail if found, None otherwise
        """
        if self.client.is_demo_mode:
            return get_demo_module_detail(mtype, path)
        return self._get_module_live(mtype, path)

    def _get_module_live(self, mtype: str, path: str) -> ModuleDetail | None:
        """Get module details from live MSF instance."""
        if not self.client.is_connected:
            self.client.connect()

        try:
            full_path = f"{mtype}/{path}"
            module = self.client.client.modules.use(mtype, path)
            info = module.info

            from bigiron.msf.models import ModuleOption

            options = []
            for name, opt_info in module.options.items():
                options.append(ModuleOption(
                    name=name,
                    required=opt_info.get("required", False),
                    description=opt_info.get("desc", ""),
                    default=opt_info.get("default"),
                    type=opt_info.get("type", "string"),
                ))

            return ModuleDetail(
                mtype=mtype,
                path=path,
                name=info.get("name", ""),
                rank=info.get("rank", "normal"),
                description=info.get("description", ""),
                authors=info.get("authors", []),
                references=info.get("references", []),
                options=options,
                targets=info.get("targets", []),
                platform=info.get("platform", ""),
            )
        except Exception:
            return None

    def sync_to_graph(self, query: str = "mainframe") -> int:
        """Import modules into the provenance graph as MSF_MODULE nodes.

        Args:
            query: Search query to find modules to import

        Returns:
            Number of modules imported
        """
        modules = self.search(query)
        count = 0

        for module in modules:
            # Check if module already exists
            existing = self.get_from_graph(module.full_path)
            if existing is not None:
                continue

            # Get full details if available
            detail = self.get_module(module.mtype, module.path)

            # Build properties
            properties = {
                "mtype": module.mtype,
                "path": module.path,
                "full_path": module.full_path,
                "rank": module.rank,
            }

            # Add detail properties if available
            if detail:
                properties["description"] = detail.description
                properties["authors"] = detail.authors
                properties["tk5_compatible"] = detail.tk5_compatible
                properties["requires_modern_zos"] = detail.requires_modern_zos
                properties["options"] = [opt.model_dump() for opt in detail.options]

            # Create node for this module
            node = Node(
                node_type=NodeType.MSF_MODULE,
                label=module.name,
                properties=properties,
                provenance=Provenance(simulated=self.client.is_demo_mode),
            )
            self.graph.add_node(node)
            count += 1

        return count

    def get_from_graph(self, full_path: str) -> Node | None:
        """Get a module node from the graph by full path.

        Args:
            full_path: Full module path (e.g., auxiliary/scanner/mainframe/ftp_jcl_creds)

        Returns:
            Node if found, None otherwise
        """
        for node in self.graph.get_nodes_by_type(NodeType.MSF_MODULE):
            if node.properties.get("full_path") == full_path:
                return node
        return None
