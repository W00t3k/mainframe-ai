"""Execution mode and module compatibility matrix."""
from enum import Enum
from typing import Literal
from pydantic import BaseModel


class ExecutionMode(str, Enum):
    """Execution mode for module runs."""
    LIVE = "live"
    RECORDED = "recorded"
    HYBRID = "hybrid"


class ModuleCompatibility(BaseModel):
    """Module compatibility information."""
    module_path: str
    works_on_tk5: bool | Literal["partial"] | None = None
    requires_modern_zos: bool = False
    demo_strategy: Literal["live", "recorded"] = "live"
    notes: str = ""


# Module compatibility matrix
# Key: full module path
# Value: compatibility info
COMPATIBILITY_MATRIX: dict[str, ModuleCompatibility] = {
    # TK5-compatible modules (live execution)
    "auxiliary/admin/mainframe/tk5_jcl_submit": ModuleCompatibility(
        module_path="auxiliary/admin/mainframe/tk5_jcl_submit",
        works_on_tk5=True,
        requires_modern_zos=False,
        demo_strategy="live",
        notes="Full TK5 JCL submission support"
    ),
    "auxiliary/scanner/mainframe/tso_enum": ModuleCompatibility(
        module_path="auxiliary/scanner/mainframe/tso_enum",
        works_on_tk5=True,
        requires_modern_zos=False,
        demo_strategy="live",
        notes="TSO user enumeration via FTP"
    ),
    "auxiliary/scanner/mainframe/vtam_enum": ModuleCompatibility(
        module_path="auxiliary/scanner/mainframe/vtam_enum",
        works_on_tk5=True,
        requires_modern_zos=False,
        demo_strategy="live",
        notes="VTAM APPLID enumeration"
    ),
    "auxiliary/scanner/mainframe/cics_enum": ModuleCompatibility(
        module_path="auxiliary/scanner/mainframe/cics_enum",
        works_on_tk5=True,
        requires_modern_zos=False,
        demo_strategy="live",
        notes="CICS enumeration via KICKS"
    ),
    "auxiliary/scanner/mainframe/ftp_jcl_creds": ModuleCompatibility(
        module_path="auxiliary/scanner/mainframe/ftp_jcl_creds",
        works_on_tk5=True,
        requires_modern_zos=False,
        demo_strategy="live",
        notes="FTP credential check with JES mode"
    ),
    "auxiliary/scanner/mainframe/jes_enum": ModuleCompatibility(
        module_path="auxiliary/scanner/mainframe/jes_enum",
        works_on_tk5=True,
        requires_modern_zos=False,
        demo_strategy="live",
        notes="JES2 job enumeration"
    ),

    # Partial TK5 support (RAKF vs RACF)
    "auxiliary/scanner/mainframe/racf_profile_check": ModuleCompatibility(
        module_path="auxiliary/scanner/mainframe/racf_profile_check",
        works_on_tk5="partial",
        requires_modern_zos=True,
        demo_strategy="recorded",
        notes="TK5 uses RAKF (subset). Full RACF requires z/OS."
    ),

    # Modern z/OS only (recorded playback)
    "auxiliary/scanner/mainframe/racf_enum": ModuleCompatibility(
        module_path="auxiliary/scanner/mainframe/racf_enum",
        works_on_tk5=False,
        requires_modern_zos=True,
        demo_strategy="recorded",
        notes="Full RACF enumeration requires z/OS"
    ),
    "auxiliary/scanner/mainframe/db2_enum": ModuleCompatibility(
        module_path="auxiliary/scanner/mainframe/db2_enum",
        works_on_tk5=False,
        requires_modern_zos=True,
        demo_strategy="recorded",
        notes="DB2 not available on TK5"
    ),
    "auxiliary/scanner/mainframe/mq_enum": ModuleCompatibility(
        module_path="auxiliary/scanner/mainframe/mq_enum",
        works_on_tk5=False,
        requires_modern_zos=True,
        demo_strategy="recorded",
        notes="MQ Series not available on TK5"
    ),
    "exploit/mainframe/ftp/ftp_jcl_injection": ModuleCompatibility(
        module_path="exploit/mainframe/ftp/ftp_jcl_injection",
        works_on_tk5=True,
        requires_modern_zos=False,
        demo_strategy="live",
        notes="JCL injection via FTP JES mode"
    ),
}


def get_compatibility(module_path: str) -> ModuleCompatibility:
    """Get compatibility info for a module.

    Args:
        module_path: Full module path (e.g., auxiliary/admin/mainframe/tk5_jcl_submit)

    Returns:
        ModuleCompatibility with info, or default for unknown modules
    """
    if module_path in COMPATIBILITY_MATRIX:
        return COMPATIBILITY_MATRIX[module_path]

    # Default for unknown modules: assume live is possible
    return ModuleCompatibility(
        module_path=module_path,
        works_on_tk5=None,
        requires_modern_zos=False,
        demo_strategy="live",
        notes="Unknown module - defaulting to live execution"
    )


def should_use_recording(
    module_path: str,
    mode: ExecutionMode,
    live_available: bool = True
) -> bool:
    """Determine if a module should use recorded playback.

    Args:
        module_path: Full module path
        mode: Current execution mode
        live_available: Whether live MSF is available

    Returns:
        True if should use recording, False for live execution
    """
    if mode == ExecutionMode.LIVE:
        return False
    if mode == ExecutionMode.RECORDED:
        return True

    # Hybrid mode: check compatibility
    compat = get_compatibility(module_path)

    if not live_available:
        return True

    return compat.demo_strategy == "recorded"
