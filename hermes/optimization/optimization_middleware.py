"""
Optimization middleware that integrates all performance and resource optimization
features into the FastAPI application.

This module provides:
- Request-level performance monitoring
- Automatic query optimization
- Intelligent caching middleware
- Resource usage tracking per request
- Performance-based auto-scaling triggers
"""

import time
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from contextlib import asynccontextmanager

from fastapi import Request, Response, HTTPException
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import RequestResponseEndpoint
import redis.asyncio as redis
import logging

from ..monitoring.performance_monitor import performance_collector, database_profiler
from ..monitoring.database_optimizer import db_performance_monitor, optimized_db_session
from ..caching.advanced_cache import multi_tier_cache, CacheDecorator
from ..optimization.resource_optimizer import (
    resource_monitor, auto_scaler, cost_optimizer, performance_optimizer
)

logger = logging.getLogger(__name__)


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive performance monitoring."""

    def __init__(self, app, redis_client: redis.Redis):
        super().__init__(app)
        self.redis = redis_client

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Monitor request performance."""
        start_time = time.time()
        request_id = f"req_{int(time.time() * 1000000)}"

        # Collect initial metrics
        initial_cpu = performance_collector.metrics_history[-1].cpu_percent if performance_collector.metrics_history else 0
        initial_memory = performance_collector.metrics_history[-1].memory_percent if performance_collector.metrics_history else 0

        # Add request ID to request state
        request.state.request_id = request_id
        request.state.start_time = start_time

        try:
            # Process request
            response = await call_next(request)

            # Calculate request metrics
            end_time = time.time()
            duration = end_time - start_time

            # Log slow requests
            if duration > 1.0:
                await self._handle_slow_request(request, response, duration, request_id)

            # Add performance headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration:.3f}s"

            # Store request metrics in Redis for dashboard
            await self._store_request_metrics(request, response, duration, request_id)

            return response

        except Exception as e:
            # Log errors
            end_time = time.time()
            duration = end_time - start_time
            await self._handle_request_error(request, e, duration, request_id)
            raise

    async def _handle_slow_request(self, request: Request, response: Response,
                                 duration: float, request_id: str):
        """Handle slow request logging and analysis."""
        logger.warning(
            f"Slow request detected: {duration:.3f}s - {request.method} {request.url.path}"
        )

        # Store slow request details
        slow_request_data = {
            'request_id': request_id,
            'method': request.method,
            'path': request.url.path,
            'query_params': str(request.query_params),
            'duration': duration,
            'status_code': response.status_code,
            'timestamp': datetime.utcnow().isoformat(),
            'user_agent': request.headers.get('user-agent'),
            'ip_address': request.client.host if request.client else None
        }

        await self.redis.lpush(
            "slow_requests",
            json.dumps(slow_request_data, default=str)
        )
        await self.redis.ltrim("slow_requests", 0, 99)  # Keep last 100

    async def _handle_request_error(self, request: Request, error: Exception,
                                  duration: float, request_id: str):
        """Handle request errors with performance context."""
        error_data = {
            'request_id': request_id,
            'method': request.method,
            'path': request.url.path,
            'duration': duration,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': datetime.utcnow().isoformat(),
            'stack_trace': str(error.__traceback__) if error.__traceback__ else None
        }

        await self.redis.lpush(
            "request_errors",
            json.dumps(error_data, default=str)
        )
        await self.redis.ltrim("request_errors", 0, 99)

    async def _store_request_metrics(self, request: Request, response: Response,
                                   duration: float, request_id: str):
        """Store request metrics for analysis."""
        metrics = {
            'request_id': request_id,
            'method': request.method,
            'path': request.url.path,
            'duration': duration,
            'status_code': response.status_code,
            'response_size': len(response.body) if hasattr(response, 'body') else 0,
            'timestamp': datetime.utcnow().isoformat()
        }

        # Store in time series data
        await self.redis.lpush(
            f"request_metrics:{request.method}:{request.url.path}",
            json.dumps(metrics, default=str)
        )
        await self.redis.expire(f"request_metrics:{request.method}:{request.url.path}", 3600)

        # Update aggregate statistics
        await self._update_aggregate_metrics(request.method, request.url.path, duration, response.status_code)

    async def _update_aggregate_metrics(self, method: str, path: str,
                                      duration: float, status_code: int):
        """Update aggregate request metrics."""
        key = f"aggregate_metrics:{method}:{path}"

        # Use Redis pipeline for atomic updates
        pipe = self.redis.pipeline()

        # Increment request count
        pipe.hincrby(key, 'total_requests', 1)

        # Update duration stats
        pipe.lpush(f"{key}:durations", duration)
        pipe.ltrim(f"{key}:durations", 0, 999)  # Keep last 1000
        pipe.expire(f"{key}:durations", 3600)

        # Update status codes
        pipe.hincrby(key, f"status_{status_code}", 1)

        # Set expiration
        pipe.expire(key, 3600)

        await pipe.execute()


