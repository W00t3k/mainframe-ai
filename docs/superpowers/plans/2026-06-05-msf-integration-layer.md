# MSF Integration Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Metasploit integration layer that imports modules from live MSF, executes them with authorization gates, and parses output into the provenance graph.

**Architecture:** Three services - CatalogService (imports modules as graph nodes), ExecutorService (runs modules with auth gate), and a parser registry (extracts entities from output). All executions flow through the graph with full provenance.

**Tech Stack:** Python 3.11+, pymetasploit3 (MSF RPC client), existing bigiron.core for graph, pytest for testing

**Depends on:** Plan 1 (Provenance Graph Core) - COMPLETE

---

## File Structure

```
bigiron/
├── core/                    # From Plan 1 (exists)
├── msf/
│   ├── __init__.py
│   ├── client.py            # MSF RPC connection wrapper
│   ├── catalog.py           # CatalogService - module import
│   ├── executor.py          # ExecutorService - auth-gated execution
│   ├── authorization.py     # Authorization model and gate
│   └── parsers/
│       ├── __init__.py
│       ├── base.py          # OutputParser base class
│       ├── registry.py      # Parser registry with decorator
│       ├── jcl.py           # JCL output parser
│       ├── tso.py           # TSO enum parser
│       └── generic.py       # Fallback regex parser
└── tests/
    └── msf/
        ├── __init__.py
        ├── test_client.py
        ├── test_catalog.py
        ├── test_executor.py
        └── test_parsers.py
```

---

## Task 1: MSF Client Wrapper

**Files:**
- Create: `bigiron/msf/__init__.py`
- Create: `bigiron/msf/client.py`
- Create: `bigiron/tests/msf/__init__.py`
- Create: `bigiron/tests/msf/test_client.py`

- [ ] **Step 1: Create package structure**

```bash
mkdir -p bigiron/msf bigiron/tests/msf
touch bigiron/msf/__init__.py bigiron/tests/msf/__init__.py
```

- [ ] **Step 2: Write failing test for MsfClient**

```python
# bigiron/tests/msf/test_client.py
import pytest
from unittest.mock import Mock, patch


def test_msf_client_initialization():
    from bigiron.msf.client import MsfClient

    client = MsfClient(
        host="127.0.0.1",
        port=55553,
        password="testpass"
    )

    assert client.host == "127.0.0.1"
    assert client.port == 55553
    assert client.password == "testpass"
    assert client._client is None  # Not connected yet


def test_msf_client_from_env(monkeypatch):
    from bigiron.msf.client import MsfClient

    monkeypatch.setenv("MSF_HOST", "10.0.0.1")
    monkeypatch.setenv("MSF_PORT", "55554")
    monkeypatch.setenv("MSF_PASSWORD", "envpass")

    client = MsfClient.from_env()

    assert client.host == "10.0.0.1"
    assert client.port == 55554
    assert client.password == "envpass"


def test_msf_client_defaults(monkeypatch):
    from bigiron.msf.client import MsfClient

    # Clear any existing env vars
    monkeypatch.delenv("MSF_HOST", raising=False)
    monkeypatch.delenv("MSF_PORT", raising=False)
    monkeypatch.delenv("MSF_PASSWORD", raising=False)

    client = MsfClient.from_env()

    assert client.host == "127.0.0.1"
    assert client.port == 55553
    assert client.password is None


def test_msf_client_is_demo_mode_without_password():
    from bigiron.msf.client import MsfClient

    client = MsfClient(host="127.0.0.1", port=55553, password=None)
    assert client.is_demo_mode is True


def test_msf_client_is_demo_mode_with_password():
    from bigiron.msf.client import MsfClient

    client = MsfClient(host="127.0.0.1", port=55553, password="secret")
    assert client.is_demo_mode is False
```

- [ ] **Step 3: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/msf/test_client.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 4: Implement MsfClient**

```python
# bigiron/msf/client.py
"""Metasploit RPC client wrapper."""
import os
from typing import Any


class MsfClient:
    """Wrapper around pymetasploit3 for MSF RPC communication.

    Supports demo mode when no password is configured - returns
    mock data instead of connecting to a real MSF instance.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 55553,
        password: str | None = None,
        ssl: bool = True
    ):
        """Initialize MSF client.

        Args:
            host: MSF RPC host
            port: MSF RPC port
            password: MSF RPC password (None for demo mode)
            ssl: Use SSL for connection
        """
        self.host = host
        self.port = port
        self.password = password
        self.ssl = ssl
        self._client = None

    @classmethod
    def from_env(cls) -> "MsfClient":
        """Create client from environment variables.

        Reads:
            MSF_HOST: Host (default: 127.0.0.1)
            MSF_PORT: Port (default: 55553)
            MSF_PASSWORD: Password (default: None = demo mode)
            MSF_SSL: Use SSL (default: true)
        """
        return cls(
            host=os.getenv("MSF_HOST", "127.0.0.1"),
            port=int(os.getenv("MSF_PORT", "55553")),
            password=os.getenv("MSF_PASSWORD"),
            ssl=os.getenv("MSF_SSL", "true").lower() == "true"
        )

    @property
    def is_demo_mode(self) -> bool:
        """Check if running in demo mode (no real MSF connection)."""
        return self.password is None

    @property
    def is_connected(self) -> bool:
        """Check if connected to MSF RPC."""
        return self._client is not None

    def connect(self) -> bool:
        """Connect to MSF RPC.

        Returns:
            True if connected, False if in demo mode

        Raises:
            ConnectionError: If connection fails
        """
        if self.is_demo_mode:
            return False

        try:
            from pymetasploit3.msfrpc import MsfRpcClient
            self._client = MsfRpcClient(
                self.password,
                server=self.host,
                port=self.port,
                ssl=self.ssl
            )
            return True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to MSF RPC: {e}")

    def disconnect(self):
        """Disconnect from MSF RPC."""
        self._client = None

    @property
    def client(self):
        """Get the underlying pymetasploit3 client.

        Raises:
            RuntimeError: If not connected
        """
        if self._client is None:
            raise RuntimeError("Not connected to MSF RPC. Call connect() first.")
        return self._client

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False
```

- [ ] **Step 5: Run tests**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/msf/test_client.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add bigiron/msf/ bigiron/tests/msf/
git commit -m "feat(msf): add MsfClient wrapper

MSF RPC client with:
- Environment variable configuration
- Demo mode when no password configured
- Context manager support
- Connection state tracking"
```

---

## Task 2: Module Schema and Demo Data

**Files:**
- Create: `bigiron/msf/models.py`
- Create: `bigiron/msf/demo_data.py`
- Modify: `bigiron/tests/msf/test_client.py`

- [ ] **Step 1: Write failing test for module models**

```python
# bigiron/tests/msf/test_models.py
import pytest


