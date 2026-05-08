"""
Security Patterns for Mainframe Reconnaissance

Shared pattern library for all recon scanners and enumerators.
"""

# RACF Message Patterns
RACF_PATTERNS = {
    "valid_user": [
        "IKJ56476I",      # Password prompt (user exists)
        "IKJ56425I",      # Userid in use (valid)
        "IKJ56479I",      # Already logged on
        "IDC3009I",       # VSAM catalog entry
        "ICH70001I",      # RACF access check
    ],
    "invalid_user": [
        "IKJ56401I",      # Unknown userid
        "IKJ56421I",      # Invalid userid
        "IKJ56420I",      # Logon rejected
        "IKJ56402I",      # Userid not defined
    ],
    "locked_user": [
        "IKJ56403I",      # Revoked
        "IKJ56457I",      # Account suspended
        "IKJ56417I",      # Password expired
    ],
    "access_denied": [
        "ICH408I",        # Not authorized
        "IRR012I",        # Not authorized
        "IRR013I",        # Access denied
        "NOT AUTHORIZED",
        "ACCESS DENIED",
        "VIOLATION",
    ],
    "privilege_indicators": [
        "SPECIAL",
        "OPERATIONS",
        "AUDITOR",
        "ROAUDIT",
        "GRPACC",
    ],
}

# Top Secret Patterns
TOPSECRET_PATTERNS = {
    "messages": [
        "TSS7102E",
        "TSS7103E",
        "TSS7000I",
        "TSS7001I",
    ],
}

# CICS Transaction Patterns
CICS_PATTERNS = {
    "valid": [
        "DFHCE",
        "SIGN",
        "CESN",
        "ENTER TRANS",
        "TRANSACTION",
    ],
    "invalid": [
        "DFH",
        "ABEND",
        "NOT FOUND",
        "UNKNOWN",
        "INVALID",
    ],
    "auth_required": [
        "NOTAUTH",
        "NOT AUTHORIZED",
        "SECURITY",
        "DFHAC2002",
    ],
}

# VTAM APPLID Patterns
VTAM_PATTERNS = {
    "valid": [
        "LOGON",
        "SESSION",
        "APPLICATION",
        "BOUND",
        "IKJ",
        "ENTER USERID",
    ],
    "error": [
        "IST075I",        # Application not active
        "IST453I",        # Unknown application
        "IST314I",        # End of display
        "NOT ACTIVE",
        "UNKNOWN",
        "UNABLE",
        "NOT FOUND",
    ],
}

# System ABEND Codes
ABEND_PATTERNS = {
    "system": [
        r"S0C1",          # Operation exception
        r"S0C4",          # Protection exception
        r"S0C6",          # Specification exception
        r"S0C7",          # Data exception
        r"S106",          # Module not found
        r"S222",          # Cancelled by operator
        r"S322",          # Time limit exceeded
        r"S806",          # Load module not found
        r"S878",          # Virtual storage exhausted
        r"S913",          # Security violation
        r"S922",          # Not authorized
    ],
    "user": [
        r"U[0-9]{4}",     # User abend codes
    ],
}

# Screen Analysis Patterns (for ScreenAnalyzer)
SCREEN_PATTERNS = {
    "userid_field": {
        "patterns": [
            r'USERID\s*[=:.]?\s*(\S+)',
            r'USER\s*ID\s*[=:.]?\s*(\S+)',
            r'LOGON\s+(\S+)',
            r'TSS7102E\s+(\S+)',
            r'ICH70001I\s+(\S+)',
        ],
        "severity": "medium",
        "description": "Userid reference detected",
    },
    "password_field": {
        "patterns": [
            r'PASSWORD\s*[=:.]?\s*(\S+)',
            r'PASSCODE\s*[=:.]?\s*(\S+)',
            r'PASSWD\s*[=:.]?\s*(\S+)',
        ],
        "severity": "critical",
        "description": "Password or credential reference",
    },
    "ssn": {
        "patterns": [
            r'\b\d{3}-\d{2}-\d{4}\b',
        ],
        "severity": "critical",
        "description": "Possible SSN detected",
    },
    "credit_card": {
        "patterns": [
            r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
        ],
        "severity": "critical",
        "description": "Possible credit card number",
    },
    "api_key": {
        "patterns": [
            r'[A-Za-z0-9]{32,}',
            r'API[_-]?KEY\s*[=:]\s*\S+',
        ],
        "severity": "high",
        "description": "Possible API key or token",
    },
    "abend_code": {
        "patterns": [
            r'S[0-9A-F]{3}',
            r'U[0-9]{4}',
            r'ABEND\s+\S+',
        ],
        "severity": "medium",
        "description": "System or user ABEND code",
    },
}

# TSO Terminal State Patterns
TSO_STATE_PATTERNS = {
    "vtam_uss": ["LOGON ===>", "LOGON==>", "ENTER LOGON", "NVAS", "VTAM"],
    "tso_logon": ["ENTER USERID", "TSO/E LOGON", "IKJ56700A"],
    "tso_password": ["PASSWORD", "IKJ56476I", "ENTER CURRENT PASSWORD"],
    "tso_ready": ["READY", "READY "],
    "tso_ispf": ["ISPF", "OPTION ===>", "COMMAND ===>"],
    "tso_apps_menu": ["TSO APPLICATIONS", "ISPF/PDF", "RFE", "TSOAPPLS"],
    "tso_more": ["***", "MORE", "HIT ENTER"],
    "tso_reenter": ["REENTER", "IKJ56703A"],
    "cics": ["CICS", "CESN", "DFHCE", "SIGN ON"],
}

# APF Library Patterns (for privilege escalation detection)
APF_PATTERNS = {
    "system_libs": [
        "SYS1.LINKLIB",
        "SYS1.SVCLIB",
        "SYS1.CMDLIB",
        "SYS1.NUCLEUS",
        "SYSC.LINKLIB",
    ],
    "finding_indicators": [
        "APF AUTHORIZED",
        "IEAAPF",
        "AC=1",
        "SETCODE AC(1)",
    ],
}
