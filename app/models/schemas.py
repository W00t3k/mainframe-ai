"""
Pydantic Schemas for API Request/Response Models
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class ChatRequest(BaseModel):
    """Chat message request."""
    message: str
    context: Optional[str] = ""


class TerminalKeyRequest(BaseModel):
    """Terminal key input request."""
    key_type: str
    value: str = ""


class ConnectRequest(BaseModel):
    """Terminal connection request."""
    target: str = "localhost:3270"


class ScanRequest(BaseModel):
    """Scanner request."""
    target: str
    ports: str = ""


class ReconEnumerateRequest(BaseModel):
    """Recon enumeration request."""
    module: str = "tso"
    wordlist: Optional[List[str]] = None
    command_sequence: Optional[List[str]] = None


class ReconMapRequest(BaseModel):
    """Recon mapping request."""
    max_depth: int = 3


class ReconReportRequest(BaseModel):
    """Recon report generation request."""
    format: str = "json"
    enumerate_results: List[Dict] = []
    hidden_fields: List[Dict] = []
    screen_findings: List[Dict] = []
    map_tree: List[Dict] = []


class RAGQueryRequest(BaseModel):
    """RAG query request."""
    query: str
    n_results: int = 3
    include_highlights: bool = True


class GraphIngestRequest(BaseModel):
    """Graph ingestion request."""
    source: str = "manual_upload"


class JCLIngestRequest(GraphIngestRequest):
    """JCL ingestion request."""
    jcl: str


class SysoutIngestRequest(GraphIngestRequest):
    """SYSOUT ingestion request."""
    sysout: str


class FindingRequest(BaseModel):
    """Finding generation request."""
    title: str = "Untitled Finding"
    evidence: List[Dict] = []
    reasoning: str = ""
    confidence: str = "MEDIUM"
    graph_context: Dict = {}


class TutorRequest(BaseModel):
    """Tutor API request."""
    goal: str = "free-explore"
    tutor_id: str = "mentor"
    question: str = ""
    module: str = "free-explore"
    step: Dict = {}
    event: str = "ask"


class PathRequest(BaseModel):
    """Learning path request."""
    path: Dict = {}
    tutor_id: str = "mentor"
    question: str = ""
    screen: str = ""


class WalkthroughRequest(BaseModel):
    """Walkthrough request."""
    name: str = "session-stack"
    target: str = "localhost:3270"
    speed: float = 4.0