def test_module_summary_creation():
    from bigiron.msf.models import ModuleSummary

    mod = ModuleSummary(
        mtype="auxiliary",
        path="scanner/mainframe/ftp_jcl_creds",
        name="FTP JCL Credential Scanner",
        rank="normal"
    )

    assert mod.mtype == "auxiliary"
    assert mod.path == "scanner/mainframe/ftp_jcl_creds"
    assert mod.full_path == "auxiliary/scanner/mainframe/ftp_jcl_creds"


def test_module_detail_creation():
    from bigiron.msf.models import ModuleDetail, ModuleOption

    opt = ModuleOption(
        name="RHOSTS",
        required=True,
        description="Target host(s)",
        default=None
    )

    detail = ModuleDetail(
        mtype="auxiliary",
        path="scanner/mainframe/ftp_jcl_creds",
        name="FTP JCL Credential Scanner",
        rank="normal",
        description="Scans for JCL submission via FTP",
        authors=["w00t3k"],
        references=[{"type": "URL", "ref": "https://example.com"}],
        options=[opt],
        targets=["MVS 3.8j", "z/OS"]
    )

    assert detail.description == "Scans for JCL submission via FTP"
    assert len(detail.options) == 1
    assert detail.options[0].name == "RHOSTS"


def test_module_option_with_default():
    from bigiron.msf.models import ModuleOption

    opt = ModuleOption(
        name="RPORT",
        required=True,
        description="FTP port",
        default="21"
    )

    assert opt.default == "21"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/msf/test_models.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Implement module models**

```python
# bigiron/msf/models.py
"""Pydantic models for MSF modules."""
from pydantic import BaseModel, Field, computed_field
from typing import Any


class ModuleOption(BaseModel):
    """A module option/parameter."""
    name: str
    required: bool = False
    description: str = ""
    default: str | None = None
    type: str = "string"


class ModuleSummary(BaseModel):
    """Summary info for a module (from search results)."""
    mtype: str  # auxiliary, exploit, post, etc.
    path: str   # scanner/mainframe/ftp_jcl_creds
    name: str
    rank: str = "normal"

    @computed_field
    @property
    def full_path(self) -> str:
        """Full module path including type."""
        return f"{self.mtype}/{self.path}"


class ModuleDetail(ModuleSummary):
    """Full module details (from module.use())."""
    description: str = ""
    authors: list[str] = Field(default_factory=list)
    references: list[dict[str, str]] = Field(default_factory=list)
    options: list[ModuleOption] = Field(default_factory=list)
    targets: list[str] = Field(default_factory=list)
    platform: str = ""
    arch: str = ""

    # For tracking in our system
    tk5_compatible: bool = False  # Can run against TK5/MVS 3.8j
    requires_modern_zos: bool = False  # Needs z/OS features


class ExecutionPreview(BaseModel):
    """Preview of what will be executed (before auth)."""
    module: ModuleSummary
    options: dict[str, str]
    command: str  # The MSF console command that would run
    target_description: str


class ExecutionResult(BaseModel):
    """Result of module execution."""
    module_path: str
    success: bool
    output: str
    job_id: str | None = None  # For mainframe jobs
    error: str | None = None
    duration_ms: int = 0
```

- [ ] **Step 4: Run tests**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/msf/test_models.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Create demo data**

```python
# bigiron/msf/demo_data.py
"""Demo/mock data for when MSF RPC is not available."""
from .models import ModuleSummary, ModuleDetail, ModuleOption


DEMO_MODULES: list[ModuleSummary] = [
    ModuleSummary(
        mtype="auxiliary",
        path="scanner/mainframe/ftp_jcl_creds",
        name="FTP JCL Credential Scanner",
        rank="normal"
    ),
    ModuleSummary(
        mtype="auxiliary",
        path="admin/mainframe/tk5_jcl_submit",
        name="TK5 JCL Job Submission",
        rank="normal"
    ),
    ModuleSummary(
        mtype="auxiliary",
        path="scanner/mainframe/tso_enum",
        name="TSO User Enumeration",
        rank="normal"
    ),
    ModuleSummary(
        mtype="auxiliary",
        path="scanner/mainframe/vtam_enum",
        name="VTAM APPLID Enumeration",
        rank="normal"
    ),
    ModuleSummary(
        mtype="auxiliary",
        path="scanner/mainframe/cics_enum",
        name="CICS Transaction Enumeration",
        rank="normal"
    ),
    ModuleSummary(
        mtype="auxiliary",
        path="scanner/mainframe/jes_enum",
        name="JES2 Configuration Scanner",
        rank="normal"
    ),
]


def get_demo_module_detail(mtype: str, path: str) -> ModuleDetail | None:
    """Get detailed info for a demo module."""

    details = {
        "auxiliary/scanner/mainframe/ftp_jcl_creds": ModuleDetail(
            mtype="auxiliary",
            path="scanner/mainframe/ftp_jcl_creds",
            name="FTP JCL Credential Scanner",
            rank="normal",
            description="This module scans for the ability to submit JCL via FTP "
                       "to the JES internal reader. If SITE FILETYPE=JES is enabled, "
                       "arbitrary JCL can be submitted under the FTP user's authority.",
            authors=["w00t3k", "Soldier of Fortran"],
            references=[
                {"type": "URL", "ref": "https://www.ibm.com/docs/en/zos/2.5.0?topic=ftp-submitting-jobs"}
            ],
            options=[
                ModuleOption(name="RHOSTS", required=True, description="Target host(s)"),
                ModuleOption(name="RPORT", required=True, description="FTP port", default="21"),
                ModuleOption(name="USERNAME", required=True, description="FTP username"),
                ModuleOption(name="PASSWORD", required=True, description="FTP password"),
            ],
            targets=["MVS 3.8j", "z/OS"],
            tk5_compatible=True,
            requires_modern_zos=False
        ),
        "auxiliary/admin/mainframe/tk5_jcl_submit": ModuleDetail(
            mtype="auxiliary",
            path="admin/mainframe/tk5_jcl_submit",
            name="TK5 JCL Job Submission",
            rank="normal",
            description="Submits JCL to a TK5/MVS 3.8j system via FTP to the JES "
                       "internal reader. Demonstrates arbitrary batch job execution.",
            authors=["w00t3k"],
            references=[],
            options=[
                ModuleOption(name="RHOSTS", required=True, description="Target host"),
                ModuleOption(name="RPORT", required=True, description="FTP port", default="21"),
                ModuleOption(name="USERNAME", required=True, description="FTP username", default="HERC01"),
                ModuleOption(name="PASSWORD", required=True, description="FTP password", default="CUL8TR"),
                ModuleOption(name="JCL", required=False, description="JCL to submit (default: IEFBR14)"),
            ],
            targets=["MVS 3.8j"],
            tk5_compatible=True,
            requires_modern_zos=False
        ),
        "auxiliary/scanner/mainframe/tso_enum": ModuleDetail(
            mtype="auxiliary",
            path="scanner/mainframe/tso_enum",
            name="TSO User Enumeration",
            rank="normal",
            description="Enumerates TSO users via the 3270 interface by attempting "
                       "logins and analyzing error messages.",
            authors=["Soldier of Fortran", "mainframed"],
            references=[
                {"type": "URL", "ref": "https://github.com/mainframed/nmap"}
            ],
            options=[
                ModuleOption(name="RHOSTS", required=True, description="Target host"),
                ModuleOption(name="RPORT", required=True, description="TN3270 port", default="23"),
                ModuleOption(name="USER_FILE", required=False, description="File with usernames to try"),
            ],
            targets=["MVS", "z/OS"],
            tk5_compatible=True,
            requires_modern_zos=False
        ),
    }

    full_path = f"{mtype}/{path}"
    return details.get(full_path)


DEMO_EXECUTION_OUTPUT = {
    "auxiliary/admin/mainframe/tk5_jcl_submit": """
[*] Connecting to 127.0.0.1:21...
[+] Connected to FTP server
[*] Logging in as HERC01...
[+] Login successful
[*] Switching to JES mode (SITE FILETYPE=JES)...
[+] JES mode enabled
[*] Submitting JCL...
[+] Job submitted successfully
[+] JOB ID: JOB00042
[*] Auxiliary module execution completed
""",
    "auxiliary/scanner/mainframe/tso_enum": """
[*] Connecting to 127.0.0.1:23...
[+] Connected to TN3270
[*] Navigating to TSO logon screen...
[+] Found TSO logon panel
[*] Enumerating users...
[+] Valid user found: HERC01
[+] Valid user found: HERC02
[+] Valid user found: IBMUSER
[-] Invalid user: TESTUSER
[-] Invalid user: ADMIN
[*] Enumeration complete
[+] Found 3 valid users
[*] Auxiliary module execution completed
"""
}
```

