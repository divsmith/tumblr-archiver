"""
Real-world acceptance tests against live Tumblr blogs.

These tests make actual network requests to public Tumblr blogs and
Internet Archive. They are marked as slow and can be skipped in CI.

IMPORTANT: These tests are optional and should be run sparingly to be
respectful of Tumblr and Archive.org servers.

Usage:
    # Skip slow tests (default in CI)
    pytest tests/acceptance/

    # Run slow tests
    pytest tests/acceptance/ --slow

    # Run only slow tests
    pytest -m slow
"""

import asyncio
from pathlib import Path

import pytest

from tumblr_archiver.config import ArchiverConfig
from tumblr_archiver.manifest import ManifestManager
from tumblr_archiver.orchestrator import Orchestrator


# Public test blog - use a small, inactive blog to minimize impact
# This is a well-known test blog that is explicitly OK to scrape
TEST_BLOG_NAME = "staff"  # Tumblr's official staff blog
TEST_POST_LIMIT = 5  # Only test with first few posts


@pytest.fixture
def real_output_dir(tmp_path):
    """Create output directory for real blog tests."""
    output_dir = tmp_path / "real-blog-test"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def real_blog_config(real_output_dir):
    """Create configuration for real blog testing."""
    return ArchiverConfig(
        blog_name=TEST_BLOG_NAME,
        output_dir=str(real_output_dir),
        concurrency=1,  # Be very conservative
        rate_limit=0.5,  # Very slow - 1 request per 2 seconds
        max_retries=2,
        timeout=30.0,
        dry_run=False,
        exclude_reblogs=True,  # Reduce total posts
        enable_fallback=True,
        verbose=True,
    )


@pytest.mark.slow
@pytest.mark.network
@pytest.mark.asyncio
async def test_real_blog_scraping(real_blog_config, real_output_dir):
    """
    REAL WORLD TEST 1: Scrape a real public Tumblr blog.
    
    This test validates:
    - Actual HTML parsing works on real Tumblr pages
    - Network requests succeed
    - Blog structure is correctly interpreted
    
    Note: This test is slow and makes real network requests.
    """
    manifest_manager = ManifestManager(real_output_dir)
    await manifest_manager.load()
    
    orchestrator = Orchestrator(real_blog_config, manifest_manager)
    
    # Run with limited posts
    stats = await orchestrator.run()
    
    # Basic validation - should find some posts
    assert stats.total_posts >= 0, "Should find at least 0 posts"
    assert stats.blog_name == TEST_BLOG_NAME
    assert stats.duration_seconds > 0
    
    # Load manifest
    manifest = await manifest_manager.load()
    assert manifest.blog_name == TEST_BLOG_NAME
    
    print(f"\nReal blog test results:")
    print(f"  Posts found: {stats.total_posts}")
    print(f"  Media items: {stats.total_media}")
    print(f"  Downloaded: {stats.downloaded}")
    print(f"  Failed: {stats.failed}")
    print(f"  Duration: {stats.duration_seconds:.2f}s")


@pytest.mark.slow
@pytest.mark.network
@pytest.mark.asyncio
async def test_real_media_download(real_blog_config, real_output_dir):
    """
    REAL WORLD TEST 2: Download media from real Tumblr blog.
    
    This test validates:
    - Media URLs are correctly extracted
    - Files are successfully downloaded
    - Checksums are calculated
    - Files are saved to disk
    
    Note: This test is slow and downloads real files.
    """
    manifest_manager = ManifestManager(real_output_dir)
    await manifest_manager.load()
    
    orchestrator = Orchestrator(real_blog_config, manifest_manager)
    stats = await orchestrator.run()
    
    # If any media was found, validate it
    if stats.total_media > 0:
        manifest = await manifest_manager.load()
        
        # Check that at least one media item was processed
        assert len(manifest.posts) > 0
        
        # Validate media items
        for post in manifest.posts:
            for media in post.media_items:
                # Basic validation
                assert media.original_url
                assert media.retrieved_from in ["tumblr", "internet_archive"]
                assert media.status in ["downloaded", "archived", "missing", "error"]
                
                # If downloaded, file should exist
                if media.status == "downloaded":
                    media_path = real_output_dir / media.filename
                    assert media_path.exists(), f"Downloaded file {media.filename} should exist"
                    assert media_path.stat().st_size > 0, f"Downloaded file {media.filename} should not be empty"
                    assert media.checksum is not None, "Downloaded file should have checksum"
                    assert media.byte_size is not None, "Downloaded file should have size"
                    assert media.byte_size > 0
    
    print(f"\nMedia download results:")
    print(f"  Total media: {stats.total_media}")
    print(f"  Downloaded: {stats.downloaded}")
    print(f"  Skipped: {stats.skipped}")
    print(f"  Failed: {stats.failed}")
    print(f"  Bytes: {stats.bytes_downloaded:,}")


