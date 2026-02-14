"""
Tests for the download manager.
"""

import asyncio
import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from tumblr_archiver.downloader import (
    DownloadError,
    DownloadManager,
    DownloadResult,
    IntegrityError,
    MediaNotFoundError,
    RateLimiter,
    RetryStrategy,
)


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create a temporary output directory."""
    output_dir = tmp_path / "downloads"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def rate_limiter():
    """Create a rate limiter for testing."""
    return RateLimiter(rate=10.0)


@pytest.fixture
def retry_strategy():
    """Create a retry strategy for testing."""
    return RetryStrategy(max_retries=2, base_backoff=0.1, max_backoff=1.0)


@pytest.fixture
def download_manager(temp_output_dir, rate_limiter, retry_strategy):
    """Create a download manager for testing."""
    return DownloadManager(
        output_dir=str(temp_output_dir),
        rate_limiter=rate_limiter,
        retry_strategy=retry_strategy,
        max_concurrent=3,
        timeout=30
    )


class TestRateLimiter:
    """Tests for RateLimiter."""
    
    @pytest.mark.asyncio
    async def test_acquire_single_token(self):
        """Test acquiring a single token."""
        limiter = RateLimiter(rate=10.0)
        
        # Should acquire immediately
        await limiter.acquire(1)
        assert limiter.tokens < limiter.max_tokens
    
    @pytest.mark.asyncio
    async def test_acquire_multiple_tokens(self):
        """Test acquiring multiple tokens."""
        limiter = RateLimiter(rate=10.0)
        
        # Acquire 5 tokens
        await limiter.acquire(5)
        assert limiter.tokens == pytest.approx(5.0, abs=0.1)
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test that rate limiting works."""
        limiter = RateLimiter(rate=5.0)  # 5 requests per second
        
        # Drain all tokens
        await limiter.acquire(5)
        
        # Next acquire should wait
        import time
        start = time.time()
        await limiter.acquire(1)
        elapsed = time.time() - start
        
        # Should have waited ~0.2 seconds (1/5)
        assert elapsed >= 0.15


class TestRetryStrategy:
    """Tests for RetryStrategy."""
    
    @pytest.mark.asyncio
    async def test_success_on_first_try(self):
        """Test successful execution on first attempt."""
        strategy = RetryStrategy(max_retries=3)
        
        async def successful_func():
            return "success"
        
        result = await strategy.execute(successful_func)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test retrying after failures."""
        strategy = RetryStrategy(max_retries=2, base_backoff=0.01)
        
        call_count = 0
        
        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise asyncio.TimeoutError("Timeout")
            return "success"
        
        result = await strategy.execute(failing_func)
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test that max retries are respected."""
        strategy = RetryStrategy(max_retries=2, base_backoff=0.01)
        
        async def always_fails():
            raise asyncio.TimeoutError("Always fails")
        
        with pytest.raises(DownloadError) as exc_info:
            await strategy.execute(always_fails)
        
        assert "Max retries" in str(exc_info.value)


