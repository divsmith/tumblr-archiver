"""
URL utility functions for Tumblr archiver.

This module provides URL parsing, validation, canonicalization, and media URL
extraction utilities for handling Tumblr blog URLs, post URLs, media URLs,
and Wayback Machine URLs.
"""

import re
from pathlib import Path
from typing import List, Optional
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup


# Media file extensions by type
IMAGE_EXTENSIONS = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".svg"
})

VIDEO_EXTENSIONS = frozenset({
    ".mp4", ".webm", ".mov", ".avi", ".mkv", ".flv", ".wmv", ".m4v"
})

AUDIO_EXTENSIONS = frozenset({
    ".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac", ".wma"
})

ALL_MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | AUDIO_EXTENSIONS

# Common tracking parameters to remove during normalization
TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ref", "ref_src", "ref_url"
})


def is_valid_url(url: str) -> bool:
    """
    Validate if a string is a properly formatted URL.
    
    Args:
        url: String to validate as URL
        
    Returns:
        True if URL is valid, False otherwise
        
    Examples:
        >>> is_valid_url("https://example.com")
        True
        >>> is_valid_url("not a url")
        False
    """
    if not url or not isinstance(url, str):
        return False
    
    try:
        result = urlparse(url.strip())
        # Must have scheme and netloc (domain)
        return bool(result.scheme in ("http", "https") and result.netloc)
    except Exception:
        return False


def normalize_url(url: str) -> str:
    """
    Canonicalize URL by removing tracking parameters and fragments.
    
    Args:
        url: URL to normalize
        
    Returns:
        Normalized URL with tracking params and fragments removed
        
    Raises:
        ValueError: If URL is invalid
        
    Examples:
        >>> normalize_url("https://example.com/path?utm_source=twitter#section")
        'https://example.com/path'
    """
    if not is_valid_url(url):
        raise ValueError(f"Invalid URL: {url}")
    
    parsed = urlparse(url.strip())
    
    # Filter out tracking parameters
    if parsed.query:
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        filtered_params = {
            k: v for k, v in query_params.items()
            if k not in TRACKING_PARAMS
        }
        # Reconstruct query string
        if filtered_params:
            query_string = "&".join(
                f"{k}={v[0]}" if v else k
                for k, v in filtered_params.items()
            )
        else:
            query_string = ""
    else:
        query_string = ""
    
    # Reconstruct URL without fragment and with filtered query
    normalized = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        query_string,
        ""  # Remove fragment
    ))
    
    return normalized


def extract_blog_name(url: str) -> Optional[str]:
    """
    Extract blog name from a Tumblr URL.
    
    Supports multiple Tumblr URL formats:
    - Standard: https://blogname.tumblr.com
    - Custom domain: https://example.com (requires tumblr.com in path)
    - Post URLs: https://blogname.tumblr.com/post/123456
    
    Args:
        url: Tumblr URL to extract blog name from
        
    Returns:
        Blog name if found, None otherwise
        
    Examples:
        >>> extract_blog_name("https://myblog.tumblr.com")
        'myblog'
        >>> extract_blog_name("https://myblog.tumblr.com/post/123456")
        'myblog'
    """
    if not is_valid_url(url):
        return None
    
    parsed = urlparse(url.strip())
    netloc = parsed.netloc.lower()
    
    # Standard Tumblr subdomain: blogname.tumblr.com
    if netloc.endswith(".tumblr.com"):
        # Extract subdomain (blog name)
        blog_name = netloc.replace(".tumblr.com", "")
        if blog_name and blog_name != "www":
            return blog_name
    
    # Handle www.tumblr.com/blog/blogname format
    if netloc in ("tumblr.com", "www.tumblr.com"):
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) >= 2 and path_parts[0] == "blog":
            return path_parts[1]
    
    return None


def build_blog_url(blog_name: str) -> str:
    """
    Construct a Tumblr blog URL from a blog name.
    
    Args:
        blog_name: Tumblr blog name
        
    Returns:
        Full Tumblr blog URL
        
    Examples:
        >>> build_blog_url("myblog")
        'https://myblog.tumblr.com'
    """
    if not blog_name:
        raise ValueError("Blog name cannot be empty")
    
    # Remove .tumblr.com if already included
    blog_name = blog_name.replace(".tumblr.com", "")
    
    return f"https://{blog_name}.tumblr.com"


