"""Authorization model for MSF module execution."""
from datetime import datetime, timezone
from typing import Any
from fnmatch import fnmatch
import ipaddress

from pydantic import BaseModel, Field, computed_field

from bigiron.core.schema import Node, NodeType, Provenance


class Authorization(BaseModel):
    """Authorization for module execution within an engagement."""

    id: str = Field(
        default_factory=lambda: f"auth-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    )
    engagement_ref: str
    operator: str
    approved_modules: list[str] = Field(default_factory=list)
    scope: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    notes: str = ""

    @computed_field
    @property
    def is_expired(self) -> bool:
        """Check if the authorization has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @computed_field
    @property
    def is_valid(self) -> bool:
        """Check if the authorization is currently valid."""
        return not self.is_expired

    def is_module_approved(self, module_path: str) -> bool:
        """Check if a module path is approved for execution.

        Args:
            module_path: Full module path (e.g., 'auxiliary/scanner/mainframe/tso_enum')

        Returns:
            True if the module is approved, False otherwise
        """
        for pattern in self.approved_modules:
            if fnmatch(module_path, pattern):
                return True
        return False

    def is_target_in_scope(self, target: str) -> bool:
        """Check if a target is within the authorized scope.

        Args:
            target: IP address, hostname, or CIDR

        Returns:
            True if the target is in scope, False otherwise
        """
        # Wildcard scope allows everything
        if "*" in self.scope:
            return True

        # Try to parse target as IP address
        try:
            target_ip = ipaddress.ip_address(target)
        except ValueError:
            # Not an IP address, check as hostname
            return target in self.scope

        # Check against each scope entry
        for scope_entry in self.scope:
            if scope_entry == "*":
                return True

            try:
                # Try as exact IP
                if ipaddress.ip_address(scope_entry) == target_ip:
                    return True
            except ValueError:
                pass

            try:
                # Try as CIDR network
                network = ipaddress.ip_network(scope_entry, strict=False)
                if target_ip in network:
                    return True
            except ValueError:
                # Not an IP or CIDR, skip
                pass

        return False

    def validate_execution(
        self, module_path: str, target: str
    ) -> tuple[bool, str]:
        """Validate that a module execution is authorized.

        Args:
            module_path: Full module path
            target: Target IP or hostname

        Returns:
            Tuple of (is_valid, message)
        """
        if not self.is_valid:
            return False, "Authorization has expired"

        if not self.is_module_approved(module_path):
            return False, f"Module '{module_path}' is not in approved list"

        if not self.is_target_in_scope(target):
            return False, f"Target '{target}' is not in authorized scope"

        return True, "Execution authorized"

    def to_node(self) -> Node:
        """Convert authorization to a graph node.

        Returns:
            Node representation of this authorization
        """
        return Node(
            id=self.id,
            node_type=NodeType.AUTHORIZATION,
            label=f"Authorization: {self.engagement_ref}",
            properties={
                "engagement_ref": self.engagement_ref,
                "operator": self.operator,
                "approved_modules": self.approved_modules,
                "scope": self.scope,
                "expires_at": self.expires_at.isoformat() if self.expires_at else None,
                "notes": self.notes,
            },
            provenance=Provenance(
                timestamp=self.created_at,
                authorization_ref=self.id,
            ),
            created_at=self.created_at,
        )


class AuthorizationError(Exception):
    """Raised when an operation is not authorized."""

    def __init__(self, message: str, authorization: Authorization | None = None):
        super().__init__(message)
        self.authorization = authorization


class AuthorizationGate:
    """Gate for checking and requiring authorization before execution."""

    def __init__(self, authorization: Authorization):
        """Initialize the gate with an authorization.

        Args:
            authorization: The authorization to check against
        """
        self.authorization = authorization

    def check(self, module_path: str, target: str) -> tuple[bool, str]:
        """Check if execution is authorized without raising.

        Args:
            module_path: Full module path
            target: Target IP or hostname

        Returns:
            Tuple of (is_authorized, message)
        """
        return self.authorization.validate_execution(module_path, target)

    def require(self, module_path: str, target: str) -> None:
        """Require authorization for execution, raising if not authorized.

        Args:
            module_path: Full module path
            target: Target IP or hostname

        Raises:
            AuthorizationError: If execution is not authorized
        """
        is_authorized, message = self.check(module_path, target)
        if not is_authorized:
            raise AuthorizationError(message, self.authorization)