class DatabaseOptimizationMiddleware(BaseHTTPMiddleware):
    """Middleware for database query optimization."""

    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Monitor and optimize database queries."""
        if not hasattr(request.state, 'db_session'):
            # Add optimized database session to request state
            request.state.db_session = None

        async with optimized_db_session(db_performance_monitor.db_engine, db_performance_monitor.cache_manager) as session:
            request.state.db_session = session

            try:
                response = await call_next(request)
                return response
            finally:
                request.state.db_session = None


class IntelligentCacheMiddleware(BaseHTTPMiddleware):
    """Intelligent caching middleware with dynamic policies."""

    def __init__(self, app, redis_client: redis.Redis):
        super().__init__(app)
        self.redis = redis_client
        self.cache_policies = self._load_cache_policies()

    def _load_cache_policies(self) -> Dict[str, Dict[str, Any]]:
        """Load caching policies for different endpoints."""
        return {
            # Health endpoints - short cache
            "/health": {
                "ttl": 30,
                "vary_headers": ["user-agent"],
                "cache_key_params": []
            },

            # API endpoints with authentication
            "/api/v1/chat/completions": {
                "ttl": 300,  # 5 minutes for identical requests
                "vary_headers": ["authorization", "content-type"],
                "cache_key_params": ["model", "messages", "max_tokens"],
                "max_response_size": 1024 * 1024  # 1MB
            },

            # User profile endpoints
            "/api/v1/user/profile": {
                "ttl": 600,  # 10 minutes
                "vary_headers": ["authorization"],
                "cache_key_params": [],
                "auth_required": True
            },

            # File listing
            "/api/v1/files/list": {
                "ttl": 60,  # 1 minute
                "vary_headers": ["authorization"],
                "cache_key_params": ["limit", "offset"],
                "auth_required": True
            }
        }

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Apply intelligent caching based on request characteristics."""
        # Check if this endpoint should be cached
        cache_policy = self._get_cache_policy(request)

        if not cache_policy:
            # No caching for this endpoint
            return await call_next(request)

        # Generate cache key
        cache_key = await self._generate_cache_key(request, cache_policy)

        # Try to get from cache
        cached_response = await self._get_cached_response(cache_key)
        if cached_response:
            return cached_response

        # Process request
        response = await call_next(request)

        # Cache response if appropriate
        if await self._should_cache_response(request, response, cache_policy):
            await self._cache_response(cache_key, response, cache_policy)

        return response

    def _get_cache_policy(self, request: Request) -> Optional[Dict[str, Any]]:
        """Get cache policy for the request path."""
        path = request.url.path

        # Exact match
        if path in self.cache_policies:
            return self.cache_policies[path]

        # Prefix match
        for policy_path, policy in self.cache_policies.items():
            if path.startswith(policy_path):
                return policy

        return None

    async def _generate_cache_key(self, request: Request,
                                cache_policy: Dict[str, Any]) -> str:
        """Generate cache key based on request and policy."""
        key_parts = [
            request.method,
            request.url.path,
        ]

        # Add query parameters
        cache_params = cache_policy.get('cache_key_params', [])
        if cache_params:
            query_params = dict(request.query_params)
            for param in cache_params:
                if param in query_params:
                    key_parts.append(f"{param}={query_params[param]}")

        # Add varying headers
        vary_headers = cache_policy.get('vary_headers', [])
        for header in vary_headers:
            if header in request.headers:
                key_parts.append(f"{header}:{request.headers[header]}")

        # Create hash for long keys
        key_string = ":".join(key_parts)
        if len(key_string) > 200:
            import hashlib
            key_hash = hashlib.md5(key_string.encode()).hexdigest()
            return f"response_cache:{key_hash}"
        else:
            return f"response_cache:{key_string.replace(':', '_')}"

    async def _get_cached_response(self, cache_key: str) -> Optional[Response]:
        """Get cached response."""
        try:
            if not multi_tier_cache:
                return None

            cached_data = await multi_tier_cache.get(cache_key)
            if cached_data:
                # Reconstruct Response object
                return Response(
                    content=cached_data['content'],
                    status_code=cached_data['status_code'],
                    headers=cached_data['headers'],
                    media_type=cached_data.get('media_type')
                )
        except Exception as e:
            logger.error(f"Error getting cached response: {e}")

        return None

    async def _should_cache_response(self, request: Request, response: Response,
                                   cache_policy: Dict[str, Any]) -> bool:
        """Determine if response should be cached."""
        # Don't cache error responses
        if response.status_code >= 400:
            return False

        # Check authentication requirement
        if cache_policy.get('auth_required') and 'authorization' not in request.headers:
            return False

        # Check response size
        max_size = cache_policy.get('max_response_size', 1024 * 1024)  # 1MB default
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > max_size:
            return False

        # Check cache control headers
        cache_control = response.headers.get('cache-control', '')
        if 'no-cache' in cache_control or 'private' in cache_control:
            return False

        return True

    async def _cache_response(self, cache_key: str, response: Response,
                            cache_policy: Dict[str, Any]):
        """Cache the response."""
        try:
            if not multi_tier_cache:
                return

            # Prepare cache data
            cache_data = {
                'content': response.body if hasattr(response, 'body') else b'',
                'status_code': response.status_code,
                'headers': dict(response.headers),
                'media_type': response.media_type,
                'cached_at': datetime.utcnow().isoformat()
            }

            # Store in cache
            await multi_tier_cache.set(
                cache_key,
                cache_data,
                ttl=cache_policy.get('ttl', 300),
                tags=['http_response', f"status_{response.status_code}"]
            )

        except Exception as e:
            logger.error(f"Error caching response: {e}")


