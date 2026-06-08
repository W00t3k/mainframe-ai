"""Tests for output parsers."""
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
