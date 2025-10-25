"""
Hermes Event Streaming System
Handles server-sent events for real-time updates
"""

import json
import logging
import time
from queue import Queue, Empty
from typing import Dict, Any, Optional, Iterator
from threading import Lock

logger = logging.getLogger(__name__)

class EventStreamer:
    """Manages server-sent events for real-time updates"""

    def __init__(self):
        self._subscribers = {}
        self._lock = Lock()

    def subscribe_to_job(self, job_id: int) -> Iterator[str]:
        """Subscribe to events for a specific job"""
        queue = Queue()

        with self._lock:
            if job_id not in self._subscribers:
                self._subscribers[job_id] = []
            self._subscribers[job_id].append(queue)

        try:
            while True:
                try:
                    event = queue.get(timeout=30)  # 30 second timeout
                    yield f"data: {json.dumps(event)}\n\n"
                except Empty:
                    # Send keepalive
                    yield f"data: {{'type': 'keepalive', 'timestamp': {time.time()}}}\n\n"
        finally:
            # Cleanup subscriber
            with self._lock:
                if job_id in self._subscribers:
                    try:
                        self._subscribers[job_id].remove(queue)
                        if not self._subscribers[job_id]:
                            del self._subscribers[job_id]
                    except ValueError:
                        pass

    def broadcast_job_event(self, job_id: int, event: Dict[str, Any]):
        """Broadcast event to all subscribers of a job"""
        with self._lock:
            if job_id in self._subscribers:
                event['timestamp'] = time.time()
                for queue in self._subscribers[job_id]:
                    try:
                        queue.put_nowait(event)
                    except:
                        # Queue is full, remove subscriber
                        try:
                            self._subscribers[job_id].remove(queue)
                        except ValueError:
                            pass

    def stream_job_events(self, job_id: int) -> Iterator[str]:
        """Stream events for a job (alias for subscribe_to_job)"""
        return self.subscribe_to_job(job_id)

# Global event streamer instance
_event_streamer = EventStreamer()

def get_event_streamer() -> EventStreamer:
    """Get the global event streamer instance"""
    return _event_streamer