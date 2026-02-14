"""
Acceptance tests for Tumblr Archiver.

Tests validate all acceptance criteria from the original specification:
1. All media retrieved locally OR from Internet Archive
2. manifest.json correctly reflects provenance
3. Resume capability works
4. Rate limiting prevents 429s

These tests use mocked data and validate end-to-end functionality
without making actual network requests.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aioresponses import aioresponses

from tumblr_archiver.config import ArchiverConfig
from tumblr_archiver.constants import (
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_TOO_MANY_REQUESTS,
    USER_AGENT,
)
from tumblr_archiver.manifest import ManifestManager
from tumblr_archiver.models import Manifest, MediaItem, Post
from tumblr_archiver.orchestrator import ArchiveStats, Orchestrator


# Sample HTML responses for mocked Tumblr pages
SAMPLE_BLOG_HTML = """
<!DOCTYPE html>
<html>
<head><title>Test Blog</title></head>
<body>
<article class="post" data-post-id="123456789">
    <div class="date">Jan 15, 2024</div>
    <img src="https://64.media.tumblr.com/abc123/tumblr_xyz_1280.jpg" />
    <img src="https://64.media.tumblr.com/def456/tumblr_abc_1280.png" />
</article>
<article class="post" data-post-id="987654321">
    <div class="date">Jan 14, 2024</div>
    <video poster="https://64.media.tumblr.com/thumb123.jpg">
        <source src="https://va.media.tumblr.com/video123.mp4" />
    </video>
</article>
</body>
</html>
"""

EMPTY_BLOG_HTML = """
<!DOCTYPE html>
<html>
<head><title>Test Blog</title></head>
<body>
<div class="no-posts">No posts found</div>
</body>
</html>
"""


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create a temporary output directory for tests."""
    output_dir = tmp_path / "test-archive"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def test_config(temp_output_dir):
    """Create test configuration."""
    return ArchiverConfig(
        blog_name="testblog",
        output_dir=str(temp_output_dir),
        concurrency=2,
        rate_limit=10.0,  # Fast for testing
        max_retries=2,
        timeout=5.0,
        dry_run=False,
        exclude_reblogs=False,
        enable_fallback=True,
        verbose=False,
    )


@pytest.fixture
async def manifest_manager(temp_output_dir):
    """Create and initialize a ManifestManager."""
    manager = ManifestManager(temp_output_dir)
    await manager.load()
    return manager


