"""
Tests for the Tumblr API client module.
"""

import pytest
import requests
from unittest.mock import Mock, patch, MagicMock

from tumblr_archiver.tumblr_api import (
    TumblrAPIClient,
    TumblrAPIError,
    AuthenticationError,
    RateLimitError,
    MediaInfo,
    extract_media_from_post,
)


class TestMediaInfo:
    """Tests for MediaInfo class."""
    
    def test_media_info_creation(self):
        """Test creating a MediaInfo object."""
        media = MediaInfo(
            media_type='photo',
            urls=['https://example.com/image.jpg'],
            dimensions={'width': 1280, 'height': 720},
            original_url='https://example.com/image.jpg',
            caption='Test image'
        )
        
        assert media.media_type == 'photo'
        assert len(media.urls) == 1
        assert media.dimensions['width'] == 1280
        assert media.caption == 'Test image'
    
    def test_media_info_repr(self):
        """Test MediaInfo string representation."""
        media = MediaInfo(
            media_type='video',
            urls=['https://example.com/video.mp4'],
        )
        
        repr_str = repr(media)
        assert 'MediaInfo' in repr_str
        assert 'video' in repr_str


class TestExtractMediaFromPost:
    """Tests for extract_media_from_post function."""
    
    def test_extract_photo_media(self, sample_photo_post):
        """Test extracting media from a photo post."""
        media_list = extract_media_from_post(sample_photo_post)
        
        assert len(media_list) > 0
        assert media_list[0].media_type == 'photo'
        assert len(media_list[0].urls) > 0
        assert '1280.jpg' in media_list[0].urls[0]
    
    def test_extract_video_media(self, sample_video_post):
        """Test extracting media from a video post."""
        media_list = extract_media_from_post(sample_video_post)
        
        assert len(media_list) > 0
        assert media_list[0].media_type == 'video'
        assert 'video.mp4' in media_list[0].urls[0]
    
    def test_extract_no_media(self):
        """Test extracting from a post with no media."""
        text_post = {
            'id': 111111,
            'type': 'text',
            'body': 'Just text, no media'
        }
        
        media_list = extract_media_from_post(text_post)
        assert len(media_list) == 0
    
    def test_extract_multiple_photos(self):
        """Test extracting multiple photos from a photoset."""
        photoset_post = {
            'id': 222222,
            'type': 'photo',
            'photos': [
                {
                    'original_size': {
                        'url': 'https://example.com/photo1.jpg',
                        'width': 1280,
                        'height': 720
                    }
                },
                {
                    'original_size': {
                        'url': 'https://example.com/photo2.jpg',
                        'width': 1920,
                        'height': 1080
                    }
                }
            ]
        }
        
        media_list = extract_media_from_post(photoset_post)
        assert len(media_list) == 2
        assert all(m.media_type == 'photo' for m in media_list)
    
    def test_extract_with_alt_sizes(self):
        """Test extracting includes alt_sizes."""
        post_with_alts = {
            'id': 333333,
            'type': 'photo',
            'photos': [
                {
                    'original_size': {
                        'url': 'https://example.com/photo_1280.jpg',
                        'width': 1280,
                        'height': 720
                    },
                    'alt_sizes': [
                        {
                            'url': 'https://example.com/photo_500.jpg',
                            'width': 500,
                            'height': 281
                        },
                        {
                            'url': 'https://example.com/photo_250.jpg',
                            'width': 250,
                            'height': 140
                        }
                    ]
                }
            ]
        }
        
        media_list = extract_media_from_post(post_with_alts)
        assert len(media_list) == 1
        # Should have original + alt sizes
        assert len(media_list[0].urls) >= 2