def build_post_url(blog_name: str, post_id: str) -> str:
    """
    Construct a Tumblr post URL from blog name and post ID.
    
    Args:
        blog_name: Tumblr blog name
        post_id: Tumblr post ID
        
    Returns:
        Full Tumblr post URL
        
    Examples:
        >>> build_post_url("myblog", "123456789")
        'https://myblog.tumblr.com/post/123456789'
    """
    if not blog_name or not post_id:
        raise ValueError("Blog name and post ID cannot be empty")
    
    base_url = build_blog_url(blog_name)
    return f"{base_url}/post/{post_id}"


def is_tumblr_url(url: str) -> bool:
    """
    Check if a URL is from Tumblr.
    
    Args:
        url: URL to check
        
    Returns:
        True if URL is from Tumblr, False otherwise
        
    Examples:
        >>> is_tumblr_url("https://myblog.tumblr.com")
        True
        >>> is_tumblr_url("https://example.com")
        False
    """
    if not is_valid_url(url):
        return False
    
    parsed = urlparse(url.strip())
    netloc = parsed.netloc.lower()
    
    return (
        netloc.endswith(".tumblr.com") or
        netloc in ("tumblr.com", "www.tumblr.com")
    )


def is_media_url(url: str) -> bool:
    """
    Check if a URL points to a media file (image, video, or audio).
    
    Args:
        url: URL to check
        
    Returns:
        True if URL points to media file, False otherwise
        
    Examples:
        >>> is_media_url("https://example.com/image.jpg")
        True
        >>> is_media_url("https://example.com/page.html")
        False
    """
    if not is_valid_url(url):
        return False
    
    parsed = urlparse(url.strip())
    path = parsed.path.lower()
    
    # Check if path has a media extension
    path_obj = Path(path)
    extension = path_obj.suffix
    
    return extension in ALL_MEDIA_EXTENSIONS


def get_media_type_from_url(url: str) -> Optional[str]:
    """
    Determine media type from URL/extension.
    
    Args:
        url: URL to analyze
        
    Returns:
        Media type ("image", "video", "audio") or None if not media
        
    Examples:
        >>> get_media_type_from_url("https://example.com/photo.jpg")
        'image'
        >>> get_media_type_from_url("https://example.com/video.mp4")
        'video'
    """
    if not is_valid_url(url):
        return None
    
    parsed = urlparse(url.strip())
    path = parsed.path.lower()
    path_obj = Path(path)
    extension = path_obj.suffix
    
    if extension in IMAGE_EXTENSIONS:
        return "image"
    elif extension in VIDEO_EXTENSIONS:
        return "video"
    elif extension in AUDIO_EXTENSIONS:
        return "audio"
    
    return None


def extract_media_urls(html: str) -> List[str]:
    """
    Extract media URLs from HTML content.
    
    Extracts URLs from:
    - <img> src attributes
    - <video> src attributes and <source> tags
    - <audio> src attributes and <source> tags
    - CSS background-image properties (basic)
    
    Args:
        html: HTML content to parse
        
    Returns:
        List of extracted media URLs
        
    Examples:
        >>> extract_media_urls('<img src="https://example.com/image.jpg">')
        ['https://example.com/image.jpg']
    """
    if not html:
        return []
    
    urls = []
    
    try:
        soup = BeautifulSoup(html, "lxml")
        
        # Extract from <img> tags
        for img in soup.find_all("img"):
            src = img.get("src")
            if src and is_valid_url(src):
                urls.append(src)
        
        # Extract from <video> tags and their <source> children
        for video in soup.find_all("video"):
            src = video.get("src")
            if src and is_valid_url(src):
                urls.append(src)
            
            # Check <source> tags within <video>
            for source in video.find_all("source"):
                src = source.get("src")
                if src and is_valid_url(src):
                    urls.append(src)
        
        # Extract from <audio> tags and their <source> children
        for audio in soup.find_all("audio"):
            src = audio.get("src")
            if src and is_valid_url(src):
                urls.append(src)
            
            # Check <source> tags within <audio>
            for source in audio.find_all("source"):
                src = source.get("src")
                if src and is_valid_url(src):
                    urls.append(src)
        
        # Extract from style attributes with background-image
        for element in soup.find_all(style=True):
            style = element.get("style", "")
            # Simple regex to find url() in CSS
            css_urls = re.findall(r'url\(["\']?([^"\')]+)["\']?\)', style)
            for css_url in css_urls:
                if is_valid_url(css_url):
                    urls.append(css_url)
    
    except Exception:
        # If parsing fails, return empty list
        return []
    
    # Remove duplicates while preserving order
    seen = set()
    unique_urls = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    
    return unique_urls


