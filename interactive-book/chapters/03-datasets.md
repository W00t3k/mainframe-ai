# Datasets: Mainframe Files

On z/OS, files are called **datasets**. They're fundamentally different from Unix/Windows files.

## Dataset Naming

Dataset names follow strict rules:

- Up to 44 characters total
- Divided into **qualifiers** separated by periods
- Each qualifier: 1-8 characters, starts with letter
- All uppercase

Examples:
```
SYS1.PARMLIB
HERC01.JCL.CNTL
PROD.PAYROLL.MASTER
```

The first qualifier is called the **high-level qualifier (HLQ)**. It often indicates ownership or purpose.

## Dataset Organizations

### Sequential (PS)
Like a flat file. Records are read/written in order.
```
Record 1
Record 2
Record 3
...
```

### Partitioned (PDS/PDSE)
A directory containing **members**—like a folder with files inside.
```
MY.SOURCE.COBOL
  ├── PROGRAM1
  ├── PROGRAM2
  └── COPYBOOK1
```

### VSAM (Virtual Storage Access Method)
Advanced file structures for databases and high-performance access:
- **KSDS**: Key-Sequenced (like an indexed table)
- **ESDS**: Entry-Sequenced (append-only log)
- **RRDS**: Relative Record (fixed slots)

## Record Formats

Unlike Unix text files, mainframe datasets have **fixed record structures**:

| Format | Meaning |
|--------|---------|
| FB | Fixed Block - all records same length |
| VB | Variable Block - records vary in length |
| FBA | Fixed Block with ASA control characters |
| U | Undefined - program handles structure |

Example: `RECFM=FB,LRECL=80,BLKSIZE=27920`
- Records are 80 bytes (like a punch card!)
- Blocked together in 27920-byte chunks

## Try It: List Your Datasets

In TSO, run:

```
LISTCAT LEVEL(HERC01)
```

This shows all datasets with HLQ `HERC01`.

To see members of a PDS:

```
LISTDS 'HERC01.JCL.CNTL' MEMBERS
```

## The Catalog

z/OS maintains a **catalog** that maps dataset names to physical disk locations (volumes). When you reference a dataset by name, the catalog tells the system where to find it.

```
LISTCAT ENT('SYS1.PARMLIB') ALL
```

This shows catalog details including volume, creation date, and space usage.
