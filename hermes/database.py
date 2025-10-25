"""
Hermes Database Module
SQLite database initialization and operations
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from contextlib import contextmanager

from .config import Config

logger = logging.getLogger(__name__)

class Database:
    """SQLite database manager for Hermes application"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db_path = self.config.get('database.path', 'hermes.db')

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            yield conn
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def initialize(self):
        """Initialize database with all required tables"""
        logger.info(f"Initializing database at {self.db_path}")

        with self.get_connection() as conn:
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")

            # Create all tables
            self._create_jobs_table(conn)
            self._create_job_events_table(conn)
            self._create_conversations_table(conn)
            self._create_conversation_messages_table(conn)
            self._create_metalearning_patterns_table(conn)
            self._create_metalearning_questions_table(conn)
            self._create_metalearning_responses_table(conn)
            self._create_backends_table(conn)
            self._create_backend_configs_table(conn)
            self._create_backend_performance_table(conn)
            self._create_system_metrics_table(conn)
            self._create_error_reports_table(conn)
            self._create_notifications_table(conn)
            self._create_monitoring_alerts_table(conn)

            conn.commit()
            logger.info("Database initialization completed")

    def _create_jobs_table(self, conn):
        """Create jobs table"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idea TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                backend_id INTEGER,
                priority INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                result TEXT,
                error_message TEXT,
                cost_cents INTEGER DEFAULT 0,
                execution_time_ms INTEGER,
                FOREIGN KEY (backend_id) REFERENCES backends (id)
            )
        """)

    def _create_job_events_table(self, conn):
        """Create job_events table"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS job_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE
            )
        """)

    def _create_conversations_table(self, conn):
        """Create conversations table"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE
            )
        """)

    def _create_conversation_messages_table(self, conn):
        """Create conversation_messages table"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                message_type TEXT NOT NULL,
                sender TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
            )
        """)

    def _create_metalearning_patterns_table(self, conn):
        """Create metalearning_patterns table"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metalearning_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_name TEXT NOT NULL UNIQUE,
                pattern_type TEXT NOT NULL,
                pattern_data TEXT NOT NULL,
                confidence_score REAL DEFAULT 0.0,
                usage_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def _create_metalearning_questions_table(self, conn):
        """Create metalearning_questions table"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metalearning_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                question_type TEXT NOT NULL,
                context_data TEXT,
                asked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                answered_at TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
            )
        """)

    def _create_metalearning_responses_table(self, conn):
        """Create metalearning_responses table"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metalearning_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                response_text TEXT NOT NULL,
                response_data TEXT,
                confidence_score REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (question_id) REFERENCES metalearning_questions (id) ON DELETE CASCADE
            )
        """)

    def _create_backends_table(self, conn):
        """Create backends table"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS backends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'inactive',
                endpoint TEXT,
                model_name TEXT,
                is_default BOOLEAN DEFAULT 0,
                priority INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def _create_backend_configs_table(self, conn):
        """Create backend_configs table"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS backend_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backend_id INTEGER NOT NULL,
                config_key TEXT NOT NULL,
                config_value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (backend_id) REFERENCES backends (id) ON DELETE CASCADE,
                UNIQUE(backend_id, config_key)
            )
        """)

    def _create_backend_performance_table(self, conn):
        """Create backend_performance table"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS backend_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backend_id INTEGER NOT NULL,
                job_id INTEGER NOT NULL,
                response_time_ms INTEGER,
                cost_cents INTEGER DEFAULT 0,
                success BOOLEAN DEFAULT 1,
                error_message TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (backend_id) REFERENCES backends (id),
                FOREIGN KEY (job_id) REFERENCES jobs (id)
            )
        """)

    def _create_system_metrics_table(self, conn):
        """Create system_metrics table"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS system_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                metric_unit TEXT,
                metadata TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def _create_error_reports_table(self, conn):
        """Create error_reports table"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS error_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_id TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                traceback TEXT,
                context TEXT,
                timestamp TIMESTAMP NOT NULL,
                job_id INTEGER,
                user_id TEXT,
                resolved BOOLEAN DEFAULT 0,
                resolution_notes TEXT,
                FOREIGN KEY (job_id) REFERENCES jobs (id)
            )
        """)

    def _create_notifications_table(self, conn):
        """Create notifications table"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                priority TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                job_id INTEGER,
                user_id TEXT,
                context TEXT,
                telegram_sent BOOLEAN DEFAULT 0,
                FOREIGN KEY (job_id) REFERENCES jobs (id)
            )
        """)

    def _create_monitoring_alerts_table(self, conn):
        """Create monitoring alerts table"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS monitoring_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                severity TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                resolved BOOLEAN DEFAULT 0,
                resolved_at TIMESTAMP,
                resolution_notes TEXT
            )
        """)

    # Jobs operations
    def create_job(self, idea: str, priority: int = 1) -> int:
        """Create a new job"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO jobs (idea, priority) VALUES (?, ?)",
                (idea, priority)
            )
            job_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Created job {job_id} for idea: {idea[:100]}...")
            return job_id

    def get_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Get job by ID"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM jobs WHERE id = ?",
                (job_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_recent_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent jobs"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def update_job_status(self, job_id: int, status: str, **kwargs):
        """Update job status and optional fields"""
        set_clauses = ["status = ?"]
        values = [status]

        if 'backend_id' in kwargs:
            set_clauses.append("backend_id = ?")
            values.append(kwargs['backend_id'])

        if 'started_at' in kwargs:
            set_clauses.append("started_at = ?")
            values.append(kwargs['started_at'])

        if 'completed_at' in kwargs:
            set_clauses.append("completed_at = ?")
            values.append(kwargs['completed_at'])

        if 'result' in kwargs:
            set_clauses.append("result = ?")
            values.append(kwargs['result'])

        if 'error_message' in kwargs:
            set_clauses.append("error_message = ?")
            values.append(kwargs['error_message'])

        if 'cost_cents' in kwargs:
            set_clauses.append("cost_cents = ?")
            values.append(kwargs['cost_cents'])

        if 'execution_time_ms' in kwargs:
            set_clauses.append("execution_time_ms = ?")
            values.append(kwargs['execution_time_ms'])

        values.append(job_id)

        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE jobs SET {', '.join(set_clauses)} WHERE id = ?",
                values
            )
            conn.commit()
            logger.info(f"Updated job {job_id} status to {status}")

    # Job events operations
    def create_job_event(self, job_id: int, event_type: str, event_data: Dict[str, Any] = None):
        """Create a job event"""
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO job_events (job_id, event_type, event_data) VALUES (?, ?, ?)",
                (job_id, event_type, json.dumps(event_data) if event_data else None)
            )
            conn.commit()

    def get_job_events(self, job_id: int) -> List[Dict[str, Any]]:
        """Get events for a job"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM job_events WHERE job_id = ? ORDER BY created_at",
                (job_id,)
            )
            events = []
            for row in cursor.fetchall():
                event = dict(row)
                if event['event_data']:
                    event['event_data'] = json.loads(event['event_data'])
                events.append(event)
            return events

    # Backends operations
    def get_active_backends(self) -> List[Dict[str, Any]]:
        """Get active backends"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM backends WHERE status = 'active' ORDER BY priority, name"
            )
            return [dict(row) for row in cursor.fetchall()]

    def create_backend(self, name: str, backend_type: str, **kwargs) -> int:
        """Create a new backend"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO backends (name, type, endpoint, model_name, is_default, priority)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, backend_type, kwargs.get('endpoint'), kwargs.get('model_name'),
                 kwargs.get('is_default', False), kwargs.get('priority', 1))
            )
            backend_id = cursor.lastrowid
            conn.commit()
            return backend_id

    # System metrics
    def record_metric(self, name: str, value: float, unit: str = None, metadata: Dict[str, Any] = None):
        """Record a system metric"""
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO system_metrics (metric_name, metric_value, metric_unit, metadata) VALUES (?, ?, ?, ?)",
                (name, value, unit, json.dumps(metadata) if metadata else None)
            )
            conn.commit()

    # Utility methods
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            with self.get_connection() as conn:
                conn.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self.get_connection() as conn:
            stats = {}

            # Job stats
            cursor = conn.execute("SELECT COUNT(*) as total_jobs FROM jobs")
            stats['total_jobs'] = cursor.fetchone()['total_jobs']

            cursor = conn.execute("SELECT status, COUNT(*) as count FROM jobs GROUP BY status")
            stats['jobs_by_status'] = {row['status']: row['count'] for row in cursor.fetchall()}

            # Backend stats
            cursor = conn.execute("SELECT COUNT(*) as total_backends FROM backends")
            stats['total_backends'] = cursor.fetchone()['total_backends']

            cursor = conn.execute("SELECT status, COUNT(*) as count FROM backends GROUP BY status")
            stats['backends_by_status'] = {row['status']: row['count'] for row in cursor.fetchall()}

            return stats