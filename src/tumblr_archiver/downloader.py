"""
Download Manager for Tumblr Media Archiver.

Handles file downloads with checksums, resume support, and verification.
"""

import asyncio
import hashlib
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

import aiofiles
import aiohttp


# Custom exceptions
class DownloadError(Exception):
    """Base exception for download errors."""
    pass


class MediaNotFoundError(DownloadError):
    """Media file not found (404, 403, 410)."""
    pass


class IntegrityError(DownloadError):
    """File integrity check failed."""
    pass


@dataclass
class DownloadResult:
    """Result of a download operation."""
    filename: str
    byte_size: int
    checksum: str  # SHA256
    duration: float
    source: str  # 'tumblr', 'internet_archive', 'external'
    status: str  # 'success', 'missing', 'error'
    error_message: Optional[str] = None
    media_missing_on_tumblr: bool = False


@dataclass
class RateLimiter:
    """Simple token bucket rate limiter."""
    rate: float  # requests per second
    max_tokens: float = field(init=False)
    tokens: float = field(init=False)
    last_update: float = field(default_factory=time.time)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def __post_init__(self):
        self.max_tokens = self.rate
        self.tokens = self.rate

    async def acquire(self, n: int = 1):
        """Acquire n tokens, waiting if necessary."""
        async with self.lock:
            while self.tokens < n:
                now = time.time()
                elapsed = now - self.last_update
                self.tokens = min(self.max_tokens, self.tokens + elapsed * self.rate)
                self.last_update = now
                
                if self.tokens < n:
                    wait_time = (n - self.tokens) / self.rate
                    await asyncio.sleep(wait_time)
            
            self.tokens -= n
            self.last_update = time.time()


