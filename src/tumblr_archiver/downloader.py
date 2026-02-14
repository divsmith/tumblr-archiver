"""Media downloader with checksum calculation, deduplication, and retry logic."""

import logging
from pathlib import Path
from typing import Callable, Literal, Optional

import aiofiles

from .archive import WaybackClient
from .checksum import calculate_file_checksum
from .deduplicator import FileDeduplicator
from .http_client import AsyncHTTPClient, HTTPError
from .models import MediaItem

logger = logging.getLogger(__name__)

# Type alias for progress callbacks
ProgressCallback = Callable[[int, Optional[int]], None]


class DownloadError(Exception):
    """Exception raised when media download fails."""
    
    def __init__(self, message: str, url: Optional[str] = None, status: Optional[int] = None):
        """Initialize download error.
        
        Args:
            message: Error message
            url: URL that failed to download
            status: HTTP status code if applicable
        """
        super().__init__(message)
        self.url = url
        self.status = status


class MediaDownloader:
    """Downloads media files with automatic fallback, deduplication, and resumption.
    
    Features:
    - Downloads from Tumblr URLs with automatic fallback to Internet Archive
    - Calculates SHA256 checksums for file integrity
    - Deduplication to avoid downloading the same file multiple times
    - Resume capability - skips already downloaded files
    - Organizes files into subdirectories by media type
    - Progress tracking via callbacks
    - Updates MediaItem objects with download results
    
    Example:
        ```python
        async with AsyncHTTPClient() as client:
            wayback = WaybackClient(client)
            downloader = MediaDownloader(
                http_client=client,
                wayback_client=wayback,
                output_dir=Path("downloads")
            )
            
            media_item = MediaItem(...)
            result = await downloader.download_media(
                media_item,
                progress_callback=lambda downloaded, total: 
                    print(f"Progress: {downloaded}/{total}")
            )
            
            print(f"Downloaded to: {result.filename}")
            print(f"Checksum: {result.checksum}")
        ```
    """
    
    def __init__(
        self,
        http_client: AsyncHTTPClient,
        wayback_client: WaybackClient,
        output_dir: Path,
        deduplicator: Optional[FileDeduplicator] = None,
    ):
        """Initialize the media downloader.
        
        Args:
            http_client: Async HTTP client for downloading files
            wayback_client: Wayback Machine client for archive fallback
            output_dir: Root directory for saving downloaded media
            deduplicator: Optional deduplicator instance. If None, creates new one.
        """
        self.http_client = http_client
        self.wayback_client = wayback_client
        self.output_dir = Path(output_dir)
        self.deduplicator = deduplicator or FileDeduplicator()
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories for different media types
        self._subdirs = {
            "image": self.output_dir / "images",
            "gif": self.output_dir / "gifs",
            "video": self.output_dir / "videos",
        }
        
        for subdir in self._subdirs.values():
            subdir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized MediaDownloader with output_dir={output_dir}")
    
    def _get_media_subdir(self, media_type: Literal["image", "gif", "video"]) -> Path:
        """Get the subdirectory for a specific media type.
        
        Args:
            media_type: Type of media
            
        Returns:
            Path to the subdirectory
        """
        return self._subdirs[media_type]
    
    def _get_output_path(self, media_item: MediaItem) -> Path:
        """Determine the output file path for a media item.
        
        Args:
            media_item: Media item to determine path for
            
        Returns:
            Full path where the file should be saved
        """
        subdir = self._get_media_subdir(media_item.media_type)
        return subdir / media_item.filename
    
    async def _download_from_url(
        self,
        url: str,
        output_path: Path,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> int:
        """Download a file from a URL to a local path.
        
        Args:
            url: URL to download from
            output_path: Local path to save the file
            progress_callback: Optional progress callback
            
        Returns:
            Size of the downloaded file in bytes
            
        Raises:
            HTTPError: If the download fails
            IOError: If file writing fails
        """
        logger.info(f"Downloading {url} to {output_path}")
        
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Download using HTTP client with streaming
        response = await self.http_client.get(url)
        total_size = response.content_length
        downloaded = 0
        
        try:
            async with aiofiles.open(output_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(8192):
                    await f.write(chunk)
                    downloaded += len(chunk)
                    
                    if progress_callback:
                        progress_callback(downloaded, total_size)
            
            logger.info(f"Downloaded {downloaded} bytes to {output_path}")
            return downloaded
            
        except Exception as e:
            # Clean up partial file on error
            if output_path.exists():
                output_path.unlink()
            raise IOError(f"Failed to write file {output_path}: {e}") from e
    
    async def download_media(
        self,
        media_item: MediaItem,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> MediaItem:
        """Download a media item with automatic fallback and deduplication.
        
        Download workflow:
        1. Check if file already exists (resume capability)
        2. Try downloading from Tumblr URL first
        3. On failure (404/error), fall back to Internet Archive
        4. Calculate SHA256 checksum of downloaded file
        5. Check for duplicates and reuse existing file if found
        6. Update MediaItem with results
        
        Args:
            media_item: Media item to download. Must have original_url and filename.
            progress_callback: Optional callback(downloaded_bytes, total_bytes)
                              Called during download progress.
            
        Returns:
            Updated MediaItem with:
            - checksum: SHA256 hash of the file
            - byte_size: Size of the file in bytes
            - retrieved_from: Source that succeeded ("tumblr" or "internet_archive")
            - status: Download status ("downloaded", "archived", or "error")
            - archive_snapshot_url: Set if retrieved from archive
            - notes: Any additional information about the download
            
        Raises:
            DownloadError: If download fails from both sources
        """
        output_path = self._get_output_path(media_item)
        
        # Check if file already exists (resume capability)
        if output_path.exists():
            logger.info(f"File already exists: {output_path}")
            
            try:
                # Calculate checksum of existing file
                checksum = await calculate_file_checksum(output_path)
                byte_size = output_path.stat().st_size
                
                # Check if it's a duplicate
                if self.deduplicator.is_duplicate(checksum):
                    existing_path = self.deduplicator.get_existing_file(checksum)
                    logger.info(
                        f"File {output_path} is a duplicate of {existing_path}"
                    )
                else:
                    # Add to deduplicator
                    self.deduplicator.add_file(checksum, str(output_path))
                
                # Update media item
                media_item.checksum = checksum
                media_item.byte_size = byte_size
                media_item.status = "downloaded" if media_item.retrieved_from == "tumblr" else "archived"
                media_item.notes = "File already existed (resumed)"
                
                return media_item
                
            except Exception as e:
                logger.warning(
                    f"Error checking existing file {output_path}: {e}. "
                    f"Will re-download."
                )
                # Remove corrupted file
                output_path.unlink()
        
        # Try downloading from Tumblr first
        try:
            logger.info(f"Attempting download from Tumblr: {media_item.original_url}")
            
            byte_size = await self._download_from_url(
                media_item.original_url,
                output_path,
                progress_callback,
            )
            
            # Calculate checksum
            checksum = await calculate_file_checksum(output_path)
            
            # Check for duplicates
            if self.deduplicator.is_duplicate(checksum):
                existing_path = self.deduplicator.get_existing_file(checksum)
                logger.info(
                    f"Downloaded file is a duplicate of {existing_path}. "
                    f"Removing duplicate."
                )
                output_path.unlink()
                
                # Update media item to point to existing file
                media_item.filename = Path(existing_path).name
                media_item.checksum = checksum
                media_item.byte_size = byte_size
                media_item.retrieved_from = "tumblr"
                media_item.status = "downloaded"
                media_item.notes = f"Duplicate of {existing_path}"
                
            else:
                # Add to deduplicator
                self.deduplicator.add_file(checksum, str(output_path))
                
                # Update media item
                media_item.checksum = checksum
                media_item.byte_size = byte_size
                media_item.retrieved_from = "tumblr"
                media_item.status = "downloaded"
                media_item.notes = None
            
            logger.info(
                f"Successfully downloaded from Tumblr: {media_item.filename} "
                f"({byte_size} bytes, {checksum})"
            )
            
            return media_item
            
        except HTTPError as e:
            # If 404 or other error, try Internet Archive
            if e.status == 404:
                logger.info(
                    f"File not found on Tumblr (404), "
                    f"falling back to Internet Archive"
                )
            else:
                logger.warning(
                    f"Error downloading from Tumblr (status={e.status}), "
                    f"falling back to Internet Archive: {e}"
                )
            
            # Try Internet Archive
            try:
                logger.info(
                    f"Attempting download from Internet Archive: "
                    f"{media_item.original_url}"
                )
                
                # Get best snapshot
                snapshot = await self.wayback_client.get_best_snapshot(
                    media_item.original_url
                )
                
                if not snapshot:
                    raise DownloadError(
                        f"No snapshots found in Internet Archive for {media_item.original_url}",
                        url=media_item.original_url,
                    )
                
                # Download from snapshot
                byte_size = await self._download_from_url(
                    snapshot.snapshot_url,
                    output_path,
                    progress_callback,
                )
                
                # Calculate checksum
                checksum = await calculate_file_checksum(output_path)
                
                # Check for duplicates
                if self.deduplicator.is_duplicate(checksum):
                    existing_path = self.deduplicator.get_existing_file(checksum)
                    logger.info(
                        f"Downloaded file is a duplicate of {existing_path}. "
                        f"Removing duplicate."
                    )
                    output_path.unlink()
                    
                    # Update media item to point to existing file
                    media_item.filename = Path(existing_path).name
                    media_item.checksum = checksum
                    media_item.byte_size = byte_size
                    media_item.retrieved_from = "internet_archive"
                    media_item.archive_snapshot_url = snapshot.snapshot_url
                    media_item.status = "archived"
                    media_item.notes = f"Duplicate of {existing_path}"
                    
                else:
                    # Add to deduplicator
                    self.deduplicator.add_file(checksum, str(output_path))
                    
                    # Update media item
                    media_item.checksum = checksum
                    media_item.byte_size = byte_size
                    media_item.retrieved_from = "internet_archive"
                    media_item.archive_snapshot_url = snapshot.snapshot_url
                    media_item.status = "archived"
                    media_item.notes = None
                
                logger.info(
                    f"Successfully downloaded from Internet Archive: "
                    f"{media_item.filename} ({byte_size} bytes, {checksum})"
                )
                
                return media_item
                
            except Exception as archive_error:
                logger.error(
                    f"Failed to download from Internet Archive: {archive_error}"
                )
                
                # Update media item with error status
                media_item.status = "error"
                media_item.notes = (
                    f"Failed to download from both Tumblr and Internet Archive. "
                    f"Tumblr error: {e}. Archive error: {archive_error}"
                )
                
                raise DownloadError(
                    f"Failed to download {media_item.original_url} from both sources",
                    url=media_item.original_url,
                ) from archive_error
        
        except Exception as e:
            # Unexpected error
            logger.error(f"Unexpected error downloading {media_item.original_url}: {e}")
            
            # Update media item with error status
            media_item.status = "error"
            media_item.notes = f"Unexpected error: {e}"
            
            raise DownloadError(
                f"Failed to download {media_item.original_url}: {e}",
                url=media_item.original_url,
            ) from e
    
    def __repr__(self) -> str:
        """String representation of the downloader."""
        return (
            f"MediaDownloader(output_dir={self.output_dir}, "
            f"deduplicator={self.deduplicator})"
        )
