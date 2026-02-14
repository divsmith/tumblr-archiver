"""
Tumblr Archiver - Main orchestrator module.

This module provides the TumblrArchiver class, which coordinates all components
to archive a Tumblr blog's media content with comprehensive error handling,
recovery capabilities, and progress tracking.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from urllib.parse import urlparse

from .config import ArchiverConfig
from .downloader import DownloadManager, DownloadResult, MediaNotFoundError
from .manifest import ManifestManager, MediaEntry
from .tumblr_api import TumblrAPIClient, extract_media_from_post, MediaInfo, TumblrAPIError
from .wayback_client import WaybackClient, SnapshotNotFoundError, WaybackError


# Set up logging
logger = logging.getLogger(__name__)


class ArchiverError(Exception):
    """Base exception for archiver errors."""
    pass


@dataclass
class ArchiveStatistics:
    """Statistics for an archive operation."""
    total_posts: int = 0
    total_media: int = 0
    media_downloaded: int = 0
    media_skipped: int = 0
    media_recovered: int = 0
    media_failed: int = 0
    media_missing: int = 0
    bytes_downloaded: int = 0
    posts_processed: int = 0
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert statistics to dictionary."""
        return {
            'total_posts': self.total_posts,
            'total_media': self.total_media,
            'media_downloaded': self.media_downloaded,
            'media_skipped': self.media_skipped,
            'media_recovered': self.media_recovered,
            'media_failed': self.media_failed,
            'media_missing': self.media_missing,
            'bytes_downloaded': self.bytes_downloaded,
            'posts_processed': self.posts_processed,
            'error_count': len(self.errors),
        }


@dataclass
class ArchiveResult:
    """Result of an archive operation."""
    blog_name: str
    blog_url: str
    success: bool
    statistics: ArchiveStatistics
    manifest_path: Path
    output_dir: Path
    start_time: datetime
    end_time: datetime
    error_message: Optional[str] = None
    
    @property
    def duration_seconds(self) -> float:
        """Calculate duration in seconds."""
        return (self.end_time - self.start_time).total_seconds()
    
    def __str__(self) -> str:
        """Human-readable summary."""
        stats = self.statistics
        duration = self.duration_seconds
        
        lines = [
            f"\n{'='*60}",
            f"Archive {'Completed' if self.success else 'Failed'}: {self.blog_name}",
            f"{'='*60}",
            f"Blog URL: {self.blog_url}",
            f"Output Directory: {self.output_dir}",
            f"Manifest: {self.manifest_path}",
            f"Duration: {duration:.2f}s",
            f"",
            f"Statistics:",
            f"  Posts Processed: {stats.posts_processed}/{stats.total_posts}",
            f"  Total Media: {stats.total_media}",
            f"  Downloaded: {stats.media_downloaded}",
            f"  Recovered (Wayback): {stats.media_recovered}",
            f"  Skipped (Already): {stats.media_skipped}",
            f"  Failed: {stats.media_failed}",
            f"  Missing: {stats.media_missing}",
            f"  Total Bytes: {stats.bytes_downloaded:,}",
        ]
        
        if not self.success and self.error_message:
            lines.append(f"\nError: {self.error_message}")
        
        if stats.errors:
            lines.append(f"\nErrors Encountered: {len(stats.errors)}")
            for idx, err in enumerate(stats.errors[:5], 1):
                lines.append(f"  {idx}. {err}")
            if len(stats.errors) > 5:
                lines.append(f"  ... and {len(stats.errors) - 5} more")
        
        lines.append(f"{'='*60}\n")
        return '\n'.join(lines)


