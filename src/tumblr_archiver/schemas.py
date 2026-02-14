"""
JSON schema validation and versioning for Tumblr archiver manifests.

This module provides schema validation helpers, version constants,
and utilities for maintaining manifest format consistency.
"""

from typing import Any, Dict

from pydantic import ValidationError

from .models import Manifest

# Schema version for manifest files
# Increment when making breaking changes to the data model
MANIFEST_SCHEMA_VERSION = "1.0.0"


def get_manifest_schema() -> Dict[str, Any]:
    """
    Get the JSON schema for the Manifest model.
    
    Returns:
        Dictionary containing the JSON schema specification
    """
    return Manifest.model_json_schema()


def validate_manifest_dict(data: Dict[str, Any]) -> tuple[bool, str]:
    """
    Validate a dictionary against the Manifest schema.
    
    Args:
        data: Dictionary to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if validation passed, False otherwise
        - error_message: Empty string if valid, error details if invalid
    """
    try:
        Manifest.model_validate(data)
        return True, ""
    except ValidationError as e:
        return False, str(e)


def validate_manifest_json(json_str: str) -> tuple[bool, str]:
    """
    Validate a JSON string against the Manifest schema.
    
    Args:
        json_str: JSON string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if validation passed, False otherwise
        - error_message: Empty string if valid, error details if invalid
    """
    try:
        Manifest.model_validate_json(json_str)
        return True, ""
    except ValidationError as e:
        return False, str(e)
    except Exception as e:
        return False, f"JSON parsing error: {str(e)}"


def add_schema_version(manifest_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add schema version metadata to a manifest dictionary.
    
    Args:
        manifest_dict: Manifest data as dictionary
        
    Returns:
        Dictionary with added schema_version field
    """
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        **manifest_dict
    }


def check_schema_version(manifest_dict: Dict[str, Any]) -> tuple[bool, str]:
    """
    Check if a manifest dictionary has a compatible schema version.
    
    Args:
        manifest_dict: Manifest data with potential schema_version field
        
    Returns:
        Tuple of (is_compatible, message)
        - is_compatible: True if version is compatible or missing
        - message: Warning or error message
    """
    if "schema_version" not in manifest_dict:
        return True, "No schema version found (assumed compatible)"
    
    version = manifest_dict["schema_version"]
    
    # Simple version comparison (works for semantic versioning)
    major_current = MANIFEST_SCHEMA_VERSION.split(".")[0]
    major_manifest = version.split(".")[0]
    
    if major_current != major_manifest:
        return False, (
            f"Incompatible schema version: manifest is {version}, "
            f"but current version is {MANIFEST_SCHEMA_VERSION}"
        )
    
    if version != MANIFEST_SCHEMA_VERSION:
        return True, (
            f"Schema version mismatch: manifest is {version}, "
            f"current is {MANIFEST_SCHEMA_VERSION}, but compatible"
        )
    
    return True, f"Schema version {version} matches"


def export_schema_to_file(filepath: str) -> None:
    """
    Export the Manifest JSON schema to a file.
    
    Useful for documentation and external validation tools.
    
    Args:
        filepath: Path where the schema JSON file should be written
    """
    import json
    
    schema = get_manifest_schema()
    schema_with_version = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "version": MANIFEST_SCHEMA_VERSION,
        **schema
    }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(schema_with_version, f, indent=2)


def validate_media_item_fields(media_dict: Dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validate individual media item fields for common errors.
    
    Performs additional validation beyond Pydantic's built-in checks.
    
    Args:
        media_dict: Dictionary representing a MediaItem
        
    Returns:
        Tuple of (is_valid, list_of_warnings)
    """
    warnings = []
    
    # Check for suspicious file sizes
    if media_dict.get("byte_size") is not None:
        size = media_dict["byte_size"]
        if size == 0:
            warnings.append("File size is 0 bytes - file may be corrupted")
        elif size < 100:
            warnings.append("File size is unusually small (< 100 bytes)")
        elif size > 100 * 1024 * 1024:  # 100 MB
            warnings.append("File size is unusually large (> 100 MB)")
    
    # Check status consistency
    status = media_dict.get("status")
    checksum = media_dict.get("checksum")
    byte_size = media_dict.get("byte_size")
    
    if status == "downloaded" and not checksum:
        warnings.append("Downloaded file should have a checksum")
    
    if status == "downloaded" and byte_size is None:
        warnings.append("Downloaded file should have byte_size")
    
    if status in ["missing", "error"] and checksum:
        warnings.append(f"Status is '{status}' but checksum exists")
    
    # Check archive URL consistency
    retrieved_from = media_dict.get("retrieved_from")
    archive_url = media_dict.get("archive_snapshot_url")
    
    if retrieved_from == "tumblr" and archive_url:
        warnings.append("Retrieved from Tumblr but has archive_snapshot_url")
    
    is_valid = len(warnings) == 0
    return is_valid, warnings
