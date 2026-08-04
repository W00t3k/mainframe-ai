# TSO and ISPF

**TSO** (Time Sharing Option) and **ISPF** (Interactive System Productivity Facility) are how you interact with z/OS.

## TSO: The Command Line

TSO is the z/OS interactive command environment. When you log on to a mainframe, you're using TSO.

### Common TSO Commands

| Command | Description |
|---------|-------------|
| `LISTCAT` | List catalog entries |
| `LISTDS` | List dataset information |
| `ALLOCATE` | Allocate a new dataset |
| `DELETE` | Delete a dataset |
| `RENAME` | Rename a dataset |
| `SUBMIT` | Submit a job |
| `STATUS` | Check job status |
| `PROFILE` | View/set profile options |

### TSO READY Prompt

When you exit ISPF, you see the TSO READY prompt:
```
READY
```

From here you can enter any TSO command directly:
```
READY
listcat level(herc01)
```

## ISPF: The Panel Interface

ISPF provides a menu-driven interface on top of TSO. Most mainframe work happens in ISPF.

### ISPF Primary Menu

```
Menu  Utilities  Compilers  Options  Status  Help
──────────────────────────────────────────────────
ISPF Primary Option Menu

0  Settings      Terminal and user parameters
1  View          Display source data or listings
2  Edit          Create or change source data
3  Utilities     Perform utility functions
4  Foreground    Interactive language processing
5  Batch         Submit job for language processing
6  Command       Enter TSO or Workstation commands
...
```

### Key ISPF Options

| Option | Name | Purpose |
|--------|------|---------|
| 2 | Edit | Edit datasets and members |
| 3 | Utilities | Dataset utilities |
| 3.4 | Dslist | Dataset list - browse the catalog |
| 6 | Command | Run TSO commands |
| S | SDSF | View jobs and output |

### Navigation Tips

**Quick Navigation:**
- `=3.4` - Jump directly to dataset list
- `=S` - Jump to SDSF
- `=X` - Exit ISPF completely

**Function Keys:**
- `PF1` - Help
- `PF3` - Exit/Go back
- `PF7/PF8` - Page up/down
- `PF10/PF11` - Scroll left/right

### The ISPF Editor

The ISPF editor is powerful. Line commands go in the left margin:

| Command | Action |
|---------|--------|
| `I` | Insert line |
| `D` | Delete line |
| `C` | Copy line |
| `M` | Move line |
| `R` | Repeat line |

Primary commands go on the command line:
```
FIND 'searchtext'
CHANGE 'old' 'new' ALL
SAVE
SUBMIT
```

## Try It: Navigate ISPF

1. Log in to TK5 (HERC01/CUL8TR)
2. You'll be in ISPF. Type `=3.4` and press Enter
3. Enter `SYS1` in the Dsname Level field
4. Press Enter to see all SYS1.* datasets
5. Type `S` next to any PDS to see its members
6. Press `PF3` to go back

## SDSF: System Display and Search Facility

SDSF shows you jobs, output, and system activity:

```
SDSF PRIMARY OPTION MENU
DA  - Display active jobs
ST  - Status of jobs
LOG - System log
```

From SDSF, you can:
- View job output
- Cancel running jobs
- Browse the system log
- Check job status

Try entering `LOG` in SDSF to see system messages.
