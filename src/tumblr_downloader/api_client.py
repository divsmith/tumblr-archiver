"""
API client for interacting with the Tumblr v1 public API.

This module provides a client for fetching blog posts from Tumblr using
the v1 public JSON API. It handles pagination, rate limiting, JSONP response
parsing, and robust error handling with exponential backoff.
"""

import json
import logging
import re
import time
from typing import Iterator, Optional, Dict, Any
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import (
    RequestException,
    Timeout,
    ConnectionError,
    HTTPError
)
from urllib3.util.retry import Retry


logger = logging.getLogger('tumblr_downloader')


class TumblrAPIError(Exception):
    """Base exception for Tumblr API related errors."""
    pass


class BlogNotFoundError(TumblrAPIError):
    """Raised when the specified blog cannot be found."""
    pass


class RateLimitError(TumblrAPIError):
    """Raised when API rate limit is exceeded."""
    pass


class TumblrAPIClient:
    """
    Client for interacting with the Tumblr v1 public API.
    
    This client provides methods to fetch posts from a Tumblr blog using
    the public JSON API endpoint. It handles pagination automatically,
    implements exponential backoff for rate limiting, and provides
    robust error handling.
    
    Attributes:
        blog_name: The name of the Tumblr blog to fetch posts from
        base_url: The base API URL for the blog
        session: Configured requests session with retry logic
        
    Example:
        >>> client = TumblrAPIClient("staff")
        >>> for post in client.get_posts(limit=100):
        ...     print(post['type'], post.get('slug', 'no-slug'))
    """
    
    # API configuration
    API_ENDPOINT = "https://{blog_name}.tumblr.com/api/read/json"
    POSTS_PER_PAGE = 50  # Maximum posts per request
    MAX_RETRIES = 5
    INITIAL_BACKOFF = 1.0  # Initial backoff in seconds
    MAX_BACKOFF = 60.0  # Maximum backoff in seconds
    REQUEST_TIMEOUT = 30  # Request timeout in seconds
    
    def __init__(self, blog_name: str) -> None:
        """
        Initialize the Tumblr API client.
        
        Args:
            blog_name: The name of the Tumblr blog (without .tumblr.com)
            
        Raises:
            ValueError: If blog_name is empty or invalid
        """
        if not blog_name or not blog_name.strip():
            raise ValueError("Blog name cannot be empty")
        
        self.blog_name = blog_name.strip()
        self.base_url = self.API_ENDPOINT.format(blog_name=self.blog_name)
        
        # Configure session with connection pooling and retry logic
        self.session = self._create_session()
        
        logger.info(f"Initialized TumblrAPIClient for blog: {self.blog_name}")
    
    def _create_session(self) -> requests.Session:
        """
        Create a configured requests session with retry logic.
        
        Returns:
            Configured requests.Session instance
        """
        session = requests.Session()
        
        # Configure retry strategy for transient failures
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set a user agent to identify our client
        session.headers.update({
            'User-Agent': 'TumblrMediaDownloader/1.0'
        })
        
        return session
    
    def _strip_jsonp_callback(self, response_text: str) -> str:
        """
        Strip JSONP callback wrapper from response.
        
        The Tumblr v1 API returns responses wrapped in a callback function.
        This method extracts the JSON content from the wrapper.
        
        Args:
            response_text: Raw response text from API
            
        Returns:
            Pure JSON string without JSONP wrapper
            
        Raises:
            TumblrAPIError: If response format is invalid
        """
        # Tumblr v1 API wraps response in: var tumblr_api_read = {...};
        match = re.search(r'var tumblr_api_read\s*=\s*({.*?});?\s*$', 
                         response_text, re.DOTALL)
        
        if not match:
            logger.error("Failed to parse JSONP response format")
            raise TumblrAPIError("Invalid JSONP response format")
        
        return match.group(1)
    
    def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> dict:
        """
        Make an API request with error handling and exponential backoff.
        
        This method implements robust error handling including:
        - Exponential backoff for rate limiting
        - Retry logic for transient failures
        - Specific error handling for different failure modes
        
        Args:
            url: The URL to request
            params: Optional query parameters
            
        Returns:
            Parsed JSON response as a dictionary
            
        Raises:
            BlogNotFoundError: If the blog doesn't exist (404)
            RateLimitError: If rate limit is exceeded after max retries
            TumblrAPIError: For other API-related errors
            RequestException: For network-related errors
        """
        attempt = 0
        backoff = self.INITIAL_BACKOFF
        
        while attempt < self.MAX_RETRIES:
            try:
                logger.debug(f"Making request to {url} (attempt {attempt + 1}/{self.MAX_RETRIES})")
                
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.REQUEST_TIMEOUT
                )
                
                # Handle HTTP errors
                if response.status_code == 404:
                    logger.error(f"Blog not found: {self.blog_name}")
                    raise BlogNotFoundError(f"Blog '{self.blog_name}' not found")
                
                if response.status_code == 429:
                    # Rate limit exceeded
                    logger.warning(f"Rate limit exceeded, backing off for {backoff}s")
                    time.sleep(backoff)
                    backoff = min(backoff * 2, self.MAX_BACKOFF)
                    attempt += 1
                    continue
                
                # Raise for other HTTP errors (will be caught by retry logic)
                response.raise_for_status()
                
                # Parse JSONP response
                json_str = self._strip_jsonp_callback(response.text)
                data = json.loads(json_str)
                
                logger.debug(f"Successfully fetched data from {url}")
                return data
                
            except (Timeout, ConnectionError) as e:
                logger.warning(f"Network error on attempt {attempt + 1}: {e}")
                attempt += 1
                
                if attempt >= self.MAX_RETRIES:
                    logger.error(f"Max retries exceeded for {url}")
                    raise TumblrAPIError(f"Failed to connect after {self.MAX_RETRIES} attempts") from e
                
                # Exponential backoff for network errors
                time.sleep(backoff)
                backoff = min(backoff * 2, self.MAX_BACKOFF)
                
            except HTTPError as e:
                if e.response.status_code >= 500:
                    # Server error, retry with backoff
                    logger.warning(f"Server error {e.response.status_code}, retrying...")
                    attempt += 1
                    
                    if attempt >= self.MAX_RETRIES:
                        raise TumblrAPIError(f"Server error persisted after {self.MAX_RETRIES} attempts") from e
                    
                    time.sleep(backoff)
                    backoff = min(backoff * 2, self.MAX_BACKOFF)
                else:
                    # Client error, don't retry
                    logger.error(f"HTTP error {e.response.status_code}: {e}")
                    raise TumblrAPIError(f"HTTP error: {e}") from e
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                raise TumblrAPIError("Invalid JSON in API response") from e
                
            except Exception as e:
                logger.error(f"Unexpected error during API request: {e}")
                raise TumblrAPIError(f"Unexpected error: {e}") from e
        
        # If we've exhausted all retries
        raise RateLimitError(f"Rate limit exceeded after {self.MAX_RETRIES} attempts")
    
    def get_posts(self, limit: Optional[int] = None) -> Iterator[dict]:
        """
        Generator that paginates through all blog posts.
        
        This method yields posts one at a time while handling pagination
        automatically. It will continue fetching until all posts are retrieved
        or the specified limit is reached.
        
        Args:
            limit: Maximum number of posts to fetch. If None, fetch all posts.
            
        Yields:
            dict: Individual post objects from the blog
            
        Raises:
            BlogNotFoundError: If the blog doesn't exist
            RateLimitError: If rate limit is exceeded
            TumblrAPIError: For other API-related errors
            
        Example:
            >>> client = TumblrAPIClient("staff")
            >>> for post in client.get_posts(limit=10):
            ...     print(f"Post ID: {post['id']}, Type: {post['type']}")
        """
        start = 0
        total_fetched = 0
        total_posts = None
        
        logger.info(f"Starting to fetch posts from blog: {self.blog_name}")
        
        while True:
            # Determine how many posts to fetch in this batch
            if limit is not None:
                remaining = limit - total_fetched
                if remaining <= 0:
                    logger.info(f"Reached limit of {limit} posts")
                    break
                num_to_fetch = min(self.POSTS_PER_PAGE, remaining)
            else:
                num_to_fetch = self.POSTS_PER_PAGE
            
            # Make the API request
            params = {
                'start': start,
                'num': num_to_fetch
            }
            
            logger.debug(f"Fetching posts {start} to {start + num_to_fetch}")
            
            try:
                data = self._make_request(self.base_url, params)
            except TumblrAPIError:
                # Re-raise API errors
                raise
            except Exception as e:
                logger.error(f"Unexpected error fetching posts: {e}")
                raise TumblrAPIError(f"Failed to fetch posts: {e}") from e
            
            # Extract metadata on first request
            if total_posts is None:
                total_posts = data.get('posts-total', 0)
                logger.info(f"Blog has {total_posts} total posts")
            
            # Get posts from response
            posts = data.get('posts', [])
            
            if not posts:
                logger.info("No more posts available")
                break
            
            # Yield individual posts
            for post in posts:
                yield post
                total_fetched += 1
                
                if limit is not None and total_fetched >= limit:
                    logger.info(f"Reached limit of {limit} posts")
                    return
            
            # Update start position for next page
            start += len(posts)
            
            # Check if we've fetched all available posts
            if start >= total_posts:
                logger.info(f"Fetched all {total_fetched} posts from blog")
                break
            
            # Small delay between requests to be respectful
            time.sleep(0.5)
        
        logger.info(f"Finished fetching {total_fetched} posts from {self.blog_name}")
    
    def get_blog_info(self) -> dict:
        """
        Fetch blog metadata/information.
        
        Returns:
            dict: Blog metadata including title, description, posts count, etc.
            
        Raises:
            BlogNotFoundError: If the blog doesn't exist
            TumblrAPIError: For other API-related errors
        """
        logger.debug(f"Fetching blog info for {self.blog_name}")
        
        data = self._make_request(self.base_url, params={'num': 0})
        
        # Extract relevant blog metadata
        blog_info = {
            'name': data.get('tumblelog', {}).get('name', self.blog_name),
            'title': data.get('tumblelog', {}).get('title', ''),
            'description': data.get('tumblelog', {}).get('description', ''),
            'posts_total': data.get('posts-total', 0),
            'url': data.get('tumblelog', {}).get('cname', f"{self.blog_name}.tumblr.com"),
            'timezone': data.get('tumblelog', {}).get('timezone', 'US/Eastern'),
        }
        
        logger.info(f"Retrieved blog info for '{blog_info['title']}' ({blog_info['posts_total']} posts)")
        
        return blog_info
    
    def close(self) -> None:
        """
        Close the session and clean up resources.
        
        This method should be called when done with the client to ensure
        proper cleanup of network connections.
        """
        if self.session:
            self.session.close()
            logger.debug(f"Closed session for blog: {self.blog_name}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
