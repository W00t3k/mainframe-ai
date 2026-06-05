# Provenance Graph Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the SQLite-backed provenance graph that serves as the single source of truth for all entities, executions, and findings.

**Architecture:** A graph database implemented on SQLite with nodes (typed entities) and edges (typed relationships with provenance metadata). All components read/write through this layer. The existing `trust_graph.py` provides concepts to build on, but this is a ground-up rewrite with SQLite persistence, proper typing, and provenance tracking.

**Tech Stack:** Python 3.11+, SQLite (via sqlite3), Pydantic v2 for models, pytest for testing

---

## File Structure

```
bigiron/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── schema.py          # Pydantic models for nodes, edges, provenance
│   ├── graph.py           # ProvenanceGraph class - main interface
│   ├── db.py              # SQLite connection, migrations, queries
│   └── queries.py         # Graph traversal queries (paths, neighbors)
└── tests/
    └── core/
        ├── __init__.py
        ├── test_schema.py
        ├── test_db.py
        ├── test_graph.py
        └── test_queries.py
```

---

## Task 1: Project Structure and Schema Models

**Files:**
- Create: `bigiron/__init__.py`
- Create: `bigiron/core/__init__.py`
- Create: `bigiron/core/schema.py`
- Create: `bigiron/tests/__init__.py`
- Create: `bigiron/tests/core/__init__.py`
- Create: `bigiron/tests/core/test_schema.py`

- [ ] **Step 1: Create package structure**

```bash
mkdir -p bigiron/core bigiron/tests/core
touch bigiron/__init__.py bigiron/core/__init__.py
touch bigiron/tests/__init__.py bigiron/tests/core/__init__.py
```

- [ ] **Step 2: Write failing test for NodeType enum**

```python
# bigiron/tests/core/test_schema.py
import pytest
from bigiron.core.schema import NodeType


def test_node_type_has_target_types():
    assert NodeType.HOST.value == "host"
    assert NodeType.SERVICE.value == "service"
    assert NodeType.CREDENTIAL.value == "credential"


def test_node_type_has_mainframe_types():
    assert NodeType.USER.value == "user"
    assert NodeType.DATASET.value == "dataset"
    assert NodeType.JOB.value == "job"
    assert NodeType.TRANSACTION.value == "transaction"
    assert NodeType.PROGRAM.value == "program"


def test_node_type_has_module_types():
    assert NodeType.MSF_MODULE.value == "msf_module"
    assert NodeType.CUSTOM_MODULE.value == "custom_module"
    assert NodeType.RECON_TOOL.value == "recon_tool"


def test_node_type_has_execution_types():
    assert NodeType.MODULE_RUN.value == "module_run"
    assert NodeType.CHECKPOINT.value == "checkpoint"
    assert NodeType.AUTHORIZATION.value == "authorization"


def test_node_type_has_finding_types():
    assert NodeType.VULNERABILITY.value == "vulnerability"
    assert NodeType.MISCONFIGURATION.value == "misconfiguration"
    assert NodeType.ACCESS_PATH.value == "access_path"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_schema.py::test_node_type_has_target_types -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'bigiron.core.schema'"

- [ ] **Step 4: Implement NodeType enum**

```python
# bigiron/core/schema.py
"""Pydantic models for the provenance graph schema."""
from enum import Enum
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """Types of nodes in the provenance graph."""
    # Target types
    HOST = "host"
    SERVICE = "service"
    CREDENTIAL = "credential"

    # Mainframe entity types
    USER = "user"
    DATASET = "dataset"
    JOB = "job"
    TRANSACTION = "transaction"
    PROGRAM = "program"
    LOADLIB = "loadlib"
    CICS_REGION = "cics_region"
    PANEL = "panel"

    # Module types
    MSF_MODULE = "msf_module"
    CUSTOM_MODULE = "custom_module"
    RECON_TOOL = "recon_tool"

    # Execution types
    MODULE_RUN = "module_run"
    CHECKPOINT = "checkpoint"
    AUTHORIZATION = "authorization"
    AGENT_TURN = "agent_turn"
    ENGAGEMENT = "engagement"

    # Finding types
    VULNERABILITY = "vulnerability"
    MISCONFIGURATION = "misconfiguration"
    ACCESS_PATH = "access_path"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_schema.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Write failing test for EdgeType enum**

```python
# bigiron/tests/core/test_schema.py (append)


def test_edge_type_has_execution_edges():
    from bigiron.core.schema import EdgeType
    assert EdgeType.TARGETS.value == "targets"
    assert EdgeType.DISCOVERED.value == "discovered"
    assert EdgeType.AUTHORIZED_BY.value == "authorized_by"


def test_edge_type_has_relationship_edges():
    from bigiron.core.schema import EdgeType
    assert EdgeType.GRANTED_ACCESS.value == "granted_access"
    assert EdgeType.ATTACK_PATH.value == "attack_path"
    assert EdgeType.MAPS_TO.value == "maps_to"
    assert EdgeType.PART_OF.value == "part_of"
```

- [ ] **Step 7: Run test to verify it fails**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_schema.py::test_edge_type_has_execution_edges -v`
Expected: FAIL with "cannot import name 'EdgeType'"

- [ ] **Step 8: Implement EdgeType enum**

```python
# bigiron/core/schema.py (append after NodeType)


class EdgeType(str, Enum):
    """Types of edges in the provenance graph."""
    # Execution edges
    TARGETS = "targets"
    DISCOVERED = "discovered"
    AUTHORIZED_BY = "authorized_by"
    CHECKPOINT_AT = "checkpoint_at"

    # Relationship edges
    GRANTED_ACCESS = "granted_access"
    ATTACK_PATH = "attack_path"
    MAPS_TO = "maps_to"
    PART_OF = "part_of"

    # Navigation edges (from existing trust graph)
    NAVIGATES_TO = "navigates_to"
    SUBMITS_JOB = "submits_job"
    EXECUTES = "executes"
    CALLS_PROC = "calls_proc"
    READS = "reads"
    WRITES = "writes"
    LOADS_FROM = "loads_from"
    INVOKES = "invokes"
    RUNS_IN = "runs_in"
    BOUNDARY_CROSS = "boundary_cross"
