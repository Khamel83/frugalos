"""
Hermes Logging System
Centralized logging configuration for all Hermes components
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

def setup_logger(
    name: str,
    level: str = "INFO",
    log_dir: str = "logs",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    console_output: bool = True
) -> logging.Logger:
    """
    Set up a logger with both file and console handlers

    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup log files to keep
        console_output: Whether to output to console

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Set log level
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Create log directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    simple_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%H:%M:%S'
    )

    # File handler with rotation
    log_file = log_path / f"{name.replace('hermes.', '')}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)

    # Error-only file handler
    error_log_file = log_path / f"{name.replace('hermes.', '')}_errors.log"
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    logger.addHandler(error_handler)

    # Console handler (optional)
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(simple_formatter)
        logger.addHandler(console_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger

class HermesLogger:
    """Enhanced logger class with additional methods for structured logging"""

    def __init__(self, name: str):
        self.logger = logging.getLogger(f"hermes.{name}")
        self.name = name

    def debug(self, message: str, **kwargs):
        """Log debug message with optional structured data"""
        self._log_with_context(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message with optional structured data"""
        self._log_with_context(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message with optional structured data"""
        self._log_with_context(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message with optional structured data"""
        self._log_with_context(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Log critical message with optional structured data"""
        self._log_with_context(logging.CRITICAL, message, **kwargs)

    def job_event(self, job_id: int, event: str, **kwargs):
        """Log job-specific event"""
        self._log_with_context(
            logging.INFO,
            f"Job {job_id}: {event}",
            job_id=job_id,
            event_type=event,
            **kwargs
        )

    def backend_event(self, backend_id: int, backend_name: str, event: str, **kwargs):
        """Log backend-specific event"""
        self._log_with_context(
            logging.INFO,
            f"Backend {backend_name} ({backend_id}): {event}",
            backend_id=backend_id,
            backend_name=backend_name,
            event_type=event,
            **kwargs
        )

    def api_request(self, method: str, endpoint: str, status_code: int, response_time_ms: float, **kwargs):
        """Log API request"""
        level = logging.INFO if 200 <= status_code < 400 else logging.ERROR
        self._log_with_context(
            level,
            f"{method} {endpoint} -> {status_code} ({response_time_ms:.0f}ms)",
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            response_time_ms=response_time_ms,
            **kwargs
        )

    def database_query(self, query_type: str, table: str, duration_ms: float, **kwargs):
        """Log database operation"""
        self._log_with_context(
            logging.DEBUG,
            f"DB {query_type} on {table} ({duration_ms:.0f}ms)",
            query_type=query_type,
            table=table,
            duration_ms=duration_ms,
            **kwargs
        )

    def performance_metric(self, metric_name: str, value: float, unit: str = None, **kwargs):
        """Log performance metric"""
        self._log_with_context(
            logging.INFO,
            f"Metric {metric_name}: {value}{' ' + unit if unit else ''}",
            metric_name=metric_name,
            value=value,
            unit=unit,
            **kwargs
        )

    def _log_with_context(self, level: int, message: str, **kwargs):
        """Internal method to log with structured context"""
        if kwargs:
            context_str = " | " + " | ".join([f"{k}={v}" for k, v in kwargs.items()])
            message += context_str

        self.logger.log(level, message)

def configure_logging(config_dict: dict = None):
    """
    Configure global logging settings

    Args:
        config_dict: Dictionary with logging configuration
    """
    # Default configuration
    default_config = {
        'level': 'INFO',
        'log_dir': 'logs',
        'max_bytes': 10 * 1024 * 1024,
        'backup_count': 5,
        'console_output': True,
        'disable_external_loggers': True
    }

    # Merge with provided config
    if config_dict:
        default_config.update(config_dict)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, default_config['level'].upper(), logging.INFO))

    # Disable noisy external loggers
    if default_config.get('disable_external_loggers'):
        external_loggers = [
            'urllib3.connectionpool',
            'requests.packages.urllib3',
            'werkzeug',
            'flask',
            'sqlite3'
        ]
        for logger_name in external_loggers:
            logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Set up main application logger
    return setup_logger(
        'hermes',
        level=default_config['level'],
        log_dir=default_config['log_dir'],
        max_bytes=default_config['max_bytes'],
        backup_count=default_config['backup_count'],
        console_output=default_config['console_output']
    )

# Convenience function for getting a logger
def get_logger(name: str) -> HermesLogger:
    """Get a HermesLogger instance"""
    return HermesLogger(name)