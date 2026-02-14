"""
Tests for Tumblr archiver data models.

Comprehensive tests for MediaItem, Post, and Manifest models including
validation, serialization, and edge cases.
"""

from datetime import datetime, timezone
from typing import Dict

import pytest
from pydantic import ValidationError

from tumblr_archiver.models import MediaItem, Manifest, Post


class TestMediaItem:
    """Tests for MediaItem model."""
    
    def test_create_valid_media_item(self):
        """Test creating a valid MediaItem with all required fields."""
        media = MediaItem(
            post_id="123456789",
            post_url="https://example.tumblr.com/post/123456789",
            timestamp=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
            media_type="image",
            filename="123456789_001.jpg",
            original_url="https://64.media.tumblr.com/abc/tumblr_xyz.jpg",
            retrieved_from="tumblr",
            status="downloaded"
        )
        
        assert media.post_id == "123456789"
        assert media.media_type == "image"
        assert media.status == "downloaded"
        assert media.retrieved_from == "tumblr"
    
    def test_media_item_with_optional_fields(self):
        """Test MediaItem with all optional fields populated."""
        media = MediaItem(
            post_id="123456789",
            post_url="https://example.tumblr.com/post/123456789",
            timestamp=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
            media_type="video",
            filename="123456789_001.mp4",
            byte_size=1024000,
            checksum="a" * 64,
            original_url="https://64.media.tumblr.com/abc/tumblr_xyz.mp4",
            retrieved_from="tumblr",
            status="downloaded",
            notes="HD quality video"
        )
        
        assert media.byte_size == 1024000
        assert media.checksum == "a" * 64
        assert media.notes == "HD quality video"
    
    def test_media_item_invalid_media_type(self):
        """Test that invalid media_type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            MediaItem(
                post_id="123",
                post_url="https://example.tumblr.com/post/123",
                timestamp=datetime.now(timezone.utc),
                media_type="audio",  # Invalid type
                filename="test.mp3",
                original_url="https://example.com/test.mp3",
                retrieved_from="tumblr",
                status="downloaded"
            )
        
        assert "media_type" in str(exc_info.value)
    
    def test_media_item_invalid_status(self):
        """Test that invalid status raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            MediaItem(
                post_id="123",
                post_url="https://example.tumblr.com/post/123",
                timestamp=datetime.now(timezone.utc),
                media_type="image",
                filename="test.jpg",
                original_url="https://example.com/test.jpg",
                retrieved_from="tumblr",
                status="pending"  # Invalid status
            )
        
        assert "status" in str(exc_info.value)
    
    def test_media_item_invalid_checksum_format(self):
        """Test that invalid checksum format raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            MediaItem(
                post_id="123",
                post_url="https://example.tumblr.com/post/123",
                timestamp=datetime.now(timezone.utc),
                media_type="image",
                filename="test.jpg",
                checksum="invalid_checksum",  # Not 64 hex chars
                original_url="https://example.com/test.jpg",
                retrieved_from="tumblr",
                status="downloaded"
            )
        
        assert "checksum" in str(exc_info.value)
    
    def test_media_item_negative_byte_size(self):
        """Test that negative byte_size raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            MediaItem(
                post_id="123",
                post_url="https://example.tumblr.com/post/123",
                timestamp=datetime.now(timezone.utc),
                media_type="image",
                filename="test.jpg",
                byte_size=-1000,  # Negative size
                original_url="https://example.com/test.jpg",
                retrieved_from="tumblr",
                status="downloaded"
            )
        
        assert "byte_size" in str(exc_info.value)
    
    def test_media_item_archive_url_required_for_archive_source(self):
        """Test that archive_snapshot_url is required when retrieved from Internet Archive."""
        with pytest.raises(ValidationError) as exc_info:
            MediaItem(
                post_id="123",
                post_url="https://example.tumblr.com/post/123",
                timestamp=datetime.now(timezone.utc),
                media_type="image",
                filename="test.jpg",
                original_url="https://example.com/test.jpg",
                retrieved_from="internet_archive",
                status="archived",
                archive_snapshot_url=None  # Should be required
            )
        
        assert "archive_snapshot_url" in str(exc_info.value)
    
    def test_media_item_archive_url_provided(self):
        """Test MediaItem from Internet Archive with snapshot URL."""
        media = MediaItem(
            post_id="123",
            post_url="https://example.tumblr.com/post/123",
            timestamp=datetime.now(timezone.utc),
            media_type="image",
            filename="test.jpg",
            original_url="https://example.com/test.jpg",
            retrieved_from="internet_archive",
            status="archived",
            archive_snapshot_url="https://web.archive.org/web/20240101/example.com"
        )
        
        assert media.retrieved_from == "internet_archive"
        assert media.archive_snapshot_url is not None
    
    def test_media_item_json_serialization(self):
        """Test MediaItem can be serialized to JSON."""
        media = MediaItem(
            post_id="123",
            post_url="https://example.tumblr.com/post/123",
            timestamp=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
            media_type="gif",
            filename="test.gif",
            original_url="https://example.com/test.gif",
            retrieved_from="tumblr",
            status="downloaded"
        )
        
        json_str = media.model_dump_json()
        assert isinstance(json_str, str)
        assert "123" in json_str
        assert "gif" in json_str
    
    def test_media_item_deserialization(self):
        """Test MediaItem can be deserialized from dict."""
        data = {
            "post_id": "123",
            "post_url": "https://example.tumblr.com/post/123",
            "timestamp": "2024-01-15T10:30:00Z",
            "media_type": "image",
            "filename": "test.jpg",
            "original_url": "https://example.com/test.jpg",
            "retrieved_from": "tumblr",
            "status": "downloaded"
        }
        
        media = MediaItem.model_validate(data)
        assert media.post_id == "123"
        assert media.media_type == "image"


