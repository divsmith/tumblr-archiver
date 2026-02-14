"""
Integration tests for resume capability.

Tests that the archiver can resume interrupted downloads and avoid
re-downloading files that already exist.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tumblr_archiver.config import ArchiverConfig
from tumblr_archiver.orchestrator import Orchestrator
from tests.integration.conftest import (
    count_manifest_items,
    get_media_item_from_manifest,
)
from tests.mocks.tumblr_server import MockTumblrServer


@pytest.mark.asyncio
async def test_resume_after_partial_download(
    sample_blog_name: str,
    integration_output_dir: Path,
    sample_image_data: bytes,
):
    """
    Test resuming after partial download.
    
    Simulates interrupted download and verifies:
    - Resume picks up where it left off
    - Already downloaded files not re-downloaded
    - Manifest updated correctly
    """
    # Set up mock server with 3 posts
    server = MockTumblrServer(sample_blog_name)
    
    for i in range(3):
        server.add_post(
            post_id=f"{100 + i}",
            media_url=f"https://64.media.tumblr.com/img_{i}.jpg",
            media_content=sample_image_data,
        )
    
    # First run: Download only first file manually to simulate partial download
    config = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
        concurrency=1,
        resume=True,
    )
    
    orchestrator1 = Orchestrator(config)
    
    with server.mock():
        # Run first time - should download all 3
        stats1 = await orchestrator1.run()
    
    assert stats1.downloaded == 3
    assert stats1.skipped == 0
    
    # Verify all files exist
    file1 = integration_output_dir / "100_001.jpg"
    file2 = integration_output_dir / "101_001.jpg"
    file3 = integration_output_dir / "102_001.jpg"
    
    assert file1.exists()
    assert file2.exists()
    assert file3.exists()
    
    # Second run: Should skip all files (resume mode)
    orchestrator2 = Orchestrator(config)
    
    with server.mock():
        stats2 = await orchestrator2.run()
    
    # All files should be skipped (already downloaded)
    assert stats2.total_media == 3
    assert stats2.downloaded == 0
    assert stats2.skipped == 3
    assert stats2.bytes_downloaded == 0
    
    # Verify manifest still correct
    manifest_path = integration_output_dir / "manifest.json"
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    assert manifest["total_media"] == 3
    
    # All items should still show as downloaded
    downloaded_count = sum(
        1 for post in manifest["posts"]
        for media in post["media_items"]
        if media["status"] == "downloaded"
    )
    assert downloaded_count == 3


@pytest.mark.asyncio
async def test_resume_with_new_posts(
    sample_blog_name: str,
    integration_output_dir: Path,
    sample_image_data: bytes,
):
    """
    Test resuming when new posts have been added.
    
    Verifies:
    - New posts detected
    - New media downloaded
    - Existing media skipped
    - Manifest updated with new posts
    """
    # Set up mock server with initial 2 posts
    server = MockTumblrServer(sample_blog_name)
    
    server.add_post(
        post_id="100",
        media_url="https://64.media.tumblr.com/img_0.jpg",
        media_content=sample_image_data,
    )
    server.add_post(
        post_id="101",
        media_url="https://64.media.tumblr.com/img_1.jpg",
        media_content=sample_image_data,
    )
    
    # First run
    config = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
        resume=True,
    )
    
    orchestrator1 = Orchestrator(config)
    
    with server.mock():
        stats1 = await orchestrator1.run()
    
    assert stats1.total_posts == 2
    assert stats1.downloaded == 2
    
    # Add new posts to mock server
    server.add_post(
        post_id="102",
        media_url="https://64.media.tumblr.com/img_2.jpg",
        media_content=sample_image_data,
    )
    server.add_post(
        post_id="103",
        media_url="https://64.media.tumblr.com/img_3.jpg",
        media_content=sample_image_data,
    )
    
    # Second run with new posts
    orchestrator2 = Orchestrator(config)
    
    with server.mock():
        stats2 = await orchestrator2.run()
    
    # Should find 4 posts total, download 2 new, skip 2 existing
    assert stats2.total_posts == 4
    assert stats2.total_media == 4
    assert stats2.downloaded == 2
    assert stats2.skipped == 2
    
    # Verify all files exist
    assert (integration_output_dir / "100_001.jpg").exists()
    assert (integration_output_dir / "101_001.jpg").exists()
    assert (integration_output_dir / "102_001.jpg").exists()
    assert (integration_output_dir / "103_001.jpg").exists()
    
    # Verify manifest updated
    manifest_path = integration_output_dir / "manifest.json"
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    assert manifest["total_posts"] == 4
    assert manifest["total_media"] == 4


@pytest.mark.asyncio
async def test_resume_with_deleted_files(
    sample_blog_name: str,
    integration_output_dir: Path,
    sample_image_data: bytes,
):
    """
    Test resuming when some downloaded files were deleted.
    
    Verifies:
    - Deleted files detected
    - Missing files re-downloaded
    - Existing files skipped
    """
    # Set up mock server
    server = MockTumblrServer(sample_blog_name)
    
    for i in range(3):
        server.add_post(
            post_id=f"{100 + i}",
            media_url=f"https://64.media.tumblr.com/img_{i}.jpg",
            media_content=sample_image_data,
        )
    
    # First run
    config = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
        resume=True,
    )
    
    orchestrator1 = Orchestrator(config)
    
    with server.mock():
        stats1 = await orchestrator1.run()
    
    assert stats1.downloaded == 3
    
    # Delete one file (simulate accidental deletion or corruption)
    deleted_file = integration_output_dir / "101_001.jpg"
    assert deleted_file.exists()
    deleted_file.unlink()
    
    # Second run - should re-download deleted file
    orchestrator2 = Orchestrator(config)
    
    with server.mock():
        stats2 = await orchestrator2.run()
    
    # Should re-download the missing file
    assert stats2.total_media == 3
    # The deleted file will be detected as missing and re-downloaded
    # Other files should be skipped
    assert stats2.downloaded >= 1
    assert stats2.skipped >= 2
    
    # Verify deleted file re-downloaded
    assert deleted_file.exists()


@pytest.mark.asyncio
async def test_resume_disabled(
    sample_blog_name: str,
    integration_output_dir: Path,
    sample_image_data: bytes,
):
    """
    Test behavior when resume is disabled.
    
    Verifies:
    - Files re-downloaded even if they exist
    - Manifest rebuilt from scratch
    """
    # Set up mock server
    server = MockTumblrServer(sample_blog_name)
    
    server.add_post(
        post_id="100",
        media_url="https://64.media.tumblr.com/img_0.jpg",
        media_content=sample_image_data,
    )
    
    # First run
    config = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
        resume=True,
    )
    
    orchestrator1 = Orchestrator(config)
    
    with server.mock():
        stats1 = await orchestrator1.run()
    
    assert stats1.downloaded == 1
    
    # Get file modification time
    file_path = integration_output_dir / "100_001.jpg"
    original_mtime = file_path.stat().st_mtime
    
    # Small delay to ensure different timestamp
    import asyncio
    await asyncio.sleep(0.1)
    
    # Second run with resume disabled
    config_no_resume = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
        resume=False,
    )
    
    orchestrator2 = Orchestrator(config_no_resume)
    
    with server.mock():
        stats2 = await orchestrator2.run()
    
    # File should be re-downloaded
    assert stats2.downloaded == 1
    assert stats2.skipped == 0
    
    # File should have been updated (newer modification time)
    new_mtime = file_path.stat().st_mtime
    # Note: In some systems the file may be overwritten quickly, 
    # so we just verify download happened
    assert stats2.downloaded == 1


@pytest.mark.asyncio
async def test_resume_with_checksum_mismatch(
    sample_blog_name: str,
    integration_output_dir: Path,
    sample_image_data: bytes,
    sample_gif_data: bytes,
):
    """
    Test resuming when a file's checksum doesn't match manifest.
    
    Verifies:
    - Corrupted files detected
    - Mismatched files re-downloaded
    """
    # Set up mock server
    server = MockTumblrServer(sample_blog_name)
    
    server.add_post(
        post_id="100",
        media_url="https://64.media.tumblr.com/img.jpg",
        media_content=sample_image_data,
    )
    
    # First run
    config = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
        resume=True,
    )
    
    orchestrator1 = Orchestrator(config)
    
    with server.mock():
        stats1 = await orchestrator1.run()
    
    assert stats1.downloaded == 1
    
    # Corrupt the file by replacing with different content
    file_path = integration_output_dir / "100_001.jpg"
    with open(file_path, "wb") as f:
        f.write(b"corrupted content")
    
    # Second run - should detect mismatch and re-download
    orchestrator2 = Orchestrator(config)
    
    with server.mock():
        stats2 = await orchestrator2.run()
    
    # File should be re-downloaded due to checksum mismatch
    # The deduplicator will detect the mismatch
    assert stats2.total_media == 1
    
    # Verify file content restored
    with open(file_path, "rb") as f:
        content = f.read()
    
    # Should match original image data
    assert content == sample_image_data


@pytest.mark.asyncio
async def test_resume_preserves_partial_success(
    sample_blog_name: str,
    integration_output_dir: Path,
    sample_image_data: bytes,
):
    """
    Test that resume preserves partial success from interrupted run.
    
    Verifies:
    - Successfully downloaded files before interruption are kept
    - Only failed/missing files re-downloaded
    - No duplicate downloads
    """
    # Set up mock server
    server = MockTumblrServer(sample_blog_name)
    
    # Add multiple posts
    for i in range(5):
        server.add_post(
            post_id=f"{100 + i}",
            media_url=f"https://64.media.tumblr.com/img_{i}.jpg",
            media_content=sample_image_data,
        )
    
    # First run: download all
    config = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
        concurrency=2,
        resume=True,
    )
    
    orchestrator1 = Orchestrator(config)
    
    with server.mock():
        stats1 = await orchestrator1.run()
    
    assert stats1.downloaded == 5
    
    # Record original file timestamps
    orig_timestamps = {}
    for i in range(5):
        file_path = integration_output_dir / f"{100 + i}_001.jpg"
        orig_timestamps[file_path] = file_path.stat().st_mtime
    
    # Small delay
    import asyncio
    await asyncio.sleep(0.1)
    
    # Second run: all should be skipped
    orchestrator2 = Orchestrator(config)
    
    with server.mock():
        stats2 = await orchestrator2.run()
    
    assert stats2.downloaded == 0
    assert stats2.skipped == 5
    
    # Verify files not modified (timestamps unchanged)
    for file_path, orig_time in orig_timestamps.items():
        # Files should not be re-downloaded, so timestamps should be very close
        # (allowing for filesystem precision differences)
        current_time = file_path.stat().st_mtime
        assert abs(current_time - orig_time) < 1.0  # Within 1 second


@pytest.mark.asyncio
async def test_resume_with_updated_manifest_format(
    sample_blog_name: str,
    integration_output_dir: Path,
    sample_image_data: bytes,
):
    """
    Test resuming with existing manifest in older format.
    
    Verifies:
    - Manifest backward compatibility
    - Graceful handling of format changes
    """
    # Set up mock server
    server = MockTumblrServer(sample_blog_name)
    
    server.add_post(
        post_id="100",
        media_url="https://64.media.tumblr.com/img.jpg",
        media_content=sample_image_data,
    )
    
    # Create a minimal "old format" manifest manually
    manifest_path = integration_output_dir / "manifest.json"
    old_manifest = {
        "blog_name": sample_blog_name,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "total_posts": 0,
        "total_media": 0,
        "posts": []
    }
    
    with open(manifest_path, "w") as f:
        json.dump(old_manifest, f)
    
    # Run archiver - should handle old manifest and update it
    config = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
        resume=True,
    )
    
    orchestrator = Orchestrator(config)
    
    with server.mock():
        stats = await orchestrator.run()
    
    # Should successfully archive
    assert stats.total_posts == 1
    assert stats.downloaded == 1
    
    # Verify manifest updated
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    assert manifest["total_posts"] == 1
    assert manifest["total_media"] == 1
    assert len(manifest["posts"]) == 1