class ResourceTrackingMiddleware(BaseHTTPMiddleware):
    """Middleware for tracking resource usage per request."""

    def __init__(self, app, redis_client: redis.Redis):
        super().__init__(app)
        self.redis = redis_client

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Track resource usage for each request."""
        # Collect initial metrics
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        initial_cpu = process.cpu_percent()

        try:
            response = await call_next(request)

            # Collect final metrics
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            final_cpu = process.cpu_percent()

            # Calculate deltas
            memory_delta = final_memory - initial_memory
            cpu_delta = final_cpu - initial_cpu

            # Store resource tracking data
            if hasattr(request.state, 'request_id'):
                resource_data = {
                    'request_id': request.state.request_id,
                    'method': request.method,
                    'path': request.url.path,
                    'memory_delta_mb': memory_delta,
                    'cpu_delta_percent': cpu_delta,
                    'peak_memory_mb': final_memory,
                    'timestamp': datetime.utcnow().isoformat()
                }

                await self.redis.hset(
                    f"resource_tracking:{request.state.request_id}",
                    mapping=resource_data
                )
                await self.redis.expire(f"resource_tracking:{request.state.request_id}", 3600)

            # Add resource headers to response
            response.headers["X-Memory-Delta"] = f"{memory_delta:.2f}MB"
            response.headers["X-CPU-Delta"] = f"{cpu_delta:.1f}%"

            return response

        except Exception as e:
            logger.error(f"Error in resource tracking: {e}")
            raise


class AutoScalingMiddleware(BaseHTTPMiddleware):
    """Middleware that can trigger auto-scaling based on performance metrics."""

    def __init__(self, app, redis_client: redis.Redis):
        super().__init__(app)
        self.redis = redis_client
        self.last_scale_check = 0
        self.scale_check_interval = 60  # seconds

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Check for auto-scaling conditions periodically."""
        current_time = time.time()

        # Check auto-scaling conditions periodically
        if (current_time - self.last_scale_check) > self.scale_check_interval:
            await self._check_auto_scaling_conditions()
            self.last_scale_check = current_time

        return await call_next(request)

    async def _check_auto_scaling_conditions(self):
        """Check if auto-scaling should be triggered."""
        try:
            if not resource_monitor or not auto_scaler:
                return

            # Get current metrics
            current_metrics = await resource_monitor.collect_metrics()
            metrics_history = resource_monitor.metrics_history

            # Evaluate scaling decisions
            decisions = await auto_scaler.evaluate_scaling(current_metrics, metrics_history)

            if decisions:
                logger.info(f"Auto-scaling decisions: {len(decisions)}")
                for decision in decisions:
                    await self._handle_scaling_decision(decision)

        except Exception as e:
            logger.error(f"Error checking auto-scaling conditions: {e}")

    async def _handle_scaling_decision(self, decision):
        """Handle a scaling decision."""
        try:
            # Log the decision
            decision_data = {
                'resource_type': decision.resource_type.value,
                'direction': decision.direction.value,
                'current_value': decision.current_value,
                'threshold_value': decision.threshold_value,
                'target_replicas': decision.target_replicas,
                'reason': decision.reason,
                'confidence': decision.confidence,
                'estimated_cost_impact': decision.estimated_cost_impact,
                'timestamp': datetime.utcnow().isoformat()
            }

            await self.redis.lpush("scaling_decisions", json.dumps(decision_data, default=str))
            await self.redis.ltrim("scaling_decisions", 0, 49)

            # Execute scaling if confidence is high
            if decision.confidence > 0.7 and auto_scaler.kubernetes_enabled:
                deployment_name = "hermes-ai-assistant"  # Get from config
                success = await auto_scaler.execute_scaling([decision], deployment_name)

                if success:
                    logger.info(f"Executed scaling: {decision.direction} to {decision.target_replicas} replicas")
                else:
                    logger.error(f"Failed to execute scaling decision")

        except Exception as e:
            logger.error(f"Error handling scaling decision: {e}")


