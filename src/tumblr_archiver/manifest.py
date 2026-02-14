"""
Manifest management system for tracking downloaded media and metadata.

This module provides the ManifestManager class and helper functions for:
- Tracking downloaded media files with checksums and metadata
- Resume support for interrupted downloads
- Deduplication across posts
- Atomic file operations to prevent corruption
"""

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Type aliases for clarity
MediaEntry = Dict[str, Any]
ManifestDict = Dict[str, Any]


class ManifestError(Exception):
    """Base exception for manifest-related errors."""

    pass


class ManifestValidationError(ManifestError):
    """Raised when manifest schema validation fails."""

    pass


class ManifestManager:
    """
    Manages the manifest.json file for tracking downloaded media and metadata.

    The manifest serves as the source of truth for archiving state and progress,
    enabling resume functionality and tracking provenance of all downloaded files.

    """

    # Required fields for the manifest root
    REQUIRED_ROOT_FIELDS = {
        "blog_url",
        "blog_name",
        "archive_date",
        "total_posts",
        "total_media",
        "media",
    }

    # Required fields for each media entry
    REQUIRED_MEDIA_FIELDS = {
        "post_id",
        "post_url",
        "timestamp",
        "media_type",
        "filename",
        "byte_size",
        "checksum",
        "original_url",
        "api_media_urls",
        "media_missing_on_tumblr",
        "retrieved_from",
        "archive_snapshot_url",
        "archive_snapshot_timestamp",
        "status",
        "notes",
    }

    # Valid status values
    VALID_STATUSES = {
        "pending",
        "downloading",
        "downloaded",
        "failed",
        "missing",
        "skipped",
        "verified",
    }

    # Valid retrieved_from values
    VALID_SOURCES = {"tumblr", "internet_archive", "external", "cached"}

    def __init__(self, manifest_path: str | Path):
        """
        Initialize the ManifestManager.

        Args:
            manifest_path: Path to the manifest.json file
        """
        self.manifest_path = Path(manifest_path)
        self.data: ManifestDict = {}
        self._modified = False

    def load(self) -> ManifestDict:
        """
        Load existing manifest or create a new one.

        If the manifest file exists, loads and validates it. If corrupted,
        creates a backup and initializes a new manifest. If file doesn't exist,
        initializes a new manifest structure.

        Returns:
            The loaded or newly created manifest data

        Raises:
            ManifestError: If manifest loading fails unrecoverably
        """
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)

                # Validate the loaded manifest
                validate_manifest(self.data)
                self._modified = False
                return self.data

            except (json.JSONDecodeError, ManifestValidationError) as e:
                # Backup corrupted manifest
                backup_path = self.manifest_path.with_suffix(".json.backup")
                backup_counter = 1
                while backup_path.exists():
                    backup_path = self.manifest_path.with_suffix(f".json.backup.{backup_counter}")
                    backup_counter += 1

                shutil.copy2(self.manifest_path, backup_path)
                print(f"Warning: Corrupted manifest backed up to {backup_path}")
                print(f"Error: {e}")
                print("Initializing new manifest...")

                # Initialize new manifest
                self._initialize_new_manifest()
                return self.data
        else:
            # Create new manifest
            self._initialize_new_manifest()
            return self.data

    def _initialize_new_manifest(self):
        """Initialize a new manifest structure with default values."""
        self.data = {
            "blog_url": "",
            "blog_name": "",
            "archive_date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_posts": 0,
            "total_media": 0,
            "media": [],
        }
        self._modified = True

    def save(self, force: bool = False) -> None:
        """
        Write manifest to disk using atomic write with temp file.

        Uses a temporary file and atomic rename to prevent corruption
        from interrupted writes.

        Args:
            force: If True, save even if not modified

        Raises:
            ManifestError: If save operation fails
        """
        if not self._modified and not force:
            return

        # Ensure parent directory exists
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temporary file first
        temp_path = self.manifest_path.with_suffix(".json.tmp")

        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())  # Ensure data is written to disk

            # Atomic rename
            shutil.move(str(temp_path), str(self.manifest_path))
            self._modified = False

        except Exception as e:
            # Clean up temp file if it exists
            if temp_path.exists():
                temp_path.unlink()
            raise ManifestError(f"Failed to save manifest: {e}") from e

    def add_media(self, media_dict: MediaEntry) -> None:
        """
        Add a new media entry to the manifest.

        Args:
            media_dict: Dictionary containing media entry data

        Raises:
            ManifestValidationError: If media_dict is missing required fields
        """
        # Validate media entry has all required fields
        missing_fields = self.REQUIRED_MEDIA_FIELDS - set(media_dict.keys())
        if missing_fields:
            raise ManifestValidationError(f"Media entry missing required fields: {missing_fields}")

        # Validate field types and values
        self._validate_media_entry(media_dict)

        # Add to media list
        self.data["media"].append(media_dict)
        self.data["total_media"] = len(self.data["media"])
        self._modified = True

    def update_media(self, post_id: str, filename: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing media entry.

        Args:
            post_id: The post ID of the media entry
            filename: The filename of the media entry
            updates: Dictionary of fields to update

        Returns:
            True if entry was found and updated, False otherwise
        """
        for entry in self.data["media"]:
            if entry["post_id"] == post_id and entry["filename"] == filename:
                entry.update(updates)
                self._modified = True
                return True
        return False

    def get_media(self, post_id: str, filename: str) -> Optional[MediaEntry]:
        """
        Retrieve a media entry by post_id and filename.

        Args:
            post_id: The post ID of the media entry
            filename: The filename of the media entry

        Returns:
            The media entry dictionary if found, None otherwise
        """
        for entry in self.data["media"]:
            if entry["post_id"] == post_id and entry["filename"] == filename:
                return entry
        return None

    def is_downloaded(
        self,
        post_id: str,
        filename: str,
        file_path: Optional[Path] = None,
        verify_checksum: bool = True,
    ) -> bool:
        """
        Check if media is already downloaded (for resume support).

        Checks if:
        1. Entry exists in manifest with status "downloaded" or "verified"
        2. File exists on disk (if file_path provided)
        3. Checksum matches (if verify_checksum=True and file_path provided)

        Args:
            post_id: The post ID of the media entry
            filename: The filename of the media entry
            file_path: Optional path to verify file existence and checksum
            verify_checksum: If True, verify file checksum matches manifest

        Returns:
            True if media is already downloaded and valid, False otherwise
        """
        entry = self.get_media(post_id, filename)
        if not entry:
            return False

        # Check status
        if entry["status"] not in ("downloaded", "verified"):
            return False

        # If file_path provided, verify file exists
        if file_path:
            if not file_path.exists():
                return False

            # Verify checksum if requested
            if verify_checksum and entry.get("checksum"):
                file_checksum = calculate_checksum(file_path)
                manifest_checksum = entry["checksum"]

                # Extract hash from "sha256:..." format if present
                if manifest_checksum.startswith("sha256:"):
                    manifest_checksum = manifest_checksum.split(":", 1)[1]

                if file_checksum != manifest_checksum:
                    return False

        return True

    def get_stats(self) -> Dict[str, Any]:
        """
        Return summary statistics about the archive.

        Returns:
            Dictionary containing statistics like total posts, media counts,
            status breakdown, unique checksums, etc.
        """
        media_list = self.data.get("media", [])

        # Count by status
        status_counts: Dict[str, int] = {}
        for entry in media_list:
            status = entry.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        # Count by media type
        type_counts: Dict[str, int] = {}
        for entry in media_list:
            media_type = entry.get("media_type", "unknown")
            type_counts[media_type] = type_counts.get(media_type, 0) + 1

        # Count by source
        source_counts: Dict[str, int] = {}
        for entry in media_list:
            source = entry.get("retrieved_from", "unknown")
            source_counts[source] = source_counts.get(source, 0) + 1

        # Calculate total bytes
        total_bytes = sum(entry.get("byte_size", 0) for entry in media_list)

        # Count unique checksums
        checksums = {entry.get("checksum") for entry in media_list if entry.get("checksum")}
        unique_media = len(checksums)

        # Count duplicate files (same checksum)
        checksum_counts: Dict[str, int] = {}
        for entry in media_list:
            checksum = entry.get("checksum")
            if checksum:
                checksum_counts[checksum] = checksum_counts.get(checksum, 0) + 1
        duplicates = sum(1 for count in checksum_counts.values() if count > 1)

        return {
            "blog_name": self.data.get("blog_name", ""),
            "blog_url": self.data.get("blog_url", ""),
            "archive_date": self.data.get("archive_date", ""),
            "total_posts": self.data.get("total_posts", 0),
            "total_media": len(media_list),
            "unique_media": unique_media,
            "duplicate_checksums": duplicates,
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / (1024 * 1024), 2),
            "status_breakdown": status_counts,
            "media_type_breakdown": type_counts,
            "source_breakdown": source_counts,
        }

    def mark_status(
        self, post_id: str, filename: str, status: str, notes: Optional[str] = None
    ) -> bool:
        """
        Update the download status of a media entry.

        Args:
            post_id: The post ID of the media entry
            filename: The filename of the media entry
            status: New status (must be in VALID_STATUSES)
            notes: Optional notes/error message

        Returns:
            True if entry was found and updated, False otherwise

        Raises:
            ValueError: If status is not valid
        """
        if status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Must be one of: {self.VALID_STATUSES}")

        updates = {"status": status}
        if notes is not None:
            updates["notes"] = notes

        return self.update_media(post_id, filename, updates)

    def deduplicate_media(self) -> List[Dict[str, Any]]:
        """
        Find media entries with duplicate checksums across posts.

        Returns:
            List of dictionaries containing duplicate groups:
            [
                {
                    "checksum": "sha256:abc...",
                    "entries": [entry1, entry2, ...],
                    "total_instances": 3,
                    "can_deduplicate": True
                },
                ...
            ]
        """
        checksum_map: Dict[str, List[MediaEntry]] = {}

        # Group entries by checksum
        for entry in self.data["media"]:
            checksum = entry.get("checksum")
            if checksum and checksum != "":
                if checksum not in checksum_map:
                    checksum_map[checksum] = []
                checksum_map[checksum].append(entry)

        # Find duplicates (more than one entry with same checksum)
        duplicates = []
        for checksum, entries in checksum_map.items():
            if len(entries) > 1:
                duplicates.append(
                    {
                        "checksum": checksum,
                        "entries": entries,
                        "total_instances": len(entries),
                        "can_deduplicate": all(e.get("status") == "downloaded" for e in entries),
                        "byte_size": entries[0].get("byte_size", 0),
                        "media_type": entries[0].get("media_type", "unknown"),
                    }
                )

        # Sort by number of instances (most duplicated first)
        duplicates.sort(key=lambda x: x["total_instances"], reverse=True)

        return duplicates

    def set_blog_info(
        self, blog_url: str, blog_name: str, total_posts: Optional[int] = None
    ) -> None:
        """
        Set or update blog information in the manifest.

        Args:
            blog_url: The blog's URL
            blog_name: The blog's name
            total_posts: Optional total number of posts
        """
        self.data["blog_url"] = blog_url
        self.data["blog_name"] = blog_name
        if total_posts is not None:
            self.data["total_posts"] = total_posts
        self._modified = True

    def _validate_media_entry(self, entry: MediaEntry) -> None:
        """
        Validate a media entry's field types and values.

        Args:
            entry: The media entry to validate

        Raises:
            ManifestValidationError: If validation fails
        """
        # Validate status
        if entry.get("status") not in self.VALID_STATUSES:
            raise ManifestValidationError(f"Invalid status: {entry.get('status')}")

        # Validate retrieved_from
        if entry.get("retrieved_from") not in self.VALID_SOURCES:
            raise ManifestValidationError(f"Invalid retrieved_from: {entry.get('retrieved_from')}")

        # Validate types
        if not isinstance(entry.get("post_id"), str):
            raise ManifestValidationError("post_id must be a string")

        if not isinstance(entry.get("byte_size"), int):
            raise ManifestValidationError("byte_size must be an integer")

        if not isinstance(entry.get("api_media_urls"), list):
            raise ManifestValidationError("api_media_urls must be a list")

        if not isinstance(entry.get("media_missing_on_tumblr"), bool):
            raise ManifestValidationError("media_missing_on_tumblr must be a boolean")


# Helper functions


def calculate_checksum(file_path: str | Path) -> str:
    """
    Compute SHA256 hash of a file.

    Args:
        file_path: Path to the file

    Returns:
        Hexadecimal SHA256 hash string (without "sha256:" prefix)

    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If file cannot be read
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    sha256_hash = hashlib.sha256()

    # Read file in chunks to handle large files efficiently
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)

    return sha256_hash.hexdigest()


