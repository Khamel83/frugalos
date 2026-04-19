"""
Advanced caching system with multiple strategies and intelligent cache management.

This module provides comprehensive caching capabilities including:
- Multi-tier caching (L1: in-memory, L2: Redis, L3: database)
- Intelligent cache warming and invalidation
- Cache compression and serialization
- Performance monitoring and optimization
"""

import asyncio
import pickle
import gzip
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable, Tuple
from dataclasses import dataclass, field
from collections import OrderedDict
from contextlib import asynccontextmanager
import logging
from enum import Enum

import redis.asyncio as redis
import mmh3  # MurmurHash3 for better hash distribution
from cachetools import TTLCache, LFUCache, LRUCache
import numpy as np

logger = logging.getLogger(__name__)


class CacheStrategy(Enum):
    """Cache eviction strategies."""
    LRU = "lru"
    LFU = "lfu"
    TTL = "ttl"
    FIFO = "fifo"


class CacheTier(Enum):
    """Cache tiers."""
    L1_MEMORY = "l1_memory"
    L2_REDIS = "l2_redis"
    L3_DATABASE = "l3_database"


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    key: str
    value: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    size_bytes: int = 0
    ttl: Optional[int] = None
    tier: CacheTier = CacheTier.L1_MEMORY
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CacheStats:
    """Cache performance statistics."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    size_bytes: int = 0
    entry_count: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate hit rate percentage."""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0


class MemoryCache:
    """L1 in-memory cache with configurable eviction strategies."""

    def __init__(self, max_size: int = 1000, strategy: CacheStrategy = CacheStrategy.LRU):
        self.max_size = max_size
        self.strategy = strategy
        self.stats = CacheStats()

        # Initialize cache based on strategy
        if strategy == CacheStrategy.LRU:
            self._cache = OrderedDict()
        elif strategy == CacheStrategy.LFU:
            self._cache = {}
            self._access_counts = {}
        elif strategy == CacheStrategy.TTL:
            self._cache = TTLCache(maxsize=max_size, ttl=300)  # 5 minutes default TTL
        else:  # FIFO
            self._cache = OrderedDict()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if self.strategy == CacheStrategy.LRU:
            if key in self._cache:
                value = self._cache.pop(key)
                self._cache[key] = value  # Move to end
                self.stats.hits += 1
                return value.value
        elif self.strategy == CacheStrategy.LFU:
            if key in self._cache:
                self._access_counts[key] = self._access_counts.get(key, 0) + 1
                self.stats.hits += 1
                return self._cache[key].value
        elif self.strategy == CacheStrategy.TTL:
            try:
                value = self._cache[key]
                self.stats.hits += 1
                return value.value
            except KeyError:
                pass
        else:  # FIFO
            if key in self._cache:
                self.stats.hits += 1
                return self._cache[key].value

        self.stats.misses += 1
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None, tags: List[str] = None) -> bool:
        """Set value in cache."""
        try:
            # Check if eviction is needed
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict()

            # Create cache entry
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=datetime.utcnow(),
                last_accessed=datetime.utcnow(),
                access_count=1,
                size_bytes=self._calculate_size(value),
                ttl=ttl,
                tier=CacheTier.L1_MEMORY,
                tags=tags or []
            )

            if self.strategy == CacheStrategy.LRU:
                self._cache[key] = entry
            elif self.strategy == CacheStrategy.LFU:
                self._cache[key] = entry
                self._access_counts[key] = 1
            elif self.strategy == CacheStrategy.TTL:
                # TTL cache handles its own eviction
                self._cache[key] = entry
            else:  # FIFO
                self._cache[key] = entry

            self.stats.sets += 1
            self.stats.entry_count = len(self._cache)
            self.stats.size_bytes = sum(entry.size_bytes for entry in self._cache.values())
            return True

        except Exception as e:
            logger.error(f"Error setting cache entry: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete entry from cache."""
        deleted = False

        if self.strategy == CacheStrategy.LRU or self.strategy == CacheStrategy.FIFO:
            if key in self._cache:
                del self._cache[key]
                deleted = True
        elif self.strategy == CacheStrategy.LFU:
            if key in self._cache:
                del self._cache[key]
                if key in self._access_counts:
                    del self._access_counts[key]
                deleted = True
        elif self.strategy == CacheStrategy.TTL:
            try:
                del self._cache[key]
                deleted = True
            except KeyError:
                pass

        if deleted:
            self.stats.deletes += 1
            self.stats.entry_count = len(self._cache)
            self.stats.size_bytes = sum(entry.size_bytes for entry in self._cache.values())

        return deleted

    def _evict(self):
        """Evict entries based on strategy."""
        if not self._cache:
            return

        if self.strategy == CacheStrategy.LRU:
            # Remove least recently used (first item)
            self._cache.popitem(last=False)
            self.stats.evictions += 1
        elif self.strategy == CacheStrategy.LFU:
            # Remove least frequently used
            if self._access_counts:
                lfu_key = min(self._access_counts, key=self._access_counts.get)
                del self._cache[lfu_key]
                del self._access_counts[lfu_key]
                self.stats.evictions += 1
        elif self.strategy == CacheStrategy.FIFO:
            # Remove first inserted
            self._cache.popitem(last=False)
            self.stats.evictions += 1

    def _calculate_size(self, value: Any) -> int:
        """Calculate approximate size of cached value."""
        try:
            return len(pickle.dumps(value))
        except Exception:
            return len(str(value).encode())

    def clear(self):
        """Clear all cache entries."""
        self._cache.clear()
        if self.strategy == CacheStrategy.LFU:
            self._access_counts.clear()
        self.stats.entry_count = 0
        self.stats.size_bytes = 0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'hits': self.stats.hits,
            'misses': self.stats.misses,
            'sets': self.stats.sets,
            'deletes': self.stats.deletes,
            'evictions': self.stats.evictions,
            'hit_rate': self.stats.hit_rate,
            'size_bytes': self.stats.size_bytes,
            'entry_count': self.stats.entry_count,
            'max_size': self.max_size,
            'strategy': self.strategy.value
        }


