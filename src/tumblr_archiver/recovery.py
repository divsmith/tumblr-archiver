"""
Media Recovery Module for Tumblr Archiver.

This module handles recovering media files that are missing from Tumblr
by querying the Internet Archive's Wayback Machine. It implements multiple
recovery strategies to maximize the chances of finding archived versions.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List
from urllib.parse import urlparse

import aiofiles
import aiohttp

from .wayback_client import (
    WaybackClient,
    WaybackError,
    SnapshotNotFoundError,
    Snapshot
)
from .config import ArchiverConfig


logger = logging.getLogger(__name__)


class RecoveryStatus(Enum):
    """Status of a media recovery attempt."""
    SUCCESS = "success"
    NOT_FOUND = "not_found"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class RecoveryResult:
    """Result of a media recovery operation.
    
    Attributes:
        media_url: Original media URL that was attempted to recover
        status: Recovery status (success, not_found, error, skipped)
        snapshot_url: Wayback Machine replay URL if successful
        timestamp: Timestamp of the snapshot if successful
        file_size: Size of recovered file in bytes
        local_path: Path where file was saved locally if downloaded
        strategy: Which recovery strategy succeeded
        error_message: Error details if recovery failed
    """
    media_url: str
    status: RecoveryStatus
    snapshot_url: Optional[str] = None
    timestamp: Optional[str] = None
    file_size: Optional[int] = None
    local_path: Optional[Path] = None
    strategy: Optional[str] = None
    error_message: Optional[str] = None
    
    @property
    def snapshot_datetime(self) -> Optional[datetime]:
        """Parse snapshot timestamp into datetime object."""
        if self.timestamp:
            try:
                return datetime.strptime(self.timestamp, "%Y%m%d%H%M%S")
            except ValueError:
                return None
        return None


class MediaRecovery:
    """Handles recovery of missing media via Internet Archive.
    
    This class implements multiple strategies to recover media that is no
    longer available on Tumblr's servers:
    
    1. Direct media URL lookup in Wayback Machine CDX API
    2. Best snapshot selection (highest quality preferred)
    3. Fallback to archived post page HTML parsing
    4. Download from Internet Archive with proper error handling
    
    Args:
        wayback_client: Configured WaybackClient instance
        config: Archiver configuration settings
    """
    
    def __init__(
        self,
        wayback_client: WaybackClient,
        config: ArchiverConfig
    ):
        """Initialize the media recovery handler.
        
        Args:
            wayback_client: WaybackClient for querying Internet Archive
            config: Configuration with recovery settings
        """
        self.wayback_client = wayback_client
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60)
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
    
    async def recover_media(
        self,
        media_url: str,
        post_url: str,
        output_path: Optional[Path] = None
    ) -> RecoveryResult:
        """Attempt to recover a missing media file from Internet Archive.
        
        This method tries multiple recovery strategies in sequence:
        1. Query exact media URL in Wayback CDX API
        2. Select best available snapshot (highest quality)
        3. If no direct snapshot, parse archived post page for media
        4. Download recovered media to output path if specified
        
        Args:
            media_url: The media URL that is missing from Tumblr
            post_url: The Tumblr post URL containing the media
            output_path: Optional path to save recovered file
            
        Returns:
            RecoveryResult with status, snapshot info, and metadata
            
        Raises:
            ValueError: If media_url or post_url is invalid
        """
        if not media_url or not post_url:
            raise ValueError("media_url and post_url are required")
        
        logger.info(f"Attempting to recover media: {media_url}")
        
        # Check if recovery is enabled
        if not self.config.wayback_enabled:
            logger.debug("Wayback recovery is disabled in config")
            return RecoveryResult(
                media_url=media_url,
                status=RecoveryStatus.SKIPPED,
                error_message="Wayback recovery disabled in configuration"
            )
        
        try:
            # Strategy 1: Try direct media URL lookup
            result = await self._try_direct_media_recovery(media_url, output_path)
            if result.status == RecoveryStatus.SUCCESS:
                return result
            
            logger.debug(
                f"Direct media recovery failed for {media_url}, "
                "trying post page extraction"
            )
            
            # Strategy 2: Try extracting from archived post page
            result = await self._try_post_page_extraction(
                media_url,
                post_url,
                output_path
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Recovery failed for {media_url}: {e}", exc_info=True)
            return RecoveryResult(
                media_url=media_url,
                status=RecoveryStatus.ERROR,
                error_message=str(e)
            )
    
    async def _try_direct_media_recovery(
        self,
        media_url: str,
        output_path: Optional[Path] = None
    ) -> RecoveryResult:
        """Try to recover media by querying its URL directly.
        
        Args:
            media_url: The media URL to recover
            output_path: Optional path to save recovered file
            
        Returns:
            RecoveryResult indicating success or failure
        """
        try:
            # Check if media URL has any archived snapshots
            logger.debug(f"Checking availability of {media_url}")
            
            # Get best snapshot (prefer highest quality)
            snapshot = await asyncio.to_thread(
                self.wayback_client.get_best_snapshot,
                media_url,
                "highest_quality"
            )
            
            logger.info(
                f"Found snapshot for {media_url}: "
                f"timestamp={snapshot.timestamp}, size={snapshot.file_size}"
            )
            
            # Download if output path is specified
            if output_path:
                await self._download_snapshot_async(snapshot, output_path)
                logger.info(f"Successfully downloaded to {output_path}")
            
            return RecoveryResult(
                media_url=media_url,
                status=RecoveryStatus.SUCCESS,
                snapshot_url=snapshot.replay_url,
                timestamp=snapshot.timestamp,
                file_size=snapshot.file_size,
                local_path=output_path if output_path else None,
                strategy="direct_media_url"
            )
            
        except SnapshotNotFoundError:
            logger.debug(f"No snapshots found for {media_url}")
            return RecoveryResult(
                media_url=media_url,
                status=RecoveryStatus.NOT_FOUND,
                error_message="No archived snapshots found"
            )
        except WaybackError as e:
            logger.warning(f"Wayback error for {media_url}: {e}")
            return RecoveryResult(
                media_url=media_url,
                status=RecoveryStatus.ERROR,
                error_message=str(e)
            )
    
    async def _try_post_page_extraction(
        self,
        media_url: str,
        post_url: str,
        output_path: Optional[Path] = None
    ) -> RecoveryResult:
        """Try to recover media by parsing archived post page HTML.
        
        If the direct media URL isn't archived, the post page itself
        might be archived and contain the media URL.
        
        Args:
            media_url: The media URL to find
            post_url: The post URL to query
            output_path: Optional path to save recovered file
            
        Returns:
            RecoveryResult indicating success or failure
        """
        try:
            logger.debug(f"Extracting media from archived post: {post_url}")
            
            # Extract media URLs from archived post page
            media_urls = await asyncio.to_thread(
                self.wayback_client.extract_media_from_archived_page,
                post_url
            )
            
            if not media_urls:
                logger.debug(f"No media found in archived post page: {post_url}")
                return RecoveryResult(
                    media_url=media_url,
                    status=RecoveryStatus.NOT_FOUND,
                    error_message="No media found in archived post page"
                )
            
            logger.debug(f"Found {len(media_urls)} media URLs in archived post")
            
            # Try to match the requested media URL
            matched_url = self._find_matching_media_url(media_url, media_urls)
            
            if not matched_url:
                logger.debug(
                    f"Requested media URL {media_url} not found in "
                    f"archived post media ({len(media_urls)} URLs)"
                )
                return RecoveryResult(
                    media_url=media_url,
                    status=RecoveryStatus.NOT_FOUND,
                    error_message=(
                        f"Media URL not found in archived post "
                        f"({len(media_urls)} other media found)"
                    )
                )
            
            logger.info(f"Matched media URL: {matched_url}")
            
            # Now try to get the best snapshot of the matched URL
            try:
                snapshot = await asyncio.to_thread(
                    self.wayback_client.get_best_snapshot,
                    matched_url,
                    "highest_quality"
                )
                
                # Download if output path is specified
                if output_path:
                    await self._download_snapshot_async(snapshot, output_path)
                    logger.info(f"Successfully downloaded to {output_path}")
                
                return RecoveryResult(
                    media_url=media_url,
                    status=RecoveryStatus.SUCCESS,
                    snapshot_url=snapshot.replay_url,
                    timestamp=snapshot.timestamp,
                    file_size=snapshot.file_size,
                    local_path=output_path if output_path else None,
                    strategy="post_page_extraction"
                )
                
            except SnapshotNotFoundError:
                logger.debug(
                    f"Media URL found in post but no snapshots: {matched_url}"
                )
                return RecoveryResult(
                    media_url=media_url,
                    status=RecoveryStatus.NOT_FOUND,
                    error_message="Media URL found in post but not archived"
                )
                
        except SnapshotNotFoundError:
            logger.debug(f"No archived post page found: {post_url}")
            return RecoveryResult(
                media_url=media_url,
                status=RecoveryStatus.NOT_FOUND,
                error_message="No archived post page found"
            )
        except WaybackError as e:
            logger.warning(f"Wayback error extracting from post {post_url}: {e}")
            return RecoveryResult(
                media_url=media_url,
                status=RecoveryStatus.ERROR,
                error_message=str(e)
            )
    
    def _find_matching_media_url(
        self,
        target_url: str,
        candidate_urls: List[str]
    ) -> Optional[str]:
        """Find a media URL that matches the target URL.
        
        Matches are done by comparing URL paths and filenames, allowing
        for different CDN domains or protocols.
        
        Args:
            target_url: The media URL to find
            candidate_urls: List of candidate URLs from archived page
            
        Returns:
            Matching URL from candidates, or None if no match
        """
        if not target_url or not candidate_urls:
            return None
        
        target_parsed = urlparse(target_url)
        target_path = target_parsed.path
        target_filename = Path(target_path).name
        
        # First try: exact URL match
        for url in candidate_urls:
            if url == target_url:
                return url
        
        # Second try: same path (different domain/scheme is OK for CDNs)
        for url in candidate_urls:
            parsed = urlparse(url)
            if parsed.path == target_path:
                return url
        
        # Third try: same filename (resolution variants might differ in path)
        for url in candidate_urls:
            parsed = urlparse(url)
            filename = Path(parsed.path).name
            if filename == target_filename:
                return url
        
        # Fourth try: same base filename (without resolution suffix)
        # e.g., "image_1280.jpg" vs "image_500.jpg"
        target_base = self._extract_base_filename(target_filename)
        for url in candidate_urls:
            parsed = urlparse(url)
            filename = Path(parsed.path).name
            base = self._extract_base_filename(filename)
            if base and base == target_base:
                return url
        
        return None
    
    def _extract_base_filename(self, filename: str) -> Optional[str]:
        """Extract base filename without resolution suffix.
        
        Tumblr media URLs often include resolution suffixes like _1280, _500.
        
        Args:
            filename: The filename to process
            
        Returns:
            Base filename without resolution suffix
        """
        if not filename:
            return None
        
        # Remove extension
        name_parts = filename.rsplit(".", 1)
        base_name = name_parts[0]
        
        # Remove resolution suffix (e.g., _1280, _500, _640)
        # Pattern: ends with _<digits>
        if "_" in base_name:
            parts = base_name.rsplit("_", 1)
            if parts[-1].isdigit():
                return parts[0]
        
        return base_name
    
    async def _download_snapshot_async(
        self,
        snapshot: Snapshot,
        output_path: Path
    ) -> None:
        """Download a snapshot asynchronously using aiohttp.
        
        Args:
            snapshot: Snapshot to download
            output_path: Path where file should be saved
            
        Raises:
            WaybackError: If download fails
        """
        if not self._session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        replay_url = snapshot.replay_url
        logger.debug(f"Downloading snapshot from {replay_url}")
        
        try:
            # Ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with self._session.get(
                replay_url,
                allow_redirects=True
            ) as response:
                response.raise_for_status()
                
                # Download in chunks
                async with aiofiles.open(output_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
                        
        except aiohttp.ClientError as e:
            raise WaybackError(
                f"Failed to download snapshot from {replay_url}: {e}"
            )
        except OSError as e:
            raise WaybackError(
                f"Failed to write file to {output_path}: {e}"
            )
    
    async def recover_multiple_media(
        self,
        media_items: List[tuple[str, str, Optional[Path]]],
        max_concurrent: int = 2
    ) -> List[RecoveryResult]:
        """Recover multiple media files concurrently.
        
        Args:
            media_items: List of (media_url, post_url, output_path) tuples
            max_concurrent: Maximum concurrent recovery operations
            
        Returns:
            List of RecoveryResult objects for each media item
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def recover_with_semaphore(
            media_url: str,
            post_url: str,
            output_path: Optional[Path]
        ) -> RecoveryResult:
            async with semaphore:
                return await self.recover_media(media_url, post_url, output_path)
        
        tasks = [
            recover_with_semaphore(media_url, post_url, output_path)
            for media_url, post_url, output_path in media_items
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                media_url = media_items[i][0]
                final_results.append(
                    RecoveryResult(
                        media_url=media_url,
                        status=RecoveryStatus.ERROR,
                        error_message=str(result)
                    )
                )
            else:
                final_results.append(result)
        
        return final_results
    
    def get_recovery_stats(
        self,
        results: List[RecoveryResult]
    ) -> dict:
        """Calculate statistics from recovery results.
        
        Args:
            results: List of RecoveryResult objects
            
        Returns:
            Dictionary with recovery statistics
        """
        total = len(results)
        if total == 0:
            return {
                "total": 0,
                "successful": 0,
                "not_found": 0,
                "errors": 0,
                "skipped": 0,
                "success_rate": 0.0
            }
        
        successful = sum(1 for r in results if r.status == RecoveryStatus.SUCCESS)
        not_found = sum(1 for r in results if r.status == RecoveryStatus.NOT_FOUND)
        errors = sum(1 for r in results if r.status == RecoveryStatus.ERROR)
        skipped = sum(1 for r in results if r.status == RecoveryStatus.SKIPPED)
        
        return {
            "total": total,
            "successful": successful,
            "not_found": not_found,
            "errors": errors,
            "skipped": skipped,
            "success_rate": (successful / total * 100) if total > 0 else 0.0
        }
