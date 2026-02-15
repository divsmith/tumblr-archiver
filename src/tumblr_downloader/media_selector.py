"""
Media selector module for Tumblr Media Downloader.

This module handles extraction and selection of media from Tumblr posts,
including photos, videos, GIFs, and audio files. It intelligently selects
the highest quality version of each media item.
"""

from typing import List, Dict, Optional, Any
import logging
import re
from html.parser import HTMLParser

logger = logging.getLogger(__name__)


class ImageExtractor(HTMLParser):
    """HTML parser to extract image URLs and dimensions from post bodies."""
    
    def __init__(self):
        super().__init__()
        self.images = []
    
    def handle_starttag(self, tag, attrs):
        """Extract img tags with their src and dimensions."""
        if tag == 'img':
            attrs_dict = dict(attrs)
            src = attrs_dict.get('src', '')
            if src:
                # Extract dimensions from data attributes
                width = 0
                height = 0
                
                try:
                    if 'data-orig-width' in attrs_dict:
                        width = int(attrs_dict['data-orig-width'])
                    if 'data-orig-height' in attrs_dict:
                        height = int(attrs_dict['data-orig-height'])
                except (ValueError, TypeError):
                    pass
                
                self.images.append({
                    'url': src,
                    'width': width,
                    'height': height
                })


def extract_media_from_post(post: dict) -> List[dict]:
    """
    Extract all media items from a Tumblr post.
    
    This is the main entry point for media extraction. It handles different
    post types (photo, video, audio) and returns a normalized list of media
    items with their metadata.
    
    Args:if post_type == 'regular':
            media_items.extend(_extract_regular(post, post_id))
        el
        post: A Tumblr post dictionary from the API response
        
    Returns:
        List of media item dictionaries, each containing:
        - url (str): Direct URL to the media file
        - width (int): Width in pixels (0 if unknown)
        - height (int): Height in pixels (0 if unknown)
        - type (str): Media type ('photo', 'video', 'gif', 'audio')
        - post_id (str): The post ID this media belongs to
        
    Examples:
        >>> post = {'id': '123', 'type': 'photo', 'photos': [...]}
        >>> media = extract_media_from_post(post)
        >>> media[0]['url']
        'https://...'
    """
    if not isinstance(post, dict):
        logger.warning("Invalid post object: not a dictionary")
        return []
    
    post_id = str(post.get('id', 'unknown'))
    post_type = post.get('type', '').lower()
    
    media_items = []
    
    try:
        if post_type == 'photo':
            media_items.extend(_extract_photos(post, post_id))
        elif post_type == 'video':
            media_items.extend(_extract_videos(post, post_id))
        elif post_type == 'audio':
            media_items.extend(_extract_audio(post, post_id))
        elif post_type == 'regular':
            media_items.extend(_extract_regular(post, post_id))
        else:
            logger.debug(f"Unsupported post type '{post_type}' for post {post_id}")
            
    except Exception as e:
        logger.error(f"Error extracting media from post {post_id}: {e}", exc_info=True)
    
    return media_items


def select_best_image(variants: List[dict]) -> dict:
    """
    Select the highest quality image from a list of variants.
    
    Selection criteria (in order of priority):
    1. Largest width × height (pixel area)
    2. Prefer 'original' in URL or larger size indicators (_1280 > _500)
    3. First variant if all else is equal
    
    Args:
        variants: List of image variant dictionaries, each should contain:
                 - url (str): Image URL
                 - width (int, optional): Image width
                 - height (int, optional): Image height
                 
    Returns:
        The best quality variant dictionary
        
    Raises:
        ValueError: If variants list is empty
        
    Examples:
        >>> variants = [
        ...     {'url': 'image_500.jpg', 'width': 500, 'height': 400},
        ...     {'url': 'image_1280.jpg', 'width': 1280, 'height': 1024}
        ... ]
        >>> best = select_best_image(variants)
        >>> best['width']
        1280
    """
    if not variants:
        raise ValueError("Cannot select from empty variants list")
    
    if len(variants) == 1:
        return variants[0]
    
    def get_pixel_area(variant: dict) -> int:
        """Calculate pixel area, returns 0 if dimensions unknown."""
        width = variant.get('width', 0) or 0
        height = variant.get('height', 0) or 0
        return width * height
    
    def get_url_size_score(url: str) -> int:
        """
        Extract size indicator from URL for tie-breaking.
        
        Returns higher scores for larger sizes mentioned in URL.
        """
        if not url:
            return 0
            
        # Check for 'original' in URL
        if 'original' in url.lower():
            return 10000
        
        # Extract common Tumblr size patterns: _1280, _500, etc.
        size_pattern = re.search(r'_(\d+)(?:\.|/|$)', url)
        if size_pattern:
            return int(size_pattern.group(1))
        
        return 0
    
    # Sort variants by:
    # 1. Pixel area (descending)
    # 2. URL size score (descending)
    # 3. Maintain original order as final tie-breaker
    sorted_variants = sorted(
        enumerate(variants),
        key=lambda x: (
            get_pixel_area(x[1]),
            get_url_size_score(x[1].get('url', '')),
            -x[0]  # Negative index to prefer earlier items
        ),
        reverse=True
    )
    
    best_variant = sorted_variants[0][1]
    logger.debug(f"Selected image variant: {best_variant.get('url', 'unknown')} "
                 f"({best_variant.get('width', 0)}×{best_variant.get('height', 0)})")
    
    return best_variant