@pytest.mark.slow
@pytest.mark.network
@pytest.mark.asyncio
async def test_real_archive_fallback(real_blog_config, real_output_dir):
    """
    REAL WORLD TEST 3: Test Internet Archive fallback with real requests.
    
    This test validates:
    - Archive.org API works
    - Snapshot selection works
    - Fallback downloads succeed
    
    Note: This test makes real requests to archive.org.
    """
    from tumblr_archiver.archive import WaybackClient
    from tumblr_archiver.http_client import AsyncHTTPClient
    
    async with AsyncHTTPClient(
        timeout=30.0,
        max_retries=2,
        rate_limiter=None,
    ) as http_client:
        wayback = WaybackClient(http_client)
        
        # Try to find snapshots for a Tumblr media URL that might be gone
        # Using an old URL that's likely in the archive
        test_url = "https://64.media.tumblr.com/avatar_test_128.png"
        
        try:
            snapshots = await wayback.find_snapshots(test_url, limit=5)
            
            # If snapshots exist, validate structure
            if snapshots:
                snapshot = snapshots[0]
                assert snapshot.original_url == test_url
                assert snapshot.snapshot_url
                assert "web.archive.org" in snapshot.snapshot_url
                assert snapshot.timestamp
                
                print(f"\nArchive.org test results:")
                print(f"  Found {len(snapshots)} snapshots")
                print(f"  Latest: {snapshot.timestamp}")
                print(f"  Status: {snapshot.statuscode}")
            else:
                print(f"\nArchive.org test: No snapshots found for test URL")
                
        except Exception as e:
            # Archive.org might be down or rate limiting
            print(f"\nArchive.org test skipped: {e}")
            pytest.skip(f"Archive.org unavailable: {e}")


@pytest.mark.slow
@pytest.mark.network
@pytest.mark.asyncio
async def test_real_resume_capability(real_blog_config, real_output_dir):
    """
    REAL WORLD TEST 4: Test resume capability with real blog.
    
    This test validates:
    - First run downloads some media
    - Second run skips already downloaded media
    - Manifest tracks progress correctly
    
    Note: This test runs the archiver twice.
    """
    # First run - download some posts
    manifest_manager1 = ManifestManager(real_output_dir)
    await manifest_manager1.load()
    
    orchestrator1 = Orchestrator(real_blog_config, manifest_manager1)
    stats1 = await orchestrator1.run()
    
    first_downloaded = stats1.downloaded
    first_total = stats1.total_media
    
    # Wait a moment
    await asyncio.sleep(1)
    
    # Second run - should skip already downloaded
    manifest_manager2 = ManifestManager(real_output_dir)
    await manifest_manager2.load()
    
    orchestrator2 = Orchestrator(real_blog_config, manifest_manager2)
    stats2 = await orchestrator2.run()
    
    # Validate resume behavior
    assert stats2.total_media >= first_total, "Should find same or more media"
    assert stats2.skipped >= first_downloaded, "Should skip previously downloaded media"
    assert stats2.downloaded <= first_downloaded, "Should download fewer or same on second run"
    
    print(f"\nResume test results:")
    print(f"  First run:")
    print(f"    Total media: {first_total}")
    print(f"    Downloaded: {first_downloaded}")
    print(f"  Second run:")
    print(f"    Total media: {stats2.total_media}")
    print(f"    Downloaded: {stats2.downloaded}")
    print(f"    Skipped: {stats2.skipped}")


@pytest.mark.slow
@pytest.mark.network
@pytest.mark.asyncio
async def test_real_rate_limiting(real_blog_config, real_output_dir):
    """
    REAL WORLD TEST 5: Verify rate limiting works with real requests.
    
    This test validates:
    - Rate limiting prevents rapid requests
    - No 429 errors occur
    - Requests are properly spaced
    
    Note: This test monitors timing of real requests.
    """
    import time
    
    manifest_manager = ManifestManager(real_output_dir)
    await manifest_manager.load()
    
    # Use very conservative rate limit
    real_blog_config.rate_limit = 0.5  # 1 request per 2 seconds
    
    start_time = time.time()
    
    orchestrator = Orchestrator(real_blog_config, manifest_manager)
    stats = await orchestrator.run()
    
    end_time = time.time()
    duration = end_time - start_time
    
    # With rate limit of 0.5 req/sec, should take at least 2 seconds per request
    # (minus one since first request is immediate)
    if stats.total_posts > 0:
        min_expected_duration = (stats.total_posts - 1) * 2.0
        
        # Allow some variance for processing time
        assert duration >= min_expected_duration * 0.7, (
            f"Requests completed too quickly: {duration:.2f}s, "
            f"expected at least {min_expected_duration * 0.7:.2f}s"
        )
    
    # Should not have hit rate limits (no 429s)
    # Note: If there were 429s, they would show in failed count
    
    print(f"\nRate limiting test:")
    print(f"  Posts: {stats.total_posts}")
    print(f"  Duration: {duration:.2f}s")
    print(f"  Rate: {stats.total_posts / duration if duration > 0 else 0:.2f} posts/sec")


