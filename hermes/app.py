#!/usr/bin/env python3
"""
Hermes: Backend-Agnostic Personal AI Assistant
Main FastAPI application with multi-modal capabilities and real-time streaming
"""

import os
import sys
import sqlite3
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
from hermes.autonomous.learning_optimizer import OptimizationStrategy

# Import new multi-modal and streaming components
from hermes.streaming.streaming_manager import streaming_manager, initialize_streaming_orchestrator
from hermes.vision.vision_service import vision_service, initialize_vision_service
from hermes.audio.audio_service import audio_service, initialize_audio_service
from hermes.multimodal.multimodal_reasoner import multimodal_reasoner, initialize_multimodal_reasoner

# Import routes
from hermes.routes.streaming_routes import router as streaming_router
from hermes.routes.multimodal_routes import router as multimodal_router
from hermes.routing.api_routes import router as routing_router

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

# Initialize new multi-modal services
def initialize_services():
    """Initialize all multi-modal and streaming services"""

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

    logger.info("Multi-modal and streaming services initialized")

# Application lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown"""

    # Startup
    logger.info("Starting Hermes AI Assistant...")
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

# Include new routes
app.include_router(streaming_router, prefix="/api/v1")
app.include_router(multimodal_router, prefix="/api/v1")
app.include_router(routing_router)  # Routing has its own prefix

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
    logger.info("Multi-modal features enabled: Streaming, Vision, Audio, Reasoning")
    logger.info(f"API Documentation: http://{host}:{port}/api/docs")

    # Run with uvicorn
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info" if not debug else "debug"
    )

        # Start in background thread
        import threading
        optimization_thread = threading.Thread(target=start_optimization_tasks, daemon=True)
        optimization_thread.start()

        logger.info("Optimization systems initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize optimization systems: {e}")
        OPTIMIZATION_ENABLED = False


# Flask performance monitoring middleware
@app.before_request
def before_request():
    """Store request start time"""
    g.start_time = time.time()


@app.after_request
def after_request(response):
    """Add performance headers and track metrics"""
    if hasattr(g, 'start_time'):
        duration = time.time() - g.start_time
        response.headers['X-Response-Time'] = f"{duration:.3f}s"

        # Log slow requests
        if duration > 1.0:
            logger.warning(f"Slow request: {request.method} {request.path} - {duration:.3f}s")

        # Store metrics if cache is available
        if cache_system and redis_client:
            try:
                metrics = {
                    'method': request.method,
                    'path': request.path,
                    'duration': duration,
                    'status_code': response.status_code,
                    'timestamp': datetime.utcnow().isoformat()
                }

                # Store in Redis
                asyncio.run(redis_client.lpush(
                    f"request_metrics:{request.method}:{request.path}",
                    str(metrics)
                ))
                asyncio.run(redis_client.expire(
                    f"request_metrics:{request.method}:{request.path}",
                    3600
                ))
            except Exception as e:
                logger.error(f"Error storing request metrics: {e}")

    return response

@app.route('/')
def index():
    """Main dashboard interface"""
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """Advanced monitoring dashboard"""
    return render_template('dashboard.html')

@app.route('/api/status')
def status():
    """System status endpoint"""
    metrics = metrics_collector.get_current_metrics()
    return jsonify({
        'status': 'operational',
        'timestamp': datetime.now().isoformat(),
        'version': '0.1.0',
        'components': {
            'database': 'connected',
            'tailscale': 'connected' if tailscale_client.test_connection() else 'disconnected',
            'hermes': 'available',
            'monitoring': 'active' if metrics_collector._running else 'inactive'
        },
        'metrics': metrics
    })

