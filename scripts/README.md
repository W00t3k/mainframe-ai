# `scripts/` — Shell Scripts and Utilities

Shell scripts for installation, MVS management, and utility Python scripts for mainframe operations.

## Shell Scripts

### `install.sh`
Linux one-command installer — handles everything:
- Detects distro (Ubuntu, Debian, Kali, Fedora, CentOS, Arch, openSUSE)
- Installs Python 3.11+, s3270/x3270, and other system dependencies
- Installs Ollama + auto-selects model based on available RAM
- Clones the public repo with `git` when needed
- Creates Python venv and installs requirements
- Validates DASD files against known-good sizes

### `mvs.sh`
TK5 MVS management (start/stop/restart/status):
```bash
./scripts/mvs.sh start     # Start TK5 in background
./scripts/mvs.sh stop      # Graceful shutdown
./scripts/mvs.sh kill      # Force kill
./scripts/mvs.sh restart   # Stop + start
./scripts/mvs.sh status    # PID, ports, memory, uptime
./scripts/mvs.sh log       # Tail Hercules log
```

### `start_mvs.sh`
Interactive/foreground TK5 launcher. Runs Hercules with console output visible — useful for debugging IPL issues.

### `start_gpu.sh`
GPU-enabled launcher with NVIDIA detection and optimized Ollama settings.

### `diagnose.sh`
Diagnostic info collector — gathers system info, port status, process list, and log tails for troubleshooting.

### `submit_uss.sh`
Submit the USS logon screen JCL (`jcl/IBMAI.jcl`) to the TK5 card reader.

### `mvs_shutdown.rc`
Hercules RC file for clean MVS shutdown sequence.

## Python Utilities

### `gen_uss_jcl.py`
Generate USS logon screen JCL from a template. Produces assembler source for ISTNSC00.

### `herc_automation.py`
Hercules console automation via HTTP API (port 8038). Sends operator commands programmatically.

### `a2etable.py` / `e2alookup.py`
ASCII ↔ EBCDIC translation table generators and lookup utilities.

### `findbytes.py`
Binary pattern finder for DASD image analysis.

### `upload_to_mvs.py`
Upload files to MVS via the card reader or FTP.

### `submit_uss_jcl.py` / `submit_uss_direct.py` / `install_uss.py`
Various USS logon screen installation approaches (card reader, direct, automated).

### `install_kicks_full.py` / `kicks_full_install.py`
Extended KICKS installation scripts with additional steps beyond `tools/install_kicks.py`.
