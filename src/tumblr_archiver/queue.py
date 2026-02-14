"""
Media download queue for distributing work to workers.

This module provides a MediaQueue class that wraps asyncio.Queue
with additional statistics tracking for monitoring download progress.
"""

import asyncio
import logging
from typing import Optional

from .models import MediaItem

logger = logging.getLogger(__name__)


class MediaQueue:
    """
    Queue for distributing media download tasks to workers.
    
    Wraps asyncio.Queue with additional statistics tracking to monitor
    download progress and queue status.
    
    Attributes:
        _queue: Underlying asyncio.Queue
        _total_items: Total number of items added to the queue
        _completed_items: Number of items marked as complete
        
    Example:
        ```python
        queue = MediaQueue()
        
        # Producer
        for media in media_items:
            await queue.add_media(media)
        
        # Consumer
        while True:
            media = await queue.get_media()
            if media is None:  # Sentinel value
                break
            
            # Process media...
            queue.mark_complete()
        
        # Wait for all tasks to complete
        await queue.wait_completion()
        ```
    """
    
    def __init__(self, maxsize: int = 0):
        """
        Initialize the media queue.
        
        Args:
            maxsize: Maximum number of items in queue. 0 means unlimited.
        """
        self._queue: asyncio.Queue[Optional[MediaItem]] = asyncio.Queue(maxsize=maxsize)
        self._total_items = 0
        self._completed_items = 0
        self._lock = asyncio.Lock()
    
    async def add_media(self, media_item: MediaItem) -> None:
        """
        Add a media item to the queue.
        
        Args:
            media_item: Media item to add to the queue
            
        Example:
            ```python
            media = MediaItem(...)
            await queue.add_media(media)
            ```
        """
        await self._queue.put(media_item)
        async with self._lock:
            self._total_items += 1
        
        logger.debug(
            f"Added media to queue: {media_item.filename} "
            f"(queue size: {self.qsize()})"
        )
    
    async def get_media(self) -> Optional[MediaItem]:
        """
        Get the next media item from the queue.
        
        Blocks until an item is available.
        
        Returns:
            Next MediaItem in the queue, or None as a sentinel value
            to signal workers to stop.
            
        Example:
            ```python
            media = await queue.get_media()
            if media is not None:
                # Process media...
                queue.mark_complete()
            ```
        """
        item = await self._queue.get()
        return item
    
    def mark_complete(self) -> None:
        """
        Mark a task as complete.
        
        Should be called after successfully processing an item from the queue.
        This is analogous to asyncio.Queue.task_done().
        
        Example:
            ```python
            media = await queue.get_media()
            try:
                # Process media...
                pass
            finally:
                queue.mark_complete()
            ```
        """
        self._queue.task_done()
        self._completed_items += 1
        
        logger.debug(
            f"Marked task complete "
            f"({self._completed_items}/{self._total_items} completed)"
        )
    
    async def wait_completion(self) -> None:
        """
        Wait for all queued items to be processed.
        
        Blocks until all items added to the queue have been processed
        and marked complete. Analogous to asyncio.Queue.join().
        
        Example:
            ```python
            # Add all items
            for media in media_items:
                await queue.add_media(media)
            
            # Start workers...
            
            # Wait for completion
            await queue.wait_completion()
            print("All downloads complete!")
            ```
        """
        await self._queue.join()
        logger.info(
            f"All {self._total_items} items completed"
        )
    
    def qsize(self) -> int:
        """
        Get the current number of items in the queue.
        
        Note: This is an approximate size on some platforms.
        
        Returns:
            Number of items currently in the queue
        """
        return self._queue.qsize()
    
    @property
    def total_items(self) -> int:
        """Total number of items added to the queue."""
        return self._total_items
    
    @property
    def completed_items(self) -> int:
        """Number of items marked as complete."""
        return self._completed_items
    
    @property
    def pending_items(self) -> int:
        """Number of items not yet completed."""
        return self._total_items - self._completed_items
    
    def stats(self) -> dict:
        """
        Get queue statistics.
        
        Returns:
            Dictionary with queue statistics:
            - total: Total items added
            - completed: Items marked complete
            - pending: Items not yet complete
            - qsize: Current queue size
        """
        return {
            "total": self._total_items,
            "completed": self._completed_items,
            "pending": self.pending_items,
            "qsize": self.qsize(),
        }
    
    async def add_sentinel(self) -> None:
        """
        Add a sentinel value (None) to signal workers to stop.
        
        Workers should check for None and break their processing loop
        when received.
        
        Example:
            ```python
            # Signal workers to stop
            for _ in range(num_workers):
                await queue.add_sentinel()
            ```
        """
        await self._queue.put(None)
        logger.debug("Added sentinel value to queue")
