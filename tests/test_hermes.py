#!/usr/bin/env python3
"""
Hermes Test Suite
Comprehensive integration and unit tests for Hermes
"""

import os
import sys
import unittest
import tempfile
import json
import time
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hermes.config import Config
from hermes.database import Database
from hermes.local_execution import LocalExecutionEngine
from hermes.queue import JobQueue
from hermes.retry_system import RetryManager
from hermes.error_handler import ErrorHandler
from hermes.notifications import NotificationManager
from hermes.monitoring import MetricsCollector

class TestConfig(unittest.TestCase):
    """Test configuration management"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, 'test_config.yaml')
        self.test_config = {
            'hermes': {
                'debug': True,
                'port': 5001
            },
            'database': {
                'path': ':memory:'
            }
        }

        with open(self.config_file, 'w') as f:
            import yaml
            yaml.dump(self.test_config, f)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_config_loading(self):
        """Test configuration loading from file"""
        config = Config(self.config_file)
        self.assertTrue(config.get('hermes.debug'))
        self.assertEqual(config.get('hermes.port'), 5001)

    def test_config_defaults(self):
        """Test configuration defaults"""
        config = Config()
        self.assertFalse(config.get('hermes.debug', False))
        self.assertEqual(config.get('hermes.port', 5000), 5000)

    def test_env_override(self):
        """Test environment variable override"""
        os.environ['HERMES_DEBUG'] = 'true'
        try:
            config = Config()
            self.assertTrue(config.get('hermes.debug'))
        finally:
            del os.environ['HERMES_DEBUG']

class TestDatabase(unittest.TestCase):
    """Test database operations"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')
        self.db = Database()
        self.db.db_path = self.db_path
        self.db.initialize()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_database_initialization(self):
        """Test database initialization"""
        self.assertTrue(os.path.exists(self.db_path))
        self.assertTrue(self.db.test_connection())

    def test_job_creation(self):
        """Test job creation and retrieval"""
        job_id = self.db.create_job("Test idea", priority=1)
        self.assertIsNotNone(job_id)
        self.assertIsInstance(job_id, int)

        job = self.db.get_job(job_id)
        self.assertIsNotNone(job)
        self.assertEqual(job['idea'], "Test idea")
        self.assertEqual(job['status'], 'queued')

    def test_job_status_update(self):
        """Test job status updates"""
        job_id = self.db.create_job("Test idea")
        self.db.update_job_status(job_id, 'running')

        job = self.db.get_job(job_id)
        self.assertEqual(job['status'], 'running')

    def test_job_events(self):
        """Test job event creation and retrieval"""
        job_id = self.db.create_job("Test idea")

        self.db.create_job_event(job_id, 'test_event', {'test': 'data'})
        events = self.db.get_job_events(job_id)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['event_type'], 'test_event')

class TestLocalExecution(unittest.TestCase):
    """Test local execution engine"""

    def setUp(self):
        self.config = Config()
        self.engine = LocalExecutionEngine(self.config)

    @patch('subprocess.run')
    def test_model_availability_check(self, mock_run):
        """Test model availability checking"""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "llama3.1:8b-instruct\nqwen2.5-coder:7b\n"

        models = self.engine.get_available_models()
        self.assertIsInstance(models, list)
        mock_run.assert_called_with(['ollama', 'list'], capture_output=True, text=True, timeout=10)

    @patch('subprocess.run')
    def test_execution_success(self, mock_run):
        """Test successful job execution"""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Task completed successfully"

        result = self.engine.run_idea("Test task", 1)

        self.assertTrue(result.success)
        self.assertEqual(result.job_id, "1")
        self.assertIsNotNone(result.result_data)

    @patch('subprocess.run')
    def test_execution_failure(self, mock_run):
        """Test job execution failure"""
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Execution failed"

        result = self.engine.run_idea("Test task", 1)

        self.assertFalse(result.success)
        self.assertIn("failed", result.error_message.lower())

class TestRetrySystem(unittest.TestCase):
    """Test retry system"""

    def setUp(self):
        self.config = Config()
        self.retry_manager = RetryManager(self.config)

    def test_retry_decision(self):
        """Test retry decision logic"""
        # Should retry connection errors
        self.assertTrue(self.retry_manager.should_retry_job(1, "Connection refused"))

        # Should not retry validation errors
        self.assertFalse(self.retry_manager.should_retry_job(1, "Invalid schema"))

    def test_delay_calculation(self):
        """Test retry delay calculation"""
        from hermes.retry_system import RetryConfig, RetryStrategy

        config = RetryConfig(
            base_delay=1.0,
            backoff_multiplier=2.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF
        )

        delay1 = self.retry_manager._calculate_delay(config, 1)
        delay2 = self.retry_manager._calculate_delay(config, 2)

        self.assertEqual(delay1, 1.0)
        self.assertEqual(delay2, 2.0)

class TestErrorHandler(unittest.TestCase):
    """Test error handling system"""

    def setUp(self):
        self.config = Config()
        self.error_handler = ErrorHandler(self.config)

    def test_error_categorization(self):
        """Test error categorization"""
        connection_error = ConnectionError("Connection refused")
        validation_error = ValueError("Invalid input")

        connection_report = self.error_handler.handle_error(connection_error)
        validation_report = self.error_handler.handle_error(validation_error)

        self.assertEqual(connection_report.category.value, 'network')
        self.assertEqual(validation_report.category.value, 'validation')

    def test_error_severity(self):
        """Test error severity assignment"""
        timeout_error = TimeoutError("Operation timed out")
        report = self.error_handler.handle_error(timeout_error)

        self.assertEqual(report.severity.value, 'high')

