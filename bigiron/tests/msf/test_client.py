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