def _extract_photos(post: dict, post_id: str) -> List[dict]:
    """
    Extract v1 API photo posts which have photo-url-XXXX fields.
    Selects the highest resolution available.
    
    Args:
        post: Tumblr post dictionary
        post_id: Post ID for metadata
        
    Returns:
        List of photo media items
    """
    media_items = []
    
    # v1 API uses photo-url-1280, photo-url-500, etc. fields
    # Build variants from all photo-url-* fields
    variants = []
    
    # Known photo URL fields in order of preference
    photo_url_fields = [
        'photo-url-1280',
        'photo-url-500', 
        'photo-url-400',
        'photo-url-250',
        'photo-url-100',
        'photo-url-75'
    ]
    
    for field in photo_url_fields:
        url = post.get(field)
        if url:
            # Extract size from field name
            size_match = re.search(r'photo-url-(\d+)', field)
            size = int(size_match.group(1)) if size_match else 0
            
            variants.append({
                'url': url,
                'width': size,  # Use size as width approximation
                'height': 0  # Height not directly available per variant
            })
    
    # Get original dimensions if available
    orig_width = post.get('width', 0) or 0
    orig_height = post.get('height', 0) or 0
    
    if variants:
        # Select best quality (usually photo-url-1280)
        best = select_best_image(variants)
        
        # Use original dimensions if available
        if orig_width and orig_height:
            best['width'] = orig_width
            best['height'] = orig_height
        
        # Determine if it's an animated GIF
        media_type = 'photo'
        url = best['url']
        if url and url.lower().endswith('.gif'):
            media_type = 'gif'
        
        media_items.append({
            'url': best['url'],
            'width': best.get('width', 0),
            'height': best.get('height', 0),
            'type': media_type,
            'post_id': post_id
        })
        
        logger.debug(f"Extracted photo from post {post_id}: {best['url']}")
    else:
        logger.warning(f"No photo URLs found in photo post {post_id}")
    
    return media_items


def _extract_videos(post: dict, post_id: str) -> List[dict]:
    """
    Extract video from a video post.
    
    Selects the highest quality video available from the player object.
    
    Args:
        post: Tumblr post dictionary
        post_id: Post ID for metadata
        
    Returns:
        List containing video media item (single item)
    """
    media_items = []
    
    # Try to get video URL from player
    player = post.get('player')
    video_url = post.get('video_url')
    
    # Method 1: Extract from player array
    if isinstance(player, list) and player:
        # Player array contains embed codes, try to find video URL
        # Usually the last player has the highest quality
        for player_item in reversed(player):
            if isinstance(player_item, dict):
                embed_code = player_item.get('embed_code', '')
                # Try to extract video URL from embed code
                url_match = re.search(r'https?://[^\s"\'<>]+\.(?:mp4|mov|avi)', embed_code)
                if url_match:
                    video_url = url_match.group(0)
                    break
    
    # Method 2: Direct video_url field
    if not video_url:
        video_url = post.get('video_url')
    
    # Method 3: Check video object
    if not video_url:
        video_obj = post.get('video')
        if isinstance(video_obj, dict):
            video_url = video_obj.get('url')
    
    if video_url:
        # Try to get dimensions
        width = 0
        height = 0
        
        # Check for dimensions in various places
        if isinstance(player, list) and player:
            last_player = player[-1]
            if isinstance(last_player, dict):
                width = last_player.get('width', 0) or 0
                height = last_player.get('height', 0) or 0
        
        media_items.append({
            'url': video_url,
            'width': width,
            'height': height,
            'type': 'video',
            'post_id': post_id
        })
    else:
        logger.warning(f"No video URL found in video post {post_id}")
    
    return media_items


def _extract_audio(post: dict, post_id: str) -> List[dict]:
    """
    Extract audio from an audio post.
    
    Args:
        post: Tumblr post dictionary
        post_id: Post ID for metadata
        
    Returns:
        List containing audio media item (single item)
    """
    media_items = []
    
    # Audio URL can be in different fields
    audio_url = post.get('audio_url')
    
    # Try to extract from player if not directly available
    if not audio_url:
        player = post.get('player')
        if isinstance(player, str):
            # Try to extract audio URL from player HTML
            url_match = re.search(r'https?://[^\s"\'<>]+\.(?:mp3|wav|m4a|ogg)', player)
            if url_match:
                audio_url = url_match.group(0)
    
    # Check audio_source_url field (some posts use this)
    if not audio_url:
        audio_url = post.get('audio_source_url')
    
    if audio_url:
        media_items.append({
            'url': audio_url,
            'width': 0,
            'height': 0,
            'type': 'audio',
            'post_id': post_id
        })
    else:
        logger.warning(f"No audio URL found in audio post {post_id}")
    
    return media_items


def _extract_regular(post: dict, post_id: str) -> List[dict]:
    """
    Extract images from a regular/text post.
    
    Regular posts contain HTML in the 'regular-body' field which may
    include embedded images. This function parses the HTML and extracts
    all image URLs with their dimensions.
    
    Args:
        post: Tumblr post dictionary
        post_id: Post ID for metadata
        
    Returns:
        List of image media items found in the post body
    """
    media_items = []
    
    # Get the HTML body content
    body = post.get('regular-body', '')
    if not body:
        logger.debug(f"No regular-body found in regular post {post_id}")
        return media_items
    
    # Parse HTML to extract images
    try:
        parser = ImageExtractor()
        parser.feed(body)
        
        for img in parser.images:
            url = img.get('url', '')
            if not url:
                continue
            
            # Determine media type
            media_type = 'photo'
            if url.lower().endswith('.gif'):
                media_type = 'gif'
            
            media_items.append({
                'url': url,
                'width': img.get('width', 0),
                'height': img.get('height', 0),
                'type': media_type,
                'post_id': post_id
            })
            
            logger.debug(f"Extracted image from regular post {post_id}: {url}")
            
    except Exception as e:
        logger.error(f"Error parsing HTML in regular post {post_id}: {e}")
    
    return media_items