```

- [ ] **Step 9: Run all schema tests**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_schema.py -v`
Expected: All 7 tests PASS

- [ ] **Step 10: Commit**

```bash
git add bigiron/
git commit -m "feat(graph): add NodeType and EdgeType enums

Define all node and edge types for the provenance graph schema.
Includes target, mainframe entity, module, execution, and finding types."
```

---

## Task 2: Node and Edge Pydantic Models

**Files:**
- Modify: `bigiron/core/schema.py`
- Modify: `bigiron/tests/core/test_schema.py`

- [ ] **Step 1: Write failing test for Provenance model**

```python
# bigiron/tests/core/test_schema.py (append)
from datetime import datetime, timezone


def test_provenance_model_creation():
    from bigiron.core.schema import Provenance

    prov = Provenance(
        timestamp=datetime(2026, 6, 5, 14, 23, 1, tzinfo=timezone.utc),
        authorization_ref="ENG-2026-0042",
        agent_turn=7,
        raw_output="[+] Job submitted",
        simulated=False
    )

    assert prov.authorization_ref == "ENG-2026-0042"
    assert prov.agent_turn == 7
    assert prov.simulated is False


def test_provenance_defaults():
    from bigiron.core.schema import Provenance

    prov = Provenance()

    assert prov.timestamp is not None
    assert prov.authorization_ref is None
    assert prov.agent_turn is None
    assert prov.raw_output is None
    assert prov.simulated is False
    assert prov.recording_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_schema.py::test_provenance_model_creation -v`
Expected: FAIL with "cannot import name 'Provenance'"

- [ ] **Step 3: Implement Provenance model**

```python
# bigiron/core/schema.py (append after EdgeType)


class Provenance(BaseModel):
    """Provenance metadata attached to nodes and edges."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    authorization_ref: str | None = None
    agent_turn: int | None = None
    raw_output: str | None = None
    parsed_entities: list[str] = Field(default_factory=list)
    simulated: bool = False
    recording_id: str | None = None
```

Add import at top of file:
```python
from datetime import datetime, timezone
```

- [ ] **Step 4: Run Provenance tests**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_schema.py -k provenance -v`
Expected: 2 tests PASS

- [ ] **Step 5: Write failing test for Node model**

```python
# bigiron/tests/core/test_schema.py (append)


def test_node_model_creation():
    from bigiron.core.schema import Node, NodeType

    node = Node(
        id="host-192.168.1.100",
        node_type=NodeType.HOST,
        label="192.168.1.100",
        properties={"ip": "192.168.1.100", "port": 23}
    )

    assert node.id == "host-192.168.1.100"
    assert node.node_type == NodeType.HOST
    assert node.label == "192.168.1.100"
    assert node.properties["port"] == 23


def test_node_auto_generates_id():
    from bigiron.core.schema import Node, NodeType

    node = Node(
        node_type=NodeType.USER,
        label="HERC01"
    )

    assert node.id is not None
    assert len(node.id) > 0


def test_node_has_provenance():
    from bigiron.core.schema import Node, NodeType, Provenance

    node = Node(
        node_type=NodeType.JOB,
        label="JOB12345",
        provenance=Provenance(authorization_ref="ENG-001")
    )

    assert node.provenance.authorization_ref == "ENG-001"
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_schema.py::test_node_model_creation -v`
Expected: FAIL with "cannot import name 'Node'"

- [ ] **Step 7: Implement Node model**

```python
# bigiron/core/schema.py (append after Provenance)
import uuid


class Node(BaseModel):
    """A node in the provenance graph."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    node_type: NodeType
    label: str
    properties: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance = Field(default_factory=Provenance)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

Add import at top:
```python
import uuid
```

- [ ] **Step 8: Run Node tests**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_schema.py -k node -v`
Expected: 3 tests PASS

- [ ] **Step 9: Write failing test for Edge model**

```python
# bigiron/tests/core/test_schema.py (append)


def test_edge_model_creation():
    from bigiron.core.schema import Edge, EdgeType

    edge = Edge(
        source_id="run-001",
        target_id="user-HERC01",
        edge_type=EdgeType.DISCOVERED,
        properties={"parser": "TSOEnumParser"}
    )

    assert edge.source_id == "run-001"
    assert edge.target_id == "user-HERC01"
    assert edge.edge_type == EdgeType.DISCOVERED


def test_edge_has_provenance():
    from bigiron.core.schema import Edge, EdgeType, Provenance

    edge = Edge(
        source_id="a",
        target_id="b",
        edge_type=EdgeType.ATTACK_PATH,
        provenance=Provenance(agent_turn=3)
    )

    assert edge.provenance.agent_turn == 3
```

- [ ] **Step 10: Implement Edge model**

```python
# bigiron/core/schema.py (append after Node)


class Edge(BaseModel):
    """An edge in the provenance graph."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str
    target_id: str
    edge_type: EdgeType
    properties: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance = Field(default_factory=Provenance)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 11: Run all schema tests**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_schema.py -v`
Expected: All 12 tests PASS

- [ ] **Step 12: Commit**

```bash
git add bigiron/core/schema.py bigiron/tests/core/test_schema.py
git commit -m "feat(graph): add Provenance, Node, and Edge models

