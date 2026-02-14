"""
Orchestrator for coordinating the Tumblr archiving workflow.

This module provides the Orchestrator class that coordinates scraping,
downloading, and manifest management with concurrent workers.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

from .archive import WaybackClient
from .config import ArchiverConfig
from .deduplicator import FileDeduplicator
from .downloader import MediaDownloader
from .http_client import AsyncHTTPClient
from .manifest import ManifestManager
from .models import MediaItem, Post
from .queue import MediaQueue
from .scraper import BlogNotFoundError, TumblrScraper
from .worker import DownloadWorker

logger = logging.getLogger(__name__)


@dataclass
class ArchiveStats:
    """
    Statistics from an archive operation.
    
    Attributes:
        blog_name: Name of the blog archived
        total_posts: Total number of posts found
        total_media: Total number of media items found
        downloaded: Number of media items successfully downloaded
        failed: Number of media items that failed to download
        skipped: Number of media items skipped (already existed)
        bytes_downloaded: Total bytes downloaded
        duration_seconds: Total time taken in seconds
        start_time: When archiving started
        end_time: When archiving completed
    """
    blog_name: str
    total_posts: int
    total_media: int
    downloaded: int
    failed: int
    skipped: int
    bytes_downloaded: int
    duration_seconds: float
    start_time: datetime
    end_time: datetime
    
    def __str__(self) -> str:
        """Format statistics as a human-readable string."""
        return (
            f"\n{'=' * 60}\n"
            f"Archive Statistics for '{self.blog_name}'\n"
            f"{'=' * 60}\n"
            f"Posts found:       {self.total_posts}\n"
            f"Media items:       {self.total_media}\n"
            f"Downloaded:        {self.downloaded}\n"
            f"Failed:            {self.failed}\n"
            f"Skipped:           {self.skipped}\n"
            f"Bytes downloaded:  {self.bytes_downloaded:,} ({self._format_bytes(self.bytes_downloaded)})\n"
            f"Duration:          {self.duration_seconds:.2f} seconds\n"
            f"Start time:        {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"End time:          {self.end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"{'=' * 60}\n"
        )
    
    @staticmethod
    def _format_bytes(bytes: int) -> str:
        """Format bytes as human-readable string."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes < 1024.0:
                return f"{bytes:.2f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.2f} PB"


class OrchestratorError(Exception):
    """Exception raised when orchestration fails."""
    pass


