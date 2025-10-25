"""
Backend Health Monitoring
Real-time health tracking and status monitoring for all backends
"""

import logging
import time
import threading
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from collections import deque

from ..config import Config
from ..database import Database
from ..logger import get_logger

logger = get_logger('backends.health_monitor')

class HealthStatus(Enum):
    """Backend health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"
    UNKNOWN = "unknown"

@dataclass
class BackendHealth:
    """Health status for a backend"""
    backend_name: str
    status: HealthStatus
    response_time_ms: float
    success_rate: float
    error_count: int
    last_check: datetime
    consecutive_failures: int
    uptime_percentage: float
    metadata: Dict[str, Any]

class BackendHealthMonitor:
    """Monitors health of all backends"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.logger = get_logger('health_monitor')

        # Health check configuration
        self.check_interval = self.config.get('backends.health_check_interval', 30)
        self.timeout_seconds = self.config.get('backends.health_check_timeout', 5)
        self.failure_threshold = self.config.get('backends.failure_threshold', 3)

        # Health state tracking
        self._health_state = {}  # backend_name -> BackendHealth
        self._response_times = {}  # backend_name -> deque of recent response times
        self._check_history = {}  # backend_name -> deque of recent check results

        # Monitoring thread
        self._running = False
        self._monitor_thread = None

        # Load initial backend list
        self._load_backends()

    def _load_backends(self):
        """Load configured backends"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT name, type, status FROM backends
                    WHERE status = 'active'
                """)

                for row in cursor.fetchall():
                    backend_name = row['name']
                    if backend_name not in self._health_state:
                        self._health_state[backend_name] = BackendHealth(
                            backend_name=backend_name,
                            status=HealthStatus.UNKNOWN,
                            response_time_ms=0.0,
                            success_rate=1.0,
                            error_count=0,
                            last_check=datetime.now(),
                            consecutive_failures=0,
                            uptime_percentage=0.0,
                            metadata={'type': row['type']}
                        )
                        self._response_times[backend_name] = deque(maxlen=100)
                        self._check_history[backend_name] = deque(maxlen=100)

            self.logger.info(f"Loaded {len(self._health_state)} backends for monitoring")

        except Exception as e:
            self.logger.error(f"Error loading backends: {e}")

    def start_monitoring(self):
        """Start background health monitoring"""
        if self._running:
            self.logger.warning("Health monitoring already running")
            return

        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        self.logger.info("Backend health monitoring started")

    def stop_monitoring(self):
        """Stop background health monitoring"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        self.logger.info("Backend health monitoring stopped")

    def _monitor_loop(self):
        """Main monitoring loop"""
        while self._running:
            try:
                self._check_all_backends()
                time.sleep(self.check_interval)
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.check_interval)

    def _check_all_backends(self):
        """Check health of all backends"""
        for backend_name in list(self._health_state.keys()):
            try:
                self._check_backend(backend_name)
            except Exception as e:
                self.logger.error(f"Error checking backend {backend_name}: {e}")

    def _check_backend(self, backend_name: str):
        """Check health of a specific backend"""
        start_time = time.time()
        health = self._health_state.get(backend_name)

        if not health:
            return

        try:
            # Perform health check
            check_result = self._perform_health_check(backend_name, health.metadata.get('type'))

            # Record response time
            response_time = (time.time() - start_time) * 1000
            self._response_times[backend_name].append(response_time)
            self._check_history[backend_name].append(check_result)

            # Update health state
            if check_result:
                # Successful check
                health.consecutive_failures = 0
                health.status = HealthStatus.HEALTHY if response_time < 1000 else HealthStatus.DEGRADED
                health.response_time_ms = sum(self._response_times[backend_name]) / len(self._response_times[backend_name])
            else:
                # Failed check
                health.consecutive_failures += 1
                health.error_count += 1

                if health.consecutive_failures >= self.failure_threshold:
                    health.status = HealthStatus.UNHEALTHY
                else:
                    health.status = HealthStatus.DEGRADED

            # Update success rate
            recent_checks = list(self._check_history[backend_name])
            health.success_rate = sum(recent_checks) / len(recent_checks) if recent_checks else 0.0

            # Update uptime percentage
            health.uptime_percentage = self._calculate_uptime(backend_name)

            health.last_check = datetime.now()

            # Log if status changed
            self.logger.debug(
                f"Backend {backend_name}: {health.status.value}, "
                f"response: {health.response_time_ms:.1f}ms, "
                f"success rate: {health.success_rate:.1%}"
            )

        except Exception as e:
            self.logger.error(f"Error checking backend {backend_name}: {e}")
            health.consecutive_failures += 1
            health.status = HealthStatus.OFFLINE

    def _perform_health_check(self, backend_name: str, backend_type: str) -> bool:
        """
        Perform actual health check on backend

        Args:
            backend_name: Name of backend
            backend_type: Type of backend (ollama, openrouter, etc.)

        Returns:
            True if healthy, False otherwise
        """
        try:
            if backend_name.startswith('ollama:'):
                # Check Ollama availability
                return self._check_ollama_health(backend_name)
            elif backend_name.startswith('openrouter:'):
                # Check OpenRouter availability
                return self._check_openrouter_health(backend_name)
            else:
                # Generic health check - just check if backend is in database
                return True

        except Exception as e:
            self.logger.error(f"Health check failed for {backend_name}: {e}")
            return False

    def _check_ollama_health(self, backend_name: str) -> bool:
        """Check Ollama backend health"""
        try:
            # Try to import and test Ollama
            import subprocess
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                timeout=self.timeout_seconds
            )
            return result.returncode == 0
        except Exception as e:
            self.logger.debug(f"Ollama health check failed: {e}")
            return False

    def _check_openrouter_health(self, backend_name: str) -> bool:
        """Check OpenRouter backend health"""
        # For now, assume OpenRouter is healthy if API key is configured
        # In production, this would make an actual API call
        api_key = self.config.get('openrouter.api_key')
        return api_key is not None and len(api_key) > 0

    def _calculate_uptime(self, backend_name: str) -> float:
        """Calculate uptime percentage over recent history"""
        if backend_name not in self._check_history:
            return 0.0

        checks = list(self._check_history[backend_name])
        if not checks:
            return 0.0

        return sum(checks) / len(checks)

    def get_backend_health(self, backend_name: str) -> Optional[BackendHealth]:
        """Get current health status for a backend"""
        return self._health_state.get(backend_name)

    def get_all_health_status(self) -> Dict[str, BackendHealth]:
        """Get health status for all backends"""
        return dict(self._health_state)

    def get_healthy_backends(self) -> List[str]:
        """Get list of currently healthy backends"""
        return [
            name for name, health in self._health_state.items()
            if health.status == HealthStatus.HEALTHY
        ]

    def get_degraded_backends(self) -> List[str]:
        """Get list of degraded backends"""
        return [
            name for name, health in self._health_state.items()
            if health.status == HealthStatus.DEGRADED
        ]

    def get_unhealthy_backends(self) -> List[str]:
        """Get list of unhealthy backends"""
        return [
            name for name, health in self._health_state.items()
            if health.status in [HealthStatus.UNHEALTHY, HealthStatus.OFFLINE]
        ]

    def is_backend_available(self, backend_name: str) -> bool:
        """Check if backend is available for use"""
        health = self._health_state.get(backend_name)
        if not health:
            return False

        return health.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]

    def get_fastest_backend(self, backend_list: List[str] = None) -> Optional[str]:
        """Get fastest available backend from list"""
        if backend_list is None:
            backend_list = list(self._health_state.keys())

        available = [
            (name, self._health_state[name].response_time_ms)
            for name in backend_list
            if self.is_backend_available(name)
        ]

        if not available:
            return None

        # Return backend with lowest response time
        return min(available, key=lambda x: x[1])[0]

    def get_health_summary(self) -> Dict[str, Any]:
        """Get summary of backend health"""
        healthy_count = len(self.get_healthy_backends())
        degraded_count = len(self.get_degraded_backends())
        unhealthy_count = len(self.get_unhealthy_backends())
        total = len(self._health_state)

        return {
            'total_backends': total,
            'healthy': healthy_count,
            'degraded': degraded_count,
            'unhealthy': unhealthy_count,
            'health_percentage': healthy_count / total if total > 0 else 0.0,
            'backends': {
                name: {
                    'status': health.status.value,
                    'response_time_ms': health.response_time_ms,
                    'success_rate': health.success_rate,
                    'uptime': health.uptime_percentage
                }
                for name, health in self._health_state.items()
            }
        }

    def record_backend_usage(
        self,
        backend_name: str,
        success: bool,
        response_time_ms: float
    ):
        """Record backend usage for health tracking"""
        if backend_name not in self._health_state:
            return

        health = self._health_state[backend_name]

        # Update response times
        self._response_times[backend_name].append(response_time_ms)
        health.response_time_ms = sum(self._response_times[backend_name]) / len(self._response_times[backend_name])

        # Update success tracking
        self._check_history[backend_name].append(success)

        if not success:
            health.error_count += 1
            health.consecutive_failures += 1
        else:
            health.consecutive_failures = 0

        # Update success rate
        recent_checks = list(self._check_history[backend_name])
        health.success_rate = sum(recent_checks) / len(recent_checks) if recent_checks else 0.0

        # Update status based on recent usage
        if health.consecutive_failures >= self.failure_threshold:
            health.status = HealthStatus.UNHEALTHY
        elif health.success_rate < 0.5:
            health.status = HealthStatus.DEGRADED
        elif response_time_ms > 2000:
            health.status = HealthStatus.DEGRADED
        else:
            health.status = HealthStatus.HEALTHY

    def reset_backend_health(self, backend_name: str):
        """Reset health tracking for a backend"""
        if backend_name in self._health_state:
            self._response_times[backend_name].clear()
            self._check_history[backend_name].clear()
            health = self._health_state[backend_name]
            health.consecutive_failures = 0
            health.error_count = 0
            health.status = HealthStatus.UNKNOWN
            self.logger.info(f"Reset health tracking for backend {backend_name}")
