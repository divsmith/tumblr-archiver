"""
HTML parser for Tumblr blog pages.

This module provides the TumblrParser class which uses BeautifulSoup to parse
Tumblr HTML and extract post metadata, timestamps, and media content.
"""

import logging
import re
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from .models import Post
from .media_extractor import MediaExtractor

logger = logging.getLogger(__name__)


class ParserError(Exception):
    """Base exception for parser errors."""
    pass


class TumblrParser:
    """
    Parser for Tumblr blog HTML pages.
    
    Uses BeautifulSoup to extract structured post data from Tumblr's HTML,
    including post IDs, timestamps, reblog status, and media items.
    
    Features:
    - Extracts post metadata (ID, URL, timestamp)
    - Detects reblogs vs original posts
    - Handles various Tumblr HTML structures and themes
    - Extracts media URLs via MediaExtractor
    
    Example:
        ```python
        parser = TumblrParser()
        posts = parser.parse_page(html_content, "https://example.tumblr.com")
        for post in posts:
            print(f"Post {post.post_id}: {len(post.media_items)} media items")
        ```
    """
    
    def __init__(self):
        """Initialize the parser with a media extractor."""
        self.media_extractor = MediaExtractor()
    
    def parse_page(self, html: str, page_url: str) -> List[Post]:
        """
        Parse a Tumblr blog page and extract all posts.
        
        Args:
            html: Raw HTML content of the page
            page_url: URL of the page being parsed (for resolving relative URLs)
            
        Returns:
            List of Post objects extracted from the page
            
        Raises:
            ParserError: If parsing fails critically
            
        Example:
            >>> with open("page.html") as f:
            ...     html = f.read()
            >>> posts = parser.parse_page(html, "https://example.tumblr.com")
            >>> print(f"Found {len(posts)} posts")
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            posts: List[Post] = []
            
            # Find all post elements - Tumblr uses various class names
            # Common patterns: article.post, li.post, div.post, or elements with data-post-id
            post_elements = self._find_post_elements(soup)
            
            logger.debug(f"Found {len(post_elements)} potential post elements")
            
            for post_elem in post_elements:
                try:
                    post = self._parse_post(post_elem, page_url)
                    if post:
                        posts.append(post)
                except Exception as e:
                    logger.warning(f"Failed to parse individual post: {e}", exc_info=True)
                    # Continue parsing other posts
                    continue
            
            return posts
            
        except Exception as e:
            logger.error(f"Failed to parse page HTML: {e}", exc_info=True)
            raise ParserError(f"HTML parsing failed: {e}")
    
    def _find_post_elements(self, soup: BeautifulSoup) -> List[Tag]:
        """
        Find all post elements in the HTML.
        
        Tumblr themes vary widely, so we check multiple selectors.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            List of Tag elements representing posts
        """
        post_elements = []
        
        # Try common Tumblr post selectors
        selectors = [
            '[data-post-id]',  # Most reliable - posts with data-post-id attribute
            'article.post',
            'div.post',
            'li.post',
            'article[id^="post"]',  # Articles with ID starting with "post"
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                logger.debug(f"Found {len(elements)} posts using selector: {selector}")
                post_elements.extend(elements)
                break  # Use first matching selector
        
        # Deduplicate by data-post-id if present
        seen_ids = set()
        unique_posts = []
        for elem in post_elements:
            post_id = elem.get('data-post-id') or elem.get('id', '')
            if post_id:
                if post_id not in seen_ids:
                    seen_ids.add(post_id)
                    unique_posts.append(elem)
            else:
                unique_posts.append(elem)
        
        return unique_posts
    
    def _parse_post(self, post_element: Tag, page_url: str) -> Optional[Post]:
        """
        Parse a single post element and extract its metadata.
        
        Args:
            post_element: BeautifulSoup Tag for the post
            page_url: Base URL for resolving relative links
            
        Returns:
            Post object or None if parsing fails
        """
        # Extract post ID
        post_id = self._extract_post_id(post_element)
        if not post_id:
            logger.debug("Could not extract post ID, skipping post")
            return None
        
        # Extract post URL
        post_url = self._extract_post_url(post_element, page_url, post_id)
        
        # Extract timestamp
        timestamp = self._extract_timestamp(post_element)
        
        # Detect if it's a reblog
        is_reblog = self._is_reblog(post_element)
        
        # Extract media items
        media_items = self.media_extractor.extract_from_post(
            post_html=str(post_element),
            post_id=post_id,
            post_url=post_url,
            timestamp=timestamp
        )
        
        logger.debug(
            f"Parsed post {post_id}: reblog={is_reblog}, "
            f"media_count={len(media_items)}, timestamp={timestamp}"
        )
        
        return Post(
            post_id=post_id,
            post_url=post_url,
            timestamp=timestamp,
            is_reblog=is_reblog,
            media_items=media_items
        )
    
    def _extract_post_id(self, post_element: Tag) -> Optional[str]:
        """
        Extract post ID from a post element.
        
        Args:
            post_element: BeautifulSoup Tag for the post
            
        Returns:
            Post ID as string, or None if not found
        """
        # Try data-post-id attribute
        post_id = post_element.get('data-post-id')
        if post_id:
            return str(post_id)
        
        # Try id attribute (format: "post-123456789")
        elem_id = post_element.get('id', '')
        if elem_id.startswith('post-') or elem_id.startswith('post_'):
            post_id = elem_id.split('-', 1)[-1].split('_', 1)[-1]
            if post_id.isdigit():
                return post_id
        
        # Try to find post ID in permalink
        permalink = post_element.find('a', class_=re.compile(r'permalink|post[_-]?link'))
        if permalink and permalink.get('href'):
            href = permalink['href']
            # Tumblr post URLs: /post/123456789 or /post/123456789/slug
            match = re.search(r'/post/(\d+)', href)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_post_url(self, post_element: Tag, page_url: str, post_id: str) -> str:
        """
        Extract or construct the post URL.
        
        Args:
            post_element: BeautifulSoup Tag for the post
            page_url: Base URL for resolving relative links
            post_id: Post ID
            
        Returns:
            Full URL to the post
        """
        # Try to find a permalink
        permalink = post_element.find('a', class_=re.compile(r'permalink|post[_-]?link'))
        if permalink and permalink.get('href'):
            href = permalink['href']
            # Resolve relative URLs
            return urljoin(page_url, href)
        
        # Construct URL from page_url and post_id
        base_url = page_url.split('/page/')[0]  # Remove pagination
        return f"{base_url}/post/{post_id}"
    
    def _extract_timestamp(self, post_element: Tag) -> datetime:
        """
        Extract post timestamp from various HTML elements.
        
        Args:
            post_element: BeautifulSoup Tag for the post
            
        Returns:
            Post timestamp as datetime (UTC), or current time if not found
        """
        # Try time element with datetime attribute
        time_elem = post_element.find('time')
        if time_elem:
            dt_str = time_elem.get('datetime') or time_elem.get('title')
            if dt_str:
                try:
                    # Parse ISO format or other common formats
                    timestamp = self._parse_datetime(dt_str)
                    if timestamp:
                        return timestamp
                except Exception as e:
                    logger.debug(f"Failed to parse timestamp from time element: {e}")
        
        # Try data-timestamp attribute (Unix timestamp)
        data_timestamp = post_element.get('data-timestamp')
        if data_timestamp:
            try:
                return datetime.fromtimestamp(int(data_timestamp), tz=timezone.utc)
            except (ValueError, OSError) as e:
                logger.debug(f"Failed to parse data-timestamp: {e}")
        
        # Try to find any ISO timestamp in attributes or text
        for attr in ['data-date', 'data-created', 'data-time']:
            value = post_element.get(attr)
            if value:
                timestamp = self._parse_datetime(value)
                if timestamp:
                    return timestamp
        
        # Default to current time if no timestamp found
        logger.debug("Could not extract post timestamp, using current time")
        return datetime.now(timezone.utc)
    
    def _parse_datetime(self, dt_str: str) -> Optional[datetime]:
        """
        Parse various datetime string formats.
        
        Args:
            dt_str: Datetime string to parse
            
        Returns:
            Parsed datetime in UTC, or None if parsing fails
        """
        formats = [
            "%Y-%m-%dT%H:%M:%S%z",  # ISO 8601 with timezone
            "%Y-%m-%d %H:%M:%S",     # Simple format
            "%Y-%m-%d",               # Date only
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(dt_str.strip(), fmt)
                # Ensure UTC timezone
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
                return dt
            except ValueError:
                continue
        
        # Try ISO format parsing
        try:
            dt = datetime.fromisoformat(dt_str.strip().replace('Z', '+00:00'))
            return dt.astimezone(timezone.utc)
        except (ValueError, AttributeError):
            pass
        
        return None
    
    def _is_reblog(self, post_element: Tag) -> bool:
        """
        Determine if a post is a reblog.
        
        Args:
            post_element: BeautifulSoup Tag for the post
            
        Returns:
            True if post is a reblog, False otherwise
        """
        # Check for reblog indicators in classes
        classes = post_element.get('class', [])
        if any('reblog' in str(c).lower() for c in classes):
            return True
        
        # Check for data-reblog attribute
        if post_element.get('data-reblog') or post_element.get('data-is-reblog'):
            return True
        
        # Check for reblog attribution elements
        reblog_indicators = [
            post_element.find(class_=re.compile(r'reblog', re.I)),
            post_element.find('div', class_=re.compile(r'reblogged[_-]from', re.I)),
            post_element.find(class_=re.compile(r'source[_-]', re.I)),
        ]
        
        if any(indicator for indicator in reblog_indicators):
            return True
        
        # Check for text like "reblogged from" or attribution links
        text = post_element.get_text().lower()
        if 'reblogged from' in text or 'reblogged this from' in text:
            return True
        
        return False
