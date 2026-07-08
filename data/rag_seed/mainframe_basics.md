# BigIron Mainframe Basics

These are safe, original mainframe concept notes for local RAG and direct-answer extraction. They are not copied from IBM manuals or Redbooks.

### Mainframe
Definition: A mainframe is a large enterprise computing platform designed for high-volume transaction processing, batch workloads, centralized data access, strong reliability, and long-lived operational control.
Security impact: Mainframe security is not root or sudo by another name, and it is not just host hardening. The important trust boundaries often involve RACF or another security manager, datasets, JES, JCL, TSO, ISPF, APF libraries, VTAM sessions, CICS transactions, SMF evidence, started task identity, PROCLIB, PARMLIB, and spool access.
Assessment angle: Avoid Unix shortcuts such as root, sudo, /etc/passwd, chmod, process-only thinking, or port-scan-only exposure. Map identity, resource, authority, execution path, session path, evidence, and operational impact.
Lab-safe example: In a TK5/MVS lab, a simple question like "who can change what runs?" leads to datasets, JCL, JES, PROCLIB, started tasks, and security profiles rather than one superuser account.

### RACF
Definition: Resource Access Control Facility, the security manager commonly used to control users, groups, datasets, and named resources through profiles and permissions.
Security impact: RACF defines authority across many resource types; it is not a single Unix root account and it is not controlled by sudo.
Assessment angle: Check user IDs, group membership, dataset profiles, resource classes, access levels, and evidence of denied or excessive access.
Lab-safe example: A user can log on to TSO but still be denied UPDATE access to a protected dataset by RACF.

### APF
Definition: Authorized Program Facility, a trusted-code boundary for libraries that contain authorized programs.
Security impact: Code loaded from APF-authorized libraries can run with authority ordinary application code should not have. APF is not sudo.
Assessment angle: Review APF library lists, write access to APF libraries, library concatenation order, and whether trusted paths are writable.
Lab-safe example: A writable APF library is a trusted-code path problem, not a temporary user elevation feature.

### JES
Definition: Job Entry Subsystem; JES accepts submitted work, queues it, schedules execution, manages spool, and routes SYSOUT.
Security impact: JES is a deferred execution and evidence plane. Submitted JCL can run later under a specific identity and leave spool output.
Assessment angle: Review who can submit jobs, alter jobs, browse spool, purge output, hold output, or route SYSOUT.
Lab-safe example: A batch job submitted from TSO may execute after the terminal session moves on, and the evidence may be in JES output.

### JCL
Definition: Job Control Language, the control language used to describe batch jobs, steps, programs, datasets, and output routing.
Security impact: JCL names the execution path: JOB identity, EXEC programs, DD datasets, STEPLIB/JOBLIB, SYSIN, and SYSOUT.
Assessment angle: Inspect DD statements, library concatenation order, dataset disposition, job class, and spool evidence.
Lab-safe example: A harmless IEFBR14 job can still allocate, catalog, or delete datasets depending on DD parameters.

### Dataset
Definition: A cataloged mainframe storage object, not the same thing as a Unix file.
Security impact: Dataset names, high-level qualifiers, catalogs, volumes, PDS members, and RACF dataset profiles define access and trust.
Assessment angle: Check dataset profiles, write access, member-level sensitivity, catalog location, and whether libraries are used by jobs or started tasks.
Lab-safe example: SYS1.PROCLIB(MEMBER) is a member in a partitioned dataset, not a path in a directory tree.

### TSO
Definition: Time Sharing Option, an interactive user environment for logon sessions, commands, dataset work, and tools such as ISPF.
Security impact: TSO is an interactive control plane where user identity, commands, datasets, and submitted jobs meet.
Assessment angle: Review TSO logon authority, command access, dataset access, submitted jobs, and session evidence.
Lab-safe example: A user may edit JCL in ISPF under TSO and submit it to JES.

### REXX
Definition: Restructured Extended Executor, a scripting language commonly used on mainframes for TSO automation, ISPF dialogs, command procedures, and operational tooling.
Security impact: REXX can automate privileged workflows, issue TSO commands, read or write datasets, call system utilities, and become part of a control path when run under a powerful user or started-task context.
Assessment angle: Review where REXX execs live, who can update those datasets or members, what identity runs them, what commands they issue, and whether they touch RACF, JES, datasets, or system libraries.
Lab-safe example: A REXX exec in a training library can list datasets or submit a harmless job; the security question is who can change the exec and under which identity it runs.

### ISPF
Definition: Interactive System Productivity Facility, a panel-driven environment commonly used from TSO for browsing, editing, and managing datasets.
Security impact: ISPF is a powerful interface to datasets and jobs, but it is not the security manager.
Assessment angle: Treat panels as workflow surfaces; check what datasets and functions the user can reach through them.
Lab-safe example: ISPF option 2 edits datasets, while RACF decides whether the user is allowed to update them.

