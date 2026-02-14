"""Checksum calculation and verification utilities for media files."""

import hashlib
import logging
from pathlib import Path
from typing import BinaryIO, Union

import aiofiles

logger = logging.getLogger(__name__)

# Buffer size for reading files in chunks
BUFFER_SIZE = 65536  # 64KB chunks


async def calculate_file_checksum(filepath: Union[str, Path]) -> str:
    """Calculate SHA256 checksum of a file asynchronously.
    
    Reads the file in chunks to handle large files efficiently without
    loading the entire file into memory.
    
    Args:
        filepath: Path to the file to checksum
        
    Returns:
        Hexadecimal SHA256 checksum string (64 characters)
        
    Raises:
        FileNotFoundError: If the file does not exist
        IOError: If there's an error reading the file
        
    Example:
        ```python
        checksum = await calculate_file_checksum("image.jpg")
        print(f"SHA256: {checksum}")
        ```
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    
    sha256 = hashlib.sha256()
    
    try:
        async with aiofiles.open(filepath, 'rb') as f:
            while True:
                data = await f.read(BUFFER_SIZE)
                if not data:
                    break
                sha256.update(data)
        
        checksum = sha256.hexdigest()
        logger.debug(f"Calculated checksum for {filepath}: {checksum}")
        return checksum
        
    except Exception as e:
        logger.error(f"Error calculating checksum for {filepath}: {e}")
        raise IOError(f"Failed to calculate checksum: {e}") from e


def calculate_stream_checksum(stream: BinaryIO) -> str:
    """Calculate SHA256 checksum of a binary stream synchronously.
    
    Reads the stream in chunks. The stream position will be at the end
    after this operation.
    
    Args:
        stream: Binary stream to checksum (file-like object)
        
    Returns:
        Hexadecimal SHA256 checksum string (64 characters)
        
    Raises:
        IOError: If there's an error reading the stream
        
    Example:
        ```python
        with open("image.jpg", "rb") as f:
            checksum = calculate_stream_checksum(f)
            print(f"SHA256: {checksum}")
        ```
    """
    sha256 = hashlib.sha256()
    
    try:
        while True:
            data = stream.read(BUFFER_SIZE)
            if not data:
                break
            sha256.update(data)
        
        checksum = sha256.hexdigest()
        logger.debug(f"Calculated stream checksum: {checksum}")
        return checksum
        
    except Exception as e:
        logger.error(f"Error calculating stream checksum: {e}")
        raise IOError(f"Failed to calculate stream checksum: {e}") from e


async def verify_checksum(filepath: Union[str, Path], expected_checksum: str) -> bool:
    """Verify that a file's checksum matches the expected value.
    
    Args:
        filepath: Path to the file to verify
        expected_checksum: Expected SHA256 checksum (64 hex characters)
        
    Returns:
        True if checksum matches, False otherwise
        
    Raises:
        FileNotFoundError: If the file does not exist
        IOError: If there's an error reading the file
        ValueError: If expected_checksum is not valid SHA256 format
        
    Example:
        ```python
        is_valid = await verify_checksum(
            "image.jpg",
            "a" * 64  # Example checksum
        )
        if is_valid:
            print("File integrity verified!")
        else:
            print("File corrupted or modified!")
        ```
    """
    # Validate expected checksum format
    expected_checksum = expected_checksum.lower()
    if len(expected_checksum) != 64 or not all(c in '0123456789abcdef' for c in expected_checksum):
        raise ValueError(f"Invalid SHA256 checksum format: {expected_checksum}")
    
    actual_checksum = await calculate_file_checksum(filepath)
    
    matches = actual_checksum == expected_checksum
    
    if matches:
        logger.debug(f"Checksum verified for {filepath}")
    else:
        logger.warning(
            f"Checksum mismatch for {filepath}: "
            f"expected {expected_checksum}, got {actual_checksum}"
        )
    
    return matches