def validate_manifest(manifest_dict: ManifestDict) -> None:
    """
    Validate manifest schema compliance.

    Args:
        manifest_dict: The manifest dictionary to validate

    Raises:
        ManifestValidationError: If validation fails
    """
    if not isinstance(manifest_dict, dict):
        raise ManifestValidationError("Manifest must be a dictionary")

    # Check required root fields
    missing_fields = ManifestManager.REQUIRED_ROOT_FIELDS - set(manifest_dict.keys())
    if missing_fields:
        raise ManifestValidationError(f"Manifest missing required fields: {missing_fields}")

    # Validate root field types
    if not isinstance(manifest_dict.get("blog_url"), str):
        raise ManifestValidationError("blog_url must be a string")

    if not isinstance(manifest_dict.get("blog_name"), str):
        raise ManifestValidationError("blog_name must be a string")

    if not isinstance(manifest_dict.get("archive_date"), str):
        raise ManifestValidationError("archive_date must be a string")

    if not isinstance(manifest_dict.get("total_posts"), int):
        raise ManifestValidationError("total_posts must be an integer")

    if not isinstance(manifest_dict.get("total_media"), int):
        raise ManifestValidationError("total_media must be an integer")

    if not isinstance(manifest_dict.get("media"), list):
        raise ManifestValidationError("media must be a list")

    # Validate each media entry has required fields
    for idx, entry in enumerate(manifest_dict.get("media", [])):
        if not isinstance(entry, dict):
            raise ManifestValidationError(f"Media entry {idx} must be a dictionary")

        missing_media_fields = ManifestManager.REQUIRED_MEDIA_FIELDS - set(entry.keys())
        if missing_media_fields:
            raise ManifestValidationError(
                f"Media entry {idx} missing required fields: {missing_media_fields}"
            )


