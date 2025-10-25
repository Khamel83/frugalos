"""
Autonomous Job Scheduler
Intelligent scheduling of jobs based on patterns, priorities, and system state
"""

import logging
import time
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from queue import PriorityQueue
import heapq

from ..config import Config
from ..database import Database
from ..logger import get_logger
from ..metalearning.pattern_engine import PatternEngine

logger = get_logger('autonomous.scheduler')

class TaskPriority(Enum):
    """Task priority levels"""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5

@dataclass
class ScheduledTask:
    """A scheduled task with metadata"""
    task_id: str
    idea: str
    priority: TaskPriority
    scheduled_time: datetime
    deadline: Optional[datetime]
    recurrence: Optional[str]  # cron-like: 'daily', 'weekly', 'hourly'
    dependencies: List[str]
    context: Dict[str, Any]
    auto_generated: bool
    confidence_score: float

    def __lt__(self, other):
        """For priority queue comparison"""
        # Lower priority number = higher priority
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        # Earlier scheduled time = higher priority
        return self.scheduled_time < other.scheduled_time

class AutonomousScheduler:
    """Autonomous job scheduling system"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.pattern_engine = PatternEngine(config)
        self.logger = get_logger('autonomous_scheduler')

        # Scheduler configuration
        self.enabled = self.config.get('autonomous.scheduler.enabled', True)
        self.check_interval = self.config.get('autonomous.scheduler.interval', 60)
        self.max_concurrent = self.config.get('autonomous.scheduler.max_concurrent', 3)
        self.learning_mode = self.config.get('autonomous.scheduler.learning_mode', True)

        # Scheduling state
        self._task_queue = []  # Heap queue for priority scheduling
        self._scheduled_tasks = {}  # task_id -> ScheduledTask
        self._running_tasks = {}  # task_id -> job_id
        self._completed_tasks = {}  # task_id -> result
        self._task_history = []  # History of executed tasks

        # Scheduler thread
        self._running = False
        self._scheduler_thread = None

        # Load scheduled tasks from database
        self._load_scheduled_tasks()

    def _load_scheduled_tasks(self):
        """Load scheduled tasks from database"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM scheduled_tasks
                    WHERE status = 'pending' OR status = 'scheduled'
                    ORDER BY scheduled_time
                """)

                for row in cursor.fetchall():
                    task = ScheduledTask(
                        task_id=str(row['id']),
                        idea=row['idea'],
                        priority=TaskPriority[row['priority']],
                        scheduled_time=datetime.fromisoformat(row['scheduled_time']),
                        deadline=datetime.fromisoformat(row['deadline']) if row['deadline'] else None,
                        recurrence=row['recurrence'],
                        dependencies=row['dependencies'].split(',') if row['dependencies'] else [],
                        context=eval(row['context']) if row['context'] else {},
                        auto_generated=bool(row['auto_generated']),
                        confidence_score=row['confidence_score'] or 0.5
                    )

                    self.schedule_task(task)

            self.logger.info(f"Loaded {len(self._scheduled_tasks)} scheduled tasks")

        except Exception as e:
            self.logger.error(f"Error loading scheduled tasks: {e}")

    def start_scheduler(self):
        """Start autonomous scheduler"""
        if self._running:
            self.logger.warning("Scheduler already running")
            return

        if not self.enabled:
            self.logger.info("Autonomous scheduler is disabled")
            return

        self._running = True
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        self.logger.info("Autonomous scheduler started")

    def stop_scheduler(self):
        """Stop autonomous scheduler"""
        self._running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
        self.logger.info("Autonomous scheduler stopped")

    def _scheduler_loop(self):
        """Main scheduler loop"""
        while self._running:
            try:
                self._process_scheduled_tasks()
                self._learn_from_patterns()
                self._generate_proactive_tasks()
                time.sleep(self.check_interval)
            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {e}")
                time.sleep(self.check_interval)

    def _process_scheduled_tasks(self):
        """Process tasks that are ready to run"""
        now = datetime.now()
        tasks_to_execute = []

        # Find tasks ready to execute
        while self._task_queue and self._task_queue[0].scheduled_time <= now:
            task = heapq.heappop(self._task_queue)

            # Check if we have capacity
            if len(self._running_tasks) >= self.max_concurrent:
                # Put it back and wait
                heapq.heappush(self._task_queue, task)
                break

            # Check dependencies
            if self._check_dependencies(task):
                tasks_to_execute.append(task)
            else:
                # Dependencies not met, reschedule for later
                task.scheduled_time = now + timedelta(minutes=5)
                heapq.heappush(self._task_queue, task)

        # Execute ready tasks
        for task in tasks_to_execute:
            self._execute_task(task)

    def _check_dependencies(self, task: ScheduledTask) -> bool:
        """Check if task dependencies are met"""
        if not task.dependencies:
            return True

        for dep_id in task.dependencies:
            if dep_id not in self._completed_tasks:
                return False

        return True

    def _execute_task(self, task: ScheduledTask):
        """Execute a scheduled task"""
        try:
            self.logger.info(
                f"Executing scheduled task: {task.task_id} - {task.idea[:50]}..."
            )

            # Create job in queue
            from ..queue import JobQueue
            queue = JobQueue(self.config)

            job_id = self.db.create_job(task.idea)
            queue.enqueue_job(job_id, task.idea, priority=task.priority.value, **task.context)

            # Track running task
            self._running_tasks[task.task_id] = job_id

            # Schedule recurrence if needed
            if task.recurrence:
                self._schedule_recurrence(task)

            # Record execution in history
            self._task_history.append({
                'task_id': task.task_id,
                'idea': task.idea,
                'scheduled_time': task.scheduled_time,
                'executed_time': datetime.now(),
                'priority': task.priority.value,
                'auto_generated': task.auto_generated
            })

        except Exception as e:
            self.logger.error(f"Error executing task {task.task_id}: {e}")

    def _schedule_recurrence(self, task: ScheduledTask):
        """Schedule next occurrence of recurring task"""
        if not task.recurrence:
            return

        # Calculate next run time
        next_time = self._calculate_next_run(task.scheduled_time, task.recurrence)

        # Create new task for next occurrence
        next_task = ScheduledTask(
            task_id=f"{task.task_id}_recur_{int(next_time.timestamp())}",
            idea=task.idea,
            priority=task.priority,
            scheduled_time=next_time,
            deadline=None,
            recurrence=task.recurrence,
            dependencies=[],
            context=task.context,
            auto_generated=task.auto_generated,
            confidence_score=task.confidence_score
        )

        self.schedule_task(next_task)

    def _calculate_next_run(self, current_time: datetime, recurrence: str) -> datetime:
        """Calculate next run time based on recurrence pattern"""
        if recurrence == 'hourly':
            return current_time + timedelta(hours=1)
        elif recurrence == 'daily':
            return current_time + timedelta(days=1)
        elif recurrence == 'weekly':
            return current_time + timedelta(weeks=1)
        elif recurrence == 'monthly':
            # Approximate month as 30 days
            return current_time + timedelta(days=30)
        else:
            # Default to daily
            return current_time + timedelta(days=1)

    def _learn_from_patterns(self):
        """Learn from execution patterns to optimize scheduling"""
        if not self.learning_mode:
            return

        try:
            # Analyze recent task history
            if len(self._task_history) < 10:
                return

            recent_tasks = self._task_history[-50:]

            # Find patterns in execution times
            hourly_distribution = [0] * 24
            for task in recent_tasks:
                hour = task['executed_time'].hour
                hourly_distribution[hour] += 1

            # Find peak hours
            peak_hour = hourly_distribution.index(max(hourly_distribution))

            # Store learned pattern
            self.logger.debug(f"Learned pattern: Peak execution hour is {peak_hour}")

            # This information can be used to optimize future scheduling

        except Exception as e:
            self.logger.error(f"Error learning from patterns: {e}")

    def _generate_proactive_tasks(self):
        """Generate proactive tasks based on patterns"""
        if not self.learning_mode:
            return

        try:
            # Use pattern engine to suggest tasks
            # This would analyze user behavior and suggest relevant tasks

            # For now, this is a placeholder for proactive task generation
            pass

        except Exception as e:
            self.logger.error(f"Error generating proactive tasks: {e}")

    def schedule_task(
        self,
        task: ScheduledTask,
        persist: bool = True
    ):
        """
        Schedule a task for execution

        Args:
            task: Task to schedule
            persist: Whether to persist to database
        """
        try:
            # Add to queue
            heapq.heappush(self._task_queue, task)
            self._scheduled_tasks[task.task_id] = task

            # Persist to database
            if persist:
                self._persist_task(task)

            self.logger.info(
                f"Scheduled task {task.task_id} for {task.scheduled_time} "
                f"(priority: {task.priority.name})"
            )

        except Exception as e:
            self.logger.error(f"Error scheduling task: {e}")

    def _persist_task(self, task: ScheduledTask):
        """Persist task to database"""
        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO scheduled_tasks (
                        id, idea, priority, scheduled_time, deadline, recurrence,
                        dependencies, context, auto_generated, confidence_score, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task.task_id,
                    task.idea,
                    task.priority.name,
                    task.scheduled_time.isoformat(),
                    task.deadline.isoformat() if task.deadline else None,
                    task.recurrence,
                    ','.join(task.dependencies) if task.dependencies else None,
                    str(task.context),
                    int(task.auto_generated),
                    task.confidence_score,
                    'scheduled'
                ))
                conn.commit()

        except Exception as e:
            self.logger.error(f"Error persisting task: {e}")

    def cancel_task(self, task_id: str):
        """Cancel a scheduled task"""
        if task_id in self._scheduled_tasks:
            task = self._scheduled_tasks[task_id]

            # Remove from queue (requires rebuilding heap)
            self._task_queue = [t for t in self._task_queue if t.task_id != task_id]
            heapq.heapify(self._task_queue)

            # Remove from tracking
            del self._scheduled_tasks[task_id]

            # Update database
            try:
                with self.db.get_connection() as conn:
                    conn.execute(
                        "UPDATE scheduled_tasks SET status = 'cancelled' WHERE id = ?",
                        (task_id,)
                    )
                    conn.commit()
            except Exception as e:
                self.logger.error(f"Error cancelling task in database: {e}")

            self.logger.info(f"Cancelled task {task_id}")

    def get_scheduled_tasks(self) -> List[ScheduledTask]:
        """Get all scheduled tasks"""
        return sorted(self._task_queue, key=lambda t: t.scheduled_time)

    def get_running_tasks(self) -> Dict[str, int]:
        """Get currently running tasks"""
        return dict(self._running_tasks)

    def get_scheduler_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics"""
        return {
            'enabled': self.enabled,
            'running': self._running,
            'scheduled_tasks': len(self._scheduled_tasks),
            'running_tasks': len(self._running_tasks),
            'completed_tasks': len(self._completed_tasks),
            'total_executed': len(self._task_history),
            'max_concurrent': self.max_concurrent,
            'next_task': {
                'task_id': self._task_queue[0].task_id,
                'scheduled_time': self._task_queue[0].scheduled_time.isoformat(),
                'priority': self._task_queue[0].priority.name
            } if self._task_queue else None
        }

    def schedule_at(
        self,
        idea: str,
        scheduled_time: datetime,
        priority: TaskPriority = TaskPriority.NORMAL,
        **kwargs
    ) -> str:
        """
        Schedule a task for a specific time

        Args:
            idea: Task description
            scheduled_time: When to execute
            priority: Task priority
            **kwargs: Additional task parameters

        Returns:
            Task ID
        """
        task_id = f"task_{int(datetime.now().timestamp())}_{hash(idea) % 10000}"

        task = ScheduledTask(
            task_id=task_id,
            idea=idea,
            priority=priority,
            scheduled_time=scheduled_time,
            deadline=kwargs.get('deadline'),
            recurrence=kwargs.get('recurrence'),
            dependencies=kwargs.get('dependencies', []),
            context=kwargs.get('context', {}),
            auto_generated=kwargs.get('auto_generated', False),
            confidence_score=kwargs.get('confidence_score', 1.0)
        )

        self.schedule_task(task)
        return task_id

    def schedule_recurring(
        self,
        idea: str,
        recurrence: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        start_time: Optional[datetime] = None
    ) -> str:
        """
        Schedule a recurring task

        Args:
            idea: Task description
            recurrence: Recurrence pattern (hourly, daily, weekly, monthly)
            priority: Task priority
            start_time: When to start (defaults to now)

        Returns:
            Task ID
        """
        start = start_time or datetime.now()

        return self.schedule_at(
            idea=idea,
            scheduled_time=start,
            priority=priority,
            recurrence=recurrence
        )
