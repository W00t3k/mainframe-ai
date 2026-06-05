"""Provenance graph - the single source of truth."""
import json
from pathlib import Path
from typing import Iterator
from datetime import datetime, timezone

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