class TumblrArchiver:
    """
    Main orchestrator for archiving Tumblr blog content.
    
    Coordinates all components (API client, download manager, manifest, wayback)
    to archive a blog's media with resume support, recovery, and progress tracking.
    """
    
    def __init__(self, config: ArchiverConfig):
        """
        Initialize the archiver with configuration.
        
        Args:
            config: ArchiverConfig instance with all settings
            
        Raises:
            ArchiverError: If configuration is invalid or clients can't be initialized
        """
        self.config = config
        self.statistics = ArchiveStatistics()
        
        # Validate configuration
        self._validate_config()
        
        # Initialize Tumblr API client
        if not self.config.tumblr_api_key:
            raise ArchiverError("Tumblr API key is required")
        
        self.api_client = TumblrAPIClient(
            api_key=self.config.tumblr_api_key,
            oauth_token=self.config.oauth_token,
            oauth_token_secret=None,  # Not using OAuth secrets for now
            timeout=30
        )
        
        # Parse blog identifier from URL
        self.blog_identifier = self._extract_blog_identifier(self.config.blog_url)
        
        # Set up output directory
        self.output_dir = Path(self.config.output_dir) / self.blog_identifier
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize manifest manager
        manifest_path = self.output_dir / "manifest.json"
        self.manifest = ManifestManager(manifest_path)
        
        # Initialize Wayback client if enabled
        self.wayback_client = None
        if self.config.wayback_enabled and self.config.recover_removed_media:
            self.wayback_client = WaybackClient(
                user_agent="TumblrArchiver/1.0",
                timeout=30,
                max_retries=self.config.max_retries
            )
        
        # Download manager will be initialized in async context
        self.download_manager: Optional[DownloadManager] = None
        
        # Progress tracking
        self.progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        
        logger.info(f"Tumblr Archiver initialized for blog: {self.blog_identifier}")
    
    def _validate_config(self):
        """Validate configuration settings."""
        if not self.config.blog_url:
            raise ArchiverError("blog_url is required")
        
        if not self.config.output_dir:
            raise ArchiverError("output_dir is required")
        
        if self.config.concurrency < 1:
            raise ArchiverError("concurrency must be at least 1")
        
        if self.config.rate_limit <= 0:
            raise ArchiverError("rate_limit must be positive")
    
    def _extract_blog_identifier(self, blog_url: str) -> str:
        """
        Extract blog identifier from URL or return as-is.
        
        Args:
            blog_url: Blog URL or identifier (e.g., 'example.tumblr.com' or 'example')
            
        Returns:
            Blog identifier suitable for API calls
        """
        # Remove protocol if present
        url = blog_url.lower().strip()
        if url.startswith(('http://', 'https://')):
            parsed = urlparse(url)
            hostname = parsed.hostname or parsed.path.split('/')[0]
            return hostname
        
        # Add .tumblr.com if not present and no domain extension
        if '.' not in url:
            return f"{url}.tumblr.com"
        
        return url
    
    def set_progress_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        Set a callback for progress updates.
        
        Args:
            callback: Function that receives progress dict with keys:
                     'event', 'current', 'total', 'message', etc.
        """
        self.progress_callback = callback
    
    def _report_progress(self, event: str, **kwargs):
        """Send progress update to callback if set."""
        if self.progress_callback:
            try:
                progress_data = {'event': event, **kwargs}
                self.progress_callback(progress_data)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")
    
    async def archive_blog(self) -> ArchiveResult:
        """
        Archive all media from the configured blog.
        
        This is the main entry point that orchestrates the entire archiving process:
        1. Fetch blog information
        2. Load or initialize manifest
        3. Fetch all posts from the blog
        4. Extract and download media from each post
        5. Handle missing media with Wayback Machine recovery
        6. Update manifest with results
        7. Return comprehensive results
        
        Returns:
            ArchiveResult with statistics and outcome
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            logger.info(f"Starting archive of blog: {self.blog_identifier}")
            self._report_progress('start', blog=self.blog_identifier)
            
            # Initialize download manager in async context
            async with self._create_download_manager() as download_manager:
                self.download_manager = download_manager
                
                # Step 1: Fetch blog information
                blog_info = await self._fetch_blog_info()
                
                # Step 2: Load or initialize manifest
                self._initialize_manifest(blog_info)
                
                # Step 3: Fetch all posts
                posts = await self._fetch_all_posts()
                
                # Step 4: Process posts and download media
                await self._process_posts(posts)
                
                # Step 5: Save final manifest
                self.manifest.save(force=True)
                
            # Generate result
            end_time = datetime.now(timezone.utc)
            result = ArchiveResult(
                blog_name=blog_info['name'],
                blog_url=blog_info['url'],
                success=True,
                statistics=self.statistics,
                manifest_path=Path(self.manifest.manifest_path),
                output_dir=self.output_dir,
                start_time=start_time,
                end_time=end_time
            )
            
            logger.info(f"Archive completed successfully: {self.blog_identifier}")
            self._report_progress('complete', result=result.to_dict() if hasattr(result, 'to_dict') else str(result))
            
            return result
            
        except Exception as e:
            end_time = datetime.now(timezone.utc)
            error_message = f"Archive failed: {str(e)}"
            logger.error(error_message, exc_info=True)
            self.statistics.errors.append(error_message)
            
            result = ArchiveResult(
                blog_name=self.blog_identifier,
                blog_url=self.config.blog_url,
                success=False,
                statistics=self.statistics,
                manifest_path=Path(self.manifest.manifest_path),
                output_dir=self.output_dir,
                start_time=start_time,
                end_time=end_time,
                error_message=error_message
            )
            
            self._report_progress('error', error=error_message)
            
            return result
    
    def _create_download_manager(self) -> DownloadManager:
        """Create and return download manager with proper configuration."""
        return DownloadManager(
            output_dir=str(self.output_dir),
            max_concurrent=self.config.concurrency,
            timeout=300
        )
    
    async def _fetch_blog_info(self) -> Dict[str, Any]:
        """Fetch blog information from Tumblr API."""
        logger.info("Fetching blog information...")
        self._report_progress('fetch_blog_info', blog=self.blog_identifier)
        
        try:
            # Use asyncio to run sync API call in executor
            blog_info = await asyncio.get_event_loop().run_in_executor(
                None,
                self.api_client.get_blog_info,
                self.blog_identifier
            )
            
            logger.info(
                f"Blog: {blog_info.get('name')} - "
                f"{blog_info.get('total_posts', 0)} posts"
            )
            
            return blog_info
            
        except TumblrAPIError as e:
            raise ArchiverError(f"Failed to fetch blog info: {e}")
    
    def _initialize_manifest(self, blog_info: Dict[str, Any]):
        """Load existing manifest or initialize new one."""
        logger.info("Loading manifest...")
        self._report_progress('load_manifest')
        
        self.manifest.load()
        
        # Update manifest metadata if new or blog info changed
        if not self.manifest.data.get('blog_name') or self.manifest.data['blog_name'] != blog_info['name']:
            self.manifest.data['blog_name'] = blog_info['name']
            self.manifest.data['blog_url'] = blog_info['url']
            self.manifest.data['total_posts'] = blog_info.get('total_posts', 0)
            self.manifest._modified = True
        
        self.statistics.total_posts = blog_info.get('total_posts', 0)
        
        logger.info(f"Manifest loaded: {len(self.manifest.data.get('media', []))} existing media entries")
    
    async def _fetch_all_posts(self) -> List[Dict[str, Any]]:
        """Fetch all posts from the blog with pagination."""
        logger.info("Fetching posts...")
        self._report_progress('fetch_posts', current=0, total=self.statistics.total_posts)
        
        posts = []
        
        def progress_callback(current: int, total: int):
            """Handle pagination progress."""
            logger.info(f"Fetching posts: {current}/{total}")
            self._report_progress('fetch_posts', current=current, total=total)
        
        try:
            # Run sync API call in executor
            posts = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.api_client.get_all_posts(
                    self.blog_identifier,
                    callback=progress_callback
                )
            )
            
            logger.info(f"Fetched {len(posts)} posts")
            return posts
            
        except TumblrAPIError as e:
            raise ArchiverError(f"Failed to fetch posts: {e}")
    
    async def _process_posts(self, posts: List[Dict[str, Any]]):
        """
        Process all posts and download their media.
        
        Args:
            posts: List of post dictionaries from Tumblr API
        """
        logger.info(f"Processing {len(posts)} posts...")
        
        for idx, post in enumerate(posts, 1):
            try:
                await self._process_single_post(post, idx, len(posts))
                self.statistics.posts_processed += 1
                
                # Periodically save manifest
                if idx % 50 == 0:
                    self.manifest.save()
                    logger.info(f"Progress saved at post {idx}/{len(posts)}")
                
            except Exception as e:
                error_msg = f"Error processing post {post.get('id', 'unknown')}: {e}"
                logger.error(error_msg)
                self.statistics.errors.append(error_msg)
        
        logger.info(f"Finished processing {len(posts)} posts")
    
    async def _process_single_post(self, post: Dict[str, Any], post_index: int, total_posts: int):
        """
        Process a single post and download its media.
        
        Args:
            post: Post dictionary from Tumblr API
            post_index: Current post index (1-based)
            total_posts: Total number of posts
        """
        post_id = str(post.get('id', ''))
        post_url = post.get('post_url', '')
        post_timestamp = post.get('timestamp', 0)
        
        if not post_id:
            logger.warning("Skipping post without ID")
            return
        
        # Extract media from post
        media_list = extract_media_from_post(post)
        
        if not media_list:
            logger.debug(f"Post {post_id} has no media")
            return
        
        logger.info(f"Processing post {post_index}/{total_posts}: {post_id} ({len(media_list)} media)")
        self._report_progress(
            'process_post',
            post_index=post_index,
            total_posts=total_posts,
            post_id=post_id,
            media_count=len(media_list)
        )
        
        # Update total media count
        self.statistics.total_media += len(media_list)
        
        # Process each media item
        for media_index, media_info in enumerate(media_list):
            await self._process_media_item(
                post_id,
                post_url,
                post_timestamp,
                media_info,
                media_index
            )
    
    async def _process_media_item(
        self,
        post_id: str,
        post_url: str,
        post_timestamp: int,
        media_info: MediaInfo,
        media_index: int
    ):
        """
        Process and download a single media item.
        
        Args:
            post_id: Post ID
            post_url: Post URL
            post_timestamp: Post timestamp
            media_info: MediaInfo object with URLs and metadata
            media_index: Index of media within the post
        """
        # Get the best URL (usually first one is highest quality)
        url = media_info.urls[0] if media_info.urls else None
        if not url:
            logger.warning(f"Media item has no URLs in post {post_id}")
            return
        
        # Generate filename
        filename = self.download_manager.generate_filename(
            url=url,
            post_id=post_id,
            media_type=media_info.media_type,
            index=media_index
        )
        
        file_path = self.output_dir / filename
        
        # Check if already downloaded (resume support)
        if self.config.resume and self.manifest.is_downloaded(
            post_id=post_id,
            filename=filename,
            file_path=file_path,
            verify_checksum=True
        ):
            logger.debug(f"Skipping already downloaded: {filename}")
            self.statistics.media_skipped += 1
            return
        
        # Check if dry run
        if self.config.dry_run:
            logger.info(f"[DRY RUN] Would download: {filename} from {url}")
            return
        
        # Download the media
        download_result = await self._download_media_with_recovery(
            url=url,
            filename=filename,
            media_info=media_info
        )
        
        # Update manifest with result
        await self._update_manifest_for_media(
            post_id=post_id,
            post_url=post_url,
            post_timestamp=post_timestamp,
            media_info=media_info,
            filename=filename,
            download_result=download_result
        )
        
        # Update statistics
        self._update_statistics(download_result)
    
    async def _download_media_with_recovery(
        self,
        url: str,
        filename: str,
        media_info: MediaInfo
    ) -> DownloadResult:
        """
        Download media with Wayback Machine recovery fallback.
        
        Args:
            url: Media URL
            filename: Target filename
            media_info: MediaInfo object
            
        Returns:
            DownloadResult
        """
        # First attempt: Tumblr direct download
        logger.debug(f"Downloading from Tumblr: {filename}")
        
        download_result = await self.download_manager.download_file(
            url=url,
            filename=filename,
            metadata={'source': 'tumblr'},
            verify_size=True,
            verify_content_type=True
        )
        
        # If download succeeded, return result
        if download_result.status == 'success':
            logger.info(f"Downloaded successfully: {filename}")
            return download_result
        
        # If media is missing and recovery is enabled, try Wayback Machine
        if (
            download_result.media_missing_on_tumblr
            and self.wayback_client
            and self.config.recover_removed_media
        ):
            logger.info(f"Media missing on Tumblr, attempting Wayback recovery: {url}")
            
            try:
                recovery_result = await self._recover_from_wayback(
                    url=url,
                    filename=filename
                )
                
                if recovery_result.status == 'success':
                    logger.info(f"Recovered from Wayback Machine: {filename}")
                    return recovery_result
                
            except Exception as e:
                logger.warning(f"Wayback recovery failed for {url}: {e}")
        
        # Return original failed result
        return download_result
    
    async def _recover_from_wayback(
        self,
        url: str,
        filename: str
    ) -> DownloadResult:
        """
        Attempt to recover media from Wayback Machine.
        
        Args:
            url: Original media URL
            filename: Target filename
            
        Returns:
            DownloadResult
            
        Raises:
            MediaNotFoundError: If recovery fails
        """
        try:
            # Run sync Wayback calls in executor
            snapshot = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.wayback_client.get_best_snapshot(
                    url,
                    prefer="highest_quality"
                )
            )
            
            logger.info(f"Found Wayback snapshot from {snapshot.timestamp}: {url}")
            
            # Download from snapshot
            download_result = await self.download_manager.download_file(
                url=snapshot.replay_url,
                filename=filename,
                metadata={
                    'source': 'internet_archive',
                    'snapshot_timestamp': snapshot.timestamp,
                    'snapshot_url': snapshot.replay_url
                },
                verify_size=True,
                verify_content_type=False  # Wayback may have different content-type
            )
            
            # Mark as recovered
            if download_result.status == 'success':
                download_result.source = 'internet_archive'
            
            return download_result
            
        except SnapshotNotFoundError:
            raise MediaNotFoundError(f"No Wayback snapshots found for {url}")
        except Exception as e:
            raise MediaNotFoundError(f"Wayback recovery failed: {e}")
    
    async def _update_manifest_for_media(
        self,
        post_id: str,
        post_url: str,
        post_timestamp: int,
        media_info: MediaInfo,
        filename: str,
        download_result: DownloadResult
    ):
        """
        Update manifest with media download result.
        
        Args:
            post_id: Post ID
            post_url: Post URL
            post_timestamp: Post timestamp
            media_info: MediaInfo object
            filename: Downloaded filename
            download_result: DownloadResult object
        """
        # Determine status
        status_map = {
            'success': 'downloaded',
            'missing': 'missing',
            'error': 'failed'
        }
        status = status_map.get(download_result.status, 'failed')
        
        # Create media entry
        media_entry: MediaEntry = {
            'post_id': post_id,
            'post_url': post_url,
            'timestamp': post_timestamp,
            'media_type': media_info.media_type,
            'filename': filename,
            'byte_size': download_result.byte_size,
            'checksum': f"sha256:{download_result.checksum}" if download_result.checksum else '',
            'original_url': media_info.urls[0] if media_info.urls else '',
            'api_media_urls': media_info.urls,
            'media_missing_on_tumblr': download_result.media_missing_on_tumblr,
            'retrieved_from': download_result.source,
            'archive_snapshot_url': '',
            'archive_snapshot_timestamp': '',
            'status': status,
            'notes': download_result.error_message or ''
        }
        
        # Add or update manifest entry
        existing = self.manifest.get_media(post_id, filename)
        if existing:
            self.manifest.update_media(post_id, filename, media_entry)
        else:
            self.manifest.add_media(media_entry)
    
    def _update_statistics(self, download_result: DownloadResult):
        """Update statistics based on download result."""
        if download_result.status == 'success':
            if download_result.source == 'internet_archive':
                self.statistics.media_recovered += 1
            else:
                self.statistics.media_downloaded += 1
            self.statistics.bytes_downloaded += download_result.byte_size
        elif download_result.media_missing_on_tumblr:
            self.statistics.media_missing += 1
        else:
            self.statistics.media_failed += 1
    
    def close(self):
        """Clean up resources."""
        if self.api_client:
            self.api_client.close()
        
        logger.info("Archiver closed")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.close()
