"""
Database for Routing System
Simple SQLite for tracking sessions and tasks
"""
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import contextmanager

from .config import DATABASE_PATH


class RoutingDatabase:
    """SQLite database for routing system"""

    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize database schema"""

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    tier TEXT NOT NULL,
                    total_cost REAL NOT NULL,
                    task_count INTEGER NOT NULL,
                    started_at DATETIME NOT NULL,
                    ended_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Tasks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    response TEXT NOT NULL,
                    local_model_used TEXT,
                    local_quality_score REAL,
                    cloud_model_used TEXT,
                    cloud_quality_score REAL,
                    final_model TEXT NOT NULL,
                    upgrade_decision TEXT NOT NULL,
                    actual_cost REAL NOT NULL,
                    predicted_cost REAL,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    response_time REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)

            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_session_id ON tasks(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_timestamp ON tasks(timestamp)")

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def save_session(self, session_id: str, tier: str, total_cost: float, task_count: int,
                    started_at: datetime, ended_at: Optional[datetime] = None):
        """Save or update session"""

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO sessions
                (session_id, tier, total_cost, task_count, started_at, ended_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, tier, total_cost, task_count, started_at, ended_at))

            conn.commit()

    def save_task(self, task_data: Dict):
        """Save task to database"""

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO tasks
                (session_id, prompt, response, local_model_used, local_quality_score,
                 cloud_model_used, cloud_quality_score, final_model, upgrade_decision,
                 actual_cost, predicted_cost, input_tokens, output_tokens, response_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_data.get("session_id"),
                task_data.get("prompt"),
                task_data.get("response"),
                task_data.get("local_model_used"),
                task_data.get("local_quality_score"),
                task_data.get("cloud_model_used"),
                task_data.get("cloud_quality_score"),
                task_data.get("final_model"),
                task_data.get("upgrade_decision"),
                task_data.get("actual_cost"),
                task_data.get("predicted_cost"),
                task_data.get("input_tokens"),
                task_data.get("output_tokens"),
                task_data.get("response_time")
            ))

            conn.commit()

    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session by ID"""

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM sessions WHERE session_id = ?
            """, (session_id,))

            row = cursor.fetchone()
            return dict(row) if row else None

    def get_session_tasks(self, session_id: str) -> List[Dict]:
        """Get all tasks for a session"""

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM tasks
                WHERE session_id = ?
                ORDER BY timestamp ASC
            """, (session_id,))

            return [dict(row) for row in cursor.fetchall()]

    def get_recent_sessions(self, limit: int = 10) -> List[Dict]:
        """Get recent sessions"""

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM sessions
                ORDER BY started_at DESC
                LIMIT ?
            """, (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def get_cost_stats(self, days: int = 7) -> Dict:
        """Get cost statistics for recent days"""

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    COUNT(*) as total_tasks,
                    SUM(actual_cost) as total_cost,
                    AVG(actual_cost) as avg_cost,
                    SUM(CASE WHEN upgrade_decision = 'cloud' THEN 1 ELSE 0 END) as cloud_tasks,
                    SUM(CASE WHEN upgrade_decision = 'local' THEN 1 ELSE 0 END) as local_tasks
                FROM tasks
                WHERE timestamp >= datetime('now', '-' || ? || ' days')
            """, (days,))

            row = cursor.fetchone()
            return dict(row) if row else {}