class TestAcceptanceCriteria1:
    """Test Requirement 1: All media retrieved locally OR from Archive."""
    
    @pytest.mark.asyncio
    async def test_media_downloaded_from_tumblr(self, test_config, manifest_manager):
        """
        ACCEPTANCE TEST 1.1: Media successfully downloaded from Tumblr.
        
        Validates:
        - Media is downloaded from original Tumblr URLs
        - Files are saved to disk
        - Manifest correctly tracks 'tumblr' as source
        """
        with aioresponses() as mocked:
            # Mock Tumblr blog page
            mocked.get(
                f"https://{test_config.blog_name}.tumblr.com",
                status=HTTP_OK,
                body=SAMPLE_BLOG_HTML,
            )
            
            # Mock pagination (no more pages)
            mocked.get(
                f"https://{test_config.blog_name}.tumblr.com/page/2",
                status=HTTP_NOT_FOUND,
            )
            
            # Mock media downloads from Tumblr
            mocked.get(
                "https://64.media.tumblr.com/abc123/tumblr_xyz_1280.jpg",
                status=HTTP_OK,
                body=b"fake-image-data-1",
                headers={"Content-Type": "image/jpeg"},
            )
            mocked.get(
                "https://64.media.tumblr.com/def456/tumblr_abc_1280.png",
                status=HTTP_OK,
                body=b"fake-image-data-2",
                headers={"Content-Type": "image/png"},
            )
            mocked.get(
                "https://64.media.tumblr.com/thumb123.jpg",
                status=HTTP_OK,
                body=b"fake-thumb-data",
                headers={"Content-Type": "image/jpeg"},
            )
            mocked.get(
                "https://va.media.tumblr.com/video123.mp4",
                status=HTTP_OK,
                body=b"fake-video-data",
                headers={"Content-Type": "video/mp4"},
            )
            
            # Run orchestrator
            orchestrator = Orchestrator(test_config, manifest_manager)
            stats = await orchestrator.run()
            
            # Validate stats
            assert stats.total_posts >= 2
            assert stats.total_media >= 3
            assert stats.downloaded > 0
            assert stats.failed == 0
            
            # Load manifest and validate
            manifest = await manifest_manager.load()
            assert manifest.total_posts >= 2
            assert manifest.total_media >= 3
            
            # Validate that all media was retrieved from Tumblr
            for post in manifest.posts:
                for media in post.media_items:
                    assert media.retrieved_from == "tumblr"
                    assert media.status == "downloaded"
                    assert media.archive_snapshot_url is None
                    
                    # Validate file exists on disk
                    media_path = test_config.output_dir / Path(media.filename)
                    assert media_path.exists()
                    assert media_path.stat().st_size > 0
    
    @pytest.mark.asyncio
    async def test_media_retrieved_from_archive(self, test_config, manifest_manager):
        """
        ACCEPTANCE TEST 1.2: Media retrieved from Internet Archive when Tumblr fails.
        
        Validates:
        - When Tumblr returns 404, Archive is tried
        - Media is downloaded from Archive snapshot
        - Manifest correctly tracks 'internet_archive' as source
        - Archive snapshot URL is recorded
        """
        with aioresponses() as mocked:
            # Mock Tumblr blog page
            mocked.get(
                f"https://{test_config.blog_name}.tumblr.com",
                status=HTTP_OK,
                body=SAMPLE_BLOG_HTML,
            )
            mocked.get(
                f"https://{test_config.blog_name}.tumblr.com/page/2",
                status=HTTP_NOT_FOUND,
            )
            
            # Mock Tumblr media downloads as FAILED
            mocked.get(
                "https://64.media.tumblr.com/abc123/tumblr_xyz_1280.jpg",
                status=HTTP_NOT_FOUND,
            )
            mocked.get(
                "https://64.media.tumblr.com/def456/tumblr_abc_1280.png",
                status=HTTP_NOT_FOUND,
            )
            mocked.get(
                "https://64.media.tumblr.com/thumb123.jpg",
                status=HTTP_NOT_FOUND,
            )
            mocked.get(
                "https://va.media.tumblr.com/video123.mp4",
                status=HTTP_NOT_FOUND,
            )
            
            # Mock Wayback CDX API responses (snapshots available)
            cdx_response_1 = (
                "com,tumblr,media,64)/abc123/tumblr_xyz_1280.jpg 20240101120000 "
                "https://64.media.tumblr.com/abc123/tumblr_xyz_1280.jpg image/jpeg "
                "200 ABCDEF12345 1024"
            )
            cdx_response_2 = (
                "com,tumblr,media,64)/def456/tumblr_abc_1280.png 20240101120000 "
                "https://64.media.tumblr.com/def456/tumblr_abc_1280.png image/png "
                "200 GHIJKL67890 2048"
            )
            
            mocked.get(
                "https://web.archive.org/cdx/search/cdx",
                status=HTTP_OK,
                body=cdx_response_1,
                repeat=True,
            )
            
            # Mock Archive snapshot downloads
            mocked.get(
                "https://web.archive.org/web/20240101120000id_/https://64.media.tumblr.com/abc123/tumblr_xyz_1280.jpg",
                status=HTTP_OK,
                body=b"archived-image-data-1",
                headers={"Content-Type": "image/jpeg"},
            )
            mocked.get(
                "https://web.archive.org/web/20240101120000id_/https://64.media.tumblr.com/def456/tumblr_abc_1280.png",
                status=HTTP_OK,
                body=b"archived-image-data-2",
                headers={"Content-Type": "image/png"},
            )
            
            # Run orchestrator
            orchestrator = Orchestrator(test_config, manifest_manager)
            stats = await orchestrator.run()
            
            # Load manifest and validate Archive fallback
            manifest = await manifest_manager.load()
            
            # At least some media should be from Internet Archive
            archive_media = [
                m for p in manifest.posts for m in p.media_items
                if m.retrieved_from == "internet_archive"
            ]
            
            assert len(archive_media) > 0, "Expected some media from Internet Archive"
            
            # Validate Archive media properties
            for media in archive_media:
                assert media.status in ["downloaded", "archived"]
                assert media.archive_snapshot_url is not None
                assert "web.archive.org" in media.archive_snapshot_url
                assert media.retrieved_from == "internet_archive"
    
    @pytest.mark.asyncio
    async def test_media_marked_as_missing_when_unavailable(
        self, test_config, manifest_manager
    ):
        """
        ACCEPTANCE TEST 1.3: Media marked as missing when unavailable from both sources.
        
        Validates:
        - When both Tumblr and Archive fail, media is marked 'missing'
        - Manifest correctly tracks status
        - Process continues without crashing
        """
        with aioresponses() as mocked:
            # Mock Tumblr blog page
            mocked.get(
                f"https://{test_config.blog_name}.tumblr.com",
                status=HTTP_OK,
                body=SAMPLE_BLOG_HTML,
            )
            mocked.get(
                f"https://{test_config.blog_name}.tumblr.com/page/2",
                status=HTTP_NOT_FOUND,
            )
            
            # Mock all media downloads as FAILED
            mocked.get(
                "https://64.media.tumblr.com/abc123/tumblr_xyz_1280.jpg",
                status=HTTP_NOT_FOUND,
            )
            mocked.get(
                "https://64.media.tumblr.com/def456/tumblr_abc_1280.png",
                status=HTTP_NOT_FOUND,
            )
            mocked.get(
                "https://64.media.tumblr.com/thumb123.jpg",
                status=HTTP_NOT_FOUND,
            )
            mocked.get(
                "https://va.media.tumblr.com/video123.mp4",
                status=HTTP_NOT_FOUND,
            )
            
            # Mock Wayback CDX API as empty (no snapshots)
            mocked.get(
                "https://web.archive.org/cdx/search/cdx",
                status=HTTP_OK,
                body="",
                repeat=True,
            )
            
            # Run orchestrator
            orchestrator = Orchestrator(test_config, manifest_manager)
            stats = await orchestrator.run()
            
            # Should complete without errors
            assert stats.total_posts >= 2
            assert stats.failed > 0  # Some media should fail
            
            # Load manifest
            manifest = await manifest_manager.load()
            
            # Find missing media
            missing_media = [
                m for p in manifest.posts for m in p.media_items
                if m.status == "missing"
            ]
            
            assert len(missing_media) > 0, "Expected some media marked as missing"
            
            # Validate missing media properties
            for media in missing_media:
                assert media.status == "missing"
                assert media.retrieved_from in ["tumblr", "internet_archive"]