Pydantic models with full provenance tracking:
- Provenance: timestamp, authorization_ref, agent_turn, raw_output
- Node: typed with properties and provenance
- Edge: connects nodes with typed relationships"
```

---

## Task 3: SQLite Database Layer

**Files:**
- Create: `bigiron/core/db.py`
- Create: `bigiron/tests/core/test_db.py`

- [ ] **Step 1: Write failing test for database initialization**

```python
# bigiron/tests/core/test_db.py
import pytest
import tempfile
import os
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_db.py::test_database_creates_tables -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'bigiron.core.db'"

- [ ] **Step 3: Implement Database class with initialization**

```python
# bigiron/core/db.py
"""SQLite database layer for the provenance graph."""
import sqlite3
from pathlib import Path
from typing import Any


class Database:
    """SQLite database connection and schema management."""

    SCHEMA_VERSION = 1

    def __init__(self, db_path: Path | str):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite file, or ":memory:" for in-memory database
        """
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        """Open database connection."""
        if self.conn is None:
            self.conn = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")
            self.conn.execute("PRAGMA journal_mode = WAL")
        return self.conn

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute SQL and return cursor."""
        return self.connect().execute(sql, params)

    def executemany(self, sql: str, params_list: list[tuple]) -> sqlite3.Cursor:
        """Execute SQL with multiple parameter sets."""
        return self.connect().executemany(sql, params_list)

    def commit(self):
        """Commit current transaction."""
        if self.conn:
            self.conn.commit()

    def initialize(self):
        """Create database schema."""
        conn = self.connect()

        conn.executescript("""
            CREATE TABLE IF NOT EXISTS migrations (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                node_type TEXT NOT NULL,
                label TEXT NOT NULL,
                properties TEXT NOT NULL DEFAULT '{}',
                provenance TEXT NOT NULL DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);
            CREATE INDEX IF NOT EXISTS idx_nodes_label ON nodes(label);

            CREATE TABLE IF NOT EXISTS edges (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                edge_type TEXT NOT NULL,
                properties TEXT NOT NULL DEFAULT '{}',
                provenance TEXT NOT NULL DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (target_id) REFERENCES nodes(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
            CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(edge_type);
        """)

        conn.commit()
```

- [ ] **Step 4: Run database tests**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_db.py -v`
Expected: Both tests PASS

- [ ] **Step 5: Write failing test for node CRUD**

```python
# bigiron/tests/core/test_db.py (append)
import json


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
```

- [ ] **Step 6: Run CRUD tests**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_db.py -v`
Expected: All 5 tests PASS

- [ ] **Step 7: Commit**

```bash
git add bigiron/core/db.py bigiron/tests/core/test_db.py
git commit -m "feat(graph): add SQLite database layer

Database class with:
- Schema initialization (nodes, edges, migrations tables)
- WAL mode and foreign keys enabled
- Cascade delete for edges when nodes removed
- In-memory support for testing"
```

---

## Task 4: ProvenanceGraph Class - Node Operations

**Files:**
- Create: `bigiron/core/graph.py`
- Create: `bigiron/tests/core/test_graph.py`

- [ ] **Step 1: Write failing test for graph initialization**

```python
# bigiron/tests/core/test_graph.py
import pytest
import tempfile
from pathlib import Path


def test_graph_initializes_database():
    from bigiron.core.graph import ProvenanceGraph

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "graph.db"
        graph = ProvenanceGraph(db_path)

        assert graph.db is not None
        assert db_path.exists()

        graph.close()


def test_graph_in_memory():
    from bigiron.core.graph import ProvenanceGraph

    graph = ProvenanceGraph(":memory:")
    assert graph.db is not None
    graph.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_graph.py::test_graph_initializes_database -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'bigiron.core.graph'"

- [ ] **Step 3: Implement ProvenanceGraph initialization**

```python
# bigiron/core/graph.py
"""Provenance graph - the single source of truth."""
from pathlib import Path
from typing import Iterator

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
```

- [ ] **Step 4: Run initialization tests**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_graph.py -v`
Expected: Both tests PASS

- [ ] **Step 5: Write failing test for add_node**

```python
# bigiron/tests/core/test_graph.py (append)
from bigiron.core.schema import Node, NodeType, Provenance


def test_add_node():
    from bigiron.core.graph import ProvenanceGraph

    graph = ProvenanceGraph(":memory:")

    node = Node(
        id="host-1",
        node_type=NodeType.HOST,
        label="192.168.1.100",
        properties={"port": 23}
    )

    graph.add_node(node)

    # Retrieve and verify
    retrieved = graph.get_node("host-1")
    assert retrieved is not None
    assert retrieved.label == "192.168.1.100"
    assert retrieved.properties["port"] == 23

    graph.close()


def test_add_node_with_provenance():
    from bigiron.core.graph import ProvenanceGraph

    graph = ProvenanceGraph(":memory:")

    node = Node(
        node_type=NodeType.MODULE_RUN,
        label="ftp_enum run",
        provenance=Provenance(
            authorization_ref="ENG-2026-001",
            agent_turn=5
        )
    )

    graph.add_node(node)
    retrieved = graph.get_node(node.id)

    assert retrieved.provenance.authorization_ref == "ENG-2026-001"
    assert retrieved.provenance.agent_turn == 5

    graph.close()
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_graph.py::test_add_node -v`
Expected: FAIL with "AttributeError: 'ProvenanceGraph' object has no attribute 'add_node'"

- [ ] **Step 7: Implement add_node and get_node**

```python
# bigiron/core/graph.py (add methods to ProvenanceGraph class)
import json

    def add_node(self, node: Node) -> Node:
        """Add a node to the graph.

        Args:
            node: The node to add

        Returns:
            The added node (with any server-side modifications)
        """
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
        """Get a node by ID.

        Args:
            node_id: The node ID

        Returns:
            The node, or None if not found
        """
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
```

Add import at top:
```python
import json
```

