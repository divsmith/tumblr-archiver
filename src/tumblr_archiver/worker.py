"""
Download worker for concurrent media processing.

This module provides the DownloadWorker class that processes media
downloads from a queue using the MediaDownloader.
"""

import logging
from typing import Callable, Optional

from .downloader import DownloadError, MediaDownloader
from .manifest import ManifestManager
from .models import MediaItem
from .queue import MediaQueue

logger = logging.getLogger(__name__)

# Type alias for progress callbacks
ProgressCallback = Callable[[str, MediaItem], None]


class WorkerError(Exception):
    """Exception raised when worker encounters an error."""
    pass


class DownloadWorker:
    """
    Worker that processes media downloads from a queue.
    
    Each worker runs independently, pulling media items from a shared
    queue, downloading them, and updating the manifest.
    
    Features:
    - Concurrent download processing
    - Automatic retry via MediaDownloader
    - Manifest updates on successful downloads
    - Progress reporting via callbacks
    - Graceful error handling
    
    Example:
        ```python
        queue = MediaQueue()
        downloader = MediaDownloader(...)
        manifest_manager = ManifestManager(...)
        
        worker = DownloadWorker(
            worker_id=1,
            queue=queue,
            downloader=downloader,
            manifest_manager=manifest_manager
        )
        
        await worker.run()
        ```
    """
    
    def __init__(
        self,
        worker_id: int,
        queue: MediaQueue,
        downloader: MediaDownloader,
        manifest_manager: ManifestManager,
        progress_callback: Optional[ProgressCallback] = None,
    ):
        """
        Initialize the download worker.
        
        Args:
            worker_id: Unique identifier for this worker
            queue: MediaQueue to pull download tasks from
            downloader: MediaDownloader for downloading files
            manifest_manager: ManifestManager for updating manifest
            progress_callback: Optional callback(worker_id, media_item) 
                             called after each successful download
        """
        self.worker_id = worker_id
        self.queue = queue
        self.downloader = downloader
        self.manifest_manager = manifest_manager
        self.progress_callback = progress_callback
        
        # Statistics
        self.downloads_completed = 0
        self.downloads_failed = 0
        self.bytes_downloaded = 0
        
        logger.info(f"Worker {worker_id} initialized")
    
    async def run(self) -> None:
        """
        Run the worker's main processing loop.
        
        Continuously pulls media items from the queue, downloads them,
        and updates the manifest until a sentinel value (None) is received.
        
        Errors during individual downloads are logged but don't stop the
        worker. The worker will continue processing remaining items.
        
        Example:
            ```python
            # Start worker in background
            worker_task = asyncio.create_task(worker.run())
            
            # ... add items to queue ...
            
            # Wait for worker to complete
            await worker_task
            ```
        """
        logger.info(f"Worker {self.worker_id} starting")
        
        try:
            while True:
                # Get next media item from queue
                media_item = await self.queue.get_media()
                
                # Check for sentinel value (None = stop signal)
                if media_item is None:
                    logger.info(f"Worker {self.worker_id} received stop signal")
                    self.queue.mark_complete()
                    break
                
                # Process the media item
                try:
                    await self._process_media(media_item)
                    self.downloads_completed += 1
                except Exception as e:
                    logger.error(
                        f"Worker {self.worker_id} failed to process "
                        f"{media_item.filename}: {e}",
                        exc_info=True
                    )
                    self.downloads_failed += 1
                finally:
                    # Always mark task as complete
                    self.queue.mark_complete()
        
        except Exception as e:
            logger.error(
                f"Worker {self.worker_id} encountered fatal error: {e}",
                exc_info=True
            )
            raise WorkerError(f"Worker {self.worker_id} failed") from e
        
        finally:
            logger.info(
                f"Worker {self.worker_id} stopping "
                f"(completed: {self.downloads_completed}, "
                f"failed: {self.downloads_failed})"
            )
    
    async def _process_media(self, media_item: MediaItem) -> None:
        """
        Process a single media item: download and update manifest.
        
        Args:
            media_item: Media item to download
            
        Raises:
            DownloadError: If download fails
            Exception: If manifest update fails
        """
        logger.debug(
            f"Worker {self.worker_id} processing {media_item.filename}"
        )
        
        try:
            # Download the media
            updated_media = await self.downloader.download_media(
                media_item,
                progress_callback=lambda downloaded, total: self._log_progress(
                    media_item, downloaded, total
                )
            )
            
            # Track bytes downloaded
            if updated_media.byte_size:
                self.bytes_downloaded += updated_media.byte_size
            
            # Update manifest with download results
            success = await self.manifest_manager.update_media_item(updated_media)
            
            if not success:
                logger.warning(
                    f"Worker {self.worker_id}: Failed to update manifest for "
                    f"{media_item.filename} (media not found in manifest)"
                )
            
            # Call progress callback if provided
            if self.progress_callback:
                self.progress_callback(f"Worker-{self.worker_id}", updated_media)
            
            logger.info(
                f"Worker {self.worker_id} completed {media_item.filename} "
                f"({updated_media.byte_size} bytes, status: {updated_media.status})"
            )
        
        except DownloadError as e:
            # Update media item status to error and save to manifest
            media_item.status = "error"
            media_item.notes = f"Download failed: {str(e)}"
            await self.manifest_manager.update_media_item(media_item)
            
            logger.error(
                f"Worker {self.worker_id}: Download failed for "
                f"{media_item.filename}: {e}"
            )
            raise
        
        except Exception as e:
            logger.error(
                f"Worker {self.worker_id}: Unexpected error processing "
                f"{media_item.filename}: {e}",
                exc_info=True
            )
            raise
    
    def _log_progress(
        self,
        media_item: MediaItem,
        downloaded: int,
        total: Optional[int]
    ) -> None:
        """
        Log download progress for a media item.
        
        Args:
            media_item: Media item being downloaded
            downloaded: Bytes downloaded so far
            total: Total bytes to download (None if unknown)
        """
        if total:
            percent = (downloaded / total) * 100
            logger.debug(
                f"Worker {self.worker_id}: {media_item.filename} - "
                f"{downloaded}/{total} bytes ({percent:.1f}%)"
            )
        else:
            logger.debug(
                f"Worker {self.worker_id}: {media_item.filename} - "
                f"{downloaded} bytes downloaded"
            )
    
    def stats(self) -> dict:
        """
        Get worker statistics.
        
        Returns:
            Dictionary with worker statistics:
            - worker_id: Worker identifier
            - downloads_completed: Number of successful downloads
            - downloads_failed: Number of failed downloads
            - bytes_downloaded: Total bytes downloaded
        """
        return {
            "worker_id": self.worker_id,
            "downloads_completed": self.downloads_completed,
            "downloads_failed": self.downloads_failed,
            "bytes_downloaded": self.bytes_downloaded,
        }
