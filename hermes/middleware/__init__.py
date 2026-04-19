"""
Middleware package for Hermes AI Assistant

This package provides advanced middleware components including:
- Rate limiting and quota management
- Authentication and authorization
- Request/response processing
- Monitoring and telemetry
- Caching and session management
"""

from .rate_limiter import (
    RateLimiter,
    RateLimitConfig,
    RateLimitType,
    RateLimitResult,
    RateLimitMiddleware,
    QuotaType,
    initialize_rate_limiter,
    rate_limiter
)

from .quota_manager import (
    QuotaManager,
    QuotaDefinition,
    QuotaAllocation,
    QuotaUsage,
    QuotaPeriod,
    QuotaStrategy,
    QuotaType as QuotaManagerType,
    QuotaStorageBackend,
    RedisQuotaStorage,
    initialize_quota_manager,
    quota_manager
)

__all__ = [
    # Rate limiting
    "RateLimiter",
    "RateLimitConfig",
    "RateLimitType",
    "RateLimitResult",
    "RateLimitMiddleware",
    "initialize_rate_limiter",
    "rate_limiter",

    # Quota management
    "QuotaManager",
    "QuotaDefinition",
    "QuotaAllocation",
    "QuotaUsage",
    "QuotaPeriod",
    "QuotaStrategy",
    "QuotaManagerType",
    "QuotaStorageBackend",
    "RedisQuotaStorage",
    "initialize_quota_manager",
    "quota_manager",
]