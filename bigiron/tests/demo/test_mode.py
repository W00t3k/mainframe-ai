# bigiron/tests/demo/test_mode.py
import pytest


def test_execution_mode_enum():
    from bigiron.demo.mode import ExecutionMode

    assert ExecutionMode.LIVE.value == "live"
    assert ExecutionMode.RECORDED.value == "recorded"
    assert ExecutionMode.HYBRID.value == "hybrid"


def test_module_compatibility_tk5():
    from bigiron.demo.mode import ModuleCompatibility, get_compatibility

    compat = get_compatibility("auxiliary/admin/mainframe/tk5_jcl_submit")

    assert compat.works_on_tk5 is True
    assert compat.requires_modern_zos is False
    assert compat.demo_strategy == "live"


def test_module_compatibility_racf():
    from bigiron.demo.mode import get_compatibility

    compat = get_compatibility("auxiliary/scanner/mainframe/racf_enum")

    assert compat.works_on_tk5 is False
    assert compat.requires_modern_zos is True
    assert compat.demo_strategy == "recorded"


def test_module_compatibility_partial():
    from bigiron.demo.mode import get_compatibility

    # RAKF on TK5 is partial RACF
    compat = get_compatibility("auxiliary/scanner/mainframe/racf_profile_check")

    assert compat.works_on_tk5 == "partial"
    assert compat.demo_strategy == "recorded"


def test_module_compatibility_unknown():
    from bigiron.demo.mode import get_compatibility

    compat = get_compatibility("auxiliary/scanner/mainframe/unknown_module")

    assert compat.works_on_tk5 is None
    assert compat.demo_strategy == "live"  # Default to live for unknown


def test_compatibility_matrix_mainframe_modules():
    from bigiron.demo.mode import COMPATIBILITY_MATRIX

    # Verify key modules are in the matrix
    assert "auxiliary/admin/mainframe/tk5_jcl_submit" in COMPATIBILITY_MATRIX
    assert "auxiliary/scanner/mainframe/tso_enum" in COMPATIBILITY_MATRIX
    assert "auxiliary/scanner/mainframe/vtam_enum" in COMPATIBILITY_MATRIX
