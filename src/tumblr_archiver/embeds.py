"""
External embed detection and extraction for Tumblr posts.

This module provides the EmbedHandler class for detecting and extracting
external video embeds (YouTube, Vimeo, Dailymotion, etc.) from Tumblr HTML.
"""

import logging
import re
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from .models import MediaItem

logger = logging.getLogger(__name__)


class EmbedHandler:
    """
    Detects and extracts external video embeds from Tumblr post HTML.
    
    Supports detection of embedded videos from:
    - YouTube (youtube.com, youtu.be)
    - Vimeo (vimeo.com)
    - Dailymotion (dailymotion.com)
    
    Features:
    - Extracts embed URLs from iframe elements
    - Parses video IDs from various URL formats
    - Converts embeds to normalized MediaItem objects
    - Filters out unsupported embed types
    
    Example:
        ```python
        handler = EmbedHandler()
        html = '<iframe src="https://www.youtube.com/embed/abc123"></iframe>'
        embeds = handler.detect_embeds(html, "https://example.tumblr.com/post/123")
        for embed in embeds:
            print(f"Found {embed.media_type}: {embed.original_url}")
        ```
    """
    
    # Supported embed domains and their patterns
    YOUTUBE_PATTERNS = [
        re.compile(r'(?:youtube\.com/embed/|youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]+)'),
        re.compile(r'youtube\.com/v/([a-zA-Z0-9_-]+)'),
    ]
    
    VIMEO_PATTERNS = [
        re.compile(r'vimeo\.com/video/(\d+)'),
        re.compile(r'vimeo\.com/(\d+)'),
        re.compile(r'player\.vimeo\.com/video/(\d+)'),
    ]
    
    DAILYMOTION_PATTERNS = [
        re.compile(r'dailymotion\.com/embed/video/([a-zA-Z0-9]+)'),
        re.compile(r'dailymotion\.com/video/([a-zA-Z0-9]+)'),
        re.compile(r'dai\.ly/([a-zA-Z0-9]+)'),
    ]
    
    SUPPORTED_DOMAINS = {
        'youtube.com', 'www.youtube.com', 'youtu.be', 'm.youtube.com',
        'vimeo.com', 'www.vimeo.com', 'player.vimeo.com',
        'dailymotion.com', 'www.dailymotion.com', 'dai.ly',
    }
    
    def detect_embeds(
        self,
        html: str,
        post_url: str,
        post_id: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> List[MediaItem]:
        """
        Detect and extract external video embeds from HTML.
        
        Args:
            html: HTML content to search for embeds
            post_url: URL of the Tumblr post containing the embeds
            post_id: Optional post ID (extracted from post_url if not provided)
            timestamp: Optional timestamp (defaults to current time)
            
        Returns:
            List of MediaItem objects representing detected embeds
            
        Example:
            >>> handler = EmbedHandler()
            >>> html = '<iframe src="https://youtube.com/embed/abc123"></iframe>'
            >>> embeds = handler.detect_embeds(html, "https://blog.tumblr.com/post/123")
            >>> len(embeds)
            1
            >>> embeds[0].media_type
            'video'
        """
        if post_id is None:
            post_id = self._extract_post_id(post_url)
        
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        embeds: List[MediaItem] = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find all iframe elements
        iframes = soup.find_all('iframe')
        logger.debug(f"Found {len(iframes)} iframe elements in post {post_id}")
        
        for idx, iframe in enumerate(iframes):
            src = iframe.get('src')
            if not src:
                continue
            
            # Check if this is a supported embed
            if not self.is_supported_embed(src):
                logger.debug(f"Skipping unsupported embed: {src}")
                continue
            
            # Normalize the embed URL
            normalized_url = self._normalize_embed_url(src)
            if not normalized_url:
                logger.warning(f"Could not normalize embed URL: {src}")
                continue
            
            # Extract video ID for filename
            video_id = self._extract_video_id(normalized_url)
            platform = self._get_platform_name(normalized_url)
            
            # Generate filename
            filename = f"{post_id}_{platform}_{video_id}.mp4"
            
            # Create MediaItem for this embed
            media_item = MediaItem(
                post_id=post_id,
                post_url=post_url,
                timestamp=timestamp,
                media_type="video",
                filename=filename,
                original_url=normalized_url,
                retrieved_from="tumblr",
                status="missing",  # Not downloaded yet
                notes=f"External embed from {platform}"
            )
            
            embeds.append(media_item)
            logger.debug(f"Detected {platform} embed: {normalized_url}")
        
        # Also check for direct video links in anchor tags
        links = soup.find_all('a', href=True)
        for link in links:
            href = link.get('href', '')
            if self.is_supported_embed(href):
                normalized_url = self._normalize_embed_url(href)
                if normalized_url and normalized_url not in [e.original_url for e in embeds]:
                    video_id = self._extract_video_id(normalized_url)
                    platform = self._get_platform_name(normalized_url)
                    filename = f"{post_id}_{platform}_{video_id}.mp4"
                    
                    media_item = MediaItem(
                        post_id=post_id,
                        post_url=post_url,
                        timestamp=timestamp,
                        media_type="video",
                        filename=filename,
                        original_url=normalized_url,
                        retrieved_from="tumblr",
                        status="missing",
                        notes=f"External embed link from {platform}"
                    )
                    embeds.append(media_item)
        
        logger.info(f"Detected {len(embeds)} external embeds in post {post_id}")
        return embeds
    
    def is_supported_embed(self, url: str) -> bool:
        """
        Check if a URL is a supported external embed.
        
        Args:
            url: URL to check
            
        Returns:
            True if the URL is from a supported embed platform
            
        Example:
            >>> handler = EmbedHandler()
            >>> handler.is_supported_embed("https://youtube.com/watch?v=abc123")
            True
            >>> handler.is_supported_embed("https://example.com/video")
            False
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remove 'www.' prefix for comparison
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Check if domain matches any supported platforms
            return any(
                supported in domain or domain in supported
                for supported in self.SUPPORTED_DOMAINS
            )
        except Exception as e:
            logger.debug(f"Error parsing URL {url}: {e}")
            return False
    
    def _normalize_embed_url(self, url: str) -> Optional[str]:
        """
        Normalize an embed URL to a standard watch/view URL.
        
        Args:
            url: Raw embed URL
            
        Returns:
            Normalized URL suitable for downloading, or None if invalid
        """
        try:
            # Extract video ID and reconstruct standard URL
            # YouTube
            for pattern in self.YOUTUBE_PATTERNS:
                match = pattern.search(url)
                if match:
                    video_id = match.group(1)
                    return f"https://www.youtube.com/watch?v={video_id}"
            
            # Vimeo
            for pattern in self.VIMEO_PATTERNS:
                match = pattern.search(url)
                if match:
                    video_id = match.group(1)
                    return f"https://vimeo.com/{video_id}"
            
            # Dailymotion
            for pattern in self.DAILYMOTION_PATTERNS:
                match = pattern.search(url)
                if match:
                    video_id = match.group(1)
                    return f"https://www.dailymotion.com/video/{video_id}"
            
            # If no pattern matched, return original if from supported domain
            if self.is_supported_embed(url):
                return url
            
            return None
            
        except Exception as e:
            logger.warning(f"Error normalizing embed URL {url}: {e}")
            return None
    
    def _extract_video_id(self, url: str) -> str:
        """
        Extract the video ID from a normalized URL.
        
        Args:
            url: Normalized video URL
            
        Returns:
            Video ID string
        """
        # Try all patterns
        for patterns in [self.YOUTUBE_PATTERNS, self.VIMEO_PATTERNS, self.DAILYMOTION_PATTERNS]:
            for pattern in patterns:
                match = pattern.search(url)
                if match:
                    return match.group(1)
        
        # Fallback: use last path segment or query param
        parsed = urlparse(url)
        if parsed.query:
            qs = parse_qs(parsed.query)
            if 'v' in qs:
                return qs['v'][0]
        
        path_parts = parsed.path.strip('/').split('/')
        if path_parts:
            return path_parts[-1]
        
        return "unknown"
    
    def _get_platform_name(self, url: str) -> str:
        """
        Get the platform name from a URL.
        
        Args:
            url: Video URL
            
        Returns:
            Platform name (youtube, vimeo, dailymotion)
        """
        url_lower = url.lower()
        if 'youtube' in url_lower or 'youtu.be' in url_lower:
            return 'youtube'
        elif 'vimeo' in url_lower:
            return 'vimeo'
        elif 'dailymotion' in url_lower or 'dai.ly' in url_lower:
            return 'dailymotion'
        else:
            return 'unknown'
    
    def _extract_post_id(self, post_url: str) -> str:
        """
        Extract post ID from a Tumblr post URL.
        
        Args:
            post_url: Tumblr post URL
            
        Returns:
            Post ID string
        """
        # Try to extract numeric ID from URL patterns like:
        # https://blog.tumblr.com/post/123456789
        # https://blog.tumblr.com/123456789
        match = re.search(r'/(?:post/)?(\d+)', post_url)
        if match:
            return match.group(1)
        
        # Fallback to using the full URL as ID
        return post_url.split('/')[-1] or "unknown"