- [ ] **Step 8: Run add_node tests**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_graph.py -k add_node -v`
Expected: Both tests PASS

- [ ] **Step 9: Write failing test for update_node and delete_node**

```python
# bigiron/tests/core/test_graph.py (append)


def test_update_node():
    from bigiron.core.graph import ProvenanceGraph

    graph = ProvenanceGraph(":memory:")

    node = Node(
        id="user-1",
        node_type=NodeType.USER,
        label="HERC01",
        properties={"group": "SYS1"}
    )
    graph.add_node(node)

    # Update properties
    node.properties["group"] = "ADMIN"
    node.label = "HERC01-ADMIN"
    graph.update_node(node)

    retrieved = graph.get_node("user-1")
    assert retrieved.label == "HERC01-ADMIN"
    assert retrieved.properties["group"] == "ADMIN"

    graph.close()


def test_delete_node():
    from bigiron.core.graph import ProvenanceGraph

    graph = ProvenanceGraph(":memory:")

    node = Node(node_type=NodeType.HOST, label="test")
    graph.add_node(node)

    assert graph.get_node(node.id) is not None

    graph.delete_node(node.id)

    assert graph.get_node(node.id) is None

    graph.close()
```

- [ ] **Step 10: Implement update_node and delete_node**

```python
# bigiron/core/graph.py (add methods)
from datetime import datetime, timezone

    def update_node(self, node: Node) -> Node:
        """Update an existing node.

        Args:
            node: The node with updated values

        Returns:
            The updated node
        """
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
        """Delete a node (and its connected edges via cascade).

        Args:
            node_id: The node ID to delete

        Returns:
            True if deleted, False if not found
        """
        cursor = self.db.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
        self.db.commit()
        return cursor.rowcount > 0
```

Add import:
```python
from datetime import datetime, timezone
```

- [ ] **Step 11: Run all node operation tests**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_graph.py -v`
Expected: All 6 tests PASS

- [ ] **Step 12: Commit**

```bash
git add bigiron/core/graph.py bigiron/tests/core/test_graph.py
git commit -m "feat(graph): add ProvenanceGraph with node CRUD

ProvenanceGraph class provides:
- add_node: Insert node with provenance
- get_node: Retrieve by ID
- update_node: Modify existing node
- delete_node: Remove node (cascades to edges)
- Context manager support"
```

---

## Task 5: ProvenanceGraph - Edge Operations

**Files:**
- Modify: `bigiron/core/graph.py`
- Modify: `bigiron/tests/core/test_graph.py`

- [ ] **Step 1: Write failing test for add_edge**

```python
# bigiron/tests/core/test_graph.py (append)
from bigiron.core.schema import Edge, EdgeType


def test_add_edge():
    from bigiron.core.graph import ProvenanceGraph

    graph = ProvenanceGraph(":memory:")

    # Create source and target nodes
    src = Node(id="run-1", node_type=NodeType.MODULE_RUN, label="TSO Enum")
    tgt = Node(id="user-1", node_type=NodeType.USER, label="HERC01")
    graph.add_node(src)
    graph.add_node(tgt)

    # Create edge
    edge = Edge(
        source_id="run-1",
        target_id="user-1",
        edge_type=EdgeType.DISCOVERED,
        properties={"parser": "TSOEnumParser"}
    )
    graph.add_edge(edge)

    # Retrieve and verify
    retrieved = graph.get_edge(edge.id)
    assert retrieved is not None
    assert retrieved.source_id == "run-1"
    assert retrieved.target_id == "user-1"
    assert retrieved.edge_type == EdgeType.DISCOVERED

    graph.close()


def test_add_edge_with_provenance():
    from bigiron.core.graph import ProvenanceGraph

    graph = ProvenanceGraph(":memory:")

    src = Node(id="a", node_type=NodeType.HOST, label="A")
    tgt = Node(id="b", node_type=NodeType.SERVICE, label="B")
    graph.add_node(src)
    graph.add_node(tgt)

    edge = Edge(
        source_id="a",
        target_id="b",
        edge_type=EdgeType.TARGETS,
        provenance=Provenance(
            authorization_ref="ENG-001",
            raw_output="[*] Targeting host..."
        )
    )
    graph.add_edge(edge)

    retrieved = graph.get_edge(edge.id)
    assert retrieved.provenance.authorization_ref == "ENG-001"
    assert "[*] Targeting" in retrieved.provenance.raw_output

    graph.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_graph.py::test_add_edge -v`
Expected: FAIL with "AttributeError: 'ProvenanceGraph' object has no attribute 'add_edge'"

- [ ] **Step 3: Implement add_edge and get_edge**

```python
# bigiron/core/graph.py (add methods)

    def add_edge(self, edge: Edge) -> Edge:
        """Add an edge between two nodes.

        Args:
            edge: The edge to add

        Returns:
            The added edge

        Raises:
            ValueError: If source or target node doesn't exist
        """
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
        """Get an edge by ID.

        Args:
            edge_id: The edge ID

        Returns:
            The edge, or None if not found
        """
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
```

- [ ] **Step 4: Run edge tests**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_graph.py -k edge -v`
Expected: Both tests PASS

- [ ] **Step 5: Write failing test for get_edges_from and get_edges_to**

```python
# bigiron/tests/core/test_graph.py (append)


