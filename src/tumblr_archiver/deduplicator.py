"""File deduplication system to avoid downloading duplicate media."""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class FileDeduplicator:
    """Tracks checksums of downloaded files to detect and avoid duplicates.
    
    Maintains an in-memory mapping of checksums to file paths, with optional
    persistence to disk. This allows the system to:
    - Detect when a file has already been downloaded
    - Reuse existing files instead of downloading duplicates
    - Save bandwidth and storage space
    
    Example:
        ```python
        dedup = FileDeduplicator()
        
        # Add a downloaded file
        dedup.add_file("abc123...", "/path/to/image.jpg")
        
        # Check if another file is a duplicate
        if dedup.is_duplicate("abc123..."):
            existing = dedup.get_existing_file("abc123...")
            print(f"Duplicate! File already exists at {existing}")
        ```
    """
    
    def __init__(self, persistence_file: Optional[Path] = None):
        """Initialize the deduplicator.
        
        Args:
            persistence_file: Optional path to file for persisting checksum data.
                             If provided, checksums will be loaded on init and
                             saved after each add operation.
        """
        self._checksums: Dict[str, str] = {}
        self._persistence_file = persistence_file
        
        if self._persistence_file:
            self._load_from_disk()
        
        logger.info(
            f"Initialized FileDeduplicator "
            f"with {len(self._checksums)} existing checksums"
        )
    
    def is_duplicate(self, checksum: str) -> bool:
        """Check if a file with this checksum has already been tracked.
        
        Args:
            checksum: SHA256 checksum to check
            
        Returns:
            True if this checksum is already tracked, False otherwise
        """
        checksum = checksum.lower()
        return checksum in self._checksums
    
    def add_file(self, checksum: str, filepath: str) -> None:
        """Add a file to the deduplication tracker.
        
        Args:
            checksum: SHA256 checksum of the file
            filepath: Path where the file is stored
            
        Raises:
            ValueError: If checksum is not valid SHA256 format
        """
        checksum = checksum.lower()
        
        # Validate checksum format
        if len(checksum) != 64 or not all(c in '0123456789abcdef' for c in checksum):
            raise ValueError(f"Invalid SHA256 checksum format: {checksum}")
        
        self._checksums[checksum] = filepath
        logger.debug(f"Added file to deduplication tracker: {checksum} -> {filepath}")
        
        # Persist if configured
        if self._persistence_file:
            self._save_to_disk()
    
    def get_existing_file(self, checksum: str) -> Optional[str]:
        """Get the path to an existing file with this checksum.
        
        Args:
            checksum: SHA256 checksum to look up
            
        Returns:
            Path to the existing file, or None if not found
        """
        checksum = checksum.lower()
        filepath = self._checksums.get(checksum)
        
        if filepath:
            logger.debug(f"Found existing file for checksum {checksum}: {filepath}")
        
        return filepath
    
    def remove_file(self, checksum: str) -> bool:
        """Remove a file from the deduplication tracker.
        
        Useful when a file has been deleted or moved.
        
        Args:
            checksum: SHA256 checksum to remove
            
        Returns:
            True if the checksum was removed, False if it wasn't tracked
        """
        checksum = checksum.lower()
        
        if checksum in self._checksums:
            del self._checksums[checksum]
            logger.debug(f"Removed checksum from tracker: {checksum}")
            
            # Persist if configured
            if self._persistence_file:
                self._save_to_disk()
            
            return True
        
        return False
    
    def get_all_checksums(self) -> Dict[str, str]:
        """Get a copy of all tracked checksums and their file paths.
        
        Returns:
            Dictionary mapping checksums to file paths
        """
        return self._checksums.copy()
    
    def clear(self) -> None:
        """Clear all tracked checksums.
        
        This does not delete any files, only clears the in-memory tracker.
        """
        count = len(self._checksums)
        self._checksums.clear()
        logger.info(f"Cleared {count} checksums from tracker")
        
        # Persist if configured
        if self._persistence_file:
            self._save_to_disk()
    
    def _load_from_disk(self) -> None:
        """Load checksums from persistence file."""
        if not self._persistence_file or not self._persistence_file.exists():
            return
        
        try:
            with open(self._persistence_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self._checksums = data
            logger.info(
                f"Loaded {len(self._checksums)} checksums from {self._persistence_file}"
            )
            
        except Exception as e:
            logger.error(f"Failed to load checksums from disk: {e}")
            # Start with empty dict if we can't load
            self._checksums = {}
    
    def _save_to_disk(self) -> None:
        """Save checksums to persistence file."""
        if not self._persistence_file:
            return
        
        try:
            # Ensure parent directory exists
            self._persistence_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self._persistence_file, 'w', encoding='utf-8') as f:
                json.dump(self._checksums, f, indent=2)
            
            logger.debug(
                f"Saved {len(self._checksums)} checksums to {self._persistence_file}"
            )
            
        except Exception as e:
            logger.error(f"Failed to save checksums to disk: {e}")
    
    def __len__(self) -> int:
        """Return the number of tracked checksums."""
        return len(self._checksums)
    
    def __repr__(self) -> str:
        """String representation of the deduplicator."""
        return (
            f"FileDeduplicator(tracked={len(self._checksums)}, "
            f"persistence={'enabled' if self._persistence_file else 'disabled'})"
        )
