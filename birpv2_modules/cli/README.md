# CLI Module

Console-based interface for BIRP v2 - text-based interactive terminal for mainframe operations.

## Overview

The `cli` module provides a menu-driven console interface for:
- Interactive TN3270 terminal sessions
- Transaction history viewing and searching
- Export functionality (JSON, CSV, HTML, XML)
- Python REPL with emulator access

## Quick Start

```python
from birpv2_modules.cli.console import run_console_mode

# Start console mode
run_console_mode(target='localhost:3270')
```

Or use the `ConsoleMode` class directly:

```python
from birpv2_modules.cli.console import ConsoleMode
from birpv2_modules.emulator.wrapper import WrappedEmulator
from birpv2_modules.core.models import History

em = WrappedEmulator(visible=False)
em.connect('localhost:3270')
history = History()

console = ConsoleMode(em, history, target='localhost:3270')
console.run()
```

## Main Menu

```
BIRP v2 Menu
============

1 - Interactive Mode
2 - View History
3 - Find Transaction
4 - Python Console
5 - Save History (Pickle)
6 - Export History (JSON/CSV/HTML/XML)
X - Quit

Selection:
```

## Interactive Mode

Real-time TN3270 terminal interaction with color-coded field display.

### Keyboard Controls

| Key | Action |
|-----|--------|
| ESC | Exit interactive mode |
| Enter | Send Enter to mainframe |
| Ctrl-c | Send Clear |
| Ctrl-q | Send PA1 |
| Ctrl-w | Send PA2 |
| Ctrl-e | Send PA3 |
| Ctrl-r | Refresh screen display |
| Ctrl-u | Manually record transaction |
| Ctrl-p | Drop to Python console |
| Ctrl-s | Save HTML screenshot |
| Ctrl-k | Show color key |
| Ctrl-h | Show help |
| F1-F12 | Send PF1-PF12 |
| Alt-F8-F11 | Send PF13-PF16 |
| Alt-F12 | Send PF24 |

### Color Key

The screen display uses colors to highlight field types:

| Color | Meaning |
|-------|---------|
| Red background | Hidden field (password) |
| Yellow text | Modified field |
| Green background | Input field (editable) |
| Red text | Unfielded text |

Field markers are shown as `∙` (bullet).

## Classes

### ConsoleMode

Main console interface class.

```python
class ConsoleMode:
    def __init__(self, emulator, history, target=None):
        """
        Args:
            emulator: WrappedEmulator instance
            history: History instance for recording transactions
            target: Target host:port string
        """
```

#### Methods

| Method | Description |
|--------|-------------|
| `run()` | Start the main menu loop |
| `interactive_mode()` | Enter interactive terminal mode |
| `view_history()` | Display transaction history |
| `find_transaction()` | Search transactions for text/regex |
| `python_console()` | Drop to Python REPL |
| `save_history_menu()` | Save history to pickle file |
| `export_menu()` | Export history to various formats |
| `push_transaction()` | Record a transaction to history |

### run_console_mode()

Convenience function to start console mode:

```python
def run_console_mode(target=None, history=None, sleep=0):
    """
    Run BIRP in console mode

    Args:
        target: Host:port to connect to (optional)
        history: Existing History object (optional)
        sleep: Delay between commands in seconds
    """
```

## Example: Automated Script with Console

```python
from birpv2_modules.cli.console import ConsoleMode
from birpv2_modules.emulator.wrapper import WrappedEmulator
from birpv2_modules.core.models import History
from birpv2_modules.io.exporters import export_to_html

# Setup
em = WrappedEmulator(visible=False, delay=0.5)
history = History()

# Connect and perform automated actions
em.connect('localhost:3270')

# Do some automated work...
em.send_string('TSO TESTUSER')
em.send_enter()

# Then drop to interactive mode for manual exploration
console = ConsoleMode(em, history, 'localhost:3270')
console.interactive_mode()

# Export what was captured
export_to_html(history, 'session_report.html')
```

## Python Console

The Python console (option 4 or Ctrl-p) provides direct access to:

- `em` - The WrappedEmulator instance
- `history` - The History object
- `self` - The ConsoleMode instance

```python
# In Python console:
>>> em.send_string('ISPF')
>>> em.send_enter()
>>> buffer = em.exec_command(b'ReadBuffer(Ascii)').data
>>> from birpv2_modules.core.models import Screen
>>> screen = Screen(buffer)
>>> print(screen)
```

If IPython is installed, it will be used for enhanced features (tab completion, syntax highlighting).

## See Also

- [Emulator README](../emulator/README.md) - TN3270 wrapper
- [Core README](../core/README.md) - Data models
- [IO README](../io/README.md) - Export formats
