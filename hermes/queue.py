"""
Hermes Job Queue System
Handles job queueing and processing
"""

import threading
import time
import logging
from queue import Queue, Empty
from typing import Dict, Any, Optional
from dataclasses import dataclass

from .config import Config
from .database import Database
from .tailscale import get_tailscale_client

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
                logger.error(f"Error processing job: {e}", exc_info=True)

    def _process_job(self, job: Job):
        """Process a single job"""
        logger.info(f"Processing job {job.id}: {job.idea[:100]}...")

        try:
            # Update job status to running
            self.db.update_job_status(job.id, 'running', started_at=time.time())
            self.db.create_job_event(job.id, 'job_started', {
                'idea': job.idea,
                'priority': job.priority
            })

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

            # Update job with final result
            self.db.update_job_status(
                job.id,
                'completed',
                completed_at=time.time(),
                result=final_result.get('result'),
                cost_cents=final_result.get('cost_cents', 0),
                execution_time_ms=final_result.get('execution_time_ms', 0)
            )

            self.db.create_job_event(job.id, 'job_completed', final_result)
            logger.info(f"Job {job.id} completed successfully")

        except Exception as e:
            # Handle error
            error_message = str(e)
            logger.error(f"Job {job.id} failed: {error_message}")

            self.db.update_job_status(
                job.id,
                'failed',
                completed_at=time.time(),
                error_message=error_message
            )

            self.db.create_job_event(job.id, 'job_failed', {
                'error': error_message
            })

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

    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        return {
            'running': self._running,
            'queue_size': self._queue.qsize(),
            'worker_alive': self._worker_thread and self._worker_thread.is_alive()
        }