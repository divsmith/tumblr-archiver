"""
Tumblr Media Archiver - CLI tool for archiving Tumblr media content.
"""

__version__ = "0.1.0"
__author__ = "Parker"
__license__ = "MIT"

from tumblr_archiver.archiver import TumblrArchiver, ArchiveResult, ArchiveStatistics
from tumblr_archiver.cli import main

__all__ = [
    "main",
    "TumblrArchiver",
    "ArchiveResult",
    "ArchiveStatistics",
    "__version__",
]