class TestDownloadManager:
    """Tests for DownloadManager."""
    
    def test_initialization(self, download_manager, temp_output_dir):
        """Test download manager initialization."""
        assert download_manager.output_dir == temp_output_dir
        assert download_manager.rate_limiter is not None
        assert download_manager.retry_strategy is not None
    
    def test_generate_filename(self, download_manager):
        """Test filename generation."""
        url = "https://64.media.tumblr.com/abc123/tumblr_xyz_1280.jpg"
        post_id = "123456789"
        
        filename = download_manager.generate_filename(url, post_id, "image", 0)
        
        assert filename.startswith(f"{post_id}_0_")
        assert filename.endswith(".jpg")
    
    def test_generate_filename_no_extension(self, download_manager):
        """Test filename generation when URL has no extension."""
        url = "https://example.com/media/abc123"
        post_id = "123456789"
        
        filename = download_manager.generate_filename(url, post_id, "image", 0)
        
        assert filename.startswith(f"{post_id}_0_")
        assert filename.endswith(".jpg")  # Default for images
    
    def test_generate_filename_collision(self, download_manager, temp_output_dir):
        """Test filename collision handling."""
        url = "https://example.com/image.jpg"
        post_id = "123"
        
        # Create existing file
        first_filename = download_manager.generate_filename(url, post_id, "image", 0)
        (temp_output_dir / first_filename).touch()
        
        # Generate again - should have different name
        second_filename = download_manager.generate_filename(url, post_id, "image", 0)
        
        assert first_filename != second_filename
        assert "_1.jpg" in second_filename
    
    @pytest.mark.asyncio
    async def test_compute_checksum(self, download_manager, temp_output_dir):
        """Test checksum computation."""
        # Create test file
        test_file = temp_output_dir / "test.txt"
        content = b"Hello, World!"
        test_file.write_bytes(content)
        
        # Compute checksum
        checksum = await download_manager._compute_checksum(test_file)
        
        # Verify checksum
        expected = hashlib.sha256(content).hexdigest()
        assert checksum == expected
    
    def test_is_placeholder_empty_file(self, download_manager):
        """Test placeholder detection for empty files."""
        checksum = "abc123"
        size = 0
        
        assert download_manager._is_placeholder(checksum, size)
    
    def test_is_placeholder_known_checksum(self, download_manager):
        """Test placeholder detection for known checksums."""
        # Empty file checksum
        checksum = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        size = 100
        
        assert download_manager._is_placeholder(checksum, size)
    
    def test_is_placeholder_tiny_file(self, download_manager):
        """Test placeholder detection for tiny files."""
        checksum = "abc123"
        size = 10  # Very small
        
        assert download_manager._is_placeholder(checksum, size)
    
    def test_is_not_placeholder(self, download_manager):
        """Test that normal files are not detected as placeholders."""
        checksum = "abc123def456"
        size = 50000  # 50 KB
        
        assert not download_manager._is_placeholder(checksum, size)
    
    def test_verify_content_type_html(self, download_manager):
        """Test content type verification rejects HTML."""
        with pytest.raises(DownloadError) as exc_info:
            download_manager._verify_content_type(
                "text/html; charset=utf-8",
                "https://example.com/image.jpg"
            )
        
        assert "HTML" in str(exc_info.value)
    
    def test_verify_content_type_valid(self, download_manager):
        """Test content type verification allows valid types."""
        # Should not raise
        download_manager._verify_content_type("image/jpeg", "https://example.com/image.jpg")
        download_manager._verify_content_type("video/mp4", "https://example.com/video.mp4")
        download_manager._verify_content_type("application/octet-stream", "https://example.com/file")
    
    def test_verify_file_size_image_too_small(self, download_manager):
        """Test file size verification for images."""
        with pytest.raises(IntegrityError) as exc_info:
            download_manager._verify_file_size(50, "image/jpeg")
        
        assert "too small" in str(exc_info.value)
    
    def test_verify_file_size_video_too_small(self, download_manager):
        """Test file size verification for videos."""
        with pytest.raises(IntegrityError) as exc_info:
            download_manager._verify_file_size(500, "video/mp4")
        
        assert "too small" in str(exc_info.value)
    
    def test_verify_file_size_valid(self, download_manager):
        """Test file size verification allows valid sizes."""
        # Should not raise
        download_manager._verify_file_size(50000, "image/jpeg")
        download_manager._verify_file_size(1000000, "video/mp4")
    
    @pytest.mark.asyncio
    async def test_context_manager(self, temp_output_dir, rate_limiter, retry_strategy):
        """Test async context manager usage."""
        async with DownloadManager(
            output_dir=str(temp_output_dir),
            rate_limiter=rate_limiter,
            retry_strategy=retry_strategy
        ) as manager:
            assert manager._session is not None
            session = manager._session
        
        # Session should be closed and set to None after exiting context
        assert session.closed
        assert manager._session is None


