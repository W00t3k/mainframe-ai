#!/usr/bin/env python3
"""
GUI TN3270 Terminal for BIRP v2
Provides a graphical interface for mainframe interaction
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import queue
from datetime import datetime
from ..core.models import Screen, Transaction, History
from ..emulator.wrapper import WrappedEmulator

class TN3270Terminal(tk.Frame):
    """GUI TN3270 Terminal Window"""
    
    def __init__(self, master, target='', history=None, dvmvs_mode=False):
        super().__init__(master)
        self.master = master
        self.master.title("BIRP v2 - TN3270 Terminal")
        self.master.geometry("1200x800")
        self.pack(fill=tk.BOTH, expand=True)
        
        self.target = target
        self.history = history or History()
        self.emulator = None
        self.connected = False
        self.dvmvs_mode = dvmvs_mode
        
        # Color scheme for 3270 display
        self.colors = {
            'background': '#000000',
            'foreground': '#00FF00',
            'protected': '#00FFFF',
            'input': '#FFFF00',
            'hidden': '#FF0000',
            'modified': '#FF00FF',
            'cursor': '#FFFFFF'
        }
        
        self.setup_ui()
        self.setup_keybindings()
        
        # Auto-connect if target was provided
        if self.target:
            self.after(500, lambda: self.connect(self.target))
    
    def _decode_buffer(self, buffer_data):
        """Convert buffer data from bytes to strings if needed"""
        if buffer_data and len(buffer_data) > 0 and isinstance(buffer_data[0], bytes):
            return [line.decode('utf-8') if isinstance(line, bytes) else line for line in buffer_data]
        return buffer_data
        
    def setup_ui(self):
        """Create the GUI layout"""
        
        # Menu bar
        menubar = tk.Menu(self.master)
        self.master.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Connect...", command=self.show_connect_dialog)
        file_menu.add_command(label="Disconnect", command=self.disconnect)
        file_menu.add_separator()
        file_menu.add_command(label="Save History", command=self.save_history)
        file_menu.add_command(label="Load History", command=self.load_history)
        file_menu.add_command(label="Export...", command=self.export_history)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Show Hidden Fields", command=self.toggle_hidden_fields)
        view_menu.add_command(label="Show Field Markers", command=self.toggle_field_markers)
        view_menu.add_command(label="History Browser", command=self.show_history_browser)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Search Transactions", command=self.show_search_dialog)
        tools_menu.add_command(label="Python Console", command=self.open_python_console)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Keyboard Shortcuts", command=self.show_shortcuts)
        if self.dvmvs_mode:
            help_menu.add_separator()
            help_menu.add_command(label="DVMVS Vulnerabilities", command=self.show_dvmvs_help)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self.show_about)
        
        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text="Connect", command=self.show_connect_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Disconnect", command=self.disconnect).pack(side=tk.LEFT, padx=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        ttk.Button(toolbar, text="Clear", command=self.clear_screen).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Reset", command=self.reset_screen).pack(side=tk.LEFT, padx=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # PF key buttons
        pf_frame = ttk.Frame(toolbar)
        pf_frame.pack(side=tk.LEFT, padx=5)
        for i in range(1, 13):
            ttk.Button(pf_frame, text=f"F{i}", width=4, 
                      command=lambda x=i: self.send_pf_key(x)).pack(side=tk.LEFT, padx=1)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Not connected")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Main content area
        main_frame = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Terminal display (left side)
        terminal_frame = ttk.Frame(main_frame)
        main_frame.add(terminal_frame, weight=3)
        
        ttk.Label(terminal_frame, text="Terminal Display").pack(side=tk.TOP, anchor=tk.W)
        
        self.terminal = scrolledtext.ScrolledText(
            terminal_frame,
            wrap=tk.NONE,
            width=80,
            height=24,
            font=('Courier', 12),
            bg=self.colors['background'],
            fg=self.colors['foreground'],
            insertbackground=self.colors['cursor']
        )
        self.terminal.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Configure text tags for coloring
        self.terminal.tag_config('protected', foreground=self.colors['protected'])
        self.terminal.tag_config('input', foreground=self.colors['input'], background='#003300')
        self.terminal.tag_config('hidden', foreground=self.colors['hidden'], background='#330000')
        self.terminal.tag_config('modified', foreground=self.colors['modified'])
        self.terminal.tag_config('cursor', background=self.colors['cursor'], foreground='#000000')
        
        # Info panel (right side)
        info_frame = ttk.Frame(main_frame)
        main_frame.add(info_frame, weight=1)
        
        ttk.Label(info_frame, text="Quick Start Guide", font=('Arial', 10, 'bold')).pack(side=tk.TOP, anchor=tk.W, pady=(0,5))
        
        self.info_text = scrolledtext.ScrolledText(
            info_frame,
            wrap=tk.WORD,
            width=40,
            height=24,
            font=('Courier', 10)
        )
        self.info_text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Add helpful quick start information
        if self.dvmvs_mode:
            quick_start = """
═══════════════════════════════
  DVMVS QUICK START
═══════════════════════════════

[+] Launching DVMVS (Damn Vulnerable MVS)...
[+] Deliberately insecure application for security training!

DOCUMENTATION:
  dvmvs/README.md
  dvmvs/docs/VULNERABILITIES.md
  dvmvs/docs/INSTALL.md

