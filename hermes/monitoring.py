"""
Hermes System Monitoring and Metrics
Comprehensive monitoring of system health and performance
"""

import psutil
import time
import logging
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict, deque

from .config import Config
from .database import Database
from .logger import get_logger

logger = get_logger('monitoring')

@dataclass
class SystemMetrics:
    """System performance metrics"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_available_gb: float
    disk_usage_percent: float
    disk_free_gb: float
    network_io_sent_mb: float
    network_io_recv_mb: float
    process_count: int
    load_average: List[float]  # 1, 5, 15 minute averages

@dataclass
class ApplicationMetrics:
    """Application-specific metrics"""
    timestamp: datetime
    active_jobs: int
    queued_jobs: int
    completed_jobs: int
    failed_jobs: int
    average_job_time: float
    jobs_per_minute: float
    error_rate: float
    active_backends: int
    total_requests: int
    response_time_avg: float

class MetricsCollector:
    """Collects and stores system and application metrics"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.logger = get_logger('metrics_collector')
        self.collection_interval = self.config.get('monitoring.collection_interval', 60)  # seconds
        self.retention_days = self.config.get('monitoring.retention_days', 30)
        self._running = False
        self._collector_thread = None

        # In-memory metrics for quick access
        self._system_metrics_history = deque(maxlen=1440)  # 24 hours at 1-minute intervals
        self._app_metrics_history = deque(maxlen=1440)
        self._alert_thresholds = self._load_alert_thresholds()

    def _load_alert_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Load alert thresholds from configuration"""
        return {
            'cpu': {
                'warning': self.config.get('monitoring.thresholds.cpu.warning', 80.0),
                'critical': self.config.get('monitoring.thresholds.cpu.critical', 95.0)
            },
            'memory': {
                'warning': self.config.get('monitoring.thresholds.memory.warning', 80.0),
                'critical': self.config.get('monitoring.thresholds.memory.critical', 95.0)
            },
            'disk': {
                'warning': self.config.get('monitoring.thresholds.disk.warning', 85.0),
                'critical': self.config.get('monitoring.thresholds.disk.critical', 95.0)
            },
            'error_rate': {
                'warning': self.config.get('monitoring.thresholds.error_rate.warning', 0.1),  # 10%
                'critical': self.config.get('monitoring.thresholds.error_rate.critical', 0.2)  # 20%
            },
            'response_time': {
                'warning': self.config.get('monitoring.thresholds.response_time.warning', 5000),  # 5 seconds
                'critical': self.config.get('monitoring.thresholds.response_time.critical', 10000)  # 10 seconds
            }
        }

    def start_collection(self):
        """Start metrics collection thread"""
        if self._running:
            self.logger.warning("Metrics collection already running")
            return

        self._running = True
        self._collector_thread = threading.Thread(target=self._collection_loop, daemon=True)
        self._collector_thread.start()
        self.logger.info("Metrics collection started")

    def stop_collection(self):
        """Stop metrics collection thread"""
        self._running = False
        if self._collector_thread:
            self._collector_thread.join(timeout=5)
        self.logger.info("Metrics collection stopped")

    def _collection_loop(self):
        """Main metrics collection loop"""
        while self._running:
            try:
                # Collect system metrics
                system_metrics = self._collect_system_metrics()
                self._system_metrics_history.append(system_metrics)
                self._store_system_metrics(system_metrics)

                # Collect application metrics
                app_metrics = self._collect_application_metrics()
                self._app_metrics_history.append(app_metrics)
                self._store_application_metrics(app_metrics)

                # Check for alerts
                self._check_alerts(system_metrics, app_metrics)

                # Cleanup old data
                self._cleanup_old_metrics()

                time.sleep(self.collection_interval)

            except Exception as e:
                self.logger.error(f"Error in metrics collection: {e}")
                time.sleep(self.collection_interval)

    def _collect_system_metrics(self) -> SystemMetrics:
        """Collect system performance metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory metrics
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available_gb = memory.available / (1024**3)

            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_usage_percent = disk.percent
            disk_free_gb = disk.free / (1024**3)

            # Network metrics
            network = psutil.net_io_counters()
            network_io_sent_mb = network.bytes_sent / (1024**2)
            network_io_recv_mb = network.bytes_recv / (1024**2)

            # Process count
            process_count = len(psutil.pids())

            # Load average (Unix-like systems)
            try:
                load_average = list(psutil.getloadavg())
            except AttributeError:
                # Windows doesn't have load average
                load_average = [0.0, 0.0, 0.0]

            return SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_available_gb=memory_available_gb,
                disk_usage_percent=disk_usage_percent,
                disk_free_gb=disk_free_gb,
                network_io_sent_mb=network_io_sent_mb,
                network_io_recv_mb=network_io_recv_mb,
                process_count=process_count,
                load_average=load_average
            )

        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")
            return SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=0.0, memory_percent=0.0, memory_available_gb=0.0,
                disk_usage_percent=0.0, disk_free_gb=0.0, network_io_sent_mb=0.0,
                network_io_recv_mb=0.0, process_count=0, load_average=[0.0, 0.0, 0.0]
            )

    def _collect_application_metrics(self) -> ApplicationMetrics:
        """Collect application-specific metrics"""
        try:
            # Job statistics from database
            with self.db.get_connection() as conn:
                # Job counts
                cursor = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'running'")
                active_jobs = cursor.fetchone()[0]

                cursor = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'queued'")
                queued_jobs = cursor.fetchone()[0]

                cursor = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'completed'")
                completed_jobs = cursor.fetchone()[0]

                cursor = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'failed'")
                failed_jobs = cursor.fetchone()[0]

                # Average job execution time (last hour)
                cursor = conn.execute("""
                    SELECT AVG(execution_time_ms) FROM jobs
                    WHERE status = 'completed' AND completed_at > datetime('now', '-1 hour')
                """)
                avg_time_result = cursor.fetchone()[0]
                average_job_time = avg_time_result / 1000.0 if avg_time_result else 0.0

                # Jobs per minute (last hour)
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM jobs
                    WHERE created_at > datetime('now', '-1 hour')
                """)
                jobs_per_hour = cursor.fetchone()[0]
                jobs_per_minute = jobs_per_hour / 60.0

                # Error rate (last hour)
                cursor = conn.execute("""
                    SELECT
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as error_rate
                    FROM jobs
                    WHERE created_at > datetime('now', '-1 hour')
                """)
                error_rate_result = cursor.fetchone()[0]
                error_rate = error_rate_result or 0.0

                # Active backends
                cursor = conn.execute("SELECT COUNT(*) FROM backends WHERE status = 'active'")
                active_backends = cursor.fetchone()[0]

            # HTTP metrics (would be collected from Flask middleware in real implementation)
            total_requests = 0  # Placeholder
            response_time_avg = 0.0  # Placeholder

            return ApplicationMetrics(
                timestamp=datetime.now(),
                active_jobs=active_jobs,
                queued_jobs=queued_jobs,
                completed_jobs=completed_jobs,
                failed_jobs=failed_jobs,
                average_job_time=average_job_time,
                jobs_per_minute=jobs_per_minute,
                error_rate=error_rate,
                active_backends=active_backends,
                total_requests=total_requests,
                response_time_avg=response_time_avg
            )

        except Exception as e:
            self.logger.error(f"Error collecting application metrics: {e}")
            return ApplicationMetrics(
                timestamp=datetime.now(),
                active_jobs=0, queued_jobs=0, completed_jobs=0, failed_jobs=0,
                average_job_time=0.0, jobs_per_minute=0.0, error_rate=0.0,
                active_backends=0, total_requests=0, response_time_avg=0.0
            )

    def _store_system_metrics(self, metrics: SystemMetrics):
        """Store system metrics in database"""
        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO system_metrics (
                        metric_name, metric_value, metric_unit, metadata, recorded_at
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    'cpu_percent', metrics.cpu_percent, 'percent',
                    json.dumps({'type': 'system'}), metrics.timestamp
                ))
                conn.execute("""
                    INSERT INTO system_metrics (
                        metric_name, metric_value, metric_unit, metadata, recorded_at
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    'memory_percent', metrics.memory_percent, 'percent',
                    json.dumps({'type': 'system'}), metrics.timestamp
                ))
                conn.execute("""
                    INSERT INTO system_metrics (
                        metric_name, metric_value, metric_unit, metadata, recorded_at
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    'disk_usage_percent', metrics.disk_usage_percent, 'percent',
                    json.dumps({'type': 'system'}), metrics.timestamp
                ))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to store system metrics: {e}")

    def _store_application_metrics(self, metrics: ApplicationMetrics):
        """Store application metrics in database"""
        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO system_metrics (
                        metric_name, metric_value, metric_unit, metadata, recorded_at
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    'active_jobs', metrics.active_jobs, 'count',
                    json.dumps({'type': 'application'}), metrics.timestamp
                ))
                conn.execute("""
                    INSERT INTO system_metrics (
                        metric_name, metric_value, metric_unit, metadata, recorded_at
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    'error_rate', metrics.error_rate, 'rate',
                    json.dumps({'type': 'application'}), metrics.timestamp
                ))
                conn.execute("""
                    INSERT INTO system_metrics (
                        metric_name, metric_value, metric_unit, metadata, recorded_at
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    'jobs_per_minute', metrics.jobs_per_minute, 'rate',
                    json.dumps({'type': 'application'}), metrics.timestamp
                ))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to store application metrics: {e}")

    def _check_alerts(self, system_metrics: SystemMetrics, app_metrics: ApplicationMetrics):
        """Check metrics against alert thresholds"""
        alerts = []

        # CPU alerts
        if system_metrics.cpu_percent >= self._alert_thresholds['cpu']['critical']:
            alerts.append(('critical', 'cpu', f"CPU usage is critical: {system_metrics.cpu_percent:.1f}%"))
        elif system_metrics.cpu_percent >= self._alert_thresholds['cpu']['warning']:
            alerts.append(('warning', 'cpu', f"CPU usage is high: {system_metrics.cpu_percent:.1f}%"))

        # Memory alerts
        if system_metrics.memory_percent >= self._alert_thresholds['memory']['critical']:
            alerts.append(('critical', 'memory', f"Memory usage is critical: {system_metrics.memory_percent:.1f}%"))
        elif system_metrics.memory_percent >= self._alert_thresholds['memory']['warning']:
            alerts.append(('warning', 'memory', f"Memory usage is high: {system_metrics.memory_percent:.1f}%"))

        # Disk alerts
        if system_metrics.disk_usage_percent >= self._alert_thresholds['disk']['critical']:
            alerts.append(('critical', 'disk', f"Disk usage is critical: {system_metrics.disk_usage_percent:.1f}%"))
        elif system_metrics.disk_usage_percent >= self._alert_thresholds['disk']['warning']:
            alerts.append(('warning', 'disk', f"Disk usage is high: {system_metrics.disk_usage_percent:.1f}%"))

        # Error rate alerts
        if app_metrics.error_rate >= self._alert_thresholds['error_rate']['critical']:
            alerts.append(('critical', 'error_rate', f"Error rate is critical: {app_metrics.error_rate:.1%}"))
        elif app_metrics.error_rate >= self._alert_thresholds['error_rate']['warning']:
            alerts.append(('warning', 'error_rate', f"Error rate is high: {app_metrics.error_rate:.1%}"))

        # Send alerts
        for severity, alert_type, message in alerts:
            self._send_alert(severity, alert_type, message)

    def _send_alert(self, severity: str, alert_type: str, message: str):
        """Send monitoring alert"""
        try:
            # Store alert in database
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO monitoring_alerts (
                        severity, alert_type, message, timestamp, resolved
                    ) VALUES (?, ?, ?, ?, ?)
                """, (severity, alert_type, message, datetime.now(), False))
                conn.commit()

            # Send notification if critical
            if severity == 'critical':
                from .notifications import get_notification_manager
                notification_manager = get_notification_manager()
                notification_manager.notify_system_error(
                    f"Monitoring Alert ({alert_type})",
                    {'severity': severity, 'message': message}
                )

            self.logger.warning(f"Alert [{severity.upper()}] {alert_type}: {message}")

        except Exception as e:
            self.logger.error(f"Failed to send alert: {e}")

    def _cleanup_old_metrics(self):
        """Clean up old metrics data"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)

            with self.db.get_connection() as conn:
                conn.execute(
                    "DELETE FROM system_metrics WHERE recorded_at < ?",
                    (cutoff_date,)
                )
                conn.execute(
                    "DELETE FROM monitoring_alerts WHERE timestamp < ?",
                    (cutoff_date,)
                )
                conn.commit()

        except Exception as e:
            self.logger.error(f"Failed to cleanup old metrics: {e}")

    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current system and application metrics"""
        system = self._system_metrics_history[-1] if self._system_metrics_history else None
        app = self._app_metrics_history[-1] if self._app_metrics_history else None

        return {
            'system': {
                'cpu_percent': system.cpu_percent if system else 0,
                'memory_percent': system.memory_percent if system else 0,
                'memory_available_gb': system.memory_available_gb if system else 0,
                'disk_usage_percent': system.disk_usage_percent if system else 0,
                'disk_free_gb': system.disk_free_gb if system else 0,
                'load_average': system.load_average if system else [0, 0, 0]
            },
            'application': {
                'active_jobs': app.active_jobs if app else 0,
                'queued_jobs': app.queued_jobs if app else 0,
                'completed_jobs': app.completed_jobs if app else 0,
                'failed_jobs': app.failed_jobs if app else 0,
                'average_job_time': app.average_job_time if app else 0,
                'jobs_per_minute': app.jobs_per_minute if app else 0,
                'error_rate': app.error_rate if app else 0,
                'active_backends': app.active_backends if app else 0
            },
            'timestamp': datetime.now().isoformat(),
            'collection_active': self._running
        }

    def get_metrics_history(self, hours: int = 24) -> Dict[str, List[Dict[str, Any]]]:
        """Get metrics history for the last N hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        system_history = []
        app_history = []

        for metrics in self._system_metrics_history:
            if metrics.timestamp >= cutoff_time:
                system_history.append({
                    'timestamp': metrics.timestamp.isoformat(),
                    'cpu_percent': metrics.cpu_percent,
                    'memory_percent': metrics.memory_percent,
                    'disk_usage_percent': metrics.disk_usage_percent
                })

        for metrics in self._app_metrics_history:
            if metrics.timestamp >= cutoff_time:
                app_history.append({
                    'timestamp': metrics.timestamp.isoformat(),
                    'active_jobs': metrics.active_jobs,
                    'queued_jobs': metrics.queued_jobs,
                    'error_rate': metrics.error_rate,
                    'jobs_per_minute': metrics.jobs_per_minute
                })

        return {
            'system': system_history,
            'application': app_history
        }

    def get_alerts(self, hours: int = 24, resolved: bool = False) -> List[Dict[str, Any]]:
        """Get monitoring alerts"""
        try:
            with self.db.get_connection() as conn:
                cutoff_time = datetime.now() - timedelta(hours=hours)

                cursor = conn.execute("""
                    SELECT * FROM monitoring_alerts
                    WHERE timestamp > ? AND resolved = ?
                    ORDER BY timestamp DESC
                """, (cutoff_time, resolved))

                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            self.logger.error(f"Failed to get alerts: {e}")
            return []

# Global metrics collector
_metrics_collector = None

def get_metrics_collector(config: Optional[Config] = None) -> MetricsCollector:
    """Get global metrics collector instance"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector(config)
    return _metrics_collector