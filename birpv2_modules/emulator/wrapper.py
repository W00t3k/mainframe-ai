#!/usr/bin/env python
"""
Emulator wrapper with timeout protection and error handling
"""

from py3270 import Emulator, CommandError, FieldTruncateError, TerminatedError, WaitError, KeyboardStateError, X3270App, S3270App
import platform
import threading
from time import sleep
from sys import exit
from os import path

class TimeoutError(Exception):
	"""Raised when a command times out"""
	pass

# Override some behaviour of py3270 library
class EmulatorIntermediate(Emulator):
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
			# Ensure is_terminated attribute exists for proper cleanup
			if not hasattr(self, 'is_terminated'):
				self.is_terminated = False

			# Set window title if visible
			if visible and window_title:
				try:
					self.set_window_title(window_title)
				except:
					pass  # Ignore if title setting fails
		except OSError as e:
			if visible:
				print(f"Can't run x3270: {e}")
				print("\nInstall x3270:")
				print("  macOS: brew install x3270")
				print("  Linux: sudo apt-get install x3270")
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
		"""Set the x3270 window title"""
		try:
			self.safe_exec_command(f'Title("{title}")'.encode(), timeout=2)
		except:
			pass  # Ignore if command not supported
	
	def take_screenshot(self, filename=None):
		"""Take a screenshot of the current screen
		
		Args:
			filename: Output filename. If None, generates timestamp-based name.
		
		Returns:
			str: Path to saved screenshot file
		"""
		import datetime
		import os
		
		if filename is None:
			timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
			filename = f"birp_screenshot_{timestamp}.png"
		
		# Ensure .png extension
		if not filename.endswith('.png'):
			filename += '.png'
		
		try:
			# Use x3270's PrintWindow action to save screenshot
			self.exec_command(f'PrintWindow(file,{filename})')
			
			if os.path.exists(filename):
				return os.path.abspath(filename)
			else:
				# Fallback: use Snap action
				self.exec_command(f'Snap(Save,{filename})')
				if os.path.exists(filename):
					return os.path.abspath(filename)
				else:
					return None
		except Exception as e:
			print(f"Screenshot failed: {e}")
			return None

	def send_enter(self):
		"""Send Enter with delay and timeout protection"""
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

	# Send text without triggering field protection
	def safe_send(self, text):
		for i in range(0,len(text)):
			self.send_string(text[i])
			if self.status.field_protection == 'P':
				return False # We triggered field protection, stop
		return True # Safe

	# Fill fields in carefully, checking for triggering field protections
	def safe_fieldfill(self, ypos, xpos, tosend, length):
		if length - len(tosend) < 0:
			raise FieldTruncateError('length limit %d, but got "%s"' % (length, tosend))
		if xpos is not None and ypos is not None:
			self.move_to(ypos, xpos)
		try:
			self.delete_field()
			if safe_send(self, tosend):
				return True # Hah, we win, take that mainframe
			else:
				return False # we entered what we could, bailing
		except CommandError as e:
			# We hit an error, get mad
			return False
			# if str(e) == 'Keyboard locked':

	# Search the screen for text when we don't know exactly where it is, checking for read errors
	def find_response(self, response):
		for rows in range(1,int(self.status.row_number)+1):
			for cols in range(1,int(self.status.col_number)+1-len(response)):
				try:
					if self.string_found(rows, cols, response):
						return True
				except CommandError as e:
					# We hit a read error, usually because the screen hasn't returned
					# increasing the delay works
					sleep(self.delay)
					self.delay += 1
					whine('Read error encountered, assuming host is slow, increasing delay by 1s to: ' + str(self.delay),kind='warn')
					return False
		return False
	
	# Get the current x3270 cursor position
	def get_pos(self, timeout=2):
		"""Get cursor position with timeout"""
		try:
			results = self.exec_command_with_timeout(b'Query(Cursor)', timeout=timeout)
			result = results.data[0]
			# Decode if bytes
			if isinstance(result, bytes):
				result = result.decode('utf-8')
			row = int(result.split(' ')[0])
			col = int(result.split(' ')[1])
			return (row, col)
		except (TimeoutError, Exception) as e:
			print(f"Warning: Could not get cursor position: {e}")
			return (0, 0)

	def get_hostinfo(self, timeout=2):
		"""Get host information with timeout"""
		try:
			result = self.exec_command_with_timeout(b'Query(Host)', timeout=timeout).data[0]
			# Decode if bytes
			if isinstance(result, bytes):
				result = result.decode('utf-8')
			return result.split(' ')
		except (TimeoutError, Exception) as e:
			print(f"Warning: Could not get host info: {e}")
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

	def connect(self, host_port, timeout=30):
		"""Connect to host with timeout protection

		Args:
			host_port: Host and port in format 'host:port' or just 'host' (default port 23)
			timeout: Timeout in seconds (default 30s for connection)
		"""
		try:
			# x3270 Connect command accepts host:port format directly
			# Use exec_command_with_timeout for the connect command
			command = f'Connect({host_port})'.encode()
			print(f"Connecting to {host_port}...")
			self.exec_command_with_timeout(command, timeout=timeout)
			print(f"Connected to {host_port}")
		except TimeoutError as e:
			print(f"Connection timed out after {timeout}s: {host_port}")
			raise
		except Exception as e:
			print(f"Connection failed: {e}")
			raise

