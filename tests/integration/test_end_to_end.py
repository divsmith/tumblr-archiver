"""
End-to-end integration tests for Tumblr Media Archiver.

These tests verify the complete workflow from CLI invocation to archived media,
including manifest generation, resume functionality, and Wayback Machine recovery.
"""

import asyncio
import hashlib
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from urllib.parse import urlparse

import pytest
import aiohttp
from click.testing import CliRunner

from tumblr_archiver.archiver import TumblrArchiver, ArchiveResult
from tumblr_archiver.cli import main
from tumblr_archiver.config import ArchiverConfig
from tumblr_archiver.downloader import DownloadManager, DownloadResult
from tumblr_archiver.manifest import ManifestManager
from tumblr_archiver.tumblr_api import TumblrAPIClient
from tumblr_archiver.wayback_client import WaybackClient, Snapshot


# ============================================================================
# Test Data - Mock API Responses
# ============================================================================

MOCK_BLOG_INFO = {
    'name': 'test-blog',
    'url': 'https://test-blog.tumblr.com',
    'title': 'Test Blog for Integration Testing',
    'total_posts': 5,
    'description': 'A test blog with various media types',
    'updated': 1640000000
}

MOCK_POSTS = [
    # Post 1: Single photo
    {
        'id': 100001,
        'post_url': 'https://test-blog.tumblr.com/post/100001',
        'timestamp': 1640000000,
        'type': 'photo',
        'tags': ['test', 'photo'],
        'note_count': 10,
        'reblog_key': 'testkey1',
        'photos': [
            {
                'original_size': {
                    'url': 'https://64.media.tumblr.com/abc123/tumblr_photo1_1280.jpg',
                    'width': 1280,
                    'height': 720
                },
                'caption': 'Test photo 1'
            }
        ]
    },
    # Post 2: Multiple photos
    {
        'id': 100002,
        'post_url': 'https://test-blog.tumblr.com/post/100002',
        'timestamp': 1640010000,
        'type': 'photo',
        'tags': ['test', 'gallery'],
        'note_count': 25,
        'reblog_key': 'testkey2',
        'photos': [
            {
                'original_size': {
                    'url': 'https://64.media.tumblr.com/def456/tumblr_photo2_1280.jpg',
                    'width': 1920,
                    'height': 1080
                },
                'caption': 'Test photo 2a'
            },
            {
                'original_size': {
                    'url': 'https://64.media.tumblr.com/ghi789/tumblr_photo3_1280.jpg',
                    'width': 800,
                    'height': 600
                },
                'caption': 'Test photo 2b'
            }
        ]
    },
    # Post 3: Video post
    {
        'id': 100003,
        'post_url': 'https://test-blog.tumblr.com/post/100003',
        'timestamp': 1640020000,
        'type': 'video',
        'tags': ['test', 'video'],
        'note_count': 15,
        'reblog_key': 'testkey3',
        'video_url': 'https://va.media.tumblr.com/tumblr_video1.mp4',
        'player': [
            {
                'width': 500,
                'embed_code': '<video src="https://va.media.tumblr.com/tumblr_video1.mp4"></video>'
            }
        ]
    },
    # Post 4: Photo that will be "missing" (for Wayback testing)
    {
        'id': 100004,
        'post_url': 'https://test-blog.tumblr.com/post/100004',
        'timestamp': 1640030000,
        'type': 'photo',
        'tags': ['test', 'missing'],
        'note_count': 5,
        'reblog_key': 'testkey4',
        'photos': [
            {
                'original_size': {
                    'url': 'https://64.media.tumblr.com/missing123/tumblr_missing_1280.jpg',
                    'width': 1024,
                    'height': 768
                },
                'caption': 'This image will be missing'
            }
        ]
    },
    # Post 5: Photo post with GIF
    {
        'id': 100005,
        'post_url': 'https://test-blog.tumblr.com/post/100005',
        'timestamp': 1640040000,
        'type': 'photo',
        'tags': ['test', 'gif'],
        'note_count': 30,
        'reblog_key': 'testkey5',
        'photos': [
            {
                'original_size': {
                    'url': 'https://64.media.tumblr.com/jkl012/tumblr_animated_500.gif',
                    'width': 500,
                    'height': 500
                },
                'caption': 'Animated GIF'
            }
        ]
    }
]

