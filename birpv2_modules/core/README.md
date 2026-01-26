# Core Models

Core data models for BIRP v2 - the foundational classes for representing TN3270 screen data, fields, transactions, and session history.

## Overview

The `core` module provides pure Python data models with no external dependencies (except colorama for display). These models represent the fundamental data structures used throughout BIRP.

## Classes

### Field

Represents a single field on a 3270 screen.

```python
from birpv2_modules.core.models import Field

field = Field(
    contents="USER001",
    row=10,
    col=15,
    rawstatus="SF(c0=c8)",
    protected=1,
    hidden=0
)

print(field.contents)     # "USER001"
print(field.row, field.col)  # 10, 15
print(len(field))         # 7
```

**Attributes:**
| Attribute | Type | Description |
|-----------|------|-------------|
| `contents` | str | Field text content |
| `row` | int | Row position (0-indexed) |
| `col` | int | Column position (0-indexed) |
| `rawstatus` | str | Raw x3270 field status |
| `protected` | int | 1 if protected (read-only), 0 if input |
| `hidden` | int | 1 if hidden field (password), 0 if visible |
| `numeric` | int | 1 if numeric-only field |
| `modify` | int | 1 if field was modified |

### Screen

Represents a complete 3270 terminal screen.

```python
from birpv2_modules.core.models import Screen

# Create from raw buffer (x3270 ReadBuffer output)
screen = Screen(raw_buffer)

# Access screen data
print(screen.rows, screen.cols)  # 24, 80
print(str(screen))               # Plain text representation

# Access fields
for field in screen.fields:
    print(f"{field.row},{field.col}: {field.contents}")

# Filter field types
input_fields = screen.input_fields      # Editable fields
protected = screen.protected_fields     # Read-only fields
hidden = screen.hidden_fields           # Password fields
modified = screen.modified_fields       # Changed fields
```

**Properties:**
| Property | Type | Description |
|----------|------|-------------|
| `rows` | int | Number of rows (typically 24 or 43) |
| `cols` | int | Number of columns (typically 80 or 132) |
| `rawbuffer` | list | Raw hex buffer from x3270 |
| `plainbuffer` | list | Buffer without field markers |
| `stringbuffer` | list | List of screen lines as strings |
| `colorbuffer` | str | Color-coded display for terminal |
| `emubuffer` | str | Emulator-style display |
| `fields` | list | All Field objects on screen |
| `input_fields` | list | Unprotected (editable) fields |
| `protected_fields` | list | Protected (read-only) fields |
| `hidden_fields` | list | Hidden (password) fields |
| `modified_fields` | list | Fields that were modified |

### Transaction

Represents a single TN3270 request/response pair.

```python
from birpv2_modules.core.models import Transaction

trans = Transaction(
    request=request_screen,
    response=response_screen,
    data=modified_fields,
    key='enter',
    host='mainframe.example.com:23'
)

print(trans.timestamp)  # When transaction occurred
print(trans.key)        # 'enter', 'PF(3)', etc.
print(trans.request)    # Screen before key press
print(trans.response)   # Screen after key press
```

**Attributes:**
| Attribute | Type | Description |
|-----------|------|-------------|
| `request` | Screen | Screen state before action |
| `response` | Screen | Screen state after action |
| `data` | list | Fields that were modified |
| `key` | str | Key that triggered transaction |
| `host` | str | Target host:port |
| `timestamp` | datetime | When transaction occurred |
| `comment` | str | Optional user comment |

### History

Container for tracking session transaction history.

```python
from birpv2_modules.core.models import History

history = History()

# Add transactions
history.append(transaction)

# Access transactions
print(len(history))           # Number of transactions
print(history[0])             # First transaction
print(history.last())         # Most recent transaction
print(history.count())        # Same as len()

# Iterate
for trans in history:
    print(trans.key, trans.timestamp)
```

## Field Attribute Flags

The 3270 protocol uses field attributes to control display and input behavior:

| Flag | Hex Value | Description |
|------|-----------|-------------|
| `FA_PRINTABLE` | 0xc0 | Character is printable |
| `FA_PROTECT` | 0x20 | Field is protected (read-only) |
| `FA_NUMERIC` | 0x10 | Numeric-only input |
| `FA_HIDDEN` | 0x0c | Non-display (hidden) |
| `FA_MODIFY` | 0x01 | Field was modified |

## Usage Example

```python
from birpv2_modules import Screen, Transaction, History
from birpv2_modules.emulator.wrapper import WrappedEmulator

# Create emulator and history
em = WrappedEmulator(visible=False)
history = History()

# Connect
em.connect('localhost:3270')

# Read screen
buffer = em.exec_command(b'ReadBuffer(Ascii)').data
screen = Screen(buffer)

# Analyze fields
print(f"Screen size: {screen.rows}x{screen.cols}")
print(f"Input fields: {len(screen.input_fields)}")
print(f"Hidden fields: {len(screen.hidden_fields)}")

# Check for sensitive data in hidden fields
for field in screen.hidden_fields:
    if field.contents.strip():
        print(f"WARNING: Hidden field at [{field.row},{field.col}] contains data!")

# Display with colors
print(screen.colorbuffer)
```

## See Also

- [Emulator README](../emulator/README.md) - TN3270 emulator wrapper
- [Security README](../security/README.md) - Security scanning tools
- [IO README](../io/README.md) - Export functionality