@app.route('/api/submit', methods=['POST'])
def submit_idea():
    """Submit new idea for execution"""
    try:
        data = request.get_json()

        if not data or 'idea' not in data:
            return jsonify({'error': 'Missing idea field'}), 400

        idea = data['idea'].strip()
        if not idea:
            return jsonify({'error': 'Idea cannot be empty'}), 400

        # Create job record
        job_id = db.create_job(idea)

        # Queue job for processing
        from hermes.queue import JobQueue
        queue = JobQueue()
        queue.enqueue_job(job_id, idea)

        logger.info(f"Job {job_id} created for idea: {idea[:100]}...")

        return jsonify({
            'job_id': job_id,
            'status': 'queued',
            'message': 'Idea submitted for execution'
        })

    except Exception as e:
        logger.error(f"Error submitting idea: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/jobs')
def list_jobs():
    """List recent jobs"""
    try:
        limit = request.args.get('limit', 20, type=int)
        jobs = db.get_recent_jobs(limit)
        return jsonify({'jobs': jobs})
    except Exception as e:
        logger.error(f"Error listing jobs: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/jobs/<int:job_id>')
def get_job(job_id):
    """Get specific job details"""
    try:
        job = db.get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        return jsonify(job)
    except Exception as e:
        logger.error(f"Error getting job {job_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/jobs/<int:job_id>/events')
def job_events(job_id):
    """Server-sent events for job updates"""
    def generate():
        try:
            # Get existing events
            events = db.get_job_events(job_id)
            for event in events:
                yield f"data: {event}\n\n"

            # Stream new events
            from hermes.events import EventStreamer
            streamer = EventStreamer()
            for event in streamer.stream_job_events(job_id):
                yield f"data: {event}\n\n"

        except Exception as e:
            logger.error(f"Error streaming events for job {job_id}: {str(e)}")
            yield f"data: {{'type': 'error', 'message': 'Stream error'}}\n\n"

    return Response(generate(), mimetype='text/plain')

@app.route('/api/backends')
def list_backends():
    """List available AI backends"""
    try:
        backends = db.get_active_backends()
        return jsonify({'backends': backends})
    except Exception as e:
        logger.error(f"Error listing backends: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Test database connection
        db_status = 'healthy' if db.test_connection() else 'unhealthy'

        # Test tailscale connection
        tailscale_status = 'connected' if tailscale_client.test_connection() else 'disconnected'

        # Test local execution
        from .local_execution import LocalExecutionEngine
        local_engine = LocalExecutionEngine(config)
        local_status = 'available' if local_engine.test_local_execution() else 'unavailable'

        # Determine overall status
        overall_status = 'healthy' if db_status == 'healthy' else 'unhealthy'

        return jsonify({
            'status': overall_status,
            'timestamp': datetime.now().isoformat(),
            'components': {
                'database': db_status,
                'tailscale': tailscale_status,
                'local_execution': local_status,
                'monitoring': 'active' if metrics_collector._running else 'inactive'
            }
        }), 200 if overall_status == 'healthy' else 503

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 503

@app.route('/api/metrics')
def get_metrics():
    """Get current system metrics"""
    return jsonify(metrics_collector.get_current_metrics())

@app.route('/api/metrics/history')
def get_metrics_history():
    """Get metrics history"""
    hours = request.args.get('hours', 24, type=int)
    return jsonify(metrics_collector.get_metrics_history(hours))

@app.route('/api/alerts')
def get_alerts():
    """Get monitoring alerts"""
    hours = request.args.get('hours', 24, type=int)
    resolved = request.args.get('resolved', 'false').lower() == 'true'
    return jsonify({'alerts': metrics_collector.get_alerts(hours, resolved)})

@app.route('/api/conversations/<int:conversation_id>')
def get_conversation(conversation_id):
    """Get conversation details"""
    try:
        summary = conversation_manager.get_conversation_summary(conversation_id)
        messages = conversation_manager.get_conversation_messages(conversation_id)

        return jsonify({
            'summary': summary,
            'messages': [
                {
                    'type': msg.message_type,
                    'sender': msg.sender,
                    'content': msg.content,
                    'metadata': msg.metadata,
                    'timestamp': msg.timestamp.isoformat()
                }
                for msg in messages
            ]
        })
    except Exception as e:
        logger.error(f"Error getting conversation: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/patterns/stats')
def get_pattern_stats():
    """Get pattern learning statistics"""
    try:
        stats = pattern_engine.get_pattern_statistics()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting pattern stats: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/patterns/suggestions', methods=['POST'])
def get_pattern_suggestions():
    """Get suggestions based on patterns"""
    try:
        data = request.get_json()
        idea = data.get('idea')

        if not idea:
            return jsonify({'error': 'Missing idea field'}), 400

        suggestions = pattern_engine.get_suggestions(idea)
        return jsonify(suggestions)

    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/context/optimize/<int:conversation_id>')
def optimize_context(conversation_id):
    """Optimize conversation context for token efficiency"""
    try:
        target_tokens = request.args.get('target_tokens', type=int)
        optimized = context_optimizer.optimize_context(conversation_id, target_tokens)
        return jsonify(optimized)
    except Exception as e:
        logger.error(f"Error optimizing context: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/context/stats/<int:conversation_id>')
def get_context_stats(conversation_id):
    """Get context optimization statistics"""
    try:
        stats = context_optimizer.get_optimization_stats(conversation_id)
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting context stats: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/questions/prioritize', methods=['POST'])
def prioritize_questions():
    """Adaptively prioritize questions"""
    try:
        data = request.get_json()
        questions = data.get('questions', [])
        conversation_id = data.get('conversation_id')
        idea = data.get('idea', '')

        if not questions or not conversation_id:
            return jsonify({'error': 'Missing required fields'}), 400

        prioritized = adaptive_prioritizer.prioritize_questions(
            questions,
            conversation_id,
            idea
        )

        # Suggest subset
        max_questions = data.get('max_questions', 3)
        to_ask, to_skip = adaptive_prioritizer.suggest_question_subset(
            prioritized,
            max_questions
        )

        return jsonify({
            'all_prioritized': [
                {
                    'question_id': q.question_id,
                    'question_text': q.question_text,
                    'priority': q.dynamic_priority,
                    'skip_likelihood': q.skip_likelihood,
                    'reasoning': q.reasoning
                }
                for q in prioritized
            ],
            'to_ask': [
                {
                    'question_id': q.question_id,
                    'question_text': q.question_text,
                    'priority': q.dynamic_priority
                }
                for q in to_ask
            ],
            'to_skip': [q.question_id for q in to_skip]
        })

    except Exception as e:
        logger.error(f"Error prioritizing questions: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/questions/prioritization-stats')
def get_prioritization_stats():
    """Get question prioritization statistics"""
    try:
        stats = adaptive_prioritizer.get_prioritization_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting prioritization stats: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/strategy/determine', methods=['POST'])
def determine_execution_strategy():
    """Determine optimal execution strategy"""
    try:
        data = request.get_json()
        idea = data.get('idea')

        if not idea:
            return jsonify({'error': 'Missing idea field'}), 400

        context = data.get('context', {})
        constraints = data.get('constraints', {})

        strategy = execution_strategy_engine.determine_strategy(
            idea,
            context,
            constraints
        )

        return jsonify({
            'mode': strategy.mode.value,
            'validation_level': strategy.validation_level.value,
            'backend_preference': strategy.backend_preference,
            'timeout_seconds': strategy.timeout_seconds,
            'retry_strategy': strategy.retry_strategy,
            'context_optimization': strategy.context_optimization,
            'confidence_score': strategy.confidence_score,
            'reasoning': strategy.reasoning,
            'estimated_cost_cents': strategy.estimated_cost_cents,
            'estimated_time_seconds': strategy.estimated_time_seconds
        })

    except Exception as e:
        logger.error(f"Error determining strategy: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/strategy/stats')
def get_strategy_stats():
    """Get execution strategy statistics"""
    try:
        stats = execution_strategy_engine.get_strategy_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting strategy stats: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/metalearning/metrics')
def get_metalearning_metrics():
    """Get comprehensive meta-learning metrics"""
    try:
        hours = request.args.get('hours', 24, type=int)
        summary = metalearning_metrics.get_comprehensive_metrics(hours)

        return jsonify({
            'total_conversations': summary.total_conversations,
            'total_questions_asked': summary.total_questions_asked,
            'total_patterns_learned': summary.total_patterns_learned,
            'avg_questions_per_conversation': summary.avg_questions_per_conversation,
            'avg_confidence_score': summary.avg_confidence_score,
            'question_effectiveness': summary.question_effectiveness,
            'pattern_success_rate': summary.pattern_success_rate,
            'context_optimization_ratio': summary.context_optimization_ratio,
            'time_saved_seconds': summary.time_saved_seconds,
            'insights': summary.insights
        })
    except Exception as e:
        logger.error(f"Error getting metalearning metrics: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/metalearning/velocity')
def get_learning_velocity():
    """Get learning velocity metrics"""
    try:
        days = request.args.get('days', 7, type=int)
        velocity = metalearning_metrics.get_learning_velocity(days)
        return jsonify(velocity)
    except Exception as e:
        logger.error(f"Error getting learning velocity: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/metalearning/top-patterns')
def get_top_patterns():
    """Get top performing patterns"""
    try:
        limit = request.args.get('limit', 10, type=int)
        patterns = metalearning_metrics.get_top_patterns(limit)
        return jsonify({'patterns': patterns})
    except Exception as e:
        logger.error(f"Error getting top patterns: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/metalearning/report')
def get_metalearning_report():
    """Export comprehensive metrics report"""
    try:
        hours = request.args.get('hours', 24, type=int)
        report = metalearning_metrics.export_metrics_report(hours)
        return jsonify(report)
    except Exception as e:
        logger.error(f"Error getting metalearning report: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/orchestrator/status')
def get_orchestrator_status():
    """Get comprehensive orchestrator status"""
    try:
        status = orchestrator.get_system_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting orchestrator status: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/orchestrator/dashboard')
def get_orchestrator_dashboard():
    """Get dashboard data"""
    try:
        data = orchestrator.get_dashboard_data()
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/orchestrator/submit', methods=['POST'])
def submit_orchestrated_job():
    """Submit job through orchestrator"""
    try:
        data = request.get_json()
        idea = data.get('idea')

        if not idea:
            return jsonify({'error': 'Missing idea field'}), 400

        priority = data.get('priority', 3)
        context = data.get('context', {})
        interactive = data.get('interactive', False)

        result = orchestrator.submit_job(idea, priority, context, interactive)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error submitting orchestrated job: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/orchestrator/execute', methods=['POST'])
def execute_with_intelligence():
    """Execute job with full intelligence stack"""
    try:
        data = request.get_json()
        idea = data.get('idea')

        if not idea:
            return jsonify({'error': 'Missing idea field'}), 400

        context = data.get('context', {})

        result = orchestrator.execute_with_intelligence(idea, context)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in intelligent execution: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/orchestrator/suggestions')
def get_orchestrator_suggestions():
    """Get proactive suggestions"""
    try:
        suggestions = orchestrator.get_suggestions()
        return jsonify({'suggestions': suggestions})
    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/orchestrator/optimizations')
def get_orchestrator_optimizations():
    """Get optimization recommendations"""
    try:
        strategy_name = request.args.get('strategy', 'BALANCED')
        strategy = OptimizationStrategy[strategy_name]

        optimizations = orchestrator.get_optimizations(strategy)

        return jsonify({'optimizations': optimizations})
    except Exception as e:
        logger.error(f"Error getting optimizations: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/orchestrator/start', methods=['POST'])
def start_orchestrator():
    """Start orchestrator systems"""
    try:
        orchestrator.start()
        return jsonify({'success': True, 'message': 'Orchestrator started'})
    except Exception as e:
        logger.error(f"Error starting orchestrator: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/orchestrator/stop', methods=['POST'])
def stop_orchestrator():
    """Stop orchestrator systems"""
    try:
        orchestrator.stop()
        return jsonify({'success': True, 'message': 'Orchestrator stopped'})
    except Exception as e:
        logger.error(f"Error stopping orchestrator: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize database
    db.initialize()

    # Initialize and start orchestrator
    logger.info("Initializing Hermes Orchestrator...")
    orchestrator.initialize()
    orchestrator.start()

    logger.info("Starting Hermes application on port 5000")
    app.run(host='0.0.0.0', port=5000, debug=config.get('hermes.debug', False))