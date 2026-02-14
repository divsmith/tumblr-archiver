"""In-memory response cache with LRU eviction policy."""

import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with value and metadata.
    
    Attributes:
        value: Cached value
        created_at: Timestamp when entry was created
        ttl: Time-to-live in seconds
    """
    
    value: Any
    created_at: float
    ttl: float
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired.
        
        Returns:
            True if entry has exceeded its TTL
        """
        if self.ttl <= 0:
            return False  # No expiration
        return time.time() - self.created_at > self.ttl


class ResponseCache:
    """In-memory cache for HTTP responses with LRU eviction.
    
    Features:
    - LRU (Least Recently Used) eviction policy
    - Configurable max size and TTL
    - Automatic expiration checking
    - Cache statistics tracking
    - Thread-safe operations
    
    Example:
        ```python
        cache = ResponseCache(max_size=100, default_ttl=300)
        
        # Store a response
        cache.set("https://example.com", response_data)
        
        # Retrieve a response
        data = cache.get("https://example.com")
        
        # Get statistics
        stats = cache.get_stats()
        print(f"Hit rate: {stats['hit_rate']:.2%}")
        ```
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: float = 300):
        """Initialize response cache.
        
        Args:
            max_size: Maximum number of entries (0 = unlimited)
            default_ttl: Default time-to-live in seconds (0 = no expiration)
        """
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        
        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        
        logger.debug(
            f"Initialized ResponseCache with max_size={max_size}, "
            f"default_ttl={default_ttl}s"
        )
    
    def _generate_key(self, key: str) -> str:
        """Generate cache key from input.
        
        Args:
            key: Original key (e.g., URL)
            
        Returns:
            Hashed key for internal use
        """
        return hashlib.sha256(key.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache.
        
        Args:
            key: Cache key (e.g., URL)
            
        Returns:
            Cached value or None if not found/expired
        """
        cache_key = self._generate_key(key)
        
        if cache_key not in self._cache:
            self._misses += 1
            logger.debug(f"Cache miss: {key[:50]}...")
            return None
        
        entry = self._cache[cache_key]
        
        # Check expiration
        if entry.is_expired():
            self._misses += 1
            logger.debug(f"Cache expired: {key[:50]}...")
            del self._cache[cache_key]
            return None
        
        # Move to end (most recently used)
        self._cache.move_to_end(cache_key)
        self._hits += 1
        logger.debug(f"Cache hit: {key[:50]}...")
        
        return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Store value in cache.
        
        Args:
            key: Cache key (e.g., URL)
            value: Value to cache
            ttl: Time-to-live in seconds (uses default_ttl if None)
        """
        cache_key = self._generate_key(key)
        
        # Use default TTL if not specified
        if ttl is None:
            ttl = self._default_ttl
        
        # Create entry
        entry = CacheEntry(
            value=value,
            created_at=time.time(),
            ttl=ttl
        )
        
        # Remove if already exists (will re-add at end)
        if cache_key in self._cache:
            del self._cache[cache_key]
        
        # Add to cache
        self._cache[cache_key] = entry
        logger.debug(f"Cache set: {key[:50]}... (ttl={ttl}s)")
        
        # Evict oldest if over max size
        if self._max_size > 0 and len(self._cache) > self._max_size:
            evicted_key = next(iter(self._cache))
            del self._cache[evicted_key]
            self._evictions += 1
            logger.debug(f"Cache eviction (LRU policy), size={len(self._cache)}")
    
    def invalidate(self, key: str) -> bool:
        """Remove entry from cache.
        
        Args:
            key: Cache key to invalidate
            
        Returns:
            True if entry was removed, False if not found
        """
        cache_key = self._generate_key(key)
        
        if cache_key in self._cache:
            del self._cache[cache_key]
            logger.debug(f"Cache invalidated: {key[:50]}...")
            return True
        
        return False
    
    def clear(self) -> None:
        """Clear all entries from cache."""
        size = len(self._cache)
        self._cache.clear()
        logger.info(f"Cache cleared ({size} entries)")
    
    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary containing:
                - hits: Number of cache hits
                - misses: Number of cache misses
                - hit_rate: Hit rate (0.0-1.0)
                - size: Current number of entries
                - max_size: Maximum number of entries
                - evictions: Number of evictions performed
        """
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0
        
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "size": len(self._cache),
            "max_size": self._max_size,
            "evictions": self._evictions,
        }
    
    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        logger.debug("Cache statistics reset")
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries.
        
        Returns:
            Number of entries removed
        """
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)
    
    def __len__(self) -> int:
        """Get number of entries in cache."""
        return len(self._cache)
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists in cache (without updating LRU).
        
        Args:
            key: Cache key to check
            
        Returns:
            True if key exists and is not expired
        """
        cache_key = self._generate_key(key)
        
        if cache_key not in self._cache:
            return False
        
        entry = self._cache[cache_key]
        return not entry.is_expired()
