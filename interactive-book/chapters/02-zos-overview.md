# z/OS Overview

**z/OS** is IBM's flagship mainframe operating system. It's the modern descendant of MVS (Multiple Virtual Storage), which debuted in 1974.

## Operating System Layers

z/OS isn't a single program—it's a collection of components working together:

```
┌─────────────────────────────────────────┐
│            Applications                 │
│    (CICS, DB2, Batch Jobs, TSO)        │
├─────────────────────────────────────────┤
│           Subsystems                    │
│    (JES2, VTAM, RACF, SMS)             │
├─────────────────────────────────────────┤
│         Base Control Program            │
│    (BCP - the kernel)                   │
├─────────────────────────────────────────┤
│           Hardware                      │
│    (zSeries processors, I/O)           │
└─────────────────────────────────────────┘
```

## Key Components

### JES2 (Job Entry Subsystem)
Manages batch job execution. When you submit a job, JES2:
1. Reads your JCL
2. Schedules the job
3. Manages output (SYSOUT)

### RACF (Resource Access Control Facility)
The security manager. Controls who can access what. Every dataset, program, and transaction is protected by RACF profiles.

### TSO (Time Sharing Option)
Your interactive login environment. Think of it as the mainframe's command line.

### ISPF (Interactive System Productivity Facility)
A panel-driven interface that runs on top of TSO. Most mainframe users work in ISPF.

### VTAM (Virtual Telecommunications Access Method)
Manages terminal sessions and network communications.

## Address Spaces

Every running program on z/OS runs in its own **address space**—an isolated virtual memory environment. This provides:

- **Protection**: One program can't crash another
- **Isolation**: Security boundaries between workloads
- **Scalability**: Thousands of address spaces can run simultaneously

## Try It: Explore TSO

After logging in (HERC01/CUL8TR), you're in TSO. Try these commands:

```
LISTCAT
```
Lists your cataloged datasets.

```
PROFILE
```
Shows your TSO profile settings.

```
TIME
```
Displays the current system time.

Ask BigIron if you get stuck!
