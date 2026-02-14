"""Retry logic with exponential backoff for API requests.

This module provides retry mechanisms with exponential backoff, jitter,
and intelligent error classification for handling transient failures.
"""

import asyncio
import functools
import logging
import random
import time
from typing import Any, Callable, Optional, Set, Type, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class RetryableError(Exception):
    """Exception indicating an operation should be retried."""
    pass


class NonRetryableError(Exception):
    """Exception indicating an operation should not be retried."""
    pass


@dataclass
class RetryStats:
    """Statistics about retry attempts."""
    total_attempts: int = 0
    total_delay: float = 0.0
    last_error: Optional[Exception] = None


class RetryStrategy:
    """Configurable retry strategy with exponential backoff.
    
    Implements exponential backoff with optional jitter to prevent
    thundering herd problems when multiple clients retry simultaneously.
    
    Attributes:
        max_retries: Maximum number of retry attempts
        base_backoff: Base delay in seconds for exponential backoff
        max_backoff: Maximum delay in seconds (cap for exponential growth)
        jitter: Whether to add randomized jitter to backoff delays
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        base_backoff: float = 1.0,
        max_backoff: float = 32.0,
        jitter: bool = True
    ):
        """Initialize retry strategy.
        
        Args:
            max_retries: Maximum number of retry attempts (default: 3)
            base_backoff: Base delay in seconds (default: 1.0)
            max_backoff: Maximum delay in seconds (default: 32.0)
            jitter: Add randomized jitter to delays (default: True)
            
        Raises:
            ValueError: If parameters are invalid
        """
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if base_backoff <= 0:
            raise ValueError("base_backoff must be positive")
        if max_backoff < base_backoff:
            raise ValueError("max_backoff must be >= base_backoff")
        
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self.max_backoff = max_backoff
        self.jitter = jitter
        
        # Retryable HTTP status codes
        self.retryable_status_codes: Set[int] = {
            429,  # Too Many Requests
            500,  # Internal Server Error
            502,  # Bad Gateway
            503,  # Service Unavailable
            504,  # Gateway Timeout
        }
        
        # Non-retryable HTTP status codes
        self.non_retryable_status_codes: Set[int] = {
            400,  # Bad Request
            401,  # Unauthorized
            403,  # Forbidden
            404,  # Not Found
        }
        
        logger.debug(
            f"RetryStrategy initialized: max_retries={max_retries}, "
            f"base_backoff={base_backoff}s, max_backoff={max_backoff}s, "
            f"jitter={jitter}"
        )
    
    def calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay for given attempt.
        
        Formula: min(base * 2^attempt, max_backoff)
        
        Args:
            attempt: Current retry attempt number (0-indexed)
            
        Returns:
            Delay in seconds before next retry
        """
        delay = self.base_backoff * (2 ** attempt)
        delay = min(delay, self.max_backoff)
        
        if self.jitter:
            delay = self.add_jitter(delay)
        
        return delay
    
    def add_jitter(self, delay: float) -> float:
        """Add randomized jitter to delay.
        
        Applies multiplicative jitter: delay * random(0.5, 1.5)
        This helps prevent thundering herd problems.
        
        Args:
            delay: Base delay in seconds
            
        Returns:
            Delay with jitter applied
        """
        jitter_factor = 0.5 + random.random()  # 0.5 to 1.5
        return delay * jitter_factor
    
    def should_retry(
        self,
        exception: Exception,
        attempt: int,
        response: Optional[Any] = None
    ) -> bool:
        """Determine if error is retryable based on exception and attempt count.
        
        Args:
            exception: The exception that occurred
            attempt: Current attempt number (0-indexed)
            response: Optional HTTP response object
            
        Returns:
            True if the operation should be retried, False otherwise
        """
        # Check if we've exceeded max retries
        if attempt >= self.max_retries:
            logger.debug(f"Max retries ({self.max_retries}) exceeded")
            return False
        
        # Check for explicit retry markers
        if isinstance(exception, NonRetryableError):
            logger.debug("NonRetryableError encountered, not retrying")
            return False
        
        if isinstance(exception, RetryableError):
            logger.debug("RetryableError encountered, will retry")
            return True
        
        # Check for network-related exceptions
        network_exceptions = (
            asyncio.TimeoutError,
            ConnectionError,
            ConnectionRefusedError,
            ConnectionResetError,
        )
        
        if isinstance(exception, network_exceptions):
            logger.debug(f"Network error encountered: {type(exception).__name__}")
            return True
        
        # Check HTTP response status if available
        if hasattr(exception, 'status') or hasattr(exception, 'status_code'):
            status = getattr(exception, 'status', None) or getattr(
                exception, 'status_code', None
            )
            if status:
                return self._is_status_retryable(status)
        
        # Default: retry on generic exceptions
        logger.debug(f"Unknown exception type: {type(exception).__name__}, retrying")
        return True
    
    def _is_status_retryable(self, status: int) -> bool:
        """Check if HTTP status code is retryable.
        
        Args:
            status: HTTP status code
            
        Returns:
            True if status indicates a retryable error
        """
        if status in self.non_retryable_status_codes:
            logger.debug(f"Non-retryable HTTP status: {status}")
            return False
        
        if status in self.retryable_status_codes:
            logger.debug(f"Retryable HTTP status: {status}")
            return True
        
        # Retry on any 5xx status
        if 500 <= status < 600:
            logger.debug(f"Server error status: {status}, will retry")
            return True
        
        # Don't retry other statuses
        logger.debug(f"Non-retryable HTTP status: {status}")
        return False


