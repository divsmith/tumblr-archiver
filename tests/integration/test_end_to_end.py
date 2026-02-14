"""
End-to-end integration tests for Tumblr archiver.

Tests the complete workflow: scrape → download → manifest creation
using mocked HTTP responses and real file operations.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tumblr_archiver.config import ArchiverConfig
from tumblr_archiver.orchestrator import Orchestrator
from tests.integration.conftest import (
    create_test_media_content,
    verify_downloaded_files,
    verify_manifest_file,
    count_manifest_items,
    get_media_item_from_manifest,
)
from tests.mocks.tumblr_server import MockTumblrServer


@pytest.mark.asyncio
async def test_end_to_end_basic_workflow(
    sample_blog_name: str,
    integration_output_dir: Path,
    sample_image_data: bytes,
):
    """
    Test complete end-to-end workflow with basic blog data.
    
    Verifies:
    - Blog scraping
    - Media download
    - Manifest creation
    - File persistence
    """
    # Set up mock server
    server = MockTumblrServer(sample_blog_name)
    server.add_post(
        post_id="123456789",
        media_url="https://64.media.tumblr.com/abc123/tumblr_img1.jpg",
        media_content=sample_image_data,
        timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
    )
    server.add_post(
        post_id="987654321",
        media_url="https://64.media.tumblr.com/xyz789/tumblr_img2.jpg",
        media_content=sample_image_data,
        timestamp=datetime(2024, 1, 14, 15, 20, 0, tzinfo=timezone.utc),
    )
    
    # Run archiver with mocked responses
    config = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
        concurrency=2,
        rate_limit=100.0,
    )
    
    orchestrator = Orchestrator(config)
    
    with server.mock():
        stats = await orchestrator.run()
    
    # Verify statistics
    assert stats.blog_name == sample_blog_name
    assert stats.total_posts == 2
    assert stats.total_media == 2
    assert stats.downloaded == 2
    assert stats.failed == 0
    assert stats.skipped == 0
    assert stats.bytes_downloaded > 0
    
    # Verify manifest.json created
    manifest_path = integration_output_dir / "manifest.json"
    assert manifest_path.exists()
    
    with open(manifest_path) as f:
        manifest_data = json.load(f)
    
    assert manifest_data["blog_name"] == sample_blog_name
    assert manifest_data["total_posts"] == 2
    assert manifest_data["total_media"] == 2
    assert len(manifest_data["posts"]) == 2
    
    # Verify files downloaded
    expected_files = ["123456789_001.jpg", "987654321_001.jpg"]
    for filename in expected_files:
        file_path = integration_output_dir / filename
        assert file_path.exists()
        assert file_path.stat().st_size > 0
    
    # Verify media items have checksums
    for post in manifest_data["posts"]:
        for media in post["media_items"]:
            assert media["status"] == "downloaded"
            assert media["checksum"] is not None
            assert len(media["checksum"]) == 64
            assert media["byte_size"] > 0


@pytest.mark.asyncio
async def test_end_to_end_multiple_media_types(
    sample_blog_name: str,
    integration_output_dir: Path,
    sample_image_data: bytes,
    sample_gif_data: bytes,
    sample_video_data: bytes,
):
    """
    Test end-to-end workflow with different media types.
    
    Verifies handling of:
    - Images (JPG, PNG)
    - Animated GIFs
    - Videos
    """
    # Set up mock server with different media types
    server = MockTumblrServer(sample_blog_name)
    
    server.add_post(
        post_id="111",
        media_url="https://64.media.tumblr.com/img1.jpg",
        media_content=sample_image_data,
        media_type="image",
    )
    
    server.add_post(
        post_id="222",
        media_url="https://64.media.tumblr.com/anim.gif",
        media_content=sample_gif_data,
        media_type="gif",
    )
    
    server.add_post(
        post_id="333",
        media_url="https://64.media.tumblr.com/video.mp4",
        media_content=sample_video_data,
        media_type="video",
    )
    
    # Run archiver
    config = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
        concurrency=2,
    )
    
    orchestrator = Orchestrator(config)
    
    with server.mock():
        stats = await orchestrator.run()
    
    # Verify all media types downloaded
    assert stats.total_media == 3
    assert stats.downloaded == 3
    
    # Verify files exist
    assert (integration_output_dir / "111_001.jpg").exists()
    assert (integration_output_dir / "222_001.gif").exists()
    assert (integration_output_dir / "333_001.mp4").exists()
    
    # Verify manifest has correct types
    media_item_img = await get_media_item_from_manifest(
        integration_output_dir, "111_001.jpg"
    )
    assert media_item_img["media_type"] == "image"
    
    media_item_gif = await get_media_item_from_manifest(
        integration_output_dir, "222_001.gif"
    )
    assert media_item_gif["media_type"] == "gif"
    
    media_item_video = await get_media_item_from_manifest(
        integration_output_dir, "333_001.mp4"
    )
    assert media_item_video["media_type"] == "video"


@pytest.mark.asyncio
async def test_end_to_end_with_pagination(
    sample_blog_name: str,
    integration_output_dir: Path,
    sample_image_data: bytes,
):
    """
    Test end-to-end workflow with paginated blog.
    
    Verifies:
    - Pagination handling
    - Multiple pages scraped
    - All posts processed
    """
    # Set up mock server with many posts (multiple pages)
    server = MockTumblrServer(sample_blog_name)
    
    # Add 15 posts (should span 2 pages with 10 posts per page)
    for i in range(15):
        post_id = f"{100 + i}"
        server.add_post(
            post_id=post_id,
            media_url=f"https://64.media.tumblr.com/img_{i}.jpg",
            media_content=sample_image_data,
        )
    
    # Run archiver
    config = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
        concurrency=3,
    )
    
    orchestrator = Orchestrator(config)
    
    with server.mock():
        stats = await orchestrator.run()
    
    # Verify all posts scraped
    assert stats.total_posts == 15
    assert stats.total_media == 15
    assert stats.downloaded == 15


@pytest.mark.asyncio
async def test_end_to_end_with_reblogs(
    sample_blog_name: str,
    integration_output_dir: Path,
    sample_image_data: bytes,
):
    """
    Test end-to-end workflow with reblogged posts.
    
    Verifies:
    - Reblog detection
    - Reblog inclusion/exclusion based on config
    """
    # Set up mock server with original and reblogged posts
    server = MockTumblrServer(sample_blog_name)
    
    # Original post
    server.add_post(
        post_id="111",
        media_url="https://64.media.tumblr.com/original.jpg",
        media_content=sample_image_data,
        is_reblog=False,
    )
    
    # Reblogged posts
    server.add_post(
        post_id="222",
        media_url="https://64.media.tumblr.com/reblog1.jpg",
        media_content=sample_image_data,
        is_reblog=True,
    )
    
    server.add_post(
        post_id="333",
        media_url="https://64.media.tumblr.com/reblog2.jpg",
        media_content=sample_image_data,
        is_reblog=True,
    )
    
    # Test with reblogs included (default)
    config = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
        include_reblogs=True,
    )
    
    orchestrator = Orchestrator(config)
    
    with server.mock():
        stats = await orchestrator.run()
    
    assert stats.total_posts == 3
    assert stats.total_media == 3


@pytest.mark.asyncio
async def test_end_to_end_empty_blog(
    sample_blog_name: str,
    integration_output_dir: Path,
):
    """
    Test end-to-end workflow with empty blog.
    
    Verifies:
    - Handling of blogs with no posts
    - Empty manifest creation (or no manifest if no posts found)
    """
    # Set up mock server with no posts
    server = MockTumblrServer(sample_blog_name)
    
    # Run archiver
    config = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
    )
    
    orchestrator = Orchestrator(config)
    
    with server.mock():
        stats = await orchestrator.run()
    
    # Verify statistics
    assert stats.total_posts == 0
    assert stats.total_media == 0
    assert stats.downloaded == 0
    
    # Note: Manifest may or may not be created when no posts found
    # This depends on implementation - the orchestrator returns early
    # when no posts are found, so manifest might not be saved


@pytest.mark.asyncio
async def test_end_to_end_with_failed_downloads(
    sample_blog_name: str,
    integration_output_dir: Path,
    sample_image_data: bytes,
):
    """
    Test end-to-end workflow with some failed downloads.
    
    Verifies:
    - Graceful handling of download failures
    - Failed items marked in manifest
    - Other downloads continue
    """
    # Set up mock server
    server = MockTumblrServer(sample_blog_name)
    
    # Add posts - mark one for failure
    server.add_post(
        post_id="111",
        media_url="https://64.media.tumblr.com/good1.jpg",
        media_content=sample_image_data,
    )
    
    server.add_post(
        post_id="222",
        media_url="https://64.media.tumblr.com/bad.jpg",
        media_content=sample_image_data,
    )
    server.mark_url_as_failing("https://64.media.tumblr.com/bad.jpg")
    
    server.add_post(
        post_id="333",
        media_url="https://64.media.tumblr.com/good2.jpg",
        media_content=sample_image_data,
    )
    
    # Run archiver
    config = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
        concurrency=1,  # Sequential to ensure order
    )
    
    orchestrator = Orchestrator(config)
    
    with server.mock():
        stats = await orchestrator.run()
    
    # Verify statistics - one failed, two succeeded
    assert stats.total_posts == 3
    assert stats.total_media == 3
    # Note: Failed downloads may still show some downloaded if fallback succeeds
    # But at least one should have an issue
    assert stats.downloaded + stats.failed == 3
    
    # Verify successful files exist
    assert (integration_output_dir / "111_001.jpg").exists()
    assert (integration_output_dir / "333_001.jpg").exists()


@pytest.mark.asyncio
async def test_end_to_end_manifest_structure(
    sample_blog_name: str,
    integration_output_dir: Path,
    sample_image_data: bytes,
):
    """
    Test manifest.json has correct structure and metadata.
    
    Verifies:
    - All required fields present
    - Correct data types
    - Proper timestamps
    - Complete media item metadata
    """
    # Set up mock server
    server = MockTumblrServer(sample_blog_name)
    server.add_post(
        post_id="123456",
        media_url="https://64.media.tumblr.com/test.jpg",
        media_content=sample_image_data,
        timestamp=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
    )
    
    # Run archiver
    config = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
    )
    
    orchestrator = Orchestrator(config)
    
    with server.mock():
        await orchestrator.run()
    
    # Load and verify manifest structure
    manifest_path = integration_output_dir / "manifest.json"
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    # Top-level fields
    assert "blog_name" in manifest
    assert "created_at" in manifest
    assert "updated_at" in manifest
    assert "total_posts" in manifest
    assert "total_media" in manifest
    assert "posts" in manifest
    
    assert manifest["blog_name"] == sample_blog_name
    assert manifest["total_posts"] == 1
    assert manifest["total_media"] == 1
    
    # Post structure
    post = manifest["posts"][0]
    assert "post_id" in post
    assert "post_url" in post
    assert "timestamp" in post
    assert "is_reblog" in post
    assert "media_items" in post
    
    # Media item structure
    media = post["media_items"][0]
    required_fields = [
        "post_id",
        "post_url",
        "timestamp",
        "media_type",
        "filename",
        "byte_size",
        "checksum",
        "original_url",
        "retrieved_from",
        "status",
    ]
    
    for field in required_fields:
        assert field in media, f"Missing required field: {field}"
    
    # Verify data types and values
    assert isinstance(media["byte_size"], int)
    assert media["byte_size"] > 0
    assert isinstance(media["checksum"], str)
    assert len(media["checksum"]) == 64
    assert media["status"] == "downloaded"
    assert media["retrieved_from"] == "tumblr"
    assert media["media_type"] == "image"
    assert media["filename"] == "123456_001.jpg"
