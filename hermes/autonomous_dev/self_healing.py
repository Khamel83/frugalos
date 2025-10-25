"""
Self-Healing System
Automatic detection and recovery from system failures
"""

import logging
import time
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque

from ..config import Config
from ..database import Database
from ..logger import get_logger

logger = get_logger('autonomous_dev.self_healing')

class HealingType(Enum):
    """Types of self-healing actions"""
    RETRY = "retry"
    RESTART_COMPONENT = "restart_component"
    FALLBACK_SWITCH = "fallback_switch"
    CACHE_REBUILD = "cache_rebuild"
    DATABASE_REPAIR = "database_repair"
    CONFIG_RESTORE = "config_restore"
    RESOURCE_SCALE = "resource_scale"

class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"

@dataclass
class HealthCheck:
    """Health check definition"""
    name: str
    component: str
    check_function: Callable[[], Dict[str, Any]]
    interval_seconds: int
    failure_threshold: int
    healing_type: HealingType
    healing_actions: List[Callable[[], bool]]
    timeout_seconds: int

@dataclass
class HealingEvent:
    """A healing event"""
    event_id: str
    health_check: HealthCheck
    status: HealthStatus
    detected_at: datetime
    healing_actions_attempted: List[str]
    healing_actions_succeeded: List[str]
    resolution_time: Optional[datetime]
    success: bool