class RedisCache:
    """L2 Redis-based distributed cache."""

    def __init__(self, redis_client: redis.Redis, key_prefix: str = "hermes_cache"):
        self.redis = redis_client
        self.key_prefix = key_prefix
        self.stats = CacheStats()
        self.compression_threshold = 1024  # Compress values larger than 1KB

    def _make_key(self, key: str) -> str:
        """Create Redis key with prefix."""
        return f"{self.key_prefix}:{key}"

    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache."""
        try:
            redis_key = self._make_key(key)
            data = await self.redis.get(redis_key)

            if data:
                # Decompress if needed
                if data.startswith(b'COMPRESSED:'):
                    data = gzip.decompress(data[11:])  # Remove 'COMPRESSED:' prefix

                value = pickle.loads(data)
                self.stats.hits += 1
                return value
            else:
                self.stats.misses += 1
                return None

        except Exception as e:
            logger.error(f"Error getting from Redis cache: {e}")
            self.stats.misses += 1
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None,
                  tags: List[str] = None) -> bool:
        """Set value in Redis cache."""
        try:
            redis_key = self._make_key(key)

            # Serialize value
            serialized = pickle.dumps(value)

            # Compress if value is large
            if len(serialized) > self.compression_threshold:
                serialized = b'COMPRESSED:' + gzip.compress(serialized)

            # Store in Redis
            if ttl:
                await self.redis.setex(redis_key, ttl, serialized)
            else:
                await self.redis.set(redis_key, serialized)

            # Store tags if provided
            if tags:
                await self._store_tags(key, tags)

            self.stats.sets += 1
            return True

        except Exception as e:
            logger.error(f"Error setting Redis cache: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete entry from Redis cache."""
        try:
            redis_key = self._make_key(key)
            result = await self.redis.delete(redis_key)

            # Delete tag references
            await self._remove_tags(key)

            if result:
                self.stats.deletes += 1
                return True
            return False

        except Exception as e:
            logger.error(f"Error deleting from Redis cache: {e}")
            return False

    async def _store_tags(self, key: str, tags: List[str]):
        """Store tags for cache invalidation."""
        for tag in tags:
            tag_key = f"{self.key_prefix}:tag:{tag}"
            await self.redis.sadd(tag_key, key)
            await self.redis.expire(tag_key, 86400)  # 24 hours

    async def _remove_tags(self, key: str):
        """Remove tag references."""
        # Find all tags that contain this key
        pattern = f"{self.key_prefix}:tag:*"
        keys = await self.redis.keys(pattern)

        for tag_key in keys:
            await self.redis.srem(tag_key, key)

    async def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all entries with a specific tag."""
        try:
            tag_key = f"{self.key_prefix}:tag:{tag}"
            keys = await self.redis.smembers(tag_key)

            if keys:
                # Delete all keys with this tag
                redis_keys = [self._make_key(key.decode()) for key in keys]
                await self.redis.delete(*redis_keys)

            # Clean up tag set
            await self.redis.delete(tag_key)

            return len(keys)

        except Exception as e:
            logger.error(f"Error invalidating by tag {tag}: {e}")
            return 0

    async def get_stats(self) -> Dict[str, Any]:
        """Get Redis cache statistics."""
        try:
            info = await self.redis.info('memory')
            return {
                'hits': self.stats.hits,
                'misses': self.stats.misses,
                'sets': self.stats.sets,
                'deletes': self.stats.deletes,
                'hit_rate': self.stats.hit_rate,
                'redis_memory_used': info.get('used_memory', 0),
                'redis_memory_human': info.get('used_memory_human', '0B'),
                'redis_connected_clients': await self.redis.dbsize()
            }
        except Exception as e:
            logger.error(f"Error getting Redis stats: {e}")
            return {'error': str(e)}


class MultiTierCache:
    """Multi-tier cache with intelligent data placement."""

    def __init__(self, l1_cache: MemoryCache, l2_cache: RedisCache):
        self.l1_cache = l1_cache
        self.l2_cache = l2_cache
        self.stats = CacheStats()
        self.warmup_tasks: Dict[str, asyncio.Task] = {}

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache (L1 -> L2 cascade)."""
        # Try L1 cache first
        value = self.l1_cache.get(key)
        if value is not None:
            self.stats.hits += 1
            return value

        # Try L2 cache
        value = await self.l2_cache.get(key)
        if value is not None:
            # Promote to L1 cache
            self.l1_cache.set(key, value)
            self.stats.hits += 1
            return value

        self.stats.misses += 1
        return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None,
                  tags: List[str] = None, store_in_l1: bool = True) -> bool:
        """Set value in cache tiers."""
        success = True

        # Store in L2 cache (always)
        l2_success = await self.l2_cache.set(key, value, ttl, tags)
        success = success and l2_success

        # Store in L1 cache if requested
        if store_in_l1:
            l1_success = self.l1_cache.set(key, value, ttl, tags)
            success = success and l1_success

        if success:
            self.stats.sets += 1

        return success

    async def delete(self, key: str) -> bool:
        """Delete from all cache tiers."""
        l1_success = self.l1_cache.delete(key)
        l2_success = await self.l2_cache.delete(key)

        if l1_success or l2_success:
            self.stats.deletes += 1
            return True
        return False

    async def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate entries by tag across all tiers."""
        # Invalidate from L2 (which handles tags)
        l2_count = await self.l2_cache.invalidate_by_tag(tag)

        # Clear entire L1 since we don't have tag information there
        # In a production system, you'd maintain tag mappings in L1 too
        self.l1_cache.clear()

        return l2_count

    async def warm_up(self, warmup_keys: List[str], data_loader: Callable[[str], Any]):
        """Warm up cache with predefined keys."""
        tasks = []
        for key in warmup_keys:
            task = asyncio.create_task(self._warm_up_key(key, data_loader))
            tasks.append(task)
            self.warmup_tasks[key] = task

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _warm_up_key(self, key: str, data_loader: Callable[[str], Any]):
        """Warm up a single cache key."""
        try:
            # Check if already cached
            if await self.get(key) is not None:
                return

            # Load data and cache it
            value = await data_loader(key)
            if value is not None:
                await self.set(key, value, ttl=3600)  # 1 hour TTL

        except Exception as e:
            logger.error(f"Error warming up cache key {key}: {e}")
        finally:
            if key in self.warmup_tasks:
                del self.warmup_tasks[key]

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        l1_stats = self.l1_cache.get_stats()
        l2_stats = asyncio.create_task(self.l2_cache.get_stats()) if hasattr(self.l2_cache, 'get_stats') else {}

        return {
            'multi_tier': {
                'hits': self.stats.hits,
                'misses': self.stats.misses,
                'sets': self.stats.sets,
                'deletes': self.stats.deletes,
                'hit_rate': self.stats.hit_rate
            },
            'l1_memory': l1_stats,
            'l2_redis': l2_stats
        }


class CacheWarmer:
    """Intelligent cache warming system."""

    def __init__(self, cache: MultiTierCache):
        self.cache = cache
        self.warmup_patterns: Dict[str, Callable[[], List[str]]] = {}
        self.warmup_schedules: Dict[str, Dict[str, Any]] = {}

    def register_warmup_pattern(self, name: str, key_generator: Callable[[], List[str]],
                               schedule: Dict[str, Any] = None):
        """Register a warmup pattern with schedule."""
        self.warmup_patterns[name] = key_generator
        self.warmup_schedules[name] = schedule or {'interval': 300}  # 5 minutes default

    async def run_warmup(self, pattern_name: str, data_loader: Callable[[str], Any]):
        """Run warmup for a specific pattern."""
        if pattern_name not in self.warmup_patterns:
            logger.error(f"Warmup pattern {pattern_name} not found")
            return

        try:
            keys = self.warmup_patterns[pattern_name]()
            if keys:
                logger.info(f"Warming up cache with {len(keys)} keys for pattern {pattern_name}")
                await self.cache.warm_up(keys, data_loader)
        except Exception as e:
            logger.error(f"Error in warmup pattern {pattern_name}: {e}")

    async def start_scheduled_warmups(self, data_loader: Callable[[str], Any]):
        """Start all scheduled warmup tasks."""
        tasks = []
        for pattern_name, schedule in self.warmup_schedules.items():
            task = asyncio.create_task(
                self._scheduled_warmup(pattern_name, data_loader, schedule)
            )
            tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _scheduled_warmup(self, pattern_name: str, data_loader: Callable[[str], Any],
                               schedule: Dict[str, Any]):
        """Run scheduled warmup task."""
        interval = schedule.get('interval', 300)
        while True:
            try:
                await self.run_warmup(pattern_name, data_loader)
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduled warmup {pattern_name}: {e}")
                await asyncio.sleep(interval)


class CacheDecorator:
    """Cache decorator for functions and methods."""

    def __init__(self, cache: MultiTierCache, ttl: Optional[int] = None,
                 key_generator: Optional[Callable[..., str]] = None,
                 tags: List[str] = None):
        self.cache = cache
        self.ttl = ttl
        self.key_generator = key_generator or self._default_key_generator
        self.tags = tags or []

    def _default_key_generator(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Generate default cache key."""
        # Create a deterministic key from function name and arguments
        key_data = f"{func_name}:{str(args)}:{str(sorted(kwargs.items()))}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def __call__(self, func: Callable) -> Callable:
        """Decorate a function with caching."""
        if asyncio.iscoroutinefunction(func):
            return self._decorate_async(func)
        else:
            return self._decorate_sync(func)

    def _decorate_async(self, func: Callable) -> Callable:
        """Decorate async function."""
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = self.key_generator(func.__name__, args, kwargs)

            # Try to get from cache
            result = await self.cache.get(cache_key)
            if result is not None:
                return result

            # Execute function and cache result
            result = await func(*args, **kwargs)
            await self.cache.set(cache_key, result, self.ttl, self.tags)
            return result

        return wrapper

    def _decorate_sync(self, func: Callable) -> Callable:
        """Decorate sync function."""
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = self.key_generator(func.__name__, args, kwargs)

            # Try to get from cache
            result = await self.cache.get(cache_key)
            if result is not None:
                return result

            # Execute function and cache result
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            await self.cache.set(cache_key, result, self.ttl, self.tags)
            return result

        # If original function is sync, return sync wrapper
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(async_wrapper(*args, **kwargs))

        return sync_wrapper if not asyncio.iscoroutinefunction(func) else async_wrapper