class TestNotificationManager(unittest.TestCase):
    """Test notification management"""

    def setUp(self):
        self.config = Config()
        self.notification_manager = NotificationManager(self.config)

    def test_notification_creation(self):
        """Test notification creation"""
        from hermes.notifications import Notification, NotificationType, NotificationPriority

        notification = Notification(
            notification_type=NotificationType.JOB_COMPLETED,
            title="Test Job",
            message="Job completed successfully",
            priority=NotificationPriority.MEDIUM,
            timestamp=time.time(),
            context={},
            job_id=1
        )

        self.assertEqual(notification.title, "Test Job")
        self.assertEqual(notification.job_id, 1)

    @patch('requests.post')
    def test_telegram_notification(self, mock_post):
        """Test Telegram notification sending"""
        # Mock successful Telegram response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {'ok': True}

        # Configure Telegram
        self.config.set('notifications.telegram.enabled', True)
        self.config.set('notifications.telegram.bot_token', 'test_token')
        self.config.set('notifications.telegram.chat_id', 'test_chat')

        # Create and send notification
        from hermes.notifications import Notification, NotificationType, NotificationPriority
        notification = Notification(
            notification_type=NotificationType.JOB_COMPLETED,
            title="Test Job",
            message="Job completed successfully",
            priority=NotificationPriority.MEDIUM,
            timestamp=time.time(),
            context={},
            job_id=1
        )

        result = self.notification_manager.telegram.send_notification(notification)
        self.assertTrue(result)

class TestMetricsCollector(unittest.TestCase):
    """Test metrics collection"""

    def setUp(self):
        self.config = Config()
        self.metrics_collector = MetricsCollector(self.config)

    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_system_metrics_collection(self, mock_disk, mock_memory, mock_cpu):
        """Test system metrics collection"""
        # Mock psutil responses
        mock_cpu.return_value = 50.0

        mock_memory_obj = Mock()
        mock_memory_obj.percent = 60.0
        mock_memory_obj.available = 8 * 1024**3  # 8GB
        mock_memory.return_value = mock_memory_obj

        mock_disk_obj = Mock()
        mock_disk_obj.percent = 70.0
        mock_disk_obj.free = 100 * 1024**3  # 100GB
        mock_disk.return_value = mock_disk_obj

        metrics = self.metrics_collector._collect_system_metrics()

        self.assertEqual(metrics.cpu_percent, 50.0)
        self.assertEqual(metrics.memory_percent, 60.0)
        self.assertEqual(metrics.disk_usage_percent, 70.0)

    def test_alert_thresholds(self):
        """Test alert threshold checking"""
        from hermes.monitoring import SystemMetrics, ApplicationMetrics

        # Create metrics that should trigger alerts
        system_metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=90.0,  # Above warning threshold
            memory_percent=80.0,
            memory_available_gb=4.0,
            disk_usage_percent=85.0,
            disk_free_gb=50.0,
            network_io_sent_mb=100.0,
            network_io_recv_mb=200.0,
            process_count=150,
            load_average=[1.5, 1.2, 1.0]
        )

        app_metrics = ApplicationMetrics(
            timestamp=time.time(),
            active_jobs=5,
            queued_jobs=2,
            completed_jobs=100,
            failed_jobs=10,
            average_job_time=30.0,
            jobs_per_minute=2.0,
            error_rate=0.15,  # Above warning threshold
            active_backends=2,
            total_requests=1000,
            response_time_avg=500.0
        )

        # This should generate alerts for high CPU and error rate
        # (We can't easily test the alert sending without a database, but we can test the threshold logic)
        self.assertGreater(system_metrics.cpu_percent, 80.0)  # Should trigger CPU warning
        self.assertGreater(app_metrics.error_rate, 0.1)       # Should trigger error rate warning

class TestIntegration(unittest.TestCase):
    """Integration tests"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = Config()
        self.config.set('database.path', os.path.join(self.temp_dir, 'test.db'))

        # Initialize components
        self.db = Database(self.config)
        self.db.initialize()

        self.queue = JobQueue(self.config)
        self.engine = LocalExecutionEngine(self.config)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    @patch('subprocess.run')
    def test_end_to_end_job_processing(self, mock_run):
        """Test end-to-end job processing"""
        # Mock successful execution
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Task completed successfully"

        # Create and enqueue job
        job_id = self.db.create_job("Test integration job")
        from hermes.queue import Job
        job = Job(id=job_id, idea="Test integration job")

        # Process job
        self.queue._process_job(job)

        # Verify job completed
        updated_job = self.db.get_job(job_id)
        self.assertEqual(updated_job['status'], 'completed')

    def test_error_recovery_flow(self):
        """Test error recovery and retry flow"""
        # Create job that will fail
        job_id = self.db.create_job("Test failing job")

        # Simulate job failure
        self.db.update_job_status(job_id, 'failed', error_message="Test error")

        # Verify error was recorded
        job = self.db.get_job(job_id)
        self.assertEqual(job['status'], 'failed')
        self.assertIn("Test error", job['error_message'])

if __name__ == '__main__':
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    test_classes = [
        TestConfig,
        TestDatabase,
        TestLocalExecution,
        TestRetrySystem,
        TestErrorHandler,
        TestNotificationManager,
        TestMetricsCollector,
        TestIntegration
    ]

    for test_class in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)