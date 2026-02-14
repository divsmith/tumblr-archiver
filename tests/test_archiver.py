"""
Tests for the TumblrArchiver orchestrator module.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from tumblr_archiver.archiver import (
    ArchiveResult,
    ArchiveStatistics,
    ArchiverError,
    TumblrArchiver,
)
from tumblr_archiver.config import ArchiverConfig
from tumblr_archiver.downloader import DownloadResult
from tumblr_archiver.tumblr_api import MediaInfo


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create a temporary output directory."""
    output_dir = tmp_path / "archives"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def mock_config(temp_output_dir):
    """Create a mock configuration."""
    return ArchiverConfig(
        blog_url="test-blog.tumblr.com",
        output_dir=temp_output_dir,
        tumblr_api_key="test_api_key",
        resume=True,
        recover_removed_media=True,
        wayback_enabled=True,
        rate_limit=10.0,
        concurrency=2,
        max_retries=2
    )


@pytest.fixture
def mock_blog_info():
    """Create mock blog information."""
    return {
        'name': 'test-blog',
        'url': 'https://test-blog.tumblr.com',
        'title': 'Test Blog',
        'total_posts': 100,
        'description': 'A test blog'
    }


@pytest.fixture
def mock_posts():
    """Create mock posts with media."""
    return [
        {
            'id': 123456789,
            'post_url': 'https://test-blog.tumblr.com/post/123456789',
            'timestamp': 1609459200,
            'type': 'photo',
            'photos': [
                {
                    'original_size': {
                        'url': 'https://64.media.tumblr.com/abc123/tumblr_test1_1280.jpg',
                        'width': 1280,
                        'height': 720
                    },
                    'caption': 'Test image 1'
                }
            ]
        },
        {
            'id': 987654321,
            'post_url': 'https://test-blog.tumblr.com/post/987654321',
            'timestamp': 1609545600,
            'type': 'photo',
            'photos': [
                {
                    'original_size': {
                        'url': 'https://64.media.tumblr.com/def456/tumblr_test2_1280.jpg',
                        'width': 1920,
                        'height': 1080
                    },
                    'caption': 'Test image 2'
                }
            ]
        }
    ]


class TestArchiveStatistics:
    """Test ArchiveStatistics data class."""
    
    def test_statistics_initialization(self):
        """Test statistics initialization with defaults."""
        stats = ArchiveStatistics()
        
        assert stats.total_posts == 0
        assert stats.total_media == 0
        assert stats.media_downloaded == 0
        assert stats.media_skipped == 0
        assert stats.media_recovered == 0
        assert stats.media_failed == 0
        assert stats.media_missing == 0
        assert stats.bytes_downloaded == 0
        assert stats.posts_processed == 0
        assert stats.errors == []
    
    def test_statistics_to_dict(self):
        """Test conversion to dictionary."""
        stats = ArchiveStatistics(
            total_posts=100,
            total_media=50,
            media_downloaded=45,
            media_skipped=3,
            media_recovered=2,
            bytes_downloaded=1024000
        )
        
        result = stats.to_dict()
        
        assert result['total_posts'] == 100
        assert result['total_media'] == 50
        assert result['media_downloaded'] == 45
        assert result['media_skipped'] == 3
        assert result['media_recovered'] == 2
        assert result['bytes_downloaded'] == 1024000
        assert 'error_count' in result


