"""Tests for ManifestManager and storage utilities."""

import asyncio
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tumblr_archiver.manifest import ManifestManager
from tumblr_archiver.models import MediaItem, Post
from tumblr_archiver.storage import (
    atomic_write,
    ensure_directory,
    generate_unique_filename,
    get_media_directory,
)


class TestStorageUtilities:
    """Tests for storage utility functions."""
    
    @pytest.mark.asyncio
    async def test_ensure_directory_creates_new_dir(self, tmp_path):
        """Test creating a new directory."""
        test_dir = tmp_path / "new" / "nested" / "directory"
        result = await ensure_directory(test_dir)
        
        assert result.exists()
        assert result.is_dir()
        assert result == test_dir
    
    @pytest.mark.asyncio
    async def test_ensure_directory_idempotent(self, tmp_path):
        """Test that ensure_directory can be called multiple times safely."""
        test_dir = tmp_path / "existing"
        
        # Create it twice
        result1 = await ensure_directory(test_dir)
        result2 = await ensure_directory(test_dir)
        
        assert result1 == result2
        assert test_dir.exists()
    
    @pytest.mark.asyncio
    async def test_atomic_write_creates_file(self, tmp_path):
        """Test atomic write creates file with correct content."""
        test_file = tmp_path / "test.txt"
        content = "Hello, World!"
        
        await atomic_write(test_file, content)
        
        assert test_file.exists()
        assert test_file.read_text() == content
    
    @pytest.mark.asyncio
    async def test_atomic_write_replaces_existing(self, tmp_path):
        """Test atomic write replaces existing file."""
        test_file = tmp_path / "test.txt"
        
        # Write initial content
        test_file.write_text("old content")
        
        # Atomically replace
        await atomic_write(test_file, "new content")
        
        assert test_file.read_text() == "new content"
    
    @pytest.mark.asyncio
    async def test_atomic_write_creates_parent_dirs(self, tmp_path):
        """Test atomic write creates parent directories."""
        test_file = tmp_path / "nested" / "dirs" / "test.txt"
        
        await atomic_write(test_file, "content")
        
        assert test_file.exists()
        assert test_file.read_text() == "content"
    
    @pytest.mark.asyncio
    async def test_atomic_write_cleans_up_on_error(self, tmp_path):
        """Test temp files are cleaned up on error."""
        test_file = tmp_path / "test.txt"
        
        # This should work initially
        await atomic_write(test_file, "content")
        
        # Force an error by making directory read-only (on Unix systems)
        # Note: This test may not work on all systems
        try:
            tmp_path.chmod(0o444)
            protected_file = tmp_path / "protected.txt"
            
            with pytest.raises(IOError):
                await atomic_write(protected_file, "content")
            
            # Check no temp files left behind
            tmp_path.chmod(0o755)
            files_after = list(tmp_path.glob("*"))
            temp_files = [f for f in files_after if f.name.startswith(".")]
            
            assert len(temp_files) == 0
        finally:
            # Restore permissions
            tmp_path.chmod(0o755)
    
    def test_get_media_directory_image(self, tmp_path):
        """Test getting image directory."""
        result = get_media_directory(tmp_path, "image")
        assert result == tmp_path / "images"
    
    def test_get_media_directory_gif(self, tmp_path):
        """Test getting gif directory."""
        result = get_media_directory(tmp_path, "gif")
        assert result == tmp_path / "gifs"
    
    def test_get_media_directory_video(self, tmp_path):
        """Test getting video directory."""
        result = get_media_directory(tmp_path, "video")
        assert result == tmp_path / "videos"
    
    def test_generate_unique_filename_with_checksum(self):
        """Test filename generation with checksum."""
        url = "https://64.media.tumblr.com/abc123/tumblr_xyz.jpg"
        checksum = "a" * 64
        
        result = generate_unique_filename(url, checksum)
        
        assert result == "aaaaaaaaaaaaaaaa.jpg"
        assert len(result) <= 25  # Reasonable length
    
    def test_generate_unique_filename_without_checksum(self):
        """Test filename generation without checksum."""
        url = "https://64.media.tumblr.com/abc123/tumblr_xyz123.jpg"
        
        result = generate_unique_filename(url)
        
        assert result == "tumblr_xyz123.jpg"
        assert result.endswith(".jpg")
    
    def test_generate_unique_filename_sanitizes_special_chars(self):
        """Test filename generation sanitizes special characters."""
        url = "https://example.com/file name!@#$%^&*().jpg"
        
        result = generate_unique_filename(url)
        
        # Should only contain safe characters
        for char in result:
            assert char.isalnum() or char in "-_."
    
    def test_generate_unique_filename_no_extension(self):
        """Test filename generation with no extension."""
        url = "https://example.com/image"
        checksum = "b" * 64
        
        result = generate_unique_filename(url, checksum)
        
        # Should add default extension
        assert result == "bbbbbbbbbbbbbbbb.jpg"


