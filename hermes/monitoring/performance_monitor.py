"""
Performance monitoring and profiling module for the Hermes AI Assistant.

This module provides comprehensive performance monitoring, profiling, and
optimization capabilities for production environments.
"""

import asyncio
import time
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
from contextlib import asynccontextmanager
import functools
import json
import logging
from pathlib import Path

import redis.asyncio as redis
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import memory_profiler
import pyroscope

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Individual performance metric data point."""
    name: str
    value: float
    unit: str
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceSnapshot:
    """Snapshot of system performance at a point in time."""
    timestamp: datetime
    cpu_percent: float
    memory_usage_mb: float
    memory_percent: float
    disk_usage_percent: float
    network_io: Dict[str, int]
    process_count: int
    load_average: List[float]
    custom_metrics: List[PerformanceMetric] = field(default_factory=list)


class PerformanceCollector:
    """Collects system and application performance metrics."""

    def __init__(self, collection_interval: int = 30):
        self.collection_interval = collection_interval
        self.metrics_history: deque = deque(maxlen=1440)  # 24 hours at 30s intervals
        self.custom_collectors: Dict[str, Callable] = {}
        self.is_collecting = False
        self._collection_task: Optional[asyncio.Task] = None

        # Prometheus metrics
        self.prom_cpu_usage = Gauge('hermes_cpu_usage_percent', 'CPU usage percentage')
        self.prom_memory_usage = Gauge('hermes_memory_usage_mb', 'Memory usage in MB')
        self.prom_memory_percent = Gauge('hermes_memory_percent', 'Memory usage percentage')
        self.prom_disk_usage = Gauge('hermes_disk_usage_percent', 'Disk usage percentage')
        self.prom_network_bytes_sent = Counter('hermes_network_bytes_sent_total', 'Total bytes sent')
        self.prom_network_bytes_recv = Counter('hermes_network_bytes_recv_total', 'Total bytes received')

    async def start_collection(self):
        """Start continuous metric collection."""
        if self.is_collecting:
            return

        self.is_collecting = True
        self._collection_task = asyncio.create_task(self._collect_loop())
        logger.info("Started performance collection")

    async def stop_collection(self):
        """Stop metric collection."""
        self.is_collecting = False
        if self._collection_task:
            self._collection_task.cancel()
            try:
                await self._collection_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped performance collection")

    async def _collect_loop(self):
        """Main collection loop."""
        while self.is_collecting:
            try:
                snapshot = await self.collect_snapshot()
                self.metrics_history.append(snapshot)
                await self._update_prometheus_metrics(snapshot)
            except Exception as e:
                logger.error(f"Error collecting performance metrics: {e}")
            await asyncio.sleep(self.collection_interval)

    async def collect_snapshot(self) -> PerformanceSnapshot:
        """Collect current performance snapshot."""
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        network = psutil.net_io_counters()
        process_count = len(psutil.pids())

        # Load average (Unix systems)
        try:
            load_avg = list(psutil.getloadavg())
        except (AttributeError, OSError):
            load_avg = [0.0, 0.0, 0.0]

        # Custom metrics
        custom_metrics = []
        for name, collector in self.custom_collectors.items():
            try:
                metrics = await collector()
                if isinstance(metrics, list):
                    custom_metrics.extend(metrics)
                else:
                    custom_metrics.append(metrics)
            except Exception as e:
                logger.error(f"Error collecting custom metric {name}: {e}")

        return PerformanceSnapshot(
            timestamp=datetime.utcnow(),
            cpu_percent=cpu_percent,
            memory_usage_mb=memory.used / 1024 / 1024,
            memory_percent=memory.percent,
            disk_usage_percent=disk.percent,
            network_io={
                'bytes_sent': network.bytes_sent,
                'bytes_recv': network.bytes_recv,
                'packets_sent': network.packets_sent,
                'packets_recv': network.packets_recv
            },
            process_count=process_count,
            load_average=load_avg,
            custom_metrics=custom_metrics
        )

    async def _update_prometheus_metrics(self, snapshot: PerformanceSnapshot):
        """Update Prometheus metrics."""
        self.prom_cpu_usage.set(snapshot.cpu_percent)
        self.prom_memory_usage.set(snapshot.memory_usage_mb)
        self.prom_memory_percent.set(snapshot.memory_percent)
        self.prom_disk_usage.set(snapshot.disk_usage_percent)

        if 'previous_network' in self.__dict__:
            bytes_sent_diff = snapshot.network_io['bytes_sent'] - self.previous_network['bytes_sent']
            bytes_recv_diff = snapshot.network_io['bytes_recv'] - self.previous_network['bytes_recv']
            self.prom_network_bytes_sent._value._value += bytes_sent_diff
            self.prom_network_bytes_recv._value._value += bytes_recv_diff

        self.previous_network = snapshot.network_io

    def register_custom_collector(self, name: str, collector: Callable):
        """Register a custom metric collector."""
        self.custom_collectors[name] = collector

    def get_metrics_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Get metrics summary for the specified time period."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_metrics = [
            m for m in self.metrics_history
            if m.timestamp >= cutoff_time
        ]

        if not recent_metrics:
            return {}

        # Calculate statistics
        cpu_values = [m.cpu_percent for m in recent_metrics]
        memory_values = [m.memory_percent for m in recent_metrics]

        return {
            'period_hours': hours,
            'sample_count': len(recent_metrics),
            'cpu': {
                'avg': sum(cpu_values) / len(cpu_values),
                'min': min(cpu_values),
                'max': max(cpu_values)
            },
            'memory': {
                'avg': sum(memory_values) / len(memory_values),
                'min': min(memory_values),
                'max': max(memory_values)
            },
            'timestamps': {
                'start': recent_metrics[0].timestamp.isoformat(),
                'end': recent_metrics[-1].timestamp.isoformat()
            }
        }


class ProfilerManager:
    """Manages profiling of application code."""

    def __init__(self, profiles_dir: Path = Path("profiles")):
        self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(exist_ok=True)
        self.active_profiles: Dict[str, Any] = {}
        self.profile_counter = 0

    @asynccontextmanager
    async def profile_request(self, request_info: Dict[str, Any]):
        """Profile a single request."""
        profile_id = f"request_{self.profile_counter}_{int(time.time())}"
        self.profile_counter += 1

        # Start profiling
        profile_data = {
            'id': profile_id,
            'request_info': request_info,
            'start_time': time.time(),
            'start_memory': psutil.Process().memory_info().rss / 1024 / 1024,
            'samples': []
        }

        try:
            yield profile_data
        finally:
            # End profiling
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024

            profile_data.update({
                'duration': end_time - profile_data['start_time'],
                'memory_delta': end_memory - profile_data['start_memory'],
                'end_time': end_time
            })

            # Save profile
            profile_file = self.profiles_dir / f"{profile_id}.json"
            with open(profile_file, 'w') as f:
                json.dump(profile_data, f, indent=2, default=str)

    def start_continuous_profiling(self, duration_minutes: int = 10):
        """Start continuous profiling with Pyroscope."""
        pyroscope.configure(
            application_name="hermes-ai-assistant",
            server_address="http://pyroscope:4040",
            tags={
                "environment": "production",
                "version": "1.0.0"
            }
        )

        # Schedule stop
        asyncio.create_task(self._stop_profiling_after(duration_minutes))

    async def _stop_profiling_after(self, minutes: int):
        """Stop profiling after specified duration."""
        await asyncio.sleep(minutes * 60)
        pyroscope.stop()


class DatabaseProfiler:
    """Profiles database query performance."""

    def __init__(self, slow_query_threshold: float = 1.0):
        self.slow_query_threshold = slow_query_threshold
        self.query_history: deque = deque(maxlen=10000)
        self.slow_queries: List[Dict[str, Any]] = []

    @asynccontextmanager
    async def profile_query(self, query: str, params: Dict[str, Any] = None):
        """Profile a database query."""
        start_time = time.time()
        query_info = {
            'query': query,
            'params': params or {},
            'timestamp': datetime.utcnow().isoformat(),
        }

        try:
            yield
        finally:
            duration = time.time() - start_time
            query_info['duration'] = duration

            self.query_history.append(query_info)

            if duration > self.slow_query_threshold:
                query_info['warning'] = f"Slow query: {duration:.3f}s > {self.slow_query_threshold}s"
                self.slow_queries.append(query_info)
                logger.warning(query_info['warning'])

    def get_query_stats(self) -> Dict[str, Any]:
        """Get query performance statistics."""
        if not self.query_history:
            return {}

        durations = [q['duration'] for q in self.query_history]

        return {
            'total_queries': len(self.query_history),
            'avg_duration': sum(durations) / len(durations),
            'min_duration': min(durations),
            'max_duration': max(durations),
            'slow_queries': len(self.slow_queries),
            'slow_query_threshold': self.slow_query_threshold
        }


def profile_function(include_memory: bool = True):
    """Decorator to profile function execution."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            start_memory = psutil.Process().memory_info().rss if include_memory else 0

            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                end_time = time.time()
                duration = end_time - start_time

                if include_memory:
                    end_memory = psutil.Process().memory_info().rss
                    memory_delta = (end_memory - start_memory) / 1024 / 1024
                else:
                    memory_delta = 0

                logger.info(
                    f"Profile {func.__name__}: {duration:.3f}s"
                    f"{' + ' + str(memory_delta) + 'MB' if include_memory else ''}"
                )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            start_memory = psutil.Process().memory_info().rss if include_memory else 0

            try:
                result = func(*args, **kwargs)
                return result
            finally:
                end_time = time.time()
                duration = end_time - start_time

                if include_memory:
                    end_memory = psutil.Process().memory_info().rss
                    memory_delta = (end_memory - start_memory) / 1024 / 1024
                else:
                    memory_delta = 0

                logger.info(
                    f"Profile {func.__name__}: {duration:.3f}s"
                    f"{' + ' + str(memory_delta) + 'MB' if include_memory else ''}"
                )

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


