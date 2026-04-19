#!/usr/bin/env python3
"""
Streaming Orchestrator for Hermes AI Assistant
Integrates streaming with model orchestration for real-time AI responses
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, AsyncGenerator, Callable
from dataclasses import dataclass
import json
import time

from ..models.model_orchestrator import ModelOrchestrator, ModelRequest, ModelResponse
from ..conversation.context_manager import ContextManager
from .streaming_manager import ActiveStream, StreamEventType, streaming_manager

logger = logging.getLogger(__name__)

@dataclass
class StreamingRequest:
    """Request for streaming AI response"""
    conversation_id: str
    message: str
    context: Optional[Dict[str, Any]] = None
    model_preferences: Optional[Dict[str, Any]] = None
    stream_options: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None

class StreamingOrchestrator:
    """Orchestrates streaming AI responses with model integration"""

    def __init__(self, model_orchestrator: ModelOrchestrator, context_manager: ContextManager):
        self.model_orchestrator = model_orchestrator
        self.context_manager = context_manager
        self.active_streaming_requests: Dict[str, ActiveStream] = {}

    async def process_streaming_request(
        self,
        request: StreamingRequest,
        stream: ActiveStream
    ) -> Dict[str, Any]:
        """Process a streaming request and send real-time events"""

        logger.info(f"Starting streaming request for conversation {request.conversation_id}")
        self.active_streaming_requests[request.conversation_id] = stream

        try:
            # Send initial metadata
            await stream.send_metadata({
                "conversationId": request.conversation_id,
                "message": request.message[:100] + "..." if len(request.message) > 100 else request.message,
                "startTime": time.time(),
                "userId": request.user_id
            })

            # Start thinking phase
            await stream.send_thinking(True)

            # Get conversation context
            conversation_context = await self._get_conversation_context(
                request.conversation_id,
                request.context
            )

            # Create model request
            model_request = ModelRequest(
                prompt=request.message,
                context=conversation_context,
                conversation_id=request.conversation_id,
                user_id=request.user_id,
                options=request.model_preferences or {}
            )

            # Send thinking completion
            await stream.send_thinking(False)

            # Process with streaming model response
            await self._process_model_streaming(model_request, stream)

            # Get final statistics
            stats = stream.stats.get_summary()

            logger.info(f"Completed streaming request for conversation {request.conversation_id}: {stats}")

            return {
                "success": True,
                "stats": stats,
                "conversationId": request.conversation_id
            }

        except Exception as e:
            logger.error(f"Error processing streaming request for {request.conversation_id}: {e}")
            await stream.send_error(str(e), "PROCESSING_ERROR")

            return {
                "success": False,
                "error": str(e),
                "conversationId": request.conversation_id
            }

        finally:
            # Clean up
            if request.conversation_id in self.active_streaming_requests:
                del self.active_streaming_requests[request.conversation_id]

    async def _process_model_streaming(
        self,
        model_request: ModelRequest,
        stream: ActiveStream
    ):
        """Process model request with streaming response"""

        # Check if model supports streaming
        selected_model = await self.model_orchestrator.select_model(model_request)

        if hasattr(selected_model, 'stream_response'):
            # Model supports native streaming
            await self._native_model_streaming(selected_model, model_request, stream)
        else:
            # Fallback to simulated streaming
            await self._simulated_model_streaming(selected_model, model_request, stream)

    async def _native_model_streaming(
        self,
        model,
        model_request: ModelRequest,
        stream: ActiveStream
    ):
        """Handle native model streaming (e.g., OpenAI, Anthropic)"""

        try:
            # Get streaming response from model
            async for chunk in model.stream_response(model_request):

                if hasattr(chunk, 'choices') and chunk.choices:
                    # OpenAI-style streaming
                    delta = chunk.choices[0].delta

                    if hasattr(delta, 'content') and delta.content:
                        await stream.send_token(delta.content)

                    if hasattr(delta, 'function_call'):
                        await stream.send_function_call(
                            delta.function_call.name,
                            json.loads(delta.function_call.arguments) if hasattr(delta.function_call, 'arguments') else {}
                        )

                elif hasattr(chunk, 'content'):
                    # Simple streaming content
                    await stream.send_token(chunk.content)

                elif isinstance(chunk, str):
                    # String chunk
                    await stream.send_token(chunk)

        except Exception as e:
            logger.error(f"Error in native model streaming: {e}")
            await stream.send_error(str(e), "MODEL_STREAMING_ERROR")

    async def _simulated_model_streaming(
        self,
        model,
        model_request: ModelRequest,
        stream: ActiveStream
    ):
        """Simulate streaming for models that don't support it"""

        try:
            # Get complete response first
            response = await model.process_request(model_request)

            if response.success and response.content:
                # Simulate token-by-token streaming
                tokens = self._tokenize_response(response.content)

                for token in tokens:
                    await stream.send_token(token)

                    # Add small delay for realism
                    await asyncio.sleep(0.01)

            else:
                await stream.send_error(response.error or "Unknown error", "MODEL_ERROR")

        except Exception as e:
            logger.error(f"Error in simulated model streaming: {e}")
            await stream.send_error(str(e), "MODEL_ERROR")

    async def _get_conversation_context(
        self,
        conversation_id: str,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get conversation context for the request"""

        try:
            # Get context from context manager
            context = await self.context_manager.get_context(conversation_id)

            # Add additional context if provided
            if additional_context:
                context.update(additional_context)

            return context

        except Exception as e:
            logger.warning(f"Error getting context for {conversation_id}: {e}")
            return additional_context or {}

    def _tokenize_response(self, response: str) -> List[str]:
        """Tokenize response for streaming simulation"""

        import re

        # Simple tokenization - split by spaces and punctuation
        tokens = re.findall(r'\w+|[^\w\s]', response)

        # Add spaces back to appropriate tokens
        result = []
        for i, token in enumerate(tokens):
            if i > 0 and not re.match(r'[^\w\s]', token):
                result.append(' ' + token)
            else:
                result.append(token)

        return result

    async def cancel_streaming_request(self, conversation_id: str) -> bool:
        """Cancel an active streaming request"""

        if conversation_id in self.active_streaming_requests:
            stream = self.active_streaming_requests[conversation_id]
            await stream.send_error("Request cancelled by user", "CANCELLED")
            await stream.close()
            return True

        return False

    def get_active_streams_info(self) -> List[Dict[str, Any]]:
        """Get information about all active streaming requests"""

        return [
            {
                "conversationId": conversation_id,
                "requestId": stream.request_id,
                "stats": stream.stats.get_summary(),
                "duration": time.time() - stream.stats.start_time
            }
            for conversation_id, stream in self.active_streaming_requests.items()
        ]

# Global streaming orchestrator instance
streaming_orchestrator: Optional[StreamingOrchestrator] = None

def initialize_streaming_orchestrator(
    model_orchestrator: ModelOrchestrator,
    context_manager: ContextManager
):
    """Initialize the global streaming orchestrator"""

    global streaming_orchestrator
    streaming_orchestrator = StreamingOrchestrator(model_orchestrator, context_manager)
    logger.info("Streaming orchestrator initialized")

def get_streaming_orchestrator() -> StreamingOrchestrator:
    """Get the global streaming orchestrator"""

    if streaming_orchestrator is None:
        raise RuntimeError("Streaming orchestrator not initialized")

    return streaming_orchestrator