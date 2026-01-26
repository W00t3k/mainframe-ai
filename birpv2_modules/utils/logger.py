#!/usr/bin/env python
"""
Enhanced logging module for BIRP
Provides structured logging with file output support
"""

import logging
import sys
from datetime import datetime
from colorama import Fore, Style

class BIRPLogger:
	"""Enhanced logger for BIRP with color support and file output"""

	def __init__(self, quiet=False, log_file=None, log_level=logging.INFO):
		"""
		Initialize the BIRPv2 logger

		Args:
			quiet (bool): Suppress info and warning messages
			log_file (str): Optional path to log file
			log_level: Logging level (default: INFO)
		"""
		self.quiet = quiet
		self.logger = logging.getLogger('birp')
		self.logger.setLevel(log_level)

		# Console handler with colors
		console_handler = logging.StreamHandler(sys.stdout)
		console_handler.setLevel(log_level)
		console_handler.setFormatter(ColoredFormatter())
		self.logger.addHandler(console_handler)

		# File handler if specified
		if log_file:
			file_handler = logging.FileHandler(log_file)
			file_handler.setLevel(logging.DEBUG)
			file_handler.setFormatter(logging.Formatter(
				'%(asctime)s - %(name)s - %(levelname)s - %(message)s'
			))
			self.logger.addHandler(file_handler)

	def log(self, text, kind='clear', level=0):
		"""
		Log a message with the specified kind and indentation level

		Args:
			text (str): Message to log
			kind (str): Message type - 'info', 'warn', 'err', 'good', 'clear', 'debug'
			level (int): Indentation level (0-3)
		"""
		if self.quiet and kind in ['warn', 'info']:
			return

		indent = '\t' * level
		message = indent + text

		if kind == 'debug':
			self.logger.debug(message)
		elif kind == 'info':
			self.logger.info(message)
		elif kind == 'warn':
			self.logger.warning(message)
		elif kind == 'err':
			self.logger.error(message)
		elif kind == 'good':
			self.logger.info(message)
		else:  # clear
			print(indent + text)

	def debug(self, message, level=0):
		"""Log debug message"""
		self.log(message, kind='debug', level=level)

	def info(self, message, level=0):
		"""Log info message"""
		self.log(message, kind='info', level=level)

	def warning(self, message, level=0):
		"""Log warning message"""
		self.log(message, kind='warn', level=level)

	def error(self, message, level=0):
		"""Log error message"""
		self.log(message, kind='err', level=level)

	def success(self, message, level=0):
		"""Log success message"""
		self.log(message, kind='good', level=level)


class ColoredFormatter(logging.Formatter):
	"""Custom formatter with color support"""

	COLORS = {
		'DEBUG': Fore.CYAN,
		'INFO': Fore.BLUE,
		'WARNING': Fore.YELLOW,
		'ERROR': Fore.RED,
		'CRITICAL': Fore.RED + Style.BRIGHT,
	}

	PREFIXES = {
		'DEBUG': '[?] ',
		'INFO': '[+] ',
		'WARNING': '[!] ',
		'ERROR': '[#] ',
		'CRITICAL': '[#] ',
	}

	def format(self, record):
		# Get color and prefix for this level
		color = self.COLORS.get(record.levelname, '')
		prefix = self.PREFIXES.get(record.levelname, '')

		# Format the message
		message = prefix + record.getMessage()

		# Add color if terminal supports it
		if color:
			message = color + message + Style.RESET_ALL

		return message


# Global logger instance
_global_logger = None

def setup_logger(log_file=None, log_level='INFO'):
	"""
	Setup the global logger instance
	
	Args:
		log_file (str): Optional path to log file
		log_level (str): Logging level as string (DEBUG, INFO, WARNING, ERROR)
	"""
	global _global_logger
	
	level_map = {
		'DEBUG': logging.DEBUG,
		'INFO': logging.INFO,
		'WARNING': logging.WARNING,
		'ERROR': logging.ERROR
	}
	
	level = level_map.get(log_level.upper(), logging.INFO)
	_global_logger = BIRPLogger(quiet=False, log_file=log_file, log_level=level)

def get_logger():
	"""Get the global logger instance"""
	global _global_logger
	if _global_logger is None:
		_global_logger = BIRPLogger()
	return _global_logger

def log_info(message, level=0):
	"""Log info message using global logger"""
	get_logger().info(message, level)

def log_warning(message, level=0):
	"""Log warning message using global logger"""
	get_logger().warning(message, level)

def log_error(message, level=0):
	"""Log error message using global logger"""
	get_logger().error(message, level)

def log_debug(message, level=0):
	"""Log debug message using global logger"""
	get_logger().debug(message, level)

def log_success(message, level=0):
	"""Log success message using global logger"""
	get_logger().success(message, level)

# Convenience function for backward compatibility
def create_logger(quiet=False, log_file=None, log_level=logging.INFO):
	"""
	Create and return a BIRP logger instance

	Args:
		quiet (bool): Suppress info and warning messages
		log_file (str): Optional path to log file
		log_level: Logging level (default: INFO)

	Returns:
		BIRPLogger: Configured logger instance
	"""
	return BIRPLogger(quiet=quiet, log_file=log_file, log_level=log_level)