def test_get_edges_from_node():
    from bigiron.core.graph import ProvenanceGraph

    graph = ProvenanceGraph(":memory:")

    # Create nodes
    run = Node(id="run-1", node_type=NodeType.MODULE_RUN, label="Scan")
    user1 = Node(id="u1", node_type=NodeType.USER, label="USER1")
    user2 = Node(id="u2", node_type=NodeType.USER, label="USER2")
    graph.add_node(run)
    graph.add_node(user1)
    graph.add_node(user2)

    # Create edges from run to users
    graph.add_edge(Edge(source_id="run-1", target_id="u1", edge_type=EdgeType.DISCOVERED))
    graph.add_edge(Edge(source_id="run-1", target_id="u2", edge_type=EdgeType.DISCOVERED))

    # Get outgoing edges
    edges = list(graph.get_edges_from("run-1"))

    assert len(edges) == 2
    target_ids = {e.target_id for e in edges}
    assert target_ids == {"u1", "u2"}

    graph.close()


def test_get_edges_to_node():
    from bigiron.core.graph import ProvenanceGraph

    graph = ProvenanceGraph(":memory:")

    # Create nodes
    auth = Node(id="auth-1", node_type=NodeType.AUTHORIZATION, label="Auth")
    run1 = Node(id="r1", node_type=NodeType.MODULE_RUN, label="Run1")
    run2 = Node(id="r2", node_type=NodeType.MODULE_RUN, label="Run2")
    graph.add_node(auth)
    graph.add_node(run1)
    graph.add_node(run2)

    # Create edges pointing to auth
    graph.add_edge(Edge(source_id="r1", target_id="auth-1", edge_type=EdgeType.AUTHORIZED_BY))
    graph.add_edge(Edge(source_id="r2", target_id="auth-1", edge_type=EdgeType.AUTHORIZED_BY))

    # Get incoming edges
    edges = list(graph.get_edges_to("auth-1"))

    assert len(edges) == 2
    source_ids = {e.source_id for e in edges}
    assert source_ids == {"r1", "r2"}

    graph.close()


def test_get_edges_filtered_by_type():
    from bigiron.core.graph import ProvenanceGraph

    graph = ProvenanceGraph(":memory:")

    a = Node(id="a", node_type=NodeType.HOST, label="A")
    b = Node(id="b", node_type=NodeType.USER, label="B")
    c = Node(id="c", node_type=NodeType.DATASET, label="C")
    graph.add_node(a)
    graph.add_node(b)
    graph.add_node(c)

    graph.add_edge(Edge(source_id="a", target_id="b", edge_type=EdgeType.DISCOVERED))
    graph.add_edge(Edge(source_id="a", target_id="c", edge_type=EdgeType.TARGETS))

    # Filter by type
    discovered = list(graph.get_edges_from("a", edge_type=EdgeType.DISCOVERED))
    assert len(discovered) == 1
    assert discovered[0].target_id == "b"

    graph.close()
```

- [ ] **Step 6: Implement get_edges_from and get_edges_to**

```python
# bigiron/core/graph.py (add methods)

    def get_edges_from(self, node_id: str, edge_type: EdgeType | None = None) -> Iterator[Edge]:
        """Get all outgoing edges from a node.

        Args:
            node_id: The source node ID
            edge_type: Optional filter by edge type

        Yields:
            Edges originating from the node
        """
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
        """Get all incoming edges to a node.

        Args:
            node_id: The target node ID
            edge_type: Optional filter by edge type

        Yields:
            Edges pointing to the node
        """
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
```

- [ ] **Step 7: Run all edge tests**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_graph.py -k edge -v`
Expected: All 5 edge tests PASS

- [ ] **Step 8: Commit**

```bash
git add bigiron/core/graph.py bigiron/tests/core/test_graph.py
git commit -m "feat(graph): add edge operations to ProvenanceGraph

Edge operations:
- add_edge: Create relationship with provenance
- get_edge: Retrieve by ID
- get_edges_from: Outgoing edges with optional type filter
- get_edges_to: Incoming edges with optional type filter"
```

---

## Task 6: Graph Query Operations

**Files:**
- Create: `bigiron/core/queries.py`
- Create: `bigiron/tests/core/test_queries.py`
- Modify: `bigiron/core/graph.py`

- [ ] **Step 1: Write failing test for get_nodes_by_type**

```python
# bigiron/tests/core/test_queries.py
import pytest
from bigiron.core.graph import ProvenanceGraph
from bigiron.core.schema import Node, Edge, NodeType, EdgeType


def test_get_nodes_by_type():
    graph = ProvenanceGraph(":memory:")

    graph.add_node(Node(node_type=NodeType.USER, label="USER1"))
    graph.add_node(Node(node_type=NodeType.USER, label="USER2"))
    graph.add_node(Node(node_type=NodeType.HOST, label="HOST1"))

    users = list(graph.get_nodes_by_type(NodeType.USER))

    assert len(users) == 2
    labels = {u.label for u in users}
    assert labels == {"USER1", "USER2"}

    graph.close()


def test_get_nodes_by_type_empty():
    graph = ProvenanceGraph(":memory:")

    graph.add_node(Node(node_type=NodeType.HOST, label="HOST1"))

    users = list(graph.get_nodes_by_type(NodeType.USER))
    assert len(users) == 0

    graph.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_queries.py::test_get_nodes_by_type -v`
Expected: FAIL with "AttributeError: 'ProvenanceGraph' object has no attribute 'get_nodes_by_type'"

- [ ] **Step 3: Implement get_nodes_by_type**

```python
# bigiron/core/graph.py (add method)

    def get_nodes_by_type(self, node_type: NodeType) -> Iterator[Node]:
        """Get all nodes of a specific type.

        Args:
            node_type: The type to filter by

        Yields:
            Nodes matching the type
        """
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
```

- [ ] **Step 4: Run query tests**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_queries.py -v`
Expected: Both tests PASS

- [ ] **Step 5: Write failing test for get_neighbors**

```python
# bigiron/tests/core/test_queries.py (append)