class PerformanceAlerting:
    """Performance-based alerting system."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.alert_thresholds = {
            'cpu_percent': 80.0,
            'memory_percent': 85.0,
            'disk_percent': 90.0,
            'response_time_p95': 2.0,  # seconds
            'error_rate': 5.0  # percent
        }
        self.alert_cooldown = 300  # 5 minutes

    async def check_alert_conditions(self, snapshot: PerformanceSnapshot):
        """Check if any alert conditions are met."""
        alerts = []
        current_time = datetime.utcnow().timestamp()

        # CPU alert
        if snapshot.cpu_percent > self.alert_thresholds['cpu_percent']:
            if await self._should_send_alert('high_cpu', current_time):
                alerts.append({
                    'type': 'high_cpu',
                    'severity': 'warning',
                    'message': f"High CPU usage: {snapshot.cpu_percent:.1f}%",
                    'value': snapshot.cpu_percent,
                    'threshold': self.alert_thresholds['cpu_percent']
                })

        # Memory alert
        if snapshot.memory_percent > self.alert_thresholds['memory_percent']:
            if await self._should_send_alert('high_memory', current_time):
                alerts.append({
                    'type': 'high_memory',
                    'severity': 'warning',
                    'message': f"High memory usage: {snapshot.memory_percent:.1f}%",
                    'value': snapshot.memory_percent,
                    'threshold': self.alert_thresholds['memory_percent']
                })

        # Disk alert
        if snapshot.disk_usage_percent > self.alert_thresholds['disk_percent']:
            if await self._should_send_alert('high_disk', current_time):
                alerts.append({
                    'type': 'high_disk',
                    'severity': 'critical',
                    'message': f"High disk usage: {snapshot.disk_usage_percent:.1f}%",
                    'value': snapshot.disk_usage_percent,
                    'threshold': self.alert_thresholds['disk_percent']
                })

        # Send alerts
        for alert in alerts:
            await self._send_alert(alert)

    async def _should_send_alert(self, alert_type: str, current_time: float) -> bool:
        """Check if alert should be sent based on cooldown."""
        last_sent_key = f"perf_alert:last_sent:{alert_type}"
        last_sent = await self.redis.get(last_sent_key)

        if last_sent is None or (current_time - float(last_sent)) > self.alert_cooldown:
            await self.redis.setex(last_sent_key, self.alert_cooldown, current_time)
            return True
        return False

    async def _send_alert(self, alert: Dict[str, Any]):
        """Send performance alert."""
        logger.warning(f"Performance Alert: {alert['message']}")

        # Store alert for dashboard
        alert_key = f"perf_alert:{alert['type']}:{int(time.time())}"
        await self.redis.hset(alert_key, mapping={
            'type': alert['type'],
            'severity': alert['severity'],
            'message': alert['message'],
            'value': str(alert['value']),
            'threshold': str(alert['threshold']),
            'timestamp': datetime.utcnow().isoformat()
        })
        await self.redis.expire(alert_key, 86400)  # 24 hours


class PerformanceOptimizer:
    """Automatic performance optimization recommendations."""

    def __init__(self):
        self.optimization_rules = [
            self._check_memory_leaks,
            self._check_cpu_spikes,
            self._check_slow_queries,
            self._check_disk_space,
            self._check_network_bottlenecks
        ]

    async def analyze_and_recommend(self, metrics_history: List[PerformanceSnapshot]) -> List[Dict[str, Any]]:
        """Analyze metrics and provide optimization recommendations."""
        recommendations = []

        for rule in self.optimization_rules:
            try:
                rule_recommendations = await rule(metrics_history)
                recommendations.extend(rule_recommendations)
            except Exception as e:
                logger.error(f"Error in optimization rule {rule.__name__}: {e}")

        return recommendations

    async def _check_memory_leaks(self, metrics: List[PerformanceSnapshot]) -> List[Dict[str, Any]]:
        """Check for potential memory leaks."""
        if len(metrics) < 10:
            return []

        # Check memory trend
        memory_values = [(m.timestamp, m.memory_usage_mb) for m in metrics]
        memory_trend = self._calculate_trend(memory_values)

        recommendations = []
        if memory_trend > 0.5:  # Growing trend
            recommendations.append({
                'type': 'memory_leak',
                'severity': 'warning',
                'message': f"Memory usage trending upward (+{memory_trend:.1f}MB/hr)",
                'recommendation': "Investigate potential memory leaks in long-running processes",
                'action': 'profile_memory_usage'
            })

        return recommendations

    async def _check_cpu_spikes(self, metrics: List[PerformanceSnapshot]) -> List[Dict[str, Any]]:
        """Check for CPU spikes and unusual patterns."""
        if len(metrics) < 5:
            return []

        cpu_values = [m.cpu_percent for m in metrics]
        avg_cpu = sum(cpu_values) / len(cpu_values)
        max_cpu = max(cpu_values)

        recommendations = []
        if max_cpu > 90 and avg_cpu < 50:
            recommendations.append({
                'type': 'cpu_spikes',
                'severity': 'warning',
                'message': f"CPU spikes detected (max: {max_cpu:.1f}%, avg: {avg_cpu:.1f}%)",
                'recommendation': "Investigate periodic CPU-intensive operations",
                'action': 'profile_cpu_usage'
            })

        return recommendations

    async def _check_slow_queries(self, metrics: List[PerformanceSnapshot]) -> List[Dict[str, Any]]:
        """Check for slow database queries."""
        # This would integrate with the database profiler
        return []

    async def _check_disk_space(self, metrics: List[PerformanceSnapshot]) -> List[Dict[str, Any]]:
        """Check disk space usage."""
        if not metrics:
            return []

        latest_disk = metrics[-1].disk_usage_percent
        recommendations = []

        if latest_disk > 85:
            recommendations.append({
                'type': 'disk_space',
                'severity': 'critical',
                'message': f"High disk usage: {latest_disk:.1f}%",
                'recommendation': "Clean up old logs and temporary files",
                'action': 'cleanup_disk_space'
            })

        return recommendations

    async def _check_network_bottlenecks(self, metrics: List[PerformanceSnapshot]) -> List[Dict[str, Any]]:
        """Check for network bottlenecks."""
        return []

    def _calculate_trend(self, values: List[tuple]) -> float:
        """Calculate linear trend (slope) for time series data."""
        if len(values) < 2:
            return 0.0

        # Simple linear regression
        n = len(values)
        x_values = [(time.time() if isinstance(values[0][0], datetime) else values[0][0]) for _, _ in values]
        y_values = [value for _, value in values]

        x_mean = sum(x_values) / n
        y_mean = sum(y_values) / n

        numerator = sum((x_values[i] - x_mean) * (y_values[i] - y_mean) for i in range(n))
        denominator = sum((x_values[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0

        return numerator / denominator * 3600  # Convert to per hour


# Global performance monitoring instance
performance_collector = PerformanceCollector()
database_profiler = DatabaseProfiler()
performance_optimizer = PerformanceOptimizer()