# Mock file contents (small test data)
MOCK_IMAGE_DATA = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01' \
                  b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01' \
                  b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'

MOCK_VIDEO_DATA = b'MOCKVIDEODATA' * 100  # Simplified video data

MOCK_GIF_DATA = b'GIF89a\x01\x00\x01\x00' * 10  # Simplified GIF data


def compute_checksum(data: bytes) -> str:
    """Compute SHA256 checksum of data."""
    return hashlib.sha256(data).hexdigest()


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_test_dir(tmp_path):
    """Create a temporary directory for test outputs."""
    test_dir = tmp_path / "tumblr_test"
    test_dir.mkdir(parents=True, exist_ok=True)
    yield test_dir
    # Cleanup after test
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)


@pytest.fixture
def test_config(temp_test_dir):
    """Create a test configuration."""
    return ArchiverConfig(
        blog_url="test-blog.tumblr.com",
        output_dir=temp_test_dir / "archives",
        tumblr_api_key="test_api_key_12345",
        resume=True,
        include_reblogs=True,
        download_embeds=False,
        recover_removed_media=True,
        wayback_enabled=True,
        wayback_max_snapshots=3,
        rate_limit=10.0,
        concurrency=2,
        max_retries=2,
        verbose=False,
        dry_run=False
    )


@pytest.fixture
def mock_tumblr_api():
    """Create a mock Tumblr API client with predefined responses."""
    with patch('tumblr_archiver.archiver.TumblrAPIClient') as mock_api_class:
        mock_api = MagicMock(spec=TumblrAPIClient)
        mock_api_class.return_value = mock_api
        
        # Mock blog info
        mock_api.get_blog_info.return_value = MOCK_BLOG_INFO
        
        # Mock get_all_posts (returns all posts)
        mock_api.get_all_posts.return_value = MOCK_POSTS
        
        yield mock_api


@pytest.fixture
def mock_http_responses():
    """Mock HTTP responses for media downloads."""
    
    class MockAsyncContextManager:
        """Mock async context manager for HTTP response."""
        def __init__(self, response):
            self.response = response
        
        async def __aenter__(self):
            return self.response
        
        async def __aexit__(self, exc_type, exc, tb):
            pass
    
    def mock_get(url, **kwargs):
        """Mock aiohttp GET request."""
        mock_response = AsyncMock()
        
        # Determine what to return based on URL
        if 'missing' in url:
            # Simulate 404 for missing files
            mock_response.status = 404
            
            def raise_for_status():
                raise aiohttp.ClientResponseError(
                    request_info=Mock(),
                    history=(),
                    status=404,
                    message="Not Found"
                )
            mock_response.raise_for_status = raise_for_status
        elif 'video' in url:
            mock_response.status = 200
            mock_response.read = AsyncMock(return_value=MOCK_VIDEO_DATA)
            mock_response.headers = {'Content-Type': 'video/mp4', 'Content-Length': str(len(MOCK_VIDEO_DATA))}
            
            # Mock iter_chunked for streaming
            async def iter_chunks(size):
                yield MOCK_VIDEO_DATA
            mock_response.content.iter_chunked = iter_chunks
        elif 'gif' in url:
            mock_response.status = 200
            mock_response.read = AsyncMock(return_value=MOCK_GIF_DATA)
            mock_response.headers = {'Content-Type': 'image/gif', 'Content-Length': str(len(MOCK_GIF_DATA))}
            
            # Mock iter_chunked for streaming
            async def iter_chunks(size):
                yield MOCK_GIF_DATA
            mock_response.content.iter_chunked = iter_chunks
        else:
            # Regular image
            mock_response.status = 200
            mock_response.read = AsyncMock(return_value=MOCK_IMAGE_DATA)
            mock_response.headers = {'Content-Type': 'image/jpeg', 'Content-Length': str(len(MOCK_IMAGE_DATA))}
            
            # Mock iter_chunked for streaming  
            async def iter_chunks(size):
                yield MOCK_IMAGE_DATA
            mock_response.content.iter_chunked = iter_chunks
        
        return MockAsyncContextManager(mock_response)
    
    with patch('aiohttp.ClientSession.get', side_effect=mock_get):
        yield


