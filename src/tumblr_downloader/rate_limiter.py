"""Rate limiter for API requests and downloads.

This module implements a token bucket rate limiter to ensure respectful
usage of external services and avoid overwhelming servers.
"""

import asyncio
import threading
import time
from typing import Optional


class RateLimiter:
    """Thread-safe token bucket rate limiter.
    
    Implements a token bucket algorithm to limit the rate of operations.
    The bucket fills with tokens at a constant rate, and each operation
    consumes one token. If no tokens are available, the operation waits.
    
    Attributes:
        max_per_second: Maximum number of operations allowed per second.
        tokens: Current number of available tokens.
        max_tokens: Maximum capacity of the token bucket.
        last_update: Timestamp of the last token refill.
    """
    
    def __init__(self, max_per_second: float):
        """Initialize the rate limiter.
        
        Args:
            max_per_second: Maximum number of operations allowed per second.
                           For example, 2.0 means 2 operations per second.
        
        Raises:
            ValueError: If max_per_second is not positive.
        """
        if max_per_second <= 0:
            raise ValueError("max_per_second must be positive")
        
        self.max_per_second = max_per_second
        self.max_tokens = max_per_second
        self.tokens = max_per_second
        self.last_update = time.monotonic()
        self._lock = threading.Lock()
        self._async_lock: Optional[asyncio.Lock] = None
    
    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time.
        
        This method is called internally and assumes the lock is already held.
        """
        now = time.monotonic()
        elapsed = now - self.last_update
        
        # Add tokens based on elapsed time
        new_tokens = elapsed * self.max_per_second
        self.tokens = min(self.max_tokens, self.tokens + new_tokens)
        self.last_update = now
    
    def wait(self) -> None:
        """Wait until a token is available (synchronous).
        
        This method blocks until a token becomes available, then consumes it.
        Safe to call from multiple threads.
        """
        with self._lock:
            while True:
                self._refill_tokens()
                
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                
                # Calculate wait time for next token
                tokens_needed = 1.0 - self.tokens
                wait_time = tokens_needed / self.max_per_second
                
                # Release lock while sleeping to allow other threads
                self._lock.release()
                try:
                    time.sleep(wait_time)
                finally:
                    self._lock.acquire()
    
    async def acquire(self) -> None:
        """Wait until a token is available (asynchronous).
        
        This method waits asynchronously until a token becomes available,
        then consumes it. Safe to call from multiple coroutines.
        """
        # Initialize async lock on first use
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        
        async with self._async_lock:
            while True:
                # Use synchronous lock for token state
                with self._lock:
                    self._refill_tokens()
                    
                    if self.tokens >= 1.0:
                        self.tokens -= 1.0
                        return
                    
                    # Calculate wait time for next token
                    tokens_needed = 1.0 - self.tokens
                    wait_time = tokens_needed / self.max_per_second
                
                # Sleep asynchronously without holding lock
                await asyncio.sleep(wait_time)
    
    def try_acquire(self) -> bool:
        """Try to acquire a token without waiting.
        
        Returns:
            True if a token was acquired, False otherwise.
        """
        with self._lock:
            self._refill_tokens()
            
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False
    
    def reset(self) -> None:
        """Reset the rate limiter to full capacity.
        
        This method immediately refills the token bucket to maximum capacity.
        Useful for testing or manual intervention.
        """
        with self._lock:
            self.tokens = self.max_tokens
            self.last_update = time.monotonic()
    
    def get_available_tokens(self) -> float:
        """Get the current number of available tokens.
        
        Returns:
            The current number of tokens in the bucket.
        """
        with self._lock:
            self._refill_tokens()
            return self.tokens
    
    def __repr__(self) -> str:
        """Return a string representation of the rate limiter."""
        return (f"RateLimiter(max_per_second={self.max_per_second}, "
                f"tokens={self.tokens:.2f})")
