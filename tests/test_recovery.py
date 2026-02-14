"""
Tests for the media recovery module.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

import pytest

from tumblr_archiver.recovery import (
    MediaRecovery,
    RecoveryResult,
    RecoveryStatus,
)
from tumblr_archiver.wayback_client import (
    WaybackClient,
    Snapshot,
    SnapshotNotFoundError,
    WaybackError,
)
from tumblr_archiver.config import ArchiverConfig


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def config():
    """Create a test configuration."""
    return ArchiverConfig(
        blog_url="https://testblog.tumblr.com",
        output_dir=Path("/tmp/test"),
        wayback_enabled=True,
        wayback_max_snapshots=5,
    )


@pytest.fixture
def config_disabled():
    """Create a config with wayback disabled."""
    return ArchiverConfig(
        blog_url="https://testblog.tumblr.com",
        output_dir=Path("/tmp/test"),
        wayback_enabled=False,
    )


@pytest.fixture
def mock_wayback_client():
    """Create a mock WaybackClient."""
    return Mock(spec=WaybackClient)


@pytest.fixture
def sample_snapshot():
    """Create a sample snapshot for testing."""
    return Snapshot(
        urlkey="com,tumblr,media)/tumblr_abc123_1280.jpg",
        timestamp="20250101120000",
        original_url="https://64.media.tumblr.com/abc123/tumblr_abc123_1280.jpg",
        mimetype="image/jpeg",
        status_code="200",
        digest="ABC123DEF456",
        length="524288"
    )


@pytest.fixture
async def recovery_handler(mock_wayback_client, config):
    """Create a MediaRecovery handler with mocked client."""
    async with MediaRecovery(mock_wayback_client, config) as handler:
        yield handler


class TestRecoveryResult:
    """Tests for RecoveryResult dataclass."""
    
    def test_recovery_result_creation(self):
        """Test creating a RecoveryResult."""
        result = RecoveryResult(
            media_url="https://example.com/image.jpg",
            status=RecoveryStatus.SUCCESS,
            snapshot_url="https://web.archive.org/web/20250101/example.com/image.jpg",
            timestamp="20250101120000"
        )
        
        assert result.media_url == "https://example.com/image.jpg"
        assert result.status == RecoveryStatus.SUCCESS
        assert result.snapshot_url is not None
    
    def test_snapshot_datetime_parsing(self):
        """Test parsing snapshot timestamp to datetime."""
        result = RecoveryResult(
            media_url="https://example.com/image.jpg",
            status=RecoveryStatus.SUCCESS,
            timestamp="20250101120000"
        )
        
        dt = result.snapshot_datetime
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 1
        assert dt.day == 1
        assert dt.hour == 12
    
    def test_snapshot_datetime_invalid(self):
        """Test handling invalid timestamp."""
        result = RecoveryResult(
            media_url="https://example.com/image.jpg",
            status=RecoveryStatus.SUCCESS,
            timestamp="invalid"
        )
        
        assert result.snapshot_datetime is None


class TestMediaRecovery:
    """Tests for MediaRecovery class."""
    
    def test_initialization(self, mock_wayback_client, config):
        """Test MediaRecovery initialization."""
        recovery = MediaRecovery(mock_wayback_client, config)
        
        assert recovery.wayback_client == mock_wayback_client
        assert recovery.config == config
    
    @pytest.mark.asyncio
    async def test_context_manager(self, mock_wayback_client, config):
        """Test async context manager."""
        async with MediaRecovery(mock_wayback_client, config) as handler:
            assert handler._session is not None
        
        # Session should be closed after exit
        # (In real implementation, we'd check session.closed)
    
    @pytest.mark.asyncio
    async def test_recover_media_disabled(self, mock_wayback_client, config_disabled):
        """Test recovery when wayback is disabled."""
        async with MediaRecovery(mock_wayback_client, config_disabled) as handler:
            result = await handler.recover_media(
                media_url="https://media.tumblr.com/test.jpg",
                post_url="https://testblog.tumblr.com/post/123"
            )
            
            assert result.status == RecoveryStatus.SKIPPED
            assert "disabled" in result.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_recover_media_invalid_input(self, mock_wayback_client, config):
        """Test recovery with invalid input."""
        async with MediaRecovery(mock_wayback_client, config) as handler:
            with pytest.raises(ValueError):
                await handler.recover_media("", "")
    
    @pytest.mark.asyncio
    async def test_direct_recovery_success(
        self,
        mock_wayback_client,
        config,
        sample_snapshot,
        temp_dir
    ):
        """Test successful direct media recovery."""
        media_url = "https://64.media.tumblr.com/abc123/tumblr_abc123_1280.jpg"
        post_url = "https://testblog.tumblr.com/post/123"
        output_path = temp_dir / "image.jpg"
        
        # Mock successful snapshot retrieval
        mock_wayback_client.get_best_snapshot.return_value = sample_snapshot
        
        async with MediaRecovery(mock_wayback_client, config) as handler:
            # Mock the download method
            handler._download_snapshot_async = AsyncMock()
            
            result = await handler.recover_media(
                media_url=media_url,
                post_url=post_url,
                output_path=output_path
            )
            
            assert result.status == RecoveryStatus.SUCCESS
            assert result.strategy == "direct_media_url"
            assert result.snapshot_url == sample_snapshot.replay_url
            assert result.timestamp == sample_snapshot.timestamp
            assert result.file_size == sample_snapshot.file_size
            
            # Verify methods were called
            mock_wayback_client.get_best_snapshot.assert_called_once_with(
                media_url,
                "highest_quality"
            )
    
    @pytest.mark.asyncio
    async def test_direct_recovery_not_found(self, mock_wayback_client, config):
        """Test direct recovery when snapshot not found."""
        media_url = "https://64.media.tumblr.com/missing.jpg"
        post_url = "https://testblog.tumblr.com/post/123"
        
        # Mock snapshot not found
        mock_wayback_client.get_best_snapshot.side_effect = SnapshotNotFoundError(
            "No snapshots found"
        )
        mock_wayback_client.extract_media_from_archived_page.side_effect = (
            SnapshotNotFoundError("No archived post")
        )
        
        async with MediaRecovery(mock_wayback_client, config) as handler:
            result = await handler.recover_media(
                media_url=media_url,
                post_url=post_url
            )
            
            assert result.status == RecoveryStatus.NOT_FOUND
    
    @pytest.mark.asyncio
    async def test_post_page_extraction_success(
        self,
        mock_wayback_client,
        config,
        sample_snapshot
    ):
        """Test successful recovery via post page extraction."""
        media_url = "https://64.media.tumblr.com/abc123/tumblr_abc123_1280.jpg"
        post_url = "https://testblog.tumblr.com/post/123"
        
        # Mock: direct media fails, but post extraction succeeds
        mock_wayback_client.get_best_snapshot.side_effect = [
            SnapshotNotFoundError("Direct not found"),  # First call fails
            sample_snapshot  # Second call (after extraction) succeeds
        ]
        mock_wayback_client.extract_media_from_archived_page.return_value = [
            media_url
        ]
        
        async with MediaRecovery(mock_wayback_client, config) as handler:
            result = await handler.recover_media(
                media_url=media_url,
                post_url=post_url
            )
            
            assert result.status == RecoveryStatus.SUCCESS
            assert result.strategy == "post_page_extraction"
            mock_wayback_client.extract_media_from_archived_page.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_recovery_with_error(self, mock_wayback_client, config):
        """Test recovery when wayback client raises error."""
        media_url = "https://64.media.tumblr.com/test.jpg"
        post_url = "https://testblog.tumblr.com/post/123"
        
        # Mock wayback error
        mock_wayback_client.get_best_snapshot.side_effect = WaybackError(
            "API error"
        )
        mock_wayback_client.extract_media_from_archived_page.side_effect = (
            WaybackError("API error")
        )
        
        async with MediaRecovery(mock_wayback_client, config) as handler:
            result = await handler.recover_media(
                media_url=media_url,
                post_url=post_url
            )
            
            assert result.status == RecoveryStatus.ERROR
            assert "error" in result.error_message.lower()


class TestMediaMatching:
    """Tests for media URL matching functionality."""
    
    @pytest.mark.asyncio
    async def test_find_exact_match(self, mock_wayback_client, config):
        """Test finding exact URL match."""
        target = "https://64.media.tumblr.com/abc123/tumblr_abc123_1280.jpg"
        candidates = [
            "https://64.media.tumblr.com/def456/tumblr_def456_500.jpg",
            target,
            "https://64.media.tumblr.com/ghi789/tumblr_ghi789_1280.jpg",
        ]
        
        async with MediaRecovery(mock_wayback_client, config) as handler:
            result = handler._find_matching_media_url(target, candidates)
            assert result == target
    
    @pytest.mark.asyncio
    async def test_find_same_path_match(self, mock_wayback_client, config):
        """Test matching by same path (different domain)."""
        target = "https://64.media.tumblr.com/abc123/tumblr_abc123_1280.jpg"
        candidates = [
            "https://65.media.tumblr.com/abc123/tumblr_abc123_1280.jpg",
        ]
        
        async with MediaRecovery(mock_wayback_client, config) as handler:
            result = handler._find_matching_media_url(target, candidates)
            assert result == candidates[0]
    
    @pytest.mark.asyncio
    async def test_find_same_filename_match(self, mock_wayback_client, config):
        """Test matching by same filename."""
        target = "https://64.media.tumblr.com/abc123/tumblr_abc123_1280.jpg"
        candidates = [
            "https://64.media.tumblr.com/def456/tumblr_abc123_1280.jpg",
        ]
        
        async with MediaRecovery(mock_wayback_client, config) as handler:
            result = handler._find_matching_media_url(target, candidates)
            assert result == candidates[0]
    
    @pytest.mark.asyncio
    async def test_find_base_filename_match(self, mock_wayback_client, config):
        """Test matching by base filename (resolution variant)."""
        target = "https://64.media.tumblr.com/abc123/tumblr_abc123_1280.jpg"
        candidates = [
            "https://64.media.tumblr.com/abc123/tumblr_abc123_500.jpg",
        ]
        
        async with MediaRecovery(mock_wayback_client, config) as handler:
            result = handler._find_matching_media_url(target, candidates)
            assert result == candidates[0]
    
    @pytest.mark.asyncio
    async def test_no_match_found(self, mock_wayback_client, config):
        """Test when no match is found."""
        target = "https://64.media.tumblr.com/abc123/tumblr_abc123_1280.jpg"
        candidates = [
            "https://64.media.tumblr.com/def456/tumblr_def456_1280.jpg",
            "https://64.media.tumblr.com/ghi789/tumblr_ghi789_500.jpg",
        ]
        
        async with MediaRecovery(mock_wayback_client, config) as handler:
            result = handler._find_matching_media_url(target, candidates)
            assert result is None


class TestBaseFilenameExtraction:
    """Tests for base filename extraction."""
    
    @pytest.mark.asyncio
    async def test_extract_with_resolution(self, mock_wayback_client, config):
        """Test extracting base name from filename with resolution."""
        async with MediaRecovery(mock_wayback_client, config) as handler:
            result = handler._extract_base_filename("tumblr_abc123_1280.jpg")
            assert result == "tumblr_abc123"
    
    @pytest.mark.asyncio
    async def test_extract_without_resolution(self, mock_wayback_client, config):
        """Test extracting base name without resolution suffix."""
        async with MediaRecovery(mock_wayback_client, config) as handler:
            result = handler._extract_base_filename("tumblr_abc123.jpg")
            assert result == "tumblr_abc123"
    
    @pytest.mark.asyncio
    async def test_extract_empty_filename(self, mock_wayback_client, config):
        """Test with empty filename."""
        async with MediaRecovery(mock_wayback_client, config) as handler:
            result = handler._extract_base_filename("")
            assert result is None


class TestMultipleMediaRecovery:
    """Tests for recovering multiple media files."""
    
    @pytest.mark.asyncio
    async def test_recover_multiple_media(
        self,
        mock_wayback_client,
        config,
        sample_snapshot
    ):
        """Test recovering multiple media files concurrently."""
        media_items = [
            (
                "https://64.media.tumblr.com/abc123/tumblr_abc123_1280.jpg",
                "https://testblog.tumblr.com/post/123",
                None
            ),
            (
                "https://64.media.tumblr.com/def456/tumblr_def456_500.jpg",
                "https://testblog.tumblr.com/post/456",
                None
            ),
        ]
        
        # Mock successful recoveries
        mock_wayback_client.get_best_snapshot.return_value = sample_snapshot
        
        async with MediaRecovery(mock_wayback_client, config) as handler:
            results = await handler.recover_multiple_media(
                media_items,
                max_concurrent=2
            )
            
            assert len(results) == 2
            assert all(isinstance(r, RecoveryResult) for r in results)
    
    @pytest.mark.asyncio
    async def test_recover_multiple_with_errors(
        self,
        mock_wayback_client,
        config,
        sample_snapshot
    ):
        """Test that errors are converted to error results."""
        media_items = [
            (
                "https://64.media.tumblr.com/abc123/tumblr_abc123_1280.jpg",
                "https://testblog.tumblr.com/post/123",
                None
            ),
        ]
        
        # Mock error
        mock_wayback_client.get_best_snapshot.side_effect = Exception(
            "Unexpected error"
        )
        mock_wayback_client.extract_media_from_archived_page.side_effect = Exception(
            "Unexpected error"
        )
        
        async with MediaRecovery(mock_wayback_client, config) as handler:
            results = await handler.recover_multiple_media(
                media_items,
                max_concurrent=1
            )
            
            assert len(results) == 1
            assert results[0].status == RecoveryStatus.ERROR


class TestRecoveryStats:
    """Tests for recovery statistics calculation."""
    
    @pytest.mark.asyncio
    async def test_get_recovery_stats(self, mock_wayback_client, config):
        """Test calculating recovery statistics."""
        results = [
            RecoveryResult(
                media_url="url1",
                status=RecoveryStatus.SUCCESS
            ),
            RecoveryResult(
                media_url="url2",
                status=RecoveryStatus.SUCCESS
            ),
            RecoveryResult(
                media_url="url3",
                status=RecoveryStatus.NOT_FOUND
            ),
            RecoveryResult(
                media_url="url4",
                status=RecoveryStatus.ERROR
            ),
        ]
        
        async with MediaRecovery(mock_wayback_client, config) as handler:
            stats = handler.get_recovery_stats(results)
            
            assert stats["total"] == 4
            assert stats["successful"] == 2
            assert stats["not_found"] == 1
            assert stats["errors"] == 1
            assert stats["success_rate"] == 50.0
    
    @pytest.mark.asyncio
    async def test_get_recovery_stats_empty(self, mock_wayback_client, config):
        """Test statistics with empty results."""
        async with MediaRecovery(mock_wayback_client, config) as handler:
            stats = handler.get_recovery_stats([])
            
            assert stats["total"] == 0
            assert stats["successful"] == 0
            assert stats["success_rate"] == 0.0