- [ ] **Step 6: Write test for demo data**

```python
# bigiron/tests/msf/test_demo_data.py
import pytest


def test_demo_modules_list():
    from bigiron.msf.demo_data import DEMO_MODULES

    assert len(DEMO_MODULES) >= 5

    paths = [m.full_path for m in DEMO_MODULES]
    assert "auxiliary/scanner/mainframe/ftp_jcl_creds" in paths
    assert "auxiliary/admin/mainframe/tk5_jcl_submit" in paths


def test_get_demo_module_detail():
    from bigiron.msf.demo_data import get_demo_module_detail

    detail = get_demo_module_detail("auxiliary", "admin/mainframe/tk5_jcl_submit")

    assert detail is not None
    assert detail.name == "TK5 JCL Job Submission"
    assert detail.tk5_compatible is True
    assert len(detail.options) >= 4


def test_get_demo_module_detail_not_found():
    from bigiron.msf.demo_data import get_demo_module_detail

    detail = get_demo_module_detail("auxiliary", "nonexistent/module")
    assert detail is None
```

- [ ] **Step 7: Run all tests**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/msf/ -v`
Expected: All 11 tests PASS

- [ ] **Step 8: Commit**

```bash
git add bigiron/msf/models.py bigiron/msf/demo_data.py bigiron/tests/msf/
git commit -m "feat(msf): add module models and demo data

Module models:
- ModuleSummary: Basic module info from search
- ModuleDetail: Full info with options, refs, targets
- ModuleOption: Parameter definitions
- ExecutionPreview/Result: Execution lifecycle

Demo data for offline/conference demos"
```

---

## Task 3: Catalog Service

**Files:**
- Create: `bigiron/msf/catalog.py`
- Create: `bigiron/tests/msf/test_catalog.py`

- [ ] **Step 1: Write failing test for CatalogService**

```python
# bigiron/tests/msf/test_catalog.py
import pytest
from unittest.mock import Mock, patch


def test_catalog_service_initialization():
    from bigiron.msf.catalog import CatalogService
    from bigiron.msf.client import MsfClient
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)  # Demo mode
    graph = ProvenanceGraph(":memory:")

    catalog = CatalogService(client=client, graph=graph)

    assert catalog.client is client
    assert catalog.graph is graph

    graph.close()


def test_catalog_search_demo_mode():
    from bigiron.msf.catalog import CatalogService
    from bigiron.msf.client import MsfClient
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)  # Demo mode
    graph = ProvenanceGraph(":memory:")

    catalog = CatalogService(client=client, graph=graph)

    # Search for mainframe modules
    results = catalog.search("mainframe")

    assert len(results) >= 5
    assert any("ftp_jcl" in m.path for m in results)

    graph.close()


def test_catalog_get_module_demo_mode():
    from bigiron.msf.catalog import CatalogService
    from bigiron.msf.client import MsfClient
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)  # Demo mode
    graph = ProvenanceGraph(":memory:")

    catalog = CatalogService(client=client, graph=graph)

    detail = catalog.get_module("auxiliary", "admin/mainframe/tk5_jcl_submit")

    assert detail is not None
    assert detail.name == "TK5 JCL Job Submission"
    assert len(detail.options) >= 4

    graph.close()


def test_catalog_sync_to_graph():
    from bigiron.msf.catalog import CatalogService
    from bigiron.msf.client import MsfClient
    from bigiron.core.graph import ProvenanceGraph
    from bigiron.core.schema import NodeType

    client = MsfClient(password=None)  # Demo mode
    graph = ProvenanceGraph(":memory:")

    catalog = CatalogService(client=client, graph=graph)

    # Sync modules to graph
    count = catalog.sync_to_graph()

    assert count >= 5

    # Verify nodes were created
    modules = list(graph.get_nodes_by_type(NodeType.MSF_MODULE))
    assert len(modules) >= 5

    graph.close()


def test_catalog_filter_by_type():
    from bigiron.msf.catalog import CatalogService
    from bigiron.msf.client import MsfClient
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")

    catalog = CatalogService(client=client, graph=graph)

    # Filter for auxiliary only
    results = catalog.search("mainframe", mtype="auxiliary")

    assert len(results) >= 5
    assert all(m.mtype == "auxiliary" for m in results)

    graph.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/msf/test_catalog.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Implement CatalogService**