def test_get_neighbors_outgoing():
    graph = ProvenanceGraph(":memory:")

    run = Node(id="run", node_type=NodeType.MODULE_RUN, label="Run")
    u1 = Node(id="u1", node_type=NodeType.USER, label="U1")
    u2 = Node(id="u2", node_type=NodeType.USER, label="U2")

    graph.add_node(run)
    graph.add_node(u1)
    graph.add_node(u2)

    graph.add_edge(Edge(source_id="run", target_id="u1", edge_type=EdgeType.DISCOVERED))
    graph.add_edge(Edge(source_id="run", target_id="u2", edge_type=EdgeType.DISCOVERED))

    neighbors = list(graph.get_neighbors("run"))

    assert len(neighbors) == 2
    neighbor_ids = {n.id for n in neighbors}
    assert neighbor_ids == {"u1", "u2"}

    graph.close()


def test_get_neighbors_incoming():
    graph = ProvenanceGraph(":memory:")

    auth = Node(id="auth", node_type=NodeType.AUTHORIZATION, label="Auth")
    r1 = Node(id="r1", node_type=NodeType.MODULE_RUN, label="R1")
    r2 = Node(id="r2", node_type=NodeType.MODULE_RUN, label="R2")

    graph.add_node(auth)
    graph.add_node(r1)
    graph.add_node(r2)

    graph.add_edge(Edge(source_id="r1", target_id="auth", edge_type=EdgeType.AUTHORIZED_BY))
    graph.add_edge(Edge(source_id="r2", target_id="auth", edge_type=EdgeType.AUTHORIZED_BY))

    neighbors = list(graph.get_neighbors("auth", direction="incoming"))

    assert len(neighbors) == 2

    graph.close()


def test_get_neighbors_both_directions():
    graph = ProvenanceGraph(":memory:")

    middle = Node(id="m", node_type=NodeType.USER, label="M")
    left = Node(id="l", node_type=NodeType.HOST, label="L")
    right = Node(id="r", node_type=NodeType.DATASET, label="R")

    graph.add_node(middle)
    graph.add_node(left)
    graph.add_node(right)

    graph.add_edge(Edge(source_id="l", target_id="m", edge_type=EdgeType.DISCOVERED))
    graph.add_edge(Edge(source_id="m", target_id="r", edge_type=EdgeType.READS))

    neighbors = list(graph.get_neighbors("m", direction="both"))

    assert len(neighbors) == 2
    neighbor_ids = {n.id for n in neighbors}
    assert neighbor_ids == {"l", "r"}

    graph.close()
```

- [ ] **Step 6: Implement get_neighbors**

```python
# bigiron/core/graph.py (add method)
from typing import Literal

    def get_neighbors(
        self,
        node_id: str,
        direction: Literal["outgoing", "incoming", "both"] = "outgoing",
        edge_type: EdgeType | None = None
    ) -> Iterator[Node]:
        """Get neighboring nodes.

        Args:
            node_id: The node to get neighbors for
            direction: Which edges to follow
            edge_type: Optional filter by edge type

        Yields:
            Neighboring nodes
        """
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
```

Add import at top:
```python
from typing import Iterator, Literal
```

- [ ] **Step 7: Run neighbor tests**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_queries.py -v`
Expected: All 5 tests PASS

- [ ] **Step 8: Write failing test for find_paths**

```python
# bigiron/tests/core/test_queries.py (append)


def test_find_paths_direct():
    graph = ProvenanceGraph(":memory:")

    a = Node(id="a", node_type=NodeType.HOST, label="A")
    b = Node(id="b", node_type=NodeType.USER, label="B")

    graph.add_node(a)
    graph.add_node(b)
    graph.add_edge(Edge(source_id="a", target_id="b", edge_type=EdgeType.DISCOVERED))

    paths = list(graph.find_paths("a", "b"))

    assert len(paths) == 1
    assert paths[0] == ["a", "b"]

    graph.close()


def test_find_paths_multi_hop():
    graph = ProvenanceGraph(":memory:")

    # Create chain: a -> b -> c -> d
    nodes = [
        Node(id="a", node_type=NodeType.HOST, label="A"),
        Node(id="b", node_type=NodeType.USER, label="B"),
        Node(id="c", node_type=NodeType.DATASET, label="C"),
        Node(id="d", node_type=NodeType.PROGRAM, label="D"),
    ]
    for n in nodes:
        graph.add_node(n)

    graph.add_edge(Edge(source_id="a", target_id="b", edge_type=EdgeType.DISCOVERED))
    graph.add_edge(Edge(source_id="b", target_id="c", edge_type=EdgeType.READS))
    graph.add_edge(Edge(source_id="c", target_id="d", edge_type=EdgeType.LOADS_FROM))

    paths = list(graph.find_paths("a", "d"))

    assert len(paths) == 1
    assert paths[0] == ["a", "b", "c", "d"]

    graph.close()


def test_find_paths_no_path():
    graph = ProvenanceGraph(":memory:")

    a = Node(id="a", node_type=NodeType.HOST, label="A")
    b = Node(id="b", node_type=NodeType.USER, label="B")

    graph.add_node(a)
    graph.add_node(b)
    # No edge between them

    paths = list(graph.find_paths("a", "b"))

    assert len(paths) == 0

    graph.close()


def test_find_paths_multiple():
    graph = ProvenanceGraph(":memory:")

    # Create diamond: a -> b -> d, a -> c -> d
    a = Node(id="a", node_type=NodeType.HOST, label="A")
    b = Node(id="b", node_type=NodeType.USER, label="B")
    c = Node(id="c", node_type=NodeType.USER, label="C")
    d = Node(id="d", node_type=NodeType.DATASET, label="D")

    for n in [a, b, c, d]:
        graph.add_node(n)

    graph.add_edge(Edge(source_id="a", target_id="b", edge_type=EdgeType.DISCOVERED))
    graph.add_edge(Edge(source_id="a", target_id="c", edge_type=EdgeType.DISCOVERED))
    graph.add_edge(Edge(source_id="b", target_id="d", edge_type=EdgeType.READS))
    graph.add_edge(Edge(source_id="c", target_id="d", edge_type=EdgeType.READS))

    paths = list(graph.find_paths("a", "d"))

    assert len(paths) == 2
    path_sets = {tuple(p) for p in paths}
    assert ("a", "b", "d") in path_sets
    assert ("a", "c", "d") in path_sets

    graph.close()
```