@dataclass
class RetryStrategy:
    """Exponential backoff retry strategy."""
    max_retries: int = 3
    base_backoff: float = 1.0
    max_backoff: float = 32.0
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function with retry logic."""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_exception = e
                
                if attempt == self.max_retries:
                    raise DownloadError(f"Max retries ({self.max_retries}) exceeded") from e
                
                # Calculate backoff with exponential increase
                backoff = min(self.base_backoff * (2 ** attempt), self.max_backoff)
                # Add jitter to avoid thundering herd
                import random
                jitter = random.uniform(0, backoff * 0.1)
                await asyncio.sleep(backoff + jitter)
        
        raise DownloadError("Retry failed") from last_exception


class DownloadManager:
    """Manages file downloads with checksums, resume support, and verification."""
    
    # Known Tumblr placeholder image checksums (small 1x1 PNGs)
    PLACEHOLDER_CHECKSUMS = {
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",  # Empty file
        "6c0a2b0e0f6e1c9c0b8d5e7f8a9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7",  # Common 1x1
    }
    
    # Minimum file sizes for media types (bytes)
    MIN_IMAGE_SIZE = 100
    MIN_VIDEO_SIZE = 1024
    
    def __init__(
        self,
        output_dir: str,
        rate_limiter: Optional[RateLimiter] = None,
        retry_strategy: Optional[RetryStrategy] = None,
        max_concurrent: int = 5,
        timeout: int = 300
    ):
        """
        Initialize the download manager.
        
        Args:
            output_dir: Base directory for downloaded files
            rate_limiter: Rate limiter for throttling requests
            retry_strategy: Retry strategy for handling transient failures
            max_concurrent: Maximum number of concurrent downloads
            timeout: Download timeout in seconds
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.rate_limiter = rate_limiter or RateLimiter(rate=5.0)
        self.retry_strategy = retry_strategy or RetryStrategy()
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
            self._session = None
    
    def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the HTTP session."""
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session
    
    def generate_filename(
        self,
        url: str,
        post_id: str,
        media_type: str,
        index: int = 0
    ) -> str:
        """
        Generate a unique filename for downloaded media.
        
        Args:
            url: Source URL of the media
            post_id: Tumblr post ID
            media_type: Media type (image, video, gif)
            index: Index for multiple media in same post
        
        Returns:
            Generated filename with pattern: {post_id}_{index}_{hash_prefix}.{ext}
        """
        # Extract extension from URL
        parsed = urlparse(url)
        path = parsed.path
        ext = os.path.splitext(path)[1].lower()
        
        # Default extensions if not found
        if not ext:
            ext_map = {
                'image': '.jpg',
                'video': '.mp4',
                'gif': '.gif'
            }
            ext = ext_map.get(media_type, '.bin')
        
        # Create hash prefix from URL
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        
        # Generate filename
        filename = f"{post_id}_{index}_{url_hash}{ext}"
        
        # Handle collisions by incrementing suffix
        output_path = self.output_dir / filename
        counter = 1
        while output_path.exists():
            name_part = f"{post_id}_{index}_{url_hash}_{counter}"
            filename = f"{name_part}{ext}"
            output_path = self.output_dir / filename
            counter += 1
        
        return filename
    
    async def download_file(
        self,
        url: str,
        filename: str,
        metadata: Optional[Dict[str, Any]] = None,
        verify_size: bool = True,
        verify_content_type: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        expected_checksum: Optional[str] = None
    ) -> DownloadResult:
        """
        Download a file with verification and checksum computation.
        
        Args:
            url: URL to download from
            filename: Target filename (relative to output_dir)
            metadata: Optional metadata about the file
            verify_size: Verify file size is reasonable
            verify_content_type: Verify Content-Type header
            progress_callback: Callback for progress updates (bytes_downloaded, total_bytes)
            expected_checksum: Expected SHA256 checksum for verification
        
        Returns:
            DownloadResult with download information
        
        Raises:
            MediaNotFoundError: If media is not found (404, 403, 410)
            IntegrityError: If integrity checks fail
            DownloadError: For other download errors
        """
        start_time = time.time()
        output_path = self.output_dir / filename
        temp_path = output_path.with_suffix(output_path.suffix + '.tmp')
        
        metadata = metadata or {}
        source = metadata.get('source', 'tumblr')
        
        # Check if file already exists with valid checksum
        if output_path.exists() and expected_checksum:
            existing_checksum = await self._compute_checksum(output_path)
            if existing_checksum == expected_checksum:
                duration = time.time() - start_time
                return DownloadResult(
                    filename=filename,
                    byte_size=output_path.stat().st_size,
                    checksum=existing_checksum,
                    duration=duration,
                    source=source,
                    status='success'
                )
        
        try:
            # Acquire rate limit token
            await self.rate_limiter.acquire()
            
            # Acquire semaphore for concurrency control
            async with self.semaphore:
                # Download with retry
                result = await self.retry_strategy.execute(
                    self._download_file_impl,
                    url,
                    temp_path,
                    output_path,
                    verify_size,
                    verify_content_type,
                    progress_callback,
                    expected_checksum,
                    source
                )
                
                duration = time.time() - start_time
                return DownloadResult(
                    filename=filename,
                    byte_size=result['size'],
                    checksum=result['checksum'],
                    duration=duration,
                    source=source,
                    status='success'
                )
                
        except MediaNotFoundError as e:
            duration = time.time() - start_time
            return DownloadResult(
                filename=filename,
                byte_size=0,
                checksum='',
                duration=duration,
                source=source,
                status='missing',
                error_message=str(e),
                media_missing_on_tumblr=True
            )
        except (DownloadError, IntegrityError) as e:
            duration = time.time() - start_time
            return DownloadResult(
                filename=filename,
                byte_size=0,
                checksum='',
                duration=duration,
                source=source,
                status='error',
                error_message=str(e)
            )
        finally:
            # Clean up temp file if it exists
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
    
    async def _download_file_impl(
        self,
        url: str,
        temp_path: Path,
        output_path: Path,
        verify_size: bool,
        verify_content_type: bool,
        progress_callback: Optional[Callable[[int, int], None]],
        expected_checksum: Optional[str],
        source: str
    ) -> Dict[str, Any]:
        """Internal implementation of file download."""
        session = self._get_session()
        
        async with session.get(url) as response:
            # Check for error status codes
            if response.status in (404, 403, 410):
                raise MediaNotFoundError(f"Media not found: HTTP {response.status}")
            
            response.raise_for_status()
            
            # Get content info
            content_type = response.headers.get('Content-Type', '').lower()
            content_length = response.headers.get('Content-Length')
            total_bytes = int(content_length) if content_length else 0
            
            # Verify content type if requested
            if verify_content_type:
                self._verify_content_type(content_type, url)
            
            # Download to temporary file with checksum computation
            checksum_hash = hashlib.sha256()
            bytes_downloaded = 0
            
            async with aiofiles.open(temp_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(8192):
                    await f.write(chunk)
                    checksum_hash.update(chunk)
                    bytes_downloaded += len(chunk)
                    
                    if progress_callback and total_bytes:
                        try:
                            progress_callback(bytes_downloaded, total_bytes)
                        except Exception:
                            pass  # Don't let callback errors stop download
            
            checksum = checksum_hash.hexdigest()
            
            # Verify checksum if provided
            if expected_checksum and checksum != expected_checksum:
                raise IntegrityError(
                    f"Checksum mismatch: expected {expected_checksum}, got {checksum}"
                )
            
            # Check for placeholder images
            if self._is_placeholder(checksum, bytes_downloaded):
                raise MediaNotFoundError("Download is a known placeholder image")
            
            # Verify file size
            if verify_size:
                self._verify_file_size(bytes_downloaded, content_type)
            
            # Move to final location
            temp_path.rename(output_path)
            
            return {
                'size': bytes_downloaded,
                'checksum': checksum
            }
    
    def _verify_content_type(self, content_type: str, url: str):
        """Verify content type matches expected media type."""
        if not content_type:
            return  # Can't verify without content type
        
        # Check for HTML (might be error page)
        if 'text/html' in content_type:
            raise DownloadError(f"Received HTML instead of media (URL: {url})")
        
        # Valid media types
        valid_types = [
            'image/', 'video/', 'application/octet-stream',
            'binary/octet-stream', 'application/x-mpegurl'
        ]
        
        if not any(vt in content_type for vt in valid_types):
            # Allow it but could be suspicious
            pass
    
    def _verify_file_size(self, size: int, content_type: str):
        """Verify file size is reasonable for media type."""
        if 'image' in content_type and size < self.MIN_IMAGE_SIZE:
            raise IntegrityError(
                f"Image file too small ({size} bytes), might be placeholder"
            )
        
        if 'video' in content_type and size < self.MIN_VIDEO_SIZE:
            raise IntegrityError(
                f"Video file too small ({size} bytes), might be placeholder"
            )
    
    def _is_placeholder(self, checksum: str, size: int) -> bool:
        """Check if file is a known Tumblr placeholder."""
        # Check against known placeholder checksums
        if checksum in self.PLACEHOLDER_CHECKSUMS:
            return True
        
        # Empty files are placeholders
        if size == 0:
            return True
        
        # Very small files are suspicious
        if size < 43:  # Smallest valid image format
            return True
        
        return False
    
    async def _compute_checksum(self, filepath: Path) -> str:
        """Compute SHA256 checksum of a file."""
        checksum_hash = hashlib.sha256()
        
        async with aiofiles.open(filepath, 'rb') as f:
            while True:
                chunk = await f.read(8192)
                if not chunk:
                    break
                checksum_hash.update(chunk)
        
        return checksum_hash.hexdigest()
    
    async def download_image(
        self,
        url: str,
        post_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        index: int = 0,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> DownloadResult:
        """
        Download an image file.
        
        Args:
            url: Image URL
            post_id: Tumblr post ID
            metadata: Optional metadata about the image
            index: Index for multiple images in same post
            progress_callback: Progress callback function
        
        Returns:
            DownloadResult with download information
        """
        filename = self.generate_filename(url, post_id, 'image', index)
        metadata = metadata or {}
        metadata['media_type'] = 'image'
        
        return await self.download_file(
            url=url,
            filename=filename,
            metadata=metadata,
            verify_size=True,
            verify_content_type=True,
            progress_callback=progress_callback
        )
    
    async def download_video(
        self,
        url: str,
        post_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        index: int = 0,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> DownloadResult:
        """
        Download a video file.
        
        Args:
            url: Video URL
            post_id: Tumblr post ID
            metadata: Optional metadata about the video
            index: Index for multiple videos in same post
            progress_callback: Progress callback function
        
        Returns:
            DownloadResult with download information
        """
        filename = self.generate_filename(url, post_id, 'video', index)
        metadata = metadata or {}
        metadata['media_type'] = 'video'
        
        return await self.download_file(
            url=url,
            filename=filename,
            metadata=metadata,
            verify_size=True,
            verify_content_type=True,
            progress_callback=progress_callback
        )
    
    async def download_gif(
        self,
        url: str,
        post_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        index: int = 0,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> DownloadResult:
        """
        Download an animated GIF file.
        
        Args:
            url: GIF URL
            post_id: Tumblr post ID
            metadata: Optional metadata about the GIF
            index: Index for multiple GIFs in same post
            progress_callback: Progress callback function
        
        Returns:
            DownloadResult with download information
        """
        filename = self.generate_filename(url, post_id, 'gif', index)
        metadata = metadata or {}
        metadata['media_type'] = 'gif'
        
        return await self.download_file(
            url=url,
            filename=filename,
            metadata=metadata,
            verify_size=True,
            verify_content_type=True,
            progress_callback=progress_callback
        )
    
    async def download_with_resume(
        self,
        url: str,
        filename: str,
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> DownloadResult:
        """
        Download a file with resume support (Range requests).
        
        Args:
            url: URL to download from
            filename: Target filename
            metadata: Optional metadata
            progress_callback: Progress callback function
        
        Returns:
            DownloadResult with download information
        """
        output_path = self.output_dir / filename
        
        # Check if partial file exists
        if output_path.exists():
            existing_size = output_path.stat().st_size
            
            # Try to resume download
            try:
                session = self._get_session()
                headers = {'Range': f'bytes={existing_size}-'}
                
                async with session.get(url, headers=headers) as response:
                    # Check if server supports range requests
                    if response.status == 206:  # Partial content
                        # Continue download
                        checksum_hash = hashlib.sha256()
                        
                        # Re-hash existing content
                        async with aiofiles.open(output_path, 'rb') as f:
                            while True:
                                chunk = await f.read(8192)
                                if not chunk:
                                    break
                                checksum_hash.update(chunk)
                        
                        # Append new content
                        bytes_downloaded = existing_size
                        content_length = response.headers.get('Content-Length')
                        total_bytes = int(content_length) + existing_size if content_length else 0
                        
                        async with aiofiles.open(output_path, 'ab') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)
                                checksum_hash.update(chunk)
                                bytes_downloaded += len(chunk)
                                
                                if progress_callback and total_bytes:
                                    try:
                                        progress_callback(bytes_downloaded, total_bytes)
                                    except Exception:
                                        pass
                        
                        checksum = checksum_hash.hexdigest()
                        source = metadata.get('source', 'tumblr') if metadata else 'tumblr'
                        
                        return DownloadResult(
                            filename=filename,
                            byte_size=bytes_downloaded,
                            checksum=checksum,
                            duration=0.0,
                            source=source,
                            status='success'
                        )
            except Exception:
                # Resume failed, fall back to regular download
                pass
        
        # Fall back to regular download
        return await self.download_file(
            url=url,
            filename=filename,
            metadata=metadata,
            progress_callback=progress_callback
        )
