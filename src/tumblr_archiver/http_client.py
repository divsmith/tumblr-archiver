"""Async HTTP client with rate limiting, retry logic, and file download support."""

import logging
from pathlib import Path
from typing import Any, Callable, Optional, Union

import aiohttp
from aiohttp import ClientResponse, ClientTimeout

from .cache import ResponseCache
from .constants import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RATE_LIMIT,
    DEFAULT_TIMEOUT,
    HTTP_TOO_MANY_REQUESTS,
    RETRYABLE_STATUS_CODES,
    USER_AGENT,
)
from .rate_limiter import TokenBucketRateLimiter
from .retry import RetryConfig, create_retry_decorator

logger = logging.getLogger(__name__)

# Type alias for progress callbacks
ProgressCallback = Callable[[int, Optional[int]], None]


class HTTPError(Exception):
    """Base exception for HTTP errors."""
    
    def __init__(self, message: str, status: Optional[int] = None, url: Optional[str] = None):
        """Initialize HTTP error.
        
        Args:
            message: Error message
            status: HTTP status code
            url: URL that caused the error
        """
        super().__init__(message)
        self.status = status
        self.url = url


class RateLimitError(HTTPError):
    """Exception raised when rate limited (HTTP 429)."""
    
    def __init__(self, message: str, retry_after: Optional[float] = None, url: Optional[str] = None):
        """Initialize rate limit error.
        
        Args:
            message: Error message
            retry_after: Seconds to wait before retrying
            url: URL that caused the error
        """
        super().__init__(message, HTTP_TOO_MANY_REQUESTS, url)
        self.retry_after = retry_after


