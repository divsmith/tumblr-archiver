"""
Media URL extractor for Tumblr posts.

This module provides the MediaExtractor class which extracts image, video,
and GIF URLs from Tumblr post HTML, handling various formats including
photosets, galleries, and external embeds.
"""

import logging
import re
from datetime import datetime
from typing import List, Set
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .models import MediaItem

logger = logging.getLogger(__name__)


class MediaExtractor:
    """
    Extracts media URLs from Tumblr post HTML.
    
    Handles various Tumblr media formats:
    - Direct image links (tumblr_*.jpg, tumblr_*.png, etc.)
    - Tumblr's media CDN (64.media.tumblr.com, etc.)
    - Video embeds (Tumblr native video player)
    - Animated GIFs
    - Photosets and galleries
    - External embeds (YouTube, Vimeo) - detection only
    
    Example:
        ```python
        extractor = MediaExtractor()
        media_items = extractor.extract_from_post(
            post_html, 
            post_id="123456789",
            post_url="https://example.tumblr.com/post/123456789",
            timestamp=datetime.now(timezone.utc)
        )
        ```
    """
    
    # Tumblr media CDN domains
    TUMBLR_MEDIA_DOMAINS = {
        '64.media.tumblr.com',
        '65.media.tumblr.com',
        '66.media.tumblr.com',
        '67.media.tumblr.com',
        'media.tumblr.com',
        'static.tumblr.com',
        'assets.tumblr.com',
    }
    
    # External video embed domains
    EXTERNAL_VIDEO_DOMAINS = {
        'youtube.com',
        'youtu.be',
        'vimeo.com',
        'dailymotion.com',
        'player.vimeo.com',
        'www.youtube.com',
    }
    
    def extract_from_post(
        self,
        post_html: str,
        post_id: str,
        post_url: str,
        timestamp: datetime
    ) -> List[MediaItem]:
        """
        Extract all media items from a post's HTML.
        
        Args:
            post_html: HTML content of the post
            post_id: Unique post identifier
            post_url: URL of the post
            timestamp: Post publication timestamp
            
        Returns:
            List of MediaItem objects found in the post
        """
        soup = BeautifulSoup(post_html, 'html.parser')
        media_items: List[MediaItem] = []
        seen_urls: Set[str] = set()  # Avoid duplicates
        
        # Extract GIFs first (before images, so they're classified correctly)
        gifs = self._extract_gifs(soup)
        for idx, gif_url in enumerate(gifs):
            if gif_url not in seen_urls:
                seen_urls.add(gif_url)
                media_items.append(self._create_media_item(
                    post_id=post_id,
                    post_url=post_url,
                    timestamp=timestamp,
                    media_url=gif_url,
                    media_type='gif',
                    index=idx
                ))
        
        # Extract images (excluding GIFs already processed)
        images = self._extract_images(soup)
        for idx, img_url in enumerate(images):
            if img_url not in seen_urls:
                seen_urls.add(img_url)
                media_items.append(self._create_media_item(
                    post_id=post_id,
                    post_url=post_url,
                    timestamp=timestamp,
                    media_url=img_url,
                    media_type='image',
                    index=idx
                ))
        
        # Extract videos
        videos = self._extract_videos(soup)
        for idx, video_url in enumerate(videos):
            if video_url not in seen_urls:
                seen_urls.add(video_url)
                media_items.append(self._create_media_item(
                    post_id=post_id,
                    post_url=post_url,
                    timestamp=timestamp,
                    media_url=video_url,
                    media_type='video',
                    index=idx
                ))
        
        logger.debug(f"Extracted {len(media_items)} media items from post {post_id}")
        return media_items
    
    def _extract_images(self, soup: BeautifulSoup) -> List[str]:
        """
        Extract image URLs from post HTML (excluding GIFs).
        
        Args:
            soup: BeautifulSoup object of post HTML
            
        Returns:
            List of image URLs (non-GIF images)
        """
        image_urls: List[str] = []
        
        # Find all img tags
        for img in soup.find_all('img'):
            # Try different attributes where Tumblr stores image URLs
            for attr in ['src', 'data-src', 'data-original', 'data-highres']:
                url = img.get(attr)
                if url and self._is_tumblr_media_url(url):
                    # Skip GIFs - they'll be extracted separately
                    if url.lower().endswith('.gif'):
                        continue
                    # Get highest resolution version
                    url = self._get_high_res_url(url)
                    if url not in image_urls:
                        image_urls.append(url)
                    break  # Only take first valid URL per img tag
        
        # Find photoset/gallery images (data-photoset attribute)
        for elem in soup.find_all(attrs={'data-photoset': True}):
            photoset_data = elem.get('data-photoset', '')
            # Extract URLs from photoset JSON-like data
            urls = re.findall(r'https?://[^\s,"\']+\.(?:jpg|jpeg|png|gif|webp)', photoset_data)
            for url in urls:
                if self._is_tumblr_media_url(url):
                    # Skip GIFs
                    if url.lower().endswith('.gif'):
                        continue
                    url = self._get_high_res_url(url)
                    if url not in image_urls:
                        image_urls.append(url)
        
        # Look for background images in style attributes
        for elem in soup.find_all(style=re.compile(r'background-image')):
            style = elem.get('style', '')
            urls = re.findall(r'url\(["\']?(https?://[^"\')\s]+)["\']?\)', style)
            for url in urls:
                if self._is_tumblr_media_url(url):
                    # Skip GIFs
                    if url.lower().endswith('.gif'):
                        continue
                    url = self._get_high_res_url(url)
                    if url not in image_urls:
                        image_urls.append(url)
        
        return image_urls
    
    def _extract_videos(self, soup: BeautifulSoup) -> List[str]:
        """
        Extract video URLs from post HTML.
        
        Args:
            soup: BeautifulSoup object of post HTML
            
        Returns:
            List of video URLs
        """
        video_urls: List[str] = []
        
        # Find all video tags
        for video in soup.find_all('video'):
            # Try src attribute on video tag
            url = video.get('src')
            if url and self._is_tumblr_media_url(url):
                if url not in video_urls:
                    video_urls.append(url)
            
            # Try source tags inside video
            for source in video.find_all('source'):
                url = source.get('src')
                if url and self._is_tumblr_media_url(url):
                    if url not in video_urls:
                        video_urls.append(url)
        
        # Find Tumblr video player iframes and extract video URLs
        for iframe in soup.find_all('iframe'):
            src = iframe.get('src', '')
            if 'tumblr.com/video' in src:
                # Try to extract actual video URL from iframe src or data attributes
                video_id = re.search(r'/video/[^/]+/(\d+)', src)
                if video_id:
                    # Construct potential video URL
                    # Note: This may need adjustment based on actual Tumblr video URLs
                    logger.debug(f"Found Tumblr video iframe: {src}")
        
        # Look for data-video attributes
        for elem in soup.find_all(attrs={'data-video': True}):
            url = elem.get('data-video')
            if url and self._is_tumblr_media_url(url):
                if url not in video_urls:
                    video_urls.append(url)
        
        return video_urls
    
    def _extract_gifs(self, soup: BeautifulSoup) -> List[str]:
        """
        Extract animated GIF URLs from post HTML.
        
        Args:
            soup: BeautifulSoup object of post HTML
            
        Returns:
            List of GIF URLs
        """
        gif_urls: List[str] = []
        
        # Find img tags with .gif extension
        for img in soup.find_all('img'):
            for attr in ['src', 'data-src', 'data-original']:
                url = img.get(attr)
                if url and url.endswith('.gif') and self._is_tumblr_media_url(url):
                    if url not in gif_urls:
                        gif_urls.append(url)
                    break
        
        return gif_urls
    
    def _is_tumblr_media_url(self, url: str) -> bool:
        """
        Check if URL is a Tumblr media URL.
        
        Args:
            url: URL to check
            
        Returns:
            True if URL is from Tumblr's media CDN
        """
        if not url:
            return False
        
        try:
            parsed = urlparse(url)
            # Check if domain is a Tumblr media domain
            if parsed.netloc in self.TUMBLR_MEDIA_DOMAINS:
                return True
            
            # Check for common Tumblr media URL patterns
            if 'tumblr' in parsed.netloc and any(
                ext in parsed.path.lower() 
                for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.webm']
            ):
                return True
            
            return False
        except Exception:
            return False
    
    def _get_high_res_url(self, url: str) -> str:
        """
        Convert Tumblr image URL to highest resolution version.
        
        Tumblr uses size suffixes like _500.jpg, _1280.jpg, etc.
        This attempts to get the highest resolution (_1280 or raw).
        
        Args:
            url: Original image URL
            
        Returns:
            High-resolution version of the URL
        """
        # Replace size suffix with _1280 for highest quality
        # Pattern: tumblr_xxxxx_500.jpg -> tumblr_xxxxx_1280.jpg
        url = re.sub(r'_\d+\.(jpg|jpeg|png|gif|webp)$', r'_1280.\1', url, flags=re.IGNORECASE)
        
        return url
    
    def _create_media_item(
        self,
        post_id: str,
        post_url: str,
        timestamp: datetime,
        media_url: str,
        media_type: str,
        index: int
    ) -> MediaItem:
        """
        Create a MediaItem object from extracted data.
        
        Args:
            post_id: Post identifier
            post_url: Post URL
            timestamp: Post timestamp
            media_url: URL of the media file
            media_type: Type of media ('image', 'video', 'gif')
            index: Index of media item in post
            
        Returns:
            MediaItem object
        """
        # Generate filename from URL and index
        parsed = urlparse(media_url)
        original_filename = parsed.path.split('/')[-1]
        extension = original_filename.split('.')[-1] if '.' in original_filename else 'jpg'
        
        # Format: postid_index.ext (e.g., 123456789_001.jpg)
        filename = f"{post_id}_{index:03d}.{extension}"
        
        return MediaItem(
            post_id=post_id,
            post_url=post_url,
            timestamp=timestamp,
            media_type=media_type,
            filename=filename,
            original_url=media_url,
            retrieved_from='tumblr',  # Will be updated during download
            status='missing',  # Will be updated during download
        )
