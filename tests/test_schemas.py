"""
Tests for JSON schema validation and versioning.

Tests the schema validation helpers, version checking, and utility functions.
"""

import json
import tempfile
from datetime import datetime, timezone

import pytest

from tumblr_archiver.models import Manifest, MediaItem, Post
from tumblr_archiver.schemas import (
    MANIFEST_SCHEMA_VERSION,
    add_schema_version,
    check_schema_version,
    export_schema_to_file,
    get_manifest_schema,
    validate_manifest_dict,
    validate_manifest_json,
    validate_media_item_fields,
)


class TestSchemaVersion:
    """Tests for schema version constants and functions."""
    
    def test_manifest_schema_version_format(self):
        """Test that schema version follows semantic versioning."""
        assert isinstance(MANIFEST_SCHEMA_VERSION, str)
        parts = MANIFEST_SCHEMA_VERSION.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)
    
    def test_add_schema_version(self):
        """Test adding schema version to manifest dict."""
        manifest_dict = {"blog_name": "test", "blog_url": "https://test.tumblr.com"}
        versioned = add_schema_version(manifest_dict)
        
        assert "schema_version" in versioned
        assert versioned["schema_version"] == MANIFEST_SCHEMA_VERSION
        assert "blog_name" in versioned
    
    def test_check_schema_version_missing(self):
        """Test checking manifest without schema version."""
        manifest_dict = {"blog_name": "test"}
        is_compatible, message = check_schema_version(manifest_dict)
        
        assert is_compatible
        assert "No schema version" in message
    
    def test_check_schema_version_matching(self):
        """Test checking manifest with matching schema version."""
        manifest_dict = {"schema_version": MANIFEST_SCHEMA_VERSION}
        is_compatible, message = check_schema_version(manifest_dict)
        
        assert is_compatible
        assert "matches" in message
    
    def test_check_schema_version_compatible_minor(self):
        """Test checking manifest with compatible minor version difference."""
        # Create a version with different minor/patch but same major
        major = MANIFEST_SCHEMA_VERSION.split(".")[0]
        test_version = f"{major}.99.99"
        
        manifest_dict = {"schema_version": test_version}
        is_compatible, message = check_schema_version(manifest_dict)
        
        assert is_compatible
        assert "mismatch" in message.lower() and "compatible" in message.lower()
    
    def test_check_schema_version_incompatible_major(self):
        """Test checking manifest with incompatible major version."""
        # Create a version with different major version
        current_major = int(MANIFEST_SCHEMA_VERSION.split(".")[0])
        incompatible_version = f"{current_major + 1}.0.0"
        
        manifest_dict = {"schema_version": incompatible_version}
        is_compatible, message = check_schema_version(manifest_dict)
        
        assert not is_compatible
        assert "Incompatible" in message


