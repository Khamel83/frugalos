#!/usr/bin/env python3
"""
Streaming API Routes for Hermes AI Assistant
Provides real-time streaming endpoints for AI responses
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import logging
import asyncio

from ..streaming.streaming_manager import streaming_manager, create_streaming_response
from ..streaming.streaming_orchestrator import get_streaming_orchestrator
from ..security.auth_service import get_current_user, User
from ..monitoring.performance_monitor import performance_monitor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/stream", tags=["streaming"])

class StreamingChatRequest(BaseModel):
    """Request model for streaming chat"""
    conversation_id: str = Field(..., description="Conversation ID")
    message: str = Field(..., min_length=1, max_length=10000, description="Message to process")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    model_preferences: Optional[Dict[str, Any]] = Field(None, description="Model preferences")
    stream_options: Optional[Dict[str, Any]] = Field(None, description="Streaming options")

class StreamingChatResponse(BaseModel):
    """Response model for streaming chat initiation"""
    stream_id: str = Field(..., description="Stream ID")
    conversation_id: str = Field(..., description="Conversation ID")
    status: str = Field(..., description="Stream status")

class StreamInfo(BaseModel):
    """Stream information model"""
    stream_id: str
    conversation_id: str
    status: str
    stats: Dict[str, Any]
    created_at: str

class StreamingStats(BaseModel):
    """Streaming statistics model"""
    active_streams: int
    max_concurrent_streams: int
    total_streams: int
    average_tokens_per_second: float
    uptime: float

@router.post("/chat/{conversation_id}")
async def start_chat_stream(
    conversation_id: str,
    request: StreamingChatRequest,
    current_user: User = Depends(get_current_user)
) -> StreamingResponse:
    """
    Start a streaming chat response for a conversation

    This endpoint provides real-time token streaming for AI responses.
    The response uses Server-Sent Events (SSE) format.
    """

    try:
        # Validate conversation ID matches
        if request.conversation_id != conversation_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Conversation ID mismatch"
            )

        # Create streaming response
        stream_response = await create_streaming_response()

        # Start background processing task
        async def process_stream():
            try:
                stream = await streaming_manager.create_stream()

                # Get streaming orchestrator
                orchestrator = get_streaming_orchestrator()

                # Create streaming request
                from ..streaming.streaming_orchestrator import StreamingRequest
                streaming_request = StreamingRequest(
                    conversation_id=conversation_id,
                    message=request.message,
                    context=request.context,
                    model_preferences=request.model_preferences,
                    stream_options=request.stream_options,
                    user_id=current_user.user_id
                )

                # Process request
                await orchestrator.process_streaming_request(streaming_request, stream)

            except Exception as e:
                logger.error(f"Error in background streaming task: {e}")
                if 'stream' in locals():
                    await stream.send_error(str(e), "PROCESSING_ERROR")
                    await stream.close()

        # Start background task
        asyncio.create_task(process_stream())

        # Log request
        await performance_monitor.log_api_request(
            endpoint="/api/v1/stream/chat",
            method="POST",
            user_id=current_user.user_id,
            request_size=len(str(request)),
            status_code=200
        )

        return stream_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting chat stream: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start streaming response"
        )

@router.get("/status/{stream_id}")
async def get_stream_status(
    stream_id: str,
    current_user: User = Depends(get_current_user)
) -> StreamInfo:
    """
    Get status of a specific stream
    """

    try:
        # Check if stream exists and is active
        if stream_id not in streaming_manager.active_streams:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stream not found or completed"
            )

        stream = streaming_manager.active_streams[stream_id]

        return StreamInfo(
            stream_id=stream_id,
            conversation_id=getattr(stream, 'conversation_id', 'unknown'),
            status="active" if not stream.is_closed else "closed",
            stats=stream.stats.get_summary(),
            created_at=str(stream.stats.start_time)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting stream status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get stream status"
        )

@router.delete("/cancel/{conversation_id}")
async def cancel_stream(
    conversation_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Cancel an active streaming request for a conversation
    """

    try:
        # Get streaming orchestrator
        orchestrator = get_streaming_orchestrator()

        # Cancel streaming request
        cancelled = await orchestrator.cancel_streaming_request(conversation_id)

        if cancelled:
            return {
                "success": True,
                "message": f"Streaming request for conversation {conversation_id} cancelled",
                "conversation_id": conversation_id
            }
        else:
            return {
                "success": False,
                "message": f"No active streaming request found for conversation {conversation_id}",
                "conversation_id": conversation_id
            }

    except Exception as e:
        logger.error(f"Error cancelling stream: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel streaming request"
        )

@router.get("/stats")
async def get_streaming_stats(
    current_user: User = Depends(get_current_user)
) -> StreamingStats:
    """
    Get overall streaming statistics
    """

    try:
        stats = streaming_manager.get_stream_stats()

        return StreamingStats(**stats)

    except Exception as e:
        logger.error(f"Error getting streaming stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get streaming statistics"
        )

@router.get("/active")
async def get_active_streams(
    current_user: User = Depends(get_current_user)
) -> List[StreamInfo]:
    """
    Get information about all active streaming requests
    """

    try:
        # Get streaming orchestrator
        orchestrator = get_streaming_orchestrator()

        # Get active streams info
        active_streams = orchestrator.get_active_streams_info()

        return [
            StreamInfo(
                stream_id=stream_info["requestId"],
                conversation_id=stream_info["conversationId"],
                status="active",
                stats=stream_info["stats"],
                created_at=str(stream_info["stats"]["start_time"])
            )
            for stream_info in active_streams
        ]

    except Exception as e:
        logger.error(f"Error getting active streams: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get active streams"
        )

@router.post("/test")
async def test_streaming(
    current_user: User = Depends(get_current_user)
) -> StreamingResponse:
    """
    Test endpoint for streaming functionality
    Returns a simple streaming response with test data
    """

    try:
        async def test_generator():
            test_stream = await streaming_manager.create_stream()

            # Send test tokens
            test_message = "Hello! This is a test streaming response from Hermes AI Assistant. "
            test_message += "Each word is being streamed as a separate token to demonstrate real-time delivery. "
            test_message += "The streaming system supports various event types including tokens, thinking indicators, "
            test_message += "function calls, and metadata. This concludes the test streaming response."

            words = test_message.split()

            for i, word in enumerate(words):
                await asyncio.sleep(0.1)  # Simulate processing delay
                await test_stream.send_token(word + (" " if i < len(words) - 1 else ""))

            # Complete the stream
            await test_stream.complete({"test": True, "wordCount": len(words)})

        return StreamingResponse(
            test_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*"
            }
        )

    except Exception as e:
        logger.error(f"Error in test streaming: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create test streaming response"
        )