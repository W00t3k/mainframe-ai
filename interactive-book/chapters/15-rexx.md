# REXX: The Mainframe Scripting Language

**REXX** (Restructured Extended Executor) is the scripting language of z/OS. It's used for automation, utilities, and ISPF customization.

## Why REXX?

- **No compilation** - Interpreted, runs immediately
- **Powerful string handling** - Parse anything
- **System integration** - Call TSO, ISPF, MVS services
- **Everywhere** - Available on all z/OS systems

## Your First REXX Program

```rexx
/* HELLO REXX - My first program */
say 'Hello from REXX!'
say 'The date is' date()
say 'The time is' time()
exit 0
```

Save as a PDS member and run:
```
EXEC 'HERC01.REXX(HELLO)'
```

## REXX Basics

### Variables

No declarations needed:
```rexx
name = 'John'
count = 42
total = count * 2
say name 'has' total 'items'
```

### Strings

Concatenation:
```rexx
first = 'Hello'
second = 'World'
combined = first second      /* Hello World */
together = first || second   /* HelloWorld */
```

### Control Structures

**IF/THEN/ELSE:**
```rexx
if count > 10 then
  say 'High'
else
  say 'Low'
```

**SELECT (like switch):**
```rexx
select
  when code = 'A' then say 'Alpha'
  when code = 'B' then say 'Beta'
  otherwise say 'Unknown'
end
```

**DO loops:**
```rexx
/* Counted loop */
do i = 1 to 10
  say 'Iteration' i
end

/* While loop */
do while count < 100
  count = count + 1
end

/* Forever loop */
do forever
  if done then leave
end
```

## Built-in Functions

### String Functions

| Function | Purpose |
|----------|---------|
| `length(str)` | String length |
| `substr(str,pos,len)` | Substring |
| `left(str,len)` | Left portion |
| `right(str,len)` | Right portion |
| `strip(str)` | Remove whitespace |
| `translate(str)` | Uppercase |
| `pos(needle,haystack)` | Find substring |
| `word(str,n)` | Get nth word |
| `words(str)` | Count words |

### Examples

```rexx
text = '  Hello World  '
say length(text)           /* 15 */
say strip(text)            /* Hello World */
say translate(text)        /* HELLO WORLD */
say word(text, 2)          /* World */
say words(text)            /* 2 */
```

## The PARSE Statement

PARSE is REXX's superpower—it splits strings:

```rexx
/* Split by spaces */
line = 'John Smith 42'
parse var line first last age
say first    /* John */
say last     /* Smith */
say age      /* 42 */

/* Split by delimiter */
record = 'A001|Active|2024-01-15'
parse var record code '|' status '|' date
say code     /* A001 */
say status   /* Active */

/* Parse with template */
input = 'Name: John Doe'
parse var input 'Name:' name
say strip(name)  /* John Doe */
```

## TSO Integration

### ADDRESS TSO

Run TSO commands:
```rexx
address TSO
"LISTCAT LEVEL(HERC01)"
"LISTDS 'SYS1.PARMLIB' MEMBERS"
```

### Capturing Output with OUTTRAP

```rexx
x = outtrap('line.',100)    /* Trap up to 100 lines */
address TSO "LISTCAT LEVEL(SYS1)"
x = outtrap('off')

do i = 1 to line.0
  say line.i
end
```

## ISPF Services

### ADDRESS ISPEXEC

```rexx
address ISPEXEC
"DISPLAY PANEL(MYPANEL)"
"BROWSE DATASET('SYS1.PARMLIB(IEASYS00)')"
"EDIT DATASET('HERC01.DATA')"
```

### LMINIT/LMOPEN

Read PDS members:
```rexx
address ISPEXEC
"LMINIT DATAID(did) DATASET('SYS1.PROCLIB')"
"LMOPEN DATAID("did")"
"LMMLIST DATAID("did") MEMBER(mem)"
do while rc = 0
  say 'Member:' mem
  "LMMLIST DATAID("did") MEMBER(mem)"
end
"LMCLOSE DATAID("did")"
"LMFREE DATAID("did")"
```

## File I/O

### EXECIO

Read a file:
```rexx
"ALLOC DD(INPUT) DSN('HERC01.DATA') SHR"
"EXECIO * DISKR INPUT (STEM line. FINIS"
"FREE DD(INPUT)"

do i = 1 to line.0
  say line.i
end
```

Write a file:
```rexx
line.1 = 'First line'
line.2 = 'Second line'
line.0 = 2

"ALLOC DD(OUTPUT) DSN('HERC01.OUTPUT') SHR"
"EXECIO" line.0 "DISKW OUTPUT (STEM line. FINIS"
"FREE DD(OUTPUT)"
```

## Error Handling

```rexx
/* Check return codes */
address TSO
"LISTCAT LEVEL(NOSUCH)"
if rc <> 0 then do
  say 'Command failed with RC' rc
  exit 8
end

/* Signal on error */
signal on error
"BADCOMMAND"
exit 0

error:
  say 'Error at line' sigl
  exit 12
```

## Try It: REXX Utility

Create this member and run it:

```rexx
/* LISTPDS - List PDS members */
arg dsname
if dsname = '' then do
  say 'Usage: LISTPDS dataset.name'
  exit 4
end

x = outtrap('out.')
address TSO "LISTDS '"dsname"' MEMBERS"
x = outtrap('off')

say 'Members of' dsname':'
do i = 1 to out.0
  say out.i
end
exit 0
```

Run: `EXEC 'HERC01.REXX(LISTPDS)' 'SYS1.PROCLIB'`
