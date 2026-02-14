"""
Shared fixtures and configuration for pytest.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_blog_info():
    """Sample Tumblr blog information."""
    return {
        'name': 'test-blog',
        'url': 'https://test-blog.tumblr.com',
        'title': 'Test Blog',
        'total_posts': 100,
        'description': 'A test blog for unit tests',
        'updated': 1609459200
    }


@pytest.fixture
def sample_photo_post():
    """Sample Tumblr photo post."""
    return {
        'id': 123456789,
        'post_url': 'https://test-blog.tumblr.com/post/123456789',
        'timestamp': 1609459200,
        'type': 'photo',
        'tags': ['test', 'photo'],
        'photos': [
            {
                'original_size': {
                    'url': 'https://64.media.tumblr.com/abc123/tumblr_test1_1280.jpg',
                    'width': 1280,
                    'height': 720
                },
                'caption': 'Test image 1',
                'alt_sizes': [
                    {
                        'url': 'https://64.media.tumblr.com/abc123/tumblr_test1_500.jpg',
                        'width': 500,
                        'height': 281
                    }
                ]
            }
        ]
    }


@pytest.fixture
def sample_video_post():
    """Sample Tumblr video post."""
    return {
        'id': 987654321,
        'post_url': 'https://test-blog.tumblr.com/post/987654321',
        'timestamp': 1609545600,
        'type': 'video',
        'tags': ['test', 'video'],
        'video': {
            'video_url': 'https://va.media.tumblr.com/tumblr_test_video.mp4',
            'width': 1920,
            'height': 1080
        }
    }


@pytest.fixture
def sample_posts(sample_photo_post, sample_video_post):
    """List of sample posts."""
    return [sample_photo_post, sample_video_post]


@pytest.fixture
def mock_api_response():
    """Mock successful API response."""
    return {
        'meta': {
            'status': 200,
            'msg': 'OK'
        },
        'response': {
            'blog': {
                'name': 'test-blog',
                'url': 'https://test-blog.tumblr.com',
                'total_posts': 100
            }
        }
    }


@pytest.fixture
def mock_session():
    """Mock requests session."""
    session = Mock()
    response = Mock()
    response.status_code = 200
    response.json.return_value = {'meta': {'status': 200}, 'response': {}}
    session.get.return_value = response
    return session


@pytest.fixture
async def mock_aiohttp_session():
    """Mock aiohttp session."""
    session = AsyncMock()
    response = AsyncMock()
    response.status = 200
    response.json = AsyncMock(return_value={'data': 'test'})
    response.read = AsyncMock(return_value=b'test data')
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock()
    session.get.return_value = response
    return session


@pytest.fixture
def sample_snapshot():
    """Sample Wayback Machine snapshot."""
    from tumblr_archiver.wayback_client import Snapshot
    return Snapshot(
        urlkey="com,tumblr,media)/tumblr_abc123_1280.jpg",
        timestamp="20250101120000",
        original_url="https://64.media.tumblr.com/abc123/tumblr_abc123_1280.jpg",
        mimetype="image/jpeg",
        status_code="200",
        digest="ABC123DEF456",
        length="524288"
    )


@pytest.fixture
def mock_download_result():
    """Mock download result."""
    from tumblr_archiver.downloader import DownloadResult
    return DownloadResult(
        url="https://example.com/image.jpg",
        file_path=Path("/tmp/image.jpg"),
        success=True,
        error=None,
        file_size=1024,
        mime_type="image/jpeg",
        checksum="abc123"
    )


@pytest.fixture
def sample_media_info():
    """Sample media info."""
    from tumblr_archiver.tumblr_api import MediaInfo
    return MediaInfo(
        media_type='photo',
        urls=['https://64.media.tumblr.com/abc123/tumblr_test_1280.jpg'],
        dimensions={'width': 1280, 'height': 720},
        original_url='https://64.media.tumblr.com/abc123/tumblr_test_1280.jpg',
        caption='Test image'
    )
