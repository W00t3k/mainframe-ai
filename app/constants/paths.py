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
    },
    'ftp-basics': {
        'id': 'ftp-basics',
        'title': 'MVS FTP: Transfer Files To and From the Mainframe',
        'description': 'Connect to the TK5 FTP server on port 2121, upload and download datasets, understand EBCDIC/ASCII translation, and see how FTP maps to MVS dataset naming.',
        'defender_outcome': 'Know how data enters and leaves the mainframe via FTP, what gets logged, and how to detect unauthorized transfers.'
    },
    'jcl-submit': {
        'id': 'jcl-submit',
        'title': 'JCL Basics: Write, Submit, and Read Output',
        'description': 'Write a simple JCL job from scratch, submit it via TSO, and read the output. Understand the JOB card, EXEC statement, DD statements, and JES return codes.',
        'defender_outcome': 'Understand the batch execution model so you can audit job submissions and detect anomalous JCL.'
    },
    'racf-recon': {
        'id': 'racf-recon',
        'title': 'RACF Recon: Map Users, Groups, and Dataset Profiles',
        'description': 'Use TSO RACF commands to list users, groups, and dataset profiles. Identify over-privileged accounts, universal access settings, and audit gaps.',
        'defender_outcome': 'Build a RACF access map to identify privilege creep, orphaned accounts, and missing resource profiles.'
    },
    'abend-analysis': {
        'id': 'abend-analysis',
        'title': 'ABEND Analysis: Read a System Dump',
        'description': 'Trigger a simple ABEND, locate the dump output, and read the key fields: completion code, PSW, registers, and failing instruction. Foundation for exploit development and incident response.',
        'defender_outcome': 'Understand what a dump tells you about a crash so you can distinguish normal ABENDs from exploitation attempts.'
    },
    'prsm-lpars': {
        'id': 'prsm-lpars',
        'title': 'PR/SM & LPARs: Hardware Partitioning',
        'description': 'Understand PR/SM (Processor Resource/Systems Manager) — the firmware layer below the OS that creates LPARs, manages CPU/memory/IO resources, and provides hardware-enforced isolation. Learn about HMC, Parallel Sysplex, and Coupling Facilities.',
        'defender_outcome': 'Know where the strongest isolation boundary exists on a mainframe, why HMC access is the most critical attack surface, and how Parallel Sysplex affects cross-LPAR risk.'
    },
    'buffer-overflow': {
        'id': 'buffer-overflow',
        'title': 'Buffer Overflow on MVS 3.8j',
        'description': 'Demonstrate a classic stack buffer overflow on a 1978 mainframe OS. Assemble a vulnerable program, trigger S0C4 (protection exception), use De Bruijn patterns to find the return address offset, and prove controlled execution with a WTO payload. The same exploitation primitive used in modern systems — on a mainframe.',
        'defender_outcome': 'Understand that mainframe programs are susceptible to memory corruption, learn to read ABEND dumps for exploitation indicators, and know why MVS 3.8j lacks modern mitigations (ASLR, canaries, DEP).'
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
    ],
    "ftp-basics": [
        {
            "title": "Connect to the MVS FTP server",
            "instruction": "Open a terminal on your local machine and run: ftp localhost 2121\nLog in with HERC01 / CUL8TR.",
            "rationale": "TK5 runs an FTP server on port 2121. It speaks standard FTP but maps commands to MVS dataset operations.",
            "expected": "FTP 220 banner and login prompt.",
            "expected_signature": ["220", "FTP", "Connected"],
            "hints": ["If connection refused, submit jcl/ftpd.jcl first via the web app", "Use: ftp -p localhost 2121 for passive mode"]
        },
        {
            "title": "List datasets via FTP",
            "instruction": "At the ftp> prompt type: dir\nThis lists your TSO datasets.",
            "rationale": "FTP DIR on MVS lists cataloged datasets under your HLQ, not a filesystem directory.",
            "expected": "A list of dataset names like HERC01.* entries.",
            "expected_signature": ["HERC01", "SYS", "Bytes"],
            "hints": ["Try: dir HERC01.* to filter by HLQ", "Dataset names use dots not slashes"]
        },
        {
            "title": "Download a dataset",
            "instruction": "Type: get 'SYS2.JCLLIB(HELLO)' hello.jcl\nThis downloads a JCL member to your local machine.",
            "rationale": "FTP GET maps to a TSO RECEIVE. Single quotes around the dataset name are required for fully-qualified names.",
            "expected": "Transfer complete message and a local hello.jcl file.",
            "expected_signature": ["Transfer complete", "226"],
            "hints": ["Always quote fully-qualified dataset names with single quotes", "ASCII mode is default — use 'binary' for load modules"]
        },
        {
            "title": "Upload a file to MVS",
            "instruction": "Create a small text file locally, then at ftp> type:\nput myfile.txt 'HERC01.TEST.DATA'\nThis creates a new sequential dataset.",
            "rationale": "FTP PUT allocates a new MVS dataset and writes the data. EBCDIC translation happens automatically in ASCII mode.",
            "expected": "Transfer complete. Dataset HERC01.TEST.DATA created on MVS.",
            "expected_signature": ["Transfer complete", "226", "HERC01"],
            "hints": ["If allocation fails, the HLQ must match your TSO prefix", "Use 'quote site lrecl 80 recfm fb' to set record format"]
        },
        {
            "title": "Understand EBCDIC translation",
            "instruction": "At ftp> type: ascii\nThen download a dataset and inspect it locally. Now type: binary\nDownload the same dataset again and compare.",
            "rationale": "MVS stores text in EBCDIC. FTP ASCII mode translates to/from ASCII automatically. Binary mode skips translation — needed for load modules and binary data.",
            "expected": "ASCII download is readable text. Binary download shows EBCDIC bytes.",
            "expected_signature": ["ascii", "binary", "200"],
            "hints": ["Load modules (executables) must always use binary mode", "Text datasets use ASCII mode"]
        },
        {
            "title": "Security implications",
            "instruction": "Think about what you just did: you transferred data to/from the mainframe using only a userid and password over cleartext FTP. Ask the tutor: what does RACF log for FTP access?",
            "rationale": "FTP on MVS 3.8j is unauthenticated in transit (no TLS). RACF controls what datasets can be accessed. SMF records log FTP activity.",
            "expected": "Understanding of FTP as an attack surface: credential exposure, data exfiltration, dataset overwrite.",
            "expected_signature": ["RACF", "SMF", "FTP"],
            "hints": ["Ask: what SMF record type covers FTP?", "Ask: can FTP overwrite SYS1.* datasets?"]
        }
    ],
    "jcl-submit": [
        {
            "title": "Log in to TSO",
            "instruction": "Connect to the mainframe via TN3270. At the LOGON ===> prompt type TSO and press Enter. Log in as HERC01 / CUL8TR.",
            "rationale": "JCL is submitted from TSO. You need an active TSO session before you can edit or submit jobs.",
            "expected": "TSO READY prompt or TSO Applications Menu.",
            "expected_signature": ["READY", "TSOAPPLS", "IKJ"],
            "hints": ["If you see a blank screen press Enter", "Type TSO at the LOGON ===> prompt"]
        },
        {
            "title": "Browse an existing JCL job",
            "instruction": "At TSO READY type: BROWSE 'SYS2.JCLLIB(HELLO)'\nRead through the JCL. Identify the JOB card, EXEC statement, and DD statements.",
            "rationale": "Understanding existing JCL before writing your own prevents syntax errors and teaches the three-card structure.",
            "expected": "BROWSE panel showing JCL source.",
            "expected_signature": ["//", "JOB", "EXEC", "DD"],
            "hints": ["PF3 to exit BROWSE", "Lines starting with // are JCL statements"]
        },
        {
            "title": "Write a simple JCL job",
            "instruction": "At TSO READY type: EDIT 'HERC01.TEST.JCL(MYJOB)' NEW\nType this JCL:\n//MYJOB   JOB (1),'TEST',CLASS=A,MSGCLASS=X\n//STEP1   EXEC PGM=IEFBR14\n//\nPress PF3 to save.",
            "rationale": "IEFBR14 is the MVS no-op program. It does nothing but return RC=0. Perfect for testing JCL syntax.",
            "expected": "Dataset saved. No errors.",
            "expected_signature": ["SAVED", "HERC01", "EDIT"],
            "hints": ["Columns 1-72 are used for JCL", "// in columns 1-2 starts every JCL statement"]
        },
        {
            "title": "Submit the job",
            "instruction": "At TSO READY type: SUBMIT 'HERC01.TEST.JCL(MYJOB)'\nNote the job number in the confirmation message.",
            "rationale": "SUBMIT sends the JCL to JES2 for scheduling. The job does not run immediately — it is queued.",
            "expected": "IEF695I message with job name and number.",
            "expected_signature": ["IEF695I", "SUBMITTED", "JOB"],
            "hints": ["Write down the job number e.g. JOB00123", "The job runs asynchronously after submission"]
        },
        {
            "title": "View job output",
            "instruction": "At TSO READY type: OUTPUT MYJOB\nOr use the QUEUE command to browse spool output.",
            "rationale": "Job output is held in the JES spool until purged. OUTPUT shows the job log, messages, and return code.",
            "expected": "Job output with return code RC=0000.",
            "expected_signature": ["RC=0000", "OUTPUT", "IEF"],
            "hints": ["RC=0000 means success", "RC=0008 or higher usually means an error"]
        }
    ],
    "racf-recon": [
        {
            "title": "List your own RACF profile",
            "instruction": "At TSO READY type: LISTUSER\nThis shows your own RACF user profile: groups, attributes, last login, password interval.",
            "rationale": "LISTUSER is the starting point for RACF recon. Every user can run it on themselves without special authority.",
            "expected": "RACF user profile for HERC01.",
            "expected_signature": ["LISTUSER", "HERC01", "GROUP", "ATTRIBUTES"],
            "hints": ["SPECIAL attribute = superuser", "OPERATIONS attribute = can access any dataset"]
        },
        {
            "title": "List another user",
            "instruction": "Type: LISTUSER IBMUSER\nNote the attributes. IBMUSER typically has SPECIAL and OPERATIONS.",
            "rationale": "On TK5, IBMUSER is the default superuser. In a real audit, finding accounts with SPECIAL+OPERATIONS is a critical finding.",
            "expected": "IBMUSER profile showing SPECIAL and OPERATIONS attributes.",
            "expected_signature": ["IBMUSER", "SPECIAL", "OPERATIONS"],
            "hints": ["If access denied, you need READ on the RACF database", "On TK5, HERC01 can usually list other users"]
        },
        {
            "title": "List group membership",
            "instruction": "Type: LISTGRP SYS1\nThis shows all users in the SYS1 group and their authorities.",
            "rationale": "Group membership determines inherited authority. Users in SYS1 or privileged groups may have elevated access.",
            "expected": "SYS1 group profile with member list.",
            "expected_signature": ["LISTGRP", "SYS1", "MEMBERS"],
            "hints": ["Try LISTGRP HERC01 to see your own group", "CONNECT authority in a group grants group-level access"]
        },
        {
            "title": "Check dataset profile access",
            "instruction": "Type: LISTDSD DATASET('SYS1.PARMLIB') ALL\nThis shows the RACF profile protecting SYS1.PARMLIB.",
            "rationale": "LISTDSD shows who has access to a dataset. UACC=READ means any authenticated user can read it — a common misconfiguration.",
            "expected": "Dataset profile for SYS1.PARMLIB with access list.",
            "expected_signature": ["LISTDSD", "UACC", "PARMLIB"],
            "hints": ["UACC=NONE is secure", "UACC=READ or higher on system datasets is a finding"]
        },
        {
            "title": "Find datasets with no protection",
            "instruction": "Type: LISTCAT ENTRIES('HERC01.*') ALL\nLook for datasets with no RACF profile (not in RACF database).",
            "rationale": "Unprotected datasets rely only on UACC defaults. If SETROPTS PROTECTALL is not active, unprotected datasets are accessible to all.",
            "expected": "Catalog listing of HERC01.* datasets.",
            "expected_signature": ["LISTCAT", "HERC01", "RACF"],
            "hints": ["Ask the tutor: what is SETROPTS PROTECTALL?", "Unprotected datasets are a common audit finding"]
        }
    ],
    "prsm-lpars": [
        {
            "title": "What is PR/SM?",
            "instruction": "Ask the tutor: What is PR/SM and where does it sit in the mainframe architecture stack?",
            "rationale": "PR/SM is firmware (Licensed Internal Code) that runs below the operating system. It creates and manages Logical Partitions on a single physical processor complex.",
            "expected": "Understanding that PR/SM is firmware-level, not software. It sits below MVS/z/OS.",
            "expected_signature": ["PR/SM", "firmware", "LPAR", "Licensed Internal Code"],
            "hints": ["Think of it as a hardware hypervisor", "PR/SM predates VMware by decades"]
        },
        {
            "title": "LPARs — Logical Partitions",
            "instruction": "Ask the tutor: What is an LPAR and how does it differ from a VM?",
            "rationale": "Each LPAR is an independent virtual machine with its own OS instance, IPL, security manager, and address spaces. Isolation is hardware-enforced by PR/SM.",
            "expected": "Understanding LPARs as hardware-isolated OS instances. Each LPAR is independent.",
            "expected_signature": ["LPAR", "isolation", "hardware", "independent"],
            "hints": ["A single IBM z16 can run 85 LPARs", "Each LPAR can run a different OS: z/OS, z/VM, Linux"]
        },
        {
            "title": "Resource Management",
            "instruction": "Ask the tutor: How does PR/SM manage CPU, memory, and I/O between LPARs?",
            "rationale": "PR/SM allocates CPUs (dedicated/shared/capped), memory (static per LPAR), and I/O channels (CHPID mapping). Weights control scheduling priority.",
            "expected": "Understanding of CPU weights, dedicated vs shared processors, static memory allocation.",
            "expected_signature": ["CPU", "memory", "I/O", "CHPID", "weight"],
            "hints": ["Shared CPUs are more efficient", "Memory cannot be shared between LPARs"]
        },
        {
            "title": "HMC and SE — Management Consoles",
            "instruction": "Ask the tutor: What are the HMC and SE? Why are they the most critical attack surface?",
            "rationale": "The HMC (Hardware Management Console) and SE (Support Element) control all LPARs. Access to HMC = ability to IPL, reset, or reconfigure any LPAR on the machine.",
            "expected": "Understanding that HMC access is the highest-privilege attack surface on a mainframe.",
            "expected_signature": ["HMC", "SE", "IPL", "reconfigure"],
            "hints": ["HMC passwords are often the weakest link", "HMC runs on a separate network — is it segmented?"]
        },
        {
            "title": "Parallel Sysplex and Coupling Facilities",
            "instruction": "Ask the tutor: What is a Parallel Sysplex and how do Coupling Facilities enable cross-LPAR cooperation?",
            "rationale": "A Parallel Sysplex is a cluster of LPARs that share workload and data via Coupling Facilities. CFs provide lock management, data caching, and cross-system communication.",
            "expected": "Understanding of sysplex as a multi-LPAR cluster with shared resources.",
            "expected_signature": ["sysplex", "Coupling Facility", "workload", "sharing"],
            "hints": ["Sysplex enables 24/7 availability", "CF policies control what can be shared"]
        },
        {
            "title": "Security Implications",
            "instruction": "Ask the tutor: What are the security implications of PR/SM for a red team assessment?",
            "rationale": "PR/SM provides the strongest isolation boundary — firmware-enforced, not software. But HMC/SE access bypasses all LPAR isolation.",
            "expected": "Understanding that LPAR isolation is the strongest boundary, but HMC is the weakest link.",
            "expected_signature": ["isolation", "HMC", "boundary", "firmware"],
            "hints": ["Compromising one LPAR does NOT compromise others", "Always ask: who has HMC access?"]
        },
        {
            "title": "TK5 and Hercules Context",
            "instruction": "Ask the tutor: Why doesn't TK5/Hercules have PR/SM? How does this lab map to production?",
            "rationale": "TK5 under Hercules simulates a single-LPAR environment. There is no real PR/SM firmware. In production, the same MVS concepts apply but within an LPAR managed by PR/SM.",
            "expected": "Understanding that TK5 is a single-LPAR simulation and production environments have multiple LPARs.",
            "expected_signature": ["TK5", "Hercules", "single", "production"],
            "hints": ["Everything you learn on TK5 applies inside one LPAR", "Production adds the PR/SM layer on top"]
        }
    ],
    "abend-analysis": [
        {
            "title": "What is an ABEND?",
            "instruction": "Ask the tutor: what is an ABEND and how does it differ from a Unix segfault?",
            "rationale": "ABEND (ABnormal END) is the MVS equivalent of a crash. Understanding ABEND codes is essential for both debugging and exploit analysis.",
            "expected": "Understanding of ABEND codes: system codes (Sxxx) and user codes (Uxxx).",
            "expected_signature": ["ABEND", "S0C", "completion"],
            "hints": ["S0C4 = protection exception (like SIGSEGV)", "S0C7 = data exception (bad data type)"]
        },
        {
            "title": "Trigger a simple ABEND",
            "instruction": "Submit this JCL:\n//ABNDTEST JOB (1),'ABEND',CLASS=A,MSGCLASS=X\n//STEP1    EXEC PGM=IEFBR14\n//DD1      DD DSN=NONEXIST.DATASET,DISP=SHR\nThis will ABEND because the dataset does not exist.",
            "rationale": "A missing dataset causes a JCL error or S0C1 ABEND depending on how the program handles it. Safe way to generate output to analyze.",
            "expected": "Job fails with JCL error or ABEND code in output.",
            "expected_signature": ["IEF", "NOT FOUND", "ABEND", "JCL ERROR"],
            "hints": ["JCL errors appear before the job runs", "Check the job log with OUTPUT command"]
        },
        {
            "title": "Read the ABEND output",
            "instruction": "View the job output with: OUTPUT ABNDTEST\nFind the completion code line. It starts with IEF or shows ABEND Sxxx.",
            "rationale": "The completion code tells you exactly what failed. System codes (Sxxx) are MVS-defined. User codes (Uxxx) are program-defined.",
            "expected": "Output showing IEF message with reason code.",
            "expected_signature": ["IEF", "COMPLETION CODE", "ABEND"],
            "hints": ["Look for lines starting with IEF", "The PSW at time of error shows where execution stopped"]
        },
        {
            "title": "Common ABEND codes",
            "instruction": "Ask the tutor to explain: S0C4, S0C7, S222, S322, S806.",
            "rationale": "These five codes cover 90% of ABENDs you will encounter. Knowing them cold is essential for both debugging and recognizing exploitation.",
            "expected": "Clear explanation of each code and what it means for security.",
            "expected_signature": ["S0C4", "S0C7", "S222", "S806"],
            "hints": ["S0C4 is the most common exploit-related code", "S806 means program not found — check STEPLIB"]
        }
    ],
    "buffer-overflow": [
        {
            "title": "Understand the Save Area Chain",
            "instruction": "Ask the tutor: How does MVS manage function calls without a stack? What is R13, R14, and the 72-byte save area?",
            "rationale": "On S/370, there is no hardware stack. Function calls use a chain of 72-byte save areas linked through R13. R14 holds the return address — the target for exploitation.",
            "expected": "Understanding that R14 = return address, R13 = save area pointer, and MVC has no bounds checking.",
            "expected_signature": ["save area", "R14", "R13"],
            "hints": ["Think of R14 as RIP/EIP on x86", "The save area is the mainframe stack frame"]
        },
        {
            "title": "Assemble the Vulnerable Program",
            "instruction": "Submit jcl/bof_demo.jcl to assemble and link-edit BOFVULN — a program with a 24-byte buffer that copies 80 bytes into it.",
            "rationale": "The MVC SMALLBUF(80),INBUF instruction copies 80 bytes regardless of SMALLBUF being only 24 bytes. No compiler warning, no runtime check.",
            "expected": "ASM RC=0000 or RC=0004, LKED RC=0000.",
            "expected_signature": ["RC=0000", "RC=0004"],
            "hints": ["RC=0004 on ASM is normal (warnings)", "LKED RC=0000 means the load module is ready"]
        },
        {
            "title": "Run with Safe Input",
            "instruction": "Check the SAFE step output — it ran with short input and should show HELLO followed by the input text.",
            "rationale": "Establishes the baseline: the program works correctly when given expected input.",
            "expected": "RC=0000 and output containing HELLO.",
            "expected_signature": ["RC=0000", "HELLO"],
            "hints": ["This proves the program logic is correct", "The overflow only matters with long input"]
        },
        {
            "title": "Trigger the S0C4 ABEND",
            "instruction": "Check the CRASH step output — it sent 68 bytes of AAAA...BBBB...CCCC...DDDD... into the 24-byte buffer.",
            "rationale": "The overflow corrupts the DEADBEEF canary, adjacent data, and eventually the save area. When the function returns, R14 points to garbage → S0C4.",
            "expected": "S0C4 ABEND — Protection Exception.",
            "expected_signature": ["S0C4", "SYSTEM COMPLETION CODE", "0C4"],
            "hints": ["S0C4 = SIGSEGV equivalent", "Look at the register dump for 0xC1C1C1C1 (EBCDIC 'AAAA')"]
        },
        {
            "title": "Use De Bruijn Pattern to Find Offset",
            "instruction": "Use the De Bruijn pattern generator at /api/labs/bof/debruijn/generate to create a unique pattern. Submit it as input and check which 4 bytes ended up in R14.",
            "rationale": "A De Bruijn sequence has unique N-byte substrings. The bytes in R14 after the crash tell you the exact offset of the return address.",
            "expected": "Pattern generated and offset calculated.",
            "expected_signature": ["offset", "pattern", "R14"],
            "hints": ["Convert R14 hex from EBCDIC back to ASCII", "The offset = padding bytes before you place your redirect address"]
        },
        {
            "title": "Prove Controlled Execution (WTO)",
            "instruction": "Submit jcl/bof_exploit.jcl to assemble and run WTOPAYLD — a WTO payload that writes messages to the operator console.",
            "rationale": "In a real exploit, this code would be injected via the overflow. The WTO messages on the Hercules console prove: user input → memory corruption → controlled execution.",
            "expected": "*** HELLO FROM EXPLOIT *** appears on the Hercules console.",
            "expected_signature": ["HELLO FROM EXPLOIT", "WTO", "CONTROLLED"],
            "hints": ["Check the Hercules console (port 8038) for WTO messages", "RC=0000 on the RUN step means the payload executed cleanly"]
        },
        {
            "title": "Why This Matters",
            "instruction": "Ask the tutor: Why does MVS 3.8j have no ASLR, no canaries, no DEP? What would an attacker do after controlling R14?",
            "rationale": "MVS 3.8j predates all modern mitigations. With controlled execution, an attacker can issue SVC calls to transition from Problem State to Supervisor State — the mainframe equivalent of a kernel exploit.",
            "expected": "Understanding of the full exploit chain: overflow → R14 control → SVC → Supervisor Mode.",
            "expected_signature": ["ASLR", "canary", "SVC", "Supervisor"],
            "hints": ["SVC 244 was a historical APF bypass", "Supervisor State = full system control"]
        }
    ]
}