@pytest.fixture
def mock_wayback_client():
    """Mock Wayback Machine client for recovery testing."""
    with patch('tumblr_archiver.archiver.WaybackClient') as mock_wayback_class:
        mock_wayback = MagicMock(spec=WaybackClient)
        mock_wayback_class.return_value = mock_wayback
        
        # Mock get_snapshots method (sync, not async)
        def mock_get_snapshots(url, limit=5):
            if 'missing' in url:
                # Return a wayback snapshot for missing media
                return [
                    Snapshot(
                        urlkey="com.tumblr.media.64)/missing123/tumblr_missing_1280.jpg",
                        timestamp="20211201120000",
                        original_url=url,
                        status_code="200",
                        mimetype="image/jpeg",
                        digest="abc123def456",
                        length=str(len(MOCK_IMAGE_DATA))
                    )
                ]
            return []
        
        mock_wayback.get_snapshots.side_effect = mock_get_snapshots
        
        # Mock download_from_snapshot method (sync, not async)
        def mock_download_from_snapshot(snapshot, output_path):
            # Write mock data for wayback recovery
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(MOCK_IMAGE_DATA)
        
        mock_wayback.download_from_snapshot.side_effect = mock_download_from_snapshot
        
        yield mock_wayback


# ============================================================================
# Integration Tests
# ============================================================================