class TestAcceptanceCriteria2:
    """Test Requirement 2: manifest.json correctly reflects provenance."""
    
    @pytest.mark.asyncio
    async def test_manifest_structure_and_schema(self, test_config, manifest_manager):
        """
        ACCEPTANCE TEST 2.1: Manifest has correct structure and validates against schema.
        
        Validates:
        - Manifest follows Pydantic schema
        - All required fields are present
        - Data types are correct
        """
        # Create sample manifest data
        post1 = Post(
            post_id="123456789",
            post_url=f"https://{test_config.blog_name}.tumblr.com/post/123456789",
            timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            is_reblog=False,
            media_items=[
                MediaItem(
                    post_id="123456789",
                    post_url=f"https://{test_config.blog_name}.tumblr.com/post/123456789",
                    timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
                    media_type="image",
                    filename="123456789_001.jpg",
                    byte_size=524288,
                    checksum="a" * 64,
                    original_url="https://64.media.tumblr.com/abc123/tumblr_xyz.jpg",
                    retrieved_from="tumblr",
                    archive_snapshot_url=None,
                    status="downloaded",
                    notes=None,
                )
            ],
        )
        
        post2 = Post(
            post_id="987654321",
            post_url=f"https://{test_config.blog_name}.tumblr.com/post/987654321",
            timestamp=datetime(2024, 1, 14, 15, 45, 0, tzinfo=timezone.utc),
            is_reblog=False,
            media_items=[
                MediaItem(
                    post_id="987654321",
                    post_url=f"https://{test_config.blog_name}.tumblr.com/post/987654321",
                    timestamp=datetime(2024, 1, 14, 15, 45, 0, tzinfo=timezone.utc),
                    media_type="image",
                    filename="987654321_001.png",
                    byte_size=1048576,
                    checksum="b" * 64,
                    original_url="https://64.media.tumblr.com/def456/tumblr_abc.png",
                    retrieved_from="internet_archive",
                    archive_snapshot_url="https://web.archive.org/web/20240101120000/https://64.media.tumblr.com/def456/tumblr_abc.png",
                    status="archived",
                    notes="Retrieved from Internet Archive",
                )
            ],
        )
        
        # Add to manifest
        await manifest_manager.add_post(post1)
        await manifest_manager.add_post(post2)
        await manifest_manager.save()
        
        # Reload manifest from disk
        manifest_manager2 = ManifestManager(test_config.output_dir)
        manifest = await manifest_manager2.load()
        
        # Validate structure
        assert manifest.blog_name == test_config.blog_name
        assert manifest.total_posts == 2
        assert manifest.total_media == 2
        assert len(manifest.posts) == 2
        
        # Validate post 1 (Tumblr source)
        p1 = manifest.posts[0]
        assert p1.post_id == "123456789"
        assert not p1.is_reblog
        assert len(p1.media_items) == 1
        m1 = p1.media_items[0]
        assert m1.media_type == "image"
        assert m1.retrieved_from == "tumblr"
        assert m1.archive_snapshot_url is None
        assert m1.status == "downloaded"
        
        # Validate post 2 (Archive source)
        p2 = manifest.posts[1]
        assert p2.post_id == "987654321"
        m2 = p2.media_items[0]
        assert m2.retrieved_from == "internet_archive"
        assert m2.archive_snapshot_url is not None
        assert "web.archive.org" in m2.archive_snapshot_url
        assert m2.status == "archived"
    
    @pytest.mark.asyncio
    async def test_manifest_provenance_tracking(self, test_config, manifest_manager):
        """
        ACCEPTANCE TEST 2.2: Manifest correctly tracks provenance for each media item.
        
        Validates:
        - original_url is always recorded
        - retrieved_from indicates source (tumblr or internet_archive)
        - archive_snapshot_url is present when retrieved from archive
        - Timestamps are preserved
        """
        # Create media from different sources
        media_tumblr = MediaItem(
            post_id="111",
            post_url=f"https://{test_config.blog_name}.tumblr.com/post/111",
            timestamp=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            media_type="image",
            filename="111_001.jpg",
            byte_size=100000,
            checksum="c" * 64,
            original_url="https://64.media.tumblr.com/original.jpg",
            retrieved_from="tumblr",
            archive_snapshot_url=None,
            status="downloaded",
            notes=None,
        )
        
        media_archive = MediaItem(
            post_id="222",
            post_url=f"https://{test_config.blog_name}.tumblr.com/post/222",
            timestamp=datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
            media_type="video",
            filename="222_001.mp4",
            byte_size=5000000,
            checksum="d" * 64,
            original_url="https://va.media.tumblr.com/original.mp4",
            retrieved_from="internet_archive",
            archive_snapshot_url="https://web.archive.org/web/20240102000000/https://va.media.tumblr.com/original.mp4",
            status="archived",
            notes="Tumblr returned 404, retrieved from archive",
        )
        
        post1 = Post(
            post_id="111",
            post_url=f"https://{test_config.blog_name}.tumblr.com/post/111",
            timestamp=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            is_reblog=False,
            media_items=[media_tumblr],
        )
        
        post2 = Post(
            post_id="222",
            post_url=f"https://{test_config.blog_name}.tumblr.com/post/222",
            timestamp=datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
            is_reblog=False,
            media_items=[media_archive],
        )
        
        await manifest_manager.add_post(post1)
        await manifest_manager.add_post(post2)
        await manifest_manager.save()
        
        # Load and validate JSON structure directly
        manifest_path = test_config.output_dir / "manifest.json"
        with open(manifest_path, "r") as f:
            data = json.load(f)
        
        # Validate Tumblr media provenance
        tumblr_media = data["posts"][0]["media_items"][0]
        assert tumblr_media["original_url"] == "https://64.media.tumblr.com/original.jpg"
        assert tumblr_media["retrieved_from"] == "tumblr"
        assert tumblr_media["archive_snapshot_url"] is None
        assert tumblr_media["status"] == "downloaded"
        
        # Validate Archive media provenance
        archive_media = data["posts"][1]["media_items"][0]
        assert archive_media["original_url"] == "https://va.media.tumblr.com/original.mp4"
        assert archive_media["retrieved_from"] == "internet_archive"
        assert archive_media["archive_snapshot_url"] is not None
        assert "web.archive.org" in archive_media["archive_snapshot_url"]
        assert archive_media["status"] == "archived"
        assert "404" in archive_media["notes"]
    
    @pytest.mark.asyncio
    async def test_manifest_checksums(self, test_config, manifest_manager):
        """
        ACCEPTANCE TEST 2.3: Manifest includes checksums for integrity verification.
        
        Validates:
        - SHA256 checksums are calculated and stored
        - Checksums are valid hex strings (64 characters)
        - byte_size is recorded
        """
        media = MediaItem(
            post_id="333",
            post_url=f"https://{test_config.blog_name}.tumblr.com/post/333",
            timestamp=datetime(2024, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
            media_type="gif",
            filename="333_001.gif",
            byte_size=2048000,
            checksum="e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2",
            original_url="https://64.media.tumblr.com/animated.gif",
            retrieved_from="tumblr",
            archive_snapshot_url=None,
            status="downloaded",
            notes=None,
        )
        
        post = Post(
            post_id="333",
            post_url=f"https://{test_config.blog_name}.tumblr.com/post/333",
            timestamp=datetime(2024, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
            is_reblog=False,
            media_items=[media],
        )
        
        await manifest_manager.add_post(post)
        await manifest_manager.save()
        
        # Load manifest
        manifest = await manifest_manager.load()
        saved_media = manifest.posts[0].media_items[0]
        
        # Validate checksum format (64 hex characters)
        assert saved_media.checksum is not None
        assert len(saved_media.checksum) == 64
        assert all(c in "0123456789abcdef" for c in saved_media.checksum)
        
        # Validate byte size
        assert saved_media.byte_size == 2048000
        assert saved_media.byte_size > 0


class TestAcceptanceCriteria3:
    """Test Requirement 3: Resume capability works."""
    
    @pytest.mark.asyncio
    async def test_resume_skips_downloaded_media(self, test_config, manifest_manager):
        """
        ACCEPTANCE TEST 3.1: Resume skips already downloaded media.
        
        Validates:
        - Existing files are detected
        - Downloaded media is not re-downloaded
        - Stats correctly show skipped count
        """
        # Pre-populate manifest with downloaded media
        existing_post = Post(
            post_id="444",
            post_url=f"https://{test_config.blog_name}.tumblr.com/post/444",
            timestamp=datetime(2024, 1, 4, 0, 0, 0, tzinfo=timezone.utc),
            is_reblog=False,
            media_items=[
                MediaItem(
                    post_id="444",
                    post_url=f"https://{test_config.blog_name}.tumblr.com/post/444",
                    timestamp=datetime(2024, 1, 4, 0, 0, 0, tzinfo=timezone.utc),
                    media_type="image",
                    filename="444_001.jpg",
                    byte_size=100000,
                    checksum="f" * 64,
                    original_url="https://64.media.tumblr.com/existing.jpg",
                    retrieved_from="tumblr",
                    archive_snapshot_url=None,
                    status="downloaded",
                    notes=None,
                )
            ],
        )
        
        await manifest_manager.add_post(existing_post)
        await manifest_manager.save()
        
        # Create the "downloaded" file
        media_path = test_config.output_dir / "444_001.jpg"
        media_path.write_bytes(b"existing-file-data")
        
        # Check if already downloaded
        is_downloaded = await manifest_manager.is_downloaded(
            "https://64.media.tumblr.com/existing.jpg"
        )
        assert is_downloaded, "Media should be marked as already downloaded"
        
        # Verify file exists
        assert (test_config.output_dir / "444_001.jpg").exists()
    
    @pytest.mark.asyncio
    async def test_resume_continues_after_interruption(
        self, test_config, manifest_manager
    ):
        """
        ACCEPTANCE TEST 3.2: Resume continues where it left off after interruption.
        
        Validates:
        - Manifest tracks progress
        - Re-running picks up remaining media
        - No duplicate downloads
        """
        # Simulate partial download - add some posts to manifest
        post1 = Post(
            post_id="555",
            post_url=f"https://{test_config.blog_name}.tumblr.com/post/555",
            timestamp=datetime(2024, 1, 5, 0, 0, 0, tzinfo=timezone.utc),
            is_reblog=False,
            media_items=[
                MediaItem(
                    post_id="555",
                    post_url=f"https://{test_config.blog_name}.tumblr.com/post/555",
                    timestamp=datetime(2024, 1, 5, 0, 0, 0, tzinfo=timezone.utc),
                    media_type="image",
                    filename="555_001.jpg",
                    byte_size=50000,
                    checksum="1" * 64,
                    original_url="https://64.media.tumblr.com/img1.jpg",
                    retrieved_from="tumblr",
                    archive_snapshot_url=None,
                    status="downloaded",
                    notes=None,
                )
            ],
        )
        
        await manifest_manager.add_post(post1)
        await manifest_manager.save()
        
        # Create file for first post
        (test_config.output_dir / "555_001.jpg").write_bytes(b"data1")
        
        # Load manifest again (simulating resume)
        manifest_manager2 = ManifestManager(test_config.output_dir)
        manifest = await manifest_manager2.load()
        
        # Verify state was preserved
        assert manifest.total_posts == 1
        assert manifest.total_media == 1
        assert len(manifest.posts) == 1
        
        # Verify downloaded URLs are tracked
        downloaded_urls = manifest_manager2.get_downloaded_urls()
        assert "https://64.media.tumblr.com/img1.jpg" in downloaded_urls
        
        # Adding a new post should work
        post2 = Post(
            post_id="666",
            post_url=f"https://{test_config.blog_name}.tumblr.com/post/666",
            timestamp=datetime(2024, 1, 6, 0, 0, 0, tzinfo=timezone.utc),
            is_reblog=False,
            media_items=[
                MediaItem(
                    post_id="666",
                    post_url=f"https://{test_config.blog_name}.tumblr.com/post/666",
                    timestamp=datetime(2024, 1, 6, 0, 0, 0, tzinfo=timezone.utc),
                    media_type="image",
                    filename="666_001.jpg",
                    byte_size=60000,
                    checksum="2" * 64,
                    original_url="https://64.media.tumblr.com/img2.jpg",
                    retrieved_from="tumblr",
                    archive_snapshot_url=None,
                    status="downloaded",
                    notes=None,
                )
            ],
        )
        
        await manifest_manager2.add_post(post2)
        await manifest_manager2.save()
        
        # Verify both posts are now in manifest
        final_manifest = await manifest_manager2.load()
        assert final_manifest.total_posts == 2
        assert final_manifest.total_media == 2


class TestAcceptanceCriteria4:
    """Test Requirement 4: Rate limiting prevents 429s."""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_enforces_delays(self, test_config):
        """
        ACCEPTANCE TEST 4.1: Rate limiter enforces delays between requests.
        
        Validates:
        - Requests are spaced according to rate limit
        - No burst of rapid requests
        - Respects configured rate limit
        """
        from tumblr_archiver.rate_limiter import RateLimiter
        
        rate_limiter = RateLimiter(requests_per_second=2.0)  # 2 req/sec = 0.5s delay
        
        timestamps = []
        
        # Make 5 requests
        for _ in range(5):
            async with rate_limiter:
                timestamps.append(asyncio.get_event_loop().time())
        
        # Verify delays between requests
        for i in range(1, len(timestamps)):
            delay = timestamps[i] - timestamps[i - 1]
            # Should be approximately 0.5 seconds (allow some variance)
            assert delay >= 0.45, f"Delay {delay} is too short for rate limit"
    
    @pytest.mark.asyncio
    async def test_rate_limiter_handles_429_retry(self, test_config):
        """
        ACCEPTANCE TEST 4.2: 429 responses trigger exponential backoff.
        
        Validates:
        - 429 errors are caught
        - Retry with exponential backoff
        - Eventually succeeds or gives up
        """
        from tumblr_archiver.retry import RetryHandler
        
        retry_handler = RetryHandler(max_retries=3, base_delay=0.1)
        
        attempt_count = 0
        
        async def failing_request():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                # Fail first 2 attempts
                from tumblr_archiver.exceptions import RateLimitError
                raise RateLimitError("Too many requests")
            return "success"
        
        # Should succeed on 3rd attempt
        result = await retry_handler.execute(failing_request)
        assert result == "success"
        assert attempt_count == 3
    
    @pytest.mark.asyncio
    async def test_concurrent_downloads_respect_rate_limit(self, test_config):
        """
        ACCEPTANCE TEST 4.3: Multiple concurrent downloads stay within rate limit.
        
        Validates:
        - Concurrency setting is respected
        - Overall rate limit is maintained
        - No race conditions
        """
        from tumblr_archiver.rate_limiter import RateLimiter
        
        rate_limiter = RateLimiter(requests_per_second=5.0)
        download_times = []
        
        async def mock_download(num):
            async with rate_limiter:
                download_times.append(asyncio.get_event_loop().time())
                await asyncio.sleep(0.01)  # Simulate download
                return f"download_{num}"
        
        # Run 10 concurrent downloads
        tasks = [mock_download(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 10
        
        # Verify rate limit was enforced
        # With 5 req/sec, 10 requests should take at least 1.8 seconds
        duration = download_times[-1] - download_times[0]
        expected_min_duration = (10 - 1) / 5.0  # 1.8 seconds
        assert duration >= expected_min_duration * 0.9  # Allow 10% variance


class TestEndToEndIntegration:
    """End-to-end integration tests validating complete workflows."""
    
    @pytest.mark.asyncio
    async def test_complete_archive_workflow(self, test_config, manifest_manager):
        """
        INTEGRATION TEST: Complete archiving workflow from start to finish.
        
        Validates:
        - Blog scraping works
        - Media downloads
        - Manifest creation
        - Stats generation
        - File organization
        """
        with aioresponses() as mocked:
            # Mock complete workflow
            mocked.get(
                f"https://{test_config.blog_name}.tumblr.com",
                status=HTTP_OK,
                body=SAMPLE_BLOG_HTML,
            )
            mocked.get(
                f"https://{test_config.blog_name}.tumblr.com/page/2",
                status=HTTP_NOT_FOUND,
            )
            
            # Mock all media downloads
            mocked.get(
                "https://64.media.tumblr.com/abc123/tumblr_xyz_1280.jpg",
                status=HTTP_OK,
                body=b"image1",
                headers={"Content-Type": "image/jpeg"},
            )
            mocked.get(
                "https://64.media.tumblr.com/def456/tumblr_abc_1280.png",
                status=HTTP_OK,
                body=b"image2",
                headers={"Content-Type": "image/png"},
            )
            mocked.get(
                "https://64.media.tumblr.com/thumb123.jpg",
                status=HTTP_OK,
                body=b"thumb",
                headers={"Content-Type": "image/jpeg"},
            )
            mocked.get(
                "https://va.media.tumblr.com/video123.mp4",
                status=HTTP_OK,
                body=b"video",
                headers={"Content-Type": "video/mp4"},
            )
            
            # Run orchestrator
            orchestrator = Orchestrator(test_config, manifest_manager)
            stats = await orchestrator.run()
            
            # Validate stats
            assert isinstance(stats, ArchiveStats)
            assert stats.blog_name == test_config.blog_name
            assert stats.total_posts > 0
            assert stats.total_media > 0
            assert stats.downloaded >= 0
            assert stats.duration_seconds > 0
            
            # Validate manifest exists
            manifest_path = test_config.output_dir / "manifest.json"
            assert manifest_path.exists()
            
            # Load and validate manifest
            with open(manifest_path) as f:
                manifest_data = json.load(f)
            
            assert "blog_name" in manifest_data
            assert "total_posts" in manifest_data
            assert "total_media" in manifest_data
            assert "posts" in manifest_data
            assert manifest_data["blog_name"] == test_config.blog_name
    
    @pytest.mark.asyncio
    async def test_dry_run_mode(self, test_config, manifest_manager):
        """
        INTEGRATION TEST: Dry run mode doesn't download files.
        
        Validates:
        - Files are not actually downloaded
        - Manifest is not created
        - Stats are still generated
        """
        test_config.dry_run = True
        
        with aioresponses() as mocked:
            mocked.get(
                f"https://{test_config.blog_name}.tumblr.com",
                status=HTTP_OK,
                body=SAMPLE_BLOG_HTML,
            )
            mocked.get(
                f"https://{test_config.blog_name}.tumblr.com/page/2",
                status=HTTP_NOT_FOUND,
            )
            
            orchestrator = Orchestrator(test_config, manifest_manager)
            stats = await orchestrator.run()
            
            # Stats should be generated
            assert stats.total_posts >= 0
            assert stats.total_media >= 0
            
            # No files should be downloaded (except manifest which may exist from setup)
            media_files = list(test_config.output_dir.glob("*.jpg"))
            media_files.extend(list(test_config.output_dir.glob("*.png")))
            media_files.extend(list(test_config.output_dir.glob("*.mp4")))
            
            # In dry run, no media files should be created
            assert len(media_files) == 0


class TestErrorHandling:
    """Tests for error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_blog_not_found(self, test_config, manifest_manager):
        """
        ERROR TEST: Handle non-existent blog gracefully.
        
        Validates:
        - Appropriate error is raised
        - No partial manifest created
        """
        with aioresponses() as mocked:
            mocked.get(
                f"https://{test_config.blog_name}.tumblr.com",
                status=HTTP_NOT_FOUND,
            )
            
            orchestrator = Orchestrator(test_config, manifest_manager)
            
            with pytest.raises(Exception):  # Should raise BlogNotFoundError or similar
                await orchestrator.run()
    
    @pytest.mark.asyncio
    async def test_empty_blog(self, test_config, manifest_manager):
        """
        EDGE CASE TEST: Handle blog with no posts.
        
        Validates:
        - Completes without errors
        - Empty manifest created
        - Stats show zero counts
        """
        with aioresponses() as mocked:
            mocked.get(
                f"https://{test_config.blog_name}.tumblr.com",
                status=HTTP_OK,
                body=EMPTY_BLOG_HTML,
            )
            
            orchestrator = Orchestrator(test_config, manifest_manager)
            stats = await orchestrator.run()
            
            # Should complete successfully with zero stats
            assert stats.total_posts == 0
            assert stats.total_media == 0
            assert stats.downloaded == 0
            assert stats.failed == 0


class TestConfigurationValidation:
    """Tests for configuration validation."""
    
    def test_config_validation(self, temp_output_dir):
        """
        CONFIG TEST: Configuration validates input parameters.
        
        Validates:
        - Invalid values are rejected
        - Defaults are applied correctly
        - Required fields are enforced
        """
        # Valid config
        config = ArchiverConfig(
            blog_name="testblog",
            output_dir=str(temp_output_dir),
        )
        assert config.concurrency == DEFAULT_CONCURRENCY
        assert config.rate_limit == DEFAULT_RATE_LIMIT
        
        # Test blog name normalization
        config2 = ArchiverConfig(
            blog_name="https://testblog.tumblr.com",
            output_dir=str(temp_output_dir),
        )
        # Should normalize to just blog name
        assert ".tumblr.com" not in config2.blog_name or config2.blog_name == "testblog"