def create_media_entry(
    post_id: str,
    post_url: str,
    timestamp: str,
    media_type: str,
    filename: str,
    original_url: str,
    api_media_urls: List[str],
    byte_size: int = 0,
    checksum: str = "",
    media_missing_on_tumblr: bool = False,
    retrieved_from: str = "tumblr",
    archive_snapshot_url: Optional[str] = None,
    archive_snapshot_timestamp: Optional[str] = None,
    status: str = "pending",
    notes: Optional[str] = None,
) -> MediaEntry:
    """
    Create a properly formatted media entry dictionary.

    This is a convenience function to ensure all required fields are present
    with correct types.

    Args:
        post_id: Tumblr post ID
        post_url: URL of the post
        timestamp: ISO 8601 timestamp of the post
        media_type: Type of media (image, video, audio, etc.)
        filename: Name of the downloaded file
        original_url: Original Tumblr CDN URL
        api_media_urls: List of URLs from API response
        byte_size: Size of file in bytes (0 if unknown)
        checksum: SHA256 checksum (with or without "sha256:" prefix)
        media_missing_on_tumblr: Whether media is missing from Tumblr
        retrieved_from: Source of the media (tumblr, internet_archive, etc.)
        archive_snapshot_url: Internet Archive snapshot URL if applicable
        archive_snapshot_timestamp: Timestamp of archive snapshot
        status: Download status (pending, downloaded, etc.)
        notes: Optional notes or error messages

    Returns:
        A properly formatted media entry dictionary
    """
    # Ensure checksum has proper format
    if checksum and not checksum.startswith("sha256:"):
        checksum = f"sha256:{checksum}"

    return {
        "post_id": str(post_id),
        "post_url": post_url,
        "timestamp": timestamp,
        "media_type": media_type,
        "filename": filename,
        "byte_size": byte_size,
        "checksum": checksum,
        "original_url": original_url,
        "api_media_urls": api_media_urls,
        "media_missing_on_tumblr": media_missing_on_tumblr,
        "retrieved_from": retrieved_from,
        "archive_snapshot_url": archive_snapshot_url,
        "archive_snapshot_timestamp": archive_snapshot_timestamp,
        "status": status,
        "notes": notes,
    }