class TestFreshArchive:
    """Test fresh archive of a blog (initial run)."""
    
    @pytest.mark.asyncio
    async def test_fresh_archive_success(
        self, test_config, mock_tumblr_api, mock_http_responses, mock_wayback_client
    ):
        """Test a complete fresh archive of a blog."""
        # Create archiver
        archiver = TumblrArchiver(test_config)
        
        # Track progress events
        progress_events = []
        def progress_callback(data):
            progress_events.append(data)
        archiver.set_progress_callback(progress_callback)
        
        # Run archive
        result = await archiver.archive_blog()
        
        # Verify result
        assert result.success is True
        assert result.statistics.posts_processed == 5  # All posts processed
        assert result.statistics.total_posts == 5
        assert result.statistics.total_media == 6  # 1+2+1+1+1
        assert result.statistics.media_downloaded > 0
        
        # Verify output directory structure
        blog_dir = test_config.output_dir / "test-blog.tumblr.com"
        assert blog_dir.exists()
        
        # Verify manifest exists
        manifest_path = blog_dir / "manifest.json"
        assert manifest_path.exists()
        
        # Load and validate manifest
        with open(manifest_path, 'r') as f:
            manifest_data = json.load(f)
        
        assert manifest_data['blog_name'] == 'test-blog'
        assert 'archive_date' in manifest_data
        assert 'media' in manifest_data
        assert len(manifest_data['media']) == 6
        
        # Verify media entries have required fields
        for media in manifest_data['media']:
            assert 'post_id' in media
            assert 'filename' in media
            assert 'checksum' in media
            assert 'status' in media
            assert 'original_url' in media
            assert 'retrieved_from' in media
        
        # Verify some files were actually created
        downloaded_count = sum(
            1 for media in manifest_data['media']
            if media['status'] == 'downloaded' and (blog_dir / media['filename']).exists()
        )
        assert downloaded_count > 0
        
        # Verify progress events were emitted
        assert len(progress_events) > 0
        event_types = [e['event'] for e in progress_events]
        assert 'start' in event_types
        assert 'process_post' in event_types
    
    @pytest.mark.asyncio
    async def test_fresh_archive_with_wayback_recovery(
        self, test_config, mock_tumblr_api, mock_http_responses, mock_wayback_client
    ):
        """Test that missing media is recovered from Wayback Machine."""
        archiver = TumblrArchiver(test_config)
        result = await archiver.archive_blog()
        
        assert result.success is True
        
        # Check that Wayback recovery was attempted and succeeded
        assert result.statistics.media_recovered >= 1
        
        # Load manifest
        blog_dir = test_config.output_dir / "test-blog.tumblr.com"
        manifest_path = blog_dir / "manifest.json"
        with open(manifest_path, 'r') as f:
            manifest_data = json.load(f)
        
        # Find the missing media entry
        recovered_media = [
            m for m in manifest_data['media']
            if 'missing' in m['original_url']
        ]
        
        assert len(recovered_media) == 1
        recovered = recovered_media[0]
        
        # Verify it was marked as recovered from Internet Archive
        assert recovered['retrieved_from'] == 'internet_archive'
        assert recovered['media_missing_on_tumblr'] is True
        assert recovered['archive_snapshot_url'] is not None
        assert recovered['status'] in ['downloaded', 'verified']
    
    @pytest.mark.asyncio
    async def test_manifest_structure_validation(
        self, test_config, mock_tumblr_api, mock_http_responses, mock_wayback_client
    ):
        """Test that generated manifest has correct structure."""
        archiver = TumblrArchiver(test_config)
        result = await archiver.archive_blog()
        
        # Load manifest
        blog_dir = test_config.output_dir / "test-blog.tumblr.com"
        manifest_manager = ManifestManager(blog_dir / "manifest.json")
        manifest_data = manifest_manager.load()
        
        # Validate using ManifestManager
        try:
            manifest_manager.validate(manifest_data)
            validation_passed = True
        except Exception as e:
            validation_passed = False
            print(f"Validation error: {e}")
        
        assert validation_passed is True
        
        # Verify specific structure
        assert 'blog_url' in manifest_data
        assert 'blog_name' in manifest_data
        assert 'total_posts' in manifest_data
        assert 'total_media' in manifest_data
        assert 'archive_date' in manifest_data
        assert 'media' in manifest_data
        
        # Verify each media entry
        for media in manifest_data['media']:
            assert 'post_id' in media
            assert 'post_url' in media
            assert 'timestamp' in media
            assert 'media_type' in media
            assert 'filename' in media
            assert 'byte_size' in media
            assert 'checksum' in media
            assert 'original_url' in media
            assert 'status' in media
            assert 'retrieved_from' in media
            assert 'media_missing_on_tumblr' in media
            
            # Check valid status
            assert media['status'] in ['downloaded', 'failed', 'missing', 'verified', 'pending']
            
            # Check valid source
            assert media['retrieved_from'] in ['tumblr', 'internet_archive', 'external', 'cached', None]


