"""
Tumblr Archiver - Media archival tool with Internet Archive fallback.

A command-line tool for downloading and archiving media content from Tumblr blogs
with automatic fallback to Internet Archive for unavailable content.
"""

__version__ = "0.1.0"
__author__ = "Parker"
__license__ = "MIT"

# Import main components for convenient access
from .app import TumblrArchiver, run_archive_app
from .config import ArchiverConfig
from .exceptions import (
    ArchiverError,
    BlogNotFoundError,
    ConfigurationError,
    DownloadError,
    ManifestError,
    NetworkError,
    OrchestratorError,
    ScrapingError,
)
from .models import Manifest, MediaItem, Post
from .orchestrator import ArchiveStats, Orchestrator
from .queue import MediaQueue
from .worker import DownloadWorker

# Package-level exports
__all__ = [
    "__version__",
    "__author__",
    "__license__",
    # Main application
    "TumblrArchiver",
    "run_archive_app",
    # Configuration
    "ArchiverConfig",
    # Core components
    "Orchestrator",
    "ArchiveStats",
    "DownloadWorker",
    "MediaQueue",
    # Models
    "MediaItem",
    "Post",
    "Manifest",
    # Exceptions
    "ArchiverError",
    "ConfigurationError",
    "NetworkError",
    "ScrapingError",
    "BlogNotFoundError",
    "DownloadError",
    "ManifestError",
    "OrchestratorError",
]

