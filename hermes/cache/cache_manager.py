"""
Advanced Cache Manager
Multi-tier caching with LRU, TTL, and intelligent eviction
"""

import logging
import time
import threading
import hashlib
import pickle
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import OrderedDict
import json

from ..config import Config
from ..database import Database
from ..logger import get_logger

logger = get_logger('cache.manager')

@dataclass
class CacheConfig:
    """Cache configuration"""
    max_memory_items: int = 1000
    max_memory_size_mb: int = 100
    max_disk_items: int = 10000
    disk_cache_dir: str = "cache"
    default_ttl_seconds: int = 3600
    enable_compression: bool = True
    enable_persistence: bool = True
    cleanup_interval_seconds: int = 300

@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    created_at: datetime
    accessed_at: datetime
    access_count: int = 0
    ttl_seconds: Optional[int] = None
    size_bytes: int = 0
    hits: int = 0
    misses: int = 0

@dataclass
class CacheStats:
    """Cache statistics"""
    total_entries: int = 0
    memory_entries: int = 0
    disk_entries: int = 0
    total_hits: int = 0
    total_misses: int = 0
    memory_usage_mb: float = 0.0
    disk_usage_mb: float = 0.0
    hit_rate: float = 0.0
    eviction_count: int = 0

class CacheManager:
    """Advanced multi-tier cache manager"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.logger = get_logger('cache_manager')

        # Cache configuration
        self.cache_config = CacheConfig()
        self._load_cache_config()

        # Cache storage
        self._memory_cache = OrderedDict()  # LRU cache
        self._disk_cache_index = {}  # Track disk entries
        self._cache_lock = threading.RLock()

        # Statistics
        self._stats = CacheStats()
        self._stats_lock = threading.Lock()

        # Background cleanup
        self._cleanup_thread = None
        self._running = False

        # Initialize
        self._initialize_cache()

    def _load_cache_config(self):
        """Load cache configuration from config"""
        cache_config = self.config.get('cache', {})

        self.cache_config.max_memory_items = cache_config.get('max_memory_items', 1000)
        self.cache_config.max_memory_size_mb = cache_config.get('max_memory_size_mb', 100)
        self.cache_config.max_disk_items = cache_config.get('max_disk_items', 10000)
        self.cache_config.disk_cache_dir = cache_config.get('disk_cache_dir', 'cache')
        self.cache_config.default_ttl_seconds = cache_config.get('default_ttl_seconds', 3600)
        self.cache_config.enable_compression = cache_config.get('enable_compression', True)
        self.cache_config.enable_persistence = cache_config.get('enable_persistence', True)

    def _initialize_cache(self):
        """Initialize cache systems"""
        import os

        # Create cache directory
        os.makedirs(self.cache_config.disk_cache_dir, exist_ok=True)

        # Load persistent cache if enabled
        if self.cache_config.enable_persistence:
            self._load_persistent_cache()

        # Start background cleanup
        self._start_cleanup()

        self.logger.info("Cache manager initialized")

    def _load_persistent_cache(self):
        """Load cache entries from persistent storage"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT key, value, created_at, accessed_at, access_count,
                           ttl_seconds, size_bytes, hits, misses
                    FROM cache_entries
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (self.cache_config.max_memory_items,))

                for row in cursor.fetchall():
                    # Deserialize value
                    try:
                        value = pickle.loads(row['value'])

                        entry = CacheEntry(
                            key=row['key'],
                            value=value,
                            created_at=datetime.fromisoformat(row['created_at']),
                            accessed_at=datetime.fromisoformat(row['accessed_at']),
                            access_count=row['access_count'],
                            ttl_seconds=row['ttl_seconds'],
                            size_bytes=row['size_bytes'],
                            hits=row['hits'],
                            misses=row['misses']
                        )

                        # Check if entry is still valid
                        if self._is_entry_valid(entry):
                            self._memory_cache[entry.key] = entry
                            self._stats.total_entries += 1
                            self._stats.memory_entries += 1

                    except Exception as e:
                        self.logger.error(f"Error loading cache entry {row['key']}: {e}")

            self.logger.info(f"Loaded {self._stats.memory_entries} persistent cache entries")

        except Exception as e:
            self.logger.error(f"Error loading persistent cache: {e}")

    def _start_cleanup(self):
        """Start background cleanup thread"""
        self._running = True
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def _cleanup_loop(self):
        """Background cleanup loop"""
        while self._running:
            try:
                self._cleanup_expired_entries()
                self._evict_if_needed()
                time.sleep(self.cache_config.cleanup_interval_seconds)
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")

    def _cleanup_expired_entries(self):
        """Remove expired entries from cache"""
        now = datetime.now()
        expired_keys = []

        with self._cache_lock:
            for key, entry in self._memory_cache.items():
                if self._is_entry_expired(entry, now):
                    expired_keys.append(key)

            for key in expired_keys:
                del self._memory_cache[key]
                self._stats.total_entries -= 1
                self._stats.memory_entries -= 1

        # Clean up disk cache too
        disk_expired_keys = []
        for key, entry in self._disk_cache_index.items():
            if self._is_entry_expired(entry, now):
                disk_expired_keys.append(key)

        for key in disk_expired_keys:
            self._remove_disk_entry(key)

        if expired_keys or disk_expired_keys:
            self.logger.debug(f"Cleaned up {len(expired_keys)} memory and {len(disk_expired_keys)} disk expired entries")

    def _evict_if_needed(self):
        """Evict entries if cache is over limits"""
        with self._cache_lock:
            # Check memory limits
            if len(self._memory_cache) > self.cache_config.max_memory_items:
                self._evict_lru_memory()

            # Check disk limits
            if len(self._disk_cache_index) > self.cache_config.max_disk_items:
                self._evict_lru_disk()

            # Check memory size limit
            total_memory_size = sum(
                self._calculate_size(entry.value)
                for entry in self._memory_cache.values()
            ) / (1024 * 1024)  # MB

            if total_memory_size > self.cache_config.max_memory_size_mb:
                self._evict_lru_memory()

    def _evict_lru_memory(self):
        """Evict least recently used entries from memory cache"""
        target_size = int(self.cache_config.max_memory_items * 0.8)

        while len(self._memory_cache) > target_size:
            if self._memory_cache:
                # OrderedDict maintains insertion order
                key, entry = self._memory_cache.popitem(last=False)
                self._move_to_disk_if_needed(entry)
                self._stats.total_entries -= 1
                self._stats.memory_entries -= 1
                self._stats.eviction_count += 1
            else:
                break

    def _evict_lru_disk(self):
        """Evict least recently used entries from disk cache"""
        target_size = int(self.cache_config.max_disk_items * 0.8)

        # Sort by last access time
        disk_entries = sorted(
            self._disk_cache_index.items(),
            key=lambda x: x[1].accessed_at
        )

        evict_count = len(self._disk_cache_index) - target_size
        for i in range(min(evict_count, len(disk_entries))):
            key = disk_entries[i][0]
            self._remove_disk_entry(key)
            self._stats.eviction_count += 1

    def _move_to_disk_if_needed(self, entry: CacheEntry):
        """Move entry to disk cache if it should be persisted"""
        if self.cache_config.enable_persistence:
            self._save_disk_entry(entry)

    def _save_disk_entry(self, entry: CacheEntry):
        """Save entry to disk cache"""
        try:
            file_path = self._get_disk_cache_path(entry.key)

            with open(file_path, 'wb') as f:
                pickle.dump(entry.value, f)

            self._disk_cache_index[entry.key] = entry
            self._stats.disk_entries += 1

        except Exception as e:
            self.logger.error(f"Error saving disk entry {entry.key}: {e}")

    def _remove_disk_entry(self, key: str):
        """Remove entry from disk cache"""
        try:
            file_path = self._get_disk_cache_path(key)

            if os.path.exists(file_path):
                os.remove(file_path)

            if key in self._disk_cache_index:
                del self._disk_cache_index[key]
                self._stats.disk_entries -= 1

        except Exception as e:
            self.logger.error(f"Error removing disk entry {key}: {e}")

    def _get_disk_cache_path(self, key: str) -> str:
        """Get file path for disk cache entry"""
        import os
        # Create safe filename from key
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.cache_config.disk_cache_dir, f"{key_hash}.cache")

    def _is_entry_valid(self, entry: CacheEntry, now: Optional[datetime] = None) -> bool:
        """Check if cache entry is still valid"""
        now = now or datetime.now()
        return not self._is_entry_expired(entry, now)

    def _is_entry_expired(self, entry: CacheEntry, now: datetime) -> bool:
        """Check if cache entry is expired"""
        if entry.ttl_seconds is None:
            return False

        expiry_time = entry.created_at + timedelta(seconds=entry.ttl_seconds)
        return now > expiry_time

    def _calculate_size(self, value: Any) -> int:
        """Calculate size of value in bytes"""
        try:
            return len(pickle.dumps(value))
        except Exception:
            return 0

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache

        Args:
            key: Cache key
            default: Default value if not found

        Returns:
            Cached value or default
        """
        now = datetime.now()

        # Check memory cache first
        with self._cache_lock:
            if key in self._memory_cache:
                entry = self._memory_cache[key]

                if self._is_entry_valid(entry, now):
                    # Update access info
                    entry.accessed_at = now
                    entry.access_count += 1
                    entry.hits += 1

                    # Move to end (LRU)
                    self._memory_cache.move_to_end(key)

                    # Update stats
                    with self._stats_lock:
                        self._stats.total_hits += 1

                    return entry.value
                else:
                    # Entry expired
                    del self._memory_cache[key]
                    self._stats.total_entries -= 1
                    self._stats.memory_entries -= 1

        # Check disk cache
        if key in self._disk_cache_index:
            entry = self._disk_cache_index[key]

            if self._is_entry_valid(entry, now):
                # Load into memory
                try:
                    file_path = self._get_disk_cache_path(key)
                    with open(file_path, 'rb') as f:
                        entry.value = pickle.load(f)

                    entry.accessed_at = now
                    entry.access_count += 1
                    entry.hits += 1

                    # Add to memory cache
                    with self._cache_lock:
                        self._memory_cache[key] = entry
                        self._stats.total_entries += 1
                        self._stats.memory_entries += 1

                    with self._stats_lock:
                        self._stats.total_hits += 1

                    return entry.value

                except Exception as e:
                    self.logger.error(f"Error loading disk entry {key}: {e}")
                    self._remove_disk_entry(key)
            else:
                # Entry expired
                self._remove_disk_entry(key)

        # Not found
        with self._stats_lock:
            self._stats.total_misses += 1

        return default

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time to live in seconds

        Returns:
            True if successful
        """
        try:
            now = datetime.now()

            entry = CacheEntry(
                key=key,
                value=value,
                created_at=now,
                accessed_at=now,
                access_count=0,
                ttl_seconds=ttl_seconds or self.cache_config.default_ttl_seconds,
                size_bytes=self._calculate_size(value)
            )

            with self._cache_lock:
                # Remove existing entry if present
                if key in self._memory_cache:
                    self._stats.total_entries -= 1
                    self._stats.memory_entries -= 1

                self._memory_cache[key] = entry
                self._stats.total_entries += 1
                self._stats.memory_entries += 1

            # Evict if needed
            self._evict_if_needed()

            # Persist if enabled
            if self.cache_config.enable_persistence:
                self._persist_entry(entry)

            return True

        except Exception as e:
            self.logger.error(f"Error setting cache entry {key}: {e}")
            return False

    def _persist_entry(self, entry: CacheEntry):
        """Persist entry to database"""
        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO cache_entries (
                        key, value, created_at, accessed_at, access_count,
                        ttl_seconds, size_bytes, hits, misses
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.key,
                    pickle.dumps(entry.value),
                    entry.created_at.isoformat(),
                    entry.accessed_at.isoformat(),
                    entry.access_count,
                    entry.ttl_seconds,
                    entry.size_bytes,
                    entry.hits,
                    entry.misses
                ))
                conn.commit()

        except Exception as e:
            self.logger.error(f"Error persisting cache entry {entry.key}: {e}")

    def delete(self, key: str) -> bool:
        """
        Delete entry from cache

        Args:
            key: Cache key

        Returns:
            True if entry was deleted
        """
        deleted = False

        with self._cache_lock:
            if key in self._memory_cache:
                del self._memory_cache[key]
                self._stats.total_entries -= 1
                self._stats.memory_entries -= 1
                deleted = True

        if key in self._disk_cache_index:
            self._remove_disk_entry(key)
            deleted = True

        # Remove from persistent storage
        if deleted:
            try:
                with self.db.get_connection() as conn:
                    conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                    conn.commit()
            except Exception as e:
                self.logger.error(f"Error deleting persistent cache entry {key}: {e}")

        return deleted

    def clear(self):
        """Clear all cache entries"""
        with self._cache_lock:
            self._memory_cache.clear()
            self._stats.total_entries = 0
            self._stats.memory_entries = 0

        # Clear disk cache
        import os
        import glob

        cache_files = glob.glob(os.path.join(self.cache_config.disk_cache_dir, "*.cache"))
        for file_path in cache_files:
            try:
                os.remove(file_path)
            except Exception as e:
                self.logger.error(f"Error removing cache file {file_path}: {e}")

        self._disk_cache_index.clear()
        self._stats.disk_entries = 0

        # Clear persistent storage
        try:
            with self.db.get_connection() as conn:
                conn.execute("DELETE FROM cache_entries")
                conn.commit()
        except Exception as e:
            self.logger.error(f"Error clearing persistent cache: {e}")

        self.logger.info("Cache cleared")

    def get_stats(self) -> CacheStats:
        """Get cache statistics"""
        with self._stats_lock:
            stats = CacheStats(
                total_entries=self._stats.total_entries,
                memory_entries=self._stats.memory_entries,
                disk_entries=self._stats.disk_entries,
                total_hits=self._stats.total_hits,
                total_misses=self._stats.total_misses,
                memory_usage_mb=sum(
                    self._calculate_size(entry.value)
                    for entry in self._memory_cache.values()
                ) / (1024 * 1024),
                disk_usage_mb=sum(
                    os.path.getsize(self._get_disk_cache_path(key)) / (1024 * 1024)
                    for key in self._disk_cache_index.keys()
                    if os.path.exists(self._get_disk_cache_path(key))
                ),
                hit_rate=(
                    self._stats.total_hits /
                    (self._stats.total_hits + self._stats.total_misses)
                    if (self._stats.total_hits + self._stats.total_misses) > 0
                    else 0
                ),
                eviction_count=self._stats.eviction_count
            )

        return stats

    def get_keys(self) -> List[str]:
        """Get all cache keys"""
        keys = []

        with self._cache_lock:
            keys.extend(self._memory_cache.keys())

        keys.extend(self._disk_cache_index.keys())

        return list(set(keys))

    def stop(self):
        """Stop cache manager"""
        self._running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)

        # Save any unsaved entries
        if self.cache_config.enable_persistence:
            with self._cache_lock:
                for entry in self._memory_cache.values():
                    self._persist_entry(entry)

        self.logger.info("Cache manager stopped")

    def __contains__(self, key: str) -> bool:
        """Check if key exists in cache"""
        return self.get(key, None) is not None

    def __len__(self) -> int:
        """Get number of cache entries"""
        return self._stats.total_entries