class SelfHealingSystem:
    """Self-healing system for automatic recovery"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.logger = get_logger('self_healing')

        # Configuration
        self.enabled = self.config.get('autonomous_dev.self_healing.enabled', True)
        self.max_concurrent_healings = self.config.get('autonomous_dev.self_healing.max_concurrent', 3)
        self.default_timeout = self.config.get('autonomous_dev.self_healing.default_timeout', 60)

        # Healing state
        self._health_checks = {}  # name -> HealthCheck
        self._health_status = defaultdict(lambda: HealthStatus.HEALTHY)
        self._failure_counts = defaultdict(int)
        self._healing_events = deque(maxlen=1000)
        self._active_healings = set()

        # Monitoring thread
        self._monitoring_thread = None
        self._running = False

        # Initialize health checks
        self._initialize_health_checks()

    def _initialize_health_checks(self):
        """Initialize default health checks"""
        # Database health check
        self.register_health_check(HealthCheck(
            name="database_connection",
            component="database",
            check_function=self._check_database_health,
            interval_seconds=30,
            failure_threshold=3,
            healing_type=HealingType.DATABASE_REPAIR,
            healing_actions=[self._heal_database_connection],
            timeout_seconds=10
        ))

        # Job queue health check
        self.register_health_check(HealthCheck(
            name="job_queue",
            component="job_queue",
            check_function=self._check_job_queue_health,
            interval_seconds=60,
            failure_threshold=5,
            healing_type=HealingType.RESTART_COMPONENT,
            healing_actions=[self._heal_job_queue],
            timeout_seconds=15
        ))

        # Backend health check
        self.register_health_check(HealthCheck(
            name="backend_availability",
            component="backends",
            check_function=self._check_backend_health,
            interval_seconds=45,
            failure_threshold=3,
            healing_type=HealingType.FALLBACK_SWITCH,
            healing_actions=[self._heal_backend_failover],
            timeout_seconds=20
        ))

        # Cache health check
        self.register_health_check(HealthCheck(
            name="cache_system",
            component="cache",
            check_function=self._check_cache_health,
            interval_seconds=120,
            failure_threshold=2,
            healing_type=HealingType.CACHE_REBUILD,
            healing_actions=[self._heal_cache_rebuild],
            timeout_seconds=30
        ))

        # Memory usage check
        self.register_health_check(HealthCheck(
            name="memory_usage",
            component="system",
            check_function=self._check_memory_health,
            interval_seconds=60,
            failure_threshold=2,
            healing_type=HealingType.RESOURCE_SCALE,
            healing_actions=[self._heal_memory_pressure],
            timeout_seconds=10
        ))

    def register_health_check(self, health_check: HealthCheck):
        """Register a new health check"""
        self._health_checks[health_check.name] = health_check
        self.logger.info(f"Registered health check: {health_check.name}")

    def start_monitoring(self):
        """Start health monitoring and self-healing"""
        if not self.enabled:
            self.logger.info("Self-healing system is disabled")
            return

        if self._running:
            self.logger.warning("Self-healing monitoring already running")
            return

        self._running = True
        self._monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitoring_thread.start()
        self.logger.info("Self-healing monitoring started")

    def stop_monitoring(self):
        """Stop health monitoring"""
        self._running = False
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=10)
        self.logger.info("Self-healing monitoring stopped")

    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self._running:
            try:
                self._run_health_checks()
                time.sleep(10)  # Check every 10 seconds
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(30)  # Wait longer on error

    def _run_health_checks(self):
        """Run all health checks"""
        for check_name, health_check in self._health_checks.items():
            if self._is_check_due(check_name, health_check):
                self._run_health_check(health_check)

    def _is_check_due(self, check_name: str, health_check: HealthCheck) -> bool:
        """Check if health check is due to run"""
        # For now, simple time-based check
        # In production, would track last run time per check
        return True

    def _run_health_check(self, health_check: HealthCheck):
        """Run a single health check"""
        try:
            start_time = time.time()
            result = health_check.check_function()
            execution_time = time.time() - start_time

            # Check if check completed successfully
            if execution_time > health_check.timeout_seconds:
                self._handle_health_check_failure(health_check, "timeout")
                return

            # Parse health status
            status = HealthStatus.HEALTHY
            if not result.get('healthy', True):
                if result.get('severity') == 'critical':
                    status = HealthStatus.CRITICAL
                elif result.get('severity') == 'degraded':
                    status = HealthStatus.DEGRADED
                else:
                    status = HealthStatus.UNHEALTHY

            # Update status
            previous_status = self._health_status[health_check.name]
            self._health_status[health_check.name] = status

            if status == HealthStatus.HEALTHY:
                self._failure_counts[health_check.name] = 0
            else:
                self._failure_counts[health_check.name] += 1

                # Check if healing is needed
                if self._failure_counts[health_check.name] >= health_check.failure_threshold:
                    self._trigger_healing(health_check, status)

            self.logger.debug(
                f"Health check {health_check.name}: {status.value} "
                f"(execution_time: {execution_time:.2f}s)"
            )

        except Exception as e:
            self.logger.error(f"Error running health check {health_check.name}: {e}")
            self._handle_health_check_failure(health_check, str(e))

    def _handle_health_check_failure(self, health_check: HealthCheck, error: str):
        """Handle health check execution failure"""
        self._failure_counts[health_check.name] += 1
        self._health_status[health_check.name] = HealthStatus.UNHEALTHY

        if self._failure_counts[health_check.name] >= health_check.failure_threshold:
            self._trigger_healing(health_check, HealthStatus.UNHEALTHY)

    def _trigger_healing(self, health_check: HealthCheck, status: HealthStatus):
        """Trigger healing actions for a failed health check"""
        if len(self._active_healings) >= self.max_concurrent_healings:
            self.logger.warning(f"Max concurrent healings reached, skipping {health_check.name}")
            return

        if health_check.name in self._active_healings:
            self.logger.warning(f"Healing already in progress for {health_check.name}")
            return

        # Create healing event
        healing_event = HealingEvent(
            event_id=self._generate_event_id(),
            health_check=health_check,
            status=status,
            detected_at=datetime.now(),
            healing_actions_attempted=[],
            healing_actions_succeeded=[],
            resolution_time=None,
            success=False
        )

        self._active_healings.add(health_check.name)
        self._healing_events.append(healing_event)

        self.logger.warning(
            f"Triggering healing for {health_check.name}: {status.value} "
            f"(failures: {self._failure_counts[health_check.name]})"
        )

        # Execute healing actions
        self._execute_healing_actions(healing_event)

    def _execute_healing_actions(self, healing_event: HealingEvent):
        """Execute healing actions"""
        health_check = healing_event.health_check
        success = False

        for action in health_check.healing_actions:
            action_name = action.__name__ if hasattr(action, '__name__') else str(action)
            healing_event.healing_actions_attempted.append(action_name)

            try:
                start_time = time.time()
                action_success = action()
                execution_time = time.time() - start_time

                if execution_time > health_check.timeout_seconds:
                    self.logger.warning(f"Healing action {action_name} timed out")
                    continue

                if action_success:
                    healing_event.healing_actions_succeeded.append(action_name)
                    self.logger.info(f"Healing action {action_name} succeeded")
                    success = True
                else:
                    self.logger.warning(f"Healing action {action_name} failed")

            except Exception as e:
                self.logger.error(f"Error executing healing action {action_name}: {e}")

        # Update healing event
        healing_event.resolution_time = datetime.now()
        healing_event.success = success

        if success:
            # Reset failure count on successful healing
            self._failure_counts[health_check.name] = 0
            self._health_status[health_check.name] = HealthStatus.HEALTHY
            self.logger.info(f"Successfully healed {health_check.name}")
        else:
            self._health_status[health_check.name] = HealthStatus.CRITICAL
            self.logger.error(f"Failed to heal {health_check.name}")

        # Remove from active healings
        self._active_healings.discard(health_check.name)

        # Store healing event
        self._store_healing_event(healing_event)

    # Health check implementations
    def _check_database_health(self) -> Dict[str, Any]:
        """Check database health"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("SELECT 1")
                cursor.fetchone()

            return {'healthy': True, 'message': 'Database connection OK'}

        except Exception as e:
            return {
                'healthy': False,
                'severity': 'critical',
                'message': f'Database connection failed: {str(e)}'
            }

    def _check_job_queue_health(self) -> Dict[str, Any]:
        """Check job queue health"""
        try:
            # Check if job queue is accessible
            from ..queue import JobQueue
            queue = JobQueue(self.config)

            status = queue.get_queue_status()

            if status['queue_size'] > 1000:
                return {
                    'healthy': False,
                    'severity': 'degraded',
                    'message': f'Job queue size too large: {status["queue_size"]}'
                }

            if status['running_tasks'] > 50:
                return {
                    'healthy': False,
                    'severity': 'degraded',
                    'message': f'Too many running tasks: {status["running_tasks"]}'
                }

            return {'healthy': True, 'message': 'Job queue OK'}

        except Exception as e:
            return {
                'healthy': False,
                'severity': 'critical',
                'message': f'Job queue check failed: {str(e)}'
            }

    def _check_backend_health(self) -> Dict[str, Any]:
        """Check backend health"""
        try:
            from ..backends.health_monitor import get_health_monitor
            monitor = get_health_monitor(self.config)

            health_summary = monitor.get_health_summary()
            total_backends = health_summary['total_backends']
            healthy_backends = health_summary['healthy']

            if total_backends == 0:
                return {
                    'healthy': False,
                    'severity': 'critical',
                    'message': 'No backends configured'
                }

            if healthy_backends == 0:
                return {
                    'healthy': False,
                    'severity': 'critical',
                    'message': 'No healthy backends available'
                }

            if healthy_backends < total_backends * 0.5:
                return {
                    'healthy': False,
                    'severity': 'degraded',
                    'message': f'Less than 50% backends healthy: {healthy_backends}/{total_backends}'
                }

            return {
                'healthy': True,
                'message': f'{healthy_backends}/{total_backends} backends healthy'
            }

        except Exception as e:
            return {
                'healthy': False,
                'severity': 'critical',
                'message': f'Backend health check failed: {str(e)}'
            }

    def _check_cache_health(self) -> Dict[str, Any]:
        """Check cache system health"""
        try:
            from ..cache.cache_manager import CacheManager
            cache = CacheManager(self.config)

            stats = cache.get_stats()

            if stats.hit_rate < 0.3 and stats.total_entries > 0:
                return {
                    'healthy': False,
                    'severity': 'degraded',
                    'message': f'Low cache hit rate: {stats.hit_rate:.2%}'
                }

            if stats.total_entries > 0 and stats.eviction_count > stats.total_entries * 0.5:
                return {
                    'healthy': False,
                    'severity': 'degraded',
                    'message': f'High eviction rate: {stats.eviction_count} evictions'
                }

            return {'healthy': True, 'message': 'Cache system OK'}

        except Exception as e:
            return {
                'healthy': False,
                'severity': 'critical',
                'message': f'Cache health check failed: {str(e)}'
            }

    def _check_memory_health(self) -> Dict[str, Any]:
        """Check memory usage"""
        try:
            import psutil
            memory = psutil.virtual_memory()

            memory_usage_percent = memory.percent

            if memory_usage_percent > 90:
                return {
                    'healthy': False,
                    'severity': 'critical',
                    'message': f'High memory usage: {memory_usage_percent:.1f}%'
                }

            if memory_usage_percent > 80:
                return {
                    'healthy': False,
                    'severity': 'degraded',
                    'message': f'Elevated memory usage: {memory_usage_percent:.1f}%'
                }

            return {
                'healthy': True,
                'message': f'Memory usage OK: {memory_usage_percent:.1f}%'
            }

        except Exception as e:
            return {
                'healthy': False,
                'severity': 'degraded',
                'message': f'Memory check failed: {str(e)}'
            }

    # Healing action implementations
    def _heal_database_connection(self) -> bool:
        """Attempt to heal database connection"""
        try:
            # Test and recreate database connection
            self.db.initialize()
            return True
        except Exception as e:
            self.logger.error(f"Failed to heal database connection: {e}")
            return False

    def _heal_job_queue(self) -> bool:
        """Attempt to heal job queue"""
        try:
            # Reset job queue state
            from ..queue import JobQueue
            queue = JobQueue(self.config)

            # Check if queue needs restart
            if hasattr(queue, 'restart'):
                queue.restart()
                return True

            return False
        except Exception as e:
            self.logger.error(f"Failed to heal job queue: {e}")
            return False

    def _heal_backend_failover(self) -> bool:
        """Attempt to heal backend issues with failover"""
        try:
            # Trigger backend health check and failover
            from ..backends.health_monitor import get_health_monitor
            monitor = get_health_monitor(self.config)

            # Force health check
            for backend_name in monitor.get_all_health_status().keys():
                if not monitor.is_backend_available(backend_name):
                    monitor.reset_backend_health(backend_name)

            return True
        except Exception as e:
            self.logger.error(f"Failed to heal backend failover: {e}")
            return False

    def _heal_cache_rebuild(self) -> bool:
        """Attempt to rebuild cache"""
        try:
            from ..cache.cache_manager import CacheManager
            cache = CacheManager(self.config)

            # Clear and rebuild cache
            cache.clear()
            return True
        except Exception as e:
            self.logger.error(f"Failed to rebuild cache: {e}")
            return False

    def _heal_memory_pressure(self) -> bool:
        """Attempt to relieve memory pressure"""
        try:
            import gc
            # Force garbage collection
            gc.collect()

            # Clear cache if possible
            try:
                from ..cache.cache_manager import CacheManager
                cache = CacheManager(self.config)
                cache.clear()
            except:
                pass

            return True
        except Exception as e:
            self.logger.error(f"Failed to heal memory pressure: {e}")
            return False

    def _store_healing_event(self, event: HealingEvent):
        """Store healing event in database"""
        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO healing_events (
                        event_id, health_check_name, status, detected_at, resolved_at,
                        actions_attempted, actions_succeeded, success
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.event_id,
                    event.health_check.name,
                    event.status.value,
                    event.detected_at.isoformat(),
                    event.resolution_time.isoformat() if event.resolution_time else None,
                    ','.join(event.healing_actions_attempted),
                    ','.join(event.healing_actions_succeeded),
                    int(event.success)
                ))
                conn.commit()

        except Exception as e:
            self.logger.error(f"Error storing healing event: {e}")

    def _generate_event_id(self) -> str:
        """Generate unique event ID"""
        return f"healing_{int(time.time() * 1000)}_{hash(time.time()) % 10000}"

    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status"""
        status_by_component = {}

        for check_name, health_check in self._health_checks.items():
            component = health_check.component
            if component not in status_by_component:
                status_by_component[component] = []

            status_by_component[component].append({
                'name': check_name,
                'status': self._health_status[check_name].value,
                'failure_count': self._failure_counts[check_name],
                'last_check': datetime.now().isoformat()
            })

        overall_status = HealthStatus.HEALTHY
        for status in self._health_status.values():
            if status == HealthStatus.CRITICAL:
                overall_status = HealthStatus.CRITICAL
                break
            elif status == HealthStatus.UNHEALTHY and overall_status != HealthStatus.CRITICAL:
                overall_status = HealthStatus.UNHEALTHY
            elif status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                overall_status = HealthStatus.DEGRADED

        return {
            'overall_status': overall_status.value,
            'components': status_by_component,
            'active_healings': len(self._active_healings),
            'total_checks': len(self._health_checks)
        }

    def get_healing_stats(self) -> Dict[str, Any]:
        """Get healing statistics"""
        total_events = len(self._healing_events)
        successful_events = sum(1 for event in self._healing_events if event.success)

        return {
            'total_healing_events': total_events,
            'successful_healings': successful_events,
            'success_rate': successful_events / total_events if total_events > 0 else 0,
            'active_healings': len(self._active_healings),
            'health_checks_count': len(self._health_checks),
            'unhealthy_components': len([
                name for name, status in self._health_status.items()
                if status != HealthStatus.HEALTHY
            ])
        }