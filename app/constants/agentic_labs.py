"""
Agentic Labs - Goal-based lab definitions

Instead of scripted action sequences, these labs define GOALS.
The agent observes the screen and decides what action to take to achieve each goal.
"""

AGENTIC_LABS = {
    "rakf-security": {
        "title": "RAKF Security: Users, Profiles & Privilege Analysis",
        "description": "Examine the RAKF security system on MVS 3.8j TK5",
        "steps": [
            {
                "id": 1,
                "goal": "Connect to the mainframe and login to TSO as HERC01",
                "context": "RAKF is the security system on TK5 MVS 3.8j. We need to authenticate first.",
                "success_criteria": ["READY", "TSOAPPLS", "RFE"],
                "narration": "**Establishing Identity**\n\nConnecting and logging in as HERC01. RAKF (not RACF) handles authentication on MVS 3.8j TK5.",
                "control_plane": "tso",
                "max_actions": 20,
            },
            {
                "id": 2,
                "goal": "Navigate to RFE and use BROWSE to view the file SYS1.SECURE.CNTL(USERS)",
                "context": "SYS1.SECURE.CNTL(USERS) contains the RAKF users table with cleartext passwords.",
                "success_criteria": ["HERC01", "CUL8TR", "IBMUSER", "ADMIN"],
                "narration": "**RAKF Users Table**\n\nBrowsing `SYS1.SECURE.CNTL(USERS)` - this file contains ALL users with their passwords in CLEARTEXT.\n\nFormat: `USERNAME GROUP *PASSWORD O`\n- `*` = password never expires\n- `O` = Operations authority (Y=god mode, N=normal)",
                "control_plane": "racf",
                "max_actions": 15,
            },
            {
                "id": 3,
                "goal": "Go back and browse SYS1.SECURE.CNTL(PROFILES) to see the access rules",
                "context": "The PROFILES member defines which users/groups can access which resources.",
                "success_criteria": ["DATASET", "FACILITY", "UACC", "READ", "NONE"],
                "narration": "**RAKF Profiles Table**\n\nBrowsing `SYS1.SECURE.CNTL(PROFILES)` - the access control rules.\n\nFormat: `CLASS RESOURCE GROUP ACCESS`\n\n**Key findings:**\n- `DATASET * READ` = everyone can read everything by default!\n- `DATASET SYS1.SECURE.* NONE` = security tables protected",
                "control_plane": "racf",
                "max_actions": 15,
            },
            {
                "id": 4,
                "goal": "Exit back to TSO READY and logoff cleanly",
                "context": "Always logoff cleanly to avoid locking the userid.",
                "success_criteria": ["LOGOFF", "LOGGED OFF", "VTAM"],
                "narration": "**Clean Exit**\n\n**RAKF Audit Summary:**\n- Cleartext passwords in USERS table\n- UACC=READ on all datasets by default\n- SYS1.SECURE.* protected\n- Operations=Y users have bypass authority",
                "control_plane": "vtam",
                "max_actions": 10,
            },
        ],
    },

    "session-stack": {
        "title": "Session Stack: VTAM → TSO → RFE",
        "description": "Map the session layers and trust boundaries on MVS 3.8j",
        "steps": [
            {
                "id": 1,
                "goal": "Connect to the mainframe via TN3270",
                "context": "We start at the VTAM session fabric - the lowest layer.",
                "success_criteria": ["VTAM", "LOGON", "TK5", "MVS"],
                "narration": "**VTAM Session Fabric**\n\nConnected to the VTAM entry point. This is the session manager - it exists independently of TCP/IP.\n\n**Identity:** Not yet bound. We're an anonymous VTAM session.",
                "control_plane": "vtam",
                "max_actions": 5,
            },
            {
                "id": 2,
                "goal": "Login to TSO as HERC01 with password CUL8TR",
                "context": "TSO login binds our identity. RAKF verifies credentials.",
                "success_criteria": ["READY", "TSOAPPLS", "IKJ56455I"],
                "narration": "**Identity Binding**\n\nLogging in as HERC01. The transition from VTAM → TSO is a control-plane boundary crossing.\n\n**Identity:** Now bound to HERC01. All commands run under this authority.",
                "control_plane": "tso",
                "max_actions": 15,
            },
            {
                "id": 3,
                "goal": "Enter RFE (option 1 from TSO Applications Menu)",
                "context": "RFE is the ISPF-like interface on TK5.",
                "success_criteria": ["RFE", "BROWSE", "EDIT", "UTILITIES", "OPTION"],
                "narration": "**RFE Primary Menu**\n\nEntered RFE - the Review Front End. This is the interactive desktop.\n\n**Note:** TK5 uses RFE, not modern ISPF. There is no SDSF.",
                "control_plane": "tso",
                "max_actions": 10,
            },
            {
                "id": 4,
                "goal": "Use option 3 (Utilities) then 4 (DSLIST) to list datasets starting with SYS1",
                "context": "Dataset navigation - see what's on the system.",
                "success_criteria": ["SYS1", "PARMLIB", "PROCLIB", "LINKLIB"],
                "narration": "**Dataset Namespace**\n\nListing SYS1.* datasets - the system libraries.\n\n- SYS1.PARMLIB - system configuration\n- SYS1.PROCLIB - started task procedures\n- SYS1.LINKLIB - system programs",
                "control_plane": "tso",
                "max_actions": 15,
            },
            {
                "id": 5,
                "goal": "Exit RFE and logoff TSO cleanly",
                "context": "Always logoff to avoid locking the userid.",
                "success_criteria": ["LOGOFF", "LOGGED OFF", "VTAM"],
                "narration": "**Session Unbinding**\n\nLogging off. Identity unbound, returning to anonymous VTAM session.\n\n**Session Stack Summary:**\n1. VTAM - session fabric (anonymous)\n2. TSO - identity bound (HERC01)\n3. RFE - interactive desktop\n4. RAKF - continuous authorization",
                "control_plane": "vtam",
                "max_actions": 15,
            },
        ],
    },

    "deferred-exec": {
        "title": "Deferred Execution: JCL → JES",
        "description": "Submit a job and trace the execution chain",
        "steps": [
            {
                "id": 1,
                "goal": "Connect and login to TSO as HERC01",
                "context": "We need to be logged in to submit jobs.",
                "success_criteria": ["READY", "TSOAPPLS"],
                "narration": "**Setup**\n\nLogging in to demonstrate deferred execution via JES.",
                "control_plane": "tso",
                "max_actions": 20,
            },
            {
                "id": 2,
                "goal": "Check job status using the STATUS command at TSO READY",
                "context": "STATUS shows active jobs and TSO sessions.",
                "success_criteria": ["STATUS", "JOB", "TSU"],
                "narration": "**JES Status**\n\nThe STATUS command shows what's running. Each entry is an address space.\n\n**Key concept:** Jobs are queued by JES, not executed immediately.",
                "control_plane": "jes",
                "max_actions": 10,
            },
            {
                "id": 3,
                "goal": "View job output using OUTPUT command - try OUTPUT * or OUTPUT jobname",
                "context": "Job output is preserved in the JES spool.",
                "success_criteria": ["OUTPUT", "SYSOUT", "ENDED"],
                "narration": "**JES Output**\n\nJob output persists after execution. The submitter's identity is recorded.\n\n**Deferred Trust:** The job ran under the submitter's authority, even if they logged off.",
                "control_plane": "jes",
                "max_actions": 10,
            },
            {
                "id": 4,
                "goal": "Logoff cleanly",
                "context": "Clean exit.",
                "success_criteria": ["LOGOFF", "LOGGED OFF"],
                "narration": "**Summary**\n\nJES demonstrates deferred execution:\n1. Jobs are declared (JCL), not immediately run\n2. Identity persists from submission to execution\n3. Output is preserved for audit",
                "control_plane": "vtam",
                "max_actions": 10,
            },
        ],
    },
}