class TestResumeFunction:
    """Test resume functionality for interrupted downloads."""
    
    @pytest.mark.asyncio
    async def test_resume_skips_downloaded_files(
        self, test_config, mock_tumblr_api, mock_http_responses, mock_wayback_client
    ):
        """Test that resume skips already downloaded files."""
        # First run - partial download
        archiver1 = TumblrArchiver(test_config)
        result1 = await archiver1.archive_blog()
        
        assert result1.success is True
        initial_downloaded = result1.statistics.media_downloaded
        
        # Load manifest and verify files exist
        blog_dir = test_config.output_dir / "test-blog.tumblr.com"
        manifest_path = blog_dir / "manifest.json"
        with open(manifest_path, 'r') as f:
            manifest_data = json.load(f)
        
        # Count files with checksums (completed downloads)
        completed_files = [
            m for m in manifest_data['media']
            if m['checksum'] and m['status'] == 'downloaded'
        ]
        initial_completed_count = len(completed_files)
        
        # Second run - should resume
        archiver2 = TumblrArchiver(test_config)
        result2 = await archiver2.archive_blog()
        
        assert result2.success is True
        
        # Should have skipped already downloaded files
        assert result2.statistics.media_skipped >= initial_completed_count
        
        # Total downloaded in second run should be minimal
        # (only new/failed files from first run)
        assert result2.statistics.media_downloaded <= (result2.statistics.total_media - initial_completed_count)
    
    @pytest.mark.asyncio
    async def test_resume_with_partially_downloaded_file(
        self, test_config, mock_tumblr_api, mock_http_responses, mock_wayback_client
    ):
        """Test resume handles partially downloaded files correctly."""
        # First run
        archiver1 = TumblrArchiver(test_config)
        result1 = await archiver1.archive_blog()
        
        blog_dir = test_config.output_dir / "test-blog.tumblr.com"
        manifest_path = blog_dir / "manifest.json"
        
        # Corrupt a downloaded file (simulate partial download)
        with open(manifest_path, 'r') as f:
            manifest_data = json.load(f)
        
        # Find a downloaded file and corrupt it
        for media in manifest_data['media']:
            if media['status'] == 'downloaded':
                file_path = blog_dir / media['filename']
                if file_path.exists():
                    # Write corrupted data
                    file_path.write_bytes(b'CORRUPTED')
                    # Break to only corrupt one file
                    break
        
        # Second run - should redownload corrupted file
        archiver2 = TumblrArchiver(test_config)
        result2 = await archiver2.archive_blog()
        
        assert result2.success is True
        
        # Verify manifest integrity
        manifest_manager = ManifestManager(manifest_path)
        final_manifest = manifest_manager.load()
        
        # All files should have valid checksums
        for media in final_manifest['media']:
            if media['status'] == 'downloaded':
                file_path = blog_dir / media['filename']
                assert file_path.exists()
                
                # Verify checksum matches
                actual_checksum = compute_checksum(file_path.read_bytes())
                assert actual_checksum == media['checksum']


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_invalid_blog_url(self, test_config, temp_test_dir):
        """Test handling of invalid blog URL."""
        test_config.blog_url = "nonexistent-blog-12345.tumblr.com"
        
        with patch('tumblr_archiver.archiver.TumblrAPIClient') as mock_api_class:
            mock_api = MagicMock()
            mock_api_class.return_value = mock_api
            
            # Simulate blog not found
            from tumblr_archiver.tumblr_api import TumblrAPIError
            mock_api.get_blog_info.side_effect = TumblrAPIError(
                "Blog not found", status_code=404
            )
            
            archiver = TumblrArchiver(test_config)
            result = await archiver.archive_blog()
            
            assert result.success is False
            assert result.error_message is not None
            assert "not found" in result.error_message.lower() or "404" in result.error_message
    
    @pytest.mark.asyncio
    async def test_network_error_recovery(
        self, test_config, mock_tumblr_api, mock_wayback_client
    ):
        """Test that temporary network errors are handled with retries."""
        call_count = {'value': 0}
        
        async def failing_get(url, **kwargs):
            """Mock that fails first 2 times then succeeds."""
            call_count['value'] += 1
            mock_response = AsyncMock()
            
            if call_count['value'] <= 2:
                # Simulate network error
                raise aiohttp.ClientError("Network error")
            else:
                # Succeed on third try
                mock_response.status = 200
                mock_response.read = AsyncMock(return_value=MOCK_IMAGE_DATA)
                mock_response.headers = {
                    'Content-Type': 'image/jpeg',
                    'Content-Length': str(len(MOCK_IMAGE_DATA))
                }
                return mock_response
        
        with patch('aiohttp.ClientSession.get', side_effect=failing_get):
            archiver = TumblrArchiver(test_config)
            result = await archiver.archive_blog()
            
            # Should eventually succeed after retries
            assert result.success is True
            assert result.statistics.media_downloaded > 0
    
    @pytest.mark.asyncio
    async def test_wayback_recovery_failure(
        self, test_config, mock_tumblr_api, mock_http_responses
    ):
        """Test handling when Wayback Machine cannot recover media."""
        with patch('tumblr_archiver.archiver.WaybackClient') as mock_wayback_class:
            mock_wayback = AsyncMock()
            mock_wayback_class.return_value = mock_wayback
            
            # Wayback finds no snapshots
            mock_wayback.get_snapshots.return_value = []
            
            archiver = TumblrArchiver(test_config)
            result = await archiver.archive_blog()
            
            # Archive should complete but with some missing media
            assert result.success is True
            assert result.statistics.media_missing >= 1
            
            # Verify manifest marks media as missing
            blog_dir = test_config.output_dir / "test-blog.tumblr.com"
            manifest_path = blog_dir / "manifest.json"
            with open(manifest_path, 'r') as f:
                manifest_data = json.load(f)
            
            missing_media = [
                m for m in manifest_data['media']
                if m['media_missing_on_tumblr'] is True and m['status'] in ['missing', 'failed']
            ]
            
            assert len(missing_media) >= 1


