# RACF Security

**RACF** (Resource Access Control Facility) is the z/OS security manager. It controls who can access what.

## Core Concepts

### Users
Every person has a RACF userid:
```
LISTUSER HERC01

USER=HERC01  NAME=HERCULES USER
  DEFAULT-GROUP=SYS1
  ATTRIBUTES=NONE
```

### Groups
Users belong to groups for easier management:
```
LISTGRP SYS1

GROUP SYS1
  USERS: HERC01, IBMUSER, OPER01
```

### Profiles
Resources are protected by **profiles** that define who has access:
```
LISTDSD DATASET('SYS1.PARMLIB') ALL

DATASET SYS1.PARMLIB
  OWNER: SYS1
  UACC: NONE
  ACCESS LIST:
    IBMUSER  ALTER
    SYSPROG  UPDATE
    HERC01   READ
```

## Access Levels

| Level | Meaning |
|-------|---------|
| NONE | No access |
| READ | Read only |
| UPDATE | Read and write |
| CONTROL | Read, write, delete |
| ALTER | Full control including security |

## UACC (Universal Access)

**UACC** is the default access for users not in the access list:

```
UACC(NONE)   - Deny by default (secure)
UACC(READ)   - Everyone can read (less secure)
```

> Always use `UACC(NONE)` and explicitly grant access.

## Key RACF Classes

| Class | Protects |
|-------|----------|
| DATASET | Datasets and files |
| PROGRAM | Program execution |
| FACILITY | System facilities |
| STARTED | Started task identity |
| OPERCMDS | Operator commands |
| TCICSTRN | CICS transactions |

## Common Commands

### List User Info
```
LISTUSER HERC01
```

### List Dataset Security
```
LISTDSD DATASET('SYS1.PARMLIB') ALL
```

### Find Privileged Users
```
SEARCH CLASS(USER) SPECIAL
SEARCH CLASS(USER) OPERATIONS
```

### Grant Access
```
PERMIT 'MY.DATASET' ID(HERC01) ACCESS(READ)
```

### Check Your Access
```
LISTDSD DATASET('SYS1.PARMLIB') AUTHUSER
```

## Special Attributes

Some users have special RACF powers:

| Attribute | Power |
|-----------|-------|
| SPECIAL | Can modify any RACF profile |
| OPERATIONS | Bypass dataset protection |
| AUDITOR | View audit records |

> These are extremely powerful. Minimize who has them.

## Try It: Check Security

Run these commands to explore RACF:

```
LISTUSER HERC01
```

```
LISTDSD DATASET('SYS1.PARMLIB') ALL
```

```
SEARCH CLASS(USER) SPECIAL
```

Ask BigIron: "What datasets can I access?"
