"""Rate limiting implementation using token bucket algorithm."""

import logging
from typing import Optional

from aiolimiter import AsyncLimiter

from .constants import DEFAULT_RATE_LIMIT

logger = logging.getLogger(__name__)


class TokenBucketRateLimiter:
    """Rate limiter using token bucket algorithm via aiolimiter.
    
    The token bucket algorithm allows for burst traffic while maintaining
    an average rate limit. Tokens are added to the bucket at a fixed rate,
    and each request consumes a token.
    
    Attributes:
        rate_limit: Maximum requests per second
        max_burst: Maximum burst size (tokens that can accumulate)
    
    Example:
        ```python
        limiter = TokenBucketRateLimiter(rate_limit=2.0)
        
        async with limiter:
            # Make request
            response = await client.get(url)
        ```
    """
    
    def __init__(
        self,
        rate_limit: float = DEFAULT_RATE_LIMIT,
        max_burst: Optional[int] = None,
    ):
        """Initialize the rate limiter.
        
        Args:
            rate_limit: Maximum requests per second (e.g., 2.0 = 2 req/s)
            max_burst: Maximum burst size. Defaults to rate_limit if None.
                      This allows accumulating tokens when idle.
        """
        if rate_limit <= 0:
            raise ValueError("rate_limit must be positive")
        
        self.rate_limit = rate_limit
        self.max_burst = max_burst or int(rate_limit) or 1
        
        # aiolimiter uses max_rate (tokens) and time_period (seconds)
        # For rate_limit req/s, we use max_rate=max_burst and time_period=max_burst/rate_limit
        time_period = self.max_burst / rate_limit
        
        self._limiter = AsyncLimiter(
            max_rate=self.max_burst,
            time_period=time_period,
        )
        
        logger.debug(
            f"Initialized rate limiter: {rate_limit} req/s, "
            f"max_burst={self.max_burst}, time_period={time_period:.2f}s"
        )
    
    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens from the rate limiter.
        
        This will block until enough tokens are available.
        
        Args:
            tokens: Number of tokens to acquire (default: 1)
        """
        await self._limiter.acquire(tokens)
        logger.debug(f"Acquired {tokens} token(s) from rate limiter")
    
    async def __aenter__(self):
        """Context manager entry - acquire a token."""
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - no cleanup needed."""
        return False
    
    def has_capacity(self) -> bool:
        """Check if the rate limiter has capacity for immediate request.
        
        Note: This is a best-effort check and not guaranteed due to
        concurrent access. Use acquire() for proper rate limiting.
        
        Returns:
            True if capacity is available (not guaranteed)
        """
        return self._limiter.has_capacity()
    
    @property
    def max_rate(self) -> float:
        """Get the maximum rate in requests per second."""
        return self.rate_limit
    
    def __repr__(self) -> str:
        """String representation of the rate limiter."""
        return (
            f"TokenBucketRateLimiter(rate_limit={self.rate_limit}, "
            f"max_burst={self.max_burst})"
        )
