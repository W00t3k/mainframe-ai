"""Demo data for offline/conference demos.

This module provides sample MSF module data for use when no Metasploit
instance is available, such as during conference demos or offline testing.
"""
from bigiron.msf.models import ModuleDetail, ModuleOption, ModuleSummary


# Demo module summaries for search results
DEMO_MODULES: list[ModuleSummary] = [
    ModuleSummary(
        mtype="auxiliary",
        path="scanner/mainframe/ftp_jcl_creds",
        name="FTP JCL Credential Scanner",
        rank="normal",
    ),
    ModuleSummary(
        mtype="auxiliary",
        path="admin/mainframe/tk5_jcl_submit",
        name="TK5 JCL Job Submission",
        rank="normal",
    ),
    ModuleSummary(
        mtype="auxiliary",
        path="scanner/mainframe/tso_enum",
        name="TSO User Enumeration",
        rank="normal",
    ),
    ModuleSummary(
        mtype="auxiliary",
        path="scanner/mainframe/vtam_enum",
        name="VTAM Application Enumeration",
        rank="normal",
    ),
    ModuleSummary(
        mtype="auxiliary",
        path="scanner/mainframe/cics_enum",
        name="CICS Transaction Enumeration",
        rank="normal",
    ),
    ModuleSummary(
        mtype="auxiliary",
        path="scanner/mainframe/jes_enum",
        name="JES Job Queue Enumeration",
        rank="normal",
    ),
]


# Full module details with options
_DEMO_MODULE_DETAILS: dict[str, ModuleDetail] = {
    "auxiliary/scanner/mainframe/ftp_jcl_creds": ModuleDetail(
        mtype="auxiliary",
        path="scanner/mainframe/ftp_jcl_creds",
        name="FTP JCL Credential Scanner",
        rank="normal",
        description="Scans for JCL job submission capabilities via FTP. "
                    "Tests whether the target allows JCL submission through "
                    "the FTP JES interface.",
        authors=["w00t3k", "mainframed767"],
        references=[
            {"type": "URL", "ref": "https://www.ibm.com/docs/en/zos/2.5.0?topic=ftp-submitting-jobs-jcl"},
        ],
        options=[
            ModuleOption(
                name="RHOSTS",
                required=True,
                description="Target host(s)",
                default=None,
            ),
            ModuleOption(
                name="RPORT",
                required=True,
                description="FTP port",
                default="21",
            ),
            ModuleOption(
                name="USERNAME",
                required=True,
                description="FTP username",
                default=None,
            ),
            ModuleOption(
                name="PASSWORD",
                required=True,
                description="FTP password",
                default=None,
            ),
        ],
        targets=["MVS 3.8j", "z/OS 2.x", "z/OS 3.x"],
        platform="mainframe",
        tk5_compatible=True,
        requires_modern_zos=False,
    ),
    "auxiliary/admin/mainframe/tk5_jcl_submit": ModuleDetail(
        mtype="auxiliary",
        path="admin/mainframe/tk5_jcl_submit",
        name="TK5 JCL Job Submission",
        rank="normal",
        description="Submits JCL jobs to a TK5/Hercules MVS 3.8j system via FTP. "
                    "Designed for use with the TK5 demo environment.",
        authors=["w00t3k"],
        references=[
            {"type": "URL", "ref": "https://github.com/MVS-sysgen/TK5"},
        ],
        options=[
            ModuleOption(
                name="RHOSTS",
                required=True,
                description="TK5 host address",
                default="localhost",
            ),
            ModuleOption(
                name="RPORT",
                required=True,
                description="FTP port",
                default="2121",
            ),
            ModuleOption(
                name="USERNAME",
                required=True,
                description="TSO/FTP username",
                default="HERC01",
            ),
            ModuleOption(
                name="PASSWORD",
                required=True,
                description="TSO/FTP password",
                default="CUL8TR",
            ),
            ModuleOption(
                name="JCL",
                required=True,
                description="JCL to submit (content or file path)",
                default=None,
            ),
        ],
        targets=["MVS 3.8j (TK5)"],
        platform="mainframe",
        tk5_compatible=True,
        requires_modern_zos=False,
    ),
    "auxiliary/scanner/mainframe/tso_enum": ModuleDetail(
        mtype="auxiliary",
        path="scanner/mainframe/tso_enum",
        name="TSO User Enumeration",
        rank="normal",
        description="Enumerates TSO users by attempting logon and analyzing "
                    "response messages. Identifies valid usernames without "
                    "requiring valid passwords.",
        authors=["mainframed767", "w00t3k"],
        references=[
            {"type": "URL", "ref": "https://www.ibm.com/docs/en/zos/2.5.0?topic=tso-logging-session"},
        ],
        options=[
            ModuleOption(
                name="RHOSTS",
                required=True,
                description="Target host(s)",
                default=None,
            ),
            ModuleOption(
                name="RPORT",
                required=True,
                description="TN3270 port",
                default="3270",
            ),
            ModuleOption(
                name="USER_FILE",
                required=False,
                description="File containing usernames to try",
                default=None,
            ),
        ],
        targets=["z/OS", "MVS 3.8j"],
        platform="mainframe",
        tk5_compatible=True,
        requires_modern_zos=False,
    ),
    "auxiliary/scanner/mainframe/vtam_enum": ModuleDetail(
        mtype="auxiliary",
        path="scanner/mainframe/vtam_enum",
        name="VTAM Application Enumeration",
        rank="normal",
        description="Enumerates VTAM applications available on the mainframe. "
                    "Identifies accessible applications like TSO, CICS, IMS.",
        authors=["mainframed767"],
        references=[
            {"type": "URL", "ref": "https://www.ibm.com/docs/en/zos/2.5.0?topic=vtam-overview"},
        ],
        options=[
            ModuleOption(
                name="RHOSTS",
                required=True,
                description="Target host(s)",
                default=None,
            ),
            ModuleOption(
                name="RPORT",
                required=True,
                description="TN3270 port",
                default="3270",
            ),
        ],
        targets=["z/OS", "MVS 3.8j"],
        platform="mainframe",
        tk5_compatible=True,
        requires_modern_zos=False,
    ),
    "auxiliary/scanner/mainframe/cics_enum": ModuleDetail(
        mtype="auxiliary",
        path="scanner/mainframe/cics_enum",
        name="CICS Transaction Enumeration",
        rank="normal",
        description="Enumerates available CICS transactions. Tests for "
                    "accessible transaction codes and their security settings.",
        authors=["mainframed767", "ayoul3"],
        references=[
            {"type": "URL", "ref": "https://www.ibm.com/docs/en/cics-ts/6.1?topic=transactions-overview"},
        ],
        options=[
            ModuleOption(
                name="RHOSTS",
                required=True,
                description="Target host(s)",
                default=None,
            ),
            ModuleOption(
                name="RPORT",
                required=True,
                description="TN3270 port",
                default="3270",
            ),
            ModuleOption(
                name="APPLID",
                required=True,
                description="CICS applid/region name",
                default="CICS",
            ),
            ModuleOption(
                name="TRANS_FILE",
                required=False,
                description="File containing transaction codes to test",
                default=None,
            ),
        ],
        targets=["z/OS with CICS"],
        platform="mainframe",
        tk5_compatible=False,
        requires_modern_zos=True,
    ),
    "auxiliary/scanner/mainframe/jes_enum": ModuleDetail(
        mtype="auxiliary",
        path="scanner/mainframe/jes_enum",
        name="JES Job Queue Enumeration",
        rank="normal",
        description="Enumerates the JES job queue. Lists jobs visible to the "
                    "authenticated user including job names, IDs, and status.",
        authors=["w00t3k"],
        references=[
            {"type": "URL", "ref": "https://www.ibm.com/docs/en/zos/2.5.0?topic=jes2-overview"},
        ],
        options=[
            ModuleOption(
                name="RHOSTS",
                required=True,
                description="Target host(s)",
                default=None,
            ),
            ModuleOption(
                name="RPORT",
                required=True,
                description="FTP port",
                default="21",
            ),
            ModuleOption(
                name="USERNAME",
                required=True,
                description="FTP/TSO username",
                default=None,
            ),
            ModuleOption(
                name="PASSWORD",
                required=True,
                description="FTP/TSO password",
                default=None,
            ),
            ModuleOption(
                name="OWNER",
                required=False,
                description="Filter jobs by owner (default: current user)",
                default="*",
            ),
        ],
        targets=["z/OS", "MVS 3.8j"],
        platform="mainframe",
        tk5_compatible=True,
        requires_modern_zos=False,
    ),
}


