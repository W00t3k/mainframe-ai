"""Pydantic models for the provenance graph schema."""
from enum import Enum
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field
import uuid


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


class Provenance(BaseModel):
    """Provenance metadata attached to nodes and edges."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    authorization_ref: str | None = None
    agent_turn: int | None = None
    raw_output: str | None = None
    parsed_entities: list[str] = Field(default_factory=list)
    simulated: bool = False
    recording_id: str | None = None


class Node(BaseModel):
    """A node in the provenance graph."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    node_type: NodeType
    label: str
    properties: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance = Field(default_factory=Provenance)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Edge(BaseModel):
    """An edge in the provenance graph."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str
    target_id: str
    edge_type: EdgeType
    properties: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance = Field(default_factory=Provenance)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