### VTAM
Definition: Virtual Telecommunications Access Method, the session and application access fabric behind many 3270 application paths.
Security impact: A single TN3270 listener can lead to multiple logical APPLIDs, sessions, and application trust boundaries.
Assessment angle: Map APPLIDs, logon paths, exposed applications, session transitions, and whether access is visible beyond a port scan.
Lab-safe example: Finding port 3270 does not tell you which VTAM applications are reachable after connection.

### CICS
Definition: Customer Information Control System, a transaction processing environment for online applications.
Security impact: CICS security depends on transaction access, region identity, program control, backend datasets, and resource permissions.
Assessment angle: Review transaction IDs, region authority, program paths, files, journals, logs, and SMF evidence.
Lab-safe example: A four-character transaction ID can invoke application logic without looking like a Unix process.

### SMF
Definition: System Management Facilities, the event recording framework used for operational and security-relevant records.
Security impact: SMF can preserve evidence about jobs, access, commands, system activity, and security events.
Assessment angle: Identify which SMF record types are enabled, where records are written, and who can read or alter evidence.
Lab-safe example: A batch job may leave useful evidence in JES spool and SMF records even after terminal activity ends.

### Started Task
Definition: A system or subsystem task started from procedures and assigned an identity.
Security impact: Started task identity and referenced libraries can define powerful long-running trust boundaries.
Assessment angle: Check started task user mapping, PROC contents, PROCLIB, PARMLIB, STEPLIB, APF paths, and dataset access.
Lab-safe example: A subsystem can run under a started task identity rather than a human TSO user.

### PROCLIB
Definition: A procedure library containing JCL procedures used by started tasks and batch jobs.
Security impact: Write access to sensitive PROCLIB members can affect future execution.
Assessment angle: Review who can update procedures, what libraries procedures reference, and which tasks consume them.
Lab-safe example: A changed PROC member may affect a task the next time it is started.

### PARMLIB
Definition: A parameter library containing system and subsystem configuration members.
Security impact: PARMLIB members influence system behavior, subsystem startup, and operational controls.
Assessment angle: Review update authority, referenced members, IPL or restart impact, and audit evidence around changes.
Lab-safe example: Configuration changes may not execute immediately but can affect the next subsystem restart.

### Spool
Definition: JES-managed storage for jobs, input queues, output queues, SYSOUT, and job-related evidence.
Security impact: Spool access can expose job output, commands, diagnostics, and sensitive data.
Assessment angle: Check who can browse, alter, purge, or route spool output and whether output classes protect sensitive data.
Lab-safe example: A failed job can leave the exact error and dataset names in SYSOUT.

### SYSOUT
Definition: Job output routed through JES spool, commonly containing messages, listings, and program output.
Security impact: SYSOUT can contain operational evidence and sensitive application data.
Assessment angle: Review output classes, spool permissions, retention, and who can browse or purge output.
Lab-safe example: An ABEND investigation often starts by checking JES job log and SYSOUT.

### System/360
Definition: IBM System/360 is the compatible mainframe architecture family announced in 1964 that established a common instruction-set and peripheral model across a range of machines.
Security impact: System/360 itself is historical hardware architecture, but it matters because later System/370, MVS, and z/OS concepts inherited the mainframe control-plane mindset: channels, datasets, batch work, terminals, and centralized access control.
Assessment angle: Use System/360 as historical context, not a modern z/OS security target. Distinguish architecture history from current controls such as RACF, JES, APF, VTAM, CICS, and SMF.
Lab-safe example: If a user asks about System/360, answer as architecture history first, then connect it to why System/370 and MVS-era labs behave differently from Unix systems.

### Initiator
Definition: A JES-controlled address space that selects eligible batch jobs from an input queue and runs their job steps.
Security impact: Initiators are part of deferred execution. Job class, initiator availability, identity, and JCL determine when and how submitted work actually runs.
Assessment angle: Check job class, initiator class assignment, JES messages, job owner, started task identity, and spool evidence around execution.
Lab-safe example: A job can sit in input until an initiator for its class is available, then execute later without the submitter staying logged on.

### SDSF
Definition: System Display and Search Facility, an interactive interface commonly used to view and control jobs, output, queues, and system activity.
Security impact: SDSF access can expose spool output, job control actions, operator-style views, and evidence that should be permissioned carefully.
Assessment angle: Review who can browse held output, issue job commands, purge output, change classes, or view sensitive SYSOUT.
Lab-safe example: A user may use SDSF to inspect a failed job's JES log and SYSOUT without directly opening a dataset.

