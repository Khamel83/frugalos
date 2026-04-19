#!/usr/bin/env python3
"""
Hermes AI Assistant v2.0 - Multi-Modal Platform
Main FastAPI application with streaming, vision, and audio capabilities
"""

import os
import sys
import logging
import time
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# Add frugalos to path for CLI integration
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hermes.database import Database
from hermes.config import Config
from hermes.logger import setup_logger
from hermes.orchestrator import get_orchestrator

# Import new multi-modal and streaming components
from hermes.streaming.streaming_manager import streaming_manager, initialize_streaming_orchestrator
from hermes.vision.vision_service import vision_service, initialize_vision_service
from hermes.audio.audio_service import audio_service, initialize_audio_service
from hermes.multimodal.multimodal_reasoner import multimodal_reasoner, initialize_multimodal_reasoner

# Import personalization components
from hermes.personalization.user_profiler import initialize_user_profiler, get_user_profiler
from hermes.personalization.personalized_generator import initialize_personalized_generator, get_personalized_generator
from hermes.personalization.contextual_awareness import initialize_contextual_awareness, get_contextual_awareness_engine
from hermes.personalization.adaptive_conversations import initialize_adaptive_conversations, get_adaptive_conversation_engine

# Import routes
from hermes.routes.streaming_routes import router as streaming_router
from hermes.routes.multimodal_routes import router as multimodal_router
from hermes.routes.personalization_routes import router as personalization_router

# Import optimization components
try:
    import redis.asyncio as redis
    import psutil
    from hermes.monitoring.performance_monitor import performance_collector
    from hermes.monitoring.database_optimizer import DatabasePerformanceMonitor
    from hermes.caching.advanced_cache import l1_cache, RedisCache, MultiTierCache
    from hermes.optimization.resource_optimizer import (
        resource_monitor, ResourceMonitor, DEFAULT_POLICIES,
        AutoScaler, CostOptimizer, PerformanceOptimizer
    )
    OPTIMIZATION_ENABLED = True
except ImportError as e:
    logging.warning(f"Optimization components not available: {e}")
    OPTIMIZATION_ENABLED = False

# Configuration
config = Config()

# Initialize components
db = Database()
logger = setup_logger('hermes.app')

# Get unified orchestrator
orchestrator = get_orchestrator(config)

# Initialize all services
def initialize_services():
    """Initialize all multi-modal and personalization services"""

    # Initialize vision service
    vision_config = {
        "openai_api_key": os.getenv('OPENAI_API_KEY'),
        "anthropic_api_key": os.getenv('ANTHROPIC_API_KEY'),
        "google_vision_api_key": os.getenv('GOOGLE_VISION_API_KEY'),
        "ocr_enabled": True,
        "max_image_size": 20 * 1024 * 1024
    }
    initialize_vision_service(vision_config)

    # Initialize audio service
    audio_config = {
        "openai_api_key": os.getenv('OPENAI_API_KEY'),
        "azure_speech_key": os.getenv('AZURE_SPEECH_KEY'),
        "aws_polly_key": os.getenv('AWS_POLLY_KEY'),
        "google_speech_key": os.getenv('GOOGLE_SPEECH_KEY'),
        "max_audio_size": 50 * 1024 * 1024,
        "default_sample_rate": 16000
    }
    initialize_audio_service(audio_config)

    # Initialize streaming orchestrator
    initialize_streaming_orchestrator(orchestrator, orchestrator.context_manager)

    # Initialize multi-modal reasoner
    multimodal_config = {
        "max_concurrent_reasoning": 10,
        "confidence_threshold": 0.7
    }
    initialize_multimodal_reasoner(vision_service, audio_service, multimodal_config)

    # Initialize personalization services
    user_profiler_config = {
        "max_history_size": 1000,
        "learning_threshold": 0.7,
        "adaptation_rate": 0.1
    }
    initialize_user_profiler(user_profiler_config)

    personalized_generator_config = {
        "min_confidence_threshold": 0.6,
        "max_adaptation_time": 2.0
    }
    initialize_personalized_generator(personalized_generator_config)

    contextual_awareness_config = {
        "max_history_size": 1000,
        "context_decay_rate": 0.1,
        "insight_threshold": 0.7,
        "session_timeout": 3600
    }
    initialize_contextual_awareness(contextual_awareness_config)

    adaptive_conversations_config = {
        "adaptation_threshold": 0.7,
        "performance_window": 20,
        "strategy_rotation_interval": 10
    }
    initialize_adaptive_conversations(adaptive_conversations_config)

    logger.info("Multi-modal and personalization services initialized")

