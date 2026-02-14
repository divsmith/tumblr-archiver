"""
Centralized exception hierarchy for the Tumblr archiver.

This module provides a unified exception hierarchy for all archiver errors,
making it easier to handle errors at different levels of granularity.
"""

from typing import Optional


class ArchiverError(Exception):
    """
    Base exception for all Tumblr archiver errors.
    
    All custom exceptions in the archiver inherit from this class,
    allowing for broad exception handling when needed.
    """
    
    def __init__(self, message: str, details: Optional[str] = None):
        """
        Initialize the exception.
        
        Args:
            message: Primary error message
            details: Additional details or context about the error
        """
        super().__init__(message)
        self.message = message
        self.details = details
    
    def __str__(self) -> str:
        """Return formatted error message."""
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class ConfigurationError(ArchiverError):
    """
    Raised when configuration validation fails.
    
    Examples:
        - Invalid blog name format
        - Negative concurrency value
        - Invalid output directory
    """
    pass


class NetworkError(ArchiverError):
    """
    Raised when network operations fail.
    
    Examples:
        - Connection timeout
        - DNS resolution failure
        - SSL/TLS errors
        - Rate limiting (HTTP 429)
    """
    
    def __init__(
        self,
        message: str,
        details: Optional[str] = None,
        status_code: Optional[int] = None,
        url: Optional[str] = None
    ):
        """
        Initialize network error.
        
        Args:
            message: Primary error message
            details: Additional details about the error
            status_code: HTTP status code if applicable
            url: URL that caused the error
        """
        super().__init__(message, details)
        self.status_code = status_code
        self.url = url
    
    def __str__(self) -> str:
        """Return formatted error message with status and URL."""
        parts = [self.message]
        
        if self.status_code:
            parts.append(f"(HTTP {self.status_code})")
        
        if self.url:
            parts.append(f"URL: {self.url}")
        
        if self.details:
            parts.append(f"- {self.details}")
        
        return " ".join(parts)


class ScrapingError(ArchiverError):
    """
    Raised when scraping operations fail.
    
    Examples:
        - Blog not found (404)
        - Blog is private or password-protected
        - HTML parsing failure
        - Unexpected page structure
    """
    
    def __init__(
        self,
        message: str,
        details: Optional[str] = None,
        blog_name: Optional[str] = None
    ):
        """
        Initialize scraping error.
        
        Args:
            message: Primary error message
            details: Additional details about the error
            blog_name: Name of the blog that caused the error
        """
        super().__init__(message, details)
        self.blog_name = blog_name
    
    def __str__(self) -> str:
        """Return formatted error message with blog name."""
        if self.blog_name:
            return f"{self.message} (blog: {self.blog_name})" + (
                f": {self.details}" if self.details else ""
            )
        return super().__str__()


class BlogNotFoundError(ScrapingError):
    """
    Raised when a Tumblr blog is not found (404).
    
    This is a specific type of scraping error indicating the blog
    does not exist or has been deleted.
    """
    
    def __init__(self, blog_name: str, details: Optional[str] = None):
        """
        Initialize blog not found error.
        
        Args:
            blog_name: Name of the blog that was not found
            details: Additional details about the error
        """
        super().__init__(
            f"Blog '{blog_name}' not found",
            details=details,
            blog_name=blog_name
        )


class DownloadError(ArchiverError):
    """
    Raised when media download operations fail.
    
    Examples:
        - Failed to download media file
        - Checksum mismatch after download
        - Disk write error
        - Invalid media URL
    """
    
    def __init__(
        self,
        message: str,
        details: Optional[str] = None,
        url: Optional[str] = None,
        filename: Optional[str] = None
    ):
        """
        Initialize download error.
        
        Args:
            message: Primary error message
            details: Additional details about the error
            url: URL of the media that failed to download
            filename: Target filename for the download
        """
        super().__init__(message, details)
        self.url = url
        self.filename = filename
    
    def __str__(self) -> str:
        """Return formatted error message with URL and filename."""
        parts = [self.message]
        
        if self.filename:
            parts.append(f"(file: {self.filename})")
        
        if self.url:
            parts.append(f"URL: {self.url}")
        
        if self.details:
            parts.append(f"- {self.details}")
        
        return " ".join(parts)


class ManifestError(ArchiverError):
    """
    Raised when manifest operations fail.
    
    Examples:
        - Failed to read manifest file
        - Invalid manifest format
        - Failed to write manifest
        - Manifest validation error
    """
    
    def __init__(
        self,
        message: str,
        details: Optional[str] = None,
        manifest_path: Optional[str] = None
    ):
        """
        Initialize manifest error.
        
        Args:
            message: Primary error message
            details: Additional details about the error
            manifest_path: Path to the manifest file that caused the error
        """
        super().__init__(message, details)
        self.manifest_path = manifest_path
    
    def __str__(self) -> str:
        """Return formatted error message with manifest path."""
        if self.manifest_path:
            return f"{self.message} (manifest: {self.manifest_path})" + (
                f": {self.details}" if self.details else ""
            )
        return super().__str__()


class OrchestratorError(ArchiverError):
    """
    Raised when the orchestrator encounters an error.
    
    This is typically a high-level error indicating that the
    overall archiving workflow has failed, possibly due to
    multiple underlying errors.
    """
    pass


# Backwards compatibility aliases for existing code
# These can be used to gradually migrate existing code to the new exception hierarchy

__all__ = [
    "ArchiverError",
    "ConfigurationError",
    "NetworkError",
    "ScrapingError",
    "BlogNotFoundError",
    "DownloadError",
    "ManifestError",
    "OrchestratorError",
]
