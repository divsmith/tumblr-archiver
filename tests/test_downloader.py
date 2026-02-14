"""Tests for media downloader."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from aiohttp import StreamReader

from tumblr_archiver.archive import Snapshot, WaybackClient
from tumblr_archiver.checksum import calculate_file_checksum
from tumblr_archiver.deduplicator import FileDeduplicator
from tumblr_archiver.downloader import DownloadError, MediaDownloader
from tumblr_archiver.http_client import AsyncHTTPClient, HTTPError
from tumblr_archiver.models import MediaItem


@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client."""
    client = Mock(spec=AsyncHTTPClient)
    return client


@pytest.fixture
def mock_wayback_client():
    """Create a mock Wayback client."""
    client = Mock(spec=WaybackClient)
    return client


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create a temporary output directory."""
    output_dir = tmp_path / "downloads"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def media_item():
    """Create a sample media item."""
    return MediaItem(
        post_id="123456789",
        post_url="https://example.tumblr.com/post/123456789",
        timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        media_type="image",
        filename="123456789_001.jpg",
        original_url="https://64.media.tumblr.com/abc123/tumblr_xyz.jpg",
        retrieved_from="tumblr",
        status="downloaded",
    )


@pytest.fixture
def downloader(mock_http_client, mock_wayback_client, temp_output_dir):
    """Create a media downloader instance."""
    return MediaDownloader(
        http_client=mock_http_client,
        wayback_client=mock_wayback_client,
        output_dir=temp_output_dir,
    )


def create_mock_response(content: bytes, status: int = 200):
    """Create a mock aiohttp response."""
    response = AsyncMock()
    response.status = status
    response.content_length = len(content)
    
    # Mock the content.iter_chunked method
    async def iter_chunked(chunk_size):
        for i in range(0, len(content), chunk_size):
            yield content[i:i + chunk_size]
    
    response.content.iter_chunked = iter_chunked
    response.read = AsyncMock(return_value=content)
    
    return response


@pytest.mark.asyncio
async def test_successful_download_from_tumblr(downloader, media_item, temp_output_dir):
    """Test successful download from Tumblr URL."""
    # Mock HTTP response
    test_content = b"Test image content"
    mock_response = create_mock_response(test_content)
    downloader.http_client.get = AsyncMock(return_value=mock_response)
    
    # Download media
    result = await downloader.download_media(media_item)
    
    # Verify download was attempted
    downloader.http_client.get.assert_called_once_with(media_item.original_url)
    
    # Verify result
    assert result.status == "downloaded"
    assert result.retrieved_from == "tumblr"
    assert result.checksum is not None
    assert len(result.checksum) == 64
    assert result.byte_size == len(test_content)
    
    # Verify file was created
    output_path = temp_output_dir / "images" / media_item.filename
    assert output_path.exists()
    assert output_path.read_bytes() == test_content


@pytest.mark.asyncio
async def test_fallback_to_internet_archive(downloader, media_item, temp_output_dir):
    """Test fallback to Internet Archive when Tumblr returns 404."""
    # Mock Tumblr request to fail with 404
    tumblr_error = HTTPError("Not found", status=404, url=media_item.original_url)
    
    # Mock successful archive download
    test_content = b"Archived image content"
    mock_response = create_mock_response(test_content)
    
    # First call raises 404, second call succeeds
    downloader.http_client.get = AsyncMock(side_effect=[tumblr_error, mock_response])
    
    # Mock Wayback snapshot
    snapshot = Snapshot(
        timestamp="20240115103000",
        statuscode="200",
        mimetype="image/jpeg",
        original_url=media_item.original_url,
        snapshot_url=f"https://web.archive.org/web/20240115103000/{media_item.original_url}",
    )
    downloader.wayback_client.get_best_snapshot = AsyncMock(return_value=snapshot)
    
    # Download media
    result = await downloader.download_media(media_item)
    
    # Verify fallback was used
    assert downloader.http_client.get.call_count == 2
    downloader.wayback_client.get_best_snapshot.assert_called_once_with(
        media_item.original_url
    )
    
    # Verify result
    assert result.status == "archived"
    assert result.retrieved_from == "internet_archive"
    assert result.archive_snapshot_url == snapshot.snapshot_url
    assert result.checksum is not None
    assert result.byte_size == len(test_content)
    
    # Verify file was created
    output_path = temp_output_dir / "images" / media_item.filename
    assert output_path.exists()
    assert output_path.read_bytes() == test_content


@pytest.mark.asyncio
async def test_download_failure_both_sources(downloader, media_item):
    """Test error handling when both Tumblr and Archive fail."""
    # Mock Tumblr request to fail
    tumblr_error = HTTPError("Not found", status=404, url=media_item.original_url)
    downloader.http_client.get = AsyncMock(side_effect=tumblr_error)
    
    # Mock Archive to return no snapshots
    downloader.wayback_client.get_best_snapshot = AsyncMock(return_value=None)
    
    # Download should fail
    with pytest.raises(DownloadError):
        await downloader.download_media(media_item)
    
    # Verify error status was set
    assert media_item.status == "error"
    assert media_item.notes is not None


@pytest.mark.asyncio
async def test_checksum_calculation(downloader, media_item, temp_output_dir):
    """Test that checksum is correctly calculated."""
    # Mock HTTP response with known content
    test_content = b"Test image content for checksum"
    mock_response = create_mock_response(test_content)
    downloader.http_client.get = AsyncMock(return_value=mock_response)
    
    # Download media
    result = await downloader.download_media(media_item)
    
    # Verify checksum
    import hashlib
    expected_checksum = hashlib.sha256(test_content).hexdigest()
    assert result.checksum == expected_checksum


@pytest.mark.asyncio
async def test_skip_existing_file(downloader, media_item, temp_output_dir):
    """Test that existing files are skipped (resume capability)."""
    # Create an existing file
    output_path = temp_output_dir / "images" / media_item.filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    test_content = b"Existing file content"
    output_path.write_bytes(test_content)
    
    # Download media (should skip)
    result = await downloader.download_media(media_item)
    
    # Verify no HTTP request was made
    downloader.http_client.get.assert_not_called()
    
    # Verify result
    assert result.checksum is not None
    assert result.byte_size == len(test_content)
    assert "already existed" in result.notes.lower()


@pytest.mark.asyncio
async def test_subdirectory_creation(downloader, media_item, temp_output_dir):
    """Test that subdirectories are created for different media types."""
    # Test image subdirectory
    assert (temp_output_dir / "images").exists()
    
    # Test gif subdirectory
    assert (temp_output_dir / "gifs").exists()
    
    # Test video subdirectory
    assert (temp_output_dir / "videos").exists()


@pytest.mark.asyncio
async def test_media_types_in_correct_subdirs(
    mock_http_client, mock_wayback_client, temp_output_dir
):
    """Test that different media types are saved in correct subdirectories."""
    downloader = MediaDownloader(
        http_client=mock_http_client,
        wayback_client=mock_wayback_client,
        output_dir=temp_output_dir,
    )
    
    # Test image with unique content
    image_content = b"Image content"
    mock_http_client.get = AsyncMock(return_value=create_mock_response(image_content))
    
    image_item = MediaItem(
        post_id="123",
        post_url="https://example.tumblr.com/post/123",
        timestamp=datetime.now(timezone.utc),
        media_type="image",
        filename="test.jpg",
        original_url="https://example.com/test.jpg",
        retrieved_from="tumblr",
        status="downloaded",
    )
    await downloader.download_media(image_item)
    assert (temp_output_dir / "images" / "test.jpg").exists()
    
    # Test gif with different content to avoid deduplication
    gif_content = b"GIF content - different from image"
    mock_http_client.get = AsyncMock(return_value=create_mock_response(gif_content))
    
    gif_item = MediaItem(
        post_id="124",
        post_url="https://example.tumblr.com/post/124",
        timestamp=datetime.now(timezone.utc),
        media_type="gif",
        filename="test.gif",
        original_url="https://example.com/test.gif",
        retrieved_from="tumblr",
        status="downloaded",
    )
    await downloader.download_media(gif_item)
    assert (temp_output_dir / "gifs" / "test.gif").exists()
    
    # Test video with different content to avoid deduplication
    video_content = b"Video content - different from others"
    mock_http_client.get = AsyncMock(return_value=create_mock_response(video_content))
    
    video_item = MediaItem(
        post_id="125",
        post_url="https://example.tumblr.com/post/125",
        timestamp=datetime.now(timezone.utc),
        media_type="video",
        filename="test.mp4",
        original_url="https://example.com/test.mp4",
        retrieved_from="tumblr",
        status="downloaded",
    )
    await downloader.download_media(video_item)
    assert (temp_output_dir / "videos" / "test.mp4").exists()


@pytest.mark.asyncio
async def test_progress_callback(downloader, media_item):
    """Test that progress callback is called during download."""
    # Mock HTTP response
    test_content = b"A" * 10000  # 10KB
    mock_response = create_mock_response(test_content)
    downloader.http_client.get = AsyncMock(return_value=mock_response)
    
    # Track progress callbacks
    progress_calls = []
    
    def progress_callback(downloaded, total):
        progress_calls.append((downloaded, total))
    
    # Download with progress callback
    await downloader.download_media(media_item, progress_callback=progress_callback)
    
    # Verify progress was tracked
    assert len(progress_calls) > 0
    
    # Verify final progress
    final_downloaded, final_total = progress_calls[-1]
    assert final_downloaded == len(test_content)
    assert final_total == len(test_content)


@pytest.mark.asyncio
async def test_deduplication(downloader, media_item, temp_output_dir):
    """Test that duplicate files are detected and reused."""
    # Download first file
    test_content = b"Test content"
    mock_response = create_mock_response(test_content)
    downloader.http_client.get = AsyncMock(return_value=mock_response)
    
    result1 = await downloader.download_media(media_item)
    checksum1 = result1.checksum
    original_filename = result1.filename
    
    # Verify first file exists
    output_path1 = temp_output_dir / "images" / original_filename
    assert output_path1.exists()
    
    # Download duplicate file with different filename
    media_item2 = MediaItem(
        post_id="987654321",
        post_url="https://example.tumblr.com/post/987654321",
        timestamp=datetime.now(timezone.utc),
        media_type="image",
        filename="987654321_001.jpg",  # Different filename
        original_url="https://64.media.tumblr.com/different/url.jpg",
        retrieved_from="tumblr",
        status="downloaded",
    )
    
    mock_response2 = create_mock_response(test_content)  # Same content
    downloader.http_client.get = AsyncMock(return_value=mock_response2)
    
    result2 = await downloader.download_media(media_item2)
    
    # Verify duplicate was detected
    assert result2.checksum == checksum1
    assert "duplicate" in result2.notes.lower()
    
    # Verify the filename was updated to point to the existing file
    assert result2.filename == original_filename
    
    # Verify only the original file exists
    assert output_path1.exists()
    
    # The second file should not exist at its intended location
    output_path2 = temp_output_dir / "images" / "987654321_001.jpg"
    assert not output_path2.exists()


@pytest.mark.asyncio
async def test_custom_deduplicator(
    mock_http_client, mock_wayback_client, temp_output_dir
):
    """Test using a custom deduplicator instance."""
    # Create a custom deduplicator
    custom_dedup = FileDeduplicator()
    
    # Add a pre-existing checksum
    existing_checksum = "a" * 64
    existing_path = "/path/to/existing/file.jpg"
    custom_dedup.add_file(existing_checksum, existing_path)
    
    # Create downloader with custom deduplicator
    downloader = MediaDownloader(
        http_client=mock_http_client,
        wayback_client=mock_wayback_client,
        output_dir=temp_output_dir,
        deduplicator=custom_dedup,
    )
    
    # Verify the deduplicator is the same instance
    assert downloader.deduplicator is custom_dedup
    assert downloader.deduplicator.is_duplicate(existing_checksum)


@pytest.mark.asyncio
async def test_error_handling_tumblr_500(downloader, media_item):
    """Test handling of server errors (500) from Tumblr."""
    # Mock Tumblr request to fail with 500
    tumblr_error = HTTPError("Server error", status=500, url=media_item.original_url)
    downloader.http_client.get = AsyncMock(side_effect=tumblr_error)
    
    # Mock successful archive download
    test_content = b"Archived content"
    mock_response = create_mock_response(test_content)
    
    # Set up responses: first call raises 500, second succeeds
    call_count = [0]
    
    async def get_with_fallback(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise tumblr_error
        return mock_response
    
    downloader.http_client.get = get_with_fallback
    
    # Mock Wayback snapshot
    snapshot = Snapshot(
        timestamp="20240115103000",
        statuscode="200",
        mimetype="image/jpeg",
        original_url=media_item.original_url,
        snapshot_url=f"https://web.archive.org/web/20240115103000/{media_item.original_url}",
    )
    downloader.wayback_client.get_best_snapshot = AsyncMock(return_value=snapshot)
    
    # Download should succeed via archive
    result = await downloader.download_media(media_item)
    
    assert result.status == "archived"
    assert result.retrieved_from == "internet_archive"


@pytest.mark.asyncio
async def test_repr(downloader, temp_output_dir):
    """Test string representation of downloader."""
    repr_str = repr(downloader)
    
    assert "MediaDownloader" in repr_str
    assert str(temp_output_dir) in repr_str
    assert "deduplicator" in repr_str


@pytest.mark.asyncio
async def test_corrupted_existing_file_redownload(downloader, media_item, temp_output_dir):
    """Test that corrupted existing files are re-downloaded."""
    # Create a corrupted existing file
    output_path = temp_output_dir / "images" / media_item.filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"corrupted")
    
    # Mock HTTP response for re-download
    test_content = b"Fresh download"
    mock_response = create_mock_response(test_content)
    downloader.http_client.get = AsyncMock(return_value=mock_response)
    
    # Patch the checksum function to fail on first call (simulating corruption),
    # then succeed on second call (after re-download)
    call_count = [0]
    original_checksum = calculate_file_checksum
    
    async def mock_checksum(filepath):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call - simulate corruption
            raise Exception("Checksum calculation failed")
        else:
            # Second call - calculate actual checksum
            return await original_checksum(filepath)
    
    with patch('tumblr_archiver.downloader.calculate_file_checksum', 
               side_effect=mock_checksum):
        result = await downloader.download_media(media_item)
    
    # Verify file was re-downloaded
    downloader.http_client.get.assert_called_once()
    
    # Verify the file now has the new content
    assert output_path.read_bytes() == test_content
    assert result.checksum is not None