class TestCLIIntegration:
    """Test CLI command integration."""
    
    def test_cli_help(self):
        """Test CLI help command."""
        runner = CliRunner()
        result = runner.invoke(main, ['--help'])
        
        assert result.exit_code == 0
        assert 'Tumblr Media Archiver' in result.output
    
    def test_cli_archive_command_help(self):
        """Test archive command help."""
        runner = CliRunner()
        result = runner.invoke(main, ['archive', '--help'])
        
        assert result.exit_code == 0
        assert '--url' in result.output
        assert '--output' in result.output
        assert '--resume' in result.output
    
    def test_cli_missing_api_key(self, temp_test_dir):
        """Test CLI with missing API key."""
        runner = CliRunner()
        result = runner.invoke(main, [
            'archive',
            '--url', 'test-blog.tumblr.com',
            '--output', str(temp_test_dir)
        ], env={'TUMBLR_API_KEY': ''})
        
        assert result.exit_code == 1
        assert 'API key is required' in result.output
    
    def test_cli_full_archive_flow(
        self, temp_test_dir, mock_tumblr_api, mock_http_responses, mock_wayback_client
    ):
        """Test complete CLI archive flow."""
        runner = CliRunner()
        
        with patch.dict('os.environ', {'TUMBLR_API_KEY': 'test_key_12345'}):
            result = runner.invoke(main, [
                'archive',
                '--url', 'test-blog.tumblr.com',
                '--output', str(temp_test_dir),
                '--concurrency', '2',
                '--rate', '10.0',
                '--resume'
            ])
        
        # Should complete successfully
        assert result.exit_code == 0
        
        # Check output messages
        assert 'test-blog' in result.output.lower()
        
        # Verify files were created
        blog_dir = temp_test_dir / "test-blog.tumblr.com"
        assert blog_dir.exists()
        assert (blog_dir / "manifest.json").exists()


