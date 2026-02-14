"""
Tumblr v2 API client for archiving blog content.

This module provides a client for interacting with the Tumblr v2 API,
including methods for fetching blog info, posts, and extracting media URLs.
"""

import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests


# Custom Exceptions
class TumblrAPIError(Exception):
    """Base exception for Tumblr API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class AuthenticationError(TumblrAPIError):
    """Exception raised for authentication failures (401, 403)."""
    pass


class RateLimitError(TumblrAPIError):
    """Exception raised when API rate limit is exceeded (429)."""
    
    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


# Media extraction helper classes and functions
class MediaInfo:
    """Represents extracted media information from a post."""
    
    def __init__(
        self,
        media_type: str,
        urls: List[str],
        dimensions: Optional[Dict[str, int]] = None,
        original_url: Optional[str] = None,
        caption: Optional[str] = None
    ):
        """
        Initialize media information.
        
        Args:
            media_type: Type of media ('photo', 'video', etc.)
            urls: List of URLs for this media (multiple sizes for photos)
            dimensions: Optional dict with 'width' and 'height'
            original_url: Original source URL if available
            caption: Optional caption text
        """
        self.media_type = media_type
        self.urls = urls
        self.dimensions = dimensions or {}
        self.original_url = original_url
        self.caption = caption
    
    def __repr__(self) -> str:
        return f"MediaInfo(type={self.media_type}, urls={len(self.urls)}, dimensions={self.dimensions})"


def extract_media_from_post(post: Dict[str, Any]) -> List[MediaInfo]:
    """
    Extract all media URLs and information from a Tumblr post.
    
    Handles:
    - Photo posts (all sizes including highest resolution)
    - Video posts (video sources)
    - Reblog trail for provenance
    
    Args:
        post: A Tumblr post object (dict)
    
    Returns:
        List of MediaInfo objects containing extracted media information
    """
    media_list: List[MediaInfo] = []
    post_type = post.get('type', '')
    
    # Extract photos
    if post_type == 'photo' and 'photos' in post:
        for photo in post['photos']:
            urls = []
            dimensions = {}
            original_url = photo.get('original_size', {}).get('url')
            caption = photo.get('caption', '')
            
            # Get all available sizes (from largest to smallest)
            if 'original_size' in photo:
                orig = photo['original_size']
                urls.append(orig['url'])
                dimensions = {'width': orig.get('width', 0), 'height': orig.get('height', 0)}
            
            if 'alt_sizes' in photo:
                for alt_size in photo['alt_sizes']:
                    url = alt_size.get('url')
                    if url and url not in urls:
                        urls.append(url)
            
            if urls:
                media_list.append(MediaInfo(
                    media_type='photo',
                    urls=urls,
                    dimensions=dimensions,
                    original_url=original_url,
                    caption=caption
                ))
    
    # Extract videos
    elif post_type == 'video' and 'video' in post:
        video_data = post['video']
        urls = []
        dimensions = {}
        
        # Get video URL
        if 'video_url' in video_data:
            urls.append(video_data['video_url'])
        
        # Get alternate video sources
        if 'player' in video_data:
            for player in video_data['player']:
                if 'embed_code' in player:
                    # Extract video URL from embed code if needed
                    pass
        
        # Check for video sources in different formats
        if isinstance(video_data, dict):
            if 'width' in video_data and 'height' in video_data:
                dimensions = {'width': video_data['width'], 'height': video_data['height']}
        
        if urls:
            media_list.append(MediaInfo(
                media_type='video',
                urls=urls,
                dimensions=dimensions
            ))
    
    # Extract media from reblog trail (for provenance)
    if 'trail' in post:
        for trail_item in post['trail']:
            if 'content' in trail_item:
                # Parse NPF (Neue Post Format) content blocks
                for content_block in trail_item['content']:
                    if isinstance(content_block, dict):
                        block_type = content_block.get('type')
                        
                        if block_type == 'image' and 'media' in content_block:
                            for media in content_block['media']:
                                urls = []
                                dimensions = {}
                                
                                if 'url' in media:
                                    urls.append(media['url'])
                                if 'width' in media and 'height' in media:
                                    dimensions = {'width': media['width'], 'height': media['height']}
                                
                                if urls:
                                    media_list.append(MediaInfo(
                                        media_type='photo',
                                        urls=urls,
                                        dimensions=dimensions
                                    ))
                        
                        elif block_type == 'video' and 'media' in content_block:
                            media = content_block['media']
                            urls = []
                            dimensions = {}
                            
                            if 'url' in media:
                                urls.append(media['url'])
                            if 'width' in media and 'height' in media:
                                dimensions = {'width': media['width'], 'height': media['height']}
                            
                            if urls:
                                media_list.append(MediaInfo(
                                    media_type='video',
                                    urls=urls,
                                    dimensions=dimensions
                                ))
    
    # Also check NPF content blocks in the main post
    if 'content' in post:
        for content_block in post['content']:
            if isinstance(content_block, dict):
                block_type = content_block.get('type')
                
                if block_type == 'image' and 'media' in content_block:
                    for media in content_block['media']:
                        urls = []
                        dimensions = {}
                        
                        if 'url' in media:
                            urls.append(media['url'])
                        if 'width' in media and 'height' in media:
                            dimensions = {'width': media['width'], 'height': media['height']}
                        
                        if urls:
                            media_list.append(MediaInfo(
                                media_type='photo',
                                urls=urls,
                                dimensions=dimensions
                            ))
                
                elif block_type == 'video' and 'media' in content_block:
                    media = content_block['media']
                    urls = []
                    dimensions = {}
                    
                    if 'url' in media:
                        urls.append(media['url'])
                    if 'width' in media and 'height' in media:
                        dimensions = {'width': media['width'], 'height': media['height']}
                    
                    if urls:
                        media_list.append(MediaInfo(
                            media_type='video',
                            urls=urls,
                            dimensions=dimensions
                        ))
    
    return media_list


class TumblrAPIClient:
    """
    Client for interacting with the Tumblr v2 API.
    
    This client provides methods for fetching blog information, posts,
    and handling pagination. It includes proper error handling and
    rate limit detection.
    """
    
    BASE_URL = "https://api.tumblr.com/v2"
    USER_AGENT = "TumblrArchiver/0.1.0"
    DEFAULT_LIMIT = 20  # Tumblr's default posts per page
    MAX_LIMIT = 20  # Tumblr's maximum posts per request
    
    def __init__(
        self,
        api_key: str,
        oauth_token: Optional[str] = None,
        oauth_token_secret: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Initialize the Tumblr API client.
        
        Args:
            api_key: Tumblr API key (required for public API access)
            oauth_token: Optional OAuth token for authenticated requests
            oauth_token_secret: Optional OAuth token secret
            timeout: Request timeout in seconds (default: 30)
        
        Raises:
            ValueError: If api_key is not provided
        """
        if not api_key:
            raise ValueError("api_key is required")
        
        self.api_key = api_key
        self.oauth_token = oauth_token
        self.oauth_token_secret = oauth_token_secret
        self.timeout = timeout
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.USER_AGENT
        })
    
    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make a request to the Tumblr API.
        
        Args:
            endpoint: API endpoint path (e.g., '/blog/{blog}/info')
            params: Optional query parameters
        
        Returns:
            Response data as a dictionary
        
        Raises:
            AuthenticationError: For 401/403 errors
            RateLimitError: For 429 rate limit errors
            TumblrAPIError: For other API errors
        """
        url = urljoin(self.BASE_URL, endpoint)
        
        # Add API key to params
        if params is None:
            params = {}
        params['api_key'] = self.api_key
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After')
                retry_seconds = int(retry_after) if retry_after else None
                raise RateLimitError(
                    f"Rate limit exceeded. Retry after {retry_seconds} seconds." if retry_seconds 
                    else "Rate limit exceeded.",
                    retry_after=retry_seconds,
                    status_code=429,
                    response=response.json() if response.content else None
                )
            
            # Handle authentication errors
            if response.status_code in (401, 403):
                error_msg = "Authentication failed"
                try:
                    error_data = response.json()
                    if 'meta' in error_data and 'msg' in error_data['meta']:
                        error_msg = error_data['meta']['msg']
                except:
                    pass
                raise AuthenticationError(
                    error_msg,
                    status_code=response.status_code,
                    response=response.json() if response.content else None
                )
            
            # Handle other client errors (4xx)
            if 400 <= response.status_code < 500:
                error_msg = f"Client error: {response.status_code}"
                try:
                    error_data = response.json()
                    if 'meta' in error_data and 'msg' in error_data['meta']:
                        error_msg = error_data['meta']['msg']
                except:
                    pass
                raise TumblrAPIError(
                    error_msg,
                    status_code=response.status_code,
                    response=response.json() if response.content else None
                )
            
            # Handle server errors (5xx)
            if response.status_code >= 500:
                raise TumblrAPIError(
                    f"Server error: {response.status_code}",
                    status_code=response.status_code,
                    response=response.json() if response.content else None
                )
            
            # Raise for any other error status
            response.raise_for_status()
            
            # Parse JSON response
            data = response.json()
            
            # Check for API-level errors
            if 'meta' in data and data['meta'].get('status') != 200:
                raise TumblrAPIError(
                    data['meta'].get('msg', 'Unknown API error'),
                    status_code=data['meta'].get('status'),
                    response=data
                )
            
            return data
        
        except requests.exceptions.Timeout:
            raise TumblrAPIError(f"Request timeout after {self.timeout} seconds")
        except requests.exceptions.ConnectionError as e:
            raise TumblrAPIError(f"Connection error: {str(e)}")
        except requests.exceptions.RequestException as e:
            if isinstance(e, (AuthenticationError, RateLimitError, TumblrAPIError)):
                raise
            raise TumblrAPIError(f"Request failed: {str(e)}")
    
    def get_blog_info(self, blog_identifier: str) -> Dict[str, Any]:
        """
        Fetch information about a Tumblr blog.
        
        Args:
            blog_identifier: Blog hostname (e.g., 'example.tumblr.com') or blog name
        
        Returns:
            Dictionary containing blog information including:
            - title: Blog title
            - name: Blog name
            - posts: Total number of posts
            - url: Blog URL
            - updated: Last update timestamp
            - description: Blog description
            And other blog metadata
        
        Raises:
            TumblrAPIError: If the request fails
            AuthenticationError: If authentication fails
            RateLimitError: If rate limit is exceeded
        """
        endpoint = f"/blog/{blog_identifier}/info"
        response = self._make_request(endpoint)
        
        if 'response' in response and 'blog' in response['response']:
            return response['response']['blog']
        
        raise TumblrAPIError("Unexpected response format: missing blog info")
    
    def get_post(self, blog_identifier: str, post_id: str) -> Dict[str, Any]:
        """
        Fetch a single post by ID.
        
        Args:
            blog_identifier: Blog hostname or blog name
            post_id: ID of the post to fetch
        
        Returns:
            Dictionary containing the post data
        
        Raises:
            TumblrAPIError: If the request fails or post not found
            AuthenticationError: If authentication fails
            RateLimitError: If rate limit is exceeded
        """
        endpoint = f"/blog/{blog_identifier}/posts"
        params = {'id': post_id}
        response = self._make_request(endpoint, params)
        
        if 'response' in response and 'posts' in response['response']:
            posts = response['response']['posts']
            if posts:
                return posts[0]
            raise TumblrAPIError(f"Post {post_id} not found")
        
        raise TumblrAPIError("Unexpected response format: missing post data")
    
    def get_all_posts(
        self,
        blog_identifier: str,
        post_type: Optional[str] = None,
        callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch ALL posts from a blog, handling pagination automatically.
        
        This method will continue fetching posts until all posts have been
        retrieved. It uses offset-based pagination and compares against the
        total_posts count to ensure completeness.
        
        Args:
            blog_identifier: Blog hostname or blog name
            post_type: Optional filter by post type ('text', 'photo', 'video', etc.)
            callback: Optional callback function called after each page.
                     Receives (current_count, total_posts) as arguments.
        
        Returns:
            List of all post dictionaries
        
        Raises:
            TumblrAPIError: If any request fails
            AuthenticationError: If authentication fails
            RateLimitError: If rate limit is exceeded
        
        Example:
            >>> client = TumblrAPIClient(api_key="your_key")
            >>> def progress(current, total):
            ...     print(f"Fetched {current}/{total} posts")
            >>> posts = client.get_all_posts("example.tumblr.com", callback=progress)
        """
        all_posts: List[Dict[str, Any]] = []
        offset = 0
        total_posts = None
        
        endpoint = f"/blog/{blog_identifier}/posts"
        
        while True:
            params = {
                'limit': self.MAX_LIMIT,
                'offset': offset,
                'npf': 'true'  # Request Neue Post Format for better media handling
            }
            
            if post_type:
                params['type'] = post_type
            
            response = self._make_request(endpoint, params)
            
            if 'response' not in response:
                raise TumblrAPIError("Unexpected response format: missing response")
            
            response_data = response['response']
            posts = response_data.get('posts', [])
            
            # Get total posts count from first response
            if total_posts is None:
                total_posts = response_data.get('total_posts', 0)
            
            # Add posts to our collection
            all_posts.extend(posts)
            
            # Call progress callback if provided
            if callback:
                callback(len(all_posts), total_posts)
            
            # Check if we've fetched all posts
            if not posts or len(posts) < self.MAX_LIMIT:
                # No more posts returned or fewer than requested
                break
            
            if total_posts and len(all_posts) >= total_posts:
                # We've reached the total count
                break
            
            # Move to next page
            offset += len(posts)
        
        return all_posts
    
    def close(self):
        """Close the HTTP session."""
        if self.session:
            self.session.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