# Application lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown"""

    # Startup
    logger.info("Starting Hermes AI Assistant v2.0...")
    initialize_services()

    yield

    # Shutdown
    logger.info("Shutting down Hermes AI Assistant...")

# Initialize FastAPI app
app = FastAPI(
    title="Hermes AI Assistant",
    description="Multi-modal AI assistant with real-time streaming, vision, and audio capabilities",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Configure middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Configure app settings
app.config = {
    'SECRET_KEY': os.getenv('HERMES_SECRET_KEY', 'dev-key-change-in-production'),
    'MAX_CONTENT_LENGTH': 50 * 1024 * 1024,  # 50MB max file size for multi-modal
    'UPLOAD_FOLDER': 'uploads'
}

# Initialize optimization components
redis_client = None
cache_system = None
performance_optimizers = {}

if OPTIMIZATION_ENABLED:
    try:
        # Initialize Redis client
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        redis_client = redis.from_url(redis_url)

        # Initialize multi-tier cache
        l2_cache = RedisCache(redis_client, key_prefix="hermes_cache")
        cache_system = MultiTierCache(l1_cache, l2_cache)

        # Initialize resource monitoring
        if not resource_monitor:
            resource_monitor = ResourceMonitor(kubernetes_enabled=False)

        # Initialize performance optimizers
        performance_optimizers = {
            'auto_scaler': AutoScaler(DEFAULT_POLICIES, kubernetes_enabled=False),
            'cost_optimizer': CostOptimizer(),
            'performance_optimizer': PerformanceOptimizer(resource_monitor)
        }

    except Exception as e:
        logger.error(f"Failed to initialize optimization systems: {e}")
        OPTIMIZATION_ENABLED = False

# Include new routes
app.include_router(streaming_router, prefix="/api/v1")
app.include_router(multimodal_router, prefix="/api/v1")
app.include_router(personalization_router, prefix="/api/v1")

# FastAPI middleware for performance monitoring
@app.middleware("http")
async def add_performance_headers(request: Request, call_next):
    """Add performance headers and track metrics"""
    start_time = time.time()

    response = await call_next(request)

    duration = time.time() - start_time
    response.headers["X-Response-Time"] = f"{duration:.3f}s"

    # Log slow requests
    if duration > 1.0:
        logger.warning(f"Slow request: {request.method} {request.url.path} - {duration:.3f}s")

    # Store metrics if cache is available
    if cache_system and redis_client:
        try:
            metrics = {
                'method': request.method,
                'path': request.url.path,
                'duration': duration,
                'status_code': response.status_code,
                'timestamp': datetime.utcnow().isoformat()
            }

            # Store in Redis
            await redis_client.lpush(
                f"request_metrics:{request.method}:{request.url.path}",
                str(metrics)
            )
            await redis_client.expire(
                f"request_metrics:{request.method}:{request.url.path}",
                3600
            )
        except Exception as e:
            logger.error(f"Error storing request metrics: {e}")

    return response

# Basic API endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Hermes AI Assistant - Multi-Modal Platform",
        "version": "2.0.0",
        "status": "running",
        "features": [
            "Real-time streaming",
            "Vision analysis (OCR, image understanding)",
            "Audio processing (speech-to-text, text-to-speech)",
            "Multi-modal reasoning",
            "Advanced personalization and user adaptation",
            "Contextual awareness and learning",
            "Adaptive conversation strategies",
            "Advanced conversation management",
            "Enterprise security",
            "Auto-scaling and optimization"
        ],
        "docs": "/api/docs",
        "health": "/api/health"
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "services": {
            "streaming": "active",
            "vision": "active",
            "audio": "active",
            "multimodal": "active",
            "personalization": "active",
            "contextual_awareness": "active",
            "adaptive_conversations": "active",
            "orchestrator": "active"
        }
    }