class AsyncHTTPClient:
    """Async HTTP client with rate limiting, retries, and download support.
    
    Features:
    - Rate limiting with token bucket algorithm
    - Automatic retries with exponential backoff and jitter
    - Respects Retry-After headers
    - Custom User-Agent
    - File download with progress callbacks
    - Proper resource management via context manager
    
    Example:
        ```python
        async with AsyncHTTPClient(rate_limit=2.0) as client:
            response = await client.get("https://example.com")
            data = await response.json()
            
            # Download a file
            await client.download_file(
                "https://example.com/file.jpg",
                Path("file.jpg"),
                progress_callback=lambda downloaded, total: print(f"{downloaded}/{total}")
            )
        ```
    """
    
    def __init__(
        self,
        rate_limit: float = DEFAULT_RATE_LIMIT,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        user_agent: str = USER_AGENT,
        retry_config: Optional[RetryConfig] = None,
        session: Optional[aiohttp.ClientSession] = None,
        cache: Optional[ResponseCache] = None,
    ):
        """Initialize the HTTP client.
        
        Args:
            rate_limit: Maximum requests per second
            timeout: Default request timeout in seconds
            max_retries: Maximum number of retry attempts
            user_agent: User-Agent header value
            retry_config: Custom retry configuration
            session: Optional existing aiohttp session to use
            cache: Optional response cache for GET requests
        """
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent
        
        # Initialize rate limiter
        self._rate_limiter = TokenBucketRateLimiter(rate_limit=rate_limit)
        
        # Initialize retry configuration
        if retry_config is None:
            retry_config = RetryConfig(max_attempts=max_retries + 1)
        self._retry_config = retry_config
        self._retry_decorator = create_retry_decorator(retry_config)
        
        # Session management
        self._session = session
        self._owns_session = session is None
        self._closed = False
        
        # Optional response cache
        self._cache = cache
        
        logger.info(
            f"Initialized AsyncHTTPClient: rate_limit={rate_limit} req/s, "
            f"timeout={timeout}s, max_retries={max_retries}, "
            f"cache={'enabled' if cache else 'disabled'}"
        )
    
    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure a session exists and return it.
        
        Returns:
            Active aiohttp ClientSession
        """
        if self._session is None or self._session.closed:
            timeout = ClientTimeout(total=self.timeout)
            headers = {
                'User-Agent': self.user_agent,
            }
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers=headers,
            )
            logger.debug("Created new aiohttp session")
        return self._session
    
    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._closed:
            return
        
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()
            logger.debug("Closed aiohttp session")
        
        self._closed = True
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        return False
    
    def _extract_retry_after(self, response: ClientResponse) -> Optional[float]:
        """Extract Retry-After header value from response.
        
        Args:
            response: HTTP response
            
        Returns:
            Seconds to wait, or None if header not present
        """
        retry_after = response.headers.get('Retry-After')
        if retry_after:
            try:
                # Try parsing as seconds (integer)
                return float(retry_after)
            except ValueError:
                # Could be HTTP date format, but we'll skip that complexity
                logger.warning(f"Could not parse Retry-After header: {retry_after}")
        return None
    
    async def _check_response_status(self, response: ClientResponse) -> None:
        """Check response status and raise appropriate exceptions.
        
        Args:
            response: HTTP response to check
            
        Raises:
            RateLimitError: If rate limited (429)
            HTTPError: For other error status codes
        """
        if response.status in RETRYABLE_STATUS_CODES:
            # Store retry_after on response for RetryAfterWait to use
            retry_after = self._extract_retry_after(response)
            
            # Raise RateLimitError specifically for 429
            if response.status == HTTP_TOO_MANY_REQUESTS:
                error = RateLimitError(
                    "Rate limited by server",
                    retry_after=retry_after,
                    url=str(response.url),
                )
                error.retry_after = retry_after
                raise error
            
            # Create HTTPError for other retryable status codes
            error = HTTPError(
                f"HTTP {response.status}: {response.reason}",
                status=response.status,
                url=str(response.url),
            )
            error.retry_after = retry_after
            raise error
        
        # Raise for non-retryable error status codes
        if response.status >= 400:
            text = await response.text()
            raise HTTPError(
                f"HTTP {response.status}: {response.reason} - {text[:200]}",
                status=response.status,
                url=str(response.url),
            )
    
    async def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> ClientResponse:
        """Make an HTTP request with rate limiting and retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: URL to request
            **kwargs: Additional arguments to pass to session.request()
            
        Returns:
            HTTP response
            
        Raises:
            HTTPError: On HTTP errors
            RateLimitError: On rate limiting
        """
        session = await self._ensure_session()
        
        # Apply rate limiting and retry logic
        async for attempt in self._retry_decorator:
            with attempt:
                # Acquire rate limit token
                async with self._rate_limiter:
                    logger.debug(f"{method} {url}")
                    
                    # Make the request
                    response = await session.request(method, url, **kwargs)
                    
                    # Check for errors
                    await self._check_response_status(response)
                    
                    return response
    
    async def get(
        self,
        url: str,
        use_cache: bool = True,
        **kwargs: Any,
    ) -> ClientResponse:
        """Make a GET request.
        
        Args:
            url: URL to request
            use_cache: Whether to use cache (if enabled). Default: True
            **kwargs: Additional arguments to pass to the request
            
        Returns:
            HTTP response
        """
        # Check cache first (only for GET requests without custom params)
        if use_cache and self._cache and not kwargs:
            cached_response = self._cache.get(url)
            if cached_response is not None:
                logger.debug(f"Returning cached response for {url}")
                return cached_response
        
        # Make request
        response = await self._request('GET', url, **kwargs)
        
        # Cache the response (only for GET requests without custom params)
        if use_cache and self._cache and not kwargs and response.status == 200:
            # Note: We cache the response object itself
            # In production, you might want to cache the content instead
            self._cache.set(url, response)
            logger.debug(f"Cached response for {url}")
        
        return response
    
    async def post(
        self,
        url: str,
        data: Any = None,
        json: Any = None,
        **kwargs: Any,
    ) -> ClientResponse:
        """Make a POST request.
        
        Args:
            url: URL to request
            data: Form data to send
            json: JSON data to send
            **kwargs: Additional arguments to pass to the request
            
        Returns:
            HTTP response
        """
        return await self._request('POST', url, data=data, json=json, **kwargs)
    
    async def head(
        self,
        url: str,
        **kwargs: Any,
    ) -> ClientResponse:
        """Make a HEAD request.
        
        Args:
            url: URL to request
            **kwargs: Additional arguments to pass to the request
            
        Returns:
            HTTP response
        """
        return await self._request('HEAD', url, **kwargs)
    
    async def download_file(
        self,
        url: str,
        destination: Union[str, Path],
        chunk_size: int = 8192,
        progress_callback: Optional[ProgressCallback] = None,
        **kwargs: Any,
    ) -> Path:
        """Download a file with progress tracking.
        
        Args:
            url: URL to download from
            destination: Path to save the file
            chunk_size: Size of chunks to read (bytes)
            progress_callback: Optional callback(downloaded_bytes, total_bytes)
                              Called after each chunk. total_bytes may be None.
            **kwargs: Additional arguments to pass to the request
            
        Returns:
            Path to the downloaded file
            
        Raises:
            HTTPError: On HTTP errors
            IOError: On file write errors
        """
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        # Use streaming response
        async with await self.get(url, **kwargs) as response:
            total_size = response.content_length
            downloaded = 0
            
            logger.info(
                f"Downloading {url} to {destination} "
                f"(size: {total_size or 'unknown'})"
            )
            
            with open(destination, 'wb') as f:
                async for chunk in response.content.iter_chunked(chunk_size):
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if progress_callback:
                        progress_callback(downloaded, total_size)
            
            logger.info(f"Downloaded {downloaded} bytes to {destination}")
            
        return destination
    
    def __repr__(self) -> str:
        """String representation of the client."""
        return (
            f"AsyncHTTPClient(rate_limit={self.rate_limit}, "
            f"timeout={self.timeout}, max_retries={self.max_retries})"
        )
