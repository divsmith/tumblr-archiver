"""
Shared fixtures for integration tests.

Provides common fixtures, mock data, and helper functions for
integration testing the complete archival workflow.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, List

import pytest

from tumblr_archiver.config import ArchiverConfig
from tumblr_archiver.models import MediaItem, Post


@pytest.fixture
def sample_blog_name() -> str:
    """Sample blog name for testing."""
    return "testblog"


@pytest.fixture
def integration_output_dir(tmp_path: Path) -> Path:
    """
    Create temporary output directory for integration tests.
    
    Args:
        tmp_path: pytest's temporary directory fixture
        
    Returns:
        Path to temporary output directory
    """
    output_dir = tmp_path / "archive"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


@pytest.fixture
def sample_config(sample_blog_name: str, integration_output_dir: Path) -> ArchiverConfig:
    """
    Create sample archiver configuration for integration tests.
    
    Args:
        sample_blog_name: Blog name to archive
        integration_output_dir: Output directory path
        
    Returns:
        ArchiverConfig instance configured for testing
    """
    return ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir,
        concurrency=2,
        rate_limit=100.0,  # Fast for tests
        max_retries=2,
        resume=True,
        dry_run=False,
        verbose=False,
    )


@pytest.fixture
def sample_media_items() -> List[MediaItem]:
    """
    Create sample media items for testing.
    
    Returns:
        List of MediaItem instances
    """
    return [
        MediaItem(
            post_id="123456789",
            post_url="https://testblog.tumblr.com/post/123456789",
            timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            media_type="image",
            filename="123456789_001.jpg",
            original_url="https://64.media.tumblr.com/abc123/tumblr_img1.jpg",
            retrieved_from="tumblr",
            status="missing",
        ),
        MediaItem(
            post_id="987654321",
            post_url="https://testblog.tumblr.com/post/987654321",
            timestamp=datetime(2024, 1, 14, 15, 20, 0, tzinfo=timezone.utc),
            media_type="image",
            filename="987654321_001.png",
            original_url="https://64.media.tumblr.com/xyz789/tumblr_img2.png",
            retrieved_from="tumblr",
            status="missing",
        ),
        MediaItem(
            post_id="555666777",
            post_url="https://testblog.tumblr.com/post/555666777",
            timestamp=datetime(2024, 1, 14, 8, 0, 0, tzinfo=timezone.utc),
            media_type="gif",
            filename="555666777_001.gif",
            original_url="https://64.media.tumblr.com/def456/tumblr_anim.gif",
            retrieved_from="tumblr",
            status="missing",
        ),
    ]


@pytest.fixture
def sample_posts(sample_media_items: List[MediaItem]) -> List[Post]:
    """
    Create sample posts with media items.
    
    Args:
        sample_media_items: List of media items to include
        
    Returns:
        List of Post instances
    """
    # Group media items by post_id
    posts_dict = {}
    for item in sample_media_items:
        if item.post_id not in posts_dict:
            posts_dict[item.post_id] = {
                "post_id": item.post_id,
                "post_url": item.post_url,
                "timestamp": item.timestamp,
                "is_reblog": False,
                "media_items": [],
            }
        posts_dict[item.post_id]["media_items"].append(item)
    
    return [Post(**data) for data in posts_dict.values()]


@pytest.fixture
def sample_image_data() -> bytes:
    """
    Create sample image data for testing.
    
    Returns:
        Binary image data (minimal PNG)
    """
    # Minimal 1x1 PNG image
    return (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
        b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    )


@pytest.fixture
def sample_gif_data() -> bytes:
    """
    Create sample GIF data for testing.
    
    Returns:
        Binary GIF data (minimal GIF)
    """
    # Minimal 1x1 GIF image
    return (
        b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00'
        b'!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00'
        b'\x00\x02\x02D\x01\x00;'
    )


@pytest.fixture
def sample_video_data() -> bytes:
    """
    Create sample video data for testing.
    
    Returns:
        Binary video data (minimal MP4)
    """
    # Minimal MP4 file header
    return (
        b'\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41'
        b'\x00\x00\x00\x08free\x00\x00\x00\x2fmdat'
    )


def create_test_media_content(media_type: str) -> bytes:
    """
    Helper to create test media content based on type.
    
    Args:
        media_type: Type of media (image, gif, video)
        
    Returns:
        Binary content appropriate for the media type
    """
    if media_type == "gif":
        return (
            b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00'
            b'!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00'
            b'\x00\x02\x02D\x01\x00;'
        )
    elif media_type == "video":
        return (
            b'\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41'
            b'\x00\x00\x00\x08free\x00\x00\x00\x2fmdat'
        )
    else:  # image
        return (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
            b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )


async def verify_manifest_file(output_dir: Path, expected_posts: int, expected_media: int) -> bool:
    """
    Verify manifest.json exists and has expected structure.
    
    Args:
        output_dir: Directory containing manifest.json
        expected_posts: Expected number of posts
        expected_media: Expected number of media items
        
    Returns:
        True if manifest is valid, False otherwise
    """
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.exists():
        return False
    
    import json
    with open(manifest_path) as f:
        data = json.load(f)
    
    # Check required fields
    if "blog_name" not in data or "posts" not in data:
        return False
    
    # Check counts
    if data.get("total_posts") != expected_posts:
        return False
    
    if data.get("total_media") != expected_media:
        return False
    
    return True


async def verify_downloaded_files(
    output_dir: Path,
    expected_filenames: List[str]
) -> bool:
    """
    Verify that expected files were downloaded.
    
    Args:
        output_dir: Directory containing downloaded files
        expected_filenames: List of expected filenames
        
    Returns:
        True if all files exist, False otherwise
    """
    for filename in expected_filenames:
        file_path = output_dir / filename
        if not file_path.exists():
            return False
        
        # Verify file is not empty
        if file_path.stat().st_size == 0:
            return False
    
    return True


async def count_manifest_items(output_dir: Path, status: str) -> int:
    """
    Count media items with specific status in manifest.
    
    Args:
        output_dir: Directory containing manifest.json
        status: Status to count (downloaded, archived, missing, error)
        
    Returns:
        Number of items with the specified status
    """
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.exists():
        return 0
    
    import json
    with open(manifest_path) as f:
        data = json.load(f)
    
    count = 0
    for post in data.get("posts", []):
        for media in post.get("media_items", []):
            if media.get("status") == status:
                count += 1
    
    return count


async def get_media_item_from_manifest(
    output_dir: Path,
    filename: str
) -> dict:
    """
    Get a specific media item from manifest by filename.
    
    Args:
        output_dir: Directory containing manifest.json
        filename: Filename to search for
        
    Returns:
        Media item dictionary or None if not found
    """
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    
    import json
    with open(manifest_path) as f:
        data = json.load(f)
    
    for post in data.get("posts", []):
        for media in post.get("media_items", []):
            if media.get("filename") == filename:
                return media
    
    return None