class OptimizationMiddlewareStack:
    """Stack of all optimization middlewares."""

    def __init__(self, app, redis_client: redis.Redis):
        self.app = app
        self.redis = redis_client

        # Apply middlewares in order
        self._apply_middlewares()

    def _apply_middlewares(self):
        """Apply all optimization middlewares."""
        # Performance monitoring (outermost - runs first)
        self.app.add_middleware(PerformanceMonitoringMiddleware, redis_client=self.redis)

        # Resource tracking
        self.app.add_middleware(ResourceTrackingMiddleware, redis_client=self.redis)

        # Database optimization
        self.app.add_middleware(DatabaseOptimizationMiddleware)

        # Intelligent caching
        self.app.add_middleware(IntelligentCacheMiddleware, redis_client=self.redis)

        # Auto-scaling (innermost - runs last)
        self.app.add_middleware(AutoScalingMiddleware, redis_client=self.redis)

        # Gzip compression for responses
        self.app.add_middleware(GZipMiddleware, minimum_size=1000)

    async def initialize_optimization_systems(self):
        """Initialize all optimization systems."""
        try:
            # Start resource monitoring
            if resource_monitor:
                await resource_monitor.start_monitoring()
                logger.info("Started resource monitoring")

            # Initialize cache system
            global multi_tier_cache, l2_cache
            if not l2_cache:
                from ..caching.advanced_cache import RedisCache
                l2_cache = RedisCache(self.redis)
                multi_tier_cache = MultiTierCache(l1_cache, l2_cache)
                logger.info("Initialized multi-tier cache system")

            # Initialize database performance monitor
            global db_performance_monitor
            if not db_performance_monitor:
                from ..monitoring.database_optimizer import DatabasePerformanceMonitor
                from sqlalchemy.ext.asyncio import create_async_engine

                # This would use the actual database URL from config
                db_engine = create_async_engine("postgresql+asyncpg://localhost/hermes")
                db_performance_monitor = DatabasePerformanceMonitor(db_engine, self.redis)
                logger.info("Initialized database performance monitor")

        except Exception as e:
            logger.error(f"Error initializing optimization systems: {e}")

    async def cleanup_optimization_systems(self):
        """Cleanup optimization systems."""
        try:
            # Stop resource monitoring
            if resource_monitor:
                await resource_monitor.stop_monitoring()
                logger.info("Stopped resource monitoring")

        except Exception as e:
            logger.error(f"Error cleaning up optimization systems: {e}")


