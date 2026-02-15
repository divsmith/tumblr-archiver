"""
Entry point for running tumblr_downloader as a module.

This allows the package to be executed directly using:
    python -m tumblr_downloader --blog myblog --out ./downloads
"""

import sys
from .cli import main

if __name__ == '__main__':
    sys.exit(main())