- [ ] **Step 9: Implement find_paths (BFS)**

```python
# bigiron/core/graph.py (add method)
from collections import deque

    def find_paths(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 10
    ) -> Iterator[list[str]]:
        """Find all paths between two nodes using BFS.

        Args:
            source_id: Starting node ID
            target_id: Destination node ID
            max_depth: Maximum path length to search

        Yields:
            Paths as lists of node IDs
        """
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
```

Add import:
```python
from collections import deque
```

- [ ] **Step 10: Run path finding tests**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_queries.py -v`
Expected: All 9 tests PASS

- [ ] **Step 11: Commit**

```bash
git add bigiron/core/graph.py bigiron/tests/core/test_queries.py
git commit -m "feat(graph): add query operations

Query operations for graph traversal:
- get_nodes_by_type: Filter nodes by type
- get_neighbors: Get adjacent nodes with direction filter
- find_paths: BFS path finding between nodes"
```

---

## Task 7: Graph Export and Statistics

**Files:**
- Modify: `bigiron/core/graph.py`
- Modify: `bigiron/tests/core/test_graph.py`

- [ ] **Step 1: Write failing test for to_dict export**

```python
# bigiron/tests/core/test_graph.py (append)


def test_to_dict_export():
    from bigiron.core.graph import ProvenanceGraph

    graph = ProvenanceGraph(":memory:")

    n1 = Node(id="n1", node_type=NodeType.HOST, label="Host1")
    n2 = Node(id="n2", node_type=NodeType.USER, label="User1")
    graph.add_node(n1)
    graph.add_node(n2)
    graph.add_edge(Edge(source_id="n1", target_id="n2", edge_type=EdgeType.DISCOVERED))

    data = graph.to_dict()

    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) == 2
    assert len(data["edges"]) == 1

    graph.close()


def test_stats():
    from bigiron.core.graph import ProvenanceGraph

    graph = ProvenanceGraph(":memory:")

    graph.add_node(Node(node_type=NodeType.HOST, label="H1"))
    graph.add_node(Node(node_type=NodeType.HOST, label="H2"))
    graph.add_node(Node(node_type=NodeType.USER, label="U1"))

    stats = graph.stats()

    assert stats["total_nodes"] == 3
    assert stats["total_edges"] == 0
    assert stats["nodes_by_type"]["host"] == 2
    assert stats["nodes_by_type"]["user"] == 1

    graph.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_graph.py::test_to_dict_export -v`
Expected: FAIL with "AttributeError: 'ProvenanceGraph' object has no attribute 'to_dict'"

- [ ] **Step 3: Implement to_dict and stats**

```python
# bigiron/core/graph.py (add methods)

    def to_dict(self) -> dict:
        """Export the entire graph as a dictionary.

        Returns:
            Dictionary with 'nodes' and 'edges' lists
        """
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
        """Get graph statistics.

        Returns:
            Dictionary with node/edge counts and type breakdowns
        """
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
```

- [ ] **Step 4: Run export tests**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_graph.py -k "dict or stats" -v`
Expected: Both tests PASS

- [ ] **Step 5: Write failing test for search_nodes**

```python
# bigiron/tests/core/test_graph.py (append)


def test_search_nodes_by_label():
    from bigiron.core.graph import ProvenanceGraph

    graph = ProvenanceGraph(":memory:")

    graph.add_node(Node(node_type=NodeType.USER, label="HERC01"))
    graph.add_node(Node(node_type=NodeType.USER, label="HERC02"))
    graph.add_node(Node(node_type=NodeType.USER, label="IBMUSER"))

    results = list(graph.search_nodes("HERC"))

    assert len(results) == 2
    labels = {n.label for n in results}
    assert labels == {"HERC01", "HERC02"}

    graph.close()


def test_search_nodes_case_insensitive():
    from bigiron.core.graph import ProvenanceGraph

    graph = ProvenanceGraph(":memory:")

    graph.add_node(Node(node_type=NodeType.DATASET, label="SYS1.PARMLIB"))

    results = list(graph.search_nodes("parmlib"))

    assert len(results) == 1
    assert results[0].label == "SYS1.PARMLIB"

    graph.close()
```

- [ ] **Step 6: Implement search_nodes**

```python
# bigiron/core/graph.py (add method)

    def search_nodes(self, query: str, node_type: NodeType | None = None) -> Iterator[Node]:
        """Search nodes by label (case-insensitive substring match).

        Args:
            query: Search string
            node_type: Optional filter by type

        Yields:
            Matching nodes
        """
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
```

- [ ] **Step 7: Run all graph tests**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_graph.py -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add bigiron/core/graph.py bigiron/tests/core/test_graph.py
git commit -m "feat(graph): add export, stats, and search

Graph utilities:
- to_dict: Export full graph as JSON-serializable dict
- stats: Node/edge counts and type breakdowns
- search_nodes: Case-insensitive label search"
```

---

## Task 8: Core Module Exports and Integration Test

**Files:**
- Modify: `bigiron/__init__.py`
- Modify: `bigiron/core/__init__.py`
- Create: `bigiron/tests/core/test_integration.py`

- [ ] **Step 1: Update package exports**

```python
# bigiron/__init__.py
"""BigIron - Mainframe Security Assessment Framework."""
__version__ = "0.1.0"

