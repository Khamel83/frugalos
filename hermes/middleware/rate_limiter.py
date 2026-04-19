"""
Advanced API Rate Limiting and Quota Management for Hermes AI Assistant

This module provides comprehensive rate limiting and quota management capabilities
including token-based limiting, tiered access, burst handling, and dynamic adjustment.
"""

import asyncio
import json
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union
import redis.asyncio as redis
import logging

logger = logging.getLogger(__name__)


class RateLimitType(Enum):
    """Rate limit types"""
    REQUESTS_PER_MINUTE = "requests_per_minute"
    REQUESTS_PER_HOUR = "requests_per_hour"
    REQUESTS_PER_DAY = "requests_per_day"
    TOKENS_PER_MINUTE = "tokens_per_minute"
    CONCURRENT_REQUESTS = "concurrent_requests"


class QuotaType(Enum):
    """Quota types"""
    MONTHLY_TOKENS = "monthly_tokens"
    MONTHLY_REQUESTS = "monthly_requests"
    DAILY_TOKENS = "daily_tokens"
    DAILY_REQUESTS = "daily_requests"


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    limit_type: RateLimitType
    limit: int
    burst_multiplier: float = 2.0
    penalty_factor: float = 1.5
    decay_rate: float = 0.1
    enabled: bool = True


@dataclass
class QuotaConfig:
    """Quota configuration"""
    quota_type: QuotaType
    limit: int
    reset_period: timedelta
    warning_threshold: float = 0.8
    hard_limit: bool = True
    auto_renewal: bool = True


@dataclass
class ClientQuota:
    """Client quota tracking"""
    client_id: str
    quotas: Dict[QuotaType, int] = field(default_factory=dict)
    resets: Dict[QuotaType, datetime] = field(default_factory=dict)
    warnings_sent: Dict[QuotaType, bool] = field(default_factory=dict)


@dataclass
class RateLimitResult:
    """Rate limit check result"""
    allowed: bool
    remaining: int
    reset_time: Optional[datetime]
    retry_after: Optional[int]
    reason: str
    quota_exceeded: Optional[QuotaType] = None


class SlidingWindowCounter:
    """Sliding window counter for accurate rate limiting"""

    def __init__(self, window_size: int):
        self.window_size = window_size
        self.requests: deque = deque()

    def add_request(self, timestamp: float):
        """Add a request timestamp"""
        self.requests.append(timestamp)
        self._cleanup_old_requests(timestamp)

    def _cleanup_old_requests(self, current_timestamp: float):
        """Remove requests outside the window"""
        cutoff = current_timestamp - self.window_size
        while self.requests and self.requests[0] <= cutoff:
            self.requests.popleft()

    def count(self, current_timestamp: float) -> int:
        """Count requests in the current window"""
        self._cleanup_old_requests(current_timestamp)
        return len(self.requests)


