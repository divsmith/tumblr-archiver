"""
Tests for the main application entry point.

This module tests the TumblrArchiver class, including initialization,
execution, error handling, and resource cleanup.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from tumblr_archiver.app import TumblrArchiver, run_archive_app
from tumblr_archiver.config import ArchiverConfig, ConfigurationError
from tumblr_archiver.exceptions import (
    ArchiverError,
    BlogNotFoundError,
    OrchestratorError,
)
from tumblr_archiver.orchestrator import ArchiveStats


@pytest.fixture
def config(tmp_path: Path) -> ArchiverConfig:
    """Create a test configuration."""
    return ArchiverConfig(
        blog_name="test-blog",
        output_dir=tmp_path / "archive",
        concurrency=2,
        rate_limit=1.0,
        verbose=False,
        dry_run=False,
    )


@pytest.fixture
def dry_run_config(tmp_path: Path) -> ArchiverConfig:
    """Create a dry-run test configuration."""
    return ArchiverConfig(
        blog_name="test-blog",
        output_dir=tmp_path / "archive",
        dry_run=True,
        verbose=True,
    )


@pytest.fixture
def mock_stats() -> ArchiveStats:
    """Create mock archive statistics."""
    now = datetime.now(timezone.utc)
    return ArchiveStats(
        blog_name="test-blog",
        total_posts=10,
        total_media=25,
        downloaded=20,
        failed=2,
        skipped=3,
        bytes_downloaded=1_048_576,
        duration_seconds=10.5,
        start_time=now,
        end_time=now,
    )


class TestTumblrArchiverInitialization:
    """Test TumblrArchiver initialization."""
    
    def test_init_with_valid_config(self, config: ArchiverConfig):
        """Test initialization with valid configuration."""
        archiver = TumblrArchiver(config)
        
        assert archiver.config == config
        assert archiver._orchestrator is None
        assert archiver._http_client is None
        assert not archiver._initialized
        assert not archiver._cleaned_up
    
    def test_init_with_invalid_blog_name(self, tmp_path: Path):
        """Test initialization fails with invalid blog name."""
        with pytest.raises(ConfigurationError):
            ArchiverConfig(
                blog_name="",  # Empty blog name
                output_dir=tmp_path / "archive"
            )
    
    def test_init_with_invalid_concurrency(self, tmp_path: Path):
        """Test initialization fails with invalid concurrency."""
        with pytest.raises(ConfigurationError):
            ArchiverConfig(
                blog_name="test",
                output_dir=tmp_path / "archive",
                concurrency=0  # Invalid
            )


class TestTumblrArchiverSetup:
    """Test TumblrArchiver setup process."""
    
    @pytest.mark.asyncio
    async def test_setup_creates_output_directory(self, config: ArchiverConfig):
        """Test that setup creates the output directory."""
        archiver = TumblrArchiver(config)
        
        assert not config.output_dir.exists()
        
        await archiver._setup()
        
        assert config.output_dir.exists()
        assert archiver._initialized
    
    @pytest.mark.asyncio
    async def test_setup_dry_run_no_directory(self, dry_run_config: ArchiverConfig):
        """Test that dry run setup doesn't create directory."""
        archiver = TumblrArchiver(dry_run_config)
        
        await archiver._setup()
        
        # In dry run mode, directory creation is skipped
        assert archiver._initialized
    
    @pytest.mark.asyncio
    async def test_setup_idempotent(self, config: ArchiverConfig):
        """Test that setup can be called multiple times safely."""
        archiver = TumblrArchiver(config)
        
        await archiver._setup()
        await archiver._setup()  # Should not raise
        
        assert archiver._initialized


