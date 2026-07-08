# BigIron Common Mainframe Terms

These are safe, original notes for common mainframe questions that should answer directly without model generation.

### COBOL
Definition: Common Business-Oriented Language, a programming language widely used for mainframe business applications, batch jobs, and transaction systems.
Security impact: COBOL programs often process sensitive records through datasets, VSAM, Db2, IMS, CICS, and batch workflows.
Assessment angle: Review program execution path, input and output datasets, copybooks, compile listings, job output, and which identity runs the program.
Lab-safe example: A COBOL batch job may read a fixed-length input dataset and write SYSOUT or another dataset through JCL DD statements.

### Copybook
Definition: A reusable COBOL source member that defines record layouts, fields, and shared data structures.
Security impact: Wrong or stale copybooks can cause data interpretation errors, ABENDs such as S0C7, and incorrect handling of sensitive fields.
Assessment angle: Compare copybook field definitions to actual input records, compiler listings, and the dataset layout used by the job.
Lab-safe example: If a packed decimal field is defined incorrectly, the program may fail when arithmetic touches invalid data.

### CICS Transaction
Definition: A named CICS unit of work, usually invoked by a short transaction ID, that runs application logic in a CICS region.
Security impact: Transaction authority can expose business functions, backend files, programs, queues, and database access through a small terminal-facing command.
Assessment angle: Review transaction IDs, program mappings, resource permissions, region identity, file access, and SMF or CICS logs.
Lab-safe example: A four-character transaction entered on a 3270 screen can invoke application logic without resembling a Unix process.

### 3270
Definition: A family of IBM terminal protocols and screens used for interactive mainframe sessions such as TSO, ISPF, CICS, and VTAM application access.
Security impact: A visible TN3270 port does not describe all reachable applications; the real exposure depends on APPLIDs, sessions, screens, and authentication paths.
Assessment angle: Map the session flow after connection: banner, APPLID, logon path, exposed applications, and which identity is bound at each step.
Lab-safe example: Connecting to port 3270 may first show a menu where TSO, CICS, or other VTAM applications are selected.

### TN3270
Definition: Telnet-based 3270 terminal access used to connect modern clients to mainframe 3270 applications.
Security impact: TN3270 is a transport path into logical mainframe applications, not proof that only one service or trust boundary exists.
Assessment angle: Check listener exposure, TLS or AT-TLS use, APPLID routing, logon flows, banner leakage, and whether brute force protections exist.
Lab-safe example: A lab TN3270 listener can expose TSO and application menus behind the same network port.

### APPLID
Definition: An application identifier used by VTAM and 3270 environments to name or route sessions to logical applications.
Security impact: APPLIDs define reachable application paths beyond what a port scan shows.
Assessment angle: Enumerate visible APPLIDs, logon menus, session transitions, and the controls protecting each application path.
Lab-safe example: A menu selection can route a user from an initial 3270 screen into TSO or a CICS region.

### JCL DD
Definition: A Data Definition statement in JCL that maps a job step's logical input or output name to datasets, SYSOUT, spool, inline data, or devices.
Security impact: DD statements define what a program can read, write, allocate, delete, or expose in job output.
Assessment angle: Review DSN, DISP, UNIT, VOL, SPACE, DCB, SYSOUT class, and whether STEPLIB/JOBLIB changes executable search paths.
Lab-safe example: `//SYSOUT DD SYSOUT=*` routes output to JES spool, while `//INPUT DD DSN=...` names a dataset.

### STEPLIB
Definition: A JCL DD statement that adds load libraries to the search path for a specific job step.
Security impact: STEPLIB can redirect which program module is loaded. Writable libraries in a STEPLIB path can become an execution trust issue.
Assessment angle: Check library order, dataset permissions, APF status where relevant, and whether the named program exists in an unexpected library.
Lab-safe example: An S806 module-not-found failure often leads reviewers to inspect STEPLIB, JOBLIB, and link-list paths.

### JOBLIB
Definition: A JCL DD statement that defines load libraries available to all job steps unless overridden by step-specific libraries.
Security impact: JOBLIB affects executable search paths across a job and can create trust-boundary issues if writable or unexpected libraries are used.
Assessment angle: Review concatenation order, dataset profiles, APF relevance, module provenance, and the job's JES output.
Lab-safe example: A batch job may use JOBLIB to find application load modules instead of relying only on system link-list libraries.

### Link List
Definition: A system-managed list of load libraries used when programs are searched for execution.
Security impact: Link-list libraries are trusted operational paths. Write access or incorrect library order can affect many jobs and tasks.
Assessment angle: Review configured libraries, update authority, APF relationships, module provenance, and change evidence.
Lab-safe example: If a program is not in STEPLIB or JOBLIB, the system may search link-list libraries.

### Catalog
Definition: A mainframe index that maps dataset names to volume and location information.
Security impact: Catalog entries affect dataset discovery and access paths, but RACF or another security manager still controls authority.
Assessment angle: Check whether datasets are cataloged, which catalog is used, aliases, volumes, and how JCL references the dataset.
Lab-safe example: A JCL DD can refer to a cataloged dataset by DSN without specifying its physical volume.

### HLQ
Definition: High-Level Qualifier, the first segment of a dataset name and often an important convention for ownership, grouping, or security profiles.
Security impact: HLQs commonly drive RACF dataset profile patterns and operational ownership assumptions.
Assessment angle: Review HLQ naming, generic dataset profiles, group ownership, and whether sensitive datasets share broad qualifiers.
Lab-safe example: `SYS1.PROCLIB` has `SYS1` as the HLQ.