class TokenBucket:
    """Token bucket implementation for burst handling"""

    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()

    def consume(self, tokens: int = 1) -> bool:
        """Consume tokens if available"""
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def _refill(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now


class RateLimiter:
    """
    Advanced rate limiter with Redis backend support
    """

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        self.local_counters: Dict[str, SlidingWindowCounter] = {}
        self.token_buckets: Dict[str, TokenBucket] = {}
        self.client_quotas: Dict[str, ClientQuota] = {}
        self.blocked_clients: Dict[str, datetime] = {}

        # Rate limit configurations
        self.rate_limits = {
            "anonymous": [
                RateLimitConfig(RateLimitType.REQUESTS_PER_MINUTE, 10),
                RateLimitConfig(RateLimitType.REQUESTS_PER_HOUR, 100),
                RateLimitConfig(RateLimitType.CONCURRENT_REQUESTS, 3),
            ],
            "basic": [
                RateLimitConfig(RateLimitType.REQUESTS_PER_MINUTE, 60),
                RateLimitConfig(RateLimitType.REQUESTS_PER_HOUR, 1000),
                RateLimitConfig(RateLimitType.TOKENS_PER_MINUTE, 10000),
                RateLimitConfig(RateLimitType.CONCURRENT_REQUESTS, 10),
            ],
            "premium": [
                RateLimitConfig(RateLimitType.REQUESTS_PER_MINUTE, 300),
                RateLimitConfig(RateLimitType.REQUESTS_PER_HOUR, 10000),
                RateLimitConfig(RateLimitType.TOKENS_PER_MINUTE, 100000),
                RateLimitConfig(RateLimitType.CONCURRENT_REQUESTS, 50),
            ],
            "enterprise": [
                RateLimitConfig(RateLimitType.REQUESTS_PER_MINUTE, 1000),
                RateLimitConfig(RateLimitType.REQUESTS_PER_HOUR, 100000),
                RateLimitConfig(RateLimitType.TOKENS_PER_MINUTE, 1000000),
                RateLimitConfig(RateLimitType.CONCURRENT_REQUESTS, 200),
            ],
        }

        # Quota configurations
        self.quotas = {
            "anonymous": [],
            "basic": [
                QuotaConfig(QuotaType.MONTHLY_TOKENS, 1000000, timedelta(days=30)),
                QuotaConfig(QuotaType.DAILY_TOKENS, 50000, timedelta(days=1)),
            ],
            "premium": [
                QuotaConfig(QuotaType.MONTHLY_TOKENS, 10000000, timedelta(days=30)),
                QuotaConfig(QuotaType.DAILY_TOKENS, 500000, timedelta(days=1)),
            ],
            "enterprise": [
                QuotaConfig(QuotaType.MONTHLY_TOKENS, 100000000, timedelta(days=30)),
                QuotaConfig(QuotaType.DAILY_TOKENS, 5000000, timedelta(days=1)),
            ],
        }

    async def initialize(self):
        """Initialize Redis connection if configured"""
        if self.redis_url:
            try:
                self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
                await self.redis_client.ping()
                logger.info("Rate limiter connected to Redis")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self.redis_client = None

    async def check_rate_limit(
        self,
        client_id: str,
        tier: str = "anonymous",
        token_count: int = 1,
        request_id: Optional[str] = None
    ) -> RateLimitResult:
        """
        Check if request is allowed based on rate limits and quotas

        Args:
            client_id: Client identifier
            tier: Client tier (anonymous, basic, premium, enterprise)
            token_count: Number of tokens being consumed
            request_id: Unique request identifier

        Returns:
            RateLimitResult with decision and metadata
        """
        # Check if client is blocked
        if await self._is_client_blocked(client_id):
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=self.blocked_clients[client_id],
                retry_after=int((self.blocked_clients[client_id] - datetime.now()).total_seconds()),
                reason="Client temporarily blocked due to abuse"
            )

        # Initialize client quota if not exists
        await self._ensure_client_quota(client_id, tier)

        # Check quotas first
        quota_result = await self._check_quotas(client_id, token_count)
        if not quota_result.allowed:
            return quota_result

        # Check rate limits
        rate_limit_result = await self._check_rate_limits(client_id, tier, token_count, request_id)

        # Update counters if allowed
        if rate_limit_result.allowed:
            await self._update_counters(client_id, tier, token_count)
        else:
            # Apply penalty if rate limit exceeded
            await self._apply_penalty(client_id, tier)

        return rate_limit_result

    async def _is_client_blocked(self, client_id: str) -> bool:
        """Check if client is temporarily blocked"""
        if client_id in self.blocked_clients:
            if datetime.now() > self.blocked_clients[client_id]:
                del self.blocked_clients[client_id]
                return False
            return True
        return False

    async def _ensure_client_quota(self, client_id: str, tier: str):
        """Ensure client quota tracking is initialized"""
        if client_id not in self.client_quotas:
            self.client_quotas[client_id] = ClientQuota(client_id=client_id)

            # Initialize quotas for this tier
            for quota_config in self.quotas.get(tier, []):
                self.client_quotas[client_id].quotas[quota_config.quota_type] = 0
                self.client_quotas[client_id].resets[quota_config.quota_type] = \
                    datetime.now() + quota_config.reset_period

    async def _check_quotas(self, client_id: str, token_count: int) -> RateLimitResult:
        """Check if client has remaining quota"""
        client_quota = self.client_quotas[client_id]
        now = datetime.now()

        for quota_type, current_usage in client_quota.quotas.items():
            # Check if quota needs reset
            if now >= client_quota.resets[quota_type]:
                await self._reset_quota(client_id, quota_type)

            # Find quota configuration
            quota_config = self._get_quota_config(quota_type, client_id)
            if not quota_config:
                continue

            # Check if quota exceeded
            if quota_config.hard_limit and current_usage + token_count > quota_config.limit:
                # Send warning if threshold reached
                if (not client_quota.warnings_sent.get(quota_type, False) and
                    current_usage / quota_config.limit >= quota_config.warning_threshold):
                    await self._send_quota_warning(client_id, quota_type, current_usage, quota_config)
                    client_quota.warnings_sent[quota_type] = True

                return RateLimitResult(
                    allowed=False,
                    remaining=max(0, quota_config.limit - current_usage),
                    reset_time=client_quota.resets[quota_type],
                    retry_after=int((client_quota.resets[quota_type] - now).total_seconds()),
                    reason=f"Quota exceeded: {quota_type.value}",
                    quota_exceeded=quota_type
                )

        return RateLimitResult(
            allowed=True,
            remaining=-1,  # Not applicable for quota checks
            reset_time=None,
            retry_after=None,
            reason="Quota check passed"
        )

    async def _check_rate_limits(
        self,
        client_id: str,
        tier: str,
        token_count: int,
        request_id: Optional[str]
    ) -> RateLimitResult:
        """Check rate limits for client"""
        now = time.time()
        rate_limit_configs = self.rate_limits.get(tier, [])

        for config in rate_limit_configs:
            if not config.enabled:
                continue

            key = f"{client_id}:{config.limit_type.value}"

            if config.limit_type == RateLimitType.CONCURRENT_REQUESTS:
                # Check concurrent requests
                if self.redis_client:
                    concurrent = await self.redis_client.get(key)
                    if concurrent and int(concurrent) >= config.limit:
                        return RateLimitResult(
                            allowed=False,
                            remaining=0,
                            reset_time=datetime.now() + timedelta(seconds=60),
                            retry_after=60,
                            reason=f"Concurrent request limit exceeded: {config.limit}"
                        )
            elif config.limit_type == RateLimitType.TOKENS_PER_MINUTE:
                # Check token bucket
                if key not in self.token_buckets:
                    burst_capacity = int(config.limit * config.burst_multiplier)
                    refill_rate = config.limit / 60  # tokens per second
                    self.token_buckets[key] = TokenBucket(burst_capacity, refill_rate)

                if not self.token_buckets[key].consume(token_count):
                    return RateLimitResult(
                        allowed=False,
                        remaining=int(self.token_buckets[key].tokens),
                        reset_time=datetime.now() + timedelta(seconds=60),
                        retry_after=60,
                        reason=f"Token rate limit exceeded: {config.limit} tokens/minute"
                    )
            else:
                # Check sliding window counter
                if self.redis_client:
                    # Redis-based sliding window
                    window_key = f"{key}:window"
                    current_count = await self._redis_sliding_window_count(window_key, config)
                else:
                    # Local sliding window
                    if key not in self.local_counters:
                        window_size = 60 if "MINUTE" in config.limit_type.value else 3600
                        self.local_counters[key] = SlidingWindowCounter(window_size)
                    current_count = self.local_counters[key].count(now)

                if current_count >= config.limit:
                    retry_after = 60 if "MINUTE" in config.limit_type.value else 3600
                    return RateLimitResult(
                        allowed=False,
                        remaining=0,
                        reset_time=datetime.now() + timedelta(seconds=retry_after),
                        retry_after=retry_after,
                        reason=f"Rate limit exceeded: {config.limit} requests/{config.limit_type.value}"
                    )

        return RateLimitResult(
            allowed=True,
            remaining=-1,  # Calculate if needed
            reset_time=None,
            retry_after=None,
            reason="Rate limit check passed"
        )

    async def _update_counters(self, client_id: str, tier: str, token_count: int):
        """Update rate limit counters after successful request"""
        now = time.time()
        rate_limit_configs = self.rate_limits.get(tier, [])

        for config in rate_limit_configs:
            if not config.enabled:
                continue

            key = f"{client_id}:{config.limit_type.value}"

            if config.limit_type == RateLimitType.CONCURRENT_REQUESTS:
                if self.redis_client:
                    await self.redis_client.incr(key)
                    await self.redis_client.expire(key, 300)  # 5 minute timeout
            elif config.limit_type != RateLimitType.TOKENS_PER_MINUTE:
                if self.redis_client:
                    window_key = f"{key}:window"
                    await self.redis_client.zadd(window_key, {str(now): now})
                    await self.redis_client.expire(window_key, 3600)  # 1 hour retention
                else:
                    if key in self.local_counters:
                        self.local_counters[key].add_request(now)

        # Update quotas
        await self._update_quotas(client_id, token_count)

    async def _update_quotas(self, client_id: str, token_count: int):
        """Update client quotas"""
        client_quota = self.client_quotas[client_id]

        # Update token quotas
        if QuotaType.DAILY_TOKENS in client_quota.quotas:
            client_quota.quotas[QuotaType.DAILY_TOKENS] += token_count
        if QuotaType.MONTHLY_TOKENS in client_quota.quotas:
            client_quota.quotas[QuotaType.MONTHLY_TOKENS] += token_count

        # Update request quotas
        if QuotaType.DAILY_REQUESTS in client_quota.quotas:
            client_quota.quotas[QuotaType.DAILY_REQUESTS] += 1
        if QuotaType.MONTHLY_REQUESTS in client_quota.quotas:
            client_quota.quotas[QuotaType.MONTHLY_REQUESTS] += 1

    async def _reset_quota(self, client_id: str, quota_type: QuotaType):
        """Reset client quota"""
        client_quota = self.client_quotas[client_id]
        client_quota.quotas[quota_type] = 0
        client_quota.warnings_sent[quota_type] = False

        # Update reset time
        quota_config = self._get_quota_config(quota_type, client_id)
        if quota_config:
            client_quota.resets[quota_type] = datetime.now() + quota_config.reset_period

    async def _apply_penalty(self, client_id: str, tier: str):
        """Apply penalty for rate limit violation"""
        # Increase block duration based on violation history
        violation_key = f"{client_id}:violations"

        if self.redis_client:
            violations = await self.redis_client.incr(violation_key)
            await self.redis_client.expire(violation_key, 3600)  # 1 hour

            # Calculate block duration (exponential backoff)
            block_duration = min(3600 * (2 ** (violations - 1)), 86400)  # Max 24 hours
        else:
            # Local tracking (simplified)
            violations = 1  # Just use default penalty
            block_duration = 300  # 5 minutes

        self.blocked_clients[client_id] = datetime.now() + timedelta(seconds=block_duration)

        logger.warning(f"Applied penalty to client {client_id}: blocked for {block_duration} seconds")

    async def _send_quota_warning(self, client_id: str, quota_type: QuotaType, current_usage: int, quota_config: QuotaConfig):
        """Send quota warning notification"""
        # In production, this would integrate with notification systems
        logger.warning(
            f"Quota warning for client {client_id}: "
            f"{quota_type.value} usage at {current_usage}/{quota_config.limit} "
            f"({current_usage/quota_config.limit*100:.1f}%)"
        )

    async def _redis_sliding_window_count(self, key: str, config: RateLimitConfig) -> int:
        """Count requests in sliding window using Redis"""
        now = time.time()
        window_size = 60 if "MINUTE" in config.limit_type.value else 3600
        cutoff = now - window_size

        # Remove old entries
        await self.redis_client.zremrangebyscore(key, 0, cutoff)

        # Count current window
        return await self.redis_client.zcard(key)

    def _get_quota_config(self, quota_type: QuotaType, client_id: str) -> Optional[QuotaConfig]:
        """Get quota configuration for client"""
        # This is a simplified implementation
        # In production, you'd look up client-specific quota configurations

        for quota_configs in self.quotas.values():
            for config in quota_configs:
                if config.quota_type == quota_type:
                    return config

        return None

    async def get_client_stats(self, client_id: str) -> Dict:
        """Get client rate limiting statistics"""
        if client_id not in self.client_quotas:
            return {"error": "Client not found"}

        client_quota = self.client_quotas[client_id]
        now = datetime.now()

        stats = {
            "client_id": client_id,
            "quotas": {},
            "is_blocked": client_id in self.blocked_clients,
            "block_expires": self.blocked_clients.get(client_id),
            "last_updated": now.isoformat()
        }

        for quota_type, usage in client_quota.quotas.items():
            quota_config = self._get_quota_config(quota_type, client_id)
            if quota_config:
                remaining = max(0, quota_config.limit - usage)
                reset_time = client_quota.resets.get(quota_type)

                stats["quotas"][quota_type.value] = {
                    "used": usage,
                    "limit": quota_config.limit,
                    "remaining": remaining,
                    "percentage_used": (usage / quota_config.limit) * 100,
                    "reset_time": reset_time.isoformat() if reset_time else None,
                    "time_until_reset": str(reset_time - now) if reset_time else None
                }

        return stats

    async def reset_client_limits(self, client_id: str, admin_key: str) -> bool:
        """Reset client rate limits (admin function)"""
        # Verify admin key (in production, use proper authentication)
        if admin_key != "admin-reset-key-12345":
            return False

        # Remove client from all tracking
        if client_id in self.client_quotas:
            del self.client_quotas[client_id]
        if client_id in self.blocked_clients:
            del self.blocked_clients[client_id]

        # Clean up Redis entries
        if self.redis_client:
            pattern = f"{client_id}:*"
            keys = await self.redis_client.keys(pattern)
            if keys:
                await self.redis_client.delete(*keys)

        logger.info(f"Reset rate limits for client {client_id}")
        return True

    async def update_client_tier(self, client_id: str, new_tier: str) -> bool:
        """Update client tier"""
        # Remove existing quota tracking
        if client_id in self.client_quotas:
            del self.client_quotas[client_id]

        # Initialize new quota tracking
        await self._ensure_client_quota(client_id, new_tier)

        logger.info(f"Updated client {client_id} to tier {new_tier}")
        return True

    async def get_system_stats(self) -> Dict:
        """Get system-wide rate limiting statistics"""
        stats = {
            "total_clients": len(self.client_quotas),
            "blocked_clients": len(self.blocked_clients),
            "local_counters": len(self.local_counters),
            "token_buckets": len(self.token_buckets),
            "redis_connected": self.redis_client is not None,
            "timestamp": datetime.now().isoformat()
        }

        if self.redis_client:
            try:
                info = await self.redis_client.info()
                stats["redis_memory"] = info.get("used_memory_human", "N/A")
                stats["redis_keys"] = info.get("db0", {}).get("keys", 0)
            except Exception as e:
                logger.error(f"Failed to get Redis stats: {e}")

        return stats


