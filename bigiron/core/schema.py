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