```python
# bigiron/msf/catalog.py
"""Catalog service for importing MSF modules into the graph."""
from typing import Iterator

from .client import MsfClient
from .models import ModuleSummary, ModuleDetail
from .demo_data import DEMO_MODULES, get_demo_module_detail
from ..core.graph import ProvenanceGraph
from ..core.schema import Node, NodeType, Provenance


class CatalogService:
    """Imports and manages MSF modules in the provenance graph.

    In demo mode, uses built-in demo data.
    In live mode, queries MSF RPC for real module info.
    """

    def __init__(self, client: MsfClient, graph: ProvenanceGraph):
        """Initialize catalog service.

        Args:
            client: MSF RPC client
            graph: Provenance graph for storing module nodes
        """
        self.client = client
        self.graph = graph

    def search(
        self,
        query: str = "",
        mtype: str | None = None
    ) -> list[ModuleSummary]:
        """Search for modules matching query.

        Args:
            query: Search string (matches name, path, description)
            mtype: Filter by module type (auxiliary, exploit, etc.)

        Returns:
            List of matching module summaries
        """
        if self.client.is_demo_mode:
            return self._search_demo(query, mtype)
        else:
            return self._search_live(query, mtype)

    def _search_demo(self, query: str, mtype: str | None) -> list[ModuleSummary]:
        """Search demo modules."""
        results = []
        query_lower = query.lower()

        for mod in DEMO_MODULES:
            # Filter by type if specified
            if mtype and mod.mtype != mtype:
                continue

            # Match query against path and name
            if query_lower in mod.path.lower() or query_lower in mod.name.lower():
                results.append(mod)

        return results

    def _search_live(self, query: str, mtype: str | None) -> list[ModuleSummary]:
        """Search live MSF instance."""
        if not self.client.is_connected:
            self.client.connect()

        search_term = f"type:{mtype} {query}" if mtype else query
        raw_results = self.client.client.modules.search(search_term)

        results = []
        for item in raw_results:
            results.append(ModuleSummary(
                mtype=item.get("type", "auxiliary"),
                path=item.get("fullname", "").replace(f"{item.get('type', '')}/", "", 1),
                name=item.get("name", ""),
                rank=item.get("rank", "normal")
            ))

        return results

    def get_module(self, mtype: str, path: str) -> ModuleDetail | None:
        """Get full details for a specific module.

        Args:
            mtype: Module type (auxiliary, exploit, etc.)
            path: Module path (without type prefix)

        Returns:
            Module details, or None if not found
        """
        if self.client.is_demo_mode:
            return get_demo_module_detail(mtype, path)
        else:
            return self._get_module_live(mtype, path)

    def _get_module_live(self, mtype: str, path: str) -> ModuleDetail | None:
        """Get module details from live MSF."""
        if not self.client.is_connected:
            self.client.connect()

        try:
            full_path = f"{mtype}/{path}"
            mod = self.client.client.modules.use(mtype, path)

            from .models import ModuleOption
            options = []
            for name, info in mod.options.items():
                options.append(ModuleOption(
                    name=name,
                    required=info.get("required", False),
                    description=info.get("desc", ""),
                    default=info.get("default"),
                    type=info.get("type", "string")
                ))

            return ModuleDetail(
                mtype=mtype,
                path=path,
                name=mod.name,
                rank=mod.rank or "normal",
                description=mod.description or "",
                authors=mod.authors or [],
                references=mod.references or [],
                options=options,
                targets=list(mod.targets.values()) if hasattr(mod, 'targets') else []
            )
        except Exception:
            return None

    def sync_to_graph(self, query: str = "mainframe") -> int:
        """Import modules into the provenance graph as nodes.

        Args:
            query: Search query to filter which modules to sync

        Returns:
            Number of modules synced
        """
        modules = self.search(query)
        count = 0

        for mod in modules:
            node_id = f"msf-{mod.full_path.replace('/', '-')}"

            # Check if already exists
            existing = self.graph.get_node(node_id)
            if existing:
                continue

            # Get full details if available
            detail = self.get_module(mod.mtype, mod.path)

            node = Node(
                id=node_id,
                node_type=NodeType.MSF_MODULE,
                label=mod.name,
                properties={
                    "mtype": mod.mtype,
                    "path": mod.path,
                    "full_path": mod.full_path,
                    "rank": mod.rank,
                    "description": detail.description if detail else "",
                    "authors": detail.authors if detail else [],
                    "tk5_compatible": detail.tk5_compatible if detail else False,
                    "requires_modern_zos": detail.requires_modern_zos if detail else False,
                    "options": [opt.model_dump() for opt in detail.options] if detail else []
                }
            )

            self.graph.add_node(node)
            count += 1

        return count

    def get_from_graph(self, full_path: str) -> Node | None:
        """Get a module node from the graph.

        Args:
            full_path: Full module path (e.g., auxiliary/admin/mainframe/tk5_jcl_submit)

        Returns:
            Module node, or None if not found
        """
        node_id = f"msf-{full_path.replace('/', '-')}"
        return self.graph.get_node(node_id)
```

- [ ] **Step 4: Run catalog tests**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/msf/test_catalog.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add bigiron/msf/catalog.py bigiron/tests/msf/test_catalog.py
git commit -m "feat(msf): add CatalogService for module import

CatalogService provides:
- search: Find modules by query and type
- get_module: Get full module details
- sync_to_graph: Import modules as graph nodes
- Demo mode with built-in module data
- Live mode queries MSF RPC"
```

---

## Task 4: Authorization Model

**Files:**
- Create: `bigiron/msf/authorization.py`
- Create: `bigiron/tests/msf/test_authorization.py`

- [ ] **Step 1: Write failing test for Authorization**

```python
# bigiron/tests/msf/test_authorization.py
import pytest
from datetime import datetime, timezone, timedelta


def test_authorization_creation():
    from bigiron.msf.authorization import Authorization

    auth = Authorization(
        engagement_ref="ENG-2026-001",
        operator="w00t3k",
        approved_modules=["auxiliary/admin/mainframe/*"],
        scope=["127.0.0.1", "10.0.0.0/24"]
    )

    assert auth.engagement_ref == "ENG-2026-001"
    assert auth.operator == "w00t3k"
    assert auth.is_valid is True


def test_authorization_expired():
    from bigiron.msf.authorization import Authorization

    auth = Authorization(
        engagement_ref="ENG-2026-001",
        operator="w00t3k",
        approved_modules=["*"],
        scope=["*"],
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
    )

    assert auth.is_valid is False
    assert auth.is_expired is True


def test_authorization_module_approved():
    from bigiron.msf.authorization import Authorization

    auth = Authorization(
        engagement_ref="ENG-2026-001",
        operator="w00t3k",
        approved_modules=[
            "auxiliary/admin/mainframe/*",
            "auxiliary/scanner/mainframe/tso_enum"
        ],
        scope=["*"]
    )

    # Exact match
    assert auth.is_module_approved("auxiliary/scanner/mainframe/tso_enum") is True

    # Wildcard match
    assert auth.is_module_approved("auxiliary/admin/mainframe/tk5_jcl_submit") is True

    # Not approved
    assert auth.is_module_approved("exploit/mainframe/dangerous") is False


