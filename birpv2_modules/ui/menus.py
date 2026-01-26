"""Menu system for BIRP"""
from colorama import Fore
import sys

MAIN_MENU = """
BIRP Menu
=========

1 - Interactive Mode
2 - View History
3 - Find Transaction
4 - Python Console
5 - Save History (Pickle)
6 - Export History (JSON/CSV/HTML/XML)
X - Quit

Selection: """

INTERACTIVE_HELP = """
Interactive mode help
=====================

Hit ESC to exit interactive mode.

Most keys will be passed directly to x3270. Except:
Ctrl-c		- Clear
Ctrl-q/w/e	- PA1, PA2, PA3
Ctrl-r		- Re-print the markedup view of the current screen
Ctrl-u		- Manually push the last interaction as a transaction
Ctrl-p		- Drop to Python interactive shell
Ctrl-s		- Create timestamped HTML file of the current screen
Ctrl-k		- Color key
Ctrl-h		- This help
Alt-F8-11	- PF13-16
Alt-F12		- PF24

Hitting Enter, any of the PF/PA keys, or Ctrl-u will record a transaction."""

COLOR_KEY = f"""
Color Key
=========

•			- Start of field marker
Hidden Fields		- {Fore.RED}Red background{Fore.RESET}
Modified Fields		- {Fore.YELLOW}Yellow text{Fore.RESET}
Input Fields		- {Fore.GREEN}Green background{Fore.RESET}
"""
