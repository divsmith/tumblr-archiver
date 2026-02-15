"""
Utility functions for the Tumblr Media Downloader.

This module provides common utilities for file handling, logging,
string manipulation, and data extraction.
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Union
from urllib.parse import urlparse


def sanitize_filename(filename: str) -> str:
    """
    Remove invalid characters from a filename and handle edge cases.
    
    Args:
        filename: The original filename to sanitize
        
    Returns:
        A sanitized filename safe for use across different filesystems
        
    Raises:
        ValueError: If the filename is empty or becomes empty after sanitization
    """
    if not filename or not filename.strip():
        raise ValueError("Filename cannot be empty")
    
    # Remove or replace invalid characters for Windows/Unix filesystems
    # Invalid chars: < > : " / \ | ? * and control characters (0-31)
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
    
    # Remove leading/trailing spaces and dots (problematic on Windows)
    sanitized = sanitized.strip('. ')
    
    # Handle reserved Windows filenames
    reserved_names = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    name_without_ext = os.path.splitext(sanitized)[0].upper()
    if name_without_ext in reserved_names:
        sanitized = f"_{sanitized}"
    
    # Limit length to 255 chars (common filesystem limit)
    if len(sanitized) > 255:
        name, ext = os.path.splitext(sanitized)
        sanitized = name[:255 - len(ext)] + ext
    
    if not sanitized:
        raise ValueError("Filename becomes empty after sanitization")
    
    return sanitized


def parse_blog_name(blog_input: str) -> str:
    """
    Extract blog name from URL or raw input.
    
    Handles various formats:
    - https://blogname.tumblr.com
    - http://blogname.tumblr.com/
    - blogname.tumblr.com
    - blogname
    - custom domain URLs
    
    Args:
        blog_input: Blog URL or name
        
    Returns:
        The extracted blog name
        
    Raises:
        ValueError: If blog_input is empty or invalid
    """
    if not blog_input or not blog_input.strip():
        raise ValueError("Blog input cannot be empty")
    
    blog_input = blog_input.strip()
    
    # If it looks like a URL, parse it
    if '://' in blog_input or blog_input.startswith('www.'):
        if not blog_input.startswith(('http://', 'https://')):
            blog_input = 'https://' + blog_input
        
        parsed = urlparse(blog_input)
        hostname = parsed.netloc or parsed.path.split('/')[0]
        
        # Extract the subdomain from tumblr.com URLs
        if '.tumblr.com' in hostname:
            blog_name = hostname.split('.tumblr.com')[0]
            # Remove www. prefix if present
            blog_name = blog_name.replace('www.', '')
        else:
            # For custom domains, use the full hostname without www
            blog_name = hostname.replace('www.', '')
    else:
        # Remove .tumblr.com suffix if present in plain text
        blog_name = blog_input.replace('.tumblr.com', '')
    
    blog_name = blog_name.strip()
    
    if not blog_name:
        raise ValueError("Could not extract valid blog name")
    
    return blog_name


def setup_logging(verbose: bool = False) -> logging.Logger:
    """
    Configure application-wide logging.
    
    Args:
        verbose: If True, set logging level to DEBUG; otherwise INFO
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger('tumblr_downloader')
    
    # Avoid adding multiple handlers if logging is setup multiple times
    if logger.handlers:
        logger.handlers.clear()
    
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # Create console handler with formatting
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # Format: timestamp - level - message
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    
    return logger


def ensure_directory(path: Union[str, Path]) -> None:
    """
    Create directory if it doesn't exist.
    
    Creates parent directories as needed. No-op if directory already exists.
    
    Args:
        path: Directory path to create
        
    Raises:
        OSError: If directory creation fails
        ValueError: If path is empty
    """
    if not path:
        raise ValueError("Path cannot be empty")
    
    path_obj = Path(path)
    
    try:
        path_obj.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise OSError(f"Failed to create directory {path}: {e}") from e


def extract_post_id(url_or_data: Any) -> str:
    """
    Extract post ID from various formats.
    
    Handles:
    - Full Tumblr post URLs (https://blog.tumblr.com/post/123456789)
    - Short URLs (https://tmblr.co/...)
    - Dictionary with 'id' or 'id_string' keys
    - Direct string/int post IDs
    
    Args:
        url_or_data: URL string, dictionary, or post ID
        
    Returns:
        Extracted post ID as string
        
    Raises:
        ValueError: If post ID cannot be extracted
    """
    # Handle None
    if url_or_data is None:
        raise ValueError("Cannot extract post ID from None")
    
    # Handle dictionary (API response format)
    if isinstance(url_or_data, dict):
        post_id = url_or_data.get('id_string') or url_or_data.get('id')
        if post_id:
            return str(post_id)
        raise ValueError("Dictionary does not contain 'id' or 'id_string' key")
    
    # Handle integer
    if isinstance(url_or_data, int):
        return str(url_or_data)
    
    # Handle string
    if isinstance(url_or_data, str):
        url_or_data = url_or_data.strip()
        
        # If it's already just digits, return it
        if url_or_data.isdigit():
            return url_or_data
        
        # Try to extract from URL
        # Pattern: /post/123456789 or /post/123456789/some-slug
        match = re.search(r'/post/(\d+)', url_or_data)
        if match:
            return match.group(1)
        
        # Try to match just a number in the string
        match = re.search(r'\d+', url_or_data)
        if match:
            return match.group(0)
    
    raise ValueError(f"Could not extract post ID from: {url_or_data}")


def format_bytes(bytes_count: int) -> str:
    """
    Convert byte count to human-readable format.
    
    Args:
        bytes_count: Number of bytes
        
    Returns:
        Formatted string (e.g., "1.5 MB", "320 KB")
    """
    if bytes_count < 0:
        raise ValueError("Byte count cannot be negative")
    
    if bytes_count == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    unit_index = 0
    size = float(bytes_count)
    
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
    
    # Format with appropriate decimal places
    if unit_index == 0:  # Bytes
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.2f} {units[unit_index]}"
