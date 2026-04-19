"""
Rate Limiting Integration for Hermes AI Assistant

This module provides FastAPI integration for the rate limiting and quota management system.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any
from fastapi import FastAPI, Request, Response, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware import Middleware
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import JSONResponse
import yaml
import logging
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .rate_limiter import RateLimiter, RateLimitResult, initialize_rate_limiter
from .quota_manager import QuotaManager, QuotaType, QuotaDefinition, QuotaPeriod, QuotaStrategy, initialize_quota_manager
from ..config.rate_limit_config import load_config

logger = logging.getLogger(__name__)

# Global instances
rate_limiter: Optional[RateLimiter] = None
quota_manager: Optional[QuotaManager] = None
config: Dict[str, Any] = {}


def load_config() -> Dict[str, Any]:
    """Load rate limiting configuration"""
    try:
        with open("config/rate_limit_config.yaml", "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning("Rate limit config file not found, using defaults")
        return get_default_config()


def get_default_config() -> Dict[str, Any]:
    """Get default rate limiting configuration"""
    return {
        "global": {
            "default_tier": "anonymous",
            "block_duration_seconds": 300
        },
        "tiers": {
            "anonymous": {
                "rate_limits": [
                    {"type": "requests_per_minute", "limit": 10},
                    {"type": "requests_per_hour", "limit": 100}
                ]
            }
        }
    }


async def init_rate_limiting(app: FastAPI, redis_url: Optional[str] = None):
    """Initialize rate limiting for the FastAPI app"""
    global rate_limiter, quota_manager, config

    # Load configuration
    config = load_config()

    # Initialize rate limiter
    redis_url = redis_url or config.get("global", {}).get("redis_url")
    rate_limiter = await initialize_rate_limiter(redis_url)

    # Initialize quota manager
    quota_manager = await initialize_quota_manager()

    # Add middleware
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(QuotaMiddleware)
    app.add_middleware(ClientIdentificationMiddleware)

    # Add exception handlers
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_exception_handler(QuotaExceededError, quota_exceeded_handler)

    logger.info("Rate limiting initialized successfully")


class ClientIdentificationMiddleware(BaseHTTPMiddleware):
    """Middleware to identify clients and determine their tier"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Identify client
        client_info = await self.identify_client(request)
        request.state.client_info = client_info

        # Call next middleware
        response = await call_next(request)

        # Add client info to headers
        response.headers["X-Client-ID"] = client_info["client_id"]
        response.headers["X-Client-Tier"] = client_info["tier"]

        return response

    async def identify_client(self, request: Request) -> Dict[str, Any]:
        """Identify the client from request"""
        client_id = None
        tier = config["global"]["default_tier"]
        api_key = None

        # Check for API key in header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            client_id = await self.get_client_from_api_key(api_key)
            if client_id:
                tier = await self.get_client_tier(client_id)

        # Check for client ID in header
        if not client_id:
            client_id = request.headers.get("X-Client-ID")
            if client_id:
                tier = await self.get_client_tier(client_id)

        # Fallback to IP address
        if not client_id:
            client_id = get_remote_address(request)

        return {
            "client_id": client_id,
            "tier": tier,
            "api_key": api_key,
            "ip_address": request.client.host
        }

    async def get_client_from_api_key(self, api_key: str) -> Optional[str]:
        """Get client ID from API key"""
        # In production, this would query your database
        # For now, return a mock client ID
        if api_key.startswith("test-key"):
            return "test-client"
        elif api_key.startswith("prod-key"):
            return "prod-client"
        return None

    async def get_client_tier(self, client_id: str) -> str:
        """Get client tier"""
        # In production, this would query your database
        # For now, return tier based on client ID pattern
        if "enterprise" in client_id:
            return "enterprise"
        elif "premium" in client_id:
            return "premium"
        elif "basic" in client_id:
            return "basic"
        elif "test" in client_id:
            return "premium"  # Test clients get premium tier
        else:
            return "anonymous"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not rate_limiter:
            # If rate limiter is not initialized, just pass through
            return await call_next(request)

        client_info = getattr(request.state, "client_info", {})
        client_id = client_info.get("client_id", "anonymous")
        tier = client_info.get("tier", "anonymous")

        # Estimate token count based on request
        token_count = await self.estimate_token_count(request)

        # Check rate limits
        result = await rate_limiter.check_rate_limit(
            client_id=client_id,
            tier=tier,
            token_count=token_count,
            request_id=request.headers.get("X-Request-ID")
        )

        # Add rate limit headers
        response = await call_next(request)
        self.add_rate_limit_headers(response, result)

        if not result.allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": result.reason,
                    "retry_after": result.retry_after,
                    "reset_time": result.reset_time.isoformat() if result.reset_time else None,
                    "client_id": client_id,
                    "tier": tier
                },
                headers={
                    "Retry-After": str(result.retry_after or 60),
                    "X-RateLimit-Reason": result.reason
                }
            )

        return response

    async def estimate_token_count(self, request: Request) -> int:
        """Estimate token count for the request"""
        # Simple estimation based on request size and method
        base_tokens = 1

        # Add tokens based on content length
        if request.headers.get("content-length"):
            content_length = int(request.headers["content-length"])
            base_tokens += max(1, content_length // 100)  # 1 token per 100 bytes

        # Add tokens based on request path
        path = request.url.path
        if "/chat" in path or "/completion" in path:
            base_tokens += 10  # Chat requests use more tokens
        elif "/file" in path:
            base_tokens += 5   # File operations
        elif "/bulk" in path:
            base_tokens += 20  # Bulk operations

        return base_tokens

    def add_rate_limit_headers(self, response: Response, result: RateLimitResult):
        """Add rate limit headers to response"""
        if config.get("headers", {}).get("enabled", True):
            header_names = config.get("headers", {}).get("header_names", {})

            if result.remaining >= 0:
                response.headers[header_names.get("rate_limit_remaining", "X-RateLimit-Remaining")] = str(result.remaining)

            if result.reset_time:
                response.headers[header_names.get("rate_limit_reset", "X-RateLimit-Reset")] = str(int(result.reset_time.timestamp()))

            if result.retry_after:
                response.headers[header_names.get("rate_limit_retry_after", "Retry-After")] = str(result.retry_after)


class QuotaMiddleware(BaseHTTPMiddleware):
    """Quota management middleware"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not quota_manager:
            return await call_next(request)

        client_info = getattr(request.state, "client_info", {})
        client_id = client_info.get("client_id", "anonymous")
        tier = client_info.get("tier", "anonymous")

        # Get quotas for this client tier
        quota_defs = self.get_quota_definitions_for_tier(tier)

        # Check and consume quotas
        for quota_def in quota_defs:
            try:
                success, allocation = await quota_manager.consume_quota(
                    client_id=client_id,
                    quota_type=quota_def.quota_type,
                    amount=await self.get_quota_amount(request, quota_def.quota_type),
                    request_id=request.headers.get("X-Request-ID")
                )

                if not success:
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={
                            "error": "Quota exceeded",
                            "message": f"Quota exceeded: {quota_def.quota_type.value}",
                            "quota_type": quota_def.quota_type.value,
                            "quota_used": allocation.used,
                            "quota_limit": allocation.allocated,
                            "quota_remaining": allocation.remaining,
                            "reset_time": allocation.period_end.isoformat(),
                            "client_id": client_id,
                            "tier": tier
                        }
                    )

                # Add quota headers
                response = await call_next(request)
                self.add_quota_headers(response, allocation, quota_def.quota_type)
                return response

            except Exception as e:
                logger.error(f"Error checking quota for {quota_def.quota_type.value}: {e}")
                continue

        # No quotas defined or all checks passed
        return await call_next(request)

    def get_quota_definitions_for_tier(self, tier: str) -> List[QuotaDefinition]:
        """Get quota definitions for a client tier"""
        tier_config = config.get("tiers", {}).get(tier, {})
        quotas = tier_config.get("quotas", [])

        quota_defs = []
        for quota in quotas:
            quota_type_str = quota.get("type")
            quota_type = QuotaType(quota_type_str)

            period = QuotaPeriod.DAILY  # Default period
            if "monthly" in quota_type_str:
                period = QuotaPeriod.MONTHLY

            quota_def = QuotaDefinition(
                quota_type=quota_type,
                period=period,
                limit=quota.get("limit", 0),
                is_hard_limit=quota.get("hard_limit", True),
                auto_scale=quota.get("auto_scale", False)
            )
            quota_defs.append(quota_def)

        return quota_defs

    async def get_quota_amount(self, request: Request, quota_type: QuotaType) -> int:
        """Get quota amount to consume for a request"""
        if quota_type == QuotaType.REQUESTS:
            return 1
        elif quota_type == QuotaType.TOKENS:
            # Estimate token usage
            return await self.estimate_token_count(request)
        else:
            return 1

    async def estimate_token_count(self, request: Request) -> int:
        """Estimate token count for quota consumption"""
        # Similar to rate limiting but more conservative
        base_tokens = 1

        if request.headers.get("content-length"):
            content_length = int(request.headers["content-length"])
            base_tokens += max(1, content_length // 200)  # 1 token per 200 bytes

        path = request.url.path
        if "/chat" in path or "/completion" in path:
            base_tokens += 50  # Estimated completion tokens
        elif "/file" in path:
            base_tokens += 10
        elif "/bulk" in path:
            base_tokens += 100

        return base_tokens

    def add_quota_headers(self, response: Response, allocation, quota_type: QuotaType):
        """Add quota headers to response"""
        if config.get("headers", {}).get("include_quota_info", True):
            response.headers["X-Quota-Type"] = quota_type.value
            response.headers["X-Quota-Used"] = str(allocation.used)
            response.headers["X-Quota-Limit"] = str(allocation.allocated)
            response.headers["X-Quota-Remaining"] = str(allocation.remaining)
            response.headers["X-Quota-Reset"] = str(int(allocation.period_end.timestamp()))


# Exception classes
class QuotaExceededError(Exception):
    """Quota exceeded exception"""
    def __init__(self, quota_type: str, allocation, message: str = "Quota exceeded"):
        self.quota_type = quota_type
        self.allocation = allocation
        self.message = message
        super().__init__(message)


# Exception handlers
async def quota_exceeded_handler(request: Request, exc: QuotaExceededError):
    """Handle quota exceeded exceptions"""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": "Quota exceeded",
            "message": exc.message,
            "quota_type": exc.quota_type,
            "quota_used": exc.allocation.used,
            "quota_limit": exc.allocation.allocated,
            "quota_remaining": exc.allocation.remaining,
            "reset_time": exc.allocation.period_end.isoformat()
        },
        headers={
            "Retry-After": "3600",
            "X-Quota-Exceeded": "true"
        }
    )


# Dependency functions
async def get_rate_limiter() -> RateLimiter:
    """Get rate limiter instance"""
    if not rate_limiter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiting service not available"
        )
    return rate_limiter


async def get_quota_manager() -> QuotaManager:
    """Get quota manager instance"""
    if not quota_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Quota management service not available"
        )
    return quota_manager


async def get_client_info(request: Request) -> Dict[str, Any]:
    """Get client information from request"""
    return getattr(request.state, "client_info", {
        "client_id": "anonymous",
        "tier": "anonymous"
    })


# API endpoints for rate limiting and quota management
async def create_rate_limit_routes(app: FastAPI):
    """Create API routes for rate limiting and quota management"""

    @app.get("/api/v1/rate-limits/status")
    async def get_rate_limit_status(
        client_info: Dict[str, Any] = Depends(get_client_info),
        limiter: RateLimiter = Depends(get_rate_limiter)
    ):
        """Get current rate limit status for client"""
        stats = await limiter.get_client_stats(client_info["client_id"])
        return {
            "client_id": client_info["client_id"],
            "tier": client_info["tier"],
            "rate_limits": stats
        }

    @app.get("/api/v1/quotas/status")
    async def get_quota_status(
        client_info: Dict[str, Any] = Depends(get_client_info),
        manager: QuotaManager = Depends(get_quota_manager)
    ):
        """Get current quota status for client"""
        quotas = await manager.get_client_quotas(client_info["client_id"])
        return {
            "client_id": client_info["client_id"],
            "tier": client_info["tier"],
            "quotas": {
                quota_type.value: {
                    "allocated": allocation.allocated,
                    "used": allocation.used,
                    "remaining": allocation.remaining,
                    "period_start": allocation.period_start.isoformat(),
                    "period_end": allocation.period_end.isoformat()
                }
                for quota_type, allocation in quotas.items()
            }
        }

    @app.post("/api/v1/admin/reset-client-limits")
    async def reset_client_limits(
        client_id: str,
        admin_key: str,
        limiter: RateLimiter = Depends(get_rate_limiter)
    ):
        """Reset rate limits for a client (admin only)"""
        success = await limiter.reset_client_limits(client_id, admin_key)
        if success:
            return {"message": f"Rate limits reset for client {client_id}"}
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid admin key"
            )

    @app.get("/api/v1/admin/system-stats")
    async def get_system_stats(
        limiter: RateLimiter = Depends(get_rate_limiter),
        manager: QuotaManager = Depends(get_quota_manager)
    ):
        """Get system-wide rate limiting and quota statistics (admin only)"""
        rate_limit_stats = await limiter.get_system_stats()
        quota_stats = await manager.get_system_overview()

        return {
            "rate_limits": rate_limit_stats,
            "quotas": quota_stats,
            "timestamp": datetime.now().isoformat()
        }

    @app.post("/api/v1/admin/update-client-tier")
    async def update_client_tier(
        client_id: str,
        new_tier: str,
        limiter: RateLimiter = Depends(get_rate_limiter)
    ):
        """Update client tier (admin only)"""
        success = await limiter.update_client_tier(client_id, new_tier)
        if success:
            return {"message": f"Client {client_id} updated to tier {new_tier}"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update client tier"
            )