class Orchestrator:
    """
    Orchestrates the complete Tumblr archiving workflow.
    
    Coordinates all components:
    - HTTP client for making requests
    - Scraper for extracting posts
    - Downloader for fetching media
    - Manifest manager for tracking progress
    - Worker pool for concurrent downloads
    - Queue for work distribution
    
    Features:
    - Full blog scraping with pagination
    - Concurrent downloads with configurable worker pool
    - Automatic retry and fallback to Internet Archive
    - Resume capability for interrupted downloads
    - Deduplication to avoid redundant downloads
    - Progress tracking and statistics
    - Graceful error handling
    
    Example:
        ```python
        config = ArchiverConfig(
            blog_name="example",
            output_dir=Path("archive"),
            concurrency=5,
            rate_limit=2.0
        )
        
        orchestrator = Orchestrator(config)
        stats = await orchestrator.run()
        
        print(f"Downloaded {stats.downloaded} items in {stats.duration_seconds}s")
        ```
    """
    
    def __init__(
        self,
        config: ArchiverConfig,
        progress_callback: Optional[Callable[[str, MediaItem], None]] = None
    ):
        """
        Initialize the orchestrator.
        
        Args:
            config: Archiver configuration
            progress_callback: Optional callback(message, media_item) for progress updates
        """
        self.config = config
        self.progress_callback = progress_callback
        
        # Components (initialized in run())
        self.http_client: Optional[AsyncHTTPClient] = None
        self.wayback_client: Optional[WaybackClient] = None
        self.scraper: Optional[TumblrScraper] = None
        self.downloader: Optional[MediaDownloader] = None
        self.manifest_manager: Optional[ManifestManager] = None
        self.deduplicator: Optional[FileDeduplicator] = None
        self.queue: Optional[MediaQueue] = None
        self.workers: List[DownloadWorker] = []
        
        logger.info(f"Orchestrator initialized for blog '{config.blog_name}'")
    
    async def run(self) -> ArchiveStats:
        """
        Run the complete archiving workflow.
        
        Workflow:
        1. Initialize all components
        2. Load or create manifest
        3. Scrape blog for posts
        4. Add posts to manifest
        5. Create download queue from media items
        6. Spawn worker pool
        7. Wait for all downloads to complete
        8. Collect and return statistics
        
        Returns:
            ArchiveStats with summary of the archiving operation
            
        Raises:
            BlogNotFoundError: If the blog doesn't exist
            OrchestratorError: If orchestration fails
            
        Example:
            ```python
            orchestrator = Orchestrator(config)
            stats = await orchestrator.run()
            print(stats)
            ```
        """
        start_time = datetime.now(timezone.utc)
        logger.info(f"Starting archive of blog '{self.config.blog_name}'")
        
        try:
            # Initialize components
            await self._initialize_components()
            
            # Load or create manifest
            await self._load_manifest()
            
            # Scrape blog for posts
            posts = await self._scrape_blog()
            
            if not posts:
                logger.warning(f"No posts found for blog '{self.config.blog_name}'")
                return self._create_stats(start_time, 0, 0, 0, 0, 0, 0)
            
            # Add posts to manifest
            await self._add_posts_to_manifest(posts)
            
            # Collect all media items
            media_items = self._collect_media_items(posts)
            
            if not media_items:
                logger.info("No media items to download")
                return self._create_stats(start_time, len(posts), 0, 0, 0, 0, 0)
            
            # Filter out already downloaded media if resuming
            media_to_download = await self._filter_downloaded_media(media_items)
            
            if not media_to_download:
                logger.info("All media items already downloaded")
                return self._create_stats(
                    start_time,
                    len(posts),
                    len(media_items),
                    0,
                    0,
                    len(media_items),
                    0
                )
            
            # Download media with worker pool
            downloaded, failed, bytes_downloaded = await self._download_media(media_to_download)
            
            # Calculate skipped items
            skipped = len(media_items) - len(media_to_download)
            
            # Create and return statistics
            stats = self._create_stats(
                start_time,
                len(posts),
                len(media_items),
                downloaded,
                failed,
                skipped,
                bytes_downloaded
            )
            
            logger.info(f"Archive complete:\n{stats}")
            return stats
        
        except BlogNotFoundError:
            logger.error(f"Blog '{self.config.blog_name}' not found")
            raise
        
        except Exception as e:
            logger.error(f"Orchestration failed: {e}", exc_info=True)
            raise OrchestratorError(f"Failed to archive blog: {e}") from e
        
        finally:
            # Clean up resources
            await self._cleanup()
    
    async def _initialize_components(self) -> None:
        """Initialize all archiver components."""
        logger.info("Initializing components")
        
        # Create HTTP client with rate limiting
        self.http_client = AsyncHTTPClient(
            rate_limit=self.config.rate_limit,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries
        )
        
        # Create Wayback Machine client
        self.wayback_client = WaybackClient(self.http_client)
        
        # Create scraper
        self.scraper = TumblrScraper(self.http_client, self.config)
        
        # Create deduplicator
        self.deduplicator = FileDeduplicator()
        
        # Create downloader
        self.downloader = MediaDownloader(
            http_client=self.http_client,
            wayback_client=self.wayback_client,
            output_dir=self.config.output_dir,
            deduplicator=self.deduplicator
        )
        
        # Create manifest manager
        self.manifest_manager = ManifestManager(self.config.output_dir)
        
        # Create download queue
        self.queue = MediaQueue()
        
        logger.info("All components initialized")
    
    async def _load_manifest(self) -> None:
        """Load existing manifest or create new one."""
        logger.info("Loading manifest")
        manifest = await self.manifest_manager.load()
        logger.info(
            f"Manifest loaded: {manifest.total_posts} posts, "
            f"{manifest.total_media} media items"
        )
    
    async def _scrape_blog(self) -> List[Post]:
        """
        Scrape all posts from the blog.
        
        Returns:
            List of Post objects
        """
        logger.info(f"Scraping blog '{self.config.blog_name}'")
        
        if self.config.dry_run:
            logger.info("Dry run mode: skipping actual scraping")
            return []
        
        posts = await self.scraper.scrape_blog(self.config.blog_name)
        
        logger.info(f"Found {len(posts)} posts")
        return posts
    
    async def _add_posts_to_manifest(self, posts: List[Post]) -> None:
        """
        Add posts to the manifest.
        
        Args:
            posts: List of posts to add
        """
        logger.info(f"Adding {len(posts)} posts to manifest")
        
        added = 0
        for post in posts:
            try:
                await self.manifest_manager.add_post(post)
                added += 1
            except ValueError as e:
                # Post already exists, skip
                logger.debug(f"Skipping duplicate post {post.post_id}: {e}")
        
        logger.info(f"Added {added} new posts to manifest")
    
    def _collect_media_items(self, posts: List[Post]) -> List[MediaItem]:
        """
        Collect all media items from posts.
        
        Args:
            posts: List of posts
            
        Returns:
            List of all media items
        """
        media_items = []
        for post in posts:
            media_items.extend(post.media_items)
        
        logger.info(f"Collected {len(media_items)} media items from posts")
        return media_items
    
    async def _filter_downloaded_media(self, media_items: List[MediaItem]) -> List[MediaItem]:
        """
        Filter out already downloaded media items.
        
        Args:
            media_items: All media items
            
        Returns:
            List of media items that need to be downloaded
        """
        if not self.config.resume:
            logger.info("Resume disabled, downloading all media")
            return media_items
        
        to_download = []
        for media in media_items:
            # Check if already downloaded
            if media.status in ["downloaded", "archived"]:
                logger.debug(f"Skipping already downloaded: {media.filename}")
                continue
            
            # Check if file exists on disk
            output_path = self.config.output_dir / self._get_media_subdir(media.media_type) / media.filename
            if output_path.exists():
                logger.debug(f"Skipping existing file: {media.filename}")
                continue
            
            to_download.append(media)
        
        logger.info(
            f"Filtered media: {len(to_download)} to download, "
            f"{len(media_items) - len(to_download)} already exist"
        )
        
        return to_download
    
    def _get_media_subdir(self, media_type: str) -> Path:
        """Get subdirectory for media type."""
        subdirs = {
            "image": "images",
            "gif": "gifs",
            "video": "videos"
        }
        return Path(subdirs.get(media_type, "other"))
    
    async def _download_media(self, media_items: List[MediaItem]) -> tuple[int, int, int]:
        """
        Download media items using worker pool.
        
        Args:
            media_items: Media items to download
            
        Returns:
            Tuple of (downloaded_count, failed_count, bytes_downloaded)
        """
        if self.config.dry_run:
            logger.info(f"Dry run mode: would download {len(media_items)} items")
            return 0, 0, 0
        
        logger.info(
            f"Starting download of {len(media_items)} items "
            f"with {self.config.concurrency} workers"
        )
        
        # Add all media items to queue
        for media in media_items:
            await self.queue.add_media(media)
        
        # Create and start workers
        worker_tasks = []
        for worker_id in range(self.config.concurrency):
            worker = DownloadWorker(
                worker_id=worker_id + 1,
                queue=self.queue,
                downloader=self.downloader,
                manifest_manager=self.manifest_manager,
                progress_callback=self.progress_callback
            )
            self.workers.append(worker)
            
            # Start worker task
            task = asyncio.create_task(worker.run())
            worker_tasks.append(task)
        
        # Add sentinel values to stop workers
        for _ in range(self.config.concurrency):
            await self.queue.add_sentinel()
        
        # Wait for all workers to complete
        logger.info("Waiting for workers to complete")
        await asyncio.gather(*worker_tasks, return_exceptions=True)
        
        # Collect statistics from workers
        total_downloaded = sum(w.downloads_completed for w in self.workers)
        total_failed = sum(w.downloads_failed for w in self.workers)
        total_bytes = sum(w.bytes_downloaded for w in self.workers)
        
        logger.info(
            f"All workers completed: {total_downloaded} downloaded, "
            f"{total_failed} failed, {total_bytes:,} bytes"
        )
        
        return total_downloaded, total_failed, total_bytes
    
    def _create_stats(
        self,
        start_time: datetime,
        total_posts: int,
        total_media: int,
        downloaded: int,
        failed: int,
        skipped: int,
        bytes_downloaded: int
    ) -> ArchiveStats:
        """Create statistics object."""
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
        return ArchiveStats(
            blog_name=self.config.blog_name,
            total_posts=total_posts,
            total_media=total_media,
            downloaded=downloaded,
            failed=failed,
            skipped=skipped,
            bytes_downloaded=bytes_downloaded,
            duration_seconds=duration,
            start_time=start_time,
            end_time=end_time
        )
    
    async def _cleanup(self) -> None:
        """Clean up resources."""
        logger.info("Cleaning up resources")
        
        if self.http_client:
            await self.http_client.close()
        
        logger.info("Cleanup complete")