GETTING STARTED:
1. Wait for connection (automatic)
2. Press ENTER at logon screen
3. Run: TSO DVBANK

DVMVS CREDENTIALS:
  USER1 / PASSWORD1 (Balance: $5000)
  ADMIN / ADMIN123 (Admin access)
  TESTUSER / TEST123 (Balance: $1000)

QUICK TESTING:
* Login with any user
* Option 5 = Admin Panel (no auth check!)
* Option 6 = Command Injection
* Option 3 = View ALL transactions
* Press F1 for full vulnerability guide

PF KEYS:
  F1  - DVMVS Vulnerability Guide
  F3  - Exit/Return
  F7  - Scroll up
  F8  - Scroll down

TIPS:
* 23+ vulnerabilities to exploit
* All passwords stored in plaintext
* No authorization checks
* Command injection available
* Race conditions exploitable

SYSTEM INFO:
  MVS 3.8j TK4- on port 23
  Created by Jürgen Winkelmann
  
═══════════════════════════════
"""
        else:
            quick_start = """
═══════════════════════════════
  MVS TK4- QUICK START
═══════════════════════════════

SYSTEM INFO:
  MVS 3.8j with TK4- updates
  Hercules Emulator
  Port: 23 (telnet)

CREDITS:
  TK4- created by Jürgen Winkelmann
  MVS 3.8j by IBM (Public Domain)
  Hercules by Roger Bowler & team
  
  Special thanks to the mainframe
  preservation community!

DOCUMENTATION:
  TK4- User Guide:
  http://wotho.ethz.ch/tk4-/
  
  MVS 3.8 Documentation:
  http://www.bitsavers.org/pdf/ibm/
  370/MVS/

DEFAULT CREDENTIALS:
  Username: HERC01
  Password: CUL8TR

COMMON USERS:
  HERC02 / CUL8TR
  HERC03 / CUL8TR
  HERC04 / CUL8TR

GETTING STARTED:
1. Wait for connection
2. Press ENTER at logon screen
3. Enter username: HERC01
4. Enter password: CUL8TR
5. Press ENTER to TSO

USEFUL TSO COMMANDS:
  LOGON    - Start TSO session
  LOGOFF   - End session
  HELP     - Show help
  LISTDS   - List datasets
  SUBMIT   - Submit JCL job
  
PF KEYS:
  F1  - Help
  F3  - Exit/Return
  F7  - Scroll up
  F8  - Scroll down
  F12 - Cancel

TIPS FOR NEW USERS:
• Passwords are case-sensitive
• Use TAB to move between fields
• Protected fields can't be edited
• Press ENTER to submit input
• Watch status bar for messages
• Use HELP command for more info

TROUBLESHOOTING:
• Connection refused?
  - Check MVS is running
  - Wait 30-60s after start
• Can't type?
  - Field may be protected
  - Try TAB to next field
• Stuck?
  - Press F3 to go back
  - Type LOGOFF to exit

