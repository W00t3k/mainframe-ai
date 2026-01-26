# Integrations Module

Integration with external mainframe security tools, particularly the mainframed toolkit by Soldier of FORTRAN.

## Attribution

**Tools by: Soldier of FORTRAN (@mainframed767)**
- GitHub: https://github.com/mainframed
- Blog: http://mainframed767.tumblr.com/

## Overview

The `integrations` module provides a unified interface for:
- Installing mainframed security tools
- Launching tools with proper configuration
- Running NMAP scripts for TN3270
- TSO user enumeration and brute force
- CICS transaction enumeration
- Network traffic sniffing
- Privilege escalation examples

## Quick Start

```python
from birpv2_modules.integrations.mainframed_tools import MainframedIntegration

integration = MainframedIntegration()

# List available tools
integration.list_tools()

# Install all tools
integration.install_all_tools()

# Run TSO enumeration
integration.tso_enumerate('192.168.1.100')
```

## Available Tools

| Tool ID | Name | Description |
|---------|------|-------------|
| `hack3270` | hack3270 | TN3270 data stream manipulation |
| `nmap-scripts` | NMAP TN3270 Scripts | TSO/CICS enumeration via NMAP |
| `enumeration` | z/OS Enumeration | REXX-based system info gathering |
| `tshocker` | TShOcker | z/OS privilege escalation |
| `privesc` | Privesc | Privilege escalation scripts |
| `mfscreen` | MFScreen | CICS screenshot capture |
| `mfsniffer` | MFSniffer | TN3270 traffic sniffing |
| `setn3270` | SETn3270 | TN3270 MitM proxy |
| `catmap` | CATMAP | z/OS catalog mapping |
| `dvca` | DVCA | Damn Vulnerable CICS App |
| `ansi2ebcdic` | ANSi2EBCDiC | ANSI to EBCDIC converter |
| `ansi2bms` | ANSi2BMS | ANSI to BMS converter |

## MainframedIntegration Class

### Initialization

```python
from birpv2_modules.integrations.mainframed_tools import MainframedIntegration

# Default tools path
integration = MainframedIntegration()

# Custom tools path
integration = MainframedIntegration(tools_path='/opt/mainframed')
```

### Tool Management

```python
# List all tools with descriptions
integration.list_tools()

# Check if tool is installed
if integration.check_tool_installed('hack3270'):
    print("hack3270 is ready")

# Install single tool
integration.install_tool('hack3270')

# Install all tools
integration.install_all_tools()

# Generate status report
report = integration.generate_tool_report()
for tool_id, info in report['tools'].items():
    status = "Installed" if info['installed'] else "Not installed"
    print(f"{tool_id}: {status}")
```

### hack3270

TN3270 data stream manipulation for CICS application testing.

```python
# Launch hack3270 proxy
integration.launch_hack3270(
    target='192.168.1.100:23',
    proxy_port=2323
)

# Connect your terminal to localhost:2323
# hack3270 intercepts and allows modification of traffic
```

### NMAP Scripts

Run mainframed's NMAP scripts for TN3270 enumeration.

```python
# Grab TN3270 screen
integration.grab_screen('192.168.1.100')

# Find hidden fields
integration.find_hidden_fields('192.168.1.100')

# TSO user enumeration
integration.tso_enumerate(
    target='192.168.1.100',
    userlist='users.txt',
    commands=''  # Commands to reach TSO prompt
)

# TSO brute force
integration.tso_brute_force(
    target='192.168.1.100',
    userlist='users.txt',
    passlist='passwords.txt',
    commands=''
)

# CICS enumeration (requires CICS)
integration.cics_enumerate(
    target='192.168.1.100',
    commands='cics'
)
```

### SETn3270 MitM Proxy

Man-in-the-middle proxy for TN3270 traffic.

```python
# Start proxy
integration.launch_setn3270(
    listen_port=3270,      # Local port to listen on
    target='192.168.1.100' # Target mainframe
)

# Connect terminal to localhost:3270
# All traffic is intercepted and can be modified
```

### MFSniffer

Passive TN3270 traffic sniffing (requires root).

```python
# Start sniffer
integration.launch_mfsniffer(
    interface='lo0',        # Network interface (lo0 for localhost)
    ip_address='127.0.0.1', # Target IP to monitor
    port='23'               # Target port
)
```

### Privilege Escalation Examples

View examples of z/OS privilege escalation techniques.

```python
# Show privesc script examples and usage
integration.show_privesc_examples()
```

This displays:
- APF authorization exploits
- RACF/security bypass techniques
- Dataset access exploits
- Job submission exploits
- System command exploits

## CLI Interface

The module includes a standalone CLI:

```python
from birpv2_modules.integrations.mainframed_tools import main
main()
```

Or run directly:
```bash
python -m birpv2_modules.integrations.mainframed_tools
```

Menu options:
1. List all tools
2. Install tool
3. Install all tools
4. Launch hack3270
5. TSO User Enumeration
6. TSO Brute Force
7. CICS Enumeration
8. Grab TN3270 Screen
9. Find Hidden Fields
10. Launch SETn3270 Proxy
11. Launch MFSniffer
12. Show Privesc Exploit Examples
13. Generate Tool Report

## Example: Security Assessment Workflow

```python
from birpv2_modules.integrations.mainframed_tools import MainframedIntegration

integration = MainframedIntegration()

# 1. Install required tools
integration.install_tool('nmap-scripts')

# 2. Reconnaissance - grab initial screen
integration.grab_screen('192.168.1.100')

# 3. Check for hidden fields
integration.find_hidden_fields('192.168.1.100')

# 4. Enumerate TSO users
integration.tso_enumerate(
    '192.168.1.100',
    userlist='common_users.txt'
)

# 5. If CICS available, enumerate transactions
integration.cics_enumerate('192.168.1.100')

# 6. For deeper analysis, launch hack3270 proxy
integration.launch_hack3270('192.168.1.100:23')
```

## Requirements

- **nmap** - For NMAP scripts
- **git** - For tool installation
- **python3** - For Python-based tools
- **sudo** - For MFSniffer (root required)

Install NMAP:
```bash
# macOS
brew install nmap

# Linux
sudo apt-get install nmap
```

## See Also

- [Security README](../security/README.md) - Built-in security scanning
- [DVCA README](../dvca/README.md) - Vulnerable test application
- [Emulator README](../emulator/README.md) - TN3270 connection
