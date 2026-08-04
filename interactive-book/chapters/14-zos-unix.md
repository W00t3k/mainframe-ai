# z/OS UNIX System Services

**z/OS UNIX** (USS) brings POSIX-compliant UNIX to the mainframe. It enables modern development tools, scripting, and open-source software on z/OS.

## Why z/OS UNIX?

- Run **open-source** tools (git, Python, Node.js)
- Use **shell scripts** for automation
- **Hierarchical file system** (HFS/zFS)
- **TCP/IP networking** and sockets
- Bridge between mainframe and distributed systems

## The Two Worlds

z/OS has two file systems:

| Traditional z/OS | z/OS UNIX |
|-----------------|-----------|
| Datasets (SYS1.PARMLIB) | Files (/usr/bin/ls) |
| PDS members | Directories |
| RECFM/LRECL | Byte streams |
| JCL | Shell scripts |
| TSO | OMVS shell |

Both coexist—programs can access either.

## Accessing z/OS UNIX

### OMVS Command

From TSO:
```
OMVS
```

You're now in a UNIX shell:
```
$ pwd
/u/herc01
$ ls -la
total 24
drwxr-xr-x  2 HERC01 SYS1  256 Jul 16 10:00 .
drwxr-xr-x 10 root   SYS1  256 Jul 16 09:00 ..
-rw-r--r--  1 HERC01 SYS1  128 Jul 16 10:00 .profile
```

### ISHELL

Interactive UNIX shell with panel interface:
```
ISHELL
```

### BPXBATCH

Run UNIX commands in batch:
```jcl
//UNIX    JOB (ACCT),'UNIX BATCH'
//STEP1   EXEC PGM=BPXBATCH
//STDIN   DD DUMMY
//STDOUT  DD SYSOUT=*
//STDERR  DD SYSOUT=*
//STDPARM DD *
SH ls -la /u/herc01
/*
```

## File System

### zFS (z/OS File System)

Modern UNIX file system for z/OS:
- **Hierarchical** directory structure
- **Permissions** (rwxr-xr-x)
- **Symbolic links**
- **Mount points**

### Common Directories

| Directory | Contents |
|-----------|----------|
| `/bin` | Essential commands |
| `/usr/bin` | User commands |
| `/etc` | Configuration files |
| `/tmp` | Temporary files |
| `/u/userid` | Home directories |
| `/var` | Variable data |

## Shell Commands

Standard UNIX commands work:

```bash
# Navigation
pwd                  # Print working directory
cd /usr/bin          # Change directory
ls -la               # List files

# File operations
cat file.txt         # Display file
cp source dest       # Copy
mv old new           # Move/rename
rm file              # Delete
mkdir dirname        # Create directory

# Permissions
chmod 755 script.sh  # Change permissions
chown user file      # Change owner

# Process
ps -ef               # List processes
kill -9 pid          # Kill process
```

## Accessing MVS Datasets

### From Shell

Use the `//'` prefix:
```bash
cat "//'SYS1.PARMLIB(IEASYS00)'"
cp myfile "//'HERC01.DATA'"
```

### OGET/OPUT

Transfer between USS and MVS:
```
OPUT /u/herc01/file.txt 'HERC01.DATA'
OGET 'HERC01.DATA' /u/herc01/file.txt
```

## Scripting

### Shell Scripts

```bash
#!/bin/sh
# myscript.sh
echo "Starting job"
date
ls -la /u/herc01
echo "Done"
```

Run it:
```bash
chmod +x myscript.sh
./myscript.sh
```

### Environment Variables

```bash
export PATH=$PATH:/u/herc01/bin
export JAVA_HOME=/usr/lpp/java
```

Put in `~/.profile` for persistence.

## Security

z/OS UNIX integrates with RACF:

- **UID/GID** mapped to RACF users/groups
- **Superuser (UID 0)** like root
- **Permission bits** enforced by RACF

### Check Your UID
```bash
id
uid=500(HERC01) gid=1(SYS1)
```

### RACF UNIXPRIV Class
Controls UNIX privileges via RACF profiles.

## TCP/IP Services

z/OS UNIX provides:
- **SSH** server
- **FTP/SFTP**
- **HTTP** servers
- **Socket programming**

### SSH Access
```bash
ssh herc01@mainframe.host
```

## Java on z/OS

Java runs in z/OS UNIX:
```bash
export JAVA_HOME=/usr/lpp/java/J8.0_64
export PATH=$JAVA_HOME/bin:$PATH
java -version
javac MyProgram.java
java MyProgram
```

## Try It: Explore UNIX

1. Enter `OMVS` from TSO
2. Try these commands:
```bash
pwd
ls -la
echo "Hello from USS"
cat "//'SYS1.PARMLIB(IEASYS00)'" | head -20
exit
```

The `exit` command returns you to TSO.
