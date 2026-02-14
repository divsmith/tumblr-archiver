"""Tests for orchestrator and worker pool."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from tumblr_archiver.config import ArchiverConfig
from tumblr_archiver.models import MediaItem, Post
from tumblr_archiver.orchestrator import ArchiveStats, Orchestrator
from tumblr_archiver.queue import MediaQueue
from tumblr_archiver.worker import DownloadWorker


@pytest.fixture
def sample_config(tmp_path):
    """Create a sample archiver configuration."""
    return ArchiverConfig(
        blog_name="testblog",
        output_dir=tmp_path / "archive",
        concurrency=3,
        rate_limit=10.0,
        max_retries=3,
        resume=True,
        dry_run=False,
    )


@pytest.fixture
def sample_media_item():
    """Create a sample media item."""
    return MediaItem(
        post_id="123456789",
        post_url="https://testblog.tumblr.com/post/123456789",
        timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        media_type="image",
        filename="123456789_001.jpg",
        original_url="https://64.media.tumblr.com/abc123/tumblr_xyz.jpg",
        retrieved_from="tumblr",
        status="missing",  # Not downloaded yet
    )


@pytest.fixture
def sample_post(sample_media_item):
    """Create a sample post with media."""
    return Post(
        post_id="123456789",
        post_url="https://testblog.tumblr.com/post/123456789",
        timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        is_reblog=False,
        media_items=[sample_media_item],
    )


class TestMediaQueue:
    """Tests for MediaQueue."""
    
    @pytest.mark.asyncio
    async def test_add_and_get_media(self, sample_media_item):
        """Test adding and getting media from queue."""
        queue = MediaQueue()
        
        await queue.add_media(sample_media_item)
        
        assert queue.qsize() == 1
        assert queue.total_items == 1
        
        media = await queue.get_media()
        
        assert media == sample_media_item
        assert media.filename == "123456789_001.jpg"
    
    @pytest.mark.asyncio
    async def test_mark_complete(self, sample_media_item):
        """Test marking task as complete."""
        queue = MediaQueue()
        
        await queue.add_media(sample_media_item)
        _media = await queue.get_media()
        
        assert queue.completed_items == 0
        
        queue.mark_complete()
        
        assert queue.completed_items == 1
    
    @pytest.mark.asyncio
    async def test_wait_completion(self, sample_media_item):
        """Test waiting for all tasks to complete."""
        queue = MediaQueue()
        
        # Add items
        for i in range(3):
            await queue.add_media(sample_media_item)
        
        # Process items in background
        async def process_items():
            for _ in range(3):
                _media = await queue.get_media()
                queue.mark_complete()
        
        # Start processing and wait for completion
        task = asyncio.create_task(process_items())
        await queue.wait_completion()
        await task
        
        assert queue.completed_items == 3
    
    @pytest.mark.asyncio
    async def test_sentinel_value(self):
        """Test adding and receiving sentinel value."""
        queue = MediaQueue()
        
        await queue.add_sentinel()
        
        sentinel = await queue.get_media()
        
        assert sentinel is None
    
    def test_queue_stats(self, sample_media_item):
        """Test queue statistics."""
        queue = MediaQueue()
        
        stats = queue.stats()
        
        assert stats["total"] == 0
        assert stats["completed"] == 0
        assert stats["pending"] == 0
        assert stats["qsize"] == 0
    
    @pytest.mark.asyncio
    async def test_pending_items(self, sample_media_item):
        """Test pending items tracking."""
        queue = MediaQueue()
        
        # Add items
        await queue.add_media(sample_media_item)
        await queue.add_media(sample_media_item)
        
        assert queue.pending_items == 2
        
        # Complete one
        await queue.get_media()
        queue.mark_complete()
        
        assert queue.pending_items == 1


class TestDownloadWorker:
    """Tests for DownloadWorker."""
    
    @pytest.mark.asyncio
    async def test_worker_processes_media(self, sample_media_item):
        """Test worker successfully processes media."""
        queue = MediaQueue()
        mock_downloader = Mock()
        mock_manifest_manager = Mock()
        
        # Setup mocks
        updated_media = sample_media_item.model_copy()
        updated_media.status = "downloaded"
        updated_media.byte_size = 1024
        updated_media.checksum = "a" * 64
        
        mock_downloader.download_media = AsyncMock(return_value=updated_media)
        mock_manifest_manager.update_media_item = AsyncMock(return_value=True)
        
        # Create worker
        worker = DownloadWorker(
            worker_id=1,
            queue=queue,
            downloader=mock_downloader,
            manifest_manager=mock_manifest_manager,
        )
        
        # Add media and sentinel
        await queue.add_media(sample_media_item)
        await queue.add_sentinel()
        
        # Run worker
        await worker.run()
        
        # Verify download was called
        mock_downloader.download_media.assert_called_once()
        mock_manifest_manager.update_media_item.assert_called_once()
        
        # Verify statistics
        assert worker.downloads_completed == 1
        assert worker.downloads_failed == 0
        assert worker.bytes_downloaded == 1024
    
    @pytest.mark.asyncio
    async def test_worker_handles_download_error(self, sample_media_item):
        """Test worker handles download errors gracefully."""
        queue = MediaQueue()
        mock_downloader = Mock()
        mock_manifest_manager = Mock()
        
        # Setup mocks to raise error
        from tumblr_archiver.downloader import DownloadError
        mock_downloader.download_media = AsyncMock(
            side_effect=DownloadError("Download failed")
        )
        mock_manifest_manager.update_media_item = AsyncMock(return_value=True)
        
        # Create worker
        worker = DownloadWorker(
            worker_id=1,
            queue=queue,
            downloader=mock_downloader,
            manifest_manager=mock_manifest_manager,
        )
        
        # Add media and sentinel
        await queue.add_media(sample_media_item)
        await queue.add_sentinel()
        
        # Run worker (should not crash)
        await worker.run()
        
        # Verify error was handled
        assert worker.downloads_completed == 0
        assert worker.downloads_failed == 1
        
        # Verify manifest was updated with error status
        mock_manifest_manager.update_media_item.assert_called()
        call_args = mock_manifest_manager.update_media_item.call_args[0][0]
        assert call_args.status == "error"
    
    @pytest.mark.asyncio
    async def test_worker_stops_on_sentinel(self, sample_media_item):
        """Test worker stops when receiving sentinel value."""
        queue = MediaQueue()
        mock_downloader = Mock()
        mock_manifest_manager = Mock()
        
        worker = DownloadWorker(
            worker_id=1,
            queue=queue,
            downloader=mock_downloader,
            manifest_manager=mock_manifest_manager,
        )
        
        # Add only sentinel (no media)
        await queue.add_sentinel()
        
        # Run worker
        await worker.run()
        
        # Verify no downloads attempted
        mock_downloader.download_media.assert_not_called()
        assert worker.downloads_completed == 0
    
    @pytest.mark.asyncio
    async def test_worker_progress_callback(self, sample_media_item):
        """Test worker calls progress callback."""
        queue = MediaQueue()
        mock_downloader = Mock()
        mock_manifest_manager = Mock()
        mock_callback = Mock()
        
        # Setup mocks
        updated_media = sample_media_item.model_copy()
        updated_media.status = "downloaded"
        
        mock_downloader.download_media = AsyncMock(return_value=updated_media)
        mock_manifest_manager.update_media_item = AsyncMock(return_value=True)
        
        # Create worker with callback
        worker = DownloadWorker(
            worker_id=1,
            queue=queue,
            downloader=mock_downloader,
            manifest_manager=mock_manifest_manager,
            progress_callback=mock_callback,
        )
        
        # Add media and sentinel
        await queue.add_media(sample_media_item)
        await queue.add_sentinel()
        
        # Run worker
        await worker.run()
        
        # Verify callback was called
        mock_callback.assert_called_once()
        assert "Worker-1" in str(mock_callback.call_args)
    
    def test_worker_stats(self):
        """Test worker statistics."""
        queue = MediaQueue()
        mock_downloader = Mock()
        mock_manifest_manager = Mock()
        
        worker = DownloadWorker(
            worker_id=1,
            queue=queue,
            downloader=mock_downloader,
            manifest_manager=mock_manifest_manager,
        )
        
        stats = worker.stats()
        
        assert stats["worker_id"] == 1
        assert stats["downloads_completed"] == 0
        assert stats["downloads_failed"] == 0
        assert stats["bytes_downloaded"] == 0


class TestOrchestrator:
    """Tests for Orchestrator."""
    
    @pytest.mark.asyncio
    async def test_orchestrator_full_workflow(self, sample_config, sample_post):
        """Test complete orchestration workflow with mocks."""
        orchestrator = Orchestrator(sample_config)
        
        # Mock all components
        with patch('tumblr_archiver.orchestrator.AsyncHTTPClient') as mock_http, \
             patch('tumblr_archiver.orchestrator.WaybackClient'), \
             patch('tumblr_archiver.orchestrator.TumblrScraper') as mock_scraper_cls, \
             patch('tumblr_archiver.orchestrator.MediaDownloader') as mock_downloader_cls, \
             patch('tumblr_archiver.orchestrator.ManifestManager') as mock_manifest_cls:
            
            # Setup mock scraper
            mock_scraper = Mock()
            mock_scraper.scrape_blog = AsyncMock(return_value=[sample_post])
            mock_scraper_cls.return_value = mock_scraper
            
            # Setup mock manifest manager
            mock_manifest = Mock()
            mock_manifest_manager = Mock()
            mock_manifest_manager.load = AsyncMock(return_value=mock_manifest)
            mock_manifest_manager.add_post = AsyncMock()
            mock_manifest_manager.update_media_item = AsyncMock(return_value=True)
            mock_manifest_cls.return_value = mock_manifest_manager
            mock_manifest.total_posts = 0
            mock_manifest.total_media = 0
            
            # Setup mock downloader
            mock_downloader = Mock()
            updated_media = sample_post.media_items[0].model_copy()
            updated_media.status = "downloaded"
            updated_media.byte_size = 1024
            updated_media.checksum = "a" * 64
            mock_downloader.download_media = AsyncMock(return_value=updated_media)
            mock_downloader_cls.return_value = mock_downloader
            
            # Setup HTTP client mock
            mock_http_instance = Mock()
            mock_http_instance.close = AsyncMock()
            mock_http.return_value = mock_http_instance
            
            # Run orchestrator
            stats = await orchestrator.run()
            
            # Verify stats
            assert stats.blog_name == "testblog"
            assert stats.total_posts == 1
            assert stats.total_media == 1
            assert stats.downloaded == 1
            assert stats.failed == 0
    
    @pytest.mark.asyncio
    async def test_orchestrator_no_posts(self, sample_config):
        """Test orchestrator with no posts found."""
        orchestrator = Orchestrator(sample_config)
        
        with patch('tumblr_archiver.orchestrator.AsyncHTTPClient') as mock_http, \
             patch('tumblr_archiver.orchestrator.WaybackClient'), \
             patch('tumblr_archiver.orchestrator.TumblrScraper') as mock_scraper_cls, \
             patch('tumblr_archiver.orchestrator.ManifestManager') as mock_manifest_cls:
            
            # Setup mock scraper with no posts
            mock_scraper = Mock()
            mock_scraper.scrape_blog = AsyncMock(return_value=[])
            mock_scraper_cls.return_value = mock_scraper
            
            # Setup mock manifest manager
            mock_manifest = Mock()
            mock_manifest_manager = Mock()
            mock_manifest_manager.load = AsyncMock(return_value=mock_manifest)
            mock_manifest_cls.return_value = mock_manifest_manager
            mock_manifest.total_posts = 0
            mock_manifest.total_media = 0
            
            # Setup HTTP client mock
            mock_http_instance = Mock()
            mock_http_instance.close = AsyncMock()
            mock_http.return_value = mock_http_instance
            
            # Run orchestrator
            stats = await orchestrator.run()
            
            # Verify stats
            assert stats.total_posts == 0
            assert stats.total_media == 0
            assert stats.downloaded == 0
    
    @pytest.mark.asyncio
    async def test_orchestrator_dry_run(self, sample_config, sample_post):
        """Test orchestrator in dry run mode."""
        sample_config.dry_run = True
        orchestrator = Orchestrator(sample_config)
        
        with patch('tumblr_archiver.orchestrator.AsyncHTTPClient') as mock_http, \
             patch('tumblr_archiver.orchestrator.WaybackClient'), \
             patch('tumblr_archiver.orchestrator.TumblrScraper') as mock_scraper_cls, \
             patch('tumblr_archiver.orchestrator.ManifestManager') as mock_manifest_cls:
            
            # Setup mock scraper (should not be called in dry run)
            mock_scraper = Mock()
            mock_scraper.scrape_blog = AsyncMock(return_value=[])
            mock_scraper_cls.return_value = mock_scraper
            
            # Setup mock manifest manager
            mock_manifest = Mock()
            mock_manifest_manager = Mock()
            mock_manifest_manager.load = AsyncMock(return_value=mock_manifest)
            mock_manifest_cls.return_value = mock_manifest_manager
            mock_manifest.total_posts = 0
            mock_manifest.total_media = 0
            
            # Setup HTTP client mock
            mock_http_instance = Mock()
            mock_http_instance.close = AsyncMock()
            mock_http.return_value = mock_http_instance
            
            # Run orchestrator
            stats = await orchestrator.run()
            
            # In dry run, no scraping should occur
            assert stats.downloaded == 0
    
    @pytest.mark.asyncio
    async def test_orchestrator_blog_not_found(self, sample_config):
        """Test orchestrator handles blog not found error."""
        from tumblr_archiver.scraper import BlogNotFoundError
        
        orchestrator = Orchestrator(sample_config)
        
        with patch('tumblr_archiver.orchestrator.AsyncHTTPClient') as mock_http, \
             patch('tumblr_archiver.orchestrator.WaybackClient'), \
             patch('tumblr_archiver.orchestrator.TumblrScraper') as mock_scraper_cls, \
             patch('tumblr_archiver.orchestrator.ManifestManager') as mock_manifest_cls:
            
            # Setup mock scraper to raise error
            mock_scraper = Mock()
            mock_scraper.scrape_blog = AsyncMock(
                side_effect=BlogNotFoundError("Blog not found")
            )
            mock_scraper_cls.return_value = mock_scraper
            
            # Setup mock manifest manager
            mock_manifest = Mock()
            mock_manifest_manager = Mock()
            mock_manifest_manager.load = AsyncMock(return_value=mock_manifest)
            mock_manifest_cls.return_value = mock_manifest_manager
            mock_manifest.total_posts = 0
            mock_manifest.total_media = 0
            
            # Setup HTTP client mock
            mock_http_instance = Mock()
            mock_http_instance.close = AsyncMock()
            mock_http.return_value = mock_http_instance
            
            # Should raise BlogNotFoundError
            with pytest.raises(BlogNotFoundError):
                await orchestrator.run()
    
    @pytest.mark.asyncio
    async def test_orchestrator_worker_pool(self, sample_config, sample_post):
        """Test orchestrator creates correct number of workers."""
        sample_config.concurrency = 5
        orchestrator = Orchestrator(sample_config)
        
        with patch('tumblr_archiver.orchestrator.AsyncHTTPClient') as mock_http, \
             patch('tumblr_archiver.orchestrator.WaybackClient'), \
             patch('tumblr_archiver.orchestrator.TumblrScraper') as mock_scraper_cls, \
             patch('tumblr_archiver.orchestrator.MediaDownloader') as mock_downloader_cls, \
             patch('tumblr_archiver.orchestrator.ManifestManager') as mock_manifest_cls:
            
            # Setup mocks
            mock_scraper = Mock()
            mock_scraper.scrape_blog = AsyncMock(return_value=[sample_post])
            mock_scraper_cls.return_value = mock_scraper
            
            mock_manifest = Mock()
            mock_manifest_manager = Mock()
            mock_manifest_manager.load = AsyncMock(return_value=mock_manifest)
            mock_manifest_manager.add_post = AsyncMock()
            mock_manifest_manager.update_media_item = AsyncMock(return_value=True)
            mock_manifest_cls.return_value = mock_manifest_manager
            mock_manifest.total_posts = 0
            mock_manifest.total_media = 0
            
            mock_downloader = Mock()
            updated_media = sample_post.media_items[0].model_copy()
            updated_media.status = "downloaded"
            mock_downloader.download_media = AsyncMock(return_value=updated_media)
            mock_downloader_cls.return_value = mock_downloader
            
            mock_http_instance = Mock()
            mock_http_instance.close = AsyncMock()
            mock_http.return_value = mock_http_instance
            
            # Run orchestrator
            await orchestrator.run()
            
            # Verify 5 workers were created
            assert len(orchestrator.workers) == 5
    
    def test_archive_stats_formatting(self):
        """Test ArchiveStats string formatting."""
        stats = ArchiveStats(
            blog_name="testblog",
            total_posts=10,
            total_media=25,
            downloaded=20,
            failed=2,
            skipped=3,
            bytes_downloaded=1024 * 1024 * 5,  # 5 MB
            duration_seconds=120.5,
            start_time=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 1, 10, 2, 0, tzinfo=timezone.utc),
        )
        
        stats_str = str(stats)
        
        # Verify key information is in string
        assert "testblog" in stats_str
        assert "10" in stats_str  # total posts
        assert "25" in stats_str  # total media
        assert "20" in stats_str  # downloaded
        assert "120.5" in stats_str  # duration
    
    @pytest.mark.asyncio
    async def test_orchestrator_resume_skips_downloaded(self, sample_config, sample_post):
        """Test orchestrator skips already downloaded media when resuming."""
        sample_config.resume = True
        orchestrator = Orchestrator(sample_config)
        
        # Mark media as already downloaded
        sample_post.media_items[0].status = "downloaded"
        
        with patch('tumblr_archiver.orchestrator.AsyncHTTPClient') as mock_http, \
             patch('tumblr_archiver.orchestrator.WaybackClient'), \
             patch('tumblr_archiver.orchestrator.TumblrScraper') as mock_scraper_cls, \
             patch('tumblr_archiver.orchestrator.ManifestManager') as mock_manifest_cls:
            
            # Setup mocks
            mock_scraper = Mock()
            mock_scraper.scrape_blog = AsyncMock(return_value=[sample_post])
            mock_scraper_cls.return_value = mock_scraper
            
            mock_manifest = Mock()
            mock_manifest_manager = Mock()
            mock_manifest_manager.load = AsyncMock(return_value=mock_manifest)
            mock_manifest_manager.add_post = AsyncMock()
            mock_manifest_cls.return_value = mock_manifest_manager
            mock_manifest.total_posts = 0
            mock_manifest.total_media = 0
            
            mock_http_instance = Mock()
            mock_http_instance.close = AsyncMock()
            mock_http.return_value = mock_http_instance
            
            # Run orchestrator
            stats = await orchestrator.run()
            
            # Verify media was skipped
            assert stats.skipped == 1
            assert stats.downloaded == 0
