"""
Hermes Retry System
Handles intelligent retry logic with exponential backoff and circuit breaking
"""

import time
import logging
import random
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

from .config import Config
from .database import Database

logger = logging.getLogger(__name__)

class RetryStrategy(Enum):
    """Retry strategies for different failure types"""
    IMMEDIATE = "immediate"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    CIRCUIT_BREAK = "circuit_break"

@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    circuit_break_threshold: int = 5
    circuit_break_timeout: float = 300.0  # 5 minutes

@dataclass
class RetryAttempt:
    """Track individual retry attempts"""
    attempt_number: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    success: bool = False
    error_message: str = ""
    response_time_ms: int = 0

@dataclass
class RetryHistory:
    """Track retry history for a job"""
    job_id: int
    attempts: List[RetryAttempt] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    final_success: bool = False

class CircuitBreaker:
    """Circuit breaker to prevent cascading failures"""

    def __init__(self, threshold: int = 5, timeout: float = 300.0):
        self.threshold = threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open

    def can_execute(self) -> bool:
        """Check if execution is allowed"""
        if self.state == "closed":
            return True
        elif self.state == "open":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half_open"
                return True
            return False
        else:  # half_open
            return True

    def record_success(self):
        """Record successful execution"""
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self):
        """Record failed execution"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")

class RetryManager:
    """Manages retry logic for failed jobs"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.circuit_breakers = {}
        self.retry_configs = self._load_retry_configs()

    def _load_retry_configs(self) -> Dict[str, RetryConfig]:
        """Load retry configurations"""
        default_config = RetryConfig(
            max_attempts=self.config.get('retry.max_attempts', 3),
            base_delay=self.config.get('retry.base_delay', 1.0),
            max_delay=self.config.get('retry.max_delay', 60.0),
            backoff_multiplier=self.config.get('retry.backoff_multiplier', 2.0),
            jitter=self.config.get('retry.jitter', True),
            strategy=RetryStrategy(self.config.get('retry.strategy', 'exponential_backoff')),
            circuit_break_threshold=self.config.get('retry.circuit_break_threshold', 5),
            circuit_break_timeout=self.config.get('retry.circuit_break_timeout', 300.0)
        )

        # Error-specific configurations
        return {
            'default': default_config,
            'timeout': RetryConfig(
                max_attempts=2,
                base_delay=5.0,
                max_delay=30.0,
                strategy=RetryStrategy.LINEAR_BACKOFF
            ),
            'connection_error': RetryConfig(
                max_attempts=5,
                base_delay=2.0,
                max_delay=120.0,
                circuit_break_threshold=3
            ),
            'validation_error': RetryConfig(
                max_attempts=1,  # Don't retry validation errors
                strategy=RetryStrategy.IMMEDIATE
            ),
            'rate_limit': RetryConfig(
                max_attempts=3,
                base_delay=60.0,  # Start with 1 minute delay
                max_delay=300.0,  # Max 5 minutes
                strategy=RetryStrategy.EXPONENTIAL_BACKOFF
            )
        }

    def should_retry_job(self, job_id: int, error_message: str) -> bool:
        """Determine if a job should be retried"""
        try:
            # Get retry history
            history = self._get_retry_history(job_id)

            if history and len(history.attempts) >= self._get_retry_config(error_message).max_attempts:
                logger.info(f"Job {job_id} exceeded max retry attempts")
                return False

            # Check circuit breaker
            backend_name = self._extract_backend_from_error(error_message)
            circuit_breaker = self._get_circuit_breaker(backend_name)

            if not circuit_breaker.can_execute():
                logger.warning(f"Circuit breaker open for backend {backend_name}, not retrying job {job_id}")
                return False

            # Check error type
            if not self._is_retryable_error(error_message):
                logger.info(f"Job {job_id} failed with non-retryable error: {error_message}")
                return False

            return True

        except Exception as e:
            logger.error(f"Error determining retry eligibility for job {job_id}: {e}")
            return False

    def retry_job(self, job_id: int, error_message: str, retry_func: Callable) -> bool:
        """Execute a job retry with appropriate delay"""
        try:
            retry_config = self._get_retry_config(error_message)
            history = self._get_or_create_history(job_id)

            attempt_number = len(history.attempts) + 1
            delay = self._calculate_delay(retry_config, attempt_number)

            logger.info(f"Retrying job {job_id}, attempt {attempt_number}/{retry_config.max_attempts}, delay: {delay:.1f}s")

            # Record retry attempt start
            attempt = RetryAttempt(
                attempt_number=attempt_number,
                started_at=datetime.now()
            )
            history.attempts.append(attempt)

            # Wait before retry
            if delay > 0:
                time.sleep(delay)

            # Execute retry
            start_time = time.time()
            try:
                result = retry_func()
                execution_time = (time.time() - start_time) * 1000

                # Record successful attempt
                attempt.completed_at = datetime.now()
                attempt.success = True
                attempt.response_time_ms = int(execution_time)

                history.completed_at = datetime.now()
                history.final_success = True

                # Update circuit breaker
                backend_name = self._extract_backend_from_error(error_message)
                circuit_breaker = self._get_circuit_breaker(backend_name)
                circuit_breaker.record_success()

                # Record in database
                self._record_retry_success(job_id, attempt, result)

                logger.info(f"Job {job_id} retry {attempt_number} succeeded")
                return True

            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                retry_error = str(e)

                # Record failed attempt
                attempt.completed_at = datetime.now()
                attempt.success = False
                attempt.error_message = retry_error
                attempt.response_time_ms = int(execution_time)

                # Update circuit breaker
                backend_name = self._extract_backend_from_error(error_message)
                circuit_breaker = self._get_circuit_breaker(backend_name)
                circuit_breaker.record_failure()

                # Record in database
                self._record_retry_failure(job_id, attempt, retry_error)

                logger.error(f"Job {job_id} retry {attempt_number} failed: {retry_error}")

                # Check if we should retry again
                if attempt_number < retry_config.max_attempts:
                    return self.retry_job(job_id, retry_error, retry_func)
                else:
                    logger.error(f"Job {job_id} exhausted all retry attempts")
                    return False

        except Exception as e:
            logger.error(f"Unexpected error during job {job_id} retry: {e}")
            return False

    def _get_retry_config(self, error_message: str) -> RetryConfig:
        """Get appropriate retry config based on error type"""
        error_lower = error_message.lower()

        if 'timeout' in error_lower:
            return self.retry_configs['timeout']
        elif 'connection' in error_lower or 'network' in error_lower:
            return self.retry_configs['connection_error']
        elif 'validation' in error_lower or 'schema' in error_lower:
            return self.retry_configs['validation_error']
        elif 'rate limit' in error_lower or 'too many requests' in error_lower:
            return self.retry_configs['rate_limit']
        else:
            return self.retry_configs['default']

    def _calculate_delay(self, config: RetryConfig, attempt_number: int) -> float:
        """Calculate delay before next retry"""
        if config.strategy == RetryStrategy.IMMEDIATE:
            return 0
        elif config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = config.base_delay * attempt_number
        elif config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = config.base_delay * (config.backoff_multiplier ** (attempt_number - 1))
        else:
            delay = config.base_delay

        # Apply max delay limit
        delay = min(delay, config.max_delay)

        # Add jitter if enabled
        if config.jitter:
            jitter_range = delay * 0.1
            delay += random.uniform(-jitter_range, jitter_range)

        return max(0, delay)

    def _is_retryable_error(self, error_message: str) -> bool:
        """Check if error is retryable"""
        non_retryable_patterns = [
            'validation failed',
            'invalid schema',
            'malformed request',
            'authentication failed',
            'authorization failed',
            'permission denied',
            'not found'
        ]

        error_lower = error_message.lower()
        return not any(pattern in error_lower for pattern in non_retryable_patterns)

    def _extract_backend_from_error(self, error_message: str) -> str:
        """Extract backend name from error message"""
        # Simple extraction - can be enhanced
        if 'ollama' in error_message.lower():
            return 'ollama'
        elif 'talos' in error_message.lower():
            return 'talos'
        elif 'openrouter' in error_message.lower():
            return 'openrouter'
        else:
            return 'unknown'

    def _get_circuit_breaker(self, backend_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for backend"""
        if backend_name not in self.circuit_breakers:
            self.circuit_breakers[backend_name] = CircuitBreaker(
                threshold=self.retry_configs['connection_error'].circuit_break_threshold,
                timeout=self.retry_configs['connection_error'].circuit_break_timeout
            )
        return self.circuit_breakers[backend_name]

    def _get_retry_history(self, job_id: int) -> Optional[RetryHistory]:
        """Get retry history for job from database"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT retry_data FROM job_retry_history WHERE job_id = ?",
                    (job_id,)
                )
                row = cursor.fetchone()
                if row and row['retry_data']:
                    # Deserialize history from JSON
                    # This is simplified - in practice you'd store individual attempts
                    return RetryHistory(job_id=job_id)
        except Exception as e:
            logger.error(f"Failed to get retry history for job {job_id}: {e}")
        return None

    def _get_or_create_history(self, job_id: int) -> RetryHistory:
        """Get or create retry history"""
        history = self._get_retry_history(job_id)
        if not history:
            history = RetryHistory(job_id=job_id)
            # Save to database
            self._save_retry_history(history)
        return history

    def _save_retry_history(self, history: RetryHistory):
        """Save retry history to database"""
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO job_retry_history
                       (job_id, retry_data, created_at, completed_at, final_success)
                       VALUES (?, ?, ?, ?, ?)""",
                    (history.job_id, '{}', history.created_at, history.completed_at, history.final_success)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save retry history: {e}")

    def _record_retry_success(self, job_id: int, attempt: RetryAttempt, result: Any):
        """Record successful retry in database"""
        try:
            self.db.create_job_event(job_id, 'retry_success', {
                'attempt_number': attempt.attempt_number,
                'response_time_ms': attempt.response_time_ms,
                'result': str(result)[:500]  # Limit size
            })
        except Exception as e:
            logger.error(f"Failed to record retry success: {e}")

    def _record_retry_failure(self, job_id: int, attempt: RetryAttempt, error_message: str):
        """Record failed retry in database"""
        try:
            self.db.create_job_event(job_id, 'retry_failure', {
                'attempt_number': attempt.attempt_number,
                'response_time_ms': attempt.response_time_ms,
                'error_message': error_message
            })
        except Exception as e:
            logger.error(f"Failed to record retry failure: {e}")

    def get_retry_stats(self) -> Dict[str, Any]:
        """Get retry system statistics"""
        stats = {
            'circuit_breakers': {},
            'total_backends': len(self.circuit_breakers),
            'open_circuits': sum(1 for cb in self.circuit_breakers.values() if cb.state == 'open')
        }

        for backend, breaker in self.circuit_breakers.items():
            stats['circuit_breakers'][backend] = {
                'state': breaker.state,
                'failure_count': breaker.failure_count,
                'last_failure': breaker.last_failure_time
            }

        return stats