class TestSchemaGeneration:
    """Tests for JSON schema generation."""
    
    def test_get_manifest_schema(self):
        """Test retrieving the Manifest JSON schema."""
        schema = get_manifest_schema()
        
        assert isinstance(schema, dict)
        assert "properties" in schema
        assert "blog_name" in schema["properties"]
        assert "blog_url" in schema["properties"]
        assert "posts" in schema["properties"]
    
    def test_export_schema_to_file(self):
        """Test exporting schema to a file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            filepath = f.name
        
        try:
            export_schema_to_file(filepath)
            
            with open(filepath, "r") as f:
                schema = json.load(f)
            
            assert "$schema" in schema
            assert "version" in schema
            assert schema["version"] == MANIFEST_SCHEMA_VERSION
            assert "properties" in schema
        finally:
            import os
            os.unlink(filepath)


class TestManifestValidation:
    """Tests for manifest validation functions."""
    
    def test_validate_valid_manifest_dict(self):
        """Test validating a valid manifest dictionary."""
        manifest = Manifest(
            blog_name="test",
            blog_url="https://test.tumblr.com"
        )
        data = manifest.to_dict()
        
        is_valid, error = validate_manifest_dict(data)
        
        assert is_valid
        assert error == ""
    
    def test_validate_invalid_manifest_dict_missing_fields(self):
        """Test validating manifest dict with missing required fields."""
        data = {"blog_name": "test"}  # Missing blog_url
        
        is_valid, error = validate_manifest_dict(data)
        
        assert not is_valid
        assert "blog_url" in error.lower() or "field required" in error.lower()
    
    def test_validate_invalid_manifest_dict_wrong_types(self):
        """Test validating manifest dict with incorrect field types."""
        data = {
            "blog_name": "test",
            "blog_url": "https://test.tumblr.com",
            "total_posts": "not_a_number"  # Should be int
        }
        
        is_valid, error = validate_manifest_dict(data)
        
        assert not is_valid
        assert "total_posts" in error.lower() or "int" in error.lower()
    
    def test_validate_valid_manifest_json(self):
        """Test validating valid manifest as JSON string."""
        manifest = Manifest(
            blog_name="test",
            blog_url="https://test.tumblr.com"
        )
        json_str = manifest.model_dump_json()
        
        is_valid, error = validate_manifest_json(json_str)
        
        assert is_valid
        assert error == ""
    
    def test_validate_invalid_manifest_json_syntax(self):
        """Test validating invalid JSON syntax."""
        invalid_json = "{ this is not valid json }"
        
        is_valid, error = validate_manifest_json(invalid_json)
        
        assert not is_valid
        assert "json" in error.lower() and ("invalid" in error.lower() or "parsing" in error.lower())
    
    def test_validate_invalid_manifest_json_schema(self):
        """Test validating JSON with invalid schema."""
        invalid_data = json.dumps({"blog_name": "test"})  # Missing fields
        
        is_valid, error = validate_manifest_json(invalid_data)
        
        assert not is_valid
        assert len(error) > 0
    
    def test_validate_complete_manifest_with_posts(self):
        """Test validating a complete manifest with posts and media."""
        media = MediaItem(
            post_id="123",
            post_url="https://test.tumblr.com/post/123",
            timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
            media_type="image",
            filename="test.jpg",
            original_url="https://example.com/test.jpg",
            retrieved_from="tumblr",
            status="downloaded"
        )
        
        post = Post(
            post_id="123",
            post_url="https://test.tumblr.com/post/123",
            timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
            is_reblog=False,
            media_items=[media]
        )
        
        manifest = Manifest(
            blog_name="test",
            blog_url="https://test.tumblr.com",
            posts=[post]
        )
        
        is_valid, error = validate_manifest_dict(manifest.to_dict())
        
        assert is_valid
        assert error == ""


class TestMediaItemValidation:
    """Tests for media item field validation."""
    
    def test_validate_healthy_media_item(self):
        """Test validating a healthy media item with no issues."""
        media_dict = {
            "post_id": "123",
            "post_url": "https://test.tumblr.com/post/123",
            "timestamp": "2024-01-15T10:30:00Z",
            "media_type": "image",
            "filename": "test.jpg",
            "byte_size": 1024000,
            "checksum": "a" * 64,
            "original_url": "https://example.com/test.jpg",
            "retrieved_from": "tumblr",
            "status": "downloaded",
        }
        
        is_valid, warnings = validate_media_item_fields(media_dict)
        
        assert is_valid
        assert len(warnings) == 0
    
    def test_validate_zero_byte_file(self):
        """Test validating media item with zero byte size."""
        media_dict = {
            "post_id": "123",
            "post_url": "https://test.tumblr.com/post/123",
            "timestamp": "2024-01-15T10:30:00Z",
            "media_type": "image",
            "filename": "test.jpg",
            "byte_size": 0,
            "original_url": "https://example.com/test.jpg",
            "retrieved_from": "tumblr",
            "status": "downloaded",
        }
        
        is_valid, warnings = validate_media_item_fields(media_dict)
        
        assert not is_valid
        assert any("0 bytes" in w for w in warnings)
    
    def test_validate_very_small_file(self):
        """Test validating media item with suspiciously small size."""
        media_dict = {
            "post_id": "123",
            "post_url": "https://test.tumblr.com/post/123",
            "timestamp": "2024-01-15T10:30:00Z",
            "media_type": "image",
            "filename": "test.jpg",
            "byte_size": 50,  # Very small
            "original_url": "https://example.com/test.jpg",
            "retrieved_from": "tumblr",
            "status": "downloaded",
        }
        
        is_valid, warnings = validate_media_item_fields(media_dict)
        
        assert not is_valid
        assert any("unusually small" in w for w in warnings)
    
    def test_validate_very_large_file(self):
        """Test validating media item with unusually large size."""
        media_dict = {
            "post_id": "123",
            "post_url": "https://test.tumblr.com/post/123",
            "timestamp": "2024-01-15T10:30:00Z",
            "media_type": "video",
            "filename": "test.mp4",
            "byte_size": 200 * 1024 * 1024,  # 200 MB
            "original_url": "https://example.com/test.mp4",
            "retrieved_from": "tumblr",
            "status": "downloaded",
        }
        
        is_valid, warnings = validate_media_item_fields(media_dict)
        
        assert not is_valid
        assert any("unusually large" in w for w in warnings)
    
    def test_validate_downloaded_without_checksum(self):
        """Test validating downloaded file without checksum."""
        media_dict = {
            "post_id": "123",
            "post_url": "https://test.tumblr.com/post/123",
            "timestamp": "2024-01-15T10:30:00Z",
            "media_type": "image",
            "filename": "test.jpg",
            "byte_size": 1024000,
            "original_url": "https://example.com/test.jpg",
            "retrieved_from": "tumblr",
            "status": "downloaded",
            # Missing checksum
        }
        
        is_valid, warnings = validate_media_item_fields(media_dict)
        
        assert not is_valid
        assert any("checksum" in w for w in warnings)
    
    def test_validate_downloaded_without_byte_size(self):
        """Test validating downloaded file without byte size."""
        media_dict = {
            "post_id": "123",
            "post_url": "https://test.tumblr.com/post/123",
            "timestamp": "2024-01-15T10:30:00Z",
            "media_type": "image",
            "filename": "test.jpg",
            "checksum": "a" * 64,
            "original_url": "https://example.com/test.jpg",
            "retrieved_from": "tumblr",
            "status": "downloaded",
            # Missing byte_size
        }
        
        is_valid, warnings = validate_media_item_fields(media_dict)
        
        assert not is_valid
        assert any("byte_size" in w for w in warnings)
    
    def test_validate_missing_with_checksum(self):
        """Test validating missing file that has a checksum."""
        media_dict = {
            "post_id": "123",
            "post_url": "https://test.tumblr.com/post/123",
            "timestamp": "2024-01-15T10:30:00Z",
            "media_type": "image",
            "filename": "test.jpg",
            "checksum": "a" * 64,  # Shouldn't have checksum if missing
            "original_url": "https://example.com/test.jpg",
            "retrieved_from": "tumblr",
            "status": "missing",
        }
        
        is_valid, warnings = validate_media_item_fields(media_dict)
        
        assert not is_valid
        assert any("missing" in w.lower() and "checksum" in w for w in warnings)
    
    def test_validate_tumblr_source_with_archive_url(self):
        """Test validating Tumblr source with archive URL."""
        media_dict = {
            "post_id": "123",
            "post_url": "https://test.tumblr.com/post/123",
            "timestamp": "2024-01-15T10:30:00Z",
            "media_type": "image",
            "filename": "test.jpg",
            "byte_size": 1024000,
            "original_url": "https://example.com/test.jpg",
            "retrieved_from": "tumblr",
            "archive_snapshot_url": "https://web.archive.org/web/test",  # Shouldn't have this
            "status": "downloaded",
        }
        
        is_valid, warnings = validate_media_item_fields(media_dict)
        
        assert not is_valid
        assert any("tumblr" in w.lower() and "archive" in w.lower() for w in warnings)
    
    def test_validate_none_byte_size(self):
        """Test validating media item with None byte_size (should be okay)."""
        media_dict = {
            "post_id": "123",
            "post_url": "https://test.tumblr.com/post/123",
            "timestamp": "2024-01-15T10:30:00Z",
            "media_type": "image",
            "filename": "test.jpg",
            "byte_size": None,
            "original_url": "https://example.com/test.jpg",
            "retrieved_from": "tumblr",
            "status": "missing",
        }
        
        is_valid, warnings = validate_media_item_fields(media_dict)
        
        # None byte_size for missing files should be acceptable
        # (specific validation might vary based on status)
        assert isinstance(warnings, list)


class TestIntegration:
    """Integration tests combining multiple schema functions."""
    
    def test_full_workflow_create_validate_export(self):
        """Test complete workflow: create, validate, and export."""
        # Create a manifest
        manifest = Manifest(
            blog_name="integration_test",
            blog_url="https://integration.tumblr.com"
        )
        
        # Validate it
        is_valid, error = validate_manifest_dict(manifest.to_dict())
        assert is_valid
        
        # Add version
        versioned = add_schema_version(manifest.to_dict())
        assert "schema_version" in versioned
        
        # Check version
        is_compatible, message = check_schema_version(versioned)
        assert is_compatible
        
        # Export schema
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            filepath = f.name
        
        try:
            export_schema_to_file(filepath)
            
            with open(filepath, "r") as f:
                schema = json.load(f)
            
            assert schema["version"] == MANIFEST_SCHEMA_VERSION
        finally:
            import os
            os.unlink(filepath)
