# Utils Module

Utility functions for BIRP v2 - logging, keyboard input, and search functionality.

## Overview

The `utils` module provides:
- **logger** - Colored console logging with file output
- **search** - Transaction history search
- **getch** - Cross-platform keyboard input
- **helpers** - Miscellaneous helper functions
- **session_logger** - Session recording

## Logger

Structured logging with color support and file output.

### Quick Start

```python
from birpv2_modules.utils.logger import log_info, log_warning, log_error

log_info('Connected to mainframe')
log_warning('Slow response detected')
log_error('Connection failed')
```

### BIRPLogger Class

```python
from birpv2_modules.utils.logger import BIRPLogger

logger = BIRPLogger(
    quiet=False,              # Suppress info/warning if True
    log_file='birp.log',      # Optional file output
    log_level=logging.INFO    # Minimum level to log
)

logger.info('Message')
logger.warning('Warning')
logger.error('Error')
logger.debug('Debug info')
logger.success('Good result')
```

### Global Logger Functions

| Function | Description | Color |
|----------|-------------|-------|
| `log_info(msg)` | Informational message | Blue |
| `log_warning(msg)` | Warning message | Yellow |
| `log_error(msg)` | Error message | Red |
| `log_debug(msg)` | Debug message | Cyan |
| `log_success(msg)` | Success message | Blue |

### Log Prefixes

| Level | Prefix | Color |
|-------|--------|-------|
| DEBUG | `[?]` | Cyan |
| INFO | `[+]` | Blue |
| WARNING | `[!]` | Yellow |
| ERROR | `[#]` | Red |
| CRITICAL | `[#]` | Bright Red |

### Setup Global Logger

```python
from birpv2_modules.utils.logger import setup_logger, get_logger

# Configure global logger
setup_logger(log_file='session.log', log_level='DEBUG')

# Get logger instance
logger = get_logger()
logger.info('Configured!')
```

### Legacy Interface

```python
from birpv2_modules.utils.logger import create_logger

logger = create_logger(quiet=False, log_file='birp.log')
logger.log('Message', kind='info', level=1)  # 1 = indented
```

## Search

Search transaction history for text or regex patterns.

### find_first()

Find first occurrence of text in history.

```python
from birpv2_modules.utils.search import find_first

# Returns (trans_id, req/resp, row, col) or (-1,-1,-1,-1)
result = find_first(history, 'PASSWORD')
trans_id, rr, row, col = result

if trans_id >= 0:
    print(f"Found in transaction {trans_id}")
    print(f"{'Request' if rr == 0 else 'Response'} at row {row}, col {col}")
```

### find_all()

Find all occurrences with options.

```python
from birpv2_modules.utils.search import find_all

# Case-insensitive search
results = find_all(history, 'error', case_sensitive=False)

# Regex search
results = find_all(history, r'IKJ\d+', use_regex=True)

# Process results
for trans_id, rr, row, col in results:
    screen_type = 'Request' if rr == 0 else 'Response'
    print(f"Trans {trans_id}: {screen_type} at [{row},{col}]")
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `history` | History | required | History object to search |
| `text` | str | required | Text or regex pattern |
| `case_sensitive` | bool | True | Case-sensitive matching |
| `use_regex` | bool | False | Interpret as regex |

## Getch

Cross-platform single-character keyboard input.

### Usage

```python
from birpv2_modules.utils.getch import getch

# Wait for keypress
key = getch()

# Check key
if ord(key) == 27:  # ESC
    print("Escape pressed")
elif ord(key) == 13:  # Enter
    print("Enter pressed")
else:
    print(f"Key: {key}")
```

### Special Key Codes

| Key | Code |
|-----|------|
| ESC | 27 |
| Enter | 13 or 10 |
| Tab | 9 |
| Backspace | 127 or 8 |
| Ctrl-C | 3 |
| Ctrl-D | 4 |
| Ctrl-H | 8 |
| Ctrl-R | 18 |
| Ctrl-U | 21 |

## Helpers

Miscellaneous utility functions.

```python
from birpv2_modules.utils.helpers import (
    # Various helper functions
)
```

## Session Logger

Record sessions for later analysis.

```python
from birpv2_modules.utils.session_logger import SessionLogger

session = SessionLogger('session_001')

# Log events
session.log_connect('localhost:3270')
session.log_screen(screen)
session.log_command('ISPF')

# Save session
session.save('session_001.json')
```

## Example: Search and Log

```python
from birpv2_modules.utils.logger import log_info, log_warning
from birpv2_modules.utils.search import find_all

# Search for sensitive data
patterns = ['PASSWORD', 'USERID', 'SECRET']

for pattern in patterns:
    results = find_all(history, pattern, case_sensitive=False)
    if results:
        log_warning(f"Found {len(results)} occurrences of '{pattern}'")
        for trans_id, rr, row, col in results:
            log_info(f"  Transaction {trans_id} at [{row},{col}]")
    else:
        log_info(f"'{pattern}' not found")
```

## Module Contents

### logger.py

| Export | Description |
|--------|-------------|
| `BIRPLogger` | Logger class with colors |
| `ColoredFormatter` | Log formatter |
| `create_logger()` | Create logger instance |
| `setup_logger()` | Configure global logger |
| `get_logger()` | Get global logger |
| `log_info()` | Log info message |
| `log_warning()` | Log warning message |
| `log_error()` | Log error message |
| `log_debug()` | Log debug message |
| `log_success()` | Log success message |

### search.py

| Function | Description |
|----------|-------------|
| `find_first(history, text)` | Find first occurrence |
| `find_all(history, text, ...)` | Find all occurrences |

### getch.py

| Function | Description |
|----------|-------------|
| `getch()` | Read single character |

## See Also

- [CLI README](../cli/README.md) - Uses getch for interactive mode
- [Security README](../security/README.md) - Uses search for scanning
- [Core README](../core/README.md) - History class for searching
