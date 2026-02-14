"""Internet Archive Wayback Machine client for retrieving archived media."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from .constants import WAYBACK_CDX_API_URL, WAYBACK_SNAPSHOT_URL_TEMPLATE
from .http_client import AsyncHTTPClient, HTTPError

logger = logging.getLogger(__name__)


@dataclass
class Snapshot:
    """Represents a Wayback Machine snapshot of a URL.
    
    Attributes:
        timestamp: Snapshot timestamp in format YYYYMMDDhhmmss
        statuscode: HTTP status code of the archived response
        mimetype: MIME type of the archived content
        original_url: Original URL that was archived
        snapshot_url: Full URL to access the archived snapshot
    """
    
    timestamp: str
    statuscode: str
    mimetype: str
    original_url: str
    snapshot_url: str
    
    @property
    def datetime(self) -> datetime:
        """Convert timestamp to datetime object.
        
        Returns:
            Datetime representation of the snapshot timestamp
        """
        return datetime.strptime(self.timestamp, "%Y%m%d%H%M%S")
    
    @property
    def status(self) -> int:
        """Get status code as integer.
        
        Returns:
            HTTP status code as integer
        """
        try:
            return int(self.statuscode)
        except (ValueError, TypeError):
            return 0
    
    def is_successful(self) -> bool:
        """Check if snapshot represents a successful capture.
        
        Returns:
            True if status code indicates success (2xx)
        """
        return 200 <= self.status < 300


class WaybackClient:
    """Client for interacting with the Internet Archive Wayback Machine.
    
    Provides methods to search for, select, and download archived snapshots
    of URLs from the Wayback Machine's CDX API.
    
    Example:
        ```python
        async with AsyncHTTPClient() as http_client:
            wayback = WaybackClient(http_client)
            
            # Find all snapshots of a URL
            snapshots = await wayback.find_snapshots(
                "https://example.com/image.jpg",
                from_date="20200101",
                to_date="20231231"
            )
            
            # Get the best available snapshot
            best = await wayback.get_best_snapshot("https://example.com/image.jpg")
            if best:
                # Download from snapshot
                content = await wayback.download_from_snapshot(best.snapshot_url)
        ```
    """
    
    def __init__(self, http_client: AsyncHTTPClient):
        """Initialize the Wayback Machine client.
        
        Args:
            http_client: Async HTTP client for making requests
        """
        self.http_client = http_client
        logger.info("Initialized WaybackClient")
    
    async def find_snapshots(
        self,
        url: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Snapshot]:
        """Find all snapshots of a URL in the Wayback Machine.
        
        Queries the CDX API to retrieve metadata about all archived snapshots
        of the given URL within the specified date range.
        
        Args:
            url: URL to search for in the archive
            from_date: Start date in format YYYYMMDD or YYYYMMDDhhmmss (optional)
            to_date: End date in format YYYYMMDD or YYYYMMDDhhmmss (optional)
            limit: Maximum number of results to return (optional)
            
        Returns:
            List of Snapshot objects, ordered by timestamp (newest first typically)
            
        Raises:
            HTTPError: If the CDX API request fails
        """
        params = {
            'url': url,
            'output': 'json',
            'fl': 'timestamp,statuscode,mimetype,original',
        }
        
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        if limit:
            params['limit'] = str(limit)
        
        logger.debug(f"Querying CDX API for snapshots of {url}")
        
        try:
            response = await self.http_client.get(WAYBACK_CDX_API_URL, params=params)
            data = await response.json()
            
            # CDX API returns JSON array where first row is headers
            if not data or len(data) < 2:
                logger.info(f"No snapshots found for {url}")
                return []
            
            # Skip the header row and parse snapshots
            snapshots = []
            for row in data[1:]:
                if len(row) >= 4:
                    timestamp, statuscode, mimetype, original = row[:4]
                    
                    # Build snapshot URL
                    snapshot_url = WAYBACK_SNAPSHOT_URL_TEMPLATE.format(
                        timestamp=timestamp,
                        url=original
                    )
                    
                    snapshot = Snapshot(
                        timestamp=timestamp,
                        statuscode=statuscode,
                        mimetype=mimetype,
                        original_url=original,
                        snapshot_url=snapshot_url,
                    )
                    snapshots.append(snapshot)
            
            logger.info(f"Found {len(snapshots)} snapshots for {url}")
            return snapshots
            
        except HTTPError as e:
            logger.error(f"Failed to query CDX API for {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error querying CDX API for {url}: {e}")
            return []
    
    async def get_best_snapshot(
        self,
        url: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> Optional[Snapshot]:
        """Find the best available snapshot of a URL.
        
        Queries the CDX API and uses the SnapshotSelector to choose the
        highest quality snapshot available.
        
        Args:
            url: URL to search for in the archive
            from_date: Start date in format YYYYMMDD or YYYYMMDDhhmmss (optional)
            to_date: End date in format YYYYMMDD or YYYYMMDDhhmmss (optional)
            
        Returns:
            Best Snapshot object, or None if no good snapshots found
            
        Raises:
            HTTPError: If the CDX API request fails
        """
        from .snapshot_selector import SnapshotSelector
        
        snapshots = await self.find_snapshots(url, from_date, to_date)
        
        if not snapshots:
            logger.warning(f"No snapshots available for {url}")
            return None
        
        selector = SnapshotSelector()
        best = selector.select_best_snapshot(snapshots)
        
        if best:
            logger.info(
                f"Selected best snapshot for {url}: "
                f"timestamp={best.timestamp}, status={best.statuscode}"
            )
        else:
            logger.warning(f"No suitable snapshot found for {url}")
        
        return best
    
    async def download_from_snapshot(self, snapshot_url: str) -> bytes:
        """Download content from a Wayback Machine snapshot.
        
        Args:
            snapshot_url: Full URL to the archived snapshot
            
        Returns:
            Raw bytes of the archived content
            
        Raises:
            HTTPError: If the download fails
        """
        logger.debug(f"Downloading from snapshot: {snapshot_url}")
        
        try:
            response = await self.http_client.get(snapshot_url)
            content = await response.read()
            
            logger.info(f"Downloaded {len(content)} bytes from snapshot")
            return content
            
        except HTTPError as e:
            logger.error(f"Failed to download from snapshot {snapshot_url}: {e}")
            raise