@app.get("/api/status")
async def get_status():
    """Get comprehensive system status"""
    try:
        # Get orchestrator status
        orchestrator_status = orchestrator.get_system_status()

        # Get streaming stats
        streaming_stats = streaming_manager.get_stream_stats()

        return {
            "status": "operational",
            "timestamp": datetime.utcnow().isoformat(),
            "orchestrator": orchestrator_status,
            "streaming": streaming_stats,
            "optimization_enabled": OPTIMIZATION_ENABLED,
            "features": {
                "real_time_streaming": True,
                "vision_analysis": True,
                "audio_processing": True,
                "multimodal_reasoning": True,
                "advanced_personalization": True,
                "contextual_awareness": True,
                "adaptive_conversations": True,
                "advanced_security": True,
                "auto_scaling": True
            }
        }
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system status"
        )

# Legacy orchestrator endpoints (updated for FastAPI)
@app.get("/api/v1/orchestrator/status")
async def get_orchestrator_status():
    """Get comprehensive orchestrator status"""
    try:
        status = orchestrator.get_system_status()
        return status
    except Exception as e:
        logger.error(f"Error getting orchestrator status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get orchestrator status"
        )

@app.get("/api/v1/orchestrator/dashboard")
async def get_orchestrator_dashboard():
    """Get dashboard data"""
    try:
        data = orchestrator.get_dashboard_data()
        return data
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get dashboard data"
        )

@app.post("/api/v1/orchestrator/submit")
async def submit_orchestrated_job(request: Request):
    """Submit job through orchestrator"""
    try:
        data = await request.json()
        idea = data.get('idea')

        if not idea:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing idea field"
            )

        priority = data.get('priority', 3)
        context = data.get('context', {})
        interactive = data.get('interactive', False)

        result = orchestrator.submit_job(idea, priority, context, interactive)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting orchestrated job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit job"
        )

@app.post("/api/v1/orchestrator/execute")
async def execute_with_intelligence(request: Request):
    """Execute job with full intelligence stack"""
    try:
        data = await request.json()
        idea = data.get('idea')

        if not idea:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing idea field"
            )

        context = data.get('context', {})

        result = orchestrator.execute_with_intelligence(idea, context)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in intelligent execution: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute job"
        )

@app.get("/api/v1/orchestrator/suggestions")
async def get_orchestrator_suggestions():
    """Get proactive suggestions"""
    try:
        suggestions = orchestrator.get_suggestions()
        return {'suggestions': suggestions}
    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get suggestions"
        )

# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error", "status_code": 500}
    )

# Main execution
if __name__ == "__main__":
    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize database
    db.initialize()

    # Initialize and start orchestrator
    logger.info("Initializing Hermes Orchestrator...")
    orchestrator.initialize()
    orchestrator.start()

    # Get configuration
    host = os.getenv('HERMES_HOST', '0.0.0.0')
    port = int(os.getenv('HERMES_PORT', 8000))
    debug = config.get('hermes.debug', False)

    logger.info(f"Starting Hermes AI Assistant v2.0.0 on {host}:{port}")
    logger.info("Advanced features enabled: Streaming, Vision, Audio, Personalization")
    logger.info(f"Personalization: User preference learning, contextual awareness, adaptive conversations")
    logger.info(f"API Documentation: http://{host}:{port}/api/docs")

    # Run with uvicorn
    uvicorn.run(
        "app_v2:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info" if not debug else "debug"
    )