class TestArchiveResult:
    """Test ArchiveResult data class."""
    
    def test_result_initialization(self):
        """Test result initialization."""
        stats = ArchiveStatistics(total_posts=10, media_downloaded=5)
        start = datetime.now(timezone.utc)
        end = datetime.now(timezone.utc)
        
        result = ArchiveResult(
            blog_name='test-blog',
            blog_url='https://test-blog.tumblr.com',
            success=True,
            statistics=stats,
            manifest_path=Path('/tmp/manifest.json'),
            output_dir=Path('/tmp/output'),
            start_time=start,
            end_time=end
        )
        
        assert result.blog_name == 'test-blog'
        assert result.success is True
        assert result.statistics == stats
        assert result.error_message is None
    
    def test_result_duration(self):
        """Test duration calculation."""
        start = datetime(2021, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        end = datetime(2021, 1, 1, 12, 5, 30, tzinfo=timezone.utc)
        
        result = ArchiveResult(
            blog_name='test',
            blog_url='https://test.tumblr.com',
            success=True,
            statistics=ArchiveStatistics(),
            manifest_path=Path('/tmp/manifest.json'),
            output_dir=Path('/tmp/output'),
            start_time=start,
            end_time=end
        )
        
        assert result.duration_seconds == 330.0  # 5 minutes 30 seconds
    
    def test_result_string_representation(self):
        """Test string representation."""
        stats = ArchiveStatistics(total_posts=10, media_downloaded=8)
        result = ArchiveResult(
            blog_name='test-blog',
            blog_url='https://test-blog.tumblr.com',
            success=True,
            statistics=stats,
            manifest_path=Path('/tmp/manifest.json'),
            output_dir=Path('/tmp/output'),
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc)
        )
        
        result_str = str(result)
        
        assert 'test-blog' in result_str
        assert 'Completed' in result_str
        assert 'Statistics:' in result_str


