"""Retry logic configuration using tenacity for robust HTTP requests."""

import logging
from dataclasses import dataclass
from typing import Callable, Optional

from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)
from tenacity.wait import wait_base

from .constants import (
    DEFAULT_BASE_BACKOFF,
    DEFAULT_MAX_BACKOFF,
    DEFAULT_MAX_RETRIES,
    RETRYABLE_STATUS_CODES,
)

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry behavior.
    
    Attributes:
        max_attempts: Maximum number of retry attempts (including initial attempt)
        min_backoff: Minimum backoff time in seconds
        max_backoff: Maximum backoff time in seconds
        retryable_status_codes: Set of HTTP status codes that should trigger retries
        retry_on_timeout: Whether to retry on timeout errors
        retry_on_connection_error: Whether to retry on connection errors
    """
    
    max_attempts: int = DEFAULT_MAX_RETRIES + 1  # +1 for initial attempt
    min_backoff: float = DEFAULT_BASE_BACKOFF
    max_backoff: float = DEFAULT_MAX_BACKOFF
    retryable_status_codes: frozenset[int] = RETRYABLE_STATUS_CODES
    retry_on_timeout: bool = True
    retry_on_connection_error: bool = True


class RetryAfterWait(wait_base):
    """Custom wait strategy that respects Retry-After headers."""
    
    def __init__(self, fallback_wait: wait_base):
        """Initialize with a fallback wait strategy.
        
        Args:
            fallback_wait: Wait strategy to use when no Retry-After header is present
        """
        self.fallback_wait = fallback_wait
    
    def __call__(self, retry_state: RetryCallState) -> float:
        """Calculate wait time based on Retry-After header or fallback.
        
        Args:
            retry_state: Current retry state
            
        Returns:
            Wait time in seconds
        """
        # Check if the exception has a retry_after attribute
        if retry_state.outcome and retry_state.outcome.failed:
            exception = retry_state.outcome.exception()
            retry_after = getattr(exception, 'retry_after', None)
            if retry_after is not None and retry_after > 0:
                logger.info(f"Respecting Retry-After header: {retry_after}s")
                return float(retry_after)
        
        # Fall back to exponential backoff with jitter
        return self.fallback_wait(retry_state)


def _should_retry_on_exception(exception: Exception) -> bool:
    """Check if an exception should trigger a retry.
    
    Args:
        exception: The exception to check
        
    Returns:
        True if the exception should trigger a retry
    """
    # Import here to avoid circular dependency
    try:
        from .http_client import HTTPError
        
        # Retry on HTTPError with retryable status codes
        if isinstance(exception, HTTPError):
            return exception.status in RETRYABLE_STATUS_CODES
    except ImportError:
        pass
    
    return False


def _before_retry_log(retry_state: RetryCallState) -> None:
    """Log before attempting a retry.
    
    Args:
        retry_state: Current retry state
    """
    attempt_number = retry_state.attempt_number
    if retry_state.outcome and retry_state.outcome.failed:
        exception = retry_state.outcome.exception()
        # Extract retry_after if present
        retry_after = getattr(exception, 'retry_after', None)
        if retry_after:
            logger.warning(
                f"Retry attempt {attempt_number} after error: {type(exception).__name__}: {exception} "
                f"(Retry-After: {retry_after}s)"
            )
        else:
            logger.warning(
                f"Retry attempt {attempt_number} after error: {type(exception).__name__}: {exception}"
            )
    elif retry_state.outcome:
        result = retry_state.outcome.result()
        status = getattr(result, 'status', 'unknown')
        logger.warning(
            f"Retry attempt {attempt_number} after HTTP {status}"
        )


def _after_retry_log(retry_state: RetryCallState) -> None:
    """Log after a retry attempt.
    
    Args:
        retry_state: Current retry state
    """
    if retry_state.outcome and not retry_state.outcome.failed:
        logger.info(f"Retry successful on attempt {retry_state.attempt_number}")


def create_retry_decorator(
    config: Optional[RetryConfig] = None,
    before_retry: Optional[Callable[[RetryCallState], None]] = None,
    after_retry: Optional[Callable[[RetryCallState], None]] = None,
) -> AsyncRetrying:
    """Create a retry decorator with the given configuration.
    
    Args:
        config: Retry configuration. Uses defaults if None.
        before_retry: Optional callback to call before each retry attempt
        after_retry: Optional callback to call after each retry attempt
        
    Returns:
        Configured AsyncRetrying instance for use with async functions
        
    Example:
        ```python
        retry = create_retry_decorator()
        
        async def fetch_data():
            async for attempt in retry:
                with attempt:
                    response = await client.get(url)
                    return response
        ```
    """
    if config is None:
        config = RetryConfig()
    
    # Use default logging callbacks if not provided
    if before_retry is None:
        before_retry = _before_retry_log
    if after_retry is None:
        after_retry = _after_retry_log
    
    # Create wait strategy with Retry-After support
    base_wait = wait_exponential_jitter(
        initial=config.min_backoff,
        max=config.max_backoff,
    )
    wait_strategy = RetryAfterWait(base_wait)
    
    # Build retry conditions
    retry_conditions = []
    
    # Retry on HTTPError with retryable status codes
    from tenacity import retry_if_exception
    retry_conditions.append(retry_if_exception(_should_retry_on_exception))
    
    # Retry on timeout errors
    if config.retry_on_timeout:
        import asyncio
        retry_conditions.append(retry_if_exception_type(asyncio.TimeoutError))
        try:
            from aiohttp import ServerTimeoutError
            retry_conditions.append(retry_if_exception_type(ServerTimeoutError))
        except ImportError:
            pass
    
    # Retry on connection errors
    if config.retry_on_connection_error:
        try:
            from aiohttp import ClientConnectionError
            retry_conditions.append(retry_if_exception_type(ClientConnectionError))
        except ImportError:
            pass
    
    # Combine all retry conditions
    from tenacity import retry_any
    retry_condition = retry_any(*retry_conditions) if retry_conditions else None
    
    return AsyncRetrying(
        stop=stop_after_attempt(config.max_attempts),
        wait=wait_strategy,
        retry=retry_condition,
        before_sleep=before_retry,
        after=after_retry,
        reraise=True,
    )