# Import required modules
try:
    import psutil
except ImportError:
    logger.warning("psutil not available - resource tracking will be limited")


# Decorator for caching function results
def optimized_cache(ttl: int = 300, key: Optional[str] = None, tags: List[str] = None):
    """Decorator for automatic function result caching."""
    def decorator(func: Callable) -> Callable:
        if not multi_tier_cache:
            return func

        # Create cache decorator
        cache_decorator = CacheDecorator(
            cache=multi_tier_cache,
            ttl=ttl,
            key_generator=key,
            tags=tags or []
        )

        return cache_decorator(func)
    return decorator


# Context manager for performance monitoring
@asynccontextmanager
async def monitor_operation(operation_name: str, tags: Dict[str, str] = None):
    """Context manager for monitoring operation performance."""
    start_time = time.time()

    try:
        yield
    finally:
        duration = time.time() - start_time

        # Log performance metrics
        logger.info(f"Operation '{operation_name}' completed in {duration:.3f}s")

        # Store metrics if Redis is available
        if multi_tier_cache:
            try:
                metrics_key = f"operation_metrics:{operation_name}"
                await multi_tier_cache.redis.lpush(
                    metrics_key,
                    json.dumps({
                        'duration': duration,
                        'timestamp': datetime.utcnow().isoformat(),
                        'tags': tags or {}
                    })
                )
                await multi_tier_cache.redis.expire(metrics_key, 3600)
            except Exception as e:
                logger.error(f"Error storing operation metrics: {e}")


# Performance optimization utilities
class PerformanceUtils:
    """Utility functions for performance optimization."""

    @staticmethod
    async def get_performance_summary() -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        summary = {
            'timestamp': datetime.utcnow().isoformat(),
            'resource_monitoring': {},
            'cache_performance': {},
            'database_performance': {},
            'recent_slow_requests': [],
            'auto_scaling_decisions': []
        }

        try:
            # Resource monitoring
            if resource_monitor:
                summary['resource_monitoring'] = resource_monitor.get_metrics_summary(hours=1)

            # Cache performance
            if multi_tier_cache:
                summary['cache_performance'] = multi_tier_cache.get_stats()

            # Database performance
            if db_performance_monitor:
                summary['database_performance'] = await db_performance_monitor.get_performance_report()

            # Recent slow requests
            if multi_tier_cache:
                slow_requests = await multi_tier_cache.redis.lrange("slow_requests", 0, 9)
                summary['recent_slow_requests'] = [
                    json.loads(req) for req in slow_requests
                ]

            # Auto-scaling decisions
            if multi_tier_cache:
                scaling_decisions = await multi_tier_cache.redis.lrange("scaling_decisions", 0, 9)
                summary['auto_scaling_decisions'] = [
                    json.loads(dec) for dec in scaling_decisions
                ]

        except Exception as e:
            logger.error(f"Error generating performance summary: {e}")
            summary['error'] = str(e)

        return summary

    @staticmethod
    async def trigger_manual_optimization() -> Dict[str, Any]:
        """Trigger manual performance optimization."""
        results = {
            'timestamp': datetime.utcnow().isoformat(),
            'optimizations_applied': []
        }

        try:
            # Performance optimization recommendations
            if performance_optimizer:
                recommendations = await performance_optimizer.analyze_and_optimize()
                results['performance_recommendations'] = recommendations

            # Cost optimization suggestions
            if resource_monitor and cost_optimizer:
                metrics_history = resource_monitor.metrics_history
                performance_requirements = {'max_cpu': 80, 'max_memory': 85}
                cost_suggestions = cost_optimizer.suggest_cost_optimizations(
                    list(metrics_history), performance_requirements
                )
                results['cost_optimizations'] = cost_suggestions

        except Exception as e:
            logger.error(f"Error in manual optimization: {e}")
            results['error'] = str(e)

        return results


# Global optimization middleware stack instance
optimization_stack: Optional[OptimizationMiddlewareStack] = None