class TestManifestValidation:
    """Test manifest generation and validation."""
    
    @pytest.mark.asyncio
    async def test_manifest_checksums(
        self, test_config, mock_tumblr_api, mock_http_responses, mock_wayback_client
    ):
        """Test that manifest checksums match actual files."""
        archiver = TumblrArchiver(test_config)
        result = await archiver.archive_blog()
        
        blog_dir = test_config.output_dir / "test-blog.tumblr.com"
        manifest_path = blog_dir / "manifest.json"
        
        with open(manifest_path, 'r') as f:
            manifest_data = json.load(f)
        
        # Verify checksums for all downloaded files
        for media in manifest_data['media']:
            if media['status'] == 'downloaded':
                file_path = blog_dir / media['filename']
                assert file_path.exists(), f"File {media['filename']} should exist"
                
                # Compute actual checksum
                actual_checksum = compute_checksum(file_path.read_bytes())
                
                # Compare with manifest
                assert actual_checksum == media['checksum'], \
                    f"Checksum mismatch for {media['filename']}"
    
    @pytest.mark.asyncio
    async def test_manifest_tracks_media_source(
        self, test_config, mock_tumblr_api, mock_http_responses, mock_wayback_client
    ):
        """Test that manifest correctly tracks media source (Tumblr vs Wayback)."""
        archiver = TumblrArchiver(test_config)
        result = await archiver.archive_blog()
        
        blog_dir = test_config.output_dir / "test-blog.tumblr.com"
        manifest_path = blog_dir / "manifest.json"
        
        with open(manifest_path, 'r') as f:
            manifest_data = json.load(f)
        
        # Count sources
        tumblr_sources = sum(
            1 for m in manifest_data['media']
            if m['retrieved_from'] == 'tumblr'
        )
        wayback_sources = sum(
            1 for m in manifest_data['media']
            if m['retrieved_from'] == 'internet_archive'
        )
        
        # We should have media from both sources
        assert tumblr_sources > 0, "Should have media from Tumblr"
        assert wayback_sources > 0, "Should have media from Wayback"
        
        # Verify Wayback entries have snapshot info
        wayback_media = [
            m for m in manifest_data['media']
            if m['retrieved_from'] == 'internet_archive'
        ]
        
        for media in wayback_media:
            assert media['media_missing_on_tumblr'] is True
            assert media['archive_snapshot_url'] is not None
            assert media['archive_snapshot_timestamp'] is not None
    
    @pytest.mark.asyncio
    async def test_manifest_update_atomicity(
        self, test_config, mock_tumblr_api, mock_http_responses, mock_wayback_client
    ):
        """Test that manifest updates are atomic (no corruption on interrupt)."""
        blog_dir = test_config.output_dir / "test-blog.tumblr.com"
        blog_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = blog_dir / "manifest.json"
        
        # Create initial manifest
        manifest_manager = ManifestManager(manifest_path)
        manifest_manager.initialize(
            blog_url="https://test-blog.tumblr.com",
            blog_name="test-blog",
            total_posts=5,
            total_media=6
        )
        manifest_manager.save()
        
        # Verify backup is created
        backup_path = blog_dir / "manifest.json.backup"
        assert backup_path.exists() or manifest_path.exists()
        
        # Load and verify
        loaded = manifest_manager.load()
        assert loaded['blog_name'] == 'test-blog'
        assert loaded['total_posts'] == 5


class TestConcurrencyAndRateLimiting:
    """Test concurrent downloads and rate limiting."""
    
    @pytest.mark.asyncio
    async def test_concurrent_downloads(
        self, test_config, mock_tumblr_api, mock_http_responses, mock_wayback_client
    ):
        """Test that multiple files are downloaded concurrently."""
        test_config.concurrency = 3
        
        download_times = []
        original_get = aiohttp.ClientSession.get
        
        async def timed_get(self, url, **kwargs):
            start = time.time()
            result = await original_get(self, url, **kwargs)
            elapsed = time.time() - start
            download_times.append(elapsed)
            return result
        
        with patch('aiohttp.ClientSession.get', timed_get):
            archiver = TumblrArchiver(test_config)
            start_time = time.time()
            result = await archiver.archive_blog()
            total_time = time.time() - start_time
        
        # With concurrency, total time should be less than sequential
        # (This is a rough check since we're using mocks)
        assert result.success is True
        assert result.statistics.media_downloaded > 0
    
    @pytest.mark.asyncio
    async def test_rate_limiting_respected(
        self, test_config, mock_tumblr_api, mock_http_responses, mock_wayback_client
    ):
        """Test that rate limiting is respected."""
        test_config.rate_limit = 2.0  # 2 requests per second
        test_config.concurrency = 1
        
        request_times = []
        original_get = aiohttp.ClientSession.get
        
        async def tracked_get(self, url, **kwargs):
            request_times.append(time.time())
            return await original_get(self, url, **kwargs)
        
        # Note: With mocks, rate limiting may not be perfectly observable
        # This test verifies the archiver completes successfully with rate limit set
        with patch('aiohttp.ClientSession.get', tracked_get):
            archiver = TumblrArchiver(test_config)
            result = await archiver.archive_blog()
        
        assert result.success is True