def classify_http_error(
    status_code: int,
    response: Optional[Any] = None
) -> Type[Exception]:
    """Classify HTTP error for retry behavior.
    
    Args:
        status_code: HTTP status code
        response: Optional HTTP response object
        
    Returns:
        Exception class (RetryableError or NonRetryableError)
    """
    retryable_codes = {429, 500, 502, 503, 504}
    non_retryable_codes = {400, 401, 403, 404}
    
    if status_code in retryable_codes:
        return RetryableError
    elif status_code in non_retryable_codes:
        return NonRetryableError
    elif 500 <= status_code < 600:
        return RetryableError
    else:
        return NonRetryableError


def extract_retry_after(response: Any) -> Optional[float]:
    """Extract Retry-After header value from HTTP response.
    
    Args:
        response: HTTP response object
        
    Returns:
        Delay in seconds, or None if header not present
    """
    if not response:
        return None
    
    # Try to get Retry-After header
    retry_after = None
    if hasattr(response, 'headers'):
        retry_after = response.headers.get('Retry-After') or response.headers.get(
            'retry-after'
        )
    
    if not retry_after:
        return None
    
    # Parse Retry-After value (can be seconds or HTTP date)
    try:
        # Try as integer seconds
        return float(retry_after)
    except ValueError:
        # Could be HTTP date format, but we'll skip parsing for simplicity
        logger.debug(f"Could not parse Retry-After value: {retry_after}")
        return None


def retry_with_backoff(
    max_retries: int = 3,
    base_backoff: float = 1.0,
    max_backoff: float = 32.0,
    jitter: bool = True,
    retryable_exceptions: Optional[tuple] = None
):
    """Decorator for automatic retries with exponential backoff.
    
    Usage:
        @retry_with_backoff(max_retries=3, base_backoff=1.0)
        async def fetch_data():
            # Your async function here
            pass
    
    Args:
        max_retries: Maximum number of retry attempts
        base_backoff: Base delay in seconds
        max_backoff: Maximum delay in seconds
        jitter: Add randomized jitter to delays
        retryable_exceptions: Tuple of exception types to retry on
        
    Returns:
        Decorated async function with retry logic
    """
    strategy = RetryStrategy(max_retries, base_backoff, max_backoff, jitter)
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            stats = RetryStats()
            last_exception = None
            
            for attempt in range(max_retries + 1):
                stats.total_attempts += 1
                
                try:
                    # Log retry attempts (but not the first attempt)
                    if attempt > 0:
                        logger.info(
                            f"Retry attempt {attempt}/{max_retries} for "
                            f"{func.__name__}"
                        )
                    
                    result = await func(*args, **kwargs)
                    
                    # Log success after retries
                    if attempt > 0:
                        logger.info(
                            f"{func.__name__} succeeded after {attempt} "
                            f"retry(ies), total delay: {stats.total_delay:.2f}s"
                        )
                    
                    return result
                
                except Exception as e:
                    last_exception = e
                    stats.last_error = e
                    
                    # Check if we should retry
                    response = getattr(e, 'response', None)
                    
                    if not strategy.should_retry(e, attempt, response):
                        # Log final failure
                        logger.error(
                            f"{func.__name__} failed permanently: "
                            f"{type(e).__name__}: {e}"
                        )
                        raise
                    
                    # Check for Retry-After header
                    retry_after = extract_retry_after(response)
                    if retry_after:
                        delay = retry_after
                        logger.info(
                            f"Using Retry-After header: {delay}s for "
                            f"{func.__name__}"
                        )
                    else:
                        delay = strategy.calculate_backoff(attempt)
                    
                    stats.total_delay += delay
                    
                    # Log retry with reason and delay
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/"
                        f"{max_retries + 1}): {type(e).__name__}: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    
                    # Emit warning for excessive retries
                    if attempt >= max_retries - 1:
                        logger.warning(
                            f"{func.__name__} approaching max retries "
                            f"({attempt + 1}/{max_retries})"
                        )
                    
                    # Wait before retry
                    await asyncio.sleep(delay)
            
            # All retries exhausted
            logger.error(
                f"{func.__name__} failed after {stats.total_attempts} attempts, "
                f"total delay: {stats.total_delay:.2f}s"
            )
            raise last_exception
        
        return wrapper
    
    return decorator


class CircuitBreaker:
    """Circuit breaker pattern for preventing cascading failures.
    
    The circuit breaker has three states:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests fail immediately
    - HALF_OPEN: Testing if service has recovered
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        """Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exception type to count as failure
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = "CLOSED"  # CLOSED, OPEN, or HALF_OPEN
        
        logger.debug(
            f"CircuitBreaker initialized: threshold={failure_threshold}, "
            f"timeout={recovery_timeout}s"
        )
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection.
        
        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Result from func
            
        Raises:
            Exception: If circuit is open or func raises
        """
        if self._state == "OPEN":
            # Check if we should transition to HALF_OPEN
            if self._should_attempt_reset():
                self._state = "HALF_OPEN"
                logger.info("Circuit breaker transitioning to HALF_OPEN")
            else:
                raise NonRetryableError("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._last_failure_time is None:
            return True
        
        elapsed = time.monotonic() - self._last_failure_time
        return elapsed >= self.recovery_timeout
    
    def _on_success(self) -> None:
        """Handle successful request."""
        if self._state == "HALF_OPEN":
            logger.info("Circuit breaker transitioning to CLOSED")
        
        self._failure_count = 0
        self._state = "CLOSED"
    
    def _on_failure(self) -> None:
        """Handle failed request."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        
        if self._failure_count >= self.failure_threshold:
            if self._state != "OPEN":
                logger.warning(
                    f"Circuit breaker opening after {self._failure_count} failures"
                )
                self._state = "OPEN"
