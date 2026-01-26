#!/usr/bin/env python3
"""
Console mode for BIRP v2
Text-based interactive terminal
"""

import sys
from colorama import Fore, Back, Style, init
from ..core.models import Screen, Transaction, History
from ..emulator.wrapper import WrappedEmulator
from ..io.file_ops import save_history, load_history
from ..io.exporters import export_to_json, export_to_csv, export_to_html, export_to_xml
from ..utils.getch import getch
from ..utils.logger import log_info, log_error, log_warning
from ..utils.search import find_all

init()

MENU_TEXT = """
BIRP v2 Menu
============

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
Ctrl-c      - Clear
Ctrl-q/w/e  - PA1, PA2, PA3
Ctrl-r      - Re-print the marked-up view of the current screen
Ctrl-u      - Manually push the last interaction as a transaction
Ctrl-p      - Drop to Python interactive shell
Ctrl-s      - Create timestamped HTML file of the current screen
Ctrl-k      - Color key
Ctrl-h      - This help
Alt-F8-11   - PF13-16
Alt-F12     - PF24

Hitting Enter, any of the PF/PA keys, or Ctrl-u will record a transaction."""

COLOR_KEY = f"""
Color Key
=========

\u2219               - Start of field marker{Style.RESET_ALL}
Hidden Fields       - {Back.RED}Red background{Style.RESET_ALL}
Modified Fields     - {Fore.YELLOW}Yellow text{Style.RESET_ALL}
Input Fields        - {Back.GREEN}Green background{Style.RESET_ALL}
"""