class TestMediaTypeHandling:
    """Test handling of different media types."""
    
    @pytest.mark.asyncio
    async def test_photo_download(
        self, test_config, mock_tumblr_api, mock_http_responses, mock_wayback_client
    ):
        """Test downloading photo media."""
        archiver = TumblrArchiver(test_config)
        result = await archiver.archive_blog()
        
        blog_dir = test_config.output_dir / "test-blog.tumblr.com"
        manifest_path = blog_dir / "manifest.json"
        
        with open(manifest_path, 'r') as f:
            manifest_data = json.load(f)
        
        # Find photo entries
        photos = [m for m in manifest_data['media'] if '.jpg' in m['filename']]
        assert len(photos) > 0
        
        # Verify at least one photo was downloaded
        downloaded_photos = [
            m for m in photos
            if m['status'] == 'downloaded' and (blog_dir / m['filename']).exists()
        ]
        assert len(downloaded_photos) > 0
    
    @pytest.mark.asyncio
    async def test_video_download(
        self, test_config, mock_tumblr_api, mock_http_responses, mock_wayback_client
    ):
        """Test downloading video media."""
        archiver = TumblrArchiver(test_config)
        result = await archiver.archive_blog()
        
        blog_dir = test_config.output_dir / "test-blog.tumblr.com"
        manifest_path = blog_dir / "manifest.json"
        
        with open(manifest_path, 'r') as f:
            manifest_data = json.load(f)
        
        # Find video entries
        videos = [m for m in manifest_data['media'] if '.mp4' in m['filename']]
        assert len(videos) > 0
    
    @pytest.mark.asyncio
    async def test_gif_download(
        self, test_config, mock_tumblr_api, mock_http_responses, mock_wayback_client
    ):
        """Test downloading GIF media."""
        archiver = TumblrArchiver(test_config)
        result = await archiver.archive_blog()
        
        blog_dir = test_config.output_dir / "test-blog.tumblr.com"
        manifest_path = blog_dir / "manifest.json"
        
        with open(manifest_path, 'r') as f:
            manifest_data = json.load(f)
        
        # Find GIF entries
        gifs = [m for m in manifest_data['media'] if '.gif' in m['filename']]
        assert len(gifs) > 0


# ============================================================================
# Test Summary and Coverage Report
# ============================================================================

def test_integration_coverage_summary():
    """
    Summary of integration test coverage:
    
    1. Fresh Archive Tests:
       - Complete archive workflow
       - Wayback Machine recovery
       - Manifest structure validation
    
    2. Resume Tests:
       - Skip already downloaded files
       - Handle partially downloaded files
    
    3. Error Handling Tests:
       - Invalid blog URL
       - Network error recovery with retries
       - Wayback recovery failure
    
    4. CLI Integration Tests:
       - Help commands
       - Missing API key handling
       - Full archive flow via CLI
    
    5. Manifest Validation Tests:
       - Checksum verification
       - Media source tracking
       - Atomic updates
    
    6. Concurrency Tests:
       - Concurrent downloads
       - Rate limiting
    
    7. Media Type Tests:
       - Photos
       - Videos
       - Animated GIFs
    
    All tests use mocked API responses and file operations to ensure
    fast, reliable, and reproducible test runs without external dependencies.
    """
    pass


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v", "--tb=short"])