def test_authorization_target_in_scope():
    from bigiron.msf.authorization import Authorization

    auth = Authorization(
        engagement_ref="ENG-2026-001",
        operator="w00t3k",
        approved_modules=["*"],
        scope=["127.0.0.1", "10.0.0.0/24"]
    )

    assert auth.is_target_in_scope("127.0.0.1") is True
    assert auth.is_target_in_scope("10.0.0.5") is True
    assert auth.is_target_in_scope("192.168.1.1") is False


def test_authorization_wildcard_scope():
    from bigiron.msf.authorization import Authorization

    auth = Authorization(
        engagement_ref="ENG-2026-001",
        operator="w00t3k",
        approved_modules=["*"],
        scope=["*"]  # Everything approved
    )

    assert auth.is_target_in_scope("192.168.1.1") is True
    assert auth.is_target_in_scope("any.host.com") is True


def test_authorization_to_graph_node():
    from bigiron.msf.authorization import Authorization
    from bigiron.core.schema import NodeType

    auth = Authorization(
        engagement_ref="ENG-2026-001",
        operator="w00t3k",
        approved_modules=["*"],
        scope=["*"]
    )

    node = auth.to_node()

    assert node.node_type == NodeType.AUTHORIZATION
    assert node.properties["engagement_ref"] == "ENG-2026-001"
    assert node.properties["operator"] == "w00t3k"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/msf/test_authorization.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Implement Authorization model**

```python
# bigiron/msf/authorization.py
"""Authorization model and gate for module execution."""
import fnmatch
import ipaddress
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field

from ..core.schema import Node, NodeType


class Authorization(BaseModel):
    """Authorization for module execution.

    All module executions must be authorized. The authorization
    specifies which modules can run, against which targets, and
    tracks who approved the action.
    """

    id: str = Field(default_factory=lambda: f"auth-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
    engagement_ref: str
    operator: str
    approved_modules: list[str]  # Glob patterns like "auxiliary/admin/*"
    scope: list[str]  # IPs, CIDRs, or "*" for all
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    notes: str = ""

    @property
    def is_expired(self) -> bool:
        """Check if authorization has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if authorization is currently valid."""
        return not self.is_expired

    def is_module_approved(self, module_path: str) -> bool:
        """Check if a module is approved for execution.

        Args:
            module_path: Full module path (e.g., auxiliary/admin/mainframe/tk5_jcl_submit)

        Returns:
            True if the module matches any approved pattern
        """
        for pattern in self.approved_modules:
            if pattern == "*":
                return True
            if fnmatch.fnmatch(module_path, pattern):
                return True
        return False

    def is_target_in_scope(self, target: str) -> bool:
        """Check if a target is within authorized scope.

        Args:
            target: IP address or hostname

        Returns:
            True if target is in scope
        """
        for scope_item in self.scope:
            if scope_item == "*":
                return True

            # Try exact match first
            if target == scope_item:
                return True

            # Try CIDR match
            try:
                if "/" in scope_item:
                    network = ipaddress.ip_network(scope_item, strict=False)
                    target_ip = ipaddress.ip_address(target)
                    if target_ip in network:
                        return True
            except ValueError:
                # Not a valid IP/CIDR, skip
                pass

        return False

    def validate_execution(self, module_path: str, target: str) -> tuple[bool, str]:
        """Validate that an execution is authorized.

        Args:
            module_path: Full module path
            target: Target host

        Returns:
            Tuple of (is_valid, reason)
        """
        if not self.is_valid:
            return False, "Authorization has expired"

        if not self.is_module_approved(module_path):
            return False, f"Module {module_path} not in approved list"

        if not self.is_target_in_scope(target):
            return False, f"Target {target} not in authorized scope"

        return True, "Authorized"

    def to_node(self) -> Node:
        """Convert to a graph node for persistence."""
        return Node(
            id=self.id,
            node_type=NodeType.AUTHORIZATION,
            label=f"Auth: {self.engagement_ref}",
            properties={
                "engagement_ref": self.engagement_ref,
                "operator": self.operator,
                "approved_modules": self.approved_modules,
                "scope": self.scope,
                "expires_at": self.expires_at.isoformat() if self.expires_at else None,
                "notes": self.notes
            }
        )


class AuthorizationGate:
    """Gate that enforces authorization before execution."""

    def __init__(self, authorization: Authorization):
        """Initialize gate with an authorization.

        Args:
            authorization: The authorization to enforce
        """
        self.authorization = authorization

    def check(self, module_path: str, target: str) -> tuple[bool, str]:
        """Check if execution is allowed.

        Args:
            module_path: Full module path
            target: Target host

        Returns:
            Tuple of (allowed, reason)
        """
        return self.authorization.validate_execution(module_path, target)

    def require(self, module_path: str, target: str):
        """Require authorization or raise exception.

        Args:
            module_path: Full module path
            target: Target host

        Raises:
            PermissionError: If not authorized
        """
        allowed, reason = self.check(module_path, target)
        if not allowed:
            raise PermissionError(f"Execution not authorized: {reason}")
```

- [ ] **Step 4: Run authorization tests**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/msf/test_authorization.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add bigiron/msf/authorization.py bigiron/tests/msf/test_authorization.py
git commit -m "feat(msf): add Authorization model and gate

Authorization system:
- Module approval via glob patterns
- Scope validation (IP, CIDR, wildcard)
- Expiration tracking
- Conversion to graph node
- AuthorizationGate for enforcement"
```

---

## Task 5: Executor Service

**Files:**
- Create: `bigiron/msf/executor.py`
- Create: `bigiron/tests/msf/test_executor.py`

- [ ] **Step 1: Write failing test for ExecutorService**

```python
# bigiron/tests/msf/test_executor.py
import pytest
from datetime import datetime, timezone


def test_executor_preview():
    from bigiron.msf.executor import ExecutorService
    from bigiron.msf.client import MsfClient
    from bigiron.msf.catalog import CatalogService
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)  # Demo mode
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)

    executor = ExecutorService(client=client, graph=graph, catalog=catalog)

    preview = executor.preview(
        mtype="auxiliary",
        path="admin/mainframe/tk5_jcl_submit",
        options={"RHOSTS": "127.0.0.1"}
    )

    assert preview is not None
    assert "use auxiliary/admin/mainframe/tk5_jcl_submit" in preview.command
    assert "set RHOSTS 127.0.0.1" in preview.command

    graph.close()


def test_executor_run_requires_authorization():
    from bigiron.msf.executor import ExecutorService
    from bigiron.msf.client import MsfClient
    from bigiron.msf.catalog import CatalogService
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)

    executor = ExecutorService(client=client, graph=graph, catalog=catalog)

    # Try to run without authorization
    with pytest.raises(PermissionError, match="No authorization provided"):
        executor.run(
            mtype="auxiliary",
            path="admin/mainframe/tk5_jcl_submit",
            options={"RHOSTS": "127.0.0.1"}
        )

    graph.close()


