# BIRP v2 Modules

**Big Iron Recon & Pwnage v2** - A comprehensive Python toolkit for mainframe security research and TN3270 interaction.

## Overview

BIRP v2 provides a modular framework for:
- TN3270 terminal emulation and automation
- Mainframe screen parsing and analysis
- Security vulnerability scanning
- Transaction recording and replay
- Integration with external security tools

## Installation

```bash
# Clone or copy birpv2_modules to your project
# Install dependencies
pip install py3270 colorama

# Install x3270 for terminal emulation
# macOS
brew install x3270

# Linux
sudo apt-get install x3270
```

## Quick Start

```python
from birpv2_modules import Screen, Transaction, History
from birpv2_modules.emulator.wrapper import WrappedEmulator

# Connect to mainframe
em = WrappedEmulator(visible=False)
em.connect('localhost:3270')

# Read and parse screen
buffer = em.exec_command(b'ReadBuffer(Ascii)').data
screen = Screen(buffer)

# Analyze fields
print(f"Input fields: {len(screen.input_fields)}")
print(f"Hidden fields: {len(screen.hidden_fields)}")

# Display screen
print(screen)
```

## Module Structure

```
birpv2_modules/
├── __init__.py          # Main exports
├── core/                # Data models
│   ├── models.py        # Field, Screen, Transaction, History
│   └── README.md
├── emulator/            # TN3270 wrapper
│   ├── wrapper.py       # WrappedEmulator class
│   └── README.md
├── cli/                 # Console interface
│   ├── console.py       # ConsoleMode class
│   └── README.md
├── ui/                  # GUI components
│   ├── gui_terminal.py  # TN3270Terminal
│   ├── history_browser.py
│   └── README.md
├── io/                  # Export functionality
│   ├── exporters.py     # JSON, CSV, HTML, XML
│   ├── file_ops.py      # Pickle save/load
│   └── README.md
├── security/            # Security tools
│   ├── scanner.py       # SecurityScanner, Fuzzer
│   ├── reporter.py      # Report generation
│   ├── replay.py        # Session replay
│   └── README.md
├── integrations/        # External tools
│   ├── mainframed_tools.py
│   └── README.md
├── utils/               # Utilities
│   ├── logger.py        # Colored logging
│   ├── search.py        # History search
│   ├── getch.py         # Keyboard input
│   └── README.md
├── zos/                 # z/OS helpers
│   ├── cics_helper.py   # CICS parsing
│   ├── tso_helper.py    # TSO/ISPF parsing
│   ├── racf_helper.py   # RACF parsing
│   ├── jes_parser.py    # JES parsing
│   └── README.md
└── dvca/                # Test application
    └── README.md
```

## Main Exports

```python
from birpv2_modules import (
    # Version info
    __version__,
    __author__,

    # Core models
    Field,
    Screen,
    Transaction,
    History,

    # Export functions
    export_to_json,
    export_to_csv,
    export_to_html,
    export_to_xml,
    auto_export,

    # Logging
    BIRPLogger,
    create_logger,

    # Search
    find_all,
    find_first,
)
```

## Usage Examples

### Console Mode

```python
from birpv2_modules.cli.console import run_console_mode

run_console_mode(target='localhost:3270')
```

### GUI Mode

```python
import tkinter as tk
from birpv2_modules.ui.gui_terminal import TN3270Terminal

root = tk.Tk()
terminal = TN3270Terminal(root, target='localhost:3270')
root.mainloop()
```

### Security Scanning

```python
from birpv2_modules.security.scanner import SecurityScanner
from birpv2_modules.security.reporter import SecurityReporter

scanner = SecurityScanner(emulator, history)
findings = scanner.scan_history()

reporter = SecurityReporter(history, findings)
reporter.generate_html_report('report.html')
```

### Transaction Replay

```python
from birpv2_modules.security.replay import SessionReplay

replay = SessionReplay(emulator, history)
result = replay.replay_transaction(history[0])
```

### z/OS Screen Analysis

```python
from birpv2_modules.zos.cics_helper import CICSHelper
from birpv2_modules.zos.tso_helper import TSOHelper

cics = CICSHelper()
if cics.detect_cics_screen(screen_text):
    messages = cics.parse_cics_message(screen_text)
```

### Export Data

```python
from birpv2_modules import export_to_json, export_to_html

export_to_json(history, 'session.json')
export_to_html(history, 'report.html')
```

## Attribution

BIRP v2 is based on the original BIRP by Dominic White (@singe) at SensePost.

Integrations with mainframed security tools by Soldier of FORTRAN (@mainframed767).

## Version

- **Version:** 2.0.0
- **Author:** @w00tock

## Documentation

Each module has its own README with detailed documentation:

- [Core Models](core/README.md) - Field, Screen, Transaction, History
- [Emulator](emulator/README.md) - TN3270 wrapper
- [CLI](cli/README.md) - Console interface
- [UI](ui/README.md) - GUI terminal
- [I/O](io/README.md) - Export functionality
- [Security](security/README.md) - Scanning and replay
- [Integrations](integrations/README.md) - External tools
- [Utils](utils/README.md) - Logging and search
- [z/OS](zos/README.md) - z/OS subsystem helpers
- [DVCA](dvca/README.md) - Vulnerable test application

## License

MIT License