class TestTumblrArchiver:
    """Test TumblrArchiver class."""
    
    def test_initialization(self, mock_config):
        """Test archiver initialization."""
        archiver = TumblrArchiver(mock_config)
        
        assert archiver.config == mock_config
        assert archiver.blog_identifier == 'test-blog.tumblr.com'
        assert archiver.output_dir.exists()
        assert archiver.api_client is not None
        assert archiver.manifest is not None
        assert archiver.wayback_client is not None
    
    def test_initialization_without_api_key(self, temp_output_dir):
        """Test initialization fails without API key."""
        config = ArchiverConfig(
            blog_url='test.tumblr.com',
            output_dir=temp_output_dir,
            tumblr_api_key=None
        )
        
        with pytest.raises(ArchiverError, match="API key is required"):
            TumblrArchiver(config)
    
    def test_initialization_without_blog_url(self, temp_output_dir):
        """Test initialization fails without blog URL."""
        config = ArchiverConfig(
            blog_url='',
            output_dir=temp_output_dir,
            tumblr_api_key='test_key'
        )
        
        with pytest.raises(ArchiverError, match="blog_url is required"):
            TumblrArchiver(config)
    
    def test_extract_blog_identifier(self, mock_config):
        """Test blog identifier extraction."""
        archiver = TumblrArchiver(mock_config)
        
        # Test various input formats
        assert archiver._extract_blog_identifier('example') == 'example.tumblr.com'
        assert archiver._extract_blog_identifier('example.tumblr.com') == 'example.tumblr.com'
        assert archiver._extract_blog_identifier('https://example.tumblr.com') == 'example.tumblr.com'
        assert archiver._extract_blog_identifier('http://example.tumblr.com/') == 'example.tumblr.com'
        assert archiver._extract_blog_identifier('custom.domain.com') == 'custom.domain.com'
    
    def test_set_progress_callback(self, mock_config):
        """Test setting progress callback."""
        archiver = TumblrArchiver(mock_config)
        
        callback = Mock()
        archiver.set_progress_callback(callback)
        
        assert archiver.progress_callback == callback
    
    def test_report_progress(self, mock_config):
        """Test progress reporting."""
        archiver = TumblrArchiver(mock_config)
        
        callback = Mock()
        archiver.set_progress_callback(callback)
        
        archiver._report_progress('test_event', key='value', number=42)
        
        callback.assert_called_once()
        call_args = callback.call_args[0][0]
        assert call_args['event'] == 'test_event'
        assert call_args['key'] == 'value'
        assert call_args['number'] == 42
    
    def test_report_progress_handles_callback_errors(self, mock_config):
        """Test progress reporting handles callback errors gracefully."""
        archiver = TumblrArchiver(mock_config)
        
        callback = Mock(side_effect=Exception("Callback error"))
        archiver.set_progress_callback(callback)
        
        # Should not raise exception
        archiver._report_progress('test_event')
        
        callback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fetch_blog_info(self, mock_config, mock_blog_info):
        """Test fetching blog information."""
        archiver = TumblrArchiver(mock_config)
        
        with patch.object(archiver.api_client, 'get_blog_info', return_value=mock_blog_info):
            blog_info = await archiver._fetch_blog_info()
            
            assert blog_info == mock_blog_info
            assert blog_info['name'] == 'test-blog'
            assert blog_info['total_posts'] == 100
    
    @pytest.mark.asyncio
    async def test_fetch_blog_info_error(self, mock_config):
        """Test fetching blog info handles errors."""
        archiver = TumblrArchiver(mock_config)
        
        with patch.object(
            archiver.api_client,
            'get_blog_info',
            side_effect=Exception("API error")
        ):
            with pytest.raises(ArchiverError, match="Failed to fetch blog info"):
                await archiver._fetch_blog_info()
    
    def test_initialize_manifest(self, mock_config, mock_blog_info):
        """Test manifest initialization."""
        archiver = TumblrArchiver(mock_config)
        
        archiver._initialize_manifest(mock_blog_info)
        
        assert archiver.manifest.data['blog_name'] == 'test-blog'
        assert archiver.manifest.data['blog_url'] == 'https://test-blog.tumblr.com'
        assert archiver.manifest.data['total_posts'] == 100
        assert archiver.statistics.total_posts == 100
    
    @pytest.mark.asyncio
    async def test_fetch_all_posts(self, mock_config, mock_posts):
        """Test fetching all posts."""
        archiver = TumblrArchiver(mock_config)
        
        with patch.object(archiver.api_client, 'get_all_posts', return_value=mock_posts):
            posts = await archiver._fetch_all_posts()
            
            assert len(posts) == 2
            assert posts == mock_posts
    
    @pytest.mark.asyncio
    async def test_download_media_with_recovery_success(self, mock_config):
        """Test successful media download."""
        archiver = TumblrArchiver(mock_config)
        
        download_result = DownloadResult(
            filename='test.jpg',
            byte_size=1024,
            checksum='abc123',
            duration=1.5,
            source='tumblr',
            status='success'
        )
        
        async with archiver._create_download_manager() as dm:
            archiver.download_manager = dm
            
            with patch.object(dm, 'download_file', return_value=download_result):
                result = await archiver._download_media_with_recovery(
                    url='https://example.com/test.jpg',
                    filename='test.jpg',
                    media_info=MediaInfo('photo', ['https://example.com/test.jpg'])
                )
                
                assert result.status == 'success'
                assert result.source == 'tumblr'
    
    @pytest.mark.asyncio
    async def test_download_media_with_wayback_recovery(self, mock_config):
        """Test media download with Wayback Machine recovery."""
        archiver = TumblrArchiver(mock_config)
        
        # First download fails (missing)
        failed_result = DownloadResult(
            filename='test.jpg',
            byte_size=0,
            checksum='',
            duration=0.5,
            source='tumblr',
            status='missing',
            media_missing_on_tumblr=True
        )
        
        # Second download from Wayback succeeds
        success_result = DownloadResult(
            filename='test.jpg',
            byte_size=2048,
            checksum='def456',
            duration=2.0,
            source='internet_archive',
            status='success'
        )
        
        async with archiver._create_download_manager() as dm:
            archiver.download_manager = dm
            
            # Mock download_file to fail first, then succeed
            dm.download_file = AsyncMock(side_effect=[failed_result, success_result])
            
            # Mock Wayback client
            mock_snapshot = Mock()
            mock_snapshot.replay_url = 'https://web.archive.org/web/20210101/example.com/test.jpg'
            mock_snapshot.timestamp = '20210101120000'
            
            with patch.object(
                archiver.wayback_client,
                'get_best_snapshot',
                return_value=mock_snapshot
            ):
                result = await archiver._download_media_with_recovery(
                    url='https://example.com/test.jpg',
                    filename='test.jpg',
                    media_info=MediaInfo('photo', ['https://example.com/test.jpg'])
                )
                
                assert result.status == 'success'
                assert result.source == 'internet_archive'
    
    def test_update_statistics_downloaded(self, mock_config):
        """Test statistics update for downloaded media."""
        archiver = TumblrArchiver(mock_config)
        
        result = DownloadResult(
            filename='test.jpg',
            byte_size=1024,
            checksum='abc',
            duration=1.0,
            source='tumblr',
            status='success'
        )
        
        archiver._update_statistics(result)
        
        assert archiver.statistics.media_downloaded == 1
        assert archiver.statistics.bytes_downloaded == 1024
    
    def test_update_statistics_recovered(self, mock_config):
        """Test statistics update for recovered media."""
        archiver = TumblrArchiver(mock_config)
        
        result = DownloadResult(
            filename='test.jpg',
            byte_size=2048,
            checksum='abc',
            duration=2.0,
            source='internet_archive',
            status='success'
        )
        
        archiver._update_statistics(result)
        
        assert archiver.statistics.media_recovered == 1
        assert archiver.statistics.bytes_downloaded == 2048
    
    def test_update_statistics_missing(self, mock_config):
        """Test statistics update for missing media."""
        archiver = TumblrArchiver(mock_config)
        
        result = DownloadResult(
            filename='test.jpg',
            byte_size=0,
            checksum='',
            duration=0.5,
            source='tumblr',
            status='missing',
            media_missing_on_tumblr=True
        )
        
        archiver._update_statistics(result)
        
        assert archiver.statistics.media_missing == 1
    
    def test_update_statistics_failed(self, mock_config):
        """Test statistics update for failed media."""
        archiver = TumblrArchiver(mock_config)
        
        result = DownloadResult(
            filename='test.jpg',
            byte_size=0,
            checksum='',
            duration=0.5,
            source='tumblr',
            status='error',
            error_message='Download failed'
        )
        
        archiver._update_statistics(result)
        
        assert archiver.statistics.media_failed == 1
    
    def test_close(self, mock_config):
        """Test closing the archiver."""
        archiver = TumblrArchiver(mock_config)
        
        with patch.object(archiver.api_client, 'close') as mock_close:
            archiver.close()
            mock_close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_context_manager(self, mock_config):
        """Test archiver as async context manager."""
        async with TumblrArchiver(mock_config) as archiver:
            assert isinstance(archiver, TumblrArchiver)
        
        # Archiver should be closed after context exit


