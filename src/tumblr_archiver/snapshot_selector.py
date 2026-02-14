"""Logic for selecting the best snapshot from Wayback Machine results."""

import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)


class SnapshotSelector:
    """Selects the best snapshot from a list of Wayback Machine snapshots.
    
    Uses a scoring algorithm to prefer:
    1. Successful HTTP responses (2xx status codes)
    2. Higher resolution media when detectable from URL patterns
    3. More recent captures as a tiebreaker
    4. Complete captures (not redirects)
    
    Filters out:
    - Error responses (4xx, 5xx status codes)
    - Redirects (3xx status codes)
    - Snapshots with missing or invalid status codes
    
    Example:
        ```python
        selector = SnapshotSelector()
        best = selector.select_best_snapshot(snapshots)
        if best:
            print(f"Best snapshot: {best.snapshot_url}")
        ```
    """
    
    # Regex patterns for detecting resolution in URLs
    RESOLUTION_PATTERNS = [
        re.compile(r'_(\d+)\.(jpg|jpeg|png|gif|webp)', re.IGNORECASE),  # _1280.jpg
        re.compile(r'(\d+)x(\d+)', re.IGNORECASE),  # 1920x1080
        re.compile(r'_s(\d+)', re.IGNORECASE),  # _s1280
    ]
    
    def __init__(self):
        """Initialize the snapshot selector."""
        logger.debug("Initialized SnapshotSelector")
    
    def select_best_snapshot(self, snapshots: List) -> Optional:
        """Select the best snapshot from a list of candidates.
        
        Args:
            snapshots: List of Snapshot objects to choose from
            
        Returns:
            The best Snapshot, or None if no suitable snapshots found
        """
        if not snapshots:
            logger.debug("No snapshots to select from")
            return None
        
        # Filter to only successful snapshots
        successful = [s for s in snapshots if self._is_valid_snapshot(s)]
        
        if not successful:
            logger.warning(f"No valid snapshots found among {len(snapshots)} candidates")
            return None
        
        logger.debug(f"Filtered to {len(successful)} valid snapshots from {len(snapshots)}")
        
        # Score and sort snapshots
        scored = [(self._score_snapshot(s), s) for s in successful]
        scored.sort(reverse=True, key=lambda x: x[0])
        
        best = scored[0][1]
        logger.info(
            f"Selected snapshot with score {scored[0][0]:.2f}: "
            f"timestamp={best.timestamp}, status={best.statuscode}"
        )
        
        return best
    
    def _is_valid_snapshot(self, snapshot) -> bool:
        """Check if a snapshot is valid for selection.
        
        Args:
            snapshot: Snapshot object to validate
            
        Returns:
            True if snapshot is valid, False otherwise
        """
        # Must have a valid status code
        status = snapshot.status
        if status == 0:
            return False
        
        # Must be a successful response (2xx)
        if not snapshot.is_successful():
            return False
        
        # Exclude common error indicators in MIME type
        if snapshot.mimetype in ['unk', 'warc/revisit', '-']:
            return False
        
        return True
    
    def _score_snapshot(self, snapshot) -> float:
        """Calculate a quality score for a snapshot.
        
        Higher scores indicate better quality. Scoring factors:
        - Base score for successful response
        - Bonus for detected resolution
        - Small bonus for recency
        
        Args:
            snapshot: Snapshot object to score
            
        Returns:
            Quality score (higher is better)
        """
        score = 0.0
        
        # Base score for HTTP 200 OK
        if snapshot.status == 200:
            score += 100.0
        # Lower score for other 2xx responses
        elif 200 <= snapshot.status < 300:
            score += 80.0
        
        # Bonus for higher resolution (if detectable)
        resolution = self._extract_resolution(snapshot.original_url)
        if resolution:
            # Normalize resolution to 0-20 range (common sizes: 75-2048)
            # Using log scale to prevent huge files from dominating
            import math
            score += min(20.0, math.log2(resolution / 100) * 5)
        
        # Small bonus for recency (0-10 points)
        # More recent snapshots get slightly higher scores
        try:
            # Convert timestamp to year (2000-2030 range)
            year = int(snapshot.timestamp[:4])
            # Scale: 2000 = 0 points, 2030 = 10 points
            recency_score = max(0, min(10, (year - 2000) / 3))
            score += recency_score
        except (ValueError, IndexError):
            pass
        
        # Bonus for better MIME types
        if snapshot.mimetype.startswith('image/'):
            score += 5.0
        elif snapshot.mimetype.startswith('video/'):
            score += 5.0
        elif snapshot.mimetype.startswith('application/'):
            score += 2.0
        
        return score
    
    def _extract_resolution(self, url: str) -> Optional[int]:
        """Extract resolution indicator from URL.
        
        Many Tumblr URLs contain resolution indicators like _1280.jpg or _500.jpg.
        This method attempts to extract the largest dimension.
        
        Args:
            url: URL to parse
            
        Returns:
            Resolution value (largest dimension) or None if not found
        """
        max_resolution = None
        
        for pattern in self.RESOLUTION_PATTERNS:
            matches = pattern.findall(url)
            for match in matches:
                try:
                    # Handle different pattern groups
                    if isinstance(match, tuple):
                        # For patterns like (\d+)x(\d+), take the max
                        values = [int(x) for x in match if x.isdigit()]
                        if values:
                            resolution = max(values)
                    else:
                        # For patterns like _(\d+)
                        resolution = int(match)
                    
                    if max_resolution is None or resolution > max_resolution:
                        max_resolution = resolution
                except (ValueError, TypeError):
                    continue
        
        if max_resolution:
            logger.debug(f"Extracted resolution {max_resolution} from URL: {url}")
        
        return max_resolution