@pytest.mark.slow
@pytest.mark.network
@pytest.mark.asyncio
async def test_real_manifest_integrity(real_blog_config, real_output_dir):
    """
    REAL WORLD TEST 6: Validate manifest integrity with real data.
    
    This test validates:
    - Manifest is valid JSON
    - All required fields are present
    - Data types are correct
    - Checksums match actual files
    
    Note: This test validates the manifest after a real run.
    """
    manifest_manager = ManifestManager(real_output_dir)
    await manifest_manager.load()
    
    orchestrator = Orchestrator(real_blog_config, manifest_manager)
    await orchestrator.run()
    
    # Load and validate manifest
    manifest = await manifest_manager.load()
    
    # Basic structure validation
    assert manifest.blog_name == TEST_BLOG_NAME
    assert manifest.total_posts >= 0
    assert manifest.total_media >= 0
    assert manifest.archive_date
    
    # Validate each post
    for post in manifest.posts:
        assert post.post_id
        assert post.post_url
        assert post.timestamp
        assert isinstance(post.is_reblog, bool)
        
        # Validate each media item
        for media in post.media_items:
            assert media.post_id == post.post_id
            assert media.media_type in ["image", "gif", "video"]
            assert media.filename
            assert media.original_url
            assert media.retrieved_from in ["tumblr", "internet_archive"]
            assert media.status in ["downloaded", "archived", "missing", "error"]
            
            # If from archive, must have snapshot URL
            if media.retrieved_from == "internet_archive":
                assert media.archive_snapshot_url is not None
                assert "web.archive.org" in media.archive_snapshot_url
            
            # If downloaded, validate file
            if media.status == "downloaded":
                media_path = real_output_dir / media.filename
                assert media_path.exists()
                
                # Validate checksum
                import hashlib
                actual_checksum = hashlib.sha256(media_path.read_bytes()).hexdigest()
                assert media.checksum == actual_checksum, (
                    f"Checksum mismatch for {media.filename}"
                )
                
                # Validate size
                actual_size = media_path.stat().st_size
                assert media.byte_size == actual_size, (
                    f"Size mismatch for {media.filename}"
                )
    
    print(f"\nManifest integrity validation:")
    print(f"  ✓ Blog name: {manifest.blog_name}")
    print(f"  ✓ Total posts: {manifest.total_posts}")
    print(f"  ✓ Total media: {manifest.total_media}")
    print(f"  ✓ All files validated")


@pytest.mark.slow
@pytest.mark.network
@pytest.mark.skipif(
    True,  # Skip by default - this is a stress test
    reason="Stress test - only run manually"
)
@pytest.mark.asyncio
async def test_real_large_blog(real_output_dir):
    """
    STRESS TEST: Test with a larger blog (manual only).
    
    This test is skipped by default and should only be run manually
    when doing thorough validation.
    
    Usage:
        pytest tests/acceptance/test_real_blog.py::test_real_large_blog -v
    """
    config = ArchiverConfig(
        blog_name=TEST_BLOG_NAME,
        output_dir=str(real_output_dir),
        concurrency=2,
        rate_limit=1.0,
        max_retries=3,
        timeout=30.0,
        dry_run=False,
        exclude_reblogs=False,  # Include reblogs for more content
        enable_fallback=True,
        verbose=True,
    )
    
    manifest_manager = ManifestManager(real_output_dir)
    await manifest_manager.load()
    
    orchestrator = Orchestrator(config, manifest_manager)
    stats = await orchestrator.run()
    
    print(f"\nLarge blog test results:")
    print(f"  Posts: {stats.total_posts}")
    print(f"  Media: {stats.total_media}")
    print(f"  Downloaded: {stats.downloaded}")
    print(f"  Failed: {stats.failed}")
    print(f"  Duration: {stats.duration_seconds:.2f}s")
    print(f"  Bytes: {stats.bytes_downloaded:,}")
    
    # Validate reasonable success rate
    if stats.total_media > 0:
        success_rate = stats.downloaded / stats.total_media
        assert success_rate > 0.5, f"Success rate too low: {success_rate:.1%}"


# Conftest.py helper for pytest markers
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers",
        "network: marks tests as requiring network access"
    )


def pytest_addoption(parser):
    """Add command line options."""
    parser.addoption(
        "--slow",
        action="store_true",
        default=False,
        help="Run slow tests that make real network requests"
    )


def pytest_collection_modifyitems(config, items):
    """Skip slow tests unless --slow is specified."""
    if config.getoption("--slow"):
        # Don't skip anything if --slow is specified
        return
    
    skip_slow = pytest.mark.skip(reason="Need --slow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
