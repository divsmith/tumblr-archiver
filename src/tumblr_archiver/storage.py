"""
Storage utilities for file operations.

This module provides utility functions for safe file operations including
atomic writes, directory management, and filename generation.
"""

import os
import tempfile
from pathlib import Path
from typing import Union
from urllib.parse import urlparse

import aiofiles


async def ensure_directory(path: Union[str, Path]) -> Path:
    """
    Create directory and parent directories if they don't exist.
    
    Thread-safe and idempotent - safe to call multiple times
    for the same path.
    
    Args:
        path: Directory path to create
        
    Returns:
        Path object for the created directory
        
    Example:
        ```python
        media_dir = await ensure_directory("output/images")
        ```
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


async def atomic_write(filepath: Union[str, Path], content: str) -> None:
    """
    Write content to file atomically using temp file and rename.
    
    Prevents file corruption by writing to a temporary file first,
    then atomically moving it to the target location. This ensures
    that the file is never in a partially written state.
    
    Args:
        filepath: Target file path
        content: String content to write
        
    Raises:
        IOError: If write or rename fails
        
    Example:
        ```python
        await atomic_write("manifest.json", json_content)
        ```
    """
    filepath = Path(filepath)
    
    # Ensure parent directory exists
    await ensure_directory(filepath.parent)
    
    # Create temp file in the same directory as target
    # This ensures atomic rename works (same filesystem)
    fd, temp_path = tempfile.mkstemp(
        dir=filepath.parent,
        prefix=f".{filepath.name}.",
        suffix=".tmp"
    )
    
    try:
        # Write to temp file
        async with aiofiles.open(temp_path, 'w', encoding='utf-8') as f:
            await f.write(content)
        
        # Close the file descriptor
        os.close(fd)
        
        # Atomically replace target file
        # On POSIX systems (Unix, Linux, macOS), this is atomic
        os.replace(temp_path, filepath)
        
    except Exception:
        # Clean up temp file on error
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def get_media_directory(output_dir: Union[str, Path], media_type: str) -> Path:
    """
    Get subdirectory path for specific media type.
    
    Organizes media files into subdirectories by type:
    - images/ for image files
    - gifs/ for GIF files
    - videos/ for video files
    
    Args:
        output_dir: Base output directory
        media_type: Type of media ('image', 'gif', or 'video')
        
    Returns:
        Path to media type subdirectory
        
    Example:
        ```python
        image_dir = get_media_directory("/archive/blog", "image")
        # Returns: /archive/blog/images
        ```
    """
    output_dir = Path(output_dir)
    
    # Map singular to plural directory names
    type_dirs = {
        "image": "images",
        "gif": "gifs",
        "video": "videos"
    }
    
    subdir_name = type_dirs.get(media_type, media_type)
    return output_dir / subdir_name


def generate_unique_filename(original_url: str, checksum: str = None) -> str:
    """
    Generate a safe, unique filename from URL and optional checksum.
    
    Creates a filename that:
    - Preserves the original file extension
    - Uses checksum (if available) for uniqueness
    - Falls back to URL-based name if no checksum
    - Is safe for all filesystems (no special characters)
    
    Args:
        original_url: Original URL of the media file
        checksum: Optional SHA256 checksum (64 hex chars)
        
    Returns:
        Safe filename string
        
    Example:
        ```python
        # With checksum
        filename = generate_unique_filename(
            "https://example.com/image.jpg",
            "a" * 64
        )
        # Returns: "aaaaaaaaaaaaaaaa.jpg"
        
        # Without checksum
        filename = generate_unique_filename(
            "https://example.com/tumblr_abc123.jpg"
        )
        # Returns: "tumblr_abc123.jpg"
        ```
    """
    # Extract filename and extension from URL
    parsed_url = urlparse(original_url)
    url_path = parsed_url.path
    
    # Get the last part of the path (filename)
    original_filename = Path(url_path).name
    
    # Extract extension (with dot)
    extension = Path(original_filename).suffix.lower()
    
    # If no extension found, try to guess from URL
    if not extension:
        extension = ".jpg"  # Default fallback
    
    if checksum:
        # Use first 16 chars of checksum for filename
        # This provides good uniqueness while keeping names reasonable
        base_name = checksum[:16]
    else:
        # Fall back to using original filename without extension
        base_name = Path(original_filename).stem
        
        # Sanitize the filename - remove special characters
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        base_name = "".join(c if c in safe_chars else "_" for c in base_name)
        
        # Truncate if too long
        if len(base_name) > 100:
            base_name = base_name[:100]
        
        # Ensure it's not empty
        if not base_name:
            base_name = "media"
    
    return f"{base_name}{extension}"