class TestDownloadManagerIntegration:
    """Integration tests for download operations."""
    
    @pytest.mark.asyncio
    async def test_download_file_already_exists(self, download_manager, temp_output_dir):
        """Test skipping download when file exists with valid checksum."""
        # Create existing file
        filename = "test_existing.jpg"
        content = b"Existing file content"
        output_path = temp_output_dir / filename
        output_path.write_bytes(content)
        
        expected_checksum = hashlib.sha256(content).hexdigest()
        
        # Try to download (should skip)
        result = await download_manager.download_file(
            url="https://example.com/image.jpg",
            filename=filename,
            expected_checksum=expected_checksum,
            verify_size=False,
            verify_content_type=False
        )
        
        assert result.status == "success"
        assert result.checksum == expected_checksum
        assert result.byte_size == len(content)
    
    @pytest.mark.asyncio
    async def test_download_image(self, download_manager):
        """Test image download method."""
        url = "https://example.com/image.jpg"
        post_id = "123456"
        
        # Mock the download_file method
        expected_result = DownloadResult(
            filename="123456_0_abc123.jpg",
            byte_size=50000,
            checksum="abc123",
            duration=1.0,
            source="tumblr",
            status="success"
        )
        
        download_manager.download_file = AsyncMock(return_value=expected_result)
        
        result = await download_manager.download_image(url, post_id)
        
        assert result.status == "success"
        download_manager.download_file.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_download_video(self, download_manager):
        """Test video download method."""
        url = "https://example.com/video.mp4"
        post_id = "123456"
        
        # Mock the download_file method
        expected_result = DownloadResult(
            filename="123456_0_abc123.mp4",
            byte_size=5000000,
            checksum="abc123",
            duration=5.0,
            source="tumblr",
            status="success"
        )
        
        download_manager.download_file = AsyncMock(return_value=expected_result)
        
        result = await download_manager.download_video(url, post_id)
        
        assert result.status == "success"
        download_manager.download_file.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_download_gif(self, download_manager):
        """Test GIF download method."""
        url = "https://example.com/animation.gif"
        post_id = "123456"
        
        # Mock the download_file method
        expected_result = DownloadResult(
            filename="123456_0_abc123.gif",
            byte_size=250000,
            checksum="abc123",
            duration=2.0,
            source="tumblr",
            status="success"
        )
        
        download_manager.download_file = AsyncMock(return_value=expected_result)
        
        result = await download_manager.download_gif(url, post_id)
        
        assert result.status == "success"
        download_manager.download_file.assert_called_once()


class TestErrorHandling:
    """Tests for error handling."""
    
    @pytest.mark.asyncio
    async def test_media_not_found_error(self):
        """Test MediaNotFoundError exception."""
        error = MediaNotFoundError("Media not found: HTTP 404")
        assert "404" in str(error)
        assert isinstance(error, DownloadError)
    
    @pytest.mark.asyncio
    async def test_integrity_error(self):
        """Test IntegrityError exception."""
        error = IntegrityError("Checksum mismatch")
        assert "Checksum" in str(error)
        assert isinstance(error, DownloadError)


class TestDownloadResult:
    """Tests for DownloadResult dataclass."""
    
    def test_download_result_success(self):
        """Test successful download result."""
        result = DownloadResult(
            filename="test.jpg",
            byte_size=50000,
            checksum="abc123",
            duration=2.5,
            source="tumblr",
            status="success"
        )
        
        assert result.status == "success"
        assert result.error_message is None
        assert not result.media_missing_on_tumblr
    
    def test_download_result_missing(self):
        """Test missing media download result."""
        result = DownloadResult(
            filename="test.jpg",
            byte_size=0,
            checksum="",
            duration=1.0,
            source="tumblr",
            status="missing",
            error_message="Media not found: HTTP 404",
            media_missing_on_tumblr=True
        )
        
        assert result.status == "missing"
        assert result.media_missing_on_tumblr
        assert "404" in result.error_message
    
    def test_download_result_error(self):
        """Test error download result."""
        result = DownloadResult(
            filename="test.jpg",
            byte_size=0,
            checksum="",
            duration=0.5,
            source="tumblr",
            status="error",
            error_message="Connection timeout"
        )
        
        assert result.status == "error"
        assert result.error_message == "Connection timeout"