def test_executor_run_with_authorization_demo():
    from bigiron.msf.executor import ExecutorService
    from bigiron.msf.client import MsfClient
    from bigiron.msf.catalog import CatalogService
    from bigiron.msf.authorization import Authorization
    from bigiron.core.graph import ProvenanceGraph
    from bigiron.core.schema import NodeType

    client = MsfClient(password=None)  # Demo mode
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)

    executor = ExecutorService(client=client, graph=graph, catalog=catalog)

    auth = Authorization(
        engagement_ref="ENG-2026-001",
        operator="w00t3k",
        approved_modules=["auxiliary/admin/mainframe/*"],
        scope=["127.0.0.1"]
    )

    result = executor.run(
        mtype="auxiliary",
        path="admin/mainframe/tk5_jcl_submit",
        options={"RHOSTS": "127.0.0.1"},
        authorization=auth
    )

    assert result.success is True
    assert "JOB" in result.output  # Should have job ID in output
    assert result.job_id is not None

    # Verify ModuleRun node was created
    runs = list(graph.get_nodes_by_type(NodeType.MODULE_RUN))
    assert len(runs) == 1
    assert runs[0].provenance.authorization_ref == auth.id

    graph.close()


def test_executor_run_unauthorized_module():
    from bigiron.msf.executor import ExecutorService
    from bigiron.msf.client import MsfClient
    from bigiron.msf.catalog import CatalogService
    from bigiron.msf.authorization import Authorization
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)

    executor = ExecutorService(client=client, graph=graph, catalog=catalog)

    auth = Authorization(
        engagement_ref="ENG-2026-001",
        operator="w00t3k",
        approved_modules=["auxiliary/scanner/*"],  # Only scanners approved
        scope=["127.0.0.1"]
    )

    with pytest.raises(PermissionError, match="not in approved list"):
        executor.run(
            mtype="auxiliary",
            path="admin/mainframe/tk5_jcl_submit",  # admin module not approved
            options={"RHOSTS": "127.0.0.1"},
            authorization=auth
        )

    graph.close()


def test_executor_run_target_out_of_scope():
    from bigiron.msf.executor import ExecutorService
    from bigiron.msf.client import MsfClient
    from bigiron.msf.catalog import CatalogService
    from bigiron.msf.authorization import Authorization
    from bigiron.core.graph import ProvenanceGraph

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)

    executor = ExecutorService(client=client, graph=graph, catalog=catalog)

    auth = Authorization(
        engagement_ref="ENG-2026-001",
        operator="w00t3k",
        approved_modules=["*"],
        scope=["10.0.0.0/24"]  # Only 10.0.0.x in scope
    )

    with pytest.raises(PermissionError, match="not in authorized scope"):
        executor.run(
            mtype="auxiliary",
            path="admin/mainframe/tk5_jcl_submit",
            options={"RHOSTS": "192.168.1.1"},  # Out of scope
            authorization=auth
        )

    graph.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/msf/test_executor.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Implement ExecutorService**

```python
# bigiron/msf/executor.py
"""Executor service for running MSF modules with authorization."""
import re
import time
from datetime import datetime, timezone
from typing import Any

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
```

- [ ] **Step 4: Run executor tests**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/msf/test_executor.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add bigiron/msf/executor.py bigiron/tests/msf/test_executor.py
git commit -m "feat(msf): add ExecutorService with auth gate

ExecutorService provides:
- preview: Show what will run (no auth needed)
- run: Execute with authorization gate
- Full provenance recording in graph
- Demo mode with canned output
- Live mode via MSF RPC console"
```

---

## Task 6: Output Parsers

**Files:**
- Create: `bigiron/msf/parsers/__init__.py`
- Create: `bigiron/msf/parsers/base.py`
- Create: `bigiron/msf/parsers/registry.py`
- Create: `bigiron/msf/parsers/tso.py`
- Create: `bigiron/msf/parsers/jcl.py`
- Create: `bigiron/msf/parsers/generic.py`
- Create: `bigiron/tests/msf/test_parsers.py`

- [ ] **Step 1: Create parser package structure**

```bash
mkdir -p bigiron/msf/parsers
touch bigiron/msf/parsers/__init__.py
```

- [ ] **Step 2: Write failing test for parsers**

```python
# bigiron/tests/msf/test_parsers.py
import pytest


def test_parser_registry_decorator():
    from bigiron.msf.parsers.registry import parser_for, get_parser
    from bigiron.msf.parsers.base import OutputParser

    @parser_for("test/module")
    class TestParser(OutputParser):
        def parse(self, output: str) -> list[dict]:
            return [{"type": "test", "value": "parsed"}]

    parser = get_parser("test/module")
    assert parser is not None

    result = parser.parse("test output")
    assert len(result) == 1
    assert result[0]["type"] == "test"


def test_tso_parser():
    from bigiron.msf.parsers.tso import TSOEnumParser

    output = """
[*] Enumerating TSO users...
[+] Valid user found: HERC01
[+] Valid user found: IBMUSER
[-] Invalid user: TESTUSER
[*] Enumeration complete
"""

    parser = TSOEnumParser()
    entities = parser.parse(output)

    assert len(entities) == 2
    usernames = [e["label"] for e in entities]
    assert "HERC01" in usernames
    assert "IBMUSER" in usernames


def test_jcl_parser():
    from bigiron.msf.parsers.jcl import JCLOutputParser

    output = """
[*] Submitting JCL...
[+] Job submitted successfully
[+] JOB ID: JOB00042
[+] Return code: 0000
"""

    parser = JCLOutputParser()
    entities = parser.parse(output)

    # Should find the job
    jobs = [e for e in entities if e["node_type"] == "job"]
    assert len(jobs) == 1
    assert jobs[0]["label"] == "JOB00042"
    assert jobs[0]["properties"]["return_code"] == "0000"


def test_generic_parser():
    from bigiron.msf.parsers.generic import GenericParser

    output = """
[+] Found user: ADMIN
[+] Dataset: SYS1.PARMLIB
[+] Transaction: CEMT
"""

    parser = GenericParser()
    entities = parser.parse(output)

    # Should extract something
    assert len(entities) >= 1


def test_get_parser_fallback():
    from bigiron.msf.parsers.registry import get_parser

    # Unknown module should return generic parser
    parser = get_parser("unknown/nonexistent/module")
    assert parser is not None
    assert parser.__class__.__name__ == "GenericParser"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/msf/test_parsers.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 4: Implement base parser and registry**