def is_wayback_url(url: str) -> bool:
    """
    Check if a URL is from Internet Archive's Wayback Machine.
    
    Args:
        url: URL to check
        
    Returns:
        True if URL is from Wayback Machine, False otherwise
        
    Examples:
        >>> is_wayback_url("https://web.archive.org/web/20210101000000/example.com")
        True
        >>> is_wayback_url("https://example.com")
        False
    """
    if not is_valid_url(url):
        return False
    
    parsed = urlparse(url.strip())
    netloc = parsed.netloc.lower()
    
    return netloc in ("web.archive.org", "archive.org")


def extract_original_url_from_wayback(url: str) -> Optional[str]:
    """
    Extract the original URL from a Wayback Machine URL.
    
    Wayback URLs follow the format:
    https://web.archive.org/web/TIMESTAMP/ORIGINAL_URL
    or
    https://web.archive.org/web/TIMESTAMPid_/ORIGINAL_URL
    
    Args:
        url: Wayback Machine URL
        
    Returns:
        Original URL if found, None otherwise
        
    Examples:
        >>> extract_original_url_from_wayback(
        ...     "https://web.archive.org/web/20210101000000/https://example.com"
        ... )
        'https://example.com'
    """
    if not is_wayback_url(url):
        return None
    
    parsed = urlparse(url.strip())
    path = parsed.path
    
    # Pattern: /web/TIMESTAMP[id_]/ORIGINAL_URL
    # Timestamp is typically 14 digits (YYYYMMDDhhmmss)
    match = re.search(r'/web/\d{1,14}(?:id_)?/(.*)', path)
    
    if match:
        original_url = match.group(1)
        # Handle case where scheme might be missing
        if not original_url.startswith(("http://", "https://")):
            # Try adding http if no scheme present
            original_url = "http://" + original_url
        
        if is_valid_url(original_url):
            return original_url
    
    return None


def get_filename_from_url(url: str) -> str:
    """
    Extract filename from a URL.
    
    Args:
        url: URL to extract filename from
        
    Returns:
        Filename extracted from URL, or "download" if no filename found
        
    Examples:
        >>> get_filename_from_url("https://example.com/path/image.jpg")
        'image.jpg'
        >>> get_filename_from_url("https://example.com/path/?query=1")
        'download'
    """
    if not is_valid_url(url):
        return "download"
    
    parsed = urlparse(url.strip())
    path = parsed.path
    
    # Get the last part of the path
    path_obj = Path(path)
    filename = path_obj.name
    
    # If no filename or it's just a directory, return default
    if not filename or filename == "/" or "." not in filename:
        return "download"
    
    return filename


def sanitize_filename(filename: str) -> str:
    """
    Make a filename safe for filesystem use.
    
    Removes or replaces characters that are problematic on various filesystems:
    - Control characters
    - Reserved characters: < > : " / \\ | ? *
    - Leading/trailing dots and spaces
    - Reserved names on Windows
    
    Args:
        filename: Filename to sanitize
        
    Returns:
        Sanitized filename safe for filesystem use
        
    Examples:
        >>> sanitize_filename("my file?.txt")
        'my file.txt'
        >>> sanitize_filename("../../../etc/passwd")
        'etc_passwd'
    """
    if not filename:
        return "unnamed"
    
    # Remove path components (security)
    filename = Path(filename).name
    
    # Replace reserved/problematic characters with underscore
    reserved_chars = r'[<>:"/\\|?*\x00-\x1f]'
    sanitized = re.sub(reserved_chars, "_", filename)
    
    # Remove leading/trailing dots and spaces first
    sanitized = sanitized.strip(". ")
    
    # Remove any remaining path traversal sequences
    while ".." in sanitized:
        sanitized = sanitized.replace("..", ".")
    
    # Strip again in case we created new leading/trailing dots
    sanitized = sanitized.strip(". ")
    
    # If empty after sanitization, return default
    if not sanitized:
        return "unnamed"
    
    # Handle Windows reserved names
    windows_reserved = {
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
    }
    
    name_without_ext = Path(sanitized).stem
    if name_without_ext.upper() in windows_reserved:
        sanitized = f"_{sanitized}"
    
    # If empty after sanitization, return default
    if not sanitized:
        return "unnamed"
    
    # Limit length to 255 bytes (common filesystem limit)
    if len(sanitized.encode("utf-8")) > 255:
        # Preserve extension if possible
        path_obj = Path(sanitized)
        ext = path_obj.suffix
        stem = path_obj.stem
        
        # Calculate max stem length
        max_stem_length = 255 - len(ext.encode("utf-8"))
        
        # Truncate stem
        while len(stem.encode("utf-8")) > max_stem_length and stem:
            stem = stem[:-1]
        
        sanitized = stem + ext
    
    return sanitized
