"""
Tests for the rate limiter module.
"""

import asyncio
import time
import pytest

from tumblr_archiver.rate_limiter import RateLimiter


class TestRateLimiter:
    """Tests for RateLimiter class."""
    
    def test_initialization(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(rate_per_second=10.0)
        
        assert limiter.rate_per_second == 10.0
        assert limiter.burst == 20  # Default is rate * 2
    
    def test_initialization_with_burst(self):
        """Test initialization with custom burst size."""
        limiter = RateLimiter(rate_per_second=5.0, burst=10)
        
        assert limiter.rate_per_second == 5.0
        assert limiter.burst == 10
    
    def test_initialization_invalid_rate(self):
        """Test initialization with invalid rate."""
        with pytest.raises(ValueError):
            RateLimiter(rate_per_second=0)
        
        with pytest.raises(ValueError):
            RateLimiter(rate_per_second=-1)
    
    @pytest.mark.asyncio
    async def test_acquire_single_token(self):
        """Test acquiring a single token."""
        limiter = RateLimiter(rate_per_second=100.0)  # High rate for fast test
        
        initial_tokens = limiter._tokens
        await limiter.acquire()
        
        # Should have consumed 1 token
        assert limiter._tokens < initial_tokens
    
    @pytest.mark.asyncio
    async def test_acquire_multiple_tokens(self):
        """Test acquiring multiple tokens at once."""
        limiter = RateLimiter(rate_per_second=100.0, burst=10)
        
        await limiter.acquire_multiple(5)
        
        # Should have consumed 5 tokens
        assert limiter._tokens <= 5.0
    
    @pytest.mark.asyncio
    async def test_acquire_multiple_invalid(self):
        """Test acquiring invalid number of tokens."""
        limiter = RateLimiter(rate_per_second=10.0, burst=10)
        
        with pytest.raises(ValueError):
            await limiter.acquire_multiple(0)
        
        with pytest.raises(ValueError):
            await limiter.acquire_multiple(-1)
        
        with pytest.raises(ValueError):
            await limiter.acquire_multiple(15)  # More than burst
    
    @pytest.mark.asyncio
    async def test_rate_limiting_delay(self):
        """Test that rate limiting causes delays."""
        limiter = RateLimiter(rate_per_second=5.0, burst=2)
        
        # Consume all tokens
        await limiter.acquire_multiple(2)
        
        # Next acquire should wait
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        
        # Should have waited at least ~0.2 seconds (1/5)
        assert elapsed >= 0.15, f"Expected delay >= 0.15s, got {elapsed}"
    
    @pytest.mark.asyncio
    async def test_token_refill(self):
        """Test that tokens refill over time."""
        limiter = RateLimiter(rate_per_second=10.0, burst=10)
        
        # Consume some tokens
        await limiter.acquire_multiple(5)
        assert limiter._tokens == 5.0
        
        # Wait for tokens to refill
        await asyncio.sleep(0.5)  # Should refill 5 tokens (10 * 0.5)
        
        # Manually trigger refill
        limiter._refill_tokens()
        
        # Tokens should be close to burst limit
        assert limiter._tokens >= 9.0
    
    @pytest.mark.asyncio
    async def test_burst_capacity(self):
        """Test burst capacity limits."""
        limiter = RateLimiter(rate_per_second=10.0, burst=5)
        
        # Even with long wait, tokens shouldn't exceed burst
        await asyncio.sleep(2.0)  # Would refill 20 tokens without limit
        limiter._refill_tokens()
        
        assert limiter._tokens <= float(limiter.burst)
    
    @pytest.mark.asyncio
    async def test_concurrent_acquires(self):
        """Test that concurrent acquires are properly serialized."""
        limiter = RateLimiter(rate_per_second=100.0, burst=10)
        
        # Launch multiple concurrent acquires
        tasks = [limiter.acquire() for _ in range(5)]
        await asyncio.gather(*tasks)
        
        # All should complete successfully
        assert limiter._tokens <= 5.0
    
    @pytest.mark.asyncio
    async def test_precise_rate_limiting(self):
        """Test that rate limiting is reasonably precise."""
        rate = 10.0  # 10 requests per second
        limiter = RateLimiter(rate_per_second=rate, burst=1)
        
        # Make several requests
        start = time.monotonic()
        for _ in range(5):
            await limiter.acquire()
        elapsed = time.monotonic() - start
        
        # Should take approximately 0.4 seconds (4 waits * 0.1s)
        # Allow some tolerance for execution time
        expected_min = 0.3
        expected_max = 0.6
        assert expected_min <= elapsed <= expected_max, \
            f"Expected {expected_min}-{expected_max}s, got {elapsed}s"
    
    @pytest.mark.asyncio
    async def test_no_wait_when_tokens_available(self):
        """Test that no waiting occurs when tokens are available."""
        limiter = RateLimiter(rate_per_second=10.0, burst=10)
        
        # Should not wait with full bucket
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        
        # Should be nearly instantaneous
        assert elapsed < 0.1
    
    @pytest.mark.asyncio
    async def test_refill_rate(self):
        """Test token refill rate is accurate."""
        limiter = RateLimiter(rate_per_second=10.0, burst=10)
        
        # Empty the bucket
        limiter._tokens = 0.0
        limiter._last_update = time.monotonic()
        
        # Wait 0.5 seconds
        await asyncio.sleep(0.5)
        
        # Refill
        limiter._refill_tokens()
        
        # Should have ~5 tokens (10 * 0.5)
        assert 4.5 <= limiter._tokens <= 5.5