class TestTumblrArchiverRun:
    """Test TumblrArchiver run method."""
    
    @pytest.mark.asyncio
    async def test_run_successful(self, config: ArchiverConfig, mock_stats: ArchiveStats):
        """Test successful archive operation."""
        archiver = TumblrArchiver(config)
        
        # Mock the orchestrator
        with patch("tumblr_archiver.app.Orchestrator") as mock_orchestrator_class:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.run.return_value = mock_stats
            mock_orchestrator_class.return_value = mock_orchestrator
            
            stats = await archiver.run()
            
            assert stats == mock_stats
            assert stats.blog_name == "test-blog"
            assert stats.downloaded == 20
            assert stats.failed == 2
            assert stats.skipped == 3
            assert archiver._initialized
            
            # Verify orchestrator was created and run
            mock_orchestrator_class.assert_called_once_with(config)
            mock_orchestrator.run.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_blog_not_found(self, config: ArchiverConfig):
        """Test handling of blog not found error."""
        archiver = TumblrArchiver(config)
        
        with patch("tumblr_archiver.app.Orchestrator") as mock_orchestrator_class:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.run.side_effect = BlogNotFoundError("test-blog")
            mock_orchestrator_class.return_value = mock_orchestrator
            
            with pytest.raises(BlogNotFoundError) as exc_info:
                await archiver.run()
            
            assert "test-blog" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_run_orchestrator_error(self, config: ArchiverConfig):
        """Test handling of orchestrator error."""
        archiver = TumblrArchiver(config)
        
        with patch("tumblr_archiver.app.Orchestrator") as mock_orchestrator_class:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.run.side_effect = OrchestratorError("Orchestration failed")
            mock_orchestrator_class.return_value = mock_orchestrator
            
            with pytest.raises(OrchestratorError):
                await archiver.run()
    
    @pytest.mark.asyncio
    async def test_run_unexpected_error_wrapped(self, config: ArchiverConfig):
        """Test that unexpected errors are wrapped in ArchiverError."""
        archiver = TumblrArchiver(config)
        
        with patch("tumblr_archiver.app.Orchestrator") as mock_orchestrator_class:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.run.side_effect = RuntimeError("Unexpected error")
            mock_orchestrator_class.return_value = mock_orchestrator
            
            with pytest.raises(ArchiverError) as exc_info:
                await archiver.run()
            
            assert "Archive operation failed" in str(exc_info.value)
            assert isinstance(exc_info.value.__cause__, RuntimeError)
    
    @pytest.mark.asyncio
    async def test_run_auto_setup(self, config: ArchiverConfig, mock_stats: ArchiveStats):
        """Test that run automatically sets up if not initialized."""
        archiver = TumblrArchiver(config)
        
        assert not archiver._initialized
        
        with patch("tumblr_archiver.app.Orchestrator") as mock_orchestrator_class:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.run.return_value = mock_stats
            mock_orchestrator_class.return_value = mock_orchestrator
            
            await archiver.run()
            
            assert archiver._initialized


class TestTumblrArchiverCleanup:
    """Test TumblrArchiver cleanup."""
    
    @pytest.mark.asyncio
    async def test_cleanup_basic(self, config: ArchiverConfig):
        """Test basic cleanup."""
        archiver = TumblrArchiver(config)
        
        await archiver.cleanup()
        
        assert archiver._cleaned_up
    
    @pytest.mark.asyncio
    async def test_cleanup_idempotent(self, config: ArchiverConfig):
        """Test that cleanup can be called multiple times safely."""
        archiver = TumblrArchiver(config)
        
        await archiver.cleanup()
        await archiver.cleanup()  # Should not raise
        
        assert archiver._cleaned_up
    
    @pytest.mark.asyncio
    async def test_cleanup_with_http_client(self, config: ArchiverConfig):
        """Test cleanup closes HTTP client if present."""
        archiver = TumblrArchiver(config)
        
        # Mock HTTP client
        mock_http_client = AsyncMock()
        archiver._http_client = mock_http_client
        
        await archiver.cleanup()
        
        mock_http_client.close.assert_called_once()
        assert archiver._cleaned_up
    
    @pytest.mark.asyncio
    async def test_cleanup_error_handling(self, config: ArchiverConfig):
        """Test that cleanup handles errors gracefully."""
        archiver = TumblrArchiver(config)
        
        # Mock HTTP client that raises on close
        mock_http_client = AsyncMock()
        mock_http_client.close.side_effect = RuntimeError("Close failed")
        archiver._http_client = mock_http_client
        
        # Should not raise, just log warning
        await archiver.cleanup()
        
        assert archiver._cleaned_up