from bigiron.core.graph import ProvenanceGraph
from bigiron.core.schema import (
    Node,
    Edge,
    NodeType,
    EdgeType,
    Provenance,
)

__all__ = [
    "ProvenanceGraph",
    "Node",
    "Edge",
    "NodeType",
    "EdgeType",
    "Provenance",
]
```

```python
# bigiron/core/__init__.py
"""Core graph components."""
from .graph import ProvenanceGraph
from .schema import Node, Edge, NodeType, EdgeType, Provenance
from .db import Database

__all__ = [
    "ProvenanceGraph",
    "Node",
    "Edge",
    "NodeType",
    "EdgeType",
    "Provenance",
    "Database",
]
```

- [ ] **Step 2: Write integration test**

```python
# bigiron/tests/core/test_integration.py
"""Integration tests for the provenance graph core."""
import pytest
import tempfile
from pathlib import Path

from bigiron import (
    ProvenanceGraph,
    Node,
    Edge,
    NodeType,
    EdgeType,
    Provenance,
)


def test_full_engagement_workflow():
    """Test a complete engagement workflow through the graph."""

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "engagement.db"

        with ProvenanceGraph(db_path) as graph:
            # 1. Create engagement
            engagement = Node(
                id="eng-2026-001",
                node_type=NodeType.ENGAGEMENT,
                label="Mainframe Assessment Q2 2026",
                properties={
                    "client": "ACME Corp",
                    "scope": ["10.0.0.0/24"],
                    "start_date": "2026-06-01"
                }
            )
            graph.add_node(engagement)

            # 2. Create authorization
            auth = Node(
                id="auth-001",
                node_type=NodeType.AUTHORIZATION,
                label="Initial Recon Authorization",
                properties={
                    "operator": "w00t3k",
                    "approved_modules": ["tso_enum", "vtam_enum"]
                }
            )
            graph.add_node(auth)
            graph.add_edge(Edge(
                source_id="auth-001",
                target_id="eng-2026-001",
                edge_type=EdgeType.PART_OF
            ))

            # 3. Simulate module run
            module_run = Node(
                id="run-001",
                node_type=NodeType.MODULE_RUN,
                label="tso_enum execution",
                provenance=Provenance(
                    authorization_ref="auth-001",
                    raw_output="[*] Enumerating TSO users...\n[+] Found: HERC01, IBMUSER"
                )
            )
            graph.add_node(module_run)
            graph.add_edge(Edge(
                source_id="run-001",
                target_id="auth-001",
                edge_type=EdgeType.AUTHORIZED_BY
            ))

            # 4. Add discovered entities
            for username in ["HERC01", "IBMUSER"]:
                user = Node(
                    id=f"user-{username}",
                    node_type=NodeType.USER,
                    label=username,
                    properties={"source": "tso_enum"}
                )
                graph.add_node(user)
                graph.add_edge(Edge(
                    source_id="run-001",
                    target_id=f"user-{username}",
                    edge_type=EdgeType.DISCOVERED,
                    provenance=Provenance(
                        parsed_entities=[username]
                    )
                ))

            # 5. Verify graph state
            stats = graph.stats()
            assert stats["total_nodes"] == 5  # engagement, auth, run, 2 users
            assert stats["total_edges"] == 4  # part_of, authorized_by, 2 discovered

            # 6. Find attack path
            paths = list(graph.find_paths("run-001", "user-HERC01"))
            assert len(paths) == 1
            assert paths[0] == ["run-001", "user-HERC01"]

            # 7. Export and verify
            export = graph.to_dict()
            assert len(export["nodes"]) == 5

            # 8. Search
            users = list(graph.search_nodes("HERC"))
            assert len(users) == 1
            assert users[0].label == "HERC01"

        # 9. Verify persistence - reopen and check
        with ProvenanceGraph(db_path) as graph:
            stats = graph.stats()
            assert stats["total_nodes"] == 5

            herc = graph.get_node("user-HERC01")
            assert herc is not None
            assert herc.properties["source"] == "tso_enum"


def test_import_from_top_level():
    """Verify all exports are accessible from bigiron package."""
    from bigiron import ProvenanceGraph, Node, Edge, NodeType, EdgeType, Provenance

    assert ProvenanceGraph is not None
    assert Node is not None
    assert Edge is not None
    assert NodeType.HOST.value == "host"
    assert EdgeType.DISCOVERED.value == "discovered"
    assert Provenance is not None
```

- [ ] **Step 3: Run integration tests**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/core/test_integration.py -v`
Expected: Both tests PASS

- [ ] **Step 4: Run full test suite**

Run: `cd /Users/w00tock/MF-local/mainframe-aisploit && python -m pytest bigiron/tests/ -v`
Expected: All tests PASS (should be ~25+ tests)

- [ ] **Step 5: Commit**

```bash
git add bigiron/__init__.py bigiron/core/__init__.py bigiron/tests/core/test_integration.py
git commit -m "feat(graph): finalize core module with integration tests

Complete provenance graph core:
- Package exports from bigiron and bigiron.core
- Integration test covering full engagement workflow
- Persistence verification across sessions"
```

- [ ] **Step 6: Push and tag**

```bash
git push
git tag -a v0.1.0-graph-core -m "Provenance graph core complete"
git push --tags
```

---

## Summary

This plan implements the **Provenance Graph Core** - the foundation of the mainframe-aisploit framework. After completing these 8 tasks, you'll have:

- **Schema models** (Node, Edge, Provenance, NodeType, EdgeType)
- **SQLite persistence** with proper indexing and foreign keys
- **ProvenanceGraph class** with full CRUD operations
- **Query operations** (by type, neighbors, path finding, search)
- **Export/stats** utilities
- **Integration tests** proving the full workflow

**Next plan**: MSF Integration Layer (catalog service, RPC client, executor with authorization gate)
