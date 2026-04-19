#!/usr/bin/env python3
"""
Real-Time Streaming Module for Hermes AI Assistant
Provides Server-Sent Events (SSE) streaming for real-time token delivery
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, AsyncGenerator, Optional, List, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import uuid
from datetime import datetime

from fastapi import HTTPException, status
from starlette.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

class StreamEventType(Enum):
    """Types of streaming events"""
    TOKEN = "token"
    ERROR = "error"
    COMPLETED = "completed"
    METADATA = "metadata"
    THINKING = "thinking"
    FUNCTION_CALL = "function_call"
    FUNCTION_RESULT = "function_result"

@dataclass
class StreamEvent:
    """Streaming event data structure"""
    event_type: StreamEventType
    data: Dict[str, Any]
    timestamp: float
    request_id: str
    sequence_id: int

    def to_sse_format(self) -> str:
        """Convert event to Server-Sent Events format"""
        event_data = {
            "type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp,
            "requestId": self.request_id,
            "sequenceId": self.sequence_id
        }

        # Format as SSE
        lines = [f"data: {json.dumps(event_data)}"]
        if self.event_type in [StreamEventType.ERROR, StreamEventType.COMPLETED]:
            lines.append(f"event: {self.event_type.value}")

        return "\n".join(lines) + "\n\n"

class StreamStats:
    """Streaming statistics and monitoring"""

    def __init__(self):
        self.start_time = time.time()
        self.token_count = 0
        self.event_count = 0
        self.errors = []
        self.thinking_periods = []
        self.function_calls = []

    def add_token(self, token: str):
        """Add a token to the stream"""
        self.token_count += len(token.split())
        self.event_count += 1

    def add_error(self, error: str):
        """Add an error to the stream"""
        self.errors.append({
            "error": error,
            "timestamp": time.time()
        })
        self.event_count += 1

    def start_thinking(self):
        """Start a thinking period"""
        self.thinking_periods.append({"start": time.time()})

    def end_thinking(self):
        """End the current thinking period"""
        if self.thinking_periods and "end" not in self.thinking_periods[-1]:
            self.thinking_periods[-1]["end"] = time.time()

    def add_function_call(self, function_name: str, args: Dict[str, Any]):
        """Add a function call to the stream"""
        self.function_calls.append({
            "function": function_name,
            "args": args,
            "timestamp": time.time()
        })
        self.event_count += 1

    def get_summary(self) -> Dict[str, Any]:
        """Get streaming statistics summary"""
        total_thinking_time = sum(
            period.get("end", time.time()) - period["start"]
            for period in self.thinking_periods
        )

        return {
            "duration": time.time() - self.start_time,
            "tokenCount": self.token_count,
            "eventCount": self.event_count,
            "errorCount": len(self.errors),
            "thinkingTime": total_thinking_time,
            "functionCallCount": len(self.function_calls),
            "averageTokensPerSecond": self.token_count / max(1, time.time() - self.start_time)
        }

class StreamingManager:
    """Manages real-time streaming connections and events"""

    def __init__(self):
        self.active_streams: Dict[str, 'ActiveStream'] = {}
        self.stream_history: List[Dict[str, Any]] = []
        self.max_concurrent_streams = 1000

    async def create_stream(self, request_id: Optional[str] = None) -> 'ActiveStream':
        """Create a new streaming session"""
        if request_id is None:
            request_id = str(uuid.uuid4())

        # Check concurrent stream limit
        if len(self.active_streams) >= self.max_concurrent_streams:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Maximum concurrent streams reached"
            )

        stream = ActiveStream(request_id=request_id, manager=self)
        self.active_streams[request_id] = stream

        logger.info(f"Created stream {request_id}. Active streams: {len(self.active_streams)}")
        return stream

    async def close_stream(self, request_id: str):
        """Close a streaming session"""
        if request_id in self.active_streams:
            stream = self.active_streams[request_id]
            await stream.close()
            del self.active_streams[request_id]

            # Add to history
            self.stream_history.append({
                "requestId": request_id,
                "stats": stream.stats.get_summary(),
                "closedAt": datetime.utcnow().isoformat()
            })

            # Keep only last 1000 streams in history
            if len(self.stream_history) > 1000:
                self.stream_history = self.stream_history[-1000:]

            logger.info(f"Closed stream {request_id}. Active streams: {len(self.active_streams)}")

    def get_stream_stats(self) -> Dict[str, Any]:
        """Get overall streaming statistics"""
        return {
            "activeStreams": len(self.active_streams),
            "maxConcurrentStreams": self.max_concurrent_streams,
            "totalStreams": len(self.stream_history),
            "averageTokensPerSecond": self._calculate_average_tps(),
            "uptime": time.time() - getattr(self, '_start_time', time.time())
        }

    def _calculate_average_tps(self) -> float:
        """Calculate average tokens per second across all active streams"""
        if not self.active_streams:
            return 0.0

        total_tps = sum(
            stream.stats.get_summary()["averageTokensPerSecond"]
            for stream in self.active_streams.values()
        )

        return total_tps / len(self.active_streams)

class ActiveStream:
    """Represents an active streaming connection"""

    def __init__(self, request_id: str, manager: StreamingManager):
        self.request_id = request_id
        self.manager = manager
        self.stats = StreamStats()
        self.sequence_id = 0
        self.is_closed = False
        self.event_queue = asyncio.Queue()
        self.subscribers: List[Callable] = []

    async def send_token(self, token: str, metadata: Optional[Dict[str, Any]] = None):
        """Send a token event"""
        if self.is_closed:
            return

        event = StreamEvent(
            event_type=StreamEventType.TOKEN,
            data={
                "token": token,
                "metadata": metadata or {}
            },
            timestamp=time.time(),
            request_id=self.request_id,
            sequence_id=self._next_sequence_id()
        )

        await self._send_event(event)
        self.stats.add_token(token)

    async def send_thinking(self, is_thinking: bool):
        """Send a thinking status event"""
        if self.is_closed:
            return

        if is_thinking:
            self.stats.start_thinking()
        else:
            self.stats.end_thinking()

        event = StreamEvent(
            event_type=StreamEventType.THINKING,
            data={"thinking": is_thinking},
            timestamp=time.time(),
            request_id=self.request_id,
            sequence_id=self._next_sequence_id()
        )

        await self._send_event(event)

    async def send_function_call(self, function_name: str, args: Dict[str, Any]):
        """Send a function call event"""
        if self.is_closed:
            return

        self.stats.add_function_call(function_name, args)

        event = StreamEvent(
            event_type=StreamEventType.FUNCTION_CALL,
            data={
                "function": function_name,
                "arguments": args
            },
            timestamp=time.time(),
            request_id=self.request_id,
            sequence_id=self._next_sequence_id()
        )

        await self._send_event(event)

    async def send_function_result(self, result: Dict[str, Any]):
        """Send a function result event"""
        if self.is_closed:
            return

        event = StreamEvent(
            event_type=StreamEventType.FUNCTION_RESULT,
            data={"result": result},
            timestamp=time.time(),
            request_id=self.request_id,
            sequence_id=self._next_sequence_id()
        )

        await self._send_event(event)

    async def send_metadata(self, metadata: Dict[str, Any]):
        """Send metadata event"""
        if self.is_closed:
            return

        event = StreamEvent(
            event_type=StreamEventType.METADATA,
            data=metadata,
            timestamp=time.time(),
            request_id=self.request_id,
            sequence_id=self._next_sequence_id()
        )

        await self._send_event(event)

    async def send_error(self, error: str, error_code: Optional[str] = None):
        """Send an error event"""
        if self.is_closed:
            return

        self.stats.add_error(error)

        event = StreamEvent(
            event_type=StreamEventType.ERROR,
            data={
                "error": error,
                "errorCode": error_code or "UNKNOWN_ERROR"
            },
            timestamp=time.time(),
            request_id=self.request_id,
            sequence_id=self._next_sequence_id()
        )

        await self._send_event(event)

    async def complete(self, final_metadata: Optional[Dict[str, Any]] = None):
        """Complete the stream"""
        if self.is_closed:
            return

        stats = self.stats.get_summary()

        event = StreamEvent(
            event_type=StreamEventType.COMPLETED,
            data={
                "stats": stats,
                "metadata": final_metadata or {}
            },
            timestamp=time.time(),
            request_id=self.request_id,
            sequence_id=self._next_sequence_id()
        )

        await self._send_event(event)
        await self.close()

    async def _send_event(self, event: StreamEvent):
        """Send an event to the queue"""
        try:
            self.event_queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(f"Event queue full for stream {self.request_id}")

    def _next_sequence_id(self) -> int:
        """Get next sequence ID"""
        self.sequence_id += 1
        return self.sequence_id

    async def close(self):
        """Close the stream"""
        if not self.is_closed:
            self.is_closed = True
            await self.manager.close_stream(self.request_id)

    async def event_generator(self) -> AsyncGenerator[str, None]:
        """Generate SSE events for the stream"""
        try:
            # Send initial metadata
            await self.send_metadata({
                "streamId": self.request_id,
                "startTime": time.time(),
                "serverInfo": {
                    "version": "1.0.0",
                    "capabilities": ["tokens", "thinking", "function_calls"]
                }
            })

            # Generate events from queue
            while not self.is_closed:
                try:
                    # Wait for event with timeout
                    event = await asyncio.wait_for(
                        self.event_queue.get(),
                        timeout=1.0
                    )
                    yield event.to_sse_format()
                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': time.time()})}\n\n"

        except Exception as e:
            logger.error(f"Error in stream generator for {self.request_id}: {e}")
            await self.send_error(str(e), "STREAM_ERROR")
        finally:
            await self.close()

# Global streaming manager instance
streaming_manager = StreamingManager()

async def create_streaming_response(
    request_id: Optional[str] = None
) -> StreamingResponse:
    """Create a FastAPI streaming response"""
    stream = await streaming_manager.create_stream(request_id)

    return StreamingResponse(
        stream.event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

async def initialize_streaming_orchestrator(orchestrator, context_manager):
    """Initialize streaming orchestrator with dependencies"""
    # Store dependencies in streaming manager
    streaming_manager.orchestrator = orchestrator
    streaming_manager.context_manager = context_manager
    logger.info("Streaming orchestrator initialized successfully")