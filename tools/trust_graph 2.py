#!/usr/bin/env python3
"""
Trust Graph - BloodHound-inspired trust relationship graph for mainframe assessment
Tracks panels, jobs, programs, datasets, transactions and their relationships
"""

import os
import json
import hashlib
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections import deque

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH_DIR = os.path.join(BASE_DIR, "data", "trust_graph_data")
GRAPH_FILE = os.path.join(GRAPH_DIR, "graph.json")
os.makedirs(GRAPH_DIR, exist_ok=True)


# =============================================================================
# Node Types
# =============================================================================

NODE_TYPES = {
    "EntryPoint": "VTAM APPLID / logon screen",
    "Panel": "ISPF/TSO panel",
    "CICSRegion": "CICS region",
    "Transaction": "CICS transaction ID",
    "Job": "Batch job",
    "Proc": "JCL procedure",
    "Program": "Executable module",
    "Dataset": "MVS dataset",
    "Loadlib": "Load library",
    "ReturnCode": "RC or ABEND code"
}

# =============================================================================
# Edge Types
# =============================================================================

EDGE_TYPES = {
    "NAVIGATES_TO": "Panel navigation (PF key / command)",
    "SUBMITS_JOB": "Interactive job submission path",
    "EXECUTES": "Job/Proc executes Program",
    "CALLS_PROC": "Job calls Proc",
    "READS": "Job reads Dataset",
    "WRITES": "Job writes Dataset",
    "LOADS_FROM": "Program loads from Loadlib",
    "INVOKES": "Transaction invokes Program",
    "RUNS_IN": "Transaction runs in CICSRegion",
    "RETURNED": "Job returned ReturnCode",
    "TRANSITIONS_TO": "EntryPoint transitions to Panel",
    "BOUNDARY_CROSS": "Crosses environment boundary"
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class GraphNode:
    """A node in the trust graph"""
    id: str
    node_type: str
    label: str
    properties: Dict[str, Any] = field(default_factory=dict)
    source_evidence: List[Dict] = field(default_factory=list)
    first_seen: str = ""
    last_seen: str = ""

    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.first_seen:
            self.first_seen = now
        self.last_seen = now

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "GraphNode":
        return cls(**data)


@dataclass
class GraphEdge:
    """An edge in the trust graph"""
    id: str
    edge_type: str
    source_id: str
    target_id: str
    properties: Dict[str, Any] = field(default_factory=dict)
    evidence: List[Dict] = field(default_factory=list)
    confidence: float = 1.0
    first_seen: str = ""
    last_seen: str = ""

    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.first_seen:
            self.first_seen = now
        self.last_seen = now

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "GraphEdge":
        return cls(**data)


# =============================================================================
# Trust Graph
# =============================================================================

class TrustGraph:
    """Main trust graph class with nodes, edges, queries, and persistence"""

    def __init__(self, auto_load: bool = True):
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: Dict[str, GraphEdge] = {}
        self._update_callbacks: List[Callable] = []

        if auto_load:
            self.load()

    # -------------------------------------------------------------------------
    # Update Callbacks (for real-time visualization)
    # -------------------------------------------------------------------------

    def add_update_callback(self, callback: Callable):
        """Add a callback that's called on every graph update.

        Callback signature: callback(event_type: str, data: dict)
        event_type: "node_added", "node_updated", "edge_added", "edge_updated"
        """
        self._update_callbacks.append(callback)

    def remove_update_callback(self, callback: Callable):
        """Remove an update callback."""
        if callback in self._update_callbacks:
            self._update_callbacks.remove(callback)

    def _notify_update(self, event_type: str, data: dict):
        """Notify all callbacks of an update."""
        for callback in self._update_callbacks:
            try:
                callback(event_type, data)
            except Exception as e:
                print(f"Graph callback error: {e}")

    # -------------------------------------------------------------------------
    # Node Operations
    # -------------------------------------------------------------------------

    @staticmethod
    def make_node_id(node_type: str, label: str) -> str:
        """Generate deterministic node ID from type and label."""
        key = f"{node_type}:{label}"
        return hashlib.md5(key.encode()).hexdigest()[:12]

    def add_node(self, node_type: str, label: str,
                 properties: Dict = None, evidence: Dict = None) -> str:
        """Add or update a node in the graph.

        Args:
            node_type: One of NODE_TYPES keys
            label: Human-readable label (e.g., dataset name, panel ID)
            properties: Type-specific properties
            evidence: Evidence dict {screen_hash, timestamp, raw_text, etc.}

        Returns:
            Node ID
        """
        node_id = self.make_node_id(node_type, label)
        properties = properties or {}
        evidence_list = [evidence] if evidence else []

        if node_id in self.nodes:
            # Update existing node
            node = self.nodes[node_id]
            node.properties.update(properties)
            if evidence:
                node.source_evidence.append(evidence)
            node.last_seen = datetime.now().isoformat()
            self._notify_update("node_updated", node.to_dict())
        else:
            # Create new node
            node = GraphNode(
                id=node_id,
                node_type=node_type,
                label=label,
                properties=properties,
                source_evidence=evidence_list
            )
            self.nodes[node_id] = node
            self._notify_update("node_added", node.to_dict())

        return node_id

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by ID."""
        return self.nodes.get(node_id)

    def get_nodes_by_type(self, node_type: str) -> List[GraphNode]:
        """Get all nodes of a given type."""
        return [n for n in self.nodes.values() if n.node_type == node_type]

    def find_node(self, node_type: str, label: str) -> Optional[GraphNode]:
        """Find a node by type and label."""
        node_id = self.make_node_id(node_type, label)
        return self.nodes.get(node_id)

    # -------------------------------------------------------------------------
    # Edge Operations
    # -------------------------------------------------------------------------

    @staticmethod
    def make_edge_id(edge_type: str, source_id: str, target_id: str) -> str:
        """Generate deterministic edge ID."""
        key = f"{edge_type}:{source_id}->{target_id}"
        return hashlib.md5(key.encode()).hexdigest()[:12]

    def add_edge(self, edge_type: str, source_id: str, target_id: str,
                 properties: Dict = None, evidence: Dict = None,
                 confidence: float = 1.0) -> str:
        """Add or update an edge in the graph.

        Args:
            edge_type: One of EDGE_TYPES keys
            source_id: Source node ID
            target_id: Target node ID
            properties: Edge-specific properties (e.g., pf_key, command)
            evidence: Evidence dict
            confidence: Confidence score 0.0-1.0

        Returns:
            Edge ID
        """
        edge_id = self.make_edge_id(edge_type, source_id, target_id)
        properties = properties or {}
        evidence_list = [evidence] if evidence else []

        if edge_id in self.edges:
            # Update existing edge
            edge = self.edges[edge_id]
            edge.properties.update(properties)
            if evidence:
                edge.evidence.append(evidence)
            edge.confidence = max(edge.confidence, confidence)
            edge.last_seen = datetime.now().isoformat()
            self._notify_update("edge_updated", edge.to_dict())
        else:
            # Create new edge
            edge = GraphEdge(
                id=edge_id,
                edge_type=edge_type,
                source_id=source_id,
                target_id=target_id,
                properties=properties,
                evidence=evidence_list,
                confidence=confidence
            )
            self.edges[edge_id] = edge
            self._notify_update("edge_added", edge.to_dict())

        return edge_id

    def get_edge(self, edge_id: str) -> Optional[GraphEdge]:
        """Get an edge by ID."""
        return self.edges.get(edge_id)

    def get_edges_by_type(self, edge_type: str) -> List[GraphEdge]:
        """Get all edges of a given type."""
        return [e for e in self.edges.values() if e.edge_type == edge_type]

    # -------------------------------------------------------------------------
    # Graph Traversal
    # -------------------------------------------------------------------------

    def get_neighbors(self, node_id: str,
                      edge_types: List[str] = None,
                      direction: str = "both") -> List[Dict]:
        """Get neighboring nodes.

        Args:
            node_id: Starting node ID
            edge_types: Filter by edge types (None = all)
            direction: "outgoing", "incoming", or "both"

        Returns:
            List of {node: GraphNode, edge: GraphEdge, direction: str}
        """
        neighbors = []

        for edge in self.edges.values():
            if edge_types and edge.edge_type not in edge_types:
                continue

            if direction in ("outgoing", "both") and edge.source_id == node_id:
                target = self.nodes.get(edge.target_id)
                if target:
                    neighbors.append({
                        "node": target,
                        "edge": edge,
                        "direction": "outgoing"
                    })

            if direction in ("incoming", "both") and edge.target_id == node_id:
                source = self.nodes.get(edge.source_id)
                if source:
                    neighbors.append({
                        "node": source,
                        "edge": edge,
                        "direction": "incoming"
                    })

        return neighbors

    def find_paths(self, from_id: str, to_id: str,
                   max_depth: int = 6) -> List[List[str]]:
        """Find all paths between two nodes using BFS.

        Args:
            from_id: Starting node ID
            to_id: Target node ID
            max_depth: Maximum path length

        Returns:
            List of paths, each path is a list of node IDs
        """
        if from_id not in self.nodes or to_id not in self.nodes:
            return []

        paths = []
        queue = deque([(from_id, [from_id])])
        visited_paths = set()

        while queue:
            current_id, path = queue.popleft()

            if len(path) > max_depth:
                continue

            if current_id == to_id and len(path) > 1:
                path_key = tuple(path)
                if path_key not in visited_paths:
                    paths.append(path)
                    visited_paths.add(path_key)
                continue

            for neighbor in self.get_neighbors(current_id, direction="outgoing"):
                next_id = neighbor["node"].id
                if next_id not in path:  # Avoid cycles
                    queue.append((next_id, path + [next_id]))

        return paths

    def get_subgraph(self, node_type: str = None,
                     edge_type: str = None) -> Dict:
        """Get a filtered subgraph.

        Args:
            node_type: Filter nodes by type (None = all)
            edge_type: Filter edges by type (None = all)

        Returns:
            Dict with "nodes" and "edges" lists
        """
        nodes = self.nodes.values()
        edges = self.edges.values()

        if node_type:
            nodes = [n for n in nodes if n.node_type == node_type]
            node_ids = {n.id for n in nodes}
            edges = [e for e in edges
                     if e.source_id in node_ids and e.target_id in node_ids]

        if edge_type:
            edges = [e for e in edges if e.edge_type == edge_type]

        return {
            "nodes": [n.to_dict() for n in nodes],
            "edges": [e.to_dict() for e in edges]
        }

    # -------------------------------------------------------------------------
    # Named Queries (10 queries from the plan)
    # -------------------------------------------------------------------------

    def query(self, query_name: str, **params) -> Dict:
        """Run a named query.

        Available queries:
        - paths_to_job_submit
        - library_load_chain
        - shared_datasets
        - reachable_transactions
        - multi_library_programs
        - edit_browse_panels
        - dataset_conflicts
        - boundary_crossings
        - abend_chains
        - shortest_to_sensitive
        - loadlib_hotspots
        - dataset_fanout
        - job_program_chain
        - orphan_datasets
        - boundary_summary
        """
        queries = {
            "paths_to_job_submit": self._query_paths_to_job_submit,
            "library_load_chain": self._query_library_load_chain,
            "shared_datasets": self._query_shared_datasets,
            "reachable_transactions": self._query_reachable_transactions,
            "multi_library_programs": self._query_multi_library_programs,
            "edit_browse_panels": self._query_edit_browse_panels,
            "dataset_conflicts": self._query_dataset_conflicts,
            "boundary_crossings": self._query_boundary_crossings,
            "abend_chains": self._query_abend_chains,
            "shortest_to_sensitive": self._query_shortest_to_sensitive,
            "loadlib_hotspots": self._query_loadlib_hotspots,
            "dataset_fanout": self._query_dataset_fanout,
            "job_program_chain": self._query_job_program_chain,
            "orphan_datasets": self._query_orphan_datasets,
            "boundary_summary": self._query_boundary_summary,
        }

        if query_name not in queries:
            return {"error": f"Unknown query: {query_name}", "results": []}

        results = queries[query_name](**params)
        return {"query": query_name, "results": results, "count": len(results)}

    def _query_paths_to_job_submit(self, **params) -> List[Dict]:
        """Q1: Which interactive paths lead to job submission?"""
        paths = []
        entry_points = self.get_nodes_by_type("EntryPoint")

        for entry in entry_points:
            # Find all SUBMITS_JOB edges
            for edge in self.get_edges_by_type("SUBMITS_JOB"):
                source_panel = self.nodes.get(edge.source_id)
                job_node = self.nodes.get(edge.target_id)
                if source_panel and job_node:
                    # Find path from entry to the panel
                    panel_paths = self.find_paths(entry.id, source_panel.id, max_depth=8)
                    for path in panel_paths:
                        paths.append({
                            "entry": entry.label,
                            "path": [self.nodes[nid].label for nid in path],
                            "job": job_node.label
                        })
        return paths

    def _query_library_load_chain(self, **params) -> List[Dict]:
        """Q2: Which jobs load programs from which libraries?"""
        chains = []
        for job in self.get_nodes_by_type("Job"):
            for exec_neighbor in self.get_neighbors(job.id, ["EXECUTES"], "outgoing"):
                program = exec_neighbor["node"]
                for load_neighbor in self.get_neighbors(program.id, ["LOADS_FROM"], "outgoing"):
                    loadlib = load_neighbor["node"]
                    chains.append({
                        "job": job.label,
                        "program": program.label,
                        "loadlib": loadlib.label
                    })
        return chains

    def _query_shared_datasets(self, **params) -> List[Dict]:
        """Q3: Which datasets appear in sensitive execution chains?"""
        dataset_usage = {}

        for dataset in self.get_nodes_by_type("Dataset"):
            reads = []
            writes = []
            for neighbor in self.get_neighbors(dataset.id, ["READS"], "incoming"):
                reads.append(neighbor["node"].label)
            for neighbor in self.get_neighbors(dataset.id, ["WRITES"], "incoming"):
                writes.append(neighbor["node"].label)

            if reads or writes:
                dataset_usage[dataset.label] = {
                    "dataset": dataset.label,
                    "readers": reads,
                    "writers": writes,
                    "shared": len(reads) > 0 and len(writes) > 0
                }

        return [v for v in dataset_usage.values() if v["shared"]]

    def _query_reachable_transactions(self, **params) -> List[Dict]:
        """Q4: What are the reachable CICS transactions from logon?"""
        results = []
        entry_points = self.get_nodes_by_type("EntryPoint")
        transactions = self.get_nodes_by_type("Transaction")

        for entry in entry_points:
            for trans in transactions:
                paths = self.find_paths(entry.id, trans.id, max_depth=10)
                if paths:
                    results.append({
                        "entry": entry.label,
                        "transaction": trans.label,
                        "depth": min(len(p) for p in paths),
                        "path_count": len(paths)
                    })
        return results

    def _query_multi_library_programs(self, **params) -> List[Dict]:
        """Q5: Which programs are loaded from multiple libraries?"""
        results = []
        for program in self.get_nodes_by_type("Program"):
            loadlibs = []
            for neighbor in self.get_neighbors(program.id, ["LOADS_FROM"], "outgoing"):
                loadlibs.append(neighbor["node"].label)
            if len(loadlibs) > 1:
                results.append({
                    "program": program.label,
                    "loadlibs": loadlibs,
                    "count": len(loadlibs)
                })
        return results

    def _query_edit_browse_panels(self, **params) -> List[Dict]:
        """Q6: What panels expose dataset browsing/editing capabilities?"""
        results = []
        sensitive_types = {"ISPF_EDIT", "ISPF_BROWSE", "ISPF_DSLIST", "ISPF_UTILITIES"}

        for panel in self.get_nodes_by_type("Panel"):
            panel_type = panel.properties.get("panel_type", "")
            if panel_type in sensitive_types:
                results.append({
                    "panel": panel.label,
                    "panel_type": panel_type,
                    "title": panel.properties.get("title", "")
                })
        return results

    def _query_dataset_conflicts(self, **params) -> List[Dict]:
        """Q7: Which batch chains share datasets (read-write conflicts)?"""
        conflicts = []
        shared = self._query_shared_datasets()

        for ds in shared:
            for reader in ds["readers"]:
                for writer in ds["writers"]:
                    if reader != writer:
                        conflicts.append({
                            "dataset": ds["dataset"],
                            "reader": reader,
                            "writer": writer
                        })
        return conflicts

    def _query_boundary_crossings(self, **params) -> List[Dict]:
        """Q8: What are the boundary transitions?"""
        results = []
        for edge in self.get_edges_by_type("BOUNDARY_CROSS"):
            source = self.nodes.get(edge.source_id)
            target = self.nodes.get(edge.target_id)
            if source and target:
                results.append({
                    "source": source.label,
                    "source_type": source.node_type,
                    "target": target.label,
                    "target_type": target.node_type,
                    "properties": edge.properties
                })
        return results

    def _query_abend_chains(self, **params) -> List[Dict]:
        """Q9: Which execution chains have ABENDed?"""
        results = []
        for rc in self.get_nodes_by_type("ReturnCode"):
            if rc.properties.get("type") == "ABEND":
                for neighbor in self.get_neighbors(rc.id, ["RETURNED"], "incoming"):
                    job = neighbor["node"]
                    results.append({
                        "job": job.label,
                        "abend_code": rc.label,
                        "step": rc.properties.get("step", "")
                    })
        return results

    def _query_shortest_to_sensitive(self, **params) -> List[Dict]:
        """Q10: What is the shortest path from entry to sensitive ops?"""
        results = []
        entry_points = self.get_nodes_by_type("EntryPoint")

        # Sensitive targets: job submit panels, CICS admin transactions
        sensitive_targets = []
        for edge in self.get_edges_by_type("SUBMITS_JOB"):
            sensitive_targets.append(self.nodes.get(edge.source_id))
        for trans in self.get_nodes_by_type("Transaction"):
            if trans.label in ("CEMT", "CEDA", "CECI", "CESN"):
                sensitive_targets.append(trans)

        for entry in entry_points:
            for target in sensitive_targets:
                if target:
                    paths = self.find_paths(entry.id, target.id, max_depth=10)
                    if paths:
                        shortest = min(paths, key=len)
                        results.append({
                            "entry": entry.label,
                            "target": target.label,
                            "target_type": target.node_type,
                            "hops": len(shortest) - 1,
                            "path": [self.nodes[nid].label for nid in shortest]
                        })

        # Sort by hop count
        results.sort(key=lambda x: x["hops"])
        return results

    def _query_loadlib_hotspots(self, **params) -> List[Dict]:
        """Which loadlibs are used by the most programs?"""
        loadlib_programs = {}
        for edge in self.get_edges_by_type("LOADS_FROM"):
            program = self.nodes.get(edge.source_id)
            loadlib = self.nodes.get(edge.target_id)
            if not program or not loadlib:
                continue
            loadlib_programs.setdefault(loadlib.id, set()).add(program.label)

        results = []
        for loadlib_id, programs in loadlib_programs.items():
            loadlib = self.nodes.get(loadlib_id)
            if not loadlib:
                continue
            results.append({
                "loadlib": loadlib.label,
                "program_count": len(programs),
                "programs": sorted(programs)
            })
        results.sort(key=lambda x: x["program_count"], reverse=True)
        return results

    def _query_dataset_fanout(self, **params) -> List[Dict]:
        """Which datasets are accessed by the most jobs?"""
        access_map = {}
        for edge in self.edges.values():
            if edge.edge_type not in ("READS", "WRITES"):
                continue
            job = self.nodes.get(edge.source_id)
            dataset = self.nodes.get(edge.target_id)
            if not job or not dataset:
                continue
            access = access_map.setdefault(dataset.id, {"readers": set(), "writers": set()})
            if edge.edge_type == "READS":
                access["readers"].add(job.label)
            else:
                access["writers"].add(job.label)

        results = []
        for dataset_id, access in access_map.items():
            dataset = self.nodes.get(dataset_id)
            if not dataset:
                continue
            results.append({
                "dataset": dataset.label,
                "readers": sorted(access["readers"]),
                "writers": sorted(access["writers"]),
                "total_jobs": len(access["readers"] | access["writers"])
            })
        results.sort(key=lambda x: x["total_jobs"], reverse=True)
        return results

    def _query_job_program_chain(self, **params) -> List[Dict]:
        """Summarize job -> program -> loadlib chains."""
        results = []
        for job in self.get_nodes_by_type("Job"):
            programs = []
            loadlibs = set()
            for neighbor in self.get_neighbors(job.id, ["EXECUTES"], "outgoing"):
                program = neighbor["node"]
                programs.append(program.label)
                for lib_neighbor in self.get_neighbors(program.id, ["LOADS_FROM"], "outgoing"):
                    loadlibs.add(lib_neighbor["node"].label)
            results.append({
                "job": job.label,
                "programs": sorted(set(programs)),
                "program_count": len(set(programs)),
                "loadlibs": sorted(loadlibs),
                "loadlib_count": len(loadlibs)
            })
        results.sort(key=lambda x: x["program_count"], reverse=True)
        return results

    def _query_orphan_datasets(self, **params) -> List[Dict]:
        """Datasets with no READS/WRITES edges."""
        dataset_ids = {n.id for n in self.get_nodes_by_type("Dataset")}
        attached = set()
        for edge in self.edges.values():
            if edge.edge_type in ("READS", "WRITES") and edge.target_id in dataset_ids:
                attached.add(edge.target_id)
        results = []
        for dataset_id in dataset_ids - attached:
            dataset = self.nodes.get(dataset_id)
            if dataset:
                results.append({"dataset": dataset.label})
        return results

    def _query_boundary_summary(self, **params) -> List[Dict]:
        """Summarize edges that cross node type boundaries."""
        summary = {}
        boundary_types = {"NAVIGATES_TO", "SUBMITS_JOB", "EXECUTES", "CALLS_PROC", "READS", "WRITES", "LOADS_FROM"}
        for edge in self.edges.values():
            if edge.edge_type not in boundary_types:
                continue
            source = self.nodes.get(edge.source_id)
            target = self.nodes.get(edge.target_id)
            if not source or not target:
                continue
            if source.node_type == target.node_type:
                continue
            key = (edge.edge_type, source.node_type, target.node_type)
            summary[key] = summary.get(key, 0) + 1

        results = []
        for (edge_type, source_type, target_type), count in summary.items():
            results.append({
                "edge": edge_type,
                "source_type": source_type,
                "target_type": target_type,
                "count": count
            })
        results.sort(key=lambda x: x["count"], reverse=True)
        return results

    # -------------------------------------------------------------------------
    # Export
    # -------------------------------------------------------------------------

    def export_json(self) -> Dict:
        """Export graph to JSON-serializable dict."""
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
            "metadata": {
                "node_count": len(self.nodes),
                "edge_count": len(self.edges),
                "exported_at": datetime.now().isoformat()
            }
        }

    def export_dot(self) -> str:
        """Export graph to Graphviz DOT format for visualization."""
        lines = ["digraph TrustGraph {"]
        lines.append("  rankdir=LR;")
        lines.append("  node [shape=box];")
        lines.append("")

        # Node colors by type
        colors = {
            "EntryPoint": "green",
            "Panel": "lightblue",
            "CICSRegion": "orange",
            "Transaction": "yellow",
            "Job": "pink",
            "Proc": "lightpink",
            "Program": "lightgray",
            "Dataset": "wheat",
            "Loadlib": "tan",
            "ReturnCode": "red"
        }

        # Nodes
        for node in self.nodes.values():
            color = colors.get(node.node_type, "white")
            label = f"{node.node_type}\\n{node.label}"
            lines.append(f'  "{node.id}" [label="{label}" fillcolor="{color}" style="filled"];')

        lines.append("")

        # Edges
        for edge in self.edges.values():
            lines.append(f'  "{edge.source_id}" -> "{edge.target_id}" [label="{edge.edge_type}"];')

        lines.append("}")
        return "\n".join(lines)

    def export_d3_json(self) -> Dict:
        """Export graph in D3.js force-directed format for real-time visualization."""
        nodes = []
        for n in self.nodes.values():
            nodes.append({
                "id": n.id,
                "label": n.label,
                "type": n.node_type,
                "properties": n.properties
            })

        links = []
        for e in self.edges.values():
            links.append({
                "id": e.id,
                "source": e.source_id,
                "target": e.target_id,
                "type": e.edge_type,
                "confidence": e.confidence
            })

        return {"nodes": nodes, "links": links}

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def save(self, path: str = None):
        """Save graph to JSON file."""
        path = path or GRAPH_FILE
        data = {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()]
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, path: str = None):
        """Load graph from JSON file."""
        path = path or GRAPH_FILE
        if not os.path.exists(path):
            return

        try:
            with open(path, "r") as f:
                data = json.load(f)

            for node_data in data.get("nodes", []):
                node = GraphNode.from_dict(node_data)
                self.nodes[node.id] = node

            for edge_data in data.get("edges", []):
                edge = GraphEdge.from_dict(edge_data)
                self.edges[edge.id] = edge

        except Exception as e:
            print(f"Error loading graph: {e}")

    def clear(self):
        """Clear the graph."""
        self.nodes.clear()
        self.edges.clear()

    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------

    def get_stats(self) -> Dict:
        """Get graph statistics."""
        node_types = {}
        for node in self.nodes.values():
            node_types[node.node_type] = node_types.get(node.node_type, 0) + 1

        edge_types = {}
        for edge in self.edges.values():
            edge_types[edge.edge_type] = edge_types.get(edge.edge_type, 0) + 1

        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "node_types": node_types,
            "edge_types": edge_types
        }


# =============================================================================
# Global Graph Instance
# =============================================================================

_trust_graph: Optional[TrustGraph] = None


def get_trust_graph() -> TrustGraph:
    """Get or create the global trust graph instance."""
    global _trust_graph
    if _trust_graph is None:
        _trust_graph = TrustGraph()
    return _trust_graph