class TestPost:
    """Tests for Post model."""
    
    def test_create_empty_post(self):
        """Test creating a Post with no media items."""
        post = Post(
            post_id="123",
            post_url="https://example.tumblr.com/post/123",
            timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
            is_reblog=False
        )
        
        assert post.post_id == "123"
        assert len(post.media_items) == 0
        assert not post.is_reblog
    
    def test_create_post_with_media(self):
        """Test creating a Post with media items."""
        media = MediaItem(
            post_id="123",
            post_url="https://example.tumblr.com/post/123",
            timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
            media_type="image",
            filename="test.jpg",
            original_url="https://example.com/test.jpg",
            retrieved_from="tumblr",
            status="downloaded"
        )
        
        post = Post(
            post_id="123",
            post_url="https://example.tumblr.com/post/123",
            timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
            is_reblog=True,
            media_items=[media]
        )
        
        assert len(post.media_items) == 1
        assert post.media_items[0].filename == "test.jpg"
        assert post.is_reblog
    
    def test_post_validates_media_post_ids(self):
        """Test that Post validates all MediaItems have matching post_id."""
        media = MediaItem(
            post_id="999",  # Mismatched ID
            post_url="https://example.tumblr.com/post/999",
            timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
            media_type="image",
            filename="test.jpg",
            original_url="https://example.com/test.jpg",
            retrieved_from="tumblr",
            status="downloaded"
        )
        
        with pytest.raises(ValidationError) as exc_info:
            Post(
                post_id="123",
                post_url="https://example.tumblr.com/post/123",
                timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
                is_reblog=False,
                media_items=[media]
            )
        
        assert "post_id" in str(exc_info.value).lower()
    
    def test_post_json_serialization(self):
        """Test Post can be serialized to JSON."""
        post = Post(
            post_id="123",
            post_url="https://example.tumblr.com/post/123",
            timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
            is_reblog=False
        )
        
        json_str = post.model_dump_json()
        assert isinstance(json_str, str)
        assert "123" in json_str


