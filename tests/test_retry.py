"""
Tests for the retry strategy module.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock

from tumblr_archiver.retry import (
    RetryStrategy,
    RetryableError,
    NonRetryableError,
    RetryStats,
)


class TestRetryStats:
    """Tests for RetryStats dataclass."""
    
    def test_retry_stats_creation(self):
        """Test creating RetryStats."""
        stats = RetryStats(
            total_attempts=3,
            total_delay=5.5,
            last_error=Exception("Test error")
        )
        
        assert stats.total_attempts == 3
        assert stats.total_delay == 5.5
        assert stats.last_error is not None
    
    def test_retry_stats_defaults(self):
        """Test RetryStats default values."""
        stats = RetryStats()
        
        assert stats.total_attempts == 0
        assert stats.total_delay == 0.0
        assert stats.last_error is None


class TestRetryStrategy:
    """Tests for RetryStrategy class."""
    
    def test_initialization(self):
        """Test retry strategy initialization."""
        strategy = RetryStrategy(
            max_retries=3,
            base_backoff=1.0,
            max_backoff=32.0,
            jitter=True
        )
        
        assert strategy.max_retries == 3
        assert strategy.base_backoff == 1.0
        assert strategy.max_backoff == 32.0
        assert strategy.jitter is True
    
    def test_initialization_defaults(self):
        """Test default initialization values."""
        strategy = RetryStrategy()
        
        assert strategy.max_retries == 3
        assert strategy.base_backoff == 1.0
        assert strategy.max_backoff == 32.0
        assert strategy.jitter is True
    
    def test_initialization_invalid_params(self):
        """Test initialization with invalid parameters."""
        with pytest.raises(ValueError):
            RetryStrategy(max_retries=-1)
        
        with pytest.raises(ValueError):
            RetryStrategy(base_backoff=0)
        
        with pytest.raises(ValueError):
            RetryStrategy(base_backoff=10.0, max_backoff=5.0)
    
    def test_calculate_backoff_exponential(self):
        """Test exponential backoff calculation."""
        strategy = RetryStrategy(base_backoff=1.0, max_backoff=32.0, jitter=False)
        
        # First retry: 1.0 * 2^0 = 1.0
        delay1 = strategy.calculate_backoff(0)
        assert delay1 == 1.0
        
        # Second retry: 1.0 * 2^1 = 2.0
        delay2 = strategy.calculate_backoff(1)
        assert delay2 == 2.0
        
        # Third retry: 1.0 * 2^2 = 4.0
        delay3 = strategy.calculate_backoff(2)
        assert delay3 == 4.0
    
    def test_calculate_backoff_max_cap(self):
        """Test that backoff is capped at max_backoff."""
        strategy = RetryStrategy(base_backoff=1.0, max_backoff=8.0, jitter=False)
        
        # 10th retry would be 1024s without cap
        delay = strategy.calculate_backoff(10)
        assert delay == 8.0  # Capped at max_backoff
    
    def test_calculate_backoff_with_jitter(self):
        """Test backoff with jitter."""
        strategy = RetryStrategy(base_backoff=1.0, max_backoff=32.0, jitter=True)
        
        # With jitter, delay should vary but be <= exponential value
        delay1 = strategy.calculate_backoff(2)  # Base would be 4.0
        delay2 = strategy.calculate_backoff(2)
        
        # Should be in range [0, 4.0]
        assert 0 <= delay1 <= 4.0
        assert 0 <= delay2 <= 4.0
        
        # Multiple calls might produce different values (stochastic test)
        # Run multiple times to increase chance of difference
        delays = [strategy.calculate_backoff(2) for _ in range(10)]
        # At least some variation expected
        assert len(set(delays)) > 1 or delays[0] == 0  # All zeros is okay
    
    def test_is_retryable_http_status(self):
        """Test HTTP status code classification."""
        strategy = RetryStrategy()
        
        # Retryable status codes
        assert strategy.is_retryable_http_status(429) is True  # Rate limit
        assert strategy.is_retryable_http_status(500) is True  # Server error
        assert strategy.is_retryable_http_status(502) is True  # Bad gateway
        assert strategy.is_retryable_http_status(503) is True  # Service unavailable
        assert strategy.is_retryable_http_status(504) is True  # Gateway timeout
        
        # Non-retryable status codes
        assert strategy.is_retryable_http_status(400) is False  # Bad request
        assert strategy.is_retryable_http_status(401) is False  # Unauthorized
        assert strategy.is_retryable_http_status(403) is False  # Forbidden
        assert strategy.is_retryable_http_status(404) is False  # Not found
        
        # Success codes
        assert strategy.is_retryable_http_status(200) is False
        assert strategy.is_retryable_http_status(201) is False
    
    def test_should_retry_exception_type(self):
        """Test exception type classification."""
        strategy = RetryStrategy()
        
        # Retryable exceptions
        assert strategy.should_retry(RetryableError("Retry me")) is True
        assert strategy.should_retry(ConnectionError("Network issue")) is True
        assert strategy.should_retry(TimeoutError("Timeout")) is True
        
        # Non-retryable exceptions
        assert strategy.should_retry(NonRetryableError("Don't retry")) is False
        assert strategy.should_retry(ValueError("Invalid input")) is False
    
    @pytest.mark.asyncio
    async def test_execute_async_success_first_try(self):
        """Test successful execution on first attempt."""
        strategy = RetryStrategy()
        
        async def successful_func():
            return "success"
        
        result = await strategy.execute_async(successful_func)
        
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_execute_async_success_after_retries(self):
        """Test successful execution after retries."""
        strategy = RetryStrategy(max_retries=3, base_backoff=0.1)
        
        call_count = 0
        
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetryableError("Temporary failure")
            return "success"
        
        result = await strategy.execute_async(flaky_func)
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_execute_async_max_retries_exceeded(self):
        """Test failure after max retries exceeded."""
        strategy = RetryStrategy(max_retries=2, base_backoff=0.1)
        
        async def always_fails():
            raise RetryableError("Always fails")
        
        with pytest.raises(RetryableError):
            await strategy.execute_async(always_fails)
    
    @pytest.mark.asyncio
    async def test_execute_async_non_retryable_error(self):
        """Test that non-retryable errors are not retried."""
        strategy = RetryStrategy(max_retries=3)
        
        call_count = 0
        
        async def non_retryable_func():
            nonlocal call_count
            call_count += 1
            raise NonRetryableError("Don't retry")
        
        with pytest.raises(NonRetryableError):
            await strategy.execute_async(non_retryable_func)
        
        # Should only be called once
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_execute_async_with_args(self):
        """Test execution with function arguments."""
        strategy = RetryStrategy()
        
        async def func_with_args(a, b, c=None):
            return f"{a}-{b}-{c}"
        
        result = await strategy.execute_async(func_with_args, 1, 2, c=3)
        
        assert result == "1-2-3"
    
    @pytest.mark.asyncio
    async def test_execute_async_backoff_timing(self):
        """Test that backoff delays are applied."""
        strategy = RetryStrategy(max_retries=2, base_backoff=0.1, jitter=False)
        
        call_count = 0
        times = []
        
        async def track_time_func():
            nonlocal call_count
            call_count += 1
            times.append(asyncio.get_event_loop().time())
            if call_count < 3:
                raise RetryableError("Retry")
            return "done"
        
        await strategy.execute_async(track_time_func)
        
        # Check delays between calls
        if len(times) >= 2:
            delay1 = times[1] - times[0]
            assert delay1 >= 0.1  # First backoff: 0.1s
        
        if len(times) >= 3:
            delay2 = times[2] - times[1]
            assert delay2 >= 0.2  # Second backoff: 0.2s
    
    def test_execute_sync_success(self):
        """Test synchronous execution success."""
        strategy = RetryStrategy()
        
        def successful_func():
            return "success"
        
        result = strategy.execute(successful_func)
        
        assert result == "success"
    
    def test_execute_sync_with_retries(self):
        """Test synchronous execution with retries."""
        strategy = RetryStrategy(max_retries=3, base_backoff=0.1)
        
        call_count = 0
        
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetryableError("Temporary failure")
            return "success"
        
        result = strategy.execute(flaky_func)
        
        assert result == "success"
        assert call_count == 3
    
    def test_execute_sync_max_retries_exceeded(self):
        """Test sync failure after max retries."""
        strategy = RetryStrategy(max_retries=2, base_backoff=0.05)
        
        def always_fails():
            raise RetryableError("Always fails")
        
        with pytest.raises(RetryableError):
            strategy.execute(always_fails)
    
    @pytest.mark.asyncio
    async def test_retry_decorator_async(self):
        """Test retry decorator on async functions."""
        strategy = RetryStrategy(max_retries=2, base_backoff=0.1)
        
        call_count = 0
        
        @strategy.retry_async
        async def decorated_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RetryableError("Retry")
            return "success"
        
        result = await decorated_func()
        
        assert result == "success"
        assert call_count == 2
    
    def test_retry_decorator_sync(self):
        """Test retry decorator on sync functions."""
        strategy = RetryStrategy(max_retries=2, base_backoff=0.1)
        
        call_count = 0
        
        @strategy.retry
        def decorated_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RetryableError("Retry")
            return "success"
        
        result = decorated_func()
        
        assert result == "success"
        assert call_count == 2