# FastAPI integration
class RateLimitMiddleware:
    """
    FastAPI middleware for rate limiting
    """

    def __init__(self, rate_limiter: RateLimiter):
        self.rate_limiter = rate_limiter

    async def __call__(self, request, call_next):
        # Extract client information
        client_ip = request.client.host
        client_id = request.headers.get("X-Client-ID", client_ip)
        tier = request.headers.get("X-Client-Tier", "anonymous")

        # Estimate token count (simplified)
        token_count = 1  # Would calculate based on request content

        # Check rate limits
        result = await self.rate_limiter.check_rate_limit(
            client_id=client_id,
            tier=tier,
            token_count=token_count,
            request_id=request.headers.get("X-Request-ID")
        )

        # Set response headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(result.remaining if result.remaining >= 0 else "unlimited")
        response.headers["X-RateLimit-Remaining"] = str(result.remaining if result.remaining >= 0 else "unlimited")

        if result.reset_time:
            response.headers["X-RateLimit-Reset"] = str(int(result.reset_time.timestamp()))

        if not result.allowed:
            response.status_code = 429
            response.headers["Retry-After"] = str(result.retry_after or 60)

            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": result.reason,
                    "retry_after": result.retry_after,
                    "reset_time": result.reset_time.isoformat() if result.reset_time else None
                }
            )

        return response


# Global rate limiter instance
rate_limiter = RateLimiter()


async def initialize_rate_limiter(redis_url: Optional[str] = None):
    """Initialize the global rate limiter"""
    global rate_limiter
    rate_limiter = RateLimiter(redis_url)
    await rate_limiter.initialize()