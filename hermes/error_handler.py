"""
Hermes Error Handler System
Comprehensive error handling and recovery mechanisms
"""

import logging
import traceback
import sys
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

from .config import Config
from .database import Database

logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    """Error categories for classification"""
    SYSTEM = "system"
    NETWORK = "network"
    DATABASE = "database"
    EXECUTION = "execution"
    VALIDATION = "validation"
    TIMEOUT = "timeout"
    RESOURCE = "resource"
    AUTHENTICATION = "authentication"
    CONFIGURATION = "configuration"

@dataclass
class ErrorReport:
    """Structured error report"""
    error_id: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    traceback: str
    context: Dict[str, Any]
    timestamp: datetime
    job_id: Optional[int] = None
    user_id: Optional[str] = None
    resolved: bool = False
    resolution_notes: Optional[str] = None

class ErrorHandler:
    """Centralized error handling system"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.error_handlers = {}
        self.error_callbacks = []
        self.suppressed_errors = set()

        # Register default handlers
        self._register_default_handlers()

    def _register_default_handlers(self):
        """Register default error handlers"""
        self.register_handler(
            Exception,
            self._handle_generic_exception,
            ErrorCategory.SYSTEM,
            ErrorSeverity.MEDIUM
        )

        self.register_handler(
            ConnectionError,
            self._handle_connection_error,
            ErrorCategory.NETWORK,
            ErrorSeverity.HIGH
        )

        self.register_handler(
            TimeoutError,
            self._handle_timeout_error,
            ErrorCategory.TIMEOUT,
            ErrorSeverity.HIGH
        )

        self.register_handler(
            ValueError,
            self._handle_validation_error,
            ErrorCategory.VALIDATION,
            ErrorSeverity.MEDIUM
        )

        self.register_handler(
            FileNotFoundError,
            self._handle_file_error,
            ErrorCategory.RESOURCE,
            ErrorSeverity.MEDIUM
        )

    def register_handler(
        self,
        exception_type: type,
        handler_func: Callable,
        category: ErrorCategory,
        severity: ErrorSeverity
    ):
        """Register an error handler for a specific exception type"""
        self.error_handlers[exception_type] = {
            'handler': handler_func,
            'category': category,
            'severity': severity
        }

    def handle_error(
        self,
        exception: Exception,
        context: Optional[Dict[str, Any]] = None,
        job_id: Optional[int] = None,
        user_id: Optional[str] = None
    ) -> ErrorReport:
        """
        Handle an exception and create an error report

        Args:
            exception: The exception that occurred
            context: Additional context information
            job_id: Associated job ID
            user_id: Associated user ID

        Returns:
            ErrorReport with details about the error
        """
        try:
            # Generate unique error ID
            error_id = f"err_{int(datetime.now().timestamp() * 1000)}_{hash(str(exception)) % 10000:04d}"

            # Find appropriate handler
            exception_type = type(exception)
            handler_info = self._find_handler(exception_type)

            # Create error report
            error_report = ErrorReport(
                error_id=error_id,
                category=handler_info['category'],
                severity=handler_info['severity'],
                message=str(exception),
                traceback=traceback.format_exc(),
                context=context or {},
                timestamp=datetime.now(),
                job_id=job_id,
                user_id=user_id
            )

            # Log the error
            self._log_error(error_report)

            # Execute handler
            try:
                handler_info['handler'](exception, error_report, context)
            except Exception as handler_error:
                logger.error(f"Error handler failed: {handler_error}")

            # Store in database
            self._store_error_report(error_report)

            # Execute callbacks
            self._execute_callbacks(error_report)

            return error_report

        except Exception as e:
            # Fallback error handling
            logger.critical(f"Error handling system failed: {e}")
            logger.critical(f"Original error: {exception}")
            return ErrorReport(
                error_id="fallback_error",
                category=ErrorCategory.CRITICAL,
                severity=ErrorSeverity.CRITICAL,
                message=f"Error handler failed: {str(e)} | Original: {str(exception)}",
                traceback=traceback.format_exc(),
                context={'original_error': str(exception)},
                timestamp=datetime.now()
            )

    def _find_handler(self, exception_type: type) -> Dict[str, Any]:
        """Find appropriate handler for exception type"""
        # Direct match
        if exception_type in self.error_handlers:
            return self.error_handlers[exception_type]

        # Look for parent class matches
        for exc_type, handler_info in self.error_handlers.items():
            if issubclass(exception_type, exc_type):
                return handler_info

        # Default handler
        return {
            'handler': self._handle_generic_exception,
            'category': ErrorCategory.SYSTEM,
            'severity': ErrorSeverity.MEDIUM
        }

    def _log_error(self, error_report: ErrorReport):
        """Log error with appropriate level"""
        message = f"[{error_report.error_id}] {error_report.category.value.upper()}: {error_report.message}"

        if error_report.severity == ErrorSeverity.CRITICAL:
            logger.critical(message)
        elif error_report.severity == ErrorSeverity.HIGH:
            logger.error(message)
        elif error_report.severity == ErrorSeverity.MEDIUM:
            logger.warning(message)
        else:
            logger.info(message)

        # Log detailed info
        logger.debug(f"Error context: {error_report.context}")
        if error_report.job_id:
            logger.debug(f"Associated job ID: {error_report.job_id}")

    def _store_error_report(self, error_report: ErrorReport):
        """Store error report in database"""
        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO error_reports (
                        error_id, category, severity, message, traceback,
                        context, timestamp, job_id, user_id, resolved
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    error_report.error_id,
                    error_report.category.value,
                    error_report.severity.value,
                    error_report.message,
                    error_report.traceback,
                    str(error_report.context),
                    error_report.timestamp,
                    error_report.job_id,
                    error_report.user_id,
                    error_report.resolved
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to store error report: {e}")

    def _execute_callbacks(self, error_report: ErrorReport):
        """Execute error callbacks"""
        for callback in self.error_callbacks:
            try:
                callback(error_report)
            except Exception as e:
                logger.error(f"Error callback failed: {e}")

    # Default error handlers
    def _handle_generic_exception(self, exception: Exception, error_report: ErrorReport, context: Dict[str, Any]):
        """Handle generic exceptions"""
        logger.info(f"Handling generic exception: {type(exception).__name__}")

    def _handle_connection_error(self, exception: ConnectionError, error_report: ErrorReport, context: Dict[str, Any]):
        """Handle connection errors"""
        logger.warning("Connection error detected - may need to retry or failover")
        # Could trigger failover logic here

    def _handle_timeout_error(self, exception: TimeoutError, error_report: ErrorReport, context: Dict[str, Any]):
        """Handle timeout errors"""
        logger.warning("Timeout error detected - may need to increase timeout or retry")
        # Could trigger timeout adjustment here

    def _handle_validation_error(self, exception: ValueError, error_report: ErrorReport, context: Dict[str, Any]):
        """Handle validation errors"""
        logger.warning("Validation error detected - input validation failed")
        # Usually shouldn't retry validation errors

    def _handle_file_error(self, exception: FileNotFoundError, error_report: ErrorReport, context: Dict[str, Any]):
        """Handle file not found errors"""
        logger.warning("File not found error - check file paths and permissions")
        # Could trigger file creation or fallback logic

    def add_error_callback(self, callback: Callable[[ErrorReport], None]):
        """Add callback to be executed when errors occur"""
        self.error_callbacks.append(callback)

    def suppress_error_type(self, exception_type: type):
        """Suppress logging of specific error types"""
        self.suppressed_errors.add(exception_type)

    def get_error_statistics(self, days: int = 7) -> Dict[str, Any]:
        """Get error statistics for the last N days"""
        try:
            with self.db.get_connection() as conn:
                cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)

                cursor = conn.execute("""
                    SELECT category, severity, COUNT(*) as count
                    FROM error_reports
                    WHERE timestamp > ?
                    GROUP BY category, severity
                    ORDER BY count DESC
                """, (cutoff_date,))

                stats = {
                    'total_errors': 0,
                    'by_category': {},
                    'by_severity': {},
                    'top_errors': []
                }

                for row in cursor.fetchall():
                    category = row['category']
                    severity = row['severity']
                    count = row['count']

                    stats['total_errors'] += count

                    if category not in stats['by_category']:
                        stats['by_category'][category] = 0
                    stats['by_category'][category] += count

                    if severity not in stats['by_severity']:
                        stats['by_severity'][severity] = 0
                    stats['by_severity'][severity] += count

                # Get top error messages
                cursor = conn.execute("""
                    SELECT message, COUNT(*) as count
                    FROM error_reports
                    WHERE timestamp > ?
                    GROUP BY message
                    ORDER BY count DESC
                    LIMIT 10
                """, (cutoff_date,))

                stats['top_errors'] = [
                    {'message': row['message'], 'count': row['count']}
                    for row in cursor.fetchall()
                ]

                return stats

        except Exception as e:
            logger.error(f"Failed to get error statistics: {e}")
            return {}

    def resolve_error(self, error_id: str, resolution_notes: str = None):
        """Mark an error as resolved"""
        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    UPDATE error_reports
                    SET resolved = 1, resolution_notes = ?
                    WHERE error_id = ?
                """, (resolution_notes, error_id))
                conn.commit()
                logger.info(f"Error {error_id} marked as resolved")
        except Exception as e:
            logger.error(f"Failed to resolve error {error_id}: {e}")

# Global error handler instance
_error_handler = None

def get_error_handler(config: Optional[Config] = None) -> ErrorHandler:
    """Get global error handler instance"""
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler(config)
    return _error_handler

def handle_error(
    exception: Exception,
    context: Optional[Dict[str, Any]] = None,
    job_id: Optional[int] = None,
    user_id: Optional[str] = None
) -> ErrorReport:
    """Convenience function to handle an error"""
    return get_error_handler().handle_error(exception, context, job_id, user_id)

# Decorator for automatic error handling
def error_handler(
    category: ErrorCategory = ErrorCategory.SYSTEM,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    context: Optional[Dict[str, Any]] = None
):
    """Decorator for automatic error handling"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Extract job_id from kwargs if available
                job_id = kwargs.get('job_id')

                # Handle the error
                error_report = handle_error(e, context, job_id)

                # Re-raise the exception if it's critical
                if error_report.severity == ErrorSeverity.CRITICAL:
                    raise

                return None
        return wrapper
    return decorator