class TestManifest:
    """Tests for Manifest model."""
    
    def test_create_empty_manifest(self):
        """Test creating an empty Manifest."""
        manifest = Manifest(
            blog_name="example",
            blog_url="https://example.tumblr.com"
        )
        
        assert manifest.blog_name == "example"
        assert manifest.total_posts == 0
        assert manifest.total_media == 0
        assert len(manifest.posts) == 0
    
    def test_manifest_auto_syncs_totals(self):
        """Test that Manifest automatically syncs total counts."""
        media = MediaItem(
            post_id="123",
            post_url="https://example.tumblr.com/post/123",
            timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
            media_type="image",
            filename="test.jpg",
            original_url="https://example.com/test.jpg",
            retrieved_from="tumblr",
            status="downloaded"
        )
        
        post = Post(
            post_id="123",
            post_url="https://example.tumblr.com/post/123",
            timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
            is_reblog=False,
            media_items=[media]
        )
        
        manifest = Manifest(
            blog_name="example",
            blog_url="https://example.tumblr.com",
            posts=[post]
        )
        
        assert manifest.total_posts == 1
        assert manifest.total_media == 1
    
    def test_manifest_to_dict(self):
        """Test Manifest.to_dict() method."""
        manifest = Manifest(
            blog_name="example",
            blog_url="https://example.tumblr.com"
        )
        
        data = manifest.to_dict()
        assert isinstance(data, dict)
        assert data["blog_name"] == "example"
        assert "created_at" in data
        assert "posts" in data
    
    def test_manifest_from_dict(self):
        """Test Manifest.from_dict() class method."""
        data = {
            "blog_name": "example",
            "blog_url": "https://example.tumblr.com",
            "created_at": "2024-01-15T10:00:00Z",
            "last_updated": "2024-01-15T10:00:00Z",
            "total_posts": 0,
            "total_media": 0,
            "posts": []
        }
        
        manifest = Manifest.from_dict(data)
        assert manifest.blog_name == "example"
        assert isinstance(manifest, Manifest)
    
    def test_manifest_add_post(self):
        """Test Manifest.add_post() method."""
        manifest = Manifest(
            blog_name="example",
            blog_url="https://example.tumblr.com"
        )
        
        post = Post(
            post_id="123",
            post_url="https://example.tumblr.com/post/123",
            timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
            is_reblog=False
        )
        
        initial_updated = manifest.last_updated
        manifest.add_post(post)
        
        assert manifest.total_posts == 1
        assert len(manifest.posts) == 1
        assert manifest.last_updated >= initial_updated
    
    def test_manifest_add_duplicate_post(self):
        """Test that adding duplicate post_id raises ValueError."""
        manifest = Manifest(
            blog_name="example",
            blog_url="https://example.tumblr.com"
        )
        
        post1 = Post(
            post_id="123",
            post_url="https://example.tumblr.com/post/123",
            timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
            is_reblog=False
        )
        
        post2 = Post(
            post_id="123",  # Duplicate
            post_url="https://example.tumblr.com/post/123",
            timestamp=datetime(2024, 1, 16, tzinfo=timezone.utc),
            is_reblog=False
        )
        
        manifest.add_post(post1)
        
        with pytest.raises(ValueError) as exc_info:
            manifest.add_post(post2)
        
        assert "already exists" in str(exc_info.value)
    
    def test_manifest_get_media_by_status(self):
        """Test Manifest.get_media_by_status() method."""
        media1 = MediaItem(
            post_id="123",
            post_url="https://example.tumblr.com/post/123",
            timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
            media_type="image",
            filename="test1.jpg",
            original_url="https://example.com/test1.jpg",
            retrieved_from="tumblr",
            status="downloaded"
        )
        
        media2 = MediaItem(
            post_id="123",
            post_url="https://example.tumblr.com/post/123",
            timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
            media_type="image",
            filename="test2.jpg",
            original_url="https://example.com/test2.jpg",
            retrieved_from="tumblr",
            status="missing"
        )
        
        post = Post(
            post_id="123",
            post_url="https://example.tumblr.com/post/123",
            timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
            is_reblog=False,
            media_items=[media1, media2]
        )
        
        manifest = Manifest(
            blog_name="example",
            blog_url="https://example.tumblr.com",
            posts=[post]
        )
        
        downloaded = manifest.get_media_by_status("downloaded")
        missing = manifest.get_media_by_status("missing")
        
        assert len(downloaded) == 1
        assert len(missing) == 1
        assert downloaded[0].filename == "test1.jpg"
        assert missing[0].filename == "test2.jpg"
    
    def test_manifest_get_statistics(self):
        """Test Manifest.get_statistics() method."""
        media1 = MediaItem(
            post_id="123",
            post_url="https://example.tumblr.com/post/123",
            timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
            media_type="image",
            filename="test1.jpg",
            original_url="https://example.com/test1.jpg",
            retrieved_from="tumblr",
            status="downloaded"
        )
        
        media2 = MediaItem(
            post_id="456",
            post_url="https://example.tumblr.com/post/456",
            timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
            media_type="video",
            filename="test2.mp4",
            original_url="https://example.com/test2.mp4",
            retrieved_from="internet_archive",
            archive_snapshot_url="https://web.archive.org/web/20240101/example.com",
            status="archived"
        )
        
        post1 = Post(
            post_id="123",
            post_url="https://example.tumblr.com/post/123",
            timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
            is_reblog=False,
            media_items=[media1]
        )
        
        post2 = Post(
            post_id="456",
            post_url="https://example.tumblr.com/post/456",
            timestamp=datetime(2024, 1, 16, tzinfo=timezone.utc),
            is_reblog=True,
            media_items=[media2]
        )
        
        manifest = Manifest(
            blog_name="example",
            blog_url="https://example.tumblr.com",
            posts=[post1, post2]
        )
        
        stats = manifest.get_statistics()
        
        assert stats["total_posts"] == 2
        assert stats["total_media"] == 2
        assert stats["reblogs"] == 1
        assert stats["original_posts"] == 1
        assert stats["media_downloaded"] == 1
        assert stats["media_archived"] == 1
        assert stats["images"] == 1
        assert stats["videos"] == 1
        assert stats["from_tumblr"] == 1
        assert stats["from_internet_archive"] == 1
    
    def test_manifest_full_serialization_roundtrip(self):
        """Test complete serialization and deserialization cycle."""
        media = MediaItem(
            post_id="123",
            post_url="https://example.tumblr.com/post/123",
            timestamp=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
            media_type="image",
            filename="test.jpg",
            byte_size=1024,
            checksum="a" * 64,
            original_url="https://example.com/test.jpg",
            retrieved_from="tumblr",
            status="downloaded",
            notes="Test note"
        )
        
        post = Post(
            post_id="123",
            post_url="https://example.tumblr.com/post/123",
            timestamp=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
            is_reblog=False,
            media_items=[media]
        )
        
        original = Manifest(
            blog_name="example",
            blog_url="https://example.tumblr.com",
            posts=[post]
        )
        
        # Serialize to dict
        data = original.to_dict()
        
        # Deserialize back
        restored = Manifest.from_dict(data)
        
        assert restored.blog_name == original.blog_name
        assert restored.total_posts == original.total_posts
        assert restored.total_media == original.total_media
        assert len(restored.posts) == 1
        assert restored.posts[0].post_id == "123"
        assert len(restored.posts[0].media_items) == 1
        assert restored.posts[0].media_items[0].checksum == "a" * 64


