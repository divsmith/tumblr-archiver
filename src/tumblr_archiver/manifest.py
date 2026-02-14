"""
Manifest persistence and management.

This module provides the ManifestManager class for loading, saving,
and managing manifest.json files that track all downloaded media.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

import aiofiles
import aiofiles.os

from .models import Manifest, MediaItem, Post
from .storage import atomic_write

logger = logging.getLogger(__name__)


class ManifestManager:
    """
    Manages manifest.json persistence and operations.
    
    Provides thread-safe operations for loading, saving, and updating
    manifest files that track all downloaded media. Supports resume
    capability by tracking which media has already been downloaded.
    
    Attributes:
        output_dir: Base directory for the archive
        manifest_path: Path to the manifest.json file
        manifest: Current Manifest instance
        _lock: Asyncio lock for thread-safe operations
        _downloaded_urls: Cached set of downloaded media URLs
    """
    
    def __init__(self, output_dir: Union[str, Path]):
        """
        Initialize ManifestManager for given output directory.
        
        Args:
            output_dir: Base directory where manifest.json will be stored
            
        Example:
            ```python
            manager = ManifestManager("/archive/myblog")
            await manager.load()
            ```
        """
        self.output_dir = Path(output_dir)
        self.manifest_path = self.output_dir / "manifest.json"
        self.manifest: Optional[Manifest] = None
        self._lock = asyncio.Lock()
        self._downloaded_urls: Set[str] = set()
    
    async def load(self) -> Manifest:
        """
        Load existing manifest.json or create new one.
        
        If manifest.json exists, loads and validates it.
        If not found, creates a new empty manifest (but doesn't save yet).
        
        Returns:
            Loaded or newly created Manifest instance
            
        Raises:
            json.JSONDecodeError: If manifest.json is malformed
            ValidationError: If manifest data doesn't match schema
            
        Example:
            ```python
            manifest = await manager.load()
            print(f"Loaded {manifest.total_posts} posts")
            ```
        """
        async with self._lock:
            if await aiofiles.os.path.exists(self.manifest_path):
                logger.info(f"Loading existing manifest from {self.manifest_path}")
                
                try:
                    async with aiofiles.open(self.manifest_path, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        data = json.loads(content)
                        self.manifest = Manifest.from_dict(data)
                        
                    # Build cache of downloaded URLs
                    self._build_url_cache()
                    
                    logger.info(
                        f"Loaded manifest: {self.manifest.total_posts} posts, "
                        f"{self.manifest.total_media} media items"
                    )
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse manifest.json: {e}")
                    raise
                except Exception as e:
                    logger.error(f"Failed to load manifest: {e}")
                    raise
                    
            else:
                logger.info("No existing manifest found, creating new one")
                
                # Create new manifest with placeholder values
                # The actual blog_name and blog_url should be set by the caller
                self.manifest = Manifest(
                    blog_name="unknown",
                    blog_url="https://unknown.tumblr.com"
                )
                
            return self.manifest
    
    async def save(self) -> None:
        """
        Write manifest.json atomically to disk.
        
        Updates the last_updated timestamp and performs atomic write
        to prevent corruption. Thread-safe.
        
        Raises:
            IOError: If write fails
            ValueError: If no manifest loaded
            
        Example:
            ```python
            await manager.save()
            ```
        """
        async with self._lock:
            if self.manifest is None:
                raise ValueError("No manifest loaded. Call load() first.")
            
            # Update timestamp
            self.manifest.last_updated = datetime.now(timezone.utc)
            
            # Convert to JSON with proper datetime serialization
            manifest_dict = self.manifest.to_dict()
            json_content = json.dumps(manifest_dict, indent=2, ensure_ascii=False)
            
            # Atomic write to prevent corruption
            await atomic_write(self.manifest_path, json_content)
            
            logger.info(f"Saved manifest to {self.manifest_path}")
    
    async def add_post(self, post: Post) -> None:
        """
        Add post to manifest and save.
        
        Adds the post, updates statistics, rebuilds URL cache,
        and saves to disk.
        
        Args:
            post: Post instance to add
            
        Raises:
            ValueError: If no manifest loaded or post already exists
            IOError: If save fails
            
        Example:
            ```python
            post = Post(
                post_id="123456789",
                post_url="https://example.tumblr.com/post/123456789",
                timestamp=datetime.now(timezone.utc),
                is_reblog=False,
                media_items=[...]
            )
            await manager.add_post(post)
            ```
        """
        async with self._lock:
            if self.manifest is None:
                raise ValueError("No manifest loaded. Call load() first.")
            
            # Check for duplicate
            if any(p.post_id == post.post_id for p in self.manifest.posts):
                logger.warning(f"Post {post.post_id} already exists, skipping")
                return
            
            # Add post
            self.manifest.posts.append(post)
            
            # Update statistics
            self.manifest.total_posts = len(self.manifest.posts)
            self.manifest.total_media = sum(len(p.media_items) for p in self.manifest.posts)
            self.manifest.last_updated = datetime.now(timezone.utc)
            
            # Update URL cache
            for media in post.media_items:
                if media.status in ["downloaded", "archived"]:
                    self._downloaded_urls.add(media.original_url)
            
            logger.debug(f"Added post {post.post_id} with {len(post.media_items)} media items")
        
        # Save outside the lock to allow concurrent reads
        await self.save()
    
    async def update_media_item(self, media_item: MediaItem) -> bool:
        """
        Update existing media item in manifest.
        
        Finds the media item by original_url and updates it with new data.
        Useful for updating status, checksum, or other fields after download.
        
        Args:
            media_item: MediaItem with updated data
            
        Returns:
            True if media was found and updated, False otherwise
            
        Raises:
            ValueError: If no manifest loaded
            
        Example:
            ```python
            # Update status after download
            media_item.status = "downloaded"
            media_item.checksum = "abc123..."
            updated = await manager.update_media_item(media_item)
            ```
        """
        async with self._lock:
            if self.manifest is None:
                raise ValueError("No manifest loaded. Call load() first.")
            
            # Find the post containing this media
            for post in self.manifest.posts:
                for i, existing_media in enumerate(post.media_items):
                    if existing_media.original_url == media_item.original_url:
                        # Update the media item
                        post.media_items[i] = media_item
                        
                        # Update URL cache if status changed
                        if media_item.status in ["downloaded", "archived"]:
                            self._downloaded_urls.add(media_item.original_url)
                        
                        self.manifest.last_updated = datetime.now(timezone.utc)
                        
                        logger.debug(
                            f"Updated media item: {media_item.filename} "
                            f"(status: {media_item.status})"
                        )
                        
                        # Save and return
                        await self.save()
                        return True
            
            logger.warning(
                f"Media item not found in manifest: {media_item.original_url}"
            )
            return False
    
    def get_downloaded_media(self) -> List[MediaItem]:
        """
        Get list of all successfully downloaded media items.
        
        Returns media with status 'downloaded' or 'archived'.
        
        Returns:
            List of MediaItem instances that have been downloaded
            
        Raises:
            ValueError: If no manifest loaded
            
        Example:
            ```python
            downloaded = manager.get_downloaded_media()
            print(f"Downloaded {len(downloaded)} files")
            ```
        """
        if self.manifest is None:
            raise ValueError("No manifest loaded. Call load() first.")
        
        downloaded = []
        for post in self.manifest.posts:
            for media in post.media_items:
                if media.status in ["downloaded", "archived"]:
                    downloaded.append(media)
        
        return downloaded
    
    def is_media_downloaded(self, url: str) -> bool:
        """
        Check if media URL has already been downloaded.
        
        Uses cached set for O(1) lookup performance.
        
        Args:
            url: Original media URL to check
            
        Returns:
            True if media already downloaded, False otherwise
            
        Raises:
            ValueError: If no manifest loaded
            
        Example:
            ```python
            if manager.is_media_downloaded(url):
                print("Already downloaded, skipping")
            else:
                await download(url)
            ```
        """
        if self.manifest is None:
            raise ValueError("No manifest loaded. Call load() first.")
        
        return url in self._downloaded_urls
    
    def get_post_by_id(self, post_id: str) -> Optional[Post]:
        """
        Retrieve post by its ID.
        
        Args:
            post_id: Tumblr post ID to find
            
        Returns:
            Post instance if found, None otherwise
            
        Raises:
            ValueError: If no manifest loaded
            
        Example:
            ```python
            post = manager.get_post_by_id("123456789")
            if post:
                print(f"Found post with {len(post.media_items)} media")
            ```
        """
        if self.manifest is None:
            raise ValueError("No manifest loaded. Call load() first.")
        
        for post in self.manifest.posts:
            if post.post_id == post_id:
                return post
        
        return None
    
    def _build_url_cache(self) -> None:
        """
        Build internal cache of downloaded media URLs.
        
        Called after loading manifest to enable fast lookups
        with is_media_downloaded().
        """
        self._downloaded_urls.clear()
        
        if self.manifest:
            for post in self.manifest.posts:
                for media in post.media_items:
                    if media.status in ["downloaded", "archived"]:
                        self._downloaded_urls.add(media.original_url)
        
        logger.debug(f"Built URL cache with {len(self._downloaded_urls)} entries")
    
    async def set_blog_info(self, blog_name: str, blog_url: str) -> None:
        """
        Set or update blog information in manifest.
        
        Args:
            blog_name: Name of the Tumblr blog
            blog_url: URL of the Tumblr blog
            
        Raises:
            ValueError: If no manifest loaded
            
        Example:
            ```python
            await manager.set_blog_info("myblog", "https://myblog.tumblr.com")
            ```
        """
        async with self._lock:
            if self.manifest is None:
                raise ValueError("No manifest loaded. Call load() first.")
            
            self.manifest.blog_name = blog_name
            self.manifest.blog_url = blog_url
            self.manifest.last_updated = datetime.now(timezone.utc)
        
        await self.save()
    
    def get_statistics(self) -> Dict[str, int]:
        """
        Get comprehensive statistics about the archive.
        
        Returns:
            Dictionary with various statistical metrics
            
        Raises:
            ValueError: If no manifest loaded
            
        Example:
            ```python
            stats = manager.get_statistics()
            print(f"Total posts: {stats['total_posts']}")
            print(f"Downloaded: {stats['media_downloaded']}")
            ```
        """
        if self.manifest is None:
            raise ValueError("No manifest loaded. Call load() first.")
        
        return self.manifest.get_statistics()
