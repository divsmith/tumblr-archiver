"""
Wayback Machine / Internet Archive client for retrieving archived media.

This module provides a client for interacting with the Internet Archive's
Wayback Machine to check availability, retrieve snapshots, and download
archived media content.
"""

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Literal
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup


# Custom exceptions
class WaybackError(Exception):
    """Base exception for Wayback Machine errors."""
    pass


class SnapshotNotFoundError(WaybackError):
    """Raised when no snapshot is found for a URL."""
    pass


class RateLimitError(WaybackError):
    """Raised when rate limit is hit."""
    pass


@dataclass
class Snapshot:
    """Represents a Wayback Machine snapshot."""
    urlkey: str
    timestamp: str
    original_url: str
    mimetype: str
    status_code: str
    digest: str
    length: str
    
    @property
    def datetime(self) -> datetime:
        """Parse timestamp into datetime object."""
        return datetime.strptime(self.timestamp, "%Y%m%d%H%M%S")
    
    @property
    def replay_url(self) -> str:
        """Construct the replay URL for this snapshot."""
        return f"https://web.archive.org/web/{self.timestamp}id_/{self.original_url}"
    
    @property
    def file_size(self) -> int:
        """Get file size as integer (defaults to 0 if unavailable)."""
        try:
            return int(self.length) if self.length != "-" else 0
        except (ValueError, TypeError):
            return 0