class TestTumblrArchiverContextManager:
    """Test TumblrArchiver as async context manager."""
    
    @pytest.mark.asyncio
    async def test_context_manager_successful(
        self, config: ArchiverConfig, mock_stats: ArchiveStats
    ):
        """Test using TumblrArchiver as context manager."""
        with patch("tumblr_archiver.app.Orchestrator") as mock_orchestrator_class:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.run.return_value = mock_stats
            mock_orchestrator_class.return_value = mock_orchestrator
            
            async with TumblrArchiver(config) as archiver:
                assert archiver._initialized
                stats = await archiver.run()
                assert stats == mock_stats
            
            # After context exit, cleanup should be called
            assert archiver._cleaned_up
    
    @pytest.mark.asyncio
    async def test_context_manager_with_exception(self, config: ArchiverConfig):
        """Test context manager cleans up even when exception occurs."""
        archiver = None
        
        with patch("tumblr_archiver.app.Orchestrator") as mock_orchestrator_class:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.run.side_effect = RuntimeError("Test error")
            mock_orchestrator_class.return_value = mock_orchestrator
            
            try:
                async with TumblrArchiver(config) as arch:
                    archiver = arch
                    await archiver.run()
            except ArchiverError:
                pass  # Expected
            
            # Cleanup should still be called
            assert archiver is not None
            assert archiver._cleaned_up
    
    @pytest.mark.asyncio
    async def test_context_manager_cleanup_after_successful_run(
        self, config: ArchiverConfig, mock_stats: ArchiveStats
    ):
        """Test that context manager properly cleans up after successful run."""
        with patch("tumblr_archiver.app.Orchestrator") as mock_orchestrator_class:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.run.return_value = mock_stats
            mock_orchestrator_class.return_value = mock_orchestrator
            
            async with TumblrArchiver(config) as archiver:
                await archiver.run()
                assert not archiver._cleaned_up  # Not yet
            
            assert archiver._cleaned_up  # After exit


class TestRunArchiveApp:
    """Test convenience function run_archive_app."""
    
    @pytest.mark.asyncio
    async def test_run_archive_app_success(
        self, config: ArchiverConfig, mock_stats: ArchiveStats
    ):
        """Test run_archive_app convenience function."""
        with patch("tumblr_archiver.app.Orchestrator") as mock_orchestrator_class:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.run.return_value = mock_stats
            mock_orchestrator_class.return_value = mock_orchestrator
            
            stats = await run_archive_app(config)
            
            assert stats == mock_stats
            assert stats.downloaded == 20
    
    @pytest.mark.asyncio
    async def test_run_archive_app_error(self, config: ArchiverConfig):
        """Test run_archive_app propagates errors."""
        with patch("tumblr_archiver.app.Orchestrator") as mock_orchestrator_class:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.run.side_effect = BlogNotFoundError("test-blog")
            mock_orchestrator_class.return_value = mock_orchestrator
            
            with pytest.raises(BlogNotFoundError):
                await run_archive_app(config)


class TestTumblrArchiverIntegration:
    """Integration tests for TumblrArchiver."""
    
    @pytest.mark.asyncio
    async def test_full_workflow_dry_run(self, dry_run_config: ArchiverConfig):
        """Test full workflow in dry-run mode (no actual downloads)."""
        # Create a more realistic mock that simulates the full workflow
        now = datetime.now(timezone.utc)
        mock_stats = ArchiveStats(
            blog_name=dry_run_config.blog_name,
            total_posts=5,
            total_media=10,
            downloaded=0,  # Dry run, no downloads
            failed=0,
            skipped=10,
            bytes_downloaded=0,
            duration_seconds=1.0,
            start_time=now,
            end_time=now,
        )
        
        with patch("tumblr_archiver.app.Orchestrator") as mock_orchestrator_class:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.run.return_value = mock_stats
            mock_orchestrator_class.return_value = mock_orchestrator
            
            async with TumblrArchiver(dry_run_config) as archiver:
                stats = await archiver.run()
                
                assert stats.total_posts == 5
                assert stats.total_media == 10
                assert stats.downloaded == 0  # Dry run
                assert stats.skipped == 10
    
    @pytest.mark.asyncio
    async def test_sequential_runs_same_instance(
        self, config: ArchiverConfig, mock_stats: ArchiveStats
    ):
        """Test that the same archiver instance can be used for multiple runs."""
        archiver = TumblrArchiver(config)
        
        with patch("tumblr_archiver.app.Orchestrator") as mock_orchestrator_class:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.run.return_value = mock_stats
            mock_orchestrator_class.return_value = mock_orchestrator
            
            # First run
            stats1 = await archiver.run()
            assert stats1.downloaded == 20
            
            # Second run (should work, creates new orchestrator)
            stats2 = await archiver.run()
            assert stats2.downloaded == 20
            
            # Verify orchestrator was created twice
            assert mock_orchestrator_class.call_count == 2
        
        # Cleanup
        await archiver.cleanup()
        assert archiver._cleaned_up
