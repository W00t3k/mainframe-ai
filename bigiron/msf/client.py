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
