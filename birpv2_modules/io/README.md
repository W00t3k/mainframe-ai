# I/O Module

File operations and export functionality for BIRP v2 - export transaction history to multiple formats.

## Overview

The `io` module provides:
- Export to JSON, CSV, HTML, and XML formats
- Automatic format detection from file extension
- Pickle-based session persistence

## Quick Start

```python
from birpv2_modules import export_to_json, export_to_html, auto_export

# Export to specific format
export_to_json(history, 'session.json')
export_to_html(history, 'report.html')

# Auto-detect format from extension
auto_export(history, 'data.csv')  # Exports as CSV
auto_export(history, 'data.xml')  # Exports as XML
```

## Export Functions

### export_to_json()

Export transaction history to JSON format with full field details.

```python
from birpv2_modules.io.exporters import export_to_json

success = export_to_json(
    history,              # History object
    'output.json',        # Output filename
    pretty=True           # Pretty print (default: True)
)
```

**JSON Structure:**
```json
[
  {
    "id": 0,
    "timestamp": "2024-01-15 10:30:45",
    "host": "mainframe:3270",
    "key": "enter",
    "comment": "",
    "request": {
      "screen": ["line1", "line2", ...],
      "rows": 24,
      "cols": 80,
      "protected_fields": [...],
      "input_fields": [...],
      "hidden_fields": [...]
    },
    "response": {
      "screen": [...],
      "rows": 24,
      "cols": 80,
      "protected_fields": [...],
      "input_fields": [...],
      "hidden_fields": [...]
    },
    "data": [
      {"row": 10, "col": 15, "contents": "USER001"}
    ]
  }
]
```

### export_to_csv()

Export transaction summary to CSV format.

```python
from birpv2_modules.io.exporters import export_to_csv

success = export_to_csv(history, 'output.csv')
```

**CSV Columns:**
| Column | Description |
|--------|-------------|
| Transaction ID | Sequential ID |
| Timestamp | When transaction occurred |
| Host | Target host:port |
| Key Pressed | enter, PF3, etc. |
| Request Screen (First Line) | First line of request |
| Response Screen (First Line) | First line of response |
| Modified Fields | Fields that were changed |
| Hidden Fields Count | Number of hidden fields |
| Comment | User comment |

### export_to_html()

Generate styled HTML report with dark theme.

```python
from birpv2_modules.io.exporters import export_to_html

success = export_to_html(history, 'report.html')
```

**HTML Features:**
- Dark theme with syntax highlighting
- Color-coded fields (hidden=red, modified=yellow)
- Full screen display with monospace font
- Transaction metadata
- Responsive layout

### export_to_xml()

Export to XML format with sanitized content.

```python
from birpv2_modules.io.exporters import export_to_xml

success = export_to_xml(history, 'output.xml')
```

**XML Structure:**
```xml
<?xml version="1.0" ?>
<birpv2_history>
  <transaction id="0">
    <timestamp>2024-01-15T10:30:45</timestamp>
    <host>mainframe:3270</host>
    <key>enter</key>
    <comment></comment>
    <request>
      <rows>24</rows>
      <cols>80</cols>
      <screen>
        <line>TSO LOGON...</line>
      </screen>
    </request>
    <response>
      <rows>24</rows>
      <cols>80</cols>
      <screen>
        <line>READY</line>
      </screen>
      <hidden_fields>
        <field>
          <row>12</row>
          <col>20</col>
          <contents>secretdata</contents>
        </field>
      </hidden_fields>
    </response>
    <modified_fields>
      <field>
        <row>10</row>
        <col>15</col>
        <contents>USER001</contents>
      </field>
    </modified_fields>
  </transaction>
</birpv2_history>
```

### auto_export()

Automatically detect format from filename extension.

```python
from birpv2_modules.io.exporters import auto_export

# These all work:
auto_export(history, 'data.json')   # JSON
auto_export(history, 'data.csv')    # CSV
auto_export(history, 'report.html') # HTML
auto_export(history, 'data.xml')    # XML
```

## File Operations

### save_history() / load_history()

Persist history using Python pickle.

```python
from birpv2_modules.io.file_ops import save_history, load_history

# Save
save_history(history, 'session.pickle')

# Load
history = load_history('session.pickle')
```

## Example: Complete Export Workflow

```python
from birpv2_modules.core.models import History
from birpv2_modules.io.exporters import (
    export_to_json,
    export_to_csv,
    export_to_html,
    export_to_xml
)
from birpv2_modules.io.file_ops import save_history

# After capturing transactions...
history = History()
# ... add transactions ...

# Export for different purposes
export_to_json(history, 'full_data.json')      # For parsing/analysis
export_to_csv(history, 'summary.csv')          # For spreadsheets
export_to_html(history, 'report.html')         # For viewing/sharing
export_to_xml(history, 'data.xml')             # For integration

# Save for later resumption
save_history(history, 'session.pickle')
```

## Module Contents

### exporters.py

| Function | Description |
|----------|-------------|
| `export_to_json(history, filename, pretty=True)` | Export to JSON |
| `export_to_csv(history, filename)` | Export to CSV |
| `export_to_html(history, filename)` | Export to HTML |
| `export_to_xml(history, filename)` | Export to XML |
| `auto_export(history, filename)` | Auto-detect format |

### file_ops.py

| Function | Description |
|----------|-------------|
| `save_history(history, filename)` | Save to pickle |
| `load_history(filename)` | Load from pickle |

## See Also

- [Core README](../core/README.md) - History and Transaction classes
- [Security README](../security/README.md) - Security report generation
- [CLI README](../cli/README.md) - Console export menu