class WaybackClient:
    """Client for interacting with the Internet Archive Wayback Machine.
    
    This client provides methods to:
    - Check if URLs have archived snapshots
    - Retrieve lists of available snapshots
    - Select the best snapshot based on quality criteria
    - Download archived media files
    - Extract media URLs from archived Tumblr posts
    
    Args:
        user_agent: Custom user agent string for requests.
        timeout: Request timeout in seconds (default: 30).
        max_retries: Maximum number of retries for failed requests (default: 3).
    """
    
    CDX_API_URL = "http://web.archive.org/cdx/search/cdx"
    AVAILABILITY_API_URL = "https://archive.org/wayback/available"
    REPLAY_BASE_URL = "https://web.archive.org/web"
    
    def __init__(
        self,
        user_agent: str = "TumblrArchiver/1.0",
        timeout: int = 30,
        max_retries: int = 3
    ):
        """Initialize the Wayback client."""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent
        })
        self.timeout = timeout
        self.max_retries = max_retries
    
    def check_availability(self, url: str) -> bool:
        """Check if a URL has any archived snapshots.
        
        Uses the Availability API for a quick check of the most recent snapshot.
        
        Args:
            url: The URL to check.
            
        Returns:
            True if at least one snapshot exists, False otherwise.
            
        Raises:
            WaybackError: If the API request fails.
        """
        try:
            params = {"url": url}
            response = self._make_request(
                self.AVAILABILITY_API_URL,
                params=params
            )
            data = response.json()
            
            # Check if archived_snapshots exists and has closest snapshot
            return bool(
                data.get("archived_snapshots", {})
                .get("closest", {})
                .get("available", False)
            )
        except requests.RequestException as e:
            raise WaybackError(f"Failed to check availability for {url}: {e}")
    
    def get_snapshots(
        self,
        url: str,
        limit: int = 5
    ) -> List[Snapshot]:
        """Get a list of available snapshots for a URL.
        
        Uses the CDX API to retrieve snapshot metadata. Results are sorted
        by timestamp with newest first.
        
        Args:
            url: The URL to query.
            limit: Maximum number of snapshots to return.
            
        Returns:
            List of Snapshot objects, sorted by timestamp (newest first).
            
        Raises:
            SnapshotNotFoundError: If no snapshots are found.
            WaybackError: If the API request fails.
        """
        try:
            params = {
                "url": url,
                "output": "json",
                "limit": limit,
                "fl": "urlkey,timestamp,original,mimetype,statuscode,digest,length"
            }
            
            response = self._make_request(
                self.CDX_API_URL,
                params=params
            )
            
            data = response.json()
            
            # First row is the header, rest are data rows
            if len(data) <= 1:
                raise SnapshotNotFoundError(f"No snapshots found for {url}")
            
            # Parse snapshots (skip header row)
            snapshots = []
            for row in data[1:]:
                if len(row) >= 7:
                    snapshot = Snapshot(
                        urlkey=row[0],
                        timestamp=row[1],
                        original_url=row[2],
                        mimetype=row[3],
                        status_code=row[4],
                        digest=row[5],
                        length=row[6]
                    )
                    snapshots.append(snapshot)
            
            # Sort by timestamp (newest first)
            snapshots.sort(key=lambda s: s.timestamp, reverse=True)
            
            return snapshots
            
        except SnapshotNotFoundError:
            raise
        except requests.RequestException as e:
            raise WaybackError(f"Failed to retrieve snapshots for {url}: {e}")
        except (KeyError, IndexError, ValueError) as e:
            raise WaybackError(f"Failed to parse CDX response: {e}")
    
    def get_best_snapshot(
        self,
        url: str,
        prefer: Literal["highest_quality", "most_recent"] = "highest_quality"
    ) -> Snapshot:
        """Select the best archived snapshot for a URL.
        
        For images and videos, prefers highest resolution or file size.
        For other content, returns the most recent snapshot.
        
        Args:
            url: The URL to query.
            prefer: Selection strategy - "highest_quality" (default) or "most_recent".
            
        Returns:
            The best Snapshot based on the preference criteria.
            
        Raises:
            SnapshotNotFoundError: If no snapshots are found.
            WaybackError: If the operation fails.
        """
        # Get more snapshots to have better selection
        snapshots = self.get_snapshots(url, limit=20)
        
        if not snapshots:
            raise SnapshotNotFoundError(f"No snapshots found for {url}")
        
        # Filter for successful responses (2xx status codes)
        successful_snapshots = [
            s for s in snapshots
            if s.status_code.startswith("2")
        ]
        
        if not successful_snapshots:
            # Fall back to any snapshot if no successful ones
            successful_snapshots = snapshots
        
        if prefer == "most_recent":
            return successful_snapshots[0]  # Already sorted newest first
        
        # For highest_quality, prefer largest file size
        # This works well for images and videos
        best_snapshot = max(
            successful_snapshots,
            key=lambda s: (s.file_size, s.timestamp)
        )
        
        return best_snapshot
    
    def download_from_snapshot(
        self,
        snapshot: Snapshot,
        output_path: Path
    ) -> None:
        """Download archived media from a snapshot.
        
        Constructs the proper replay URL with identity flag to get original
        content without Wayback Machine modifications.
        
        Args:
            snapshot: The Snapshot to download from.
            output_path: Path where the file should be saved.
            
        Raises:
            WaybackError: If the download fails.
        """
        # Use id_ flag to get original content without modifications
        replay_url = snapshot.replay_url
        
        try:
            response = self._make_request(
                replay_url,
                stream=True,
                allow_redirects=True
            )
            
            # Ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Download in chunks
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        
        except requests.RequestException as e:
            raise WaybackError(
                f"Failed to download from snapshot {replay_url}: {e}"
            )
        except OSError as e:
            raise WaybackError(
                f"Failed to write file to {output_path}: {e}"
            )
    
    def extract_media_from_archived_page(
        self,
        post_url: str,
        timestamp: Optional[str] = None
    ) -> List[str]:
        """Extract media URLs from an archived Tumblr post page.
        
        If the direct media URL is not in the archive, this method fetches
        the archived post page and parses it to extract media URLs.
        
        Args:
            post_url: The Tumblr post URL to retrieve.
            timestamp: Optional specific timestamp to use. If not provided,
                      uses the most recent snapshot.
            
        Returns:
            List of media URLs found in the archived page.
            
        Raises:
            SnapshotNotFoundError: If no snapshot of the page is found.
            WaybackError: If the operation fails.
        """
        try:
            # Get snapshot of the page
            if timestamp:
                # Use specific timestamp
                replay_url = f"{self.REPLAY_BASE_URL}/{timestamp}/{post_url}"
            else:
                # Get most recent snapshot
                snapshot = self.get_best_snapshot(post_url, prefer="most_recent")
                replay_url = f"{self.REPLAY_BASE_URL}/{snapshot.timestamp}/{post_url}"
            
            # Fetch the archived page
            response = self._make_request(replay_url)
            html_content = response.text
            
            # Parse HTML
            soup = BeautifulSoup(html_content, "html.parser")
            
            media_urls = []
            
            # Extract image URLs
            # Look for images in common Tumblr selectors
            for img in soup.find_all("img"):
                src = img.get("src")
                if src and self._is_tumblr_media_url(src):
                    # Convert archived URL to original if needed
                    original_url = self._extract_original_url(src)
                    if original_url:
                        media_urls.append(original_url)
            
            # Extract video URLs
            for video in soup.find_all("video"):
                src = video.get("src")
                if src and self._is_tumblr_media_url(src):
                    original_url = self._extract_original_url(src)
                    if original_url:
                        media_urls.append(original_url)
                
                # Check source tags within video
                for source in video.find_all("source"):
                    src = source.get("src")
                    if src and self._is_tumblr_media_url(src):
                        original_url = self._extract_original_url(src)
                        if original_url:
                            media_urls.append(original_url)
            
            # Look for meta tags with media URLs
            for meta in soup.find_all("meta", property=["og:image", "og:video"]):
                content = meta.get("content")
                if content and self._is_tumblr_media_url(content):
                    original_url = self._extract_original_url(content)
                    if original_url:
                        media_urls.append(original_url)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_media_urls = []
            for url in media_urls:
                if url not in seen:
                    seen.add(url)
                    unique_media_urls.append(url)
            
            return unique_media_urls
            
        except SnapshotNotFoundError:
            raise
        except requests.RequestException as e:
            raise WaybackError(
                f"Failed to fetch archived page for {post_url}: {e}"
            )
        except Exception as e:
            raise WaybackError(
                f"Failed to extract media from archived page: {e}"
            )
    
    def _is_tumblr_media_url(self, url: str) -> bool:
        """Check if a URL is a Tumblr media URL."""
        if not url:
            return False
        
        tumblr_domains = [
            "media.tumblr.com",
            "static.tumblr.com",
            "va.media.tumblr.com",
            "vtt.tumblr.com",
            "vt.tumblr.com"
        ]
        
        # Handle both direct URLs and archived URLs
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        
        return any(domain in hostname for domain in tumblr_domains)
    
    def _extract_original_url(self, url: str) -> Optional[str]:
        """Extract original URL from a Wayback Machine URL.
        
        Args:
            url: URL that may be a Wayback archived URL.
            
        Returns:
            Original URL if it's an archived URL, otherwise the input URL.
        """
        if not url:
            return None
        
        # Check if it's already a Wayback URL
        if "web.archive.org/web/" in url:
            # Extract original URL from Wayback format
            # Format: https://web.archive.org/web/TIMESTAMP/ORIGINAL_URL
            try:
                parts = url.split("web.archive.org/web/", 1)
                if len(parts) == 2:
                    # Remove timestamp and flags (like id_, if_)
                    after_archive = parts[1]
                    # Find the original URL after timestamp
                    tokens = after_archive.split("/", 1)
                    if len(tokens) == 2:
                        # tokens[0] is timestamp+flags, tokens[1] is original URL
                        return tokens[1]
            except Exception:
                pass
        
        # If it's not a Wayback URL or extraction failed, return as-is
        return url
    
    def _make_request(
        self,
        url: str,
        params: Optional[dict] = None,
        stream: bool = False,
        allow_redirects: bool = True
    ) -> requests.Response:
        """Make an HTTP request with retry logic and error handling.
        
        Args:
            url: URL to request.
            params: Optional query parameters.
            stream: Whether to stream the response.
            allow_redirects: Whether to follow redirects.
            
        Returns:
            Response object.
            
        Raises:
            RateLimitError: If rate limited (429 status).
            WaybackError: For other HTTP errors.
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout,
                    stream=stream,
                    allow_redirects=allow_redirects
                )
                
                # Check for rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    if attempt < self.max_retries - 1:
                        time.sleep(retry_after)
                        continue
                    raise RateLimitError(
                        f"Rate limited by Wayback Machine. Retry after {retry_after}s"
                    )
                
                # Raise for other HTTP errors
                response.raise_for_status()
                
                return response
                
            except requests.Timeout as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                    
            except requests.RequestException as e:
                last_exception = e
                # Don't retry for certain errors
                if isinstance(e, requests.HTTPError):
                    status_code = e.response.status_code if e.response else None
                    if status_code and status_code < 500:
                        # Client errors shouldn't be retried
                        raise
                
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
        
        # If we exhausted all retries
        raise WaybackError(
            f"Request failed after {self.max_retries} attempts: {last_exception}"
        )
