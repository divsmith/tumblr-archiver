"""
Tests for the manifest management system.
"""

import json
import os
import tempfile
from pathlib import Path
from datetime import datetime

import pytest

from tumblr_archiver.manifest import (
    ManifestManager,
    ManifestError,
    ManifestValidationError,
    calculate_checksum,
    validate_manifest,
    create_media_entry,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def manifest_path(temp_dir):
    """Return a path for a test manifest file."""
    return temp_dir / "manifest.json"


@pytest.fixture
def manager(manifest_path):
    """Create a ManifestManager instance."""
    manager = ManifestManager(manifest_path)
    manager.load()
    manager.set_blog_info(
        blog_url="https://example.tumblr.com",
        blog_name="example",
        total_posts=100
    )
    return manager


class TestManifestManager:
    """Tests for the ManifestManager class."""
    
    def test_init(self, manifest_path):
        """Test ManifestManager initialization."""
        manager = ManifestManager(manifest_path)
        assert manager.manifest_path == manifest_path
        assert manager.data == {}
    
    def test_load_new_manifest(self, manifest_path):
        """Test loading when no manifest exists."""
        manager = ManifestManager(manifest_path)
        data = manager.load()
        
        assert "blog_url" in data
        assert "blog_name" in data
        assert "archive_date" in data
        assert "total_posts" in data
        assert "total_media" in data
        assert "media" in data
        assert data["media"] == []
    
    def test_load_existing_manifest(self, manifest_path):
        """Test loading an existing valid manifest."""
        # Create a manifest file
        test_data = {
            "blog_url": "https://test.tumblr.com",
            "blog_name": "test",
            "archive_date": "2026-02-13T10:00:00Z",
            "total_posts": 50,
            "total_media": 0,
            "media": []
        }
        with open(manifest_path, 'w') as f:
            json.dump(test_data, f)
        
        manager = ManifestManager(manifest_path)
        data = manager.load()
        
        assert data["blog_name"] == "test"
        assert data["total_posts"] == 50
    
    def test_load_corrupted_manifest(self, manifest_path):
        """Test loading a corrupted manifest creates backup."""
        # Create a corrupted manifest file
        with open(manifest_path, 'w') as f:
            f.write("{ invalid json }")
        
        manager = ManifestManager(manifest_path)
        data = manager.load()
        
        # Should have created backup and new manifest
        backup_path = manifest_path.with_suffix('.json.backup')
        assert backup_path.exists()
        assert "media" in data
        assert data["media"] == []
    
    def test_save(self, manifest_path):
        """Test saving manifest to disk."""
        manager = ManifestManager(manifest_path)
        manager.load()
        manager.set_blog_info(
            blog_url="https://test.tumblr.com",
            blog_name="test"
        )
        manager.save()
        
        assert manifest_path.exists()
        
        # Verify content
        with open(manifest_path, 'r') as f:
            data = json.load(f)
        assert data["blog_name"] == "test"
    
    def test_save_atomic(self, manifest_path, monkeypatch):
        """Test that save uses atomic write."""
        manager = ManifestManager(manifest_path)
        manager.load()
        manager.set_blog_info(blog_url="https://test.tumblr.com", blog_name="test")
        
        # Check that temp file is created during save
        temp_path = manifest_path.with_suffix('.json.tmp')
        
        manager.save()
        
        # Temp file should be cleaned up
        assert not temp_path.exists()
        assert manifest_path.exists()
    
    def test_add_media(self, manager):
        """Test adding a media entry."""
        media_entry = create_media_entry(
            post_id="12345",
            post_url="https://example.tumblr.com/post/12345",
            timestamp="2023-05-15T14:20:00Z",
            media_type="image",
            filename="test.jpg",
            original_url="https://64.media.tumblr.com/test.jpg",
            api_media_urls=["https://64.media.tumblr.com/test.jpg"],
            byte_size=100000,
            checksum="abc123",
            status="downloaded"
        )
        
        manager.add_media(media_entry)
        
        assert len(manager.data["media"]) == 1
        assert manager.data["total_media"] == 1
        assert manager.data["media"][0]["post_id"] == "12345"
    
    def test_add_media_missing_fields(self, manager):
        """Test adding media with missing required fields raises error."""
        incomplete_entry = {
            "post_id": "12345",
            "filename": "test.jpg"
        }
        
        with pytest.raises(ManifestValidationError):
            manager.add_media(incomplete_entry)
    
    def test_update_media(self, manager):
        """Test updating an existing media entry."""
        media_entry = create_media_entry(
            post_id="12345",
            post_url="https://example.tumblr.com/post/12345",
            timestamp="2023-05-15T14:20:00Z",
            media_type="image",
            filename="test.jpg",
            original_url="https://64.media.tumblr.com/test.jpg",
            api_media_urls=["https://64.media.tumblr.com/test.jpg"],
            status="pending"
        )
        manager.add_media(media_entry)
        
        updated = manager.update_media(
            "12345",
            "test.jpg",
            {"status": "downloaded", "byte_size": 200000}
        )
        
        assert updated is True
        entry = manager.get_media("12345", "test.jpg")
        assert entry["status"] == "downloaded"
        assert entry["byte_size"] == 200000
    
    def test_update_media_not_found(self, manager):
        """Test updating non-existent media returns False."""
        updated = manager.update_media("99999", "nonexistent.jpg", {"status": "failed"})
        assert updated is False
    
    def test_get_media(self, manager):
        """Test retrieving a media entry."""
        media_entry = create_media_entry(
            post_id="12345",
            post_url="https://example.tumblr.com/post/12345",
            timestamp="2023-05-15T14:20:00Z",
            media_type="image",
            filename="test.jpg",
            original_url="https://64.media.tumblr.com/test.jpg",
            api_media_urls=["https://64.media.tumblr.com/test.jpg"]
        )
        manager.add_media(media_entry)
        
        entry = manager.get_media("12345", "test.jpg")
        
        assert entry is not None
        assert entry["post_id"] == "12345"
        assert entry["filename"] == "test.jpg"
    
    def test_get_media_not_found(self, manager):
        """Test retrieving non-existent media returns None."""
        entry = manager.get_media("99999", "nonexistent.jpg")
        assert entry is None
    
    def test_is_downloaded(self, manager):
        """Test checking if media is downloaded."""
        media_entry = create_media_entry(
            post_id="12345",
            post_url="https://example.tumblr.com/post/12345",
            timestamp="2023-05-15T14:20:00Z",
            media_type="image",
            filename="test.jpg",
            original_url="https://64.media.tumblr.com/test.jpg",
            api_media_urls=["https://64.media.tumblr.com/test.jpg"],
            status="downloaded"
        )
        manager.add_media(media_entry)
        
        assert manager.is_downloaded("12345", "test.jpg") is True
    
    def test_is_downloaded_with_file_verification(self, manager, temp_dir):
        """Test checking if media is downloaded with file verification."""
        # Create a test file
        test_file = temp_dir / "test.jpg"
        test_file.write_text("test content")
        checksum = calculate_checksum(test_file)
        
        media_entry = create_media_entry(
            post_id="12345",
            post_url="https://example.tumblr.com/post/12345",
            timestamp="2023-05-15T14:20:00Z",
            media_type="image",
            filename="test.jpg",
            original_url="https://64.media.tumblr.com/test.jpg",
            api_media_urls=["https://64.media.tumblr.com/test.jpg"],
            checksum=checksum,
            status="downloaded"
        )
        manager.add_media(media_entry)
        
        assert manager.is_downloaded("12345", "test.jpg", test_file) is True
    
    def test_is_downloaded_checksum_mismatch(self, manager, temp_dir):
        """Test that checksum mismatch returns False."""
        test_file = temp_dir / "test.jpg"
        test_file.write_text("test content")
        
        media_entry = create_media_entry(
            post_id="12345",
            post_url="https://example.tumblr.com/post/12345",
            timestamp="2023-05-15T14:20:00Z",
            media_type="image",
            filename="test.jpg",
            original_url="https://64.media.tumblr.com/test.jpg",
            api_media_urls=["https://64.media.tumblr.com/test.jpg"],
            checksum="wrongchecksum123",
            status="downloaded"
        )
        manager.add_media(media_entry)
        
        assert manager.is_downloaded("12345", "test.jpg", test_file) is False
    
    def test_is_downloaded_pending_status(self, manager):
        """Test that pending status returns False."""
        media_entry = create_media_entry(
            post_id="12345",
            post_url="https://example.tumblr.com/post/12345",
            timestamp="2023-05-15T14:20:00Z",
            media_type="image",
            filename="test.jpg",
            original_url="https://64.media.tumblr.com/test.jpg",
            api_media_urls=["https://64.media.tumblr.com/test.jpg"],
            status="pending"
        )
        manager.add_media(media_entry)
        
        assert manager.is_downloaded("12345", "test.jpg") is False
    
    def test_mark_status(self, manager):
        """Test marking media status."""
        media_entry = create_media_entry(
            post_id="12345",
            post_url="https://example.tumblr.com/post/12345",
            timestamp="2023-05-15T14:20:00Z",
            media_type="image",
            filename="test.jpg",
            original_url="https://64.media.tumblr.com/test.jpg",
            api_media_urls=["https://64.media.tumblr.com/test.jpg"],
            status="pending"
        )
        manager.add_media(media_entry)
        
        success = manager.mark_status("12345", "test.jpg", "downloaded")
        
        assert success is True
        entry = manager.get_media("12345", "test.jpg")
        assert entry["status"] == "downloaded"
    
    def test_mark_status_with_notes(self, manager):
        """Test marking status with notes."""
        media_entry = create_media_entry(
            post_id="12345",
            post_url="https://example.tumblr.com/post/12345",
            timestamp="2023-05-15T14:20:00Z",
            media_type="image",
            filename="test.jpg",
            original_url="https://64.media.tumblr.com/test.jpg",
            api_media_urls=["https://64.media.tumblr.com/test.jpg"],
            status="pending"
        )
        manager.add_media(media_entry)
        
        manager.mark_status("12345", "test.jpg", "failed", "Network error")
        
        entry = manager.get_media("12345", "test.jpg")
        assert entry["status"] == "failed"
        assert entry["notes"] == "Network error"
    
    def test_mark_status_invalid(self, manager):
        """Test marking with invalid status raises error."""
        media_entry = create_media_entry(
            post_id="12345",
            post_url="https://example.tumblr.com/post/12345",
            timestamp="2023-05-15T14:20:00Z",
            media_type="image",
            filename="test.jpg",
            original_url="https://64.media.tumblr.com/test.jpg",
            api_media_urls=["https://64.media.tumblr.com/test.jpg"]
        )
        manager.add_media(media_entry)
        
        with pytest.raises(ValueError):
            manager.mark_status("12345", "test.jpg", "invalid_status")
    
    def test_get_stats(self, manager):
        """Test getting statistics."""
        # Add some media entries
        for i in range(5):
            entry = create_media_entry(
                post_id=str(i),
                post_url=f"https://example.tumblr.com/post/{i}",
                timestamp="2023-05-15T14:20:00Z",
                media_type="image" if i < 3 else "video",
                filename=f"test{i}.jpg",
                original_url=f"https://64.media.tumblr.com/test{i}.jpg",
                api_media_urls=[f"https://64.media.tumblr.com/test{i}.jpg"],
                byte_size=100000 * (i + 1),
                checksum=f"checksum{i}",
                status="downloaded" if i < 3 else "pending"
            )
            manager.add_media(entry)
        
        stats = manager.get_stats()
        
        assert stats["total_media"] == 5
        assert stats["unique_media"] == 5
        assert stats["status_breakdown"]["downloaded"] == 3
        assert stats["status_breakdown"]["pending"] == 2
        assert stats["media_type_breakdown"]["image"] == 3
        assert stats["media_type_breakdown"]["video"] == 2
        assert stats["total_bytes"] == 1500000  # 100k + 200k + 300k + 400k + 500k
    
    def test_deduplicate_media(self, manager):
        """Test finding duplicate media."""
        # Add entries with duplicate checksums
        same_checksum = "sha256:duplicate123"
        
        for i in range(3):
            entry = create_media_entry(
                post_id=str(i),
                post_url=f"https://example.tumblr.com/post/{i}",
                timestamp="2023-05-15T14:20:00Z",
                media_type="image",
                filename=f"test{i}.jpg",
                original_url=f"https://64.media.tumblr.com/test{i}.jpg",
                api_media_urls=[f"https://64.media.tumblr.com/test{i}.jpg"],
                byte_size=100000,
                checksum=same_checksum,
                status="downloaded"
            )
            manager.add_media(entry)
        
        # Add a unique one
        unique_entry = create_media_entry(
            post_id="999",
            post_url="https://example.tumblr.com/post/999",
            timestamp="2023-05-15T14:20:00Z",
            media_type="image",
            filename="unique.jpg",
            original_url="https://64.media.tumblr.com/unique.jpg",
            api_media_urls=["https://64.media.tumblr.com/unique.jpg"],
            checksum="sha256:unique456",
            status="downloaded"
        )
        manager.add_media(unique_entry)
        
        duplicates = manager.deduplicate_media()
        
        assert len(duplicates) == 1
        assert duplicates[0]["checksum"] == same_checksum
        assert duplicates[0]["total_instances"] == 3
        assert duplicates[0]["can_deduplicate"] is True
    
    def test_set_blog_info(self, manager):
        """Test setting blog information."""
        manager.set_blog_info(
            blog_url="https://newblog.tumblr.com",
            blog_name="newblog",
            total_posts=250
        )
        
        assert manager.data["blog_url"] == "https://newblog.tumblr.com"
        assert manager.data["blog_name"] == "newblog"
        assert manager.data["total_posts"] == 250


class TestHelperFunctions:
    """Tests for helper functions."""
    
    def test_calculate_checksum(self, temp_dir):
        """Test calculating file checksum."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!")
        
        checksum = calculate_checksum(test_file)
        
        assert isinstance(checksum, str)
        assert len(checksum) == 64  # SHA256 hex digest length
        
        # Verify it's deterministic
        checksum2 = calculate_checksum(test_file)
        assert checksum == checksum2
    
    def test_calculate_checksum_large_file(self, temp_dir):
        """Test calculating checksum for large file."""
        test_file = temp_dir / "large.bin"
        # Create a 1MB file
        test_file.write_bytes(b"0" * (1024 * 1024))
        
        checksum = calculate_checksum(test_file)
        
        assert isinstance(checksum, str)
        assert len(checksum) == 64
    
    def test_calculate_checksum_nonexistent(self, temp_dir):
        """Test calculating checksum for non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            calculate_checksum(temp_dir / "nonexistent.txt")
    
    def test_validate_manifest_valid(self):
        """Test validating a valid manifest."""
        manifest = {
            "blog_url": "https://example.tumblr.com",
            "blog_name": "example",
            "archive_date": "2026-02-13T10:00:00Z",
            "total_posts": 100,
            "total_media": 1,
            "media": [
                create_media_entry(
                    post_id="12345",
                    post_url="https://example.tumblr.com/post/12345",
                    timestamp="2023-05-15T14:20:00Z",
                    media_type="image",
                    filename="test.jpg",
                    original_url="https://64.media.tumblr.com/test.jpg",
                    api_media_urls=["https://64.media.tumblr.com/test.jpg"]
                )
            ]
        }
        
        # Should not raise
        validate_manifest(manifest)
    
    def test_validate_manifest_missing_fields(self):
        """Test validating manifest with missing fields."""
        manifest = {
            "blog_url": "https://example.tumblr.com",
            "blog_name": "example"
            # Missing other required fields
        }
        
        with pytest.raises(ManifestValidationError):
            validate_manifest(manifest)
    
    def test_validate_manifest_wrong_types(self):
        """Test validating manifest with wrong types."""
        manifest = {
            "blog_url": "https://example.tumblr.com",
            "blog_name": "example",
            "archive_date": "2026-02-13T10:00:00Z",
            "total_posts": "100",  # Should be int
            "total_media": 0,
            "media": []
        }
        
        with pytest.raises(ManifestValidationError):
            validate_manifest(manifest)
    
    def test_create_media_entry(self):
        """Test creating a media entry."""
        entry = create_media_entry(
            post_id="12345",
            post_url="https://example.tumblr.com/post/12345",
            timestamp="2023-05-15T14:20:00Z",
            media_type="image",
            filename="test.jpg",
            original_url="https://64.media.tumblr.com/test.jpg",
            api_media_urls=["https://64.media.tumblr.com/test.jpg"],
            byte_size=100000,
            checksum="abc123",
            status="downloaded"
        )
        
        assert entry["post_id"] == "12345"
        assert entry["filename"] == "test.jpg"
        assert entry["byte_size"] == 100000
        assert entry["checksum"] == "sha256:abc123"  # Should add prefix
        assert entry["status"] == "downloaded"
    
    def test_create_media_entry_with_checksum_prefix(self):
        """Test creating entry with checksum that already has prefix."""
        entry = create_media_entry(
            post_id="12345",
            post_url="https://example.tumblr.com/post/12345",
            timestamp="2023-05-15T14:20:00Z",
            media_type="image",
            filename="test.jpg",
            original_url="https://64.media.tumblr.com/test.jpg",
            api_media_urls=["https://64.media.tumblr.com/test.jpg"],
            checksum="sha256:abc123"
        )
        
        # Should not double-prefix
        assert entry["checksum"] == "sha256:abc123"
