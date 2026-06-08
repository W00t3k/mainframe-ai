"""Authorization model and gate for module execution."""
import fnmatch
import ipaddress
from datetime import datetime, timezone
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