def get_demo_module_detail(mtype: str, path: str) -> ModuleDetail | None:
    """Get full module details for a demo module.

    Args:
        mtype: Module type (auxiliary, exploit, etc.)
        path: Module path without type prefix

    Returns:
        ModuleDetail if found, None otherwise
    """
    full_path = f"{mtype}/{path}"
    return _DEMO_MODULE_DETAILS.get(full_path)


# Demo execution output for simulated runs
DEMO_EXECUTION_OUTPUT: dict[str, str] = {
    "auxiliary/admin/mainframe/tk5_jcl_submit": """
[*] Connecting to 127.0.0.1:2121...
[+] Connected to FTP server
[*] Logging in as HERC01...
[+] Login successful
[*] Switching to JES mode (SITE FILETYPE=JES)...
[+] JES mode enabled
[*] Submitting JCL...
[+] Job submitted successfully
[+] JOB ID: JOB00042
[*] Auxiliary module execution completed
""",
    "auxiliary/scanner/mainframe/tso_enum": """
[*] Connecting to 127.0.0.1:3270...
[+] Connected to TN3270
[*] Navigating to TSO logon screen...
[+] Found TSO logon panel
[*] Enumerating users...
[+] Valid user found: HERC01
[+] Valid user found: HERC02
[+] Valid user found: IBMUSER
[-] Invalid user: TESTUSER
[-] Invalid user: ADMIN
[*] Enumeration complete
[+] Found 3 valid users
[*] Auxiliary module execution completed
""",
    "auxiliary/scanner/mainframe/ftp_jcl_creds": """
[*] Connecting to target FTP server...
[+] Connected to 127.0.0.1:21
[*] Attempting login...
[+] Login successful
[*] Testing JES mode capability...
[+] SITE FILETYPE=JES is available
[+] JCL submission is possible via FTP
[*] Auxiliary module execution completed
""",
}
