"""
Learning Path Catalog

Definitions for the guided learning paths in the tutor system.
"""

PATH_CATALOG = {
    'session-stack': {
        'id': 'session-stack',
        'title': 'Session Stack',
        'description': 'Connect VTAM→TSO→ISPF and learn navigation, PF keys, panels, and command flow.',
        'defender_outcome': 'Understand where authentication, authorization, and auditing occur in the session stack.'
    },
    'batch-execution': {
        'id': 'batch-execution',
        'title': 'Batch Execution',
        'description': 'Create and submit JCL, interpret JES output, and trace job logs and return codes.',
        'defender_outcome': 'Know where jobs are queued, scheduled, and logged so you can trace execution safely.'
    },
    'dataset-trust': {
        'id': 'dataset-trust',
        'title': 'Dataset Trust',
        'description': 'Understand RACF/Dataset profiles, access checks, and common misconfig trust breaks.',
        'defender_outcome': 'Map dataset access patterns to least-privilege controls and audit evidence.'
    },
    'free-explore': {
        'id': 'free-explore',
        'title': 'Free Explore',
        'description': 'Explore with guardrails—ask questions and get contextual help on the current screen.',
        'defender_outcome': 'Practice safe exploration while maintaining system integrity.'
    }
}


FALLBACK_STEPS = {
    "session-stack": [
        {
            "title": "Find the LOGON prompt",
            "instruction": "Look for the LOGON ===> prompt on the terminal. If you don't see it, press Enter once.",
            "rationale": "VTAM/TN3270 sessions typically start at the LOGON prompt before TSO.",
            "expected": "A screen with LOGON ===> or similar prompt.",
            "expected_signature": ["LOGON", "LOGON ===>"],
            "hints": ["Press Enter once", "If you see a blank screen, press Clear"]
        },
        {
            "title": "Enter TSO",
            "instruction": "Type TSO and press Enter.",
            "rationale": "TSO is the interactive shell used to access ISPF and datasets.",
            "expected": "A TSO/E logon panel or READY prompt.",
            "expected_signature": ["TSO", "READY", "IKJ"],
            "hints": ["If you see IKJ, you are in TSO", "If denied, verify your user ID"]
        },
        {
            "title": "Launch ISPF",
            "instruction": "At the TSO READY prompt, type ISPF and press Enter.",
            "rationale": "ISPF is the menu-driven interface for dataset and panel navigation.",
            "expected": "ISPF Primary Option Menu.",
            "expected_signature": ["ISPF", "Primary Option Menu"],
            "hints": ["If you see option menu, you're in ISPF"]
        }
    ],
    "batch-execution": [
        {
            "title": "Locate a JCL member",
            "instruction": "In ISPF, go to option 3.4 and locate a dataset with JCL members.",
            "rationale": "Batch execution starts with JCL source members.",
            "expected": "ISPF Dataset List panel.",
            "expected_signature": ["DATA SET LIST", "DSLIST", "3.4"],
            "hints": ["If not in ISPF, launch it first", "Use wildcards like HLQ.*"]
        },
        {
            "title": "Submit a job",
            "instruction": "Select a JCL member and submit it (SUB or JCL submit action).",
            "rationale": "Submitting a job sends it to JES for execution.",
            "expected": "A message that the job was submitted.",
            "expected_signature": ["SUBMITTED", "JOB", "JES"],
            "hints": ["Look for a confirmation line", "If you see error, review the JOB card"]
        },
        {
            "title": "View job output",
            "instruction": "Go to SDSF or JES output panel and find your job output.",
            "rationale": "Output verification confirms batch execution.",
            "expected": "Job output listing or SDSF panel.",
            "expected_signature": ["SDSF", "OUTPUT", "JOBNAME"],
            "hints": ["If SDSF unavailable, use JES panels"]
        }
    ],
    "dataset-trust": [
        {
            "title": "Open dataset list",
            "instruction": "In ISPF, open option 3.4 and list datasets under your HLQ.",
            "rationale": "Dataset access is central to mainframe trust boundaries.",
            "expected": "ISPF Dataset List panel.",
            "expected_signature": ["DATA SET LIST", "DSLIST", "3.4"],
            "hints": ["Use HLQ.* to filter"]
        },
        {
            "title": "Inspect dataset attributes",
            "instruction": "Select a dataset and view its attributes (DSORG, LRECL, BLKSIZE).",
            "rationale": "Attributes affect how data is stored and protected.",
            "expected": "Dataset attributes panel.",
            "expected_signature": ["DSORG", "LRECL", "BLKSIZE"],
            "hints": ["Use the info/attributes action from the list"]
        },
        {
            "title": "Understand DISP",
            "instruction": "Open a JCL member and locate DISP parameters.",
            "rationale": "DISP controls dataset disposition and access behavior.",
            "expected": "JCL member view with DISP=...",
            "expected_signature": ["DISP="],
            "hints": ["Search for DISP in the JCL"]
        }
    ],
    "free-explore": [
        {
            "title": "Take a look around",
            "instruction": "Use the menu or panels available and describe what you see.",
            "rationale": "Exploration builds familiarity and context.",
            "expected": "Any stable panel to discuss.",
            "expected_signature": ["MENU", "OPTION", "TSO", "ISPF"],
            "hints": ["Ask the tutor what the current panel is"]
        }
    ]
}
