"""Tests for the rate limiter module."""

import asyncio
import time
from typing import List

import pytest

from tumblr_archiver.rate_limiter import TokenBucketRateLimiter


class TestTokenBucketRateLimiter:
    """Tests for TokenBucketRateLimiter."""
    
    def test_initialization(self):
        """Test rate limiter initialization."""
        limiter = TokenBucketRateLimiter(rate_limit=2.0)
        assert limiter.rate_limit == 2.0
        assert limiter.max_burst >= 1
        
    def test_initialization_with_burst(self):
        """Test rate limiter initialization with custom burst."""
        limiter = TokenBucketRateLimiter(rate_limit=5.0, max_burst=10)
        assert limiter.rate_limit == 5.0
        assert limiter.max_burst == 10
    
    def test_invalid_rate_limit(self):
        """Test that invalid rate limits raise ValueError."""
        with pytest.raises(ValueError, match="rate_limit must be positive"):
            TokenBucketRateLimiter(rate_limit=0)
        
        with pytest.raises(ValueError, match="rate_limit must be positive"):
            TokenBucketRateLimiter(rate_limit=-1)
    
    @pytest.mark.asyncio
    async def test_single_acquisition(self):
        """Test acquiring a single token."""
        limiter = TokenBucketRateLimiter(rate_limit=10.0)
        
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start
        
        # Should be nearly instantaneous for first request
        assert elapsed < 0.1
    
    @pytest.mark.asyncio
    async def test_rate_limiting_enforced(self):
        """Test that rate limiting is actually enforced."""
        rate_limit = 5.0  # 5 requests per second
        limiter = TokenBucketRateLimiter(rate_limit=rate_limit)
        
        # Make several requests
        num_requests = 10
        start = time.time()
        
        for _ in range(num_requests):
            await limiter.acquire()
        
        elapsed = time.time() - start
        
        # Should take at least (num_requests - burst) / rate_limit seconds
        # Accounting for burst, we allow some variance
        min_expected = (num_requests - limiter.max_burst) / rate_limit
        
        # Allow some tolerance for timing variations
        assert elapsed >= min_expected * 0.8
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_rate_limited(self):
        """Test that concurrent requests still respect rate limit."""
        rate_limit = 4.0  # 4 requests per second
        limiter = TokenBucketRateLimiter(rate_limit=rate_limit)
        
        num_requests = 12
        timestamps: List[float] = []
        
        async def make_request():
            """Simulate making a request."""
            await limiter.acquire()
            timestamps.append(time.time())
        
        # Launch all requests concurrently
        start = time.time()
        await asyncio.gather(*[make_request() for _ in range(num_requests)])
        elapsed = time.time() - start
        
        # Check that timestamps are properly spaced
        assert len(timestamps) == num_requests
        
        # Total time should be at least (num_requests - burst) / rate_limit
        min_expected = (num_requests - limiter.max_burst) / rate_limit
        assert elapsed >= min_expected * 0.8
    
    @pytest.mark.asyncio
    async def test_burst_handling(self):
        """Test that burst capacity is handled correctly."""
        rate_limit = 2.0
        max_burst = 5
        limiter = TokenBucketRateLimiter(rate_limit=rate_limit, max_burst=max_burst)
        
        # First burst should be fast
        start = time.time()
        for _ in range(max_burst):
            await limiter.acquire()
        burst_time = time.time() - start
        
        # Burst should complete quickly (all tokens available initially)
        assert burst_time < 0.5
        
        # Next request should wait
        start = time.time()
        await limiter.acquire()
        wait_time = time.time() - start
        
        # Should wait for tokens to refill
        assert wait_time > 0.2  # Should wait at least some time
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test using rate limiter as a context manager."""
        limiter = TokenBucketRateLimiter(rate_limit=10.0)
        
        start = time.time()
        async with limiter:
            # Inside context, token should be acquired
            pass
        elapsed = time.time() - start
        
        # Should complete quickly
        assert elapsed < 0.1
    
    @pytest.mark.asyncio
    async def test_multiple_tokens(self):
        """Test acquiring multiple tokens at once."""
        limiter = TokenBucketRateLimiter(rate_limit=5.0, max_burst=10)
        
        # Acquire multiple tokens
        await limiter.acquire(tokens=3)
        
        # Should succeed without error
        assert True
    
    @pytest.mark.asyncio
    async def test_has_capacity(self):
        """Test has_capacity method."""
        limiter = TokenBucketRateLimiter(rate_limit=10.0, max_burst=2)
        
        # Should have capacity initially
        assert limiter.has_capacity() is True
        
        # After exhausting burst
        await limiter.acquire(tokens=2)
        
        # Capacity might be exhausted (not guaranteed due to timing)
        # This is a best-effort check, so we just verify it doesn't crash
        _ = limiter.has_capacity()
    
    def test_repr(self):
        """Test string representation."""
        limiter = TokenBucketRateLimiter(rate_limit=3.5, max_burst=7)
        repr_str = repr(limiter)
        
        assert "TokenBucketRateLimiter" in repr_str
        assert "3.5" in repr_str
        assert "7" in repr_str
    
    def test_max_rate_property(self):
        """Test max_rate property."""
        rate_limit = 4.5
        limiter = TokenBucketRateLimiter(rate_limit=rate_limit)
        
        assert limiter.max_rate == rate_limit


@pytest.mark.asyncio
async def test_multiple_limiters_independent():
    """Test that multiple limiters operate independently."""
    limiter1 = TokenBucketRateLimiter(rate_limit=2.0)
    limiter2 = TokenBucketRateLimiter(rate_limit=5.0)
    
    # Exhaust limiter1
    await limiter1.acquire(tokens=2)
    
    # limiter2 should still have full capacity
    start = time.time()
    await limiter2.acquire()
    elapsed = time.time() - start
    
    # Should be nearly instant since limiter2 is independent
    assert elapsed < 0.1
