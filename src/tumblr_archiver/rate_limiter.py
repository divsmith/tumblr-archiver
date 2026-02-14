"""Rate limiting and concurrency control for API requests.

This module implements token bucket rate limiting and semaphore-based
concurrency control to ensure API usage stays within limits.
"""

import asyncio
import time
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for async operations.
    
    The token bucket algorithm allows for burst traffic while maintaining
    a sustained rate limit over time. Tokens are added to the bucket at
    a constant rate, and requests consume tokens.
    
    Attributes:
        rate_per_second: Sustained rate limit (tokens per second)
        burst: Maximum bucket capacity (max burst size)
    """
    
    def __init__(self, rate_per_second: float, burst: Optional[int] = None):
        """Initialize rate limiter with token bucket algorithm.
        
        Args:
            rate_per_second: Sustained rate limit (e.g., 1.0 for 1 req/sec)
            burst: Maximum burst size (default: rate * 2)
        """
        if rate_per_second <= 0:
            raise ValueError("rate_per_second must be positive")
        
        self.rate_per_second = rate_per_second
        self.burst = burst if burst is not None else int(rate_per_second * 2)
        
        if self.burst < 1:
            self.burst = 1
        
        # Token bucket state
        self._tokens: float = float(self.burst)
        self._last_update: float = time.monotonic()
        self._lock = asyncio.Lock()
        
        logger.debug(
            f"RateLimiter initialized: {rate_per_second} req/s, "
            f"burst={self.burst}"
        )
    
    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time since last update."""
        now = time.monotonic()
        elapsed = now - self._last_update
        
        # Add tokens based on elapsed time
        new_tokens = elapsed * self.rate_per_second
        self._tokens = min(self._tokens + new_tokens, float(self.burst))
        self._last_update = now
    
    async def acquire(self) -> None:
        """Acquire a single token, waiting if necessary.
        
        This method blocks until a token is available, then consumes it.
        """
        await self.acquire_multiple(1)
    
    async def acquire_multiple(self, n: int) -> None:
        """Acquire n tokens, waiting if necessary.
        
        Args:
            n: Number of tokens to acquire (for batch operations)
            
        Raises:
            ValueError: If n is less than 1 or greater than burst size
        """
        if n < 1:
            raise ValueError("Must acquire at least 1 token")
        if n > self.burst:
            raise ValueError(
                f"Cannot acquire {n} tokens (burst limit is {self.burst})"
            )
        
        async with self._lock:
            while True:
                self._refill_tokens()
                
                if self._tokens >= n:
                    self._tokens -= n
                    logger.debug(
                        f"Acquired {n} token(s), {self._tokens:.2f} remaining"
                    )
                    return
                
                # Calculate wait time until we have enough tokens
                tokens_needed = n - self._tokens
                wait_time = tokens_needed / self.rate_per_second
                
                logger.debug(
                    f"Not enough tokens ({self._tokens:.2f}/{n}), "
                    f"waiting {wait_time:.2f}s"
                )
                
                # Release lock while waiting
                await asyncio.sleep(wait_time)
    
    def get_available_tokens(self) -> float:
        """Get current number of available tokens (non-blocking).
        
        Returns:
            Current token count in the bucket
        """
        # Update tokens without acquiring lock (approximate)
        now = time.monotonic()
        elapsed = now - self._last_update
        new_tokens = elapsed * self.rate_per_second
        current_tokens = min(self._tokens + new_tokens, float(self.burst))
        return current_tokens


class ConcurrencyLimiter:
    """Semaphore-based concurrency limiter for async operations.
    
    Limits the number of concurrent operations to prevent overwhelming
    the API or local resources.
    """
    
    def __init__(self, max_concurrent: int):
        """Initialize concurrency limiter.
        
        Args:
            max_concurrent: Maximum number of concurrent operations
            
        Raises:
            ValueError: If max_concurrent is less than 1
        """
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be at least 1")
        
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_count = 0
        self._lock = asyncio.Lock()
        
        logger.debug(f"ConcurrencyLimiter initialized: {max_concurrent} max")
    
    async def __aenter__(self):
        """Acquire semaphore slot (async context manager entry)."""
        await self._semaphore.acquire()
        async with self._lock:
            self._active_count += 1
            logger.debug(
                f"Acquired concurrency slot ({self._active_count}/"
                f"{self.max_concurrent})"
            )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Release semaphore slot (async context manager exit)."""
        self._semaphore.release()
        async with self._lock:
            self._active_count -= 1
            logger.debug(
                f"Released concurrency slot ({self._active_count}/"
                f"{self.max_concurrent})"
            )
        return False
    
    def get_active_count(self) -> int:
        """Get current number of active operations.
        
        Returns:
            Number of currently active operations
        """
        return self._active_count


class RequestThrottler:
    """Combined rate and concurrency limiter for API requests.
    
    This class combines token bucket rate limiting with semaphore-based
    concurrency control, providing comprehensive request throttling.
    
    Usage:
        throttler = RequestThrottler(rate_per_second=1.0, max_concurrent=5)
        async with throttler:
            response = await make_request()
    """
    
    def __init__(
        self,
        rate_per_second: float,
        max_concurrent: int,
        burst: Optional[int] = None
    ):
        """Initialize combined request throttler.
        
        Args:
            rate_per_second: Sustained rate limit (tokens per second)
            max_concurrent: Maximum concurrent requests
            burst: Maximum burst size (default: rate * 2)
        """
        self.rate_limiter = RateLimiter(rate_per_second, burst)
        self.concurrency_limiter = ConcurrencyLimiter(max_concurrent)
        
        logger.info(
            f"RequestThrottler initialized: {rate_per_second} req/s, "
            f"max {max_concurrent} concurrent, burst={self.rate_limiter.burst}"
        )
    
    async def __aenter__(self):
        """Acquire both rate and concurrency limits."""
        # First acquire rate limit token
        await self.rate_limiter.acquire()
        # Then acquire concurrency slot
        await self.concurrency_limiter.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Release concurrency slot (rate limit token already consumed)."""
        return await self.concurrency_limiter.__aexit__(
            exc_type, exc_val, exc_tb
        )
    
    def get_status(self) -> dict:
        """Get current throttler status.
        
        Returns:
            Dictionary with current tokens and active requests
        """
        return {
            "available_tokens": self.rate_limiter.get_available_tokens(),
            "max_burst": self.rate_limiter.burst,
            "rate_per_second": self.rate_limiter.rate_per_second,
            "active_requests": self.concurrency_limiter.get_active_count(),
            "max_concurrent": self.concurrency_limiter.max_concurrent,
        }