```python
# bigiron/msf/parsers/base.py
"""Base class for output parsers."""
from abc import ABC, abstractmethod
from typing import Any


class OutputParser(ABC):
    """Base class for module output parsers.

    Parsers extract entities from module output and return them
    as dictionaries ready to become graph nodes.
    """

    @abstractmethod
    def parse(self, output: str) -> list[dict[str, Any]]:
        """Parse module output and extract entities.

        Args:
            output: Raw module output text

        Returns:
            List of entity dictionaries with:
            - node_type: The NodeType value (as string)
            - label: Human-readable label
            - properties: Additional properties dict
        """
        pass
```

```python
# bigiron/msf/parsers/registry.py
"""Parser registry with decorator for registration."""
from typing import Type, Callable
from .base import OutputParser

# Global registry
_PARSERS: dict[str, Type[OutputParser]] = {}


def parser_for(module_pattern: str) -> Callable[[Type[OutputParser]], Type[OutputParser]]:
    """Decorator to register a parser for a module pattern.

    Args:
        module_pattern: Module path pattern (can use * for wildcard)

    Returns:
        Decorator function
    """
    def decorator(cls: Type[OutputParser]) -> Type[OutputParser]:
        _PARSERS[module_pattern] = cls
        return cls
    return decorator


def get_parser(module_path: str) -> OutputParser:
    """Get the appropriate parser for a module.

    Args:
        module_path: Full module path

    Returns:
        Parser instance (GenericParser if no specific parser found)
    """
    # Try exact match first
    if module_path in _PARSERS:
        return _PARSERS[module_path]()

    # Try pattern matching
    import fnmatch
    for pattern, parser_cls in _PARSERS.items():
        if fnmatch.fnmatch(module_path, pattern):
            return parser_cls()

    # Fallback to generic parser
    from .generic import GenericParser
    return GenericParser()
```

- [ ] **Step 5: Implement TSO parser**

```python
# bigiron/msf/parsers/tso.py
"""Parser for TSO enumeration output."""
import re
from typing import Any

from .base import OutputParser
from .registry import parser_for


@parser_for("auxiliary/scanner/mainframe/tso_enum")
@parser_for("*/tso_enum")
class TSOEnumParser(OutputParser):
    """Parses TSO user enumeration output."""

    # Pattern for valid user lines
    USER_PATTERN = re.compile(r'\[\+\]\s*(?:Valid user found|Found):\s*(\w+)', re.IGNORECASE)

    def parse(self, output: str) -> list[dict[str, Any]]:
        """Extract discovered TSO users from output."""
        entities = []

        for match in self.USER_PATTERN.finditer(output):
            username = match.group(1).upper()
            entities.append({
                "node_type": "user",
                "label": username,
                "properties": {
                    "source": "tso_enum",
                    "username": username
                }
            })

        return entities
```

- [ ] **Step 6: Implement JCL parser**

```python
# bigiron/msf/parsers/jcl.py
"""Parser for JCL submission output."""
import re
from typing import Any

from .base import OutputParser
from .registry import parser_for


@parser_for("auxiliary/admin/mainframe/tk5_jcl_submit")
@parser_for("auxiliary/scanner/mainframe/ftp_jcl_creds")
@parser_for("*/*jcl*")
class JCLOutputParser(OutputParser):
    """Parses JCL job submission output."""

    JOB_ID_PATTERN = re.compile(r'JOB\s*(?:ID)?[:\s]*([A-Z0-9]+)', re.IGNORECASE)
    RETURN_CODE_PATTERN = re.compile(r'(?:Return|RC|Condition)\s*code[:\s]*(\d+)', re.IGNORECASE)
    DATASET_PATTERN = re.compile(r'([A-Z][A-Z0-9]*(?:\.[A-Z][A-Z0-9]*)+)', re.IGNORECASE)

    def parse(self, output: str) -> list[dict[str, Any]]:
        """Extract job info and datasets from JCL output."""
        entities = []

        # Find job ID
        job_match = self.JOB_ID_PATTERN.search(output)
        if job_match:
            job_id = job_match.group(1).upper()

            # Find return code if present
            rc_match = self.RETURN_CODE_PATTERN.search(output)
            return_code = rc_match.group(1) if rc_match else None

            entities.append({
                "node_type": "job",
                "label": job_id,
                "properties": {
                    "job_id": job_id,
                    "return_code": return_code,
                    "source": "jcl_submit"
                }
            })

        # Find datasets mentioned
        seen_datasets = set()
        for match in self.DATASET_PATTERN.finditer(output):
            dsn = match.group(1).upper()
            # Filter out common false positives
            if dsn in seen_datasets or len(dsn) < 5:
                continue
            if any(x in dsn for x in ["HTTP", "HTTPS", "FTP"]):
                continue

            seen_datasets.add(dsn)
            entities.append({
                "node_type": "dataset",
                "label": dsn,
                "properties": {
                    "dsn": dsn,
                    "source": "jcl_output"
                }
            })

        return entities
```

- [ ] **Step 7: Implement generic parser**

```python
# bigiron/msf/parsers/generic.py
"""Generic fallback parser for unknown modules."""
import re
from typing import Any

from .base import OutputParser


class GenericParser(OutputParser):
    """Fallback parser that extracts common patterns."""

    PATTERNS = [
        # Users
        (re.compile(r'(?:user|username|userid)[:\s]+(\w+)', re.I), "user"),
        # Datasets
        (re.compile(r'([A-Z][A-Z0-9]*(?:\.[A-Z][A-Z0-9]*){2,})', re.I), "dataset"),
        # Jobs
        (re.compile(r'JOB[:\s]*([A-Z0-9]{5,8})', re.I), "job"),
        # Transactions
        (re.compile(r'(?:transaction|tran)[:\s]+(\w{4})', re.I), "transaction"),
        # IPs
        (re.compile(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', re.I), "host"),
    ]

    def parse(self, output: str) -> list[dict[str, Any]]:
        """Extract entities using generic patterns."""
        entities = []
        seen = set()

        for pattern, node_type in self.PATTERNS:
            for match in pattern.finditer(output):
                value = match.group(1)
                key = f"{node_type}:{value}"

                if key in seen:
                    continue
                seen.add(key)

                entities.append({
                    "node_type": node_type,
                    "label": value,
                    "properties": {
                        "source": "generic_parser",
                        "value": value
                    }
                })

        return entities
```

- [ ] **Step 8: Update parser package init**

```python
# bigiron/msf/parsers/__init__.py
"""Output parsers for extracting entities from module output."""
from .base import OutputParser
from .registry import parser_for, get_parser
from .tso import TSOEnumParser
from .jcl import JCLOutputParser
from .generic import GenericParser

__all__ = [
    "OutputParser",
    "parser_for",
    "get_parser",
    "TSOEnumParser",
    "JCLOutputParser",
    "GenericParser",
]
```

- [ ] **Step 9: Run parser tests**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/msf/test_parsers.py -v`
Expected: All 5 tests PASS

- [ ] **Step 10: Commit**

```bash
git add bigiron/msf/parsers/ bigiron/tests/msf/test_parsers.py
git commit -m "feat(msf): add output parser system