═══════════════════════════════
"""
        self.info_text.insert('1.0', quick_start)
        self.info_text.config(state='disabled')  # Make read-only
        
    def setup_keybindings(self):
        """Setup keyboard shortcuts"""
        self.terminal.bind('<Key>', self.handle_keypress)
        self.terminal.bind('<Return>', lambda e: self.send_enter())
        self.terminal.bind('<Escape>', lambda e: self.send_pa_key(1))
        
        # Function keys
        for i in range(1, 13):
            self.bind(f'<F{i}>', lambda e, x=i: self.send_pf_key(x))
        
        # F1 for DVMVS help if in DVMVS mode
        if self.dvmvs_mode:
            self.bind('<F1>', lambda e: self.show_dvmvs_help())
        
        # Control keys
        self.bind('<Control-c>', lambda e: self.clear_screen())
        self.bind('<Control-r>', lambda e: self.refresh_screen())
        self.bind('<Control-h>', lambda e: self.show_shortcuts())
        
    def show_connect_dialog(self):
        """Show connection dialog"""
        dialog = tk.Toplevel(self)
        dialog.title("Connect to Mainframe")
        dialog.geometry("400x200")
        dialog.transient(self)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Host:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        host_entry = ttk.Entry(dialog, width=30)
        host_entry.grid(row=0, column=1, padx=10, pady=10)
        host_entry.insert(0, "localhost")
        
        ttk.Label(dialog, text="Port:").grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
        port_entry = ttk.Entry(dialog, width=30)
        port_entry.grid(row=1, column=1, padx=10, pady=10)
        port_entry.insert(0, "23")
        
        def do_connect():
            host = host_entry.get()
            port = port_entry.get()
            target = f"{host}:{port}"
            dialog.destroy()
            self.connect(target)
        
        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=2, column=0, columnspan=2, pady=20)
        ttk.Button(button_frame, text="Connect", command=do_connect).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        host_entry.focus()
        dialog.bind('<Return>', lambda e: do_connect())
        
    def connect(self, target):
        """Connect to mainframe (async to prevent GUI freeze)"""
        import threading
        
        def do_connect():
            try:
                from ..utils.logger import log_info, log_error
                log_info(f"Starting connection to {target}")
                
                # Create emulator if needed
                if not self.emulator:
                    try:
                        log_info("Creating s3270 emulator...")
                        # Use s3270 (visible=False) - BIRP GUI uses Tkinter for display
                        self.emulator = WrappedEmulator(visible=False)
                        log_info("Emulator created successfully")
                    except Exception as e:
                        log_error(f"Failed to create emulator: {e}")
                        self.after(0, self._connection_failed, target, f"Failed to create emulator: {e}")
                        return
                
                # Attempt connection with retry
                import time
                max_retries = 3
                retry_delay = 2
                
                for attempt in range(max_retries):
                    try:
                        log_info(f"Attempting to connect to {target}... (attempt {attempt + 1}/{max_retries})")
                        self.emulator.connect(target)
                        log_info("Connection successful")
                        break
                    except Exception as e:
                        if attempt < max_retries - 1:
                            log_info(f"Connection attempt {attempt + 1} failed, retrying in {retry_delay} seconds...")
                            time.sleep(retry_delay)
                        else:
                            log_error(f"Connection failed after {max_retries} attempts: {e}")
                            self.after(0, self._connection_failed, target, f"Connection failed: {e}")
                            return
                
                # Update GUI from main thread
                self.after(0, self._connection_complete, target)
            except Exception as e:
                from ..utils.logger import log_error
                log_error(f"Unexpected error in connection thread: {e}")
                self.after(0, self._connection_failed, target, f"Unexpected error: {e}")
        
        # Update status immediately
        self.status_var.set(f"Connecting to {target}...")
        self.update()
        
        # Connect in background thread
        thread = threading.Thread(target=do_connect, daemon=True)
        thread.start()
    
    def _connection_complete(self, target):
        """Called when connection succeeds"""
        try:
            if self.emulator and self.emulator.is_connected():
                self.connected = True
                self.status_var.set(f"Connected to {target}")
                self.refresh_screen()
                
                # Update info panel with appropriate quick start guide
                # DVMVS mode or port 3270 → DVMVS guide
                # Otherwise (port 23) → MVS guide (already shown at init)
                if self.dvmvs_mode or ':3270' in target:
                    self._show_dvmvs_quick_start()
                else:
                    self._show_mvs_quick_start()
            else:
                self.status_var.set("Connection failed")
                messagebox.showerror("Connection Error", f"Could not connect to {target}\n\nCheck that:\n- MVS is running\n- Port 23 is accessible\n- Target address is correct")
        except Exception as e:
            self.status_var.set("Connection error")
            messagebox.showerror("Connection Error", f"Error checking connection: {e}")
    
    def _connection_failed(self, target, error):
        """Called when connection fails"""
        self.status_var.set("Connection error")
        messagebox.showerror("Connection Error", error)
    
    def disconnect(self):
        """Disconnect from mainframe"""
        if self.emulator and self.connected:
            try:
                self.emulator.terminate()
                self.connected = False
                self.status_var.set("Disconnected")
                self.terminal.delete('1.0', tk.END)
            except Exception as e:
                messagebox.showerror("Disconnect Error", str(e))
    
    def refresh_screen(self):
        """Refresh the terminal display"""
        if not self.connected or not self.emulator:
            return
        
        try:
            buffer_data = self.emulator.exec_command_with_timeout(b'ReadBuffer(Ascii)', timeout=5).data
            buffer_data = self._decode_buffer(buffer_data)
            self.current_screen = Screen(buffer_data)
            self.display_screen(self.current_screen)
            self.update_field_info(self.current_screen)
        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")
    
    def display_screen(self, screen):
        """Display screen with color coding"""
        self.terminal.delete('1.0', tk.END)
        
        row_num = 0
        for line in screen.stringbuffer:
            self.terminal.insert(tk.END, line + '\n')
            row_num += 1
        
        # Highlight fields
        for field in screen.fields:
            start_idx = f"{field.row + 1}.{field.col}"
            end_idx = f"{field.row + 1}.{field.col + len(field.contents)}"
            
            if field.hidden:
                self.terminal.tag_add('hidden', start_idx, end_idx)
            elif field.modify:
                self.terminal.tag_add('modified', start_idx, end_idx)
            elif not field.protected:
                self.terminal.tag_add('input', start_idx, end_idx)
            else:
                self.terminal.tag_add('protected', start_idx, end_idx)
    
    def update_field_info(self, screen):
        """Update field information panel"""
        self.info_text.delete('1.0', tk.END)
        
        self.info_text.insert(tk.END, "=== Field Summary ===\n\n")
        self.info_text.insert(tk.END, f"Total Fields: {len(screen.fields)}\n")
        self.info_text.insert(tk.END, f"Input Fields: {len(screen.input_fields)}\n")
        self.info_text.insert(tk.END, f"Protected: {len(screen.protected_fields)}\n")
        self.info_text.insert(tk.END, f"Hidden: {len(screen.hidden_fields)}\n")
        self.info_text.insert(tk.END, f"Modified: {len(screen.modified_fields)}\n\n")
        
        if screen.hidden_fields:
            self.info_text.insert(tk.END, "=== Hidden Fields ===\n")
            for field in screen.hidden_fields:
                content = field.contents.strip()
                if content:
                    self.info_text.insert(tk.END, f"[{field.row},{field.col}]: {content}\n")
    
    def handle_keypress(self, event):
        """Handle keyboard input"""
        if not self.connected:
            return "break"
        
        char = event.char
        if char and ord(char) >= 32 and ord(char) < 127:
            try:
                self.emulator.safe_send(char)
                self.refresh_screen()
            except Exception as e:
                self.status_var.set(f"Error: {str(e)}")
        
        return "break"
    
    def send_enter(self):
        """Send Enter key"""
        if not self.connected:
            return
        
        try:
            # Record transaction
            request = self.current_screen
            self.emulator.send_enter()
            self.emulator.exec_command_with_timeout(b'Wait(1,3270Mode)', timeout=5)

            buffer_data = self.emulator.exec_command_with_timeout(b'ReadBuffer(Ascii)', timeout=5).data
            buffer_data = self._decode_buffer(buffer_data)
            response = Screen(buffer_data)
            
            hostinfo = self.emulator.get_hostinfo()
            host = f"{hostinfo[1]}:{hostinfo[2]}"
            
            trans = Transaction(request, response, request.modified_fields, 'enter', host)
            self.history.append(trans)
            
            self.current_screen = response
            self.display_screen(response)
            self.update_field_info(response)
            
            self.status_var.set(f"Transaction recorded ({len(self.history)} total)")
        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")
    
    def send_pf_key(self, num):
        """Send PF key"""
        if not self.connected:
            return
        
        try:
            request = self.current_screen
            self.emulator.exec_command_with_timeout(f'PF({num})'.encode(), timeout=5)
            self.emulator.exec_command_with_timeout(b'Wait(1,3270Mode)', timeout=5)

            buffer_data = self.emulator.exec_command_with_timeout(b'ReadBuffer(Ascii)', timeout=5).data
            buffer_data = self._decode_buffer(buffer_data)
            response = Screen(buffer_data)
            
            hostinfo = self.emulator.get_hostinfo()
            host = f"{hostinfo[1]}:{hostinfo[2]}"
            
            trans = Transaction(request, response, request.modified_fields, f'PF({num})', host)
            self.history.append(trans)
            
            self.current_screen = response
            self.display_screen(response)
            self.update_field_info(response)
            
            self.status_var.set(f"PF{num} sent")
        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")
    
    def send_pa_key(self, num):
        """Send PA key"""
        if not self.connected:
            return
        
        try:
            self.emulator.exec_command_with_timeout(f'PA({num})'.encode(), timeout=5)
            self.refresh_screen()
            self.status_var.set(f"PA{num} sent")
        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")

    def clear_screen(self):
        """Clear the screen"""
        if self.connected:
            try:
                self.emulator.exec_command_with_timeout(b'Clear()', timeout=5)
                self.refresh_screen()
            except Exception as e:
                self.status_var.set(f"Error: {str(e)}")

    def reset_screen(self):
        """Reset the connection"""
        if self.connected:
            try:
                self.emulator.exec_command_with_timeout(b'Reset()', timeout=5)
                self.refresh_screen()
            except Exception as e:
                self.status_var.set(f"Error: {str(e)}")
    
    def toggle_hidden_fields(self):
        """Toggle display of hidden fields"""
        messagebox.showinfo("Info", "Hidden fields are always shown in BIRP")
    
    def toggle_field_markers(self):
        """Toggle field markers"""
        messagebox.showinfo("Info", "Field markers feature coming soon")
    
    def show_history_browser(self):
        """Show history browser window"""
        from .history_browser import HistoryBrowser
        browser = HistoryBrowser(self, self.history)
        browser.mainloop()
    
    def show_search_dialog(self):
        """Show search dialog"""
        messagebox.showinfo("Info", "Search feature coming soon")
    
    def open_python_console(self):
        """Open Python console"""
        try:
            from IPython import embed
            embed(user_ns={'history': self.history, 'emulator': self.emulator, 
                          'screen': self.current_screen})
        except ImportError:
            messagebox.showerror("Error", "IPython not installed")
    
    def save_history(self):
        """Save history to file"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".pickle",
            filetypes=[("Pickle files", "*.pickle"), ("All files", "*.*")]
        )
        if filename:
            try:
                from ..io.file_ops import save_history
                if save_history(self.history, filename):
                    messagebox.showinfo("Success", f"History saved to {filename}")
            except Exception as e:
                messagebox.showerror("Error", str(e))
    
    def load_history(self):
        """Load history from file"""
        filename = filedialog.askopenfilename(
            filetypes=[("Pickle files", "*.pickle"), ("All files", "*.*")]
        )
        if filename:
            try:
                from ..io.file_ops import load_history
                self.history = load_history(filename)
                messagebox.showinfo("Success", f"History loaded from {filename}")
            except Exception as e:
                messagebox.showerror("Error", str(e))
    
    def export_history(self):
        """Export history"""
        filename = filedialog.asksaveasfilename(
            filetypes=[
                ("JSON files", "*.json"),
                ("CSV files", "*.csv"),
                ("HTML files", "*.html"),
                ("XML files", "*.xml"),
                ("All files", "*.*")
            ]
        )
        if filename:
            try:
                from ..io.exporters import auto_export
                if auto_export(self.history, filename):
                    messagebox.showinfo("Success", f"History exported to {filename}")
            except Exception as e:
                messagebox.showerror("Error", str(e))
    
    def show_shortcuts(self):
        """Show keyboard shortcuts"""
        shortcuts = """
Keyboard Shortcuts:

F1-F12          PF1-PF12 keys
Enter           Send Enter
Escape          PA1
Ctrl-C          Clear screen
Ctrl-R          Refresh screen
Ctrl-H          Show this help

Navigation:
Arrow keys      Move cursor
Tab             Next field
Backspace       Delete character
"""
        messagebox.showinfo("Keyboard Shortcuts", shortcuts)
    
    def _show_mvs_quick_start(self):
        """Display MVS quick start guide in info panel"""
        mvs_banner = """
═══════════════════════════════
  MVS TK4- QUICK START
═══════════════════════════════

SYSTEM INFO:
  MVS 3.8j with TK4- updates
  Hercules Emulator
  Port: 23 (telnet)

CREDITS:
  TK4- by Jürgen Winkelmann
  MVS 3.8j by IBM (Public Domain)
  Hercules by Roger Bowler & team

DEFAULT CREDENTIALS:
  Username: HERC01
  Password: CUL8TR

COMMON USERS:
  HERC02 / CUL8TR
  HERC03 / CUL8TR
  HERC04 / CUL8TR

GETTING STARTED:
1. Wait for connection
2. Press ENTER at logon screen
3. Enter username: HERC01
4. Enter password: CUL8TR
5. Press ENTER to TSO

USEFUL TSO COMMANDS:
  LOGON    - Start TSO session
  LOGOFF   - End session
  HELP     - Show help
  LISTDS   - List datasets
  SUBMIT   - Submit JCL job
  ISPF     - ISPF panels
  
PF KEYS:
  F1  - Help
  F3  - Exit/Return
  F7  - Scroll up
  F8  - Scroll down
  F12 - Cancel

DOCUMENTATION:
  http://wotho.ethz.ch/tk4-/

═══════════════════════════════
"""
        self.info_text.config(state='normal')
        self.info_text.delete('1.0', tk.END)
        self.info_text.insert('1.0', mvs_banner)
        self.info_text.config(state='disabled')
    
    def _show_dvmvs_quick_start(self):
        """Display DVMVS quick start guide in info panel"""
        dvmvs_banner = """
═══════════════════════════════
  DVMVS QUICK START
═══════════════════════════════

SYSTEM INFO:
  DVMVS - Damn Vulnerable MVS
  Port: 3270 (TN3270)

ABOUT:
  Deliberately insecure mainframe
  application for security training.
  23+ intentional vulnerabilities!

MVS LOGIN:
  HERC01 / CUL8TR

THEN RUN:
  TSO DVBANK

DVBANK USERS:
  USER1 / PASSWORD1 ($5000)
  ADMIN / ADMIN123 (Admin)
  TESTUSER / TEST123 ($1000)

GETTING STARTED:
1. Login to MVS: HERC01 / CUL8TR
2. Run: TSO DVBANK
3. Login to DVBANK
4. Explore vulnerabilities!

QUICK EXPLOITS:
  Option 5 - Admin Panel (no auth!)
  Option 6 - Command Injection
  Option 3 - View ALL transactions
  Debug Mode - Execute TSO commands

VULNERABILITIES:
  ✗ Authentication Bypass
  ✗ Authorization Flaws
  ✗ Command Injection
  ✗ Information Disclosure
  ✗ Plaintext Passwords
  ✗ Race Conditions
  ✗ Missing Input Validation
  ... and 16 more!

PF KEYS:
  F1  - Full vulnerability guide
  F3  - Exit/Return
  F7  - Scroll up
  F8  - Scroll down

DOCUMENTATION:
  dvmvs/README.md
  dvmvs/docs/VULNERABILITIES.md
  
Press F1 for complete exploit guide!

═══════════════════════════════
"""
        self.info_text.config(state='normal')
        self.info_text.delete('1.0', tk.END)
        self.info_text.insert('1.0', dvmvs_banner)
        self.info_text.config(state='disabled')
    
    def show_dvmvs_help(self):
        # Show DVMVS banner if in DVMVS mode
        if self.dvmvs_mode or hasattr(self, '_is_dvca_connection'):
            self._show_dvmvs_quick_start()
        else:
            dvmvs_help = """
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║              DVMVS - Damn Vulnerable MVS                       ║
║              Security Testing Guide                           ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝

QUICK START:
  Run: TSO DVBANK
  Login with: USER1 / PASSWORD1

23+ INTENTIONAL VULNERABILITIES:

AUTHENTICATION & SESSION:
  [X] No session management or timeouts
  [X] Command injection in login fields
  [X] Plaintext password storage
  [X] Default admin credentials (ADMIN/ADMIN123)
  [X] Verbose error messages reveal system info
  [X] Username enumeration possible

AUTHORIZATION:
  [X] Missing authorization checks
  [X] Admin panel accessible to all users (Option 5)
  [X] Privilege escalation via modify_balance
  [X] No verification of resource ownership

BUSINESS LOGIC:
  [X] Race conditions in fund transfers
  [X] No input validation (negative amounts)
  [X] TOCTOU vulnerabilities
  [X] No transaction locking

INFORMATION DISCLOSURE:
  [X] View all users' transaction history
  [X] Expose all account data (passwords + balances)
  [X] System information disclosure
  [X] Password recovery without verification

COMMAND INJECTION:
  [X] Debug mode executes arbitrary TSO commands (Option 6)
  [X] No command validation or whitelist

PASSWORD SECURITY:
  [X] No length requirements
  [X] No complexity requirements
  [X] Passwords displayed in clear text

EXPLOITATION EXAMPLES:

1. ADMIN BYPASS:
   - Login with any valid user
   - Select Option 5 (Admin Panel)
   - Access granted without admin check

2. COMMAND INJECTION:
   - Login to DVBANK
   - Select Option 6 (Debug Mode)
   - Enter: LISTDS SYS1.PARMLIB
   - Arbitrary TSO command executed

3. RACE CONDITION:
   - Submit multiple transfer requests simultaneously
   - Overdraw account beyond balance

4. INFORMATION DISCLOSURE:
   - Select Option 3 (View History)
   - See ALL users' transactions

5. PRIVILEGE ESCALATION:
   - Access Admin Panel (Option 5)
   - Select Option 2 (Modify Balance)
   - Change any user's balance

TESTING CHECKLIST:
  [ ] Test authentication bypass
  [ ] Exploit command injection
  [ ] Trigger race conditions
  [ ] Escalate privileges
  [ ] Enumerate usernames
  [ ] Extract sensitive data
  [ ] Test weak password policy
  [ ] Exploit TOCTOU flaws

REMEMBER:
  * This is for TRAINING ONLY
  * Never deploy on production
  * Document all findings
  * Practice responsible disclosure

FULL DOCUMENTATION:
  dvmvs/docs/VULNERABILITIES.md
  dvmvs/docs/INSTALL.md
  dvmvs/README.md

Press F1 or Help -> DVMVS Vulnerabilities to view this again
"""
        
        # Create multi-page help dialog
        self._show_multipage_help(dvmvs_help, "DVMVS Vulnerabilities & Testing Guide", is_dvmvs=True)
    
    def _show_multipage_help(self, initial_content, title, is_dvmvs=False):
        """Show multi-page help dialog with F3 navigation"""
        # Define help pages
        if is_dvmvs:
            help_pages = [
                ("DVMVS Vulnerabilities", initial_content),
                ("TSO Commands", self._get_tso_help()),
                ("BIRP Features", self._get_birp_help()),
                ("Keyboard Shortcuts", self._get_keyboard_help()),
                ("Security Testing", self._get_security_help())
            ]
        else:
            help_pages = [
                ("MVS Quick Start", initial_content),
                ("TSO Commands", self._get_tso_help()),
                ("BIRP Features", self._get_birp_help()),
                ("Keyboard Shortcuts", self._get_keyboard_help()),
                ("z/OS Subsystems", self._get_zos_help())
            ]
        
        current_page = [0]  # Use list for mutable closure
        
        dialog = tk.Toplevel(self)
        dialog.geometry("900x700")
        dialog.transient(self)
        
        # Page indicator
        page_label = ttk.Label(dialog, text="", font=('Courier', 10, 'bold'))
        page_label.pack(pady=5)
        
        # Text area
        text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, font=('Courier', 10))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        def show_page(page_num):
            page_title, page_content = help_pages[page_num]
            dialog.title(f"{title} - {page_title}")
            page_label.config(text=f"Page {page_num + 1}/{len(help_pages)}: {page_title} (F3=Next, F1=Prev, ESC=Close)")
            text.config(state='normal')
            text.delete('1.0', tk.END)
            text.insert('1.0', page_content)
            text.config(state='disabled')
        
        def next_page(event=None):
            current_page[0] = (current_page[0] + 1) % len(help_pages)
            show_page(current_page[0])
        
        def prev_page(event=None):
            current_page[0] = (current_page[0] - 1) % len(help_pages)
            show_page(current_page[0])
        
        # Bind keys
        dialog.bind('<F3>', next_page)
        dialog.bind('<F1>', prev_page)
        dialog.bind('<Escape>', lambda e: dialog.destroy())
        
        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="← Previous (F1)", command=prev_page).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Next (F3) →", command=next_page).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Close (ESC)", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        # Show first page
        show_page(0)
    
    def _get_tso_help(self):
        return """╔════════════════════════════════════════════════════════════════╗
║                    TSO COMMANDS REFERENCE                      ║
╚════════════════════════════════════════════════════════════════╝

BASIC COMMANDS:
  LOGON        - Start TSO session
  LOGOFF       - End TSO session
  HELP         - Display help information
  TIME         - Display current time
  STATUS       - Show session status

DATASET COMMANDS:
  LISTDS       - List datasets
  LISTCAT      - List catalog entries
  ALLOCATE     - Allocate new dataset
  DELETE       - Delete dataset
  RENAME       - Rename dataset

FILE OPERATIONS:
  EDIT         - Edit dataset (ISPF)
  BROWSE       - Browse dataset
  VIEW         - View dataset (read-only)
  COPY         - Copy dataset
  PRINT        - Print dataset

JOB CONTROL:
  SUBMIT       - Submit JCL job
  OUTPUT       - View job output
  CANCEL       - Cancel running job
  STATUS       - Check job status

SYSTEM COMMANDS:
  SEND         - Send message to user
  LISTBC       - List broadcast messages
  ACCOUNT      - Display account info
  OPERATOR     - Send operator command

ISPF COMMANDS:
  ISPF         - Start ISPF
  PDF          - Start Program Development Facility
  SDSF         - System Display and Search Facility

EXAMPLES:
  LISTDS 'HERC01.*'              - List all datasets
  SUBMIT 'HERC01.JCL(MYJOB)'     - Submit JCL
  EDIT 'HERC01.SOURCE.COBOL'     - Edit COBOL source
  SEND 'Hello' USER(HERC02)      - Send message

TIPS:
  - Use quotes for dataset names
  - TSO commands are case-insensitive
  - Press F1 in ISPF for context help
  - Use HELP <command> for command help
"""
    
    def _get_birp_help(self):
        return """╔════════════════════════════════════════════════════════════════╗
║                    BIRP FEATURES & TOOLS                       ║
╚════════════════════════════════════════════════════════════════╝

CORE FEATURES:
  • Transaction Recording  - All screens saved automatically
  • Hidden Field Detection - Reveals protected/hidden data
  • Session Replay        - Re-execute recorded transactions
  • Field Analysis        - Analyze input fields and protection
  • History Browser       - Search and review all screens

SECURITY SCANNING:
  • Automated Scanner     - Detect common vulnerabilities
  • Application Crawler   - Map entire application structure
  • Field Fuzzer          - Test input validation
  • Credential Harvester  - Detect exposed credentials
  • SQL Injection Tests   - Test for injection flaws

EXPORT FORMATS:
  • JSON                  - Structured data export
  • CSV                   - Spreadsheet-compatible
  • HTML                  - Web-viewable reports
  • XML                   - Standard data format
  • Pickle                - Python object serialization

z/OS SUBSYSTEM SUPPORT:
  • JES (Job Entry)       - Job submission and output
  • RACF (Security)       - User and resource profiles
  • CICS (Transactions)   - Transaction processing
  • TSO (Time Sharing)    - Interactive commands
  • ISPF (Development)    - Panel and dataset operations

MAINFRAMED TOOLS INTEGRATION:
  • hack3270              - TN3270 data stream manipulation
  • NMAP Scripts          - Enumeration and brute force
  • SETn3270              - TN3270 MitM proxy
  • DVCA Testing          - Vulnerable app exploitation

MENU OPTIONS:
  File → Save History     - Save session to file
  File → Load History     - Load previous session
  File → Export           - Export in various formats
  Tools → Security Scan   - Run automated scanner
  Tools → Python Console  - Drop to IPython shell
  Help → Shortcuts        - View keyboard shortcuts

COMMAND LINE:
  ./birpv2.py -t host:port     - Connect to target
  ./birpv2.py -c -t host:port  - Console mode
  ./birpv2.py -l file.pickle   - Load saved session
  ./birpv2.py --dvmvs          - DVMVS mode
"""
    
    def _get_keyboard_help(self):
        return """╔════════════════════════════════════════════════════════════════╗
║                    KEYBOARD SHORTCUTS                          ║
╚════════════════════════════════════════════════════════════════╝

PF KEYS (FUNCTION KEYS):
  F1           - Help / Previous help page
  F2           - (Application specific)
  F3           - Exit/Return / Next help page
  F4           - (Application specific)
  F5           - Refresh
  F6           - (Application specific)
  F7           - Scroll up / Page up
  F8           - Scroll down / Page down
  F9           - (Application specific)
  F10          - (Application specific)
  F11          - (Application specific)
  F12          - Cancel / Retrieve

ATTENTION KEYS:
  Enter        - Send / Submit
  Escape       - PA1 (Program Attention)
  Ctrl-C       - Clear screen
  Ctrl-R       - Refresh display

NAVIGATION:
  Arrow Keys   - Move cursor
  Tab          - Next field
  Shift-Tab    - Previous field
  Home         - Start of field
  End          - End of field
  Page Up      - Scroll up
  Page Down    - Scroll down

EDITING:
  Backspace    - Delete character left
  Delete       - Delete character right
  Ctrl-A       - Select all
  Ctrl-X       - Cut
  Ctrl-C       - Copy (when text selected)
  Ctrl-V       - Paste

BIRP SHORTCUTS:
  Ctrl-H       - Show help
  Ctrl-S       - Save history
  Ctrl-O       - Open/Load history
  Ctrl-E       - Export history
  Ctrl-P       - Python console
  Ctrl-B       - Browse history

3270 TERMINAL BEHAVIOR:
  • Fields may be protected (read-only)
  • Some fields are hidden (password entry)
  • Tab moves between input fields only
  • Enter sends entire screen to host
  • Modified fields are highlighted

TIPS:
  • Use Tab to navigate between fields
  • F3 typically exits current screen
  • F7/F8 for scrolling in lists
  • F12 often cancels current operation
  • Escape (PA1) interrupts running programs
"""
    
    def _get_security_help(self):
        return """╔════════════════════════════════════════════════════════════════╗
║                    SECURITY TESTING GUIDE                      ║
╚════════════════════════════════════════════════════════════════╝

RECONNAISSANCE:
  1. Map Application      - Use crawler to discover all screens
  2. Identify Subsystems  - Detect JES, RACF, CICS, TSO
  3. Enumerate Users      - Find valid usernames
  4. Document Workflows   - Record transaction flows

VULNERABILITY TESTING:
  • Authentication Bypass - Test default credentials
  • Authorization Flaws   - Access unauthorized functions
  • Input Validation      - Fuzz input fields
  • Information Disclosure- Check hidden fields
  • Session Management    - Test session handling
  • Command Injection     - Test for OS command injection

COMMON MAINFRAME VULNERABILITIES:
  ✗ Default Credentials   - IBMUSER, ADMIN, etc.
  ✗ Weak Passwords        - Short, simple passwords
  ✗ Missing Authorization - No access controls
  ✗ Information Leakage   - Error messages, hidden fields
  ✗ Insecure Defaults     - Unpatched systems
  ✗ Privilege Escalation  - Unauthorized access elevation

TESTING WORKFLOW:
  1. SCAN    - Run automated security scanner
  2. MAP     - Crawl and document application
  3. REPLAY  - Test transaction replay
  4. FUZZ    - Automated input testing
  5. REPORT  - Generate findings report

BIRP SECURITY FEATURES:
  • Automated Scanner     - Detect common issues
  • Hidden Field Viewer   - Reveal protected data
  • Session Replay        - Modify and replay transactions
  • Field Fuzzer          - Test input validation
  • Credential Detector   - Find exposed passwords

DVMVS PRACTICE TARGETS:
  • 23+ Intentional Vulnerabilities
  • Authentication Bypass
  • Command Injection
  • Authorization Flaws
  • Information Disclosure
  • Race Conditions

REPORTING:
  • Document all findings
  • Include screenshots
  • Provide reproduction steps
  • Rate severity (Critical/High/Medium/Low)
  • Suggest remediation

ETHICAL TESTING:
  ⚠ Only test systems you have permission to test
  ⚠ Follow rules of engagement
  ⚠ Don't cause damage or disruption
  ⚠ Report findings responsibly
  ⚠ Respect data privacy
"""
    
    def _get_zos_help(self):
        return """╔════════════════════════════════════════════════════════════════╗
║                    z/OS SUBSYSTEMS GUIDE                       ║
╚════════════════════════════════════════════════════════════════╝

JES (JOB ENTRY SUBSYSTEM):
  Purpose: Job scheduling and management
  
  Commands:
    $D A              - Display active jobs
    $D Q              - Display job queue
    $P JOBxxxx        - Purge job
    $C JOBxxxx        - Cancel job
  
  BIRP Detection:
    • Looks for JES2/JES3 messages
    • Parses job output
    • Tracks job submissions

RACF (RESOURCE ACCESS CONTROL FACILITY):
  Purpose: Security and access control
  
  Commands:
    LISTUSER          - List user profiles
    LISTGRP           - List groups
    LISTDSD           - List datasets
    RLIST             - List resources
  
  BIRP Detection:
    • Identifies RACF commands
    • Extracts user/group info
    • Detects access violations

CICS (CUSTOMER INFORMATION CONTROL SYSTEM):
  Purpose: Transaction processing
  
  Transactions:
    CESN              - Sign on
    CESF LOGOFF       - Sign off
    CEMT              - Master terminal
    CEDA              - Resource definition
  
  BIRP Detection:
    • Recognizes CICS screens
    • Tracks transactions
    • Maps transaction IDs

TSO (TIME SHARING OPTION):
  Purpose: Interactive user interface
  
  Features:
    • Command line interface
    • Dataset management
    • Job submission
    • ISPF integration
  
  BIRP Detection:
    • Identifies TSO prompts
    • Parses command output
    • Tracks dataset operations

ISPF (INTERACTIVE SYSTEM PRODUCTIVITY FACILITY):
  Purpose: Development environment
  
  Panels:
    0 - Settings
    1 - Browse
    2 - Edit
    3 - Utilities
    4 - Foreground
    5 - Batch
    6 - Command
  
  BIRP Detection:
    • Recognizes ISPF panels
    • Tracks panel navigation
    • Extracts panel data

SUBSYSTEM IDENTIFICATION:
  BIRP automatically detects subsystems by:
  • Screen content analysis
  • Command patterns
  • Message formats
  • Panel structures

SECURITY IMPLICATIONS:
  • JES - Job manipulation, privilege escalation
  • RACF - Access control bypass, user enumeration
  • CICS - Transaction abuse, data access
  • TSO - Command injection, file access
  • ISPF - Source code access, configuration
"""
    
    def show_about(self):
        """Show about dialog"""
        about_text = """
Big Iron Recon & Pwnage (BIRP) v2.0
GUI TN3270 Terminal

Version: 2.0
Author: @w00tock (based on @singe's original)

A tool for security assessment of mainframe
applications served over TN3270.

For z/OS, System/390, and compatible systems.
"""
        messagebox.showinfo("About BIRP v2", about_text)


def launch_gui(target='', history=None, dvmvs_mode=False):
    """Launch the GUI terminal
    
    Args:
        target: Optional target to connect to (host:port)
        history: Optional History object with saved session data
        dvmvs_mode: If True, display DVMVS welcome banner
    """
    root = tk.Tk()
    app = TN3270Terminal(root, target=target, history=history, dvmvs_mode=dvmvs_mode)
    root.mainloop()


if __name__ == '__main__':
    launch_gui()
