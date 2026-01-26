#!/usr/bin/env python3
"""
Session logging for BIRP v2
Automatic logging of all sessions with rotation

Author: @w00tock
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

class SessionLogger:
    """Manages session-based logging with automatic rotation"""
    
    def __init__(self, log_dir='logs', max_bytes=10*1024*1024, backup_count=5):
        """
        Initialize session logger
        
        Args:
            log_dir: Directory to store log files
            max_bytes: Maximum size per log file (default: 10MB)
            backup_count: Number of backup files to keep
        """
        self.log_dir = log_dir
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        
        # Create log directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)
        
        # Generate session log filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_log = os.path.join(log_dir, f"birp_session_{timestamp}.log")
        self.main_log = os.path.join(log_dir, "birp.log")
        
        # Setup loggers
        self._setup_session_logger()
        self._setup_main_logger()
    
    def _setup_session_logger(self):
        """Setup session-specific logger"""
        self.session_logger = logging.getLogger('birp.session')
        self.session_logger.setLevel(logging.DEBUG)
        
        # Session file handler (no rotation, one file per session)
        session_handler = logging.FileHandler(self.session_log)
        session_handler.setLevel(logging.DEBUG)
        session_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.session_logger.addHandler(session_handler)
    
    def _setup_main_logger(self):
        """Setup main rotating logger"""
        self.main_logger = logging.getLogger('birp.main')
        self.main_logger.setLevel(logging.INFO)
        
        # Rotating file handler for main log
        main_handler = RotatingFileHandler(
            self.main_log,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count
        )
        main_handler.setLevel(logging.INFO)
        main_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.main_logger.addHandler(main_handler)
    
    def log_session(self, message, level='INFO'):
        """Log to session file"""
        level_map = {
            'DEBUG': self.session_logger.debug,
            'INFO': self.session_logger.info,
            'WARNING': self.session_logger.warning,
            'ERROR': self.session_logger.error,
            'CRITICAL': self.session_logger.critical
        }
        log_func = level_map.get(level.upper(), self.session_logger.info)
        log_func(message)
    
    def log_main(self, message, level='INFO'):
        """Log to main rotating file"""
        level_map = {
            'DEBUG': self.main_logger.debug,
            'INFO': self.main_logger.info,
            'WARNING': self.main_logger.warning,
            'ERROR': self.main_logger.error,
            'CRITICAL': self.main_logger.critical
        }
        log_func = level_map.get(level.upper(), self.main_logger.info)
        log_func(message)
    
    def log_both(self, message, level='INFO'):
        """Log to both session and main files"""
        self.log_session(message, level)
        self.log_main(message, level)
    
    def get_session_log_path(self):
        """Get path to current session log"""
        return os.path.abspath(self.session_log)
    
    def get_main_log_path(self):
        """Get path to main log"""
        return os.path.abspath(self.main_log)


# Global session logger instance
_session_logger = None

def init_session_logging(log_dir='logs'):
    """Initialize global session logger"""
    global _session_logger
    _session_logger = SessionLogger(log_dir=log_dir)
    return _session_logger

def get_session_logger():
    """Get global session logger instance"""
    global _session_logger
    if _session_logger is None:
        _session_logger = SessionLogger()
    return _session_logger

def log_session_event(message, level='INFO'):
    """Log event to session log"""
    get_session_logger().log_both(message, level)
