# BigIron-AI Skills Framework

## Skill Categories

### 1. Security Assessment Skills
| Skill | Commands | Output |
|-------|----------|--------|
| `audit-racf` | LISTUSER, LISTGRP, LISTDSD, RLIST, SEARCH CLASS | User/group/resource permissions |
| `audit-apf` | D PROG,APF, LISTDSD on APF libs | Writable APF libraries |
| `audit-linklist` | D PROG,LNK, SETPROG LNK | Link list exposure |
| `audit-started-tasks` | RLIST STARTED, D A,L | Started task privileges |
| `audit-escalation` | Check APF+LINKLIST+PROCLIB write | Privilege escalation paths |

### 2. System Administration Skills
| Skill | Commands | Output |
|-------|----------|--------|
| `show-system` | D IPLINFO, D SYMBOLS, D M=CPU | System configuration |
| `show-storage` | D SMS, LISTCAT | Storage management |
| `show-jobs` | D A,L, $DA, $DQ | Active jobs and queues |
| `manage-datasets` | IDCAMS, IEBCOPY, IEBGENER | Dataset operations |

### 3. Development Skills
| Skill | Language | Pattern |
|-------|----------|---------|
| `write-jcl` | JCL | Job structure, DD statements, utilities |
| `write-cobol` | COBOL | Divisions, file handling, DB2/CICS |
| `write-rexx` | REXX | EXECIO, TSO, ISPF services |
| `debug-abend` | S0C7, S0C4, S806 | Dump analysis, common causes |

### 4. Operational Skills
| Skill | Context | Output |
|-------|---------|--------|
| `explain-component` | Any z/OS term | Plain English explanation |
| `compare-components` | Two+ components | How they work together |
| `troubleshoot` | Error/symptom | Diagnosis steps |

## Skill Activation

Skills activate by keyword detection in prompts:

```
"audit RACF" → audit-racf skill
"write JCL to copy" → write-jcl skill  
"what causes S0C7" → debug-abend skill
"explain JES2 and CICS" → compare-components skill
```

## Tool-Use Patterns

Each skill produces structured, executable output:

```
SKILL: audit-apf
INPUT: "Check for writable APF libraries"
OUTPUT:
1. List APF libraries:
   D PROG,APF
   
2. For each library, check write access:
   LISTDSD DATASET('SYS1.LINKLIB') ALL
   
3. Look for:
   - UACC > NONE
   - USER profiles with UPDATE/ALTER
   - Group access patterns

4. Red flags:
   - Any user with UPDATE to APF library = privilege escalation
```