class TestManifestManager:
    """Tests for ManifestManager class."""
    
    @pytest.mark.asyncio
    async def test_init(self, tmp_path):
        """Test ManifestManager initialization."""
        manager = ManifestManager(tmp_path)
        
        assert manager.output_dir == tmp_path
        assert manager.manifest_path == tmp_path / "manifest.json"
        assert manager.manifest is None
        assert len(manager._downloaded_urls) == 0
    
    @pytest.mark.asyncio
    async def test_load_creates_new_manifest(self, tmp_path):
        """Test loading creates new manifest if none exists."""
        manager = ManifestManager(tmp_path)
        manifest = await manager.load()
        
        assert manifest is not None
        assert manifest.blog_name == "unknown"
        assert manifest.total_posts == 0
        assert manifest.total_media == 0
        assert len(manifest.posts) == 0
    
    @pytest.mark.asyncio
    async def test_load_existing_manifest(self):
        """Test loading existing manifest from fixtures."""
        # Use the fixture manifest
        fixtures_dir = Path(__file__).parent / "fixtures"
        
        # Copy fixture to temp dir
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            manifest_path = tmp_path / "manifest.json"
            
            # Copy fixture
            fixture_content = (fixtures_dir / "manifest.json").read_text()
            manifest_path.write_text(fixture_content)
            
            # Load it
            manager = ManifestManager(tmp_path)
            manifest = await manager.load()
            
            assert manifest.blog_name == "example-blog"
            assert manifest.total_posts == 3
            assert manifest.total_media == 5
            assert len(manifest.posts) == 3
    
    @pytest.mark.asyncio
    async def test_save_creates_manifest_file(self, tmp_path):
        """Test saving creates manifest.json file."""
        manager = ManifestManager(tmp_path)
        await manager.load()
        await manager.set_blog_info("test-blog", "https://test-blog.tumblr.com")
        await manager.save()
        
        manifest_path = tmp_path / "manifest.json"
        assert manifest_path.exists()
        
        # Verify content
        content = json.loads(manifest_path.read_text())
        assert content["blog_name"] == "test-blog"
        assert content["blog_url"] == "https://test-blog.tumblr.com"
    
    @pytest.mark.asyncio
    async def test_save_without_load_raises_error(self, tmp_path):
        """Test saving without loading raises error."""
        manager = ManifestManager(tmp_path)
        
        with pytest.raises(ValueError, match="No manifest loaded"):
            await manager.save()
    
    @pytest.mark.asyncio
    async def test_save_updates_timestamp(self, tmp_path):
        """Test saving updates last_updated timestamp."""
        manager = ManifestManager(tmp_path)
        manifest = await manager.load()
        
        original_time = manifest.last_updated
        
        # Wait a tiny bit to ensure time difference
        await asyncio.sleep(0.01)
        
        await manager.save()
        
        assert manifest.last_updated > original_time
    
    @pytest.mark.asyncio
    async def test_add_post(self, tmp_path):
        """Test adding a post to manifest."""
        manager = ManifestManager(tmp_path)
        await manager.load()
        await manager.set_blog_info("test-blog", "https://test-blog.tumblr.com")
        
        # Create a post
        post = Post(
            post_id="123456789",
            post_url="https://test-blog.tumblr.com/post/123456789",
            timestamp=datetime.now(timezone.utc),
            is_reblog=False,
            media_items=[]
        )
        
        await manager.add_post(post)
        
        assert manager.manifest.total_posts == 1
        assert len(manager.manifest.posts) == 1
        assert manager.manifest.posts[0].post_id == "123456789"
    
    @pytest.mark.asyncio
    async def test_add_post_with_media(self, tmp_path):
        """Test adding a post with media items."""
        manager = ManifestManager(tmp_path)
        await manager.load()
        await manager.set_blog_info("test-blog", "https://test-blog.tumblr.com")
        
        # Create media item
        media = MediaItem(
            post_id="123456789",
            post_url="https://test-blog.tumblr.com/post/123456789",
            timestamp=datetime.now(timezone.utc),
            media_type="image",
            filename="123456789_001.jpg",
            byte_size=524288,
            checksum="a" * 64,
            original_url="https://64.media.tumblr.com/abc/image.jpg",
            retrieved_from="tumblr",
            status="downloaded"
        )
        
        # Create post with media
        post = Post(
            post_id="123456789",
            post_url="https://test-blog.tumblr.com/post/123456789",
            timestamp=datetime.now(timezone.utc),
            is_reblog=False,
            media_items=[media]
        )
        
        await manager.add_post(post)
        
        assert manager.manifest.total_posts == 1
        assert manager.manifest.total_media == 1
        assert len(manager.manifest.posts[0].media_items) == 1
    
    @pytest.mark.asyncio
    async def test_add_duplicate_post_skipped(self, tmp_path):
        """Test adding duplicate post is skipped."""
        manager = ManifestManager(tmp_path)
        await manager.load()
        await manager.set_blog_info("test-blog", "https://test-blog.tumblr.com")
        
        post = Post(
            post_id="123456789",
            post_url="https://test-blog.tumblr.com/post/123456789",
            timestamp=datetime.now(timezone.utc),
            is_reblog=False,
            media_items=[]
        )
        
        # Add twice
        await manager.add_post(post)
        await manager.add_post(post)
        
        # Should only have one
        assert manager.manifest.total_posts == 1
    
    @pytest.mark.asyncio
    async def test_update_media_item(self, tmp_path):
        """Test updating an existing media item."""
        manager = ManifestManager(tmp_path)
        await manager.load()
        await manager.set_blog_info("test-blog", "https://test-blog.tumblr.com")
        
        # Create and add initial media
        original_media = MediaItem(
            post_id="123456789",
            post_url="https://test-blog.tumblr.com/post/123456789",
            timestamp=datetime.now(timezone.utc),
            media_type="image",
            filename="123456789_001.jpg",
            byte_size=None,
            checksum=None,
            original_url="https://64.media.tumblr.com/abc/image.jpg",
            retrieved_from="tumblr",
            status="missing"
        )
        
        post = Post(
            post_id="123456789",
            post_url="https://test-blog.tumblr.com/post/123456789",
            timestamp=datetime.now(timezone.utc),
            is_reblog=False,
            media_items=[original_media]
        )
        
        await manager.add_post(post)
        
        # Update the media
        updated_media = MediaItem(
            post_id="123456789",
            post_url="https://test-blog.tumblr.com/post/123456789",
            timestamp=datetime.now(timezone.utc),
            media_type="image",
            filename="123456789_001.jpg",
            byte_size=524288,
            checksum="a" * 64,
            original_url="https://64.media.tumblr.com/abc/image.jpg",
            retrieved_from="tumblr",
            status="downloaded"
        )
        
        result = await manager.update_media_item(updated_media)
        
        assert result is True
        
        # Verify update
        stored_media = manager.manifest.posts[0].media_items[0]
        assert stored_media.status == "downloaded"
        assert stored_media.checksum == "a" * 64
        assert stored_media.byte_size == 524288
    
    @pytest.mark.asyncio
    async def test_update_nonexistent_media_returns_false(self, tmp_path):
        """Test updating non-existent media returns False."""
        manager = ManifestManager(tmp_path)
        await manager.load()
        
        media = MediaItem(
            post_id="999999999",
            post_url="https://test-blog.tumblr.com/post/999999999",
            timestamp=datetime.now(timezone.utc),
            media_type="image",
            filename="999999999_001.jpg",
            byte_size=524288,
            checksum="a" * 64,
            original_url="https://64.media.tumblr.com/xyz/nonexistent.jpg",
            retrieved_from="tumblr",
            status="downloaded"
        )
        
        result = await manager.update_media_item(media)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_downloaded_media(self, tmp_path):
        """Test getting list of downloaded media."""
        manager = ManifestManager(tmp_path)
        await manager.load()
        await manager.set_blog_info("test-blog", "https://test-blog.tumblr.com")
        
        # Add posts with different statuses
        downloaded_media = MediaItem(
            post_id="111",
            post_url="https://test-blog.tumblr.com/post/111",
            timestamp=datetime.now(timezone.utc),
            media_type="image",
            filename="111_001.jpg",
            original_url="https://64.media.tumblr.com/abc/downloaded.jpg",
            retrieved_from="tumblr",
            status="downloaded"
        )
        
        archived_media = MediaItem(
            post_id="222",
            post_url="https://test-blog.tumblr.com/post/222",
            timestamp=datetime.now(timezone.utc),
            media_type="image",
            filename="222_001.jpg",
            original_url="https://64.media.tumblr.com/def/archived.jpg",
            retrieved_from="internet_archive",
            archive_snapshot_url="https://web.archive.org/web/123/image.jpg",
            status="archived"
        )
        
        missing_media = MediaItem(
            post_id="333",
            post_url="https://test-blog.tumblr.com/post/333",
            timestamp=datetime.now(timezone.utc),
            media_type="image",
            filename="333_001.jpg",
            original_url="https://64.media.tumblr.com/ghi/missing.jpg",
            retrieved_from="tumblr",
            status="missing"
        )
        
        post1 = Post(
            post_id="111",
            post_url="https://test-blog.tumblr.com/post/111",
            timestamp=datetime.now(timezone.utc),
            is_reblog=False,
            media_items=[downloaded_media]
        )
        
        post2 = Post(
            post_id="222",
            post_url="https://test-blog.tumblr.com/post/222",
            timestamp=datetime.now(timezone.utc),
            is_reblog=False,
            media_items=[archived_media]
        )
        
        post3 = Post(
            post_id="333",
            post_url="https://test-blog.tumblr.com/post/333",
            timestamp=datetime.now(timezone.utc),
            is_reblog=False,
            media_items=[missing_media]
        )
        
        await manager.add_post(post1)
        await manager.add_post(post2)
        await manager.add_post(post3)
        
        # Get downloaded media
        downloaded = manager.get_downloaded_media()
        
        assert len(downloaded) == 2  # downloaded + archived
        urls = [m.original_url for m in downloaded]
        assert "https://64.media.tumblr.com/abc/downloaded.jpg" in urls
        assert "https://64.media.tumblr.com/def/archived.jpg" in urls
    
    @pytest.mark.asyncio
    async def test_is_media_downloaded(self, tmp_path):
        """Test checking if media is downloaded."""
        manager = ManifestManager(tmp_path)
        await manager.load()
        await manager.set_blog_info("test-blog", "https://test-blog.tumblr.com")
        
        # Add downloaded media
        media = MediaItem(
            post_id="123456789",
            post_url="https://test-blog.tumblr.com/post/123456789",
            timestamp=datetime.now(timezone.utc),
            media_type="image",
            filename="123456789_001.jpg",
            original_url="https://64.media.tumblr.com/abc/image.jpg",
            retrieved_from="tumblr",
            status="downloaded"
        )
        
        post = Post(
            post_id="123456789",
            post_url="https://test-blog.tumblr.com/post/123456789",
            timestamp=datetime.now(timezone.utc),
            is_reblog=False,
            media_items=[media]
        )
        
        await manager.add_post(post)
        
        # Check downloaded URL
        assert manager.is_media_downloaded("https://64.media.tumblr.com/abc/image.jpg")
        
        # Check non-downloaded URL
        assert not manager.is_media_downloaded("https://64.media.tumblr.com/xyz/other.jpg")
    
    @pytest.mark.asyncio
    async def test_resume_capability(self):
        """Test resume capability by loading existing manifest."""
        # Use fixture
        fixtures_dir = Path(__file__).parent / "fixtures"
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            manifest_path = tmp_path / "manifest.json"
            
            # Copy fixture
            fixture_content = (fixtures_dir / "manifest.json").read_text()
            manifest_path.write_text(fixture_content)
            
            # Load manifest
            manager = ManifestManager(tmp_path)
            await manager.load()
            
            # Check resume capability
            # These URLs should be marked as downloaded in the fixture
            assert manager.is_media_downloaded(
                "https://64.media.tumblr.com/abc123/tumblr_xyz001.jpg"
            )
            assert manager.is_media_downloaded(
                "https://64.media.tumblr.com/abc123/tumblr_xyz002.jpg"
            )
            assert manager.is_media_downloaded(
                "https://64.media.tumblr.com/def456/tumblr_animated.gif"
            )
            assert manager.is_media_downloaded(
                "https://64.media.tumblr.com/ghi789/tumblr_photo.jpg"
            )
            
            # This URL is missing, should not be marked as downloaded
            assert not manager.is_media_downloaded(
                "https://va.media.tumblr.com/tumblr_video123.mp4"
            )
    
    @pytest.mark.asyncio
    async def test_get_post_by_id(self, tmp_path):
        """Test retrieving post by ID."""
        manager = ManifestManager(tmp_path)
        await manager.load()
        await manager.set_blog_info("test-blog", "https://test-blog.tumblr.com")
        
        post = Post(
            post_id="123456789",
            post_url="https://test-blog.tumblr.com/post/123456789",
            timestamp=datetime.now(timezone.utc),
            is_reblog=False,
            media_items=[]
        )
        
        await manager.add_post(post)
        
        # Find it
        found = manager.get_post_by_id("123456789")
        assert found is not None
        assert found.post_id == "123456789"
        
        # Try non-existent
        not_found = manager.get_post_by_id("999999999")
        assert not_found is None
    
    @pytest.mark.asyncio
    async def test_set_blog_info(self, tmp_path):
        """Test setting blog information."""
        manager = ManifestManager(tmp_path)
        await manager.load()
        
        await manager.set_blog_info("myblog", "https://myblog.tumblr.com")
        
        assert manager.manifest.blog_name == "myblog"
        assert manager.manifest.blog_url == "https://myblog.tumblr.com"
        
        # Should be saved
        manifest_path = tmp_path / "manifest.json"
        assert manifest_path.exists()
        
        content = json.loads(manifest_path.read_text())
        assert content["blog_name"] == "myblog"
    
    @pytest.mark.asyncio
    async def test_get_statistics(self, tmp_path):
        """Test getting statistics."""
        manager = ManifestManager(tmp_path)
        await manager.load()
        await manager.set_blog_info("test-blog", "https://test-blog.tumblr.com")
        
        # Add some posts
        media1 = MediaItem(
            post_id="111",
            post_url="https://test-blog.tumblr.com/post/111",
            timestamp=datetime.now(timezone.utc),
            media_type="image",
            filename="111_001.jpg",
            original_url="https://64.media.tumblr.com/abc/image1.jpg",
            retrieved_from="tumblr",
            status="downloaded"
        )
        
        media2 = MediaItem(
            post_id="222",
            post_url="https://test-blog.tumblr.com/post/222",
            timestamp=datetime.now(timezone.utc),
            media_type="gif",
            filename="222_001.gif",
            original_url="https://64.media.tumblr.com/def/image2.gif",
            retrieved_from="internet_archive",
            archive_snapshot_url="https://web.archive.org/web/123/image.gif",
            status="archived"
        )
        
        post1 = Post(
            post_id="111",
            post_url="https://test-blog.tumblr.com/post/111",
            timestamp=datetime.now(timezone.utc),
            is_reblog=False,
            media_items=[media1]
        )
        
        post2 = Post(
            post_id="222",
            post_url="https://test-blog.tumblr.com/post/222",
            timestamp=datetime.now(timezone.utc),
            is_reblog=True,
            media_items=[media2]
        )
        
        await manager.add_post(post1)
        await manager.add_post(post2)
        
        # Get stats
        stats = manager.get_statistics()
        
        assert stats["total_posts"] == 2
        assert stats["total_media"] == 2
        assert stats["original_posts"] == 1
        assert stats["reblogs"] == 1
        assert stats["media_downloaded"] == 1
        assert stats["media_archived"] == 1
        assert stats["images"] == 1
        assert stats["gifs"] == 1
        assert stats["from_tumblr"] == 1
        assert stats["from_internet_archive"] == 1
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self, tmp_path):
        """Test thread-safe concurrent operations."""
        manager = ManifestManager(tmp_path)
        await manager.load()
        await manager.set_blog_info("test-blog", "https://test-blog.tumblr.com")
        
        # Create multiple posts
        async def add_post_task(post_id: str):
            post = Post(
                post_id=post_id,
                post_url=f"https://test-blog.tumblr.com/post/{post_id}",
                timestamp=datetime.now(timezone.utc),
                is_reblog=False,
                media_items=[]
            )
            await manager.add_post(post)
        
        # Add posts concurrently
        tasks = [add_post_task(str(i)) for i in range(10)]
        await asyncio.gather(*tasks)
        
        # All should be added
        assert manager.manifest.total_posts == 10
        
        # Verify manifest file is valid
        manifest_path = tmp_path / "manifest.json"
        content = json.loads(manifest_path.read_text())
        assert content["total_posts"] == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
