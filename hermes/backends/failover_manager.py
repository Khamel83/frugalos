"""
Backend Failover Management
Automatic failover and recovery for backend failures
"""

import logging
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from collections import deque

from ..config import Config
from ..database import Database
from ..logger import get_logger
from .health_monitor import BackendHealthMonitor, HealthStatus
from .load_balancer import BackendLoadBalancer

logger = get_logger('backends.failover_manager')

class FailoverStrategy(Enum):
    """Failover strategies"""
    IMMEDIATE = "immediate"  # Fail over immediately on error
    PROGRESSIVE = "progressive"  # Try alternatives progressively
    CIRCUIT_BREAKER = "circuit_breaker"  # Circuit breaker pattern
    RETRY_THEN_FAILOVER = "retry_then_failover"  # Retry first, then fail over

@dataclass
class FailoverEvent:
    """Record of a failover event"""
    timestamp: datetime
    original_backend: str
    failover_backend: str
    reason: str
    success: bool
    metadata: Dict[str, Any]

class FailoverManager:
    """Manages automatic failover between backends"""

    def __init__(
        self,
        health_monitor: BackendHealthMonitor,
        load_balancer: BackendLoadBalancer,
        config: Optional[Config] = None
    ):
        self.config = config or Config()
        self.db = Database()
        self.health_monitor = health_monitor
        self.load_balancer = load_balancer
        self.logger = get_logger('failover_manager')

        # Failover configuration
        self.default_strategy = FailoverStrategy[
            self.config.get('backends.failover_strategy', 'PROGRESSIVE')
        ]
        self.max_retries = self.config.get('backends.max_retries', 2)
        self.retry_delay_seconds = self.config.get('backends.retry_delay', 1.0)
        self.circuit_breaker_threshold = self.config.get('backends.circuit_breaker_threshold', 5)
        self.circuit_breaker_timeout = self.config.get('backends.circuit_breaker_timeout', 60)

        # State tracking
        self._failover_history = deque(maxlen=1000)
        self._circuit_breakers = {}  # backend_name -> (open_time, failure_count)
        self._failover_chains = {}  # backend_name -> [fallback_backends]

    def execute_with_failover(
        self,
        backends: List[str],
        operation: Callable[[str], Any],
        strategy: Optional[FailoverStrategy] = None,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Execute operation with automatic failover

        Args:
            backends: Ordered list of backends to try
            operation: Function that takes backend_name and performs operation
            strategy: Failover strategy to use
            context: Additional context for failover decisions

        Returns:
            Result dictionary with success status, result, and metadata
        """
        strategy = strategy or self.default_strategy
        context = context or {}

        if strategy == FailoverStrategy.IMMEDIATE:
            return self._immediate_failover(backends, operation, context)
        elif strategy == FailoverStrategy.PROGRESSIVE:
            return self._progressive_failover(backends, operation, context)
        elif strategy == FailoverStrategy.CIRCUIT_BREAKER:
            return self._circuit_breaker_failover(backends, operation, context)
        elif strategy == FailoverStrategy.RETRY_THEN_FAILOVER:
            return self._retry_then_failover(backends, operation, context)
        else:
            return self._progressive_failover(backends, operation, context)

    def _immediate_failover(
        self,
        backends: List[str],
        operation: Callable[[str], Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Immediate failover on first error"""
        for i, backend in enumerate(backends):
            if not self._is_backend_available(backend):
                continue

            try:
                start_time = time.time()
                self.load_balancer.start_request(backend)

                result = operation(backend)

                response_time = (time.time() - start_time) * 1000
                self.load_balancer.end_request(backend, True, response_time)

                if i > 0:
                    # Record failover event
                    self._record_failover(
                        backends[0],
                        backend,
                        "immediate_failover",
                        True,
                        context
                    )

                return {
                    'success': True,
                    'result': result,
                    'backend_used': backend,
                    'failover_occurred': i > 0,
                    'attempts': i + 1
                }

            except Exception as e:
                response_time = (time.time() - start_time) * 1000
                self.load_balancer.end_request(backend, False, response_time)

                self.logger.warning(f"Backend {backend} failed: {str(e)}")

                if i == len(backends) - 1:
                    # Last backend, no more failovers
                    return {
                        'success': False,
                        'error': str(e),
                        'backend_used': backend,
                        'failover_occurred': True,
                        'attempts': i + 1
                    }

        return {
            'success': False,
            'error': 'No available backends',
            'backend_used': None,
            'failover_occurred': False,
            'attempts': 0
        }

    def _progressive_failover(
        self,
        backends: List[str],
        operation: Callable[[str], Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Progressive failover with retry on each backend"""
        original_backend = backends[0] if backends else None

        for i, backend in enumerate(backends):
            if not self._is_backend_available(backend):
                continue

            # Try each backend with retries
            for attempt in range(self.max_retries):
                try:
                    start_time = time.time()
                    self.load_balancer.start_request(backend)

                    result = operation(backend)

                    response_time = (time.time() - start_time) * 1000
                    self.load_balancer.end_request(backend, True, response_time)

                    if i > 0 or attempt > 0:
                        self._record_failover(
                            original_backend,
                            backend,
                            f"progressive_failover_attempt_{attempt}",
                            True,
                            context
                        )

                    return {
                        'success': True,
                        'result': result,
                        'backend_used': backend,
                        'failover_occurred': i > 0,
                        'attempts': i * self.max_retries + attempt + 1,
                        'retries': attempt
                    }

                except Exception as e:
                    response_time = (time.time() - start_time) * 1000
                    self.load_balancer.end_request(backend, False, response_time)

                    self.logger.warning(
                        f"Backend {backend} attempt {attempt + 1} failed: {str(e)}"
                    )

                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay_seconds)

            # Backend exhausted, try next

        return {
            'success': False,
            'error': 'All backends exhausted',
            'backend_used': backends[-1] if backends else None,
            'failover_occurred': True,
            'attempts': len(backends) * self.max_retries
        }

    def _circuit_breaker_failover(
        self,
        backends: List[str],
        operation: Callable[[str], Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Failover with circuit breaker pattern"""
        for i, backend in enumerate(backends):
            # Check circuit breaker
            if self._is_circuit_open(backend):
                self.logger.info(f"Circuit breaker open for {backend}, skipping")
                continue

            if not self._is_backend_available(backend):
                continue

            try:
                start_time = time.time()
                self.load_balancer.start_request(backend)

                result = operation(backend)

                response_time = (time.time() - start_time) * 1000
                self.load_balancer.end_request(backend, True, response_time)

                # Reset circuit breaker on success
                self._reset_circuit(backend)

                if i > 0:
                    self._record_failover(
                        backends[0],
                        backend,
                        "circuit_breaker_failover",
                        True,
                        context
                    )

                return {
                    'success': True,
                    'result': result,
                    'backend_used': backend,
                    'failover_occurred': i > 0,
                    'attempts': i + 1
                }

            except Exception as e:
                response_time = (time.time() - start_time) * 1000
                self.load_balancer.end_request(backend, False, response_time)

                # Increment circuit breaker failure count
                self._record_circuit_failure(backend)

                self.logger.warning(f"Backend {backend} failed: {str(e)}")

        return {
            'success': False,
            'error': 'All backends failed or circuits open',
            'backend_used': None,
            'failover_occurred': True,
            'attempts': len(backends)
        }

    def _retry_then_failover(
        self,
        backends: List[str],
        operation: Callable[[str], Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Retry on primary, then failover"""
        if not backends:
            return {
                'success': False,
                'error': 'No backends provided',
                'backend_used': None,
                'failover_occurred': False,
                'attempts': 0
            }

        primary = backends[0]
        fallbacks = backends[1:]

        # Try primary with retries
        for attempt in range(self.max_retries):
            if not self._is_backend_available(primary):
                break

            try:
                start_time = time.time()
                self.load_balancer.start_request(primary)

                result = operation(primary)

                response_time = (time.time() - start_time) * 1000
                self.load_balancer.end_request(primary, True, response_time)

                return {
                    'success': True,
                    'result': result,
                    'backend_used': primary,
                    'failover_occurred': False,
                    'attempts': attempt + 1,
                    'retries': attempt
                }

            except Exception as e:
                response_time = (time.time() - start_time) * 1000
                self.load_balancer.end_request(primary, False, response_time)

                self.logger.warning(
                    f"Primary backend {primary} attempt {attempt + 1} failed: {str(e)}"
                )

                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay_seconds)

        # Primary exhausted, try fallbacks
        for backend in fallbacks:
            if not self._is_backend_available(backend):
                continue

            try:
                start_time = time.time()
                self.load_balancer.start_request(backend)

                result = operation(backend)

                response_time = (time.time() - start_time) * 1000
                self.load_balancer.end_request(backend, True, response_time)

                self._record_failover(
                    primary,
                    backend,
                    "retry_exhausted_failover",
                    True,
                    context
                )

                return {
                    'success': True,
                    'result': result,
                    'backend_used': backend,
                    'failover_occurred': True,
                    'attempts': self.max_retries + 1,
                    'primary_retries': self.max_retries
                }

            except Exception as e:
                response_time = (time.time() - start_time) * 1000
                self.load_balancer.end_request(backend, False, response_time)

                self.logger.warning(f"Fallback backend {backend} failed: {str(e)}")

        return {
            'success': False,
            'error': 'Primary and all fallbacks failed',
            'backend_used': None,
            'failover_occurred': True,
            'attempts': self.max_retries + len(fallbacks)
        }

    def _is_backend_available(self, backend_name: str) -> bool:
        """Check if backend is available for use"""
        # Check health status
        if not self.health_monitor.is_backend_available(backend_name):
            return False

        # Check circuit breaker
        if self._is_circuit_open(backend_name):
            return False

        return True

    def _is_circuit_open(self, backend_name: str) -> bool:
        """Check if circuit breaker is open for backend"""
        if backend_name not in self._circuit_breakers:
            return False

        open_time, failure_count = self._circuit_breakers[backend_name]

        # Check if timeout expired
        if datetime.now() - open_time > timedelta(seconds=self.circuit_breaker_timeout):
            # Timeout expired, reset
            del self._circuit_breakers[backend_name]
            return False

        return failure_count >= self.circuit_breaker_threshold

    def _record_circuit_failure(self, backend_name: str):
        """Record a circuit breaker failure"""
        if backend_name not in self._circuit_breakers:
            self._circuit_breakers[backend_name] = (datetime.now(), 1)
        else:
            open_time, count = self._circuit_breakers[backend_name]
            self._circuit_breakers[backend_name] = (open_time, count + 1)

            if count + 1 >= self.circuit_breaker_threshold:
                self.logger.warning(
                    f"Circuit breaker opened for {backend_name} "
                    f"({count + 1} failures)"
                )

    def _reset_circuit(self, backend_name: str):
        """Reset circuit breaker for backend"""
        if backend_name in self._circuit_breakers:
            del self._circuit_breakers[backend_name]
            self.logger.info(f"Circuit breaker reset for {backend_name}")

    def _record_failover(
        self,
        original: str,
        failover: str,
        reason: str,
        success: bool,
        metadata: Dict[str, Any]
    ):
        """Record a failover event"""
        event = FailoverEvent(
            timestamp=datetime.now(),
            original_backend=original,
            failover_backend=failover,
            reason=reason,
            success=success,
            metadata=metadata
        )

        self._failover_history.append(event)

        self.logger.info(
            f"Failover from {original} to {failover}: {reason}, "
            f"success={success}"
        )

    def get_failover_stats(self) -> Dict[str, Any]:
        """Get failover statistics"""
        total_failovers = len(self._failover_history)
        successful_failovers = sum(1 for e in self._failover_history if e.success)

        # Circuit breaker status
        open_circuits = [
            name for name, (_, count) in self._circuit_breakers.items()
            if count >= self.circuit_breaker_threshold
        ]

        return {
            'total_failovers': total_failovers,
            'successful_failovers': successful_failovers,
            'failover_success_rate': successful_failovers / total_failovers if total_failovers > 0 else 0,
            'open_circuit_breakers': open_circuits,
            'recent_failovers': [
                {
                    'timestamp': e.timestamp.isoformat(),
                    'from': e.original_backend,
                    'to': e.failover_backend,
                    'reason': e.reason,
                    'success': e.success
                }
                for e in list(self._failover_history)[-10:]
            ]
        }

    def configure_failover_chain(
        self,
        backend_name: str,
        fallbacks: List[str]
    ):
        """Configure failover chain for a backend"""
        self._failover_chains[backend_name] = fallbacks
        self.logger.info(
            f"Configured failover chain for {backend_name}: {' -> '.join(fallbacks)}"
        )

    def get_failover_chain(self, backend_name: str) -> List[str]:
        """Get configured failover chain for backend"""
        return self._failover_chains.get(backend_name, [])
