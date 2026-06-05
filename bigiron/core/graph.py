"""Provenance graph - the single source of truth."""
import json
from pathlib import Path
from typing import Iterator, Literal
from datetime import datetime, timezone
from collections import deque

from .db import Database
from .schema import Node, Edge, NodeType, EdgeType, Provenance


class ProvenanceGraph:
    """Main interface for the provenance graph.

    All components read and write through this class.
    The graph IS the engagement record.
    """

    def __init__(self, db_path: Path | str):
        """Initialize the provenance graph.

        Args:
            db_path: Path to SQLite database, or ":memory:" for in-memory
        """
        self.db = Database(db_path)
        self.db.initialize()

    def close(self):
        """Close database connection."""
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def add_node(self, node: Node) -> Node:
        """Add a node to the graph."""
        self.db.execute("""
            INSERT INTO nodes (id, node_type, label, properties, provenance, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            node.id,
            node.node_type.value,
            node.label,
            json.dumps(node.properties),
            node.provenance.model_dump_json(),
            node.created_at.isoformat(),
            node.updated_at.isoformat()
        ))
        self.db.commit()
        return node

    def get_node(self, node_id: str) -> Node | None:
        """Get a node by ID."""
        row = self.db.execute(
            "SELECT * FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()

        if row is None:
            return None

        return Node(
            id=row["id"],
            node_type=NodeType(row["node_type"]),
            label=row["label"],
            properties=json.loads(row["properties"]),
            provenance=Provenance.model_validate_json(row["provenance"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )

    def update_node(self, node: Node) -> Node:
        """Update an existing node."""
        node.updated_at = datetime.now(timezone.utc)

        self.db.execute("""
            UPDATE nodes
            SET label = ?, properties = ?, provenance = ?, updated_at = ?
            WHERE id = ?
        """, (
            node.label,
            json.dumps(node.properties),
            node.provenance.model_dump_json(),
            node.updated_at.isoformat(),
            node.id
        ))
        self.db.commit()
        return node

    def delete_node(self, node_id: str) -> bool:
        """Delete a node (and its connected edges via cascade)."""
        cursor = self.db.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
        self.db.commit()
        return cursor.rowcount > 0

    def add_edge(self, edge: Edge) -> Edge:
        """Add an edge between two nodes."""
        # Verify nodes exist
        if self.get_node(edge.source_id) is None:
            raise ValueError(f"Source node {edge.source_id} not found")
        if self.get_node(edge.target_id) is None:
            raise ValueError(f"Target node {edge.target_id} not found")

        self.db.execute("""
            INSERT INTO edges (id, source_id, target_id, edge_type, properties, provenance, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            edge.id,
            edge.source_id,
            edge.target_id,
            edge.edge_type.value,
            json.dumps(edge.properties),
            edge.provenance.model_dump_json(),
            edge.created_at.isoformat()
        ))
        self.db.commit()
        return edge

    def get_edge(self, edge_id: str) -> Edge | None:
        """Get an edge by ID."""
        row = self.db.execute(
            "SELECT * FROM edges WHERE id = ?", (edge_id,)
        ).fetchone()

        if row is None:
            return None

        return Edge(
            id=row["id"],
            source_id=row["source_id"],
            target_id=row["target_id"],
            edge_type=EdgeType(row["edge_type"]),
            properties=json.loads(row["properties"]),
            provenance=Provenance.model_validate_json(row["provenance"]),
            created_at=row["created_at"]
        )

    def get_edges_from(self, node_id: str, edge_type: EdgeType | None = None) -> Iterator[Edge]:
        """Get all outgoing edges from a node."""
        if edge_type:
            rows = self.db.execute(
                "SELECT * FROM edges WHERE source_id = ? AND edge_type = ?",
                (node_id, edge_type.value)
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT * FROM edges WHERE source_id = ?", (node_id,)
            ).fetchall()

        for row in rows:
            yield Edge(
                id=row["id"],
                source_id=row["source_id"],
                target_id=row["target_id"],
                edge_type=EdgeType(row["edge_type"]),
                properties=json.loads(row["properties"]),
                provenance=Provenance.model_validate_json(row["provenance"]),
                created_at=row["created_at"]
            )

    def get_edges_to(self, node_id: str, edge_type: EdgeType | None = None) -> Iterator[Edge]:
        """Get all incoming edges to a node."""
        if edge_type:
            rows = self.db.execute(
                "SELECT * FROM edges WHERE target_id = ? AND edge_type = ?",
                (node_id, edge_type.value)
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT * FROM edges WHERE target_id = ?", (node_id,)
            ).fetchall()

        for row in rows:
            yield Edge(
                id=row["id"],
                source_id=row["source_id"],
                target_id=row["target_id"],
                edge_type=EdgeType(row["edge_type"]),
                properties=json.loads(row["properties"]),
                provenance=Provenance.model_validate_json(row["provenance"]),
                created_at=row["created_at"]
            )

    def get_nodes_by_type(self, node_type: NodeType) -> Iterator[Node]:
        """Get all nodes of a specific type."""
        rows = self.db.execute(
            "SELECT * FROM nodes WHERE node_type = ?", (node_type.value,)
        ).fetchall()

        for row in rows:
            yield Node(
                id=row["id"],
                node_type=NodeType(row["node_type"]),
                label=row["label"],
                properties=json.loads(row["properties"]),
                provenance=Provenance.model_validate_json(row["provenance"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )

    def get_neighbors(
        self,
        node_id: str,
        direction: Literal["outgoing", "incoming", "both"] = "outgoing",
        edge_type: EdgeType | None = None
    ) -> Iterator[Node]:
        """Get neighboring nodes."""
        neighbor_ids = set()

        if direction in ("outgoing", "both"):
            for edge in self.get_edges_from(node_id, edge_type):
                neighbor_ids.add(edge.target_id)

        if direction in ("incoming", "both"):
            for edge in self.get_edges_to(node_id, edge_type):
                neighbor_ids.add(edge.source_id)

        for nid in neighbor_ids:
            node = self.get_node(nid)
            if node:
                yield node

    def find_paths(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 10
    ) -> Iterator[list[str]]:
        """Find all paths between two nodes using BFS."""
        if source_id == target_id:
            yield [source_id]
            return

        # BFS with path tracking
        queue: deque[list[str]] = deque([[source_id]])

        while queue:
            path = queue.popleft()

            if len(path) > max_depth:
                continue

            current = path[-1]

            for edge in self.get_edges_from(current):
                next_id = edge.target_id

                if next_id in path:  # Avoid cycles
                    continue

                new_path = path + [next_id]

                if next_id == target_id:
                    yield new_path
                else:
                    queue.append(new_path)

    def to_dict(self) -> dict:
        """Export the entire graph as a dictionary."""
        nodes = []
        for row in self.db.execute("SELECT * FROM nodes").fetchall():
            nodes.append({
                "id": row["id"],
                "node_type": row["node_type"],
                "label": row["label"],
                "properties": json.loads(row["properties"]),
                "provenance": json.loads(row["provenance"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            })

        edges = []
        for row in self.db.execute("SELECT * FROM edges").fetchall():
            edges.append({
                "id": row["id"],
                "source_id": row["source_id"],
                "target_id": row["target_id"],
                "edge_type": row["edge_type"],
                "properties": json.loads(row["properties"]),
                "provenance": json.loads(row["provenance"]),
                "created_at": row["created_at"]
            })

        return {"nodes": nodes, "edges": edges}

    def stats(self) -> dict:
        """Get graph statistics."""
        total_nodes = self.db.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        total_edges = self.db.execute("SELECT COUNT(*) FROM edges").fetchone()[0]

        nodes_by_type = {}
        for row in self.db.execute(
            "SELECT node_type, COUNT(*) as count FROM nodes GROUP BY node_type"
        ).fetchall():
            nodes_by_type[row["node_type"]] = row["count"]

        edges_by_type = {}
        for row in self.db.execute(
            "SELECT edge_type, COUNT(*) as count FROM edges GROUP BY edge_type"
        ).fetchall():
            edges_by_type[row["edge_type"]] = row["count"]

        return {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "nodes_by_type": nodes_by_type,
            "edges_by_type": edges_by_type
        }

    def search_nodes(self, query: str, node_type: NodeType | None = None) -> Iterator[Node]:
        """Search nodes by label (case-insensitive substring match)."""
        if node_type:
            rows = self.db.execute(
                "SELECT * FROM nodes WHERE label LIKE ? AND node_type = ?",
                (f"%{query}%", node_type.value)
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT * FROM nodes WHERE label LIKE ?",
                (f"%{query}%",)
            ).fetchall()

        for row in rows:
            yield Node(
                id=row["id"],
                node_type=NodeType(row["node_type"]),
                label=row["label"],
                properties=json.loads(row["properties"]),
                provenance=Provenance.model_validate_json(row["provenance"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )
