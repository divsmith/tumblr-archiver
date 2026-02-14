"""
Security utilities for input validation and sanitization.

This module provides functions to validate and sanitize user inputs,
preventing common security vulnerabilities like path traversal,
URL manipulation, and injection attacks.
"""

import os
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urlunparse


class SecurityError(Exception):
    """Base exception for security-related errors."""
    pass


class InvalidBlogNameError(SecurityError):
    """Raised when a blog name is invalid or potentially malicious."""
    pass


class InvalidURLError(SecurityError):
    """Raised when a URL is invalid or potentially malicious."""
    pass


class PathTraversalError(SecurityError):
    """Raised when a path contains traversal attempts."""
    pass


class InvalidInputError(SecurityError):
    """Raised when user input fails validation."""
    pass


def sanitize_blog_name(name: str) -> str:
    """
    Validate and sanitize a Tumblr blog name.
    
    Blog names must:
    - Be 1-32 characters long
    - Contain only alphanumeric characters and hyphens
    - Not start or end with a hyphen
    - Not contain consecutive hyphens
    
    Args:
        name: The blog name to validate and sanitize
        
    Returns:
        The sanitized blog name
        
    Raises:
        InvalidBlogNameError: If the blog name is invalid
        
    Examples:
        >>> sanitize_blog_name("my-blog")
        'my-blog'
        >>> sanitize_blog_name("../etc/passwd")
        Traceback (most recent call last):
        ...
        InvalidBlogNameError: Invalid blog name format
    """
    if not name or not isinstance(name, str):
        raise InvalidBlogNameError("Blog name must be a non-empty string")
    
    # Strip whitespace
    name = name.strip()
    
    # Check if empty after stripping
    if not name:
        raise InvalidBlogNameError("Blog name must be a non-empty string")
    
    # Check length
    if len(name) < 1 or len(name) > 32:
        raise InvalidBlogNameError(
            "Blog name must be between 1 and 32 characters"
        )
    
    # Check for valid characters (alphanumeric and hyphens only)
    if not re.match(r'^[a-zA-Z0-9-]+$', name):
        raise InvalidBlogNameError(
            "Blog name can only contain letters, numbers, and hyphens"
        )
    
    # Check for leading/trailing hyphens
    if name.startswith('-') or name.endswith('-'):
        raise InvalidBlogNameError(
            "Blog name cannot start or end with a hyphen"
        )
    
    # Check for consecutive hyphens
    if '--' in name:
        raise InvalidBlogNameError(
            "Blog name cannot contain consecutive hyphens"
        )
    
    return name.lower()


def validate_url(url: str, allowed_schemes: Optional[list[str]] = None) -> str:
    """
    Validate and sanitize a URL.
    
    Checks that the URL:
    - Has a valid format
    - Uses an allowed scheme (http/https by default)
    - Has a valid netloc (domain)
    - Doesn't contain suspicious patterns
    
    Args:
        url: The URL to validate
        allowed_schemes: List of allowed URL schemes (default: ['http', 'https'])
        
    Returns:
        The validated and normalized URL
        
    Raises:
        InvalidURLError: If the URL is invalid or potentially malicious
        
    Examples:
        >>> validate_url("https://example.tumblr.com/post/123")
        'https://example.tumblr.com/post/123'
        >>> validate_url("javascript:alert(1)")
        Traceback (most recent call last):
        ...
        InvalidURLError: URL scheme 'javascript' not allowed
    """
    if not url or not isinstance(url, str):
        raise InvalidURLError("URL must be a non-empty string")
    
    # Strip whitespace
    url = url.strip()
    
    # Parse the URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise InvalidURLError(f"Invalid URL format: {e}")
    
    # Check scheme
    if allowed_schemes is None:
        allowed_schemes = ['http', 'https']
    
    if not parsed.scheme:
        raise InvalidURLError("URL must have a scheme (http:// or https://)")
    
    if parsed.scheme.lower() not in allowed_schemes:
        raise InvalidURLError(
            f"URL scheme '{parsed.scheme}' not allowed. "
            f"Allowed schemes: {', '.join(allowed_schemes)}"
        )
    
    # Check netloc (domain)
    if not parsed.netloc:
        raise InvalidURLError("URL must have a valid domain")
    
    # Check for suspicious patterns
    suspicious_patterns = [
        r'@',  # Potential credential injection
        r'\.\.',  # Path traversal
        r'[\x00-\x1f]',  # Control characters
        r'[\x7f-\x9f]',  # More control characters
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, url):
            raise InvalidURLError(
                f"URL contains suspicious pattern: {pattern}"
            )
    
    # Normalize and return
    return urlunparse(parsed)


def is_safe_path(path: str, base_dir: Optional[str] = None) -> bool:
    """
    Check if a path is safe and doesn't attempt path traversal.
    
    Validates that the resolved path:
    - Doesn't contain path traversal sequences
    - Stays within the base directory (if provided)
    - Doesn't point to sensitive system locations
    
    Args:
        path: The path to validate
        base_dir: Optional base directory to restrict path to
        
    Returns:
        True if the path is safe, False otherwise
        
    Examples:
        >>> is_safe_path("downloads/blog/image.jpg")
        True
        >>> is_safe_path("../../../etc/passwd")
        False
        >>> is_safe_path("downloads/blog/image.jpg", "/home/user/tumblr")
        True
    """
    if not path or not isinstance(path, str):
        return False
    
    try:
        # Check for path traversal patterns in the raw path
        if '..' in Path(path).parts:
            return False
        
        # If base_dir is provided, resolve relative to it
        if base_dir:
            base_obj = Path(base_dir).resolve()
            # For relative paths, resolve relative to base_dir
            if not Path(path).is_absolute():
                path_obj = (base_obj / path).resolve()
            else:
                path_obj = Path(path).resolve()
            
            # Ensure path is within base_dir
            try:
                path_obj.relative_to(base_obj)
            except ValueError:
                # Path is not relative to base_dir
                return False
        else:
            # No base_dir, just resolve the path
            path_obj = Path(path).resolve()
        
        # Check for sensitive system paths (Unix-like systems)
        # Check both the resolved path and common symlink locations
        path_str = str(path_obj)
        sensitive_paths = [
            '/etc',
            '/sys',
            '/proc',
            '/dev',
            '/root',
            '/boot',
            '/private/etc',  # macOS symlink target
            '/private/var/root',  # macOS root
        ]
        
        for sensitive in sensitive_paths:
            if path_str.startswith(sensitive + '/') or path_str == sensitive:
                return False
        
        return True
        
    except (OSError, RuntimeError, ValueError):
        return False


def sanitize_user_input(
    user_input: str,
    max_length: int = 1000,
    allow_newlines: bool = False
) -> str:
    """
    Sanitize general user input.
    
    Removes or escapes potentially dangerous characters and patterns.
    
    Args:
        user_input: The input string to sanitize
        max_length: Maximum allowed length
        allow_newlines: Whether to allow newline characters
        
    Returns:
        The sanitized input string
        
    Raises:
        InvalidInputError: If input fails validation
        
    Examples:
        >>> sanitize_user_input("normal-input")
        'normal-input'
        >>> sanitize_user_input("x" * 2000)
        Traceback (most recent call last):
        ...
        InvalidInputError: Input exceeds maximum length of 1000 characters
    """
    if not isinstance(user_input, str):
        raise InvalidInputError("Input must be a string")
    
    # Check length
    if len(user_input) > max_length:
        raise InvalidInputError(
            f"Input exceeds maximum length of {max_length} characters"
        )
    
    # Remove control characters except newlines/tabs if allowed
    if allow_newlines:
        # Allow newlines and tabs
        sanitized = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', user_input)
    else:
        # Remove all control characters including newlines
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', user_input)
    
    # Strip leading/trailing whitespace
    sanitized = sanitized.strip()
    
    return sanitized


def validate_file_path(
    file_path: str,
    base_dir: str,
    allowed_extensions: Optional[list[str]] = None
) -> Path:
    """
    Validate a file path for safe file operations.
    
    Args:
        file_path: The file path to validate
        base_dir: The base directory to restrict operations to
        allowed_extensions: Optional list of allowed file extensions
        
    Returns:
        The validated Path object
        
    Raises:
        PathTraversalError: If the path attempts traversal
        InvalidInputError: If the path is invalid
        
    Examples:
        >>> validate_file_path("images/photo.jpg", "/home/user/downloads", [".jpg", ".png"])
        PosixPath('/home/user/downloads/images/photo.jpg')
    """
    if not file_path or not isinstance(file_path, str):
        raise InvalidInputError("File path must be a non-empty string")
    
    if not base_dir or not isinstance(base_dir, str):
        raise InvalidInputError("Base directory must be a non-empty string")
    
    # Check if path is safe
    if not is_safe_path(file_path, base_dir):
        raise PathTraversalError(
            f"Path '{file_path}' is not safe or attempts traversal"
        )
    
    # Create full path
    base_path = Path(base_dir).resolve()
    full_path = (base_path / file_path).resolve()
    
    # Double-check it's within base_dir
    try:
        full_path.relative_to(base_path)
    except ValueError:
        raise PathTraversalError(
            f"Path '{file_path}' is outside base directory"
        )
    
    # Check file extension if restrictions apply
    if allowed_extensions:
        ext = full_path.suffix.lower()
        allowed_extensions = [e.lower() for e in allowed_extensions]
        if ext not in allowed_extensions:
            raise InvalidInputError(
                f"File extension '{ext}' not allowed. "
                f"Allowed: {', '.join(allowed_extensions)}"
            )
    
    return full_path


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a filename to be safe for filesystem operations.
    
    Args:
        filename: The filename to sanitize
        max_length: Maximum filename length (default: 255)
        
    Returns:
        The sanitized filename
        
    Raises:
        InvalidInputError: If filename is invalid
        
    Examples:
        >>> sanitize_filename("photo.jpg")
        'photo.jpg'
        >>> sanitize_filename("../../../etc/passwd")
        'etcpasswd'
        >>> sanitize_filename("file:with:colons.txt")
        'filewithcolons.txt'
    """
    if not filename or not isinstance(filename, str):
        raise InvalidInputError("Filename must be a non-empty string")
    
    # Remove path separators
    filename = filename.replace('/', '').replace('\\', '')
    
    # Remove or replace dangerous characters
    # Keep alphanumeric, dots, hyphens, underscores
    filename = re.sub(r'[^\w\s.-]', '', filename)
    
    # Remove leading/trailing periods and spaces
    filename = filename.strip('. ')
    
    # Replace multiple spaces with single space
    filename = re.sub(r'\s+', ' ', filename)
    
    # Truncate if too long (preserve extension)
    if len(filename) > max_length:
        name_part, ext = os.path.splitext(filename)
        max_name_length = max_length - len(ext)
        filename = name_part[:max_name_length] + ext
    
    if not filename:
        raise InvalidInputError("Filename is empty after sanitization")
    
    return filename