# Set the emulator intelligently based on your platform
if platform.system() == 'Darwin':
	class WrappedEmulator(EmulatorIntermediate):
		# Try to find x3270/s3270 in common locations
		# Prefer locally built x3270 with BIRP patches
		import os
		home = os.path.expanduser('~')
		if path.isfile(f'{home}/.local/bin/x3270'):
			X3270App.executable = f'{home}/.local/bin/x3270'
		elif path.isfile('/opt/homebrew/bin/x3270'):
			X3270App.executable = '/opt/homebrew/bin/x3270'
		elif path.isfile('/usr/local/bin/x3270'):
			X3270App.executable = '/usr/local/bin/x3270'
		elif path.isfile('/opt/homebrew/Cellar/x3270/4.4ga6/bin/x3270'):
			X3270App.executable = '/opt/homebrew/Cellar/x3270/4.4ga6/bin/x3270'
		else:
			X3270App.executable = 'x3270'  # Hope it's in PATH
		
		# s3270 is the scriptable version used for console mode
		if path.isfile('/opt/homebrew/bin/s3270'):
			S3270App.executable = '/opt/homebrew/bin/s3270'
		elif path.isfile('/opt/homebrew/Cellar/x3270/4.4ga6/bin/s3270'):
			S3270App.executable = '/opt/homebrew/Cellar/x3270/4.4ga6/bin/s3270'
		elif path.isfile('/usr/local/bin/s3270'):
			S3270App.executable = '/usr/local/bin/s3270'
		else:
			S3270App.executable = 's3270'  # Hope it's in PATH

		def __init__(self, visible=True, delay=0, window_title="BIRP v2 - TN3270 Terminal", command_timeout=10):
			"""
			Initialize with timeout protection

			Args:
				visible: Use GUI (x3270) if True, console (s3270) if False
				delay: Delay between commands
				window_title: Window title for GUI mode
				command_timeout: Timeout in seconds for commands (default: 10)
			"""
			super().__init__(visible, delay, window_title, command_timeout)
			
elif platform.system() == 'Linux':
	class WrappedEmulator(EmulatorIntermediate):
		# Try common Linux paths
		if path.isfile('/usr/bin/x3270'):
			X3270App.executable = '/usr/bin/x3270'
		else:
			X3270App.executable = 'x3270'
		
		if path.isfile('/usr/bin/s3270'):
			S3270App.executable = '/usr/bin/s3270'
		else:
			S3270App.executable = 's3270'

		def __init__(self, visible=True, delay=0, window_title="BIRP v2 - TN3270 Terminal", command_timeout=10):
			super().__init__(visible, delay, window_title, command_timeout)

elif platform.system() == 'Windows':
	class WrappedEmulator(EmulatorIntermediate):
		X3270App.executable = 'wc3270.exe'

		def __init__(self, visible=True, delay=0, window_title="BIRP v2 - TN3270 Terminal", command_timeout=10):
			super().__init__(visible, delay, window_title, command_timeout)
else:
	print('Your Platform:', platform.system(), 'is not supported at this time.')
	exit(1)

# Check for s3270 executable (warning only, not fatal on import)
if not path.isfile(S3270App.executable):
	import warnings
	warnings.warn(
		f"s3270 executable not found at {S3270App.executable}. "
		f"Install x3270 suite: brew install x3270 (macOS) or apt-get install x3270 (Linux). "
		f"The tool will not work without x3270 installed.",
		RuntimeWarning
	)