class TestArchiverIntegration:
    """Integration tests for the full archiving workflow."""
    
    @pytest.mark.asyncio
    async def test_full_archive_workflow(self, mock_config, mock_blog_info, mock_posts):
        """Test complete archive workflow."""
        archiver = TumblrArchiver(mock_config)
        
        # Mock all external dependencies
        with patch.object(archiver.api_client, 'get_blog_info', return_value=mock_blog_info), \
             patch.object(archiver.api_client, 'get_all_posts', return_value=mock_posts):
            
            # Mock download manager
            async def mock_download_manager():
                dm = Mock()
                
                # Mock download_file
                async def download_file(*args, **kwargs):
                    return DownloadResult(
                        filename='test.jpg',
                        byte_size=1024,
                        checksum='abc123',
                        duration=1.0,
                        source='tumblr',
                        status='success'
                    )
                
                dm.download_file = download_file
                dm.generate_filename = lambda *args, **kwargs: 'test.jpg'
                dm.__aenter__ = AsyncMock(return_value=dm)
                dm.__aexit__ = AsyncMock(return_value=None)
                
                return dm
            
            with patch.object(archiver, '_create_download_manager', side_effect=mock_download_manager):
                result = await archiver.archive_blog()
                
                assert result.success is True
                assert result.blog_name == 'test-blog'
                assert result.statistics.posts_processed == 2
                assert result.statistics.total_media == 2
    
    @pytest.mark.asyncio
    async def test_archive_with_progress_callback(self, mock_config, mock_blog_info, mock_posts):
        """Test archive with progress callback."""
        archiver = TumblrArchiver(mock_config)
        
        progress_events = []
        
        def track_progress(data):
            progress_events.append(data['event'])
        
        archiver.set_progress_callback(track_progress)
        
        with patch.object(archiver.api_client, 'get_blog_info', return_value=mock_blog_info), \
             patch.object(archiver.api_client, 'get_all_posts', return_value=[]):
            
            async def mock_download_manager():
                dm = Mock()
                dm.__aenter__ = AsyncMock(return_value=dm)
                dm.__aexit__ = AsyncMock(return_value=None)
                return dm
            
            with patch.object(archiver, '_create_download_manager', side_effect=mock_download_manager):
                result = await archiver.archive_blog()
                
                # Check that progress events were fired
                assert 'start' in progress_events
                assert 'fetch_blog_info' in progress_events
                assert 'fetch_posts' in progress_events
                assert 'complete' in progress_events