class ConsoleMode:
    """Console-based BIRP interface"""
    
    def __init__(self, emulator, history, target=None):
        self.em = emulator
        self.history = history
        self.target = target
        self.host = target if target else 'unknown'
        
    def run(self):
        """Run the console menu"""
        while True:
            try:
                choice = input(MENU_TEXT).strip().upper()
                
                if choice == '1':
                    self.interactive_mode()
                elif choice == '2':
                    self.view_history()
                elif choice == '3':
                    self.find_transaction()
                elif choice == '4':
                    self.python_console()
                elif choice == '5':
                    self.save_history_menu()
                elif choice == '6':
                    self.export_menu()
                elif choice == 'X':
                    print("\nExiting BIRP v2. Goodbye!")
                    break
                else:
                    print("Invalid selection. Please try again.")
            except KeyboardInterrupt:
                print("\n\nInterrupted. Exiting...")
                break
            except Exception as e:
                log_error(f"Menu error: {e}")
    
    def interactive_mode(self):
        """Interactive TN3270 mode"""
        print("\nEntering interactive mode...")
        print("Press Ctrl-h for help, ESC to exit")
        print(COLOR_KEY)
        
        if not self.em.is_connected():
            print("Not connected to a mainframe. Please connect first.")
            return
        
        # Get initial screen
        try:
            buffer = self.em.exec_command_with_timeout(b'ReadBuffer(Ascii)', timeout=5).data
            screen = Screen(buffer)
            print(screen.colorbuffer)
        except Exception as e:
            log_error(f"Failed to read screen: {e}")
            return
        
        request_screen = screen
        
        while True:
            try:
                key = getch()
                
                # ESC - Exit
                if ord(key) == 27:
                    print("\nExiting interactive mode...")
                    break
                
                # Ctrl-h - Help
                elif ord(key) == 8:
                    print(INTERACTIVE_HELP)
                    continue
                
                # Ctrl-k - Color key
                elif ord(key) == 11:
                    print(COLOR_KEY)
                    continue
                
                # Ctrl-r - Refresh screen
                elif ord(key) == 18:
                    buffer = self.em.exec_command_with_timeout(b'ReadBuffer(Ascii)', timeout=5).data
                    screen = Screen(buffer)
                    print(screen.colorbuffer)
                    continue

                # Ctrl-c - Clear
                elif ord(key) == 3:
                    self.em.exec_command_with_timeout(b'Clear()', timeout=5)
                    buffer = self.em.exec_command_with_timeout(b'ReadBuffer(Ascii)', timeout=5).data
                    screen = Screen(buffer)
                    print(screen.colorbuffer)
                    continue
                
                # Ctrl-p - Python console
                elif ord(key) == 16:
                    self.python_console()
                    continue
                
                # Ctrl-u - Manual transaction push
                elif ord(key) == 21:
                    self.push_transaction(request_screen, screen)
                    request_screen = screen
                    continue
                
                # Enter
                elif ord(key) == 13 or ord(key) == 10:
                    self.em.send_enter()
                    buffer = self.em.exec_command_with_timeout(b'ReadBuffer(Ascii)', timeout=5).data
                    response_screen = Screen(buffer)
                    self.push_transaction(request_screen, response_screen, 'enter')
                    request_screen = response_screen
                    screen = response_screen
                    print(screen.colorbuffer)
                
                # Regular keys - send to emulator
                else:
                    self.em.send_string(key)
                    
            except KeyboardInterrupt:
                print("\nExiting interactive mode...")
                break
            except Exception as e:
                log_error(f"Interactive mode error: {e}")
                break
    
    def push_transaction(self, request, response, key='manual'):
        """Record a transaction"""
        try:
            data = response.modified_fields
            trans = Transaction(request, response, data, key, self.host)
            self.history.append(trans)
            log_info(f"Transaction recorded: {key}")
        except Exception as e:
            log_error(f"Failed to record transaction: {e}")
    
    def view_history(self):
        """View transaction history"""
        if len(self.history) == 0:
            print("\nNo transactions recorded yet.")
            return
        
        print(f"\n=== Transaction History ({len(self.history)} transactions) ===\n")
        
        for i, trans in enumerate(self.history):
            print(f"Transaction {i}:")
            print(f"  Timestamp: {trans.timestamp}")
            print(f"  Key: {trans.key}")
            print(f"  Host: {trans.host}")
            print(f"  Modified fields: {len(trans.data)}")
            print()
    
    def find_transaction(self):
        """Search transactions"""
        if len(self.history) == 0:
            print("\nNo transactions to search.")
            return
        
        term = input("\nEnter search term: ").strip()
        if not term:
            return
        
        case_sensitive = input("Case sensitive? (y/n): ").strip().lower() == 'y'
        use_regex = input("Use regex? (y/n): ").strip().lower() == 'y'
        
        results = find_all(self.history, term, case_sensitive, use_regex)
        
        if results:
            print(f"\nFound {len(results)} match(es):")
            for trans_id, rr, row, col in results:
                trans_type = "Request" if rr == 0 else "Response"
                print(f"  Transaction {trans_id} - {trans_type} at row {row}, col {col}")
        else:
            print(f"\nNo matches found for '{term}'")
    
    def python_console(self):
        """Drop to Python console"""
        print("\nEntering Python console...")
        print("Available variables: em (emulator), history, self")
        print("Type 'exit()' to return to BIRP menu")
        
        try:
            from IPython import embed
            embed()
        except ImportError:
            import code
            code.interact(local={'em': self.em, 'history': self.history, 'self': self})
    
    def save_history_menu(self):
        """Save history to pickle file"""
        if len(self.history) == 0:
            print("\nNo transactions to save.")
            return
        
        filename = input("\nEnter filename (default: history.pickle): ").strip()
        if not filename:
            filename = "history.pickle"
        
        try:
            save_history(self.history, filename)
            print(f"History saved to {filename}")
        except Exception as e:
            log_error(f"Failed to save history: {e}")
    
    def export_menu(self):
        """Export history menu"""
        if len(self.history) == 0:
            print("\nNo transactions to export.")
            return
        
        print("\nExport formats:")
        print("1 - JSON")
        print("2 - CSV")
        print("3 - HTML")
        print("4 - XML")
        
        choice = input("Select format: ").strip()
        filename = input("Enter filename: ").strip()
        
        if not filename:
            print("Filename required.")
            return
        
        try:
            if choice == '1':
                export_to_json(self.history, filename)
            elif choice == '2':
                export_to_csv(self.history, filename)
            elif choice == '3':
                export_to_html(self.history, filename)
            elif choice == '4':
                export_to_xml(self.history, filename)
            else:
                print("Invalid format.")
                return
            
            print(f"History exported to {filename}")
        except Exception as e:
            log_error(f"Failed to export: {e}")


def run_console_mode(target=None, history=None, sleep=0):
    """Run BIRP in console mode"""
    
    # Create emulator (visible=False uses s3270 for console mode)
    em = WrappedEmulator(visible=False, delay=sleep)
    
    # Create or use provided history
    if history is None:
        history = History()
    
    # Connect if target provided
    if target:
        log_info(f'Connecting to {target}')
        try:
            em.connect(target)
        except Exception as e:
            log_error(f'Connection failure: {e}')
            sys.exit(1)
        
        if not em.is_connected():
            log_error(f'Could not connect to {target}')
            sys.exit(1)
        
        log_info('Connected successfully')
    
    # Run console
    console = ConsoleMode(em, history, target)
    console.run()
