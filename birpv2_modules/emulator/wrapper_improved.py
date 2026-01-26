#!/usr/bin/env python
"""
Improved emulator wrapper with timeout protection and better error handling
"""

from py3270 import Emulator, CommandError, FieldTruncateError, TerminatedError, WaitError, KeyboardStateError, X3270App, S3270App
import platform
import signal
import threading
from time import sleep
from sys import exit
from os import path

class TimeoutError(Exception):
    """Raised when a command times out"""
    pass

def timeout_handler(signum, frame):
    """Signal handler for timeouts"""
    raise TimeoutError("Command timed out")

class EmulatorImproved(Emulator):
    """Improved emulator with timeout protection"""
    
    def __init__(self, visible=True, delay=0, window_title="BIRP v2 - TN3270 Terminal", command_timeout=10):
        """
        Initialize emulator with timeout protection
        
        Args:
            visible: Use GUI (x3270) if True, console (s3270) if False
            delay: Delay between commands
            window_title: Window title for GUI mode
            command_timeout: Timeout in seconds for commands (0 = no timeout)
        """
        try:
            Emulator.__init__(self, visible)
            self.delay = delay
            self.window_title = window_title
            self.command_timeout = command_timeout
            self.is_terminated = False
            
            if visible and window_title:
                try:
                    self.set_window_title(window_title)
                except:
                    pass  # Ignore if title setting fails
                    
        except OSError as e:
            if visible:
                print(f"Can't run x3270: {e}")
                print("\nGUI mode not available. Use console mode instead:")
                print("  em = WrappedEmulator(visible=False)")
            else:
                print(f"Can't run s3270: {e}")
                print("\nInstall x3270 suite:")
                print("  macOS: brew install x3270")
                print("  Linux: sudo apt-get install x3270")
            raise
    
    def exec_command_with_timeout(self, command, timeout=None):
        """
        Execute command with timeout protection
        
        Args:
            command: Command to execute
            timeout: Timeout in seconds (uses default if None)
            
        Returns:
            Command result
            
        Raises:
            TimeoutError: If command times out
        """
        if timeout is None:
            timeout = self.command_timeout
        
        if timeout <= 0:
            # No timeout, use normal exec_command
            return self.exec_command(command)
        
        # Use threading for timeout
        result = [None]
        exception = [None]
        
        def run_command():
            try:
                result[0] = self.exec_command(command)
            except Exception as e:
                exception[0] = e
        
        thread = threading.Thread(target=run_command)
        thread.daemon = True
        thread.start()
        thread.join(timeout)
        
        if thread.is_alive():
            # Command timed out
            raise TimeoutError(f"Command timed out after {timeout}s: {command}")
        
        if exception[0]:
            raise exception[0]
        
        return result[0]
    
    def safe_exec_command(self, command, timeout=None, default=None):
        """
        Safely execute command with timeout and error handling
        
        Args:
            command: Command to execute
            timeout: Timeout in seconds
            default: Default value to return on error
            
        Returns:
            Command result or default value on error
        """
        try:
            return self.exec_command_with_timeout(command, timeout)
        except TimeoutError as e:
            print(f"Warning: {e}")
            return default
        except Exception as e:
            print(f"Warning: Command failed: {e}")
            return default
    
    def set_window_title(self, title):
        """Set window title (safe version)"""
        try:
            self.safe_exec_command(f'Title("{title}")'.encode(), timeout=2)
        except:
            pass
    
    def send_enter(self):
        """Send Enter with delay"""
        try:
            self.exec_command_with_timeout(b'Enter()', timeout=5)
            if self.delay > 0:
                sleep(self.delay)
        except TimeoutError:
            print("Warning: Enter command timed out")
    
    def screen_get(self, timeout=5):
        """Get screen content with timeout"""
        try:
            response = self.exec_command_with_timeout(b'Ascii()', timeout=timeout)
            return response.data
        except TimeoutError:
            print("Warning: Screen read timed out")
            return []
    
    def safe_send_string(self, text, timeout=5):
        """Send string with timeout protection"""
        try:
            self.exec_command_with_timeout(f'String("{text}")'.encode(), timeout=timeout)
            return True
        except TimeoutError:
            print(f"Warning: String send timed out: {text}")
            return False
    
    def safe_send_pf(self, key_num, timeout=5):
        """Send PF key with timeout protection"""
        try:
            self.exec_command_with_timeout(f'PF({key_num})'.encode(), timeout=timeout)
            return True
        except TimeoutError:
            print(f"Warning: PF{key_num} timed out")
            return False
    
    def get_pos(self, timeout=2):
        """Get cursor position with timeout"""
        try:
            results = self.exec_command_with_timeout(b'Query(Cursor)', timeout=timeout)
            result = results.data[0]
            if isinstance(result, bytes):
                result = result.decode('utf-8')
            row = int(result.split(' ')[0])
            col = int(result.split(' ')[1])
            return (row, col)
        except (TimeoutError, Exception) as e:
            print(f"Warning: Could not get cursor position: {e}")
            return (0, 0)
    
    def is_connected(self, timeout=2):
        """Check if connected to host"""
        try:
            result = self.exec_command_with_timeout(b'Query(ConnectionState)', timeout=timeout)
            if result and result.data:
                state = result.data[0]
                if isinstance(state, bytes):
                    state = state.decode('utf-8')
                return 'connected' in state.lower()
        except:
            pass
        return False

# Platform-specific setup
if platform.system() == 'Darwin':
    class WrappedEmulator(EmulatorImproved):
        import os
        home = os.path.expanduser('~')
        
        # Find x3270
        if path.isfile(f'{home}/.local/bin/x3270'):
            X3270App.executable = f'{home}/.local/bin/x3270'
        elif path.isfile('/opt/homebrew/bin/x3270'):
            X3270App.executable = '/opt/homebrew/bin/x3270'
        elif path.isfile('/usr/local/bin/x3270'):
            X3270App.executable = '/usr/local/bin/x3270'
        else:
            X3270App.executable = 'x3270'
        
        # Find s3270
        if path.isfile('/opt/homebrew/bin/s3270'):
            S3270App.executable = '/opt/homebrew/bin/s3270'
        elif path.isfile('/usr/local/bin/s3270'):
            S3270App.executable = '/usr/local/bin/s3270'
        else:
            S3270App.executable = 's3270'
        
        def __init__(self, visible=False, delay=0, window_title="BIRP v2 - TN3270 Terminal", command_timeout=10):
            """
            Initialize with console mode by default (visible=False)
            to avoid GUI display issues
            """
            super().__init__(visible, delay, window_title, command_timeout)

elif platform.system() == 'Linux':
    class WrappedEmulator(EmulatorImproved):
        if path.isfile('/usr/bin/x3270'):
            X3270App.executable = '/usr/bin/x3270'
        else:
            X3270App.executable = 'x3270'
        
        if path.isfile('/usr/bin/s3270'):
            S3270App.executable = '/usr/bin/s3270'
        else:
            S3270App.executable = 's3270'
        
        def __init__(self, visible=False, delay=0, window_title="BIRP v2 - TN3270 Terminal", command_timeout=10):
            super().__init__(visible, delay, window_title, command_timeout)

elif platform.system() == 'Windows':
    class WrappedEmulator(EmulatorImproved):
        X3270App.executable = 'wc3270.exe'
        
        def __init__(self, visible=False, delay=0, window_title="BIRP v2 - TN3270 Terminal", command_timeout=10):
            super().__init__(visible, delay, window_title, command_timeout)
else:
    print('Your Platform:', platform.system(), 'is not supported at this time.')
    exit(1)