### VSAM
Definition: Virtual Storage Access Method, a mainframe access method and dataset organization commonly used for keyed and sequential application data.
Security impact: VSAM clusters can hold sensitive business records, and access is governed through dataset profiles, application paths, and job or transaction identity.
Assessment angle: Check cluster names, alternate indexes, catalog entries, RACF dataset access, CICS file definitions, batch DD usage, and backup or unload paths.
Lab-safe example: A CICS transaction may read a VSAM KSDS through a file definition rather than opening a Unix-style file path.

### IPL
Definition: Initial Program Load, the mainframe boot/start process for loading an operating system image or LPAR environment.
Security impact: IPL paths, PARMLIB members, system libraries, and console controls influence what system image and parameters come up.
Assessment angle: Review who can initiate IPL-related actions, which PARMLIB members are used, what LOADxx points to, and what evidence exists around restart changes.
Lab-safe example: In a lab, an IPL reloads the MVS system under Hercules and starts subsystems according to configured procedures.

### LPAR
Definition: Logical Partition, a hardware-enforced partition of an IBM mainframe processor complex that runs an independent operating environment.
Security impact: LPAR boundaries sit below z/OS and RACF; management access through HMC/SE and PR/SM configuration can affect entire operating environments.
Assessment angle: Distinguish OS-level findings from hardware partitioning control. Review management-plane access, network segmentation, and operational authority.
Lab-safe example: TK5 is a single lab system under emulation, but production systems may run many LPARs on one physical machine.

### SAF
Definition: System Authorization Facility, the z/OS interface that lets system components ask an external security manager such as RACF for authorization decisions.
Security impact: SAF is the call path between components and the security manager. The security decision is not simply a local file permission check.
Assessment angle: Identify which resource class and profile are checked, which identity is used, and whether RACF or another security product answers the SAF request.
Lab-safe example: A dataset access request can flow through SAF to RACF before the open is allowed.

### Db2
Definition: IBM's relational database management system on the mainframe, commonly used by business applications and batch or CICS workloads.
Security impact: Db2 authority, plans, packages, tables, stored procedures, and connected identities can define important application trust boundaries.
Assessment angle: Review connection paths, auth IDs, package/plan authority, table privileges, audit evidence, and how batch or CICS work reaches Db2.
Lab-safe example: A batch job may run a program that accesses Db2 through a bound plan rather than directly reading a dataset.

### IMS
Definition: Information Management System, a mainframe transaction and hierarchical database environment used by many long-lived enterprise applications.
Security impact: IMS authority involves transaction access, region identity, database access, program paths, and operational controls.
Assessment angle: Review transaction codes, dependent regions, PSBs/PCBs at a high level, dataset access, operator commands, and audit evidence.
Lab-safe example: An IMS transaction can reach application data through IMS control structures rather than a visible Unix-style process path.

### System/370
Definition: IBM mainframe architecture family behind classic MVS-era concepts such as 3270 interaction, batch work, datasets, and channel I/O.
Security impact: System/370 and MVS assumptions differ from Unix assumptions about users, files, processes, and network exposure.
Assessment angle: Use a mainframe control-plane model: RACF, JES, JCL, TSO, ISPF, datasets, VTAM, CICS, SMF, and APF.
Lab-safe example: A System/370-style lab teaches why port scans and Unix privilege terms do not explain the whole system.

### System/390
Definition: IBM System/390 is the mainframe architecture generation announced in 1990 between the System/370 lineage and the later z/Architecture era.
Security impact: System/390 systems commonly sit in the MVS/ESA and OS/390 lineage, where security analysis still centers on RACF, datasets, JES, JCL, APF, VTAM, CICS, SMF, and started task identity.
Assessment angle: Clarify whether the user means System/390 hardware, MVS/ESA, or OS/390. Do not collapse all of them into generic "mainframe" wording.
Lab-safe example: A System/390 question may need a timeline answer, while an OS/390 question may need an operating-system lineage answer.

### MVS
Definition: Multiple Virtual Storage, a classic IBM mainframe operating system lineage.
Security impact: MVS uses datasets, JES, JCL, TSO, system libraries, and started tasks rather than a Unix process-and-file model.
Assessment angle: Map authority through datasets, job execution, system libraries, and session paths.
Lab-safe example: MVS 3.8j labs are useful for learning mainframe-native reasoning.

### z/OS
Definition: IBM's modern mainframe operating system.
Security impact: z/OS security and operations commonly involve RACF, datasets, JES, JCL, TSO, ISPF, CICS, VTAM, SMF, APF, and started tasks.
Assessment angle: Avoid Linux shortcuts; identify the actual control plane enforcing each action.
Lab-safe example: A z/OS finding should explain identity, resource, permission, evidence, and operational impact.
