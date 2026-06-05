import pytest
import tempfile
import os
import json
from pathlib import Path


def test_database_creates_tables():
    from bigiron.core.db import Database

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)
        db.initialize()

        # Check tables exist
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [t[0] for t in tables]

        assert "nodes" in table_names
        assert "edges" in table_names
        assert "migrations" in table_names

        db.close()


def test_database_in_memory():
    from bigiron.core.db import Database

    db = Database(":memory:")
    db.initialize()

    tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    assert len(tables) >= 2

    db.close()


def test_insert_node():
    from bigiron.core.db import Database

    db = Database(":memory:")
    db.initialize()

    db.execute("""
        INSERT INTO nodes (id, node_type, label, properties, provenance)
        VALUES (?, ?, ?, ?, ?)
    """, ("node-1", "host", "192.168.1.1", '{"port": 23}', '{}'))
    db.commit()

    row = db.execute("SELECT * FROM nodes WHERE id = ?", ("node-1",)).fetchone()

    assert row["id"] == "node-1"
    assert row["node_type"] == "host"
    assert row["label"] == "192.168.1.1"
    assert json.loads(row["properties"])["port"] == 23

    db.close()


def test_insert_edge():
    from bigiron.core.db import Database

    db = Database(":memory:")
    db.initialize()

    # Create source and target nodes first
    db.execute("""
        INSERT INTO nodes (id, node_type, label) VALUES (?, ?, ?)
    """, ("src", "module_run", "Run-1"))
    db.execute("""
        INSERT INTO nodes (id, node_type, label) VALUES (?, ?, ?)
    """, ("tgt", "user", "HERC01"))

    # Create edge
    db.execute("""
        INSERT INTO edges (id, source_id, target_id, edge_type, properties, provenance)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ("edge-1", "src", "tgt", "discovered", '{"parser": "TSO"}', '{}'))
    db.commit()

    row = db.execute("SELECT * FROM edges WHERE id = ?", ("edge-1",)).fetchone()

    assert row["source_id"] == "src"
    assert row["target_id"] == "tgt"
    assert row["edge_type"] == "discovered"

    db.close()


def test_cascade_delete_edges():
    from bigiron.core.db import Database

    db = Database(":memory:")
    db.initialize()

    # Create nodes and edge
    db.execute("INSERT INTO nodes (id, node_type, label) VALUES (?, ?, ?)", ("a", "host", "A"))
    db.execute("INSERT INTO nodes (id, node_type, label) VALUES (?, ?, ?)", ("b", "user", "B"))
    db.execute("INSERT INTO edges (id, source_id, target_id, edge_type) VALUES (?, ?, ?, ?)",
               ("e1", "a", "b", "discovered"))
    db.commit()

    # Delete source node
    db.execute("DELETE FROM nodes WHERE id = ?", ("a",))
    db.commit()

    # Edge should be cascade deleted
    edge = db.execute("SELECT * FROM edges WHERE id = ?", ("e1",)).fetchone()
    assert edge is None

    db.close()