class TestEdgeCases:
    """Tests for edge cases and error conditions."""
    
    def test_missing_required_fields(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            MediaItem(
                post_id="123",
                # Missing required fields
            )
    
    def test_invalid_enum_values(self):
        """Test that invalid enum values are rejected."""
        with pytest.raises(ValidationError):
            MediaItem(
                post_id="123",
                post_url="https://example.tumblr.com/post/123",
                timestamp=datetime.now(timezone.utc),
                media_type="document",  # Invalid
                filename="test.pdf",
                original_url="https://example.com/test.pdf",
                retrieved_from="tumblr",
                status="downloaded"
            )
    
    def test_manifest_with_multiple_posts_and_media(self):
        """Test Manifest with complex nested structure."""
        posts = []
        for i in range(5):
            media_items = []
            for j in range(3):
                media = MediaItem(
                    post_id=f"{i}",
                    post_url=f"https://example.tumblr.com/post/{i}",
                    timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
                    media_type="image",
                    filename=f"post{i}_media{j}.jpg",
                    original_url=f"https://example.com/post{i}_media{j}.jpg",
                    retrieved_from="tumblr",
                    status="downloaded"
                )
                media_items.append(media)
            
            post = Post(
                post_id=f"{i}",
                post_url=f"https://example.tumblr.com/post/{i}",
                timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
                is_reblog=i % 2 == 0,
                media_items=media_items
            )
            posts.append(post)
        
        manifest = Manifest(
            blog_name="example",
            blog_url="https://example.tumblr.com",
            posts=posts
        )
        
        assert manifest.total_posts == 5
        assert manifest.total_media == 15
        
        stats = manifest.get_statistics()
        assert stats["reblogs"] == 3
        assert stats["original_posts"] == 2
    
    def test_zero_byte_file_allowed(self):
        """Test that zero-byte files are allowed (but may trigger warnings in schema validation)."""
        media = MediaItem(
            post_id="123",
            post_url="https://example.tumblr.com/post/123",
            timestamp=datetime.now(timezone.utc),
            media_type="image",
            filename="empty.jpg",
            byte_size=0,  # Allowed but suspicious
            original_url="https://example.com/empty.jpg",
            retrieved_from="tumblr",
            status="downloaded"
        )
        
        assert media.byte_size == 0
    
    def test_manifest_dates_auto_generated(self):
        """Test that created_at and last_updated are auto-generated."""
        before = datetime.now(timezone.utc)
        
        manifest = Manifest(
            blog_name="example",
            blog_url="https://example.tumblr.com"
        )
        
        after = datetime.now(timezone.utc)
        
        assert before <= manifest.created_at <= after
        assert before <= manifest.last_updated <= after
