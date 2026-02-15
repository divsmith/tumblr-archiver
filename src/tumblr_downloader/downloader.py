"""Media downloader with parallel downloads and retry logic.

This module provides functionality to download media files from URLs
with support for parallel downloads, rate limiting, retry logic,
and comprehensive error handling.
"""

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class MediaDownloader:
    """Downloads media files with parallel processing and retry logic.
    
    Features:
    - Parallel downloads using ThreadPoolExecutor
    - Rate limiting to be respectful to servers
    - Automatic retry with exponential backoff
    - Idempotent (skips existing files)
    - Dry-run mode for testing
    - Progress tracking and detailed logging
    
    Attributes:
        output_dir: Directory where files will be saved.
        concurrency: Maximum number of parallel downloads.
        dry_run: If True, simulates downloads without actually downloading.
        rate_limiter: Rate limiter instance to control request rate.
        session: Requests session with retry configuration.
    """
    
    def __init__(
        self,
        output_dir: str,
        concurrency: int = 5,
        dry_run: bool = False,
        rate_limit: float = 2.0,
        max_retries: int = 3,
        timeout: int = 30
    ):
        """Initialize the media downloader.
        
        Args:
            output_dir: Directory where downloaded files will be saved.
            concurrency: Maximum number of parallel downloads (default: 5).
            dry_run: If True, simulate downloads without saving files (default: False).
            rate_limit: Maximum requests per second (default: 2.0).
            max_retries: Maximum number of retry attempts per file (default: 3).
            timeout: Request timeout in seconds (default: 30).
        
        Raises:
            ValueError: If concurrency is not positive or output_dir is invalid.
        """
        if concurrency <= 0:
            raise ValueError("concurrency must be positive")
        
        self.output_dir = Path(output_dir)
        self.concurrency = concurrency
        self.dry_run = dry_run
        self.max_retries = max_retries
        self.timeout = timeout
        
        # Create output directory if it doesn't exist
        if not dry_run:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize rate limiter
        self.rate_limiter = RateLimiter(max_per_second=rate_limit)
        
        # Configure requests session with retry logic
        self.session = self._create_session()
        
        logger.info(
            f"MediaDownloader initialized: output_dir={output_dir}, "
            f"concurrency={concurrency}, dry_run={dry_run}, "
            f"rate_limit={rate_limit}/s"
        )
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry configuration.
        
        Returns:
            Configured requests session with retry adapter.
        """
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,  # Exponential backoff: 0s, 1s, 2s, 4s...
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def download_media(self, media_items: List[Dict]) -> List[Dict]:
        """Download multiple media files in parallel.
        
        Args:
            media_items: List of media item dictionaries. Each dictionary should contain:
                - url: The URL of the media file
                - post_id: The post ID for naming
                - Additional metadata fields are preserved
        
        Returns:
            List of result dictionaries with download status and metadata:
                - success: Boolean indicating if download succeeded
                - filename: Name of the saved file (if successful)
                - filepath: Full path to the saved file (if successful)
                - bytes_downloaded: Number of bytes downloaded
                - error: Error message (if failed)
                - skipped: Boolean indicating if file was skipped (already exists)
                - All original fields from media_item
        """
        if not media_items:
            logger.warning("No media items to download")
            return []
        
        logger.info(f"Starting download of {len(media_items)} media items")
        start_time = time.time()
        
        results = []
        
        # Use ThreadPoolExecutor for parallel downloads
        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            # Submit all download tasks
            future_to_item = {
                executor.submit(self._download_single, item): item
                for item in media_items
            }
            
            # Process completed downloads
            for i, future in enumerate(as_completed(future_to_item), 1):
                item = future_to_item[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    # Log progress
                    status = "SUCCESS" if result["success"] else "FAILED"
                    if result.get("skipped"):
                        status = "SKIPPED"
                    
                    logger.info(
                        f"[{i}/{len(media_items)}] {status}: "
                        f"{result.get('filename', 'N/A')}"
                    )
                    
                except Exception as e:
                    logger.error(f"Unexpected error processing item: {e}")
                    results.append({
                        **item,
                        "success": False,
                        "error": str(e),
                        "bytes_downloaded": 0
                    })
        
        # Calculate statistics
        elapsed_time = time.time() - start_time
        successful = sum(1 for r in results if r["success"])
        failed = sum(1 for r in results if not r["success"] and not r.get("skipped"))
        skipped = sum(1 for r in results if r.get("skipped"))
        total_bytes = sum(r.get("bytes_downloaded", 0) for r in results)
        
        logger.info(
            f"Download complete: {successful} successful, {failed} failed, "
            f"{skipped} skipped | {total_bytes / 1024 / 1024:.2f} MB in "
            f"{elapsed_time:.2f}s"
        )
        
        return results
    
    def _download_single(self, media_item: Dict) -> Dict:
        """Download a single media file with retry logic.
        
        Args:
            media_item: Dictionary containing at minimum:
                - url: URL to download from
                - post_id: Post ID for filename generation
        
        Returns:
            Result dictionary with download status and metadata.
        """
        url = media_item.get("url")
        post_id = media_item.get("post_id", "unknown")
        
        if not url:
            logger.error(f"No URL provided for media item: {media_item}")
            return {
                **media_item,
                "success": False,
                "error": "No URL provided",
                "bytes_downloaded": 0
            }
        
        # Generate filename
        try:
            original_filename = self._extract_filename(url)
            filename = f"{post_id}_{original_filename}"
            filepath = self.output_dir / filename
        except Exception as e:
            logger.error(f"Error generating filename for {url}: {e}")
            return {
                **media_item,
                "success": False,
                "error": f"Invalid URL or filename: {e}",
                "bytes_downloaded": 0
            }
        
        # Check if file should be skipped (already exists)
        if self._should_skip(filepath):
            logger.debug(f"Skipping existing file: {filename}")
            return {
                **media_item,
                "success": True,
                "skipped": True,
                "filename": filename,
                "filepath": str(filepath),
                "bytes_downloaded": 0
            }
        
        # Dry-run mode: simulate download
        if self.dry_run:
            logger.info(f"[DRY RUN] Would download: {url} -> {filename}")
            return {
                **media_item,
                "success": True,
                "filename": filename,
                "filepath": str(filepath),
                "bytes_downloaded": 0,
                "dry_run": True
            }
        
        # Perform actual download with rate limiting and retry
        for attempt in range(self.max_retries + 1):
            try:
                # Rate limit the request
                self.rate_limiter.wait()
                
                # Download the file
                logger.debug(
                    f"Downloading {url} (attempt {attempt + 1}/{self.max_retries + 1})"
                )
                
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    stream=True
                )
                response.raise_for_status()
                
                # Write file to disk
                bytes_downloaded = 0
                with open(filepath, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            bytes_downloaded += len(chunk)
                
                logger.debug(
                    f"Successfully downloaded {filename} "
                    f"({bytes_downloaded / 1024:.2f} KB)"
                )
                
                return {
                    **media_item,
                    "success": True,
                    "filename": filename,
                    "filepath": str(filepath),
                    "bytes_downloaded": bytes_downloaded
                }
                
            except requests.exceptions.Timeout as e:
                logger.warning(
                    f"Timeout downloading {url} "
                    f"(attempt {attempt + 1}/{self.max_retries + 1}): {e}"
                )
                if attempt == self.max_retries:
                    return {
                        **media_item,
                        "success": False,
                        "error": f"Timeout after {self.max_retries + 1} attempts",
                        "bytes_downloaded": 0
                    }
                time.sleep(2 ** attempt)  # Exponential backoff
                
            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"Error downloading {url} "
                    f"(attempt {attempt + 1}/{self.max_retries + 1}): {e}"
                )
                if attempt == self.max_retries:
                    return {
                        **media_item,
                        "success": False,
                        "error": str(e),
                        "bytes_downloaded": 0
                    }
                time.sleep(2 ** attempt)  # Exponential backoff
                
            except Exception as e:
                logger.error(f"Unexpected error downloading {url}: {e}")
                return {
                    **media_item,
                    "success": False,
                    "error": f"Unexpected error: {e}",
                    "bytes_downloaded": 0
                }
        
        # This should never be reached, but just in case
        return {
            **media_item,
            "success": False,
            "error": "Unknown error",
            "bytes_downloaded": 0
        }
    
    def _extract_filename(self, url: str) -> str:
        """Extract filename from URL.
        
        Args:
            url: URL to extract filename from.
        
        Returns:
            Filename extracted from URL path.
        
        Raises:
            ValueError: If URL is invalid or has no filename.
        """
        parsed = urlparse(url)
        path = parsed.path
        
        if not path or path == "/":
            raise ValueError(f"No filename in URL: {url}")
        
        filename = os.path.basename(path)
        
        if not filename:
            raise ValueError(f"Could not extract filename from URL: {url}")
        
        return filename
    
    def _should_skip(self, filepath: Path) -> bool:
        """Check if a file should be skipped (already exists).
        
        Args:
            filepath: Path to check.
        
        Returns:
            True if file exists and should be skipped, False otherwise.
        """
        return filepath.exists() and filepath.stat().st_size > 0
    
    def close(self) -> None:
        """Close the downloader and clean up resources."""
        if self.session:
            self.session.close()
            logger.debug("Downloader session closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def __repr__(self) -> str:
        """Return a string representation of the downloader."""
        return (f"MediaDownloader(output_dir={self.output_dir}, "
                f"concurrency={self.concurrency}, dry_run={self.dry_run})")