Parser system:
- Base OutputParser class
- Registry with @parser_for decorator
- TSOEnumParser: Extract users from TSO enum
- JCLOutputParser: Extract jobs/datasets from JCL output
- GenericParser: Fallback regex patterns"
```

---

## Task 7: MSF Package Exports and Integration Test

**Files:**
- Modify: `bigiron/msf/__init__.py`
- Create: `bigiron/tests/msf/test_integration.py`

- [ ] **Step 1: Update MSF package exports**

```python
# bigiron/msf/__init__.py
"""Metasploit integration layer."""
from .client import MsfClient
from .models import (
    ModuleSummary,
    ModuleDetail,
    ModuleOption,
    ExecutionPreview,
    ExecutionResult,
)
from .catalog import CatalogService
from .executor import ExecutorService
from .authorization import Authorization, AuthorizationGate
from .parsers import get_parser, parser_for, OutputParser

__all__ = [
    "MsfClient",
    "ModuleSummary",
    "ModuleDetail",
    "ModuleOption",
    "ExecutionPreview",
    "ExecutionResult",
    "CatalogService",
    "ExecutorService",
    "Authorization",
    "AuthorizationGate",
    "get_parser",
    "parser_for",
    "OutputParser",
]
```

- [ ] **Step 2: Write integration test**

```python
# bigiron/tests/msf/test_integration.py
"""Integration tests for MSF layer."""
import pytest
from bigiron.core.graph import ProvenanceGraph
from bigiron.core.schema import NodeType, EdgeType
from bigiron.msf import (
    MsfClient,
    CatalogService,
    ExecutorService,
    Authorization,
    get_parser,
)


def test_full_execution_workflow():
    """Test complete workflow: catalog -> authorize -> execute -> parse."""

    # Setup
    client = MsfClient(password=None)  # Demo mode
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)
    executor = ExecutorService(client=client, graph=graph, catalog=catalog)

    # 1. Sync modules to graph
    count = catalog.sync_to_graph("mainframe")
    assert count >= 5

    # 2. Search for a module
    results = catalog.search("tso_enum")
    assert len(results) >= 1
    module = results[0]

    # 3. Preview execution
    preview = executor.preview(
        mtype=module.mtype,
        path=module.path,
        options={"RHOSTS": "127.0.0.1"}
    )
    assert "use" in preview.command
    assert "RHOSTS" in preview.command

    # 4. Create authorization
    auth = Authorization(
        engagement_ref="ENG-TEST-001",
        operator="test_user",
        approved_modules=["auxiliary/scanner/mainframe/*"],
        scope=["127.0.0.1"]
    )

    # 5. Execute with authorization
    result = executor.run(
        mtype=module.mtype,
        path=module.path,
        options={"RHOSTS": "127.0.0.1"},
        authorization=auth
    )
    assert result.success is True

    # 6. Parse output
    parser = get_parser(f"{module.mtype}/{module.path}")
    entities = parser.parse(result.output)
    assert len(entities) >= 1  # Should find some users

    # 7. Verify graph state
    stats = graph.stats()

    # Should have: modules + auth + run + host
    assert stats["total_nodes"] >= 7

    # Should have edges: run->auth, run->module, run->host
    assert stats["total_edges"] >= 2

    # Verify module run was recorded
    runs = list(graph.get_nodes_by_type(NodeType.MODULE_RUN))
    assert len(runs) == 1
    assert runs[0].provenance.authorization_ref == auth.id

    # Verify authorization edge
    auth_edges = list(graph.get_edges_from(runs[0].id, EdgeType.AUTHORIZED_BY))
    assert len(auth_edges) == 1

    graph.close()


def test_parser_integration_with_graph():
    """Test parsing module output and adding entities to graph."""

    graph = ProvenanceGraph(":memory:")

    # Simulate TSO enum output
    output = """
[*] Enumerating TSO users...
[+] Valid user found: HERC01
[+] Valid user found: IBMUSER
[*] Enumeration complete
"""

    # Parse
    parser = get_parser("auxiliary/scanner/mainframe/tso_enum")
    entities = parser.parse(output)

    # Add to graph
    from bigiron.core.schema import Node, NodeType
    for entity in entities:
        node = Node(
            node_type=NodeType(entity["node_type"]),
            label=entity["label"],
            properties=entity["properties"]
        )
        graph.add_node(node)

    # Verify
    users = list(graph.get_nodes_by_type(NodeType.USER))
    assert len(users) == 2

    labels = {u.label for u in users}
    assert labels == {"HERC01", "IBMUSER"}

    graph.close()


def test_catalog_module_detail_to_graph_properties():
    """Verify module details are properly stored in graph nodes."""

    client = MsfClient(password=None)
    graph = ProvenanceGraph(":memory:")
    catalog = CatalogService(client=client, graph=graph)

    # Sync one module
    catalog.sync_to_graph("tk5_jcl_submit")

    # Get the module node
    nodes = list(graph.get_nodes_by_type(NodeType.MSF_MODULE))

    # Find the tk5 module
    tk5_node = None
    for node in nodes:
        if "tk5" in node.properties.get("path", ""):
            tk5_node = node
            break

    assert tk5_node is not None
    assert tk5_node.properties["tk5_compatible"] is True
    assert len(tk5_node.properties["options"]) >= 4

    graph.close()
```

- [ ] **Step 3: Run integration tests**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/msf/test_integration.py -v`
Expected: All 3 tests PASS

- [ ] **Step 4: Run full test suite**

Run: `source .venv/bin/activate && python -m pytest bigiron/tests/ -v`
Expected: All tests PASS (should be ~65+ tests)

- [ ] **Step 5: Commit**

```bash
git add bigiron/msf/__init__.py bigiron/tests/msf/test_integration.py
git commit -m "feat(msf): finalize MSF layer with integration tests

Complete MSF integration:
- Package exports from bigiron.msf
- Full workflow integration test
- Parser-to-graph integration test
- Module detail to node properties test"
```

- [ ] **Step 6: Push and tag**

```bash
git push
git tag -a v0.2.0-msf-integration -m "MSF integration layer complete"
git push --tags
```

---

## Summary

This plan implements the **MSF Integration Layer** - connecting BigIron to Metasploit. After completing these 7 tasks, you'll have:

- **MsfClient** - RPC connection with demo mode support
- **Module models** - ModuleSummary, ModuleDetail, options
- **Demo data** - Built-in module info for offline demos
- **CatalogService** - Import modules into graph as nodes
- **Authorization** - Module/target approval with gates
- **ExecutorService** - Run modules with auth and provenance
- **Parsers** - Extract entities from output (TSO, JCL, generic)

**Next plan**: Agent Layer (tool schema, loop, checkpoints)
