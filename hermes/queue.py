"""
Hermes Job Queue System
Handles job queueing and processing
"""

import threading
import time
import json
import logging
from queue import Queue, Empty
from typing import Dict, Any, Optional
from dataclasses import dataclass

from .config import Config
from .database import Database
from .tailscale import get_tailscale_client
from .local_execution import LocalExecutionEngine
from .error_handler import handle_error, ErrorCategory, ErrorSeverity
from .notifications import get_notification_manager
from .metalearning.conversation_manager import ConversationManager

logger = logging.getLogger(__name__)

@dataclass
class Job:
    """Job data structure"""
    id: int
    idea: str
    priority: int = 1
    created_at: float = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.metadata is None:
            self.metadata = {}

class JobQueue:
    """Job queue manager"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.tailscale = get_tailscale_client(self.config)
        self.local_engine = LocalExecutionEngine(self.config)
        self.retry_manager = RetryManager(self.config)
        self.notification_manager = get_notification_manager(self.config)
        self.conversation_manager = ConversationManager(self.config)
        self._queue = Queue()
        self._running = False
        self._worker_thread = None

    def start(self):
        """Start the queue worker"""
        if self._running:
            logger.warning("Job queue already running")
            return

        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info("Job queue worker started")

    def stop(self):
        """Stop the queue worker"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        logger.info("Job queue worker stopped")

    def enqueue_job(self, job_id: int, idea: str, priority: int = 1, **metadata):
        """Enqueue a job for processing"""
        job = Job(id=job_id, idea=idea, priority=priority, metadata=metadata)
        self._queue.put(job)
        logger.info(f"Job {job_id} enqueued: {idea[:100]}...")

    def _worker_loop(self):
        """Main worker loop"""
        logger.info("Job queue worker loop started")

        while self._running:
            try:
                # Get job from queue with timeout
                job = self._queue.get(timeout=1)
                self._process_job(job)
                self._queue.task_done()

            except Empty:
                # No jobs available, continue loop
                continue
            except Exception as e:
                handle_error(
                    e,
                    context={
                        'action': 'queue_worker_loop',
                        'queue_size': self._queue.qsize()
                    }
                )

    def _process_job(self, job: Job):
        """Process a single job"""
        logger.info(f"Processing job {job.id}: {job.idea[:100]}...")

        try:
            # Create conversation for meta-learning
            conversation_id = self.conversation_manager.create_conversation(job.id, job.idea)

            # Check if we should gather context first
            if self.conversation_manager.should_gather_context(job.idea):
                logger.info(f"Job {job.id} requires context gathering")
                # For now, skip context gathering in automatic mode
                # In interactive mode, this would pause for user input
                pass

            # Update job status to running
            self.db.update_job_status(job.id, 'running', started_at=time.time())
            self.db.create_job_event(job.id, 'job_started', {
                'idea': job.idea,
                'priority': job.priority,
                'conversation_id': conversation_id
            })

            # Check if we should use local execution or remote Talos
            use_remote = self.config.get('hermes.allow_remote', False) and \
                        self.tailscale.test_connection()

            if use_remote:
                # Execute job on Talos
                result = self.tailscale.run_frugalos_job(
                    job.idea,
                    job.id,
                    **job.metadata
                )

                # Handle success
                talos_job_id = result.get('job_id')
                self.db.create_job_event(job.id, 'talos_job_submitted', {
                    'talos_job_id': talos_job_id,
                    'result': result
                })

                # Wait for completion (simplified for now)
                final_result = self._wait_for_job_completion(job.id, talos_job_id)
            else:
                # Execute locally using local execution engine
                logger.info(f"Executing job {job.id} locally with Hermes")
                local_result = self.local_engine.run_idea(
                    job.idea,
                    job.id,
                    **job.metadata
                )

                if local_result.success:
                    final_result = {
                        'result': local_result.result_data,
                        'cost_cents': local_result.cost_cents,
                        'execution_time_ms': local_result.execution_time_ms,
                        'backend_used': local_result.backend_used,
                        'model_used': local_result.model_used,
                        'validation_passed': local_result.validation_passed,
                        'consensus_score': local_result.consensus_score
                    }
                else:
                    raise Exception(local_result.error_message)

            # Update job with final result
            self.db.update_job_status(
                job.id,
                'completed',
                completed_at=time.time(),
                result=json.dumps(final_result.get('result')),
                cost_cents=final_result.get('cost_cents', 0),
                execution_time_ms=final_result.get('execution_time_ms', 0)
            )

            # Store additional metadata in database
            backend_id = self._get_or_create_backend(final_result.get('backend_used', 'local'))
            self.db.update_job_status(job.id, 'completed', backend_id=backend_id)

            self.db.create_job_event(job.id, 'job_completed', final_result)
            logger.info(f"Job {job.id} completed successfully")

            # Finalize conversation and learn from interaction
            if 'conversation_id' in locals():
                self.conversation_manager.finalize_conversation(
                    conversation_id,
                    {
                        'success': True,
                        'execution_time_ms': final_result.get('execution_time_ms', 0),
                        'backend': final_result.get('backend_used', 'local'),
                        'error_count': 0
                    }
                )

            # Send completion notification
            self.notification_manager.notify_job_completed(
                job.id,
                final_result,
                final_result.get('execution_time_ms', 0) / 1000.0
            )

        except Exception as e:
            # Handle error with comprehensive error reporting
            error_report = handle_error(
                e,
                context={
                    'job_id': job.id,
                    'idea': job.idea,
                    'action': 'job_processing'
                },
                job_id=job.id
            )
            error_message = str(e)

            # Check if we should retry
            if self.retry_manager.should_retry_job(job.id, error_message):
                logger.info(f"Attempting to retry job {job.id}")
                retry_success = self.retry_manager.retry_job(
                    job.id,
                    error_message,
                    lambda: self._execute_job_with_retry(job)
                )

                if retry_success:
                    return  # Success, exit function
                else:
                    logger.error(f"Retries exhausted for job {job.id}")

            # Mark as failed
            self.db.update_job_status(
                job.id,
                'failed',
                completed_at=time.time(),
                error_message=error_message
            )

            self.db.create_job_event(job.id, 'job_failed', {
                'error': error_message
            })

            # Finalize conversation with failure
            if 'conversation_id' in locals():
                self.conversation_manager.finalize_conversation(
                    conversation_id,
                    {
                        'success': False,
                        'error_message': error_message,
                        'error_count': 1
                    }
                )

            # Send failure notification
            self.notification_manager.notify_job_failed(
                job.id,
                error_message,
                {
                    'category': error_report.category.value if 'error_report' in locals() else 'unknown',
                    'severity': error_report.severity.value if 'error_report' in locals() else 'medium',
                    'retry_attempt': len(self.retry_manager._get_retry_history(job.id).attempts) if hasattr(self.retry_manager, '_get_retry_history') else 0
                }
            )

    def _wait_for_job_completion(self, job_id: int, talos_job_id: str) -> Dict[str, Any]:
        """Wait for Talos job completion"""
        try:
            # For now, simulate completion
            # In real implementation, this would poll Talos
            time.sleep(2)  # Simulate work

            return {
                'result': f"Simulated result for job {job_id}",
                'cost_cents': 0,
                'execution_time_ms': 2000,
                'talos_job_id': talos_job_id
            }

        except Exception as e:
            logger.error(f"Error waiting for job completion: {e}")
            raise

    def _get_or_create_backend(self, backend_name: str) -> int:
        """Get or create backend ID"""
        try:
            # Try to find existing backend
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT id FROM backends WHERE name = ?",
                    (backend_name,)
                )
                row = cursor.fetchone()
                if row:
                    return row['id']

                # Create new backend
                cursor = conn.execute(
                    """INSERT INTO backends (name, type, status, is_default)
                       VALUES (?, ?, ?, ?)""",
                    (backend_name, 'frugalos', 'active', False)
                )
                backend_id = cursor.lastrowid
                conn.commit()
                return backend_id

        except Exception as e:
            logger.error(f"Failed to get/create backend {backend_name}: {e}")
            return None

    def _execute_job_with_retry(self, job: Job) -> Dict[str, Any]:
        """Execute job logic (extracted for retry)"""
        # This is the core job execution logic that can be retried
        use_remote = self.config.get('hermes.allow_remote', False) and \
                    self.tailscale.test_connection()

        if use_remote:
            # Execute job on Talos
            result = self.tailscale.run_frugalos_job(
                job.idea,
                job.id,
                **job.metadata
            )

            # Handle success
            talos_job_id = result.get('job_id')
            self.db.create_job_event(job.id, 'talos_job_submitted', {
                'talos_job_id': talos_job_id,
                'result': result
            })

            # Wait for completion (simplified for now)
            return self._wait_for_job_completion(job.id, talos_job_id)
        else:
            # Execute locally using local execution engine
            logger.info(f"Executing job {job.id} locally with Hermes")
            local_result = self.local_engine.run_idea(
                job.idea,
                job.id,
                **job.metadata
            )

            if local_result.success:
                return {
                    'result': local_result.result_data,
                    'cost_cents': local_result.cost_cents,
                    'execution_time_ms': local_result.execution_time_ms,
                    'backend_used': local_result.backend_used,
                    'model_used': local_result.model_used,
                    'validation_passed': local_result.validation_passed,
                    'consensus_score': local_result.consensus_score
                }
            else:
                raise Exception(local_result.error_message)

    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        return {
            'running': self._running,
            'queue_size': self._queue.qsize(),
            'worker_alive': self._worker_thread and self._worker_thread.is_alive(),
            'local_available': self.local_engine.test_local_execution(),
            'talos_connected': self.tailscale.test_connection(),
            'available_models': self.local_engine.get_available_models(),
            'retry_stats': self.retry_manager.get_retry_stats()
        }