class TestTumblrAPIClient:
    """Tests for TumblrAPIClient class."""
    
    def test_client_initialization(self):
        """Test client initialization."""
        client = TumblrAPIClient(api_key='test_key')
        
        assert client.api_key == 'test_key'
        assert client.base_url == 'https://api.tumblr.com/v2'
        assert client.session is not None
    
    def test_client_with_oauth(self):
        """Test client initialization with OAuth credentials."""
        client = TumblrAPIClient(
            api_key='test_key',
            oauth_consumer_key='consumer',
            oauth_token='token'
        )
        
        assert client.oauth_consumer_key == 'consumer'
        assert client.oauth_token == 'token'
    
    @patch('requests.Session')
    def test_get_blog_info_success(self, mock_session_class):
        """Test successful blog info retrieval."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'meta': {'status': 200, 'msg': 'OK'},
            'response': {
                'blog': {
                    'name': 'test-blog',
                    'url': 'https://test-blog.tumblr.com',
                    'title': 'Test Blog',
                    'total_posts': 100
                }
            }
        }
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = TumblrAPIClient(api_key='test_key')
        client.session = mock_session
        
        blog_info = client.get_blog_info('test-blog')
        
        assert blog_info['name'] == 'test-blog'
        assert blog_info['total_posts'] == 100
        mock_session.get.assert_called_once()
    
    @patch('requests.Session')
    def test_get_blog_info_authentication_error(self, mock_session_class):
        """Test authentication error handling."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            'meta': {'status': 401, 'msg': 'Unauthorized'}
        }
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = TumblrAPIClient(api_key='invalid_key')
        client.session = mock_session
        
        with pytest.raises(AuthenticationError):
            client.get_blog_info('test-blog')
    
    @patch('requests.Session')
    def test_get_blog_info_rate_limit_error(self, mock_session_class):
        """Test rate limit error handling."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {'Retry-After': '60'}
        mock_response.json.return_value = {
            'meta': {'status': 429, 'msg': 'Rate Limit Exceeded'}
        }
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = TumblrAPIClient(api_key='test_key')
        client.session = mock_session
        
        with pytest.raises(RateLimitError) as exc_info:
            client.get_blog_info('test-blog')
        
        assert exc_info.value.retry_after == 60
    
    @patch('requests.Session')
    def test_get_posts_pagination(self, mock_session_class):
        """Test posts retrieval with pagination."""
        mock_session = Mock()
        
        # First page
        mock_response_1 = Mock()
        mock_response_1.status_code = 200
        mock_response_1.json.return_value = {
            'meta': {'status': 200, 'msg': 'OK'},
            'response': {
                'posts': [
                    {'id': 1, 'type': 'photo'},
                    {'id': 2, 'type': 'photo'}
                ]
            }
        }
        
        # Second page (empty)
        mock_response_2 = Mock()
        mock_response_2.status_code = 200
        mock_response_2.json.return_value = {
            'meta': {'status': 200, 'msg': 'OK'},
            'response': {
                'posts': []
            }
        }
        
        mock_session.get.side_effect = [mock_response_1, mock_response_2]
        mock_session_class.return_value = mock_session
        
        client = TumblrAPIClient(api_key='test_key')
        client.session = mock_session
        
        all_posts = []
        for posts in client.get_posts('test-blog', limit=20):
            all_posts.extend(posts)
        
        assert len(all_posts) == 2
        assert all_posts[0]['id'] == 1
    
    @patch('requests.Session')
    def test_get_posts_with_filters(self, mock_session_class):
        """Test posts retrieval with type and tag filters."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'meta': {'status': 200, 'msg': 'OK'},
            'response': {
                'posts': [
                    {'id': 1, 'type': 'photo', 'tags': ['nature']}
                ]
            }
        }
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = TumblrAPIClient(api_key='test_key')
        client.session = mock_session
        
        posts_gen = client.get_posts('test-blog', post_type='photo', tag='nature')
        posts = next(posts_gen)
        
        assert len(posts) == 1
        assert posts[0]['type'] == 'photo'
    
    def test_client_context_manager(self):
        """Test client as context manager."""
        with TumblrAPIClient(api_key='test_key') as client:
            assert client.session is not None
        
        # Session should be closed after exiting context
        # We can't easily test this without mocking, but at least verify no exception
    
    @patch('requests.Session')
    def test_network_error_handling(self, mock_session_class):
        """Test handling of network errors."""
        mock_session = Mock()
        mock_session.get.side_effect = requests.ConnectionError("Network error")
        mock_session_class.return_value = mock_session
        
        client = TumblrAPIClient(api_key='test_key')
        client.session = mock_session
        
        with pytest.raises(TumblrAPIError):
            client.get_blog_info('test-blog')
    
    def test_invalid_api_key(self):
        """Test initialization with invalid API key."""
        with pytest.raises(ValueError):
            TumblrAPIClient(api_key='')
        
        with pytest.raises(ValueError):
            TumblrAPIClient(api_key=None)
