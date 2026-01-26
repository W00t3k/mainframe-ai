# UI Module

Graphical user interface components for BIRP v2 - tkinter-based terminal and history browser.

## Overview

The `ui` module provides:
- **TN3270Terminal** - Full GUI terminal emulator
- **HistoryBrowser** - Transaction history viewer
- **Display utilities** - Screen rendering helpers
- **Menus** - Context menus and dialogs

## Requirements

The UI module uses tkinter (included with Python) and requires x3270 for terminal emulation.

## TN3270Terminal

Full-featured GUI terminal for mainframe interaction.

### Quick Start

```python
import tkinter as tk
from birpv2_modules.ui.gui_terminal import TN3270Terminal

root = tk.Tk()
terminal = TN3270Terminal(
    root,
    target='localhost:3270',
    history=None,           # Uses new History if not provided
    dvmvs_mode=False        # Enable DVMVS vulnerability hints
)
root.mainloop()
```

### Features

- Full TN3270 terminal emulation
- Color-coded field display
- Connection management
- Transaction recording
- History export
- Search functionality
- Python console access

### Color Scheme

| Color | Meaning |
|-------|---------|
| Green (#00FF00) | Default foreground |
| Cyan (#00FFFF) | Protected fields |
| Yellow (#FFFF00) | Input fields |
| Red (#FF0000) | Hidden fields |
| Magenta (#FF00FF) | Modified fields |
| White (#FFFFFF) | Cursor |
| Black (#000000) | Background |

### Menu Bar

**File Menu:**
- Connect... - Open connection dialog
- Disconnect - Close connection
- Save History - Save to pickle
- Load History - Load from pickle
- Export... - Export to JSON/CSV/HTML/XML
- Exit - Close application

**View Menu:**
- Show Hidden Fields - Toggle hidden field visibility
- Show Field Markers - Toggle field marker display
- History Browser - Open transaction browser

**Tools Menu:**
- Search Transactions - Search history
- Python Console - Open Python REPL

**Help Menu:**
- Keyboard Shortcuts - Show keybindings
- DVMVS Vulnerabilities - (DVMVS mode only)
- About - Version info

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Enter | Send Enter |
| F1-F12 | Send PF1-PF12 |
| Ctrl+F1-F12 | Send PF13-PF24 |
| Escape | Clear |
| Tab | Next field |
| Shift+Tab | Previous field |
| Ctrl+C | Copy selection |
| Ctrl+V | Paste |
| Ctrl+S | Save screenshot |
| Ctrl+H | Show help |

### Methods

```python
terminal.connect('host:port')      # Connect to mainframe
terminal.disconnect()               # Disconnect
terminal.send_key('PF3')           # Send function key
terminal.refresh_screen()          # Refresh display
terminal.save_history()            # Save transaction history
terminal.export_history()          # Export dialog
terminal.show_history_browser()    # Open history browser
terminal.open_python_console()     # Open Python REPL
```

## HistoryBrowser

Browse and analyze recorded transactions.

### Quick Start

```python
from birpv2_modules.ui.history_browser import HistoryBrowser

# Open browser as child of main window
browser = HistoryBrowser(parent_window, history)
```

### Features

- Transaction list with metadata
- Request/Response screen comparison
- Field analysis (hidden, modified)
- Search functionality
- Export individual transactions
- Navigation (first, previous, next, last)

### Layout

```
+----------------------------------------------+
| Toolbar: First|Prev|Next|Last | Go to | Search|
+----------------------------------------------+
| Transaction List (Treeview)                   |
| ID | Timestamp | Key | Host | Request | Resp  |
+----------------------------------------------+
| Request Screen          | Response Screen     |
|                         |                     |
+----------------------------------------------+
| Field Details                                 |
| Hidden: [...] | Modified: [...] | Input: [...] |
+----------------------------------------------+
```

### Methods

```python
browser.first_transaction()        # Go to first
browser.prev_transaction()         # Go to previous
browser.next_transaction()         # Go to next
browser.last_transaction()         # Go to last
browser.goto_transaction()         # Go to specific index
browser.show_search()              # Open search dialog
browser.export_transaction()       # Export current
```

## Display Utilities

Helper functions for screen rendering.

```python
from birpv2_modules.ui.display import (
    format_screen_text,
    highlight_fields,
    create_color_map
)

# Format screen for display
formatted = format_screen_text(screen)

# Create field highlighting
color_map = create_color_map(screen)
```

## Menus

Context menus and dialog helpers.

```python
from birpv2_modules.ui.menus import (
    create_context_menu,
    show_connect_dialog,
    show_export_dialog
)
```

## Example: Custom Terminal

```python
import tkinter as tk
from birpv2_modules.ui.gui_terminal import TN3270Terminal
from birpv2_modules.core.models import History

class CustomTerminal(TN3270Terminal):
    """Custom terminal with additional features"""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.add_custom_menu()

    def add_custom_menu(self):
        """Add custom menu items"""
        custom_menu = tk.Menu(self.master.config()['menu'][4], tearoff=0)
        custom_menu.add_command(label="Auto Login", command=self.auto_login)
        custom_menu.add_command(label="Run Script", command=self.run_script)

    def auto_login(self):
        """Automated login sequence"""
        if self.connected:
            self.emulator.send_string('USERID')
            self.emulator.send_enter()
            # ... more automation

    def run_script(self):
        """Run automation script"""
        pass

# Launch
root = tk.Tk()
terminal = CustomTerminal(root, target='localhost:3270')
root.mainloop()
```

## Module Contents

### gui_terminal.py

| Class | Description |
|-------|-------------|
| `TN3270Terminal` | Main GUI terminal |

### history_browser.py

| Class | Description |
|-------|-------------|
| `HistoryBrowser` | Transaction browser |

### display.py

| Function | Description |
|----------|-------------|
| `format_screen_text()` | Format screen for display |
| Display helpers | Various rendering utilities |

### menus.py

| Function | Description |
|----------|-------------|
| `create_context_menu()` | Build context menu |
| Menu helpers | Dialog functions |

## See Also

- [CLI README](../cli/README.md) - Text-based console alternative
- [Core README](../core/README.md) - Screen and History classes
- [Emulator README](../emulator/README.md) - TN3270 wrapper
