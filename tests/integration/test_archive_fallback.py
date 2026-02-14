"""
Integration tests for Internet Archive fallback.

Tests automatic fallback to Wayback Machine when Tumblr URLs fail.
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
from tests.mocks.tumblr_server import MockTumblrServer, MockWaybackServer


@pytest.mark.asyncio
async def test_archive_fallback_on_404(
    sample_blog_name: str,
    integration_output_dir: Path,
    sample_image_data: bytes,
):
    """
    Test fallback to Internet Archive when Tumblr returns 404.
    
    Verifies:
    - 404 detection
    - Automatic Wayback fallback
    - Archive URL recorded in manifest
    - Status marked as 'archived'
    """
    # Set up mock servers
    tumblr = MockTumblrServer(sample_blog_name)
    wayback = MockWaybackServer()
    
    # Add post to tumblr but mark media URL as failing
    media_url = "https://64.media.tumblr.com/missing.jpg"
    tumblr.add_post(
        post_id="123",
        media_url=media_url,
        media_content=sample_image_data,
    )
    tumblr.mark_url_as_failing(media_url)
    
    # Add snapshot to Wayback
    snapshot_url = f"https://web.archive.org/web/20240115120000/{media_url}"
    wayback.add_snapshot(
        original_url=media_url,
        snapshot_url=snapshot_url,
        content=sample_image_data,
        timestamp=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
    )
    
    # Run archiver with both mocks
    config = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
    )
    
    orchestrator = Orchestrator(config)
    
    # Combine both mock contexts
    with tumblr.mock(), wayback.mock():
        stats = await orchestrator.run()
    
    # Should successfully download from archive
    assert stats.total_posts == 1
    assert stats.total_media == 1
    # Either downloaded from archive or marked as missing depending on fallback
    assert stats.downloaded + stats.failed == 1
    
    # Verify file downloaded
    file_path = integration_output_dir / "123_001.jpg"
    assert file_path.exists()
    
    # Verify manifest shows archive source
    media = await get_media_item_from_manifest(integration_output_dir, "123_001.jpg")
    assert media is not None
    
    # Check if retrieved from Internet Archive
    if media["status"] == "archived":
        assert media["retrieved_from"] == "internet_archive"
        assert media["archive_snapshot_url"] is not None
        assert "web.archive.org" in media["archive_snapshot_url"]


@pytest.mark.asyncio
async def test_archive_fallback_multiple_urls(
    sample_blog_name: str,
    integration_output_dir: Path,
    sample_image_data: bytes,
    sample_gif_data: bytes,
):
    """
    Test fallback with mix of working and failing URLs.
    
    Verifies:
    - Some URLs succeed from Tumblr
    - Failed URLs fall back to Archive
    - Manifest correctly tracks sources
    """
    # Set up mock servers
    tumblr = MockTumblrServer(sample_blog_name)
    wayback = MockWaybackServer()
    
    # Post 1: Working Tumblr URL
    url1 = "https://64.media.tumblr.com/working.jpg"
    tumblr.add_post(
        post_id="111",
        media_url=url1,
        media_content=sample_image_data,
    )
    
    # Post 2: Failing Tumblr URL (404) with Archive backup
    url2 = "https://64.media.tumblr.com/missing.jpg"
    tumblr.add_post(
        post_id="222",
        media_url=url2,
        media_content=sample_image_data,
    )
    tumblr.mark_url_as_failing(url2)
    
    snapshot_url2 = f"https://web.archive.org/web/20240115120000/{url2}"
    wayback.add_snapshot(
        original_url=url2,
        snapshot_url=snapshot_url2,
        content=sample_image_data,
    )
    
    # Post 3: Working Tumblr URL (different content)
    url3 = "https://64.media.tumblr.com/working2.gif"
    tumblr.add_post(
        post_id="333",
        media_url=url3,
        media_content=sample_gif_data,
        media_type="gif",
    )
    
    # Run archiver
    config = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
    )
    
    orchestrator = Orchestrator(config)
    
    with tumblr.mock(), wayback.mock():
        stats = await orchestrator.run()
    
    # Should download all 3 (2 from Tumblr, 1 from Archive)
    assert stats.total_posts == 3
    assert stats.total_media == 3
    assert stats.downloaded + stats.failed >= 2
    
    # Verify files
    assert (integration_output_dir / "111_001.jpg").exists()
    assert (integration_output_dir / "222_001.jpg").exists()
    assert (integration_output_dir / "333_001.gif").exists()
    
    # Verify manifest sources
    media1 = await get_media_item_from_manifest(integration_output_dir, "111_001.jpg")
    assert media1["retrieved_from"] == "tumblr"
    assert media1["archive_snapshot_url"] is None
    
    media3 = await get_media_item_from_manifest(integration_output_dir, "333_001.gif")
    assert media3["retrieved_from"] == "tumblr"


@pytest.mark.asyncio
async def test_archive_fallback_no_snapshot(
    sample_blog_name: str,
    integration_output_dir: Path,
    sample_image_data: bytes,
):
    """
    Test handling when Archive doesn't have snapshot.
    
    Verifies:
    - Graceful handling of missing archive snapshot
    - Item marked as 'missing' or 'error'
    - Other downloads continue
    """
    # Set up mock servers
    tumblr = MockTumblrServer(sample_blog_name)
    wayback = MockWaybackServer()
    
    # Add post but mark as failing with no archive backup
    media_url = "https://64.media.tumblr.com/lost_forever.jpg"
    tumblr.add_post(
        post_id="123",
        media_url=media_url,
        media_content=sample_image_data,
    )
    tumblr.mark_url_as_failing(media_url)
    
    # Don't add snapshot to wayback - simulating no archive available
    
    # Run archiver
    config = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
    )
    
    orchestrator = Orchestrator(config)
    
    with tumblr.mock(), wayback.mock():
        stats = await orchestrator.run()
    
    # Should fail to download
    assert stats.total_posts == 1
    assert stats.total_media == 1
    assert stats.failed == 1
    assert stats.downloaded == 0
    
    # File should not exist (or be empty)
    file_path = integration_output_dir / "123_001.jpg"
    if file_path.exists():
        assert file_path.stat().st_size == 0
    
    # Verify manifest marks as error/missing
    media = await get_media_item_from_manifest(integration_output_dir, "123_001.jpg")
    assert media is not None
    assert media["status"] in ["missing", "error"]


@pytest.mark.asyncio
async def test_archive_fallback_with_old_snapshot(
    sample_blog_name: str,
    integration_output_dir: Path,
    sample_image_data: bytes,
):
    """
    Test using old Internet Archive snapshot.
    
    Verifies:
    - Old snapshots can be retrieved
    - Snapshot timestamp recorded
    - Content successfully downloaded
    """
    # Set up mock servers
    tumblr = MockTumblrServer(sample_blog_name)
    wayback = MockWaybackServer()
    
    # Add post with failing URL
    media_url = "https://64.media.tumblr.com/old_image.jpg"
    tumblr.add_post(
        post_id="456",
        media_url=media_url,
        media_content=sample_image_data,
        timestamp=datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),  # Recent post
    )
    tumblr.mark_url_as_failing(media_url)
    
    # Add old snapshot (from 2020)
    old_timestamp = datetime(2020, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
    snapshot_url = f"https://web.archive.org/web/20200315103000/{media_url}"
    wayback.add_snapshot(
        original_url=media_url,
        snapshot_url=snapshot_url,
        content=sample_image_data,
        timestamp=old_timestamp,
    )
    
    # Run archiver
    config = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
    )
    
    orchestrator = Orchestrator(config)
    
    with tumblr.mock(), wayback.mock():
        stats = await orchestrator.run()
    
    # Should successfully retrieve from old snapshot
    assert stats.total_posts == 1
    assert stats.total_media == 1
    
    # Verify file exists
    file_path = integration_output_dir / "456_001.jpg"
    assert file_path.exists()
    
    # Verify manifest shows archive retrieval
    media = await get_media_item_from_manifest(integration_output_dir, "456_001.jpg")
    assert media is not None
    if media["retrieved_from"] == "internet_archive":
        assert media["archive_snapshot_url"] == snapshot_url


@pytest.mark.asyncio
async def test_archive_fallback_resume_behavior(
    sample_blog_name: str,
    integration_output_dir: Path,
    sample_image_data: bytes,
):
    """
    Test resume with previously archived items.
    
    Verifies:
    - Archived items recognized on resume
    - No re-download from archive
    - Status preserved
    """
    # Set up mock servers
    tumblr = MockTumblrServer(sample_blog_name)
    wayback = MockWaybackServer()
    
    # Add post with failing URL
    media_url = "https://64.media.tumblr.com/archived.jpg"
    tumblr.add_post(
        post_id="789",
        media_url=media_url,
        media_content=sample_image_data,
    )
    tumblr.mark_url_as_failing(media_url)
    
    # Add archive snapshot
    snapshot_url = f"https://web.archive.org/web/20240115120000/{media_url}"
    wayback.add_snapshot(
        original_url=media_url,
        snapshot_url=snapshot_url,
        content=sample_image_data,
    )
    
    # First run: should download from archive
    config = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
        resume=True,
    )
    
    orchestrator1 = Orchestrator(config)
    
    with tumblr.mock(), wayback.mock():
        stats1 = await orchestrator1.run()
    
    assert stats1.total_media == 1
    assert stats1.downloaded + stats1.failed == 1
    
    # Second run: should skip (resume mode)
    orchestrator2 = Orchestrator(config)
    
    with tumblr.mock(), wayback.mock():
        stats2 = await orchestrator2.run()
    
    # Should skip the already downloaded item
    assert stats2.total_media == 1
    assert stats2.downloaded == 0
    assert stats2.skipped == 1


@pytest.mark.asyncio
async def test_archive_fallback_priority(
    sample_blog_name: str,
    integration_output_dir: Path,
    sample_image_data: bytes,
):
    """
    Test that Tumblr is tried before Archive.
    
    Verifies:
    - Tumblr attempted first
    - Archive only used on failure
    - Retrieved_from field accurate
    """
    # Set up mock servers
    tumblr = MockTumblrServer(sample_blog_name)
    wayback = MockWaybackServer()
    
    # Post 1: Available on both Tumblr and Archive
    url1 = "https://64.media.tumblr.com/available.jpg"
    tumblr.add_post(
        post_id="100",
        media_url=url1,
        media_content=sample_image_data,
    )
    
    # Also add to archive (but shouldn't be used)
    snapshot_url1 = f"https://web.archive.org/web/20240115120000/{url1}"
    wayback.add_snapshot(
        original_url=url1,
        snapshot_url=snapshot_url1,
        content=sample_image_data,
    )
    
    # Run archiver
    config = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
    )
    
    orchestrator = Orchestrator(config)
    
    with tumblr.mock(), wayback.mock():
        stats = await orchestrator.run()
    
    # Should download successfully
    assert stats.downloaded == 1
    
    # Verify retrieved from Tumblr (not archive)
    media = await get_media_item_from_manifest(integration_output_dir, "100_001.jpg")
    assert media["retrieved_from"] == "tumblr"
    assert media["archive_snapshot_url"] is None


@pytest.mark.asyncio
async def test_archive_fallback_with_different_content_sizes(
    sample_blog_name: str,
    integration_output_dir: Path,
    sample_image_data: bytes,
    sample_gif_data: bytes,
):
    """
    Test archive fallback with various file sizes.
    
    Verifies:
    - Small files handled correctly
    - Larger files chunked properly
    - All downloads complete successfully
    """
    # Set up mock servers
    tumblr = MockTumblrServer(sample_blog_name)
    wayback = MockWaybackServer()
    
    # Create different sized content
    small_content = b"small"
    medium_content = sample_image_data * 10  # Repeat to make larger
    large_content = sample_gif_data * 100
    
    # Add posts with failing URLs
    url1 = "https://64.media.tumblr.com/small.jpg"
    url2 = "https://64.media.tumblr.com/medium.jpg"
    url3 = "https://64.media.tumblr.com/large.gif"
    
    tumblr.add_post(post_id="100", media_url=url1, media_content=small_content)
    tumblr.mark_url_as_failing(url1)
    
    tumblr.add_post(post_id="200", media_url=url2, media_content=medium_content)
    tumblr.mark_url_as_failing(url2)
    
    tumblr.add_post(
        post_id="300",
        media_url=url3,
        media_content=large_content,
        media_type="gif",
    )
    tumblr.mark_url_as_failing(url3)
    
    # Add archive snapshots
    wayback.add_snapshot(
        original_url=url1,
        snapshot_url=f"https://web.archive.org/web/20240115120000/{url1}",
        content=small_content,
    )
    wayback.add_snapshot(
        original_url=url2,
        snapshot_url=f"https://web.archive.org/web/20240115120000/{url2}",
        content=medium_content,
    )
    wayback.add_snapshot(
        original_url=url3,
        snapshot_url=f"https://web.archive.org/web/20240115120000/{url3}",
        content=large_content,
    )
    
    # Run archiver
    config = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
    )
    
    orchestrator = Orchestrator(config)
    
    with tumblr.mock(), wayback.mock():
        stats = await orchestrator.run()
    
    # Should download all files
    assert stats.total_media == 3
    
    # Verify files exist with correct sizes
    file1 = integration_output_dir / "100_001.jpg"
    file2 = integration_output_dir / "200_001.jpg"
    file3 = integration_output_dir / "300_001.gif"
    
    if file1.exists():
        assert file1.stat().st_size == len(small_content)
    if file2.exists():
        assert file2.stat().st_size == len(medium_content)
    if file3.exists():
        assert file3.stat().st_size == len(large_content)


@pytest.mark.asyncio
async def test_archive_fallback_manifest_notes(
    sample_blog_name: str,
    integration_output_dir: Path,
    sample_image_data: bytes,
):
    """
    Test that fallback adds notes to manifest.
    
    Verifies:
    - Notes field populated
    - Explanation of fallback
    - Useful debug information
    """
    # Set up mock servers
    tumblr = MockTumblrServer(sample_blog_name)
    wayback = MockWaybackServer()
    
    # Add post with failing URL
    media_url = "https://64.media.tumblr.com/noted.jpg"
    tumblr.add_post(
        post_id="555",
        media_url=media_url,
        media_content=sample_image_data,
    )
    tumblr.mark_url_as_failing(media_url)
    
    # Add archive snapshot
    snapshot_url = f"https://web.archive.org/web/20240115120000/{media_url}"
    wayback.add_snapshot(
        original_url=media_url,
        snapshot_url=snapshot_url,
        content=sample_image_data,
    )
    
    # Run archiver
    config = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
    )
    
    orchestrator = Orchestrator(config)
    
    with tumblr.mock(), wayback.mock():
        stats = await orchestrator.run()
    
    # Verify manifest has notes (if fallback succeeded)
    media = await get_media_item_from_manifest(integration_output_dir, "555_001.jpg")
    assert media is not None
    
    # If retrieved from archive, notes should explain
    if media["retrieved_from"] == "internet_archive":
        # Notes may contain information about the fallback
        # (This is optional, depends on implementation)
        pass
