# Emulator Module

TN3270 terminal emulator wrapper with timeout protection and cross-platform support.

## Overview

The `emulator` module provides a Python wrapper around x3270/s3270 for interacting with IBM mainframes via the TN3270 protocol. It extends the `py3270` library with:

- Timeout protection for commands
- Cross-platform support (macOS, Linux, Windows)
- Safe field filling with protection checking
- Screenshot capabilities
- Connection state management

## Requirements

You must have x3270 installed:

```bash
# macOS
brew install x3270

# Linux (Debian/Ubuntu)
sudo apt-get install x3270

# Windows
# Download wc3270 from x3270.bgp.nu
```

## Quick Start

```python
from birpv2_modules.emulator.wrapper import WrappedEmulator

# Create emulator (visible=True for GUI, False for headless)
em = WrappedEmulator(visible=False, delay=0.5)

# Connect to mainframe
em.connect('localhost:3270', timeout=30)

# Check connection
if em.is_connected():
    print("Connected!")

# Read screen
buffer = em.exec_command(b'ReadBuffer(Ascii)').data
print(buffer)

# Send text and Enter
em.send_string('USERID')
em.send_enter()

# Get cursor position
row, col = em.get_pos()
print(f"Cursor at: {row}, {col}")

# Clean up
em.terminate()
```

## Classes

### WrappedEmulator

Main emulator class with platform-specific configuration.

```python
em = WrappedEmulator(
    visible=True,           # True=x3270 GUI, False=s3270 headless
    delay=0,                # Delay between commands (seconds)
    window_title="BIRP",    # Window title (GUI mode only)
    command_timeout=10      # Default timeout for commands (seconds)
)
```

### Key Methods

#### Connection

```python
# Connect with timeout
em.connect('host:port', timeout=30)

# Check if connected
em.is_connected()

# Get host info
info = em.get_hostinfo()
```

#### Screen Reading

```python
# Get screen as ASCII
buffer = em.screen_get(timeout=5)

# Read buffer with field markers
result = em.exec_command(b'ReadBuffer(Ascii)')
buffer = result.data

# Search for text on screen
found = em.find_response('READY')
```

#### Input

```python
# Send string
em.send_string('text')
em.safe_send_string('text', timeout=5)  # With timeout

# Send Enter
em.send_enter()

# Send PF/PA keys
em.safe_send_pf(3, timeout=5)  # PF3
em.exec_command(b'PA(1)')      # PA1

# Move cursor
em.move_to(10, 15)  # row, col

# Safe field fill (checks protection)
em.safe_fieldfill(ypos=10, xpos=15, tosend='data', length=20)

# Safe send (stops if field protection triggered)
success = em.safe_send('text')
```

#### Commands with Timeout

```python
# Execute with timeout (raises TimeoutError)
result = em.exec_command_with_timeout(b'Ascii()', timeout=5)

# Safe execute (returns default on error)
result = em.safe_exec_command(b'Query(Cursor)', timeout=2, default=None)
```

#### Screenshots

```python
# Take screenshot
path = em.take_screenshot()  # Auto-named with timestamp
path = em.take_screenshot('login_screen.png')  # Custom name
```

#### Cursor

```python
# Get current position
row, col = em.get_pos(timeout=2)

# Delete current field content
em.delete_field()
```

## Timeout Handling

All commands support timeout protection to prevent hanging:

```python
from birpv2_modules.emulator.wrapper import WrappedEmulator, TimeoutError

em = WrappedEmulator(command_timeout=10)  # Default 10s timeout

try:
    result = em.exec_command_with_timeout(b'Wait(10,3270Mode)', timeout=5)
except TimeoutError as e:
    print(f"Command timed out: {e}")
```

## Platform Support

The wrapper automatically configures executables based on platform:

| Platform | GUI Emulator | Headless Emulator |
|----------|--------------|-------------------|
| macOS | x3270 | s3270 |
| Linux | x3270 | s3270 |
| Windows | wc3270.exe | - |

Common paths searched:
- `~/.local/bin/x3270` (custom builds)
- `/opt/homebrew/bin/x3270` (Homebrew on Apple Silicon)
- `/usr/local/bin/x3270` (Homebrew on Intel Mac)
- `/usr/bin/x3270` (Linux)

## Example: Complete Session

```python
from birpv2_modules.emulator.wrapper import WrappedEmulator
from birpv2_modules.core.models import Screen, Transaction, History

# Initialize
em = WrappedEmulator(visible=False, delay=0.5)
history = History()

try:
    # Connect
    em.connect('localhost:3270')

    # Read initial screen
    buffer = em.exec_command(b'ReadBuffer(Ascii)').data
    request_screen = Screen(buffer)

    # Login
    em.send_string('TSO USERID')
    em.send_enter()

    # Wait for response
    em.exec_command(b'Wait(5,3270Mode)')

    # Read response
    buffer = em.exec_command(b'ReadBuffer(Ascii)').data
    response_screen = Screen(buffer)

    # Record transaction
    trans = Transaction(
        request=request_screen,
        response=response_screen,
        data=response_screen.modified_fields,
        key='enter',
        host='localhost:3270'
    )
    history.append(trans)

    # Check for hidden fields
    for field in response_screen.hidden_fields:
        if field.contents.strip():
            print(f"Hidden field data: {field.contents}")

finally:
    em.terminate()
```

## See Also

- [Core Models](../core/README.md) - Screen, Field, Transaction classes
- [CLI Console](../cli/README.md) - Interactive console mode
- [Security Scanner](../security/README.md) - Automated security scanning