# Utility functions
def cached(ttl: Optional[int] = None, key: Optional[str] = None, tags: List[str] = None):
    """Cache decorator factory."""
    def decorator(func: Callable) -> Callable:
        # This will be initialized when the cache system is set up
        func._cached = True
        func._cache_ttl = ttl
        func._cache_key = key
        func._cache_tags = tags
        return func
    return decorator


@asynccontextmanager
async def cache_transaction(cache: MultiTierCache):
    """Context manager for cache operations with rollback."""
    operations = []

    async def set_op(key: str, value: Any, ttl: Optional[int] = None):
        operations.append(('set', key, value, ttl))

    async def delete_op(key: str):
        operations.append(('delete', key))

    try:
        yield {'set': set_op, 'delete': delete_op}

        # Commit all operations
        for op in operations:
            if op[0] == 'set':
                await cache.set(op[1], op[2], op[3])
            elif op[0] == 'delete':
                await cache.delete(op[1])

    except Exception:
        # Rollback - operations weren't executed yet
        logger.warning("Cache transaction rolled back")
        raise


# Global cache instances
l1_cache = MemoryCache(max_size=1000, strategy=CacheStrategy.LRU)
l2_cache: Optional[RedisCache] = None
multi_tier_cache: Optional[MultiTierCache] = None
cache_warmer: Optional[CacheWarmer] = None