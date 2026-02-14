"""Tests for checksum calculation and verification."""

import hashlib
import io
from pathlib import Path

import pytest

from tumblr_archiver.checksum import (
    calculate_file_checksum,
    calculate_stream_checksum,
    verify_checksum,
)


@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary test file."""
    test_file = tmp_path / "test_file.txt"
    test_content = b"Hello, World! This is a test file for checksum calculation."
    test_file.write_bytes(test_content)
    
    # Calculate expected checksum
    expected_checksum = hashlib.sha256(test_content).hexdigest()
    
    return test_file, expected_checksum


@pytest.fixture
def large_temp_file(tmp_path):
    """Create a large temporary test file to test chunked reading."""
    test_file = tmp_path / "large_file.bin"
    
    # Create a 1MB file
    test_content = b"A" * (1024 * 1024)
    test_file.write_bytes(test_content)
    
    # Calculate expected checksum
    expected_checksum = hashlib.sha256(test_content).hexdigest()
    
    return test_file, expected_checksum


@pytest.mark.asyncio
async def test_calculate_file_checksum(temp_file):
    """Test calculating checksum of a file."""
    test_file, expected_checksum = temp_file
    
    checksum = await calculate_file_checksum(test_file)
    
    assert checksum == expected_checksum
    assert len(checksum) == 64
    assert all(c in '0123456789abcdef' for c in checksum)


@pytest.mark.asyncio
async def test_calculate_file_checksum_large_file(large_temp_file):
    """Test calculating checksum of a large file (tests chunked reading)."""
    test_file, expected_checksum = large_temp_file
    
    checksum = await calculate_file_checksum(test_file)
    
    assert checksum == expected_checksum
    assert len(checksum) == 64


@pytest.mark.asyncio
async def test_calculate_file_checksum_nonexistent_file(tmp_path):
    """Test calculating checksum of a non-existent file."""
    nonexistent_file = tmp_path / "does_not_exist.txt"
    
    with pytest.raises(FileNotFoundError):
        await calculate_file_checksum(nonexistent_file)


@pytest.mark.asyncio
async def test_calculate_file_checksum_empty_file(tmp_path):
    """Test calculating checksum of an empty file."""
    empty_file = tmp_path / "empty.txt"
    empty_file.write_bytes(b"")
    
    checksum = await calculate_file_checksum(empty_file)
    
    # SHA256 of empty string
    expected = hashlib.sha256(b"").hexdigest()
    assert checksum == expected


def test_calculate_stream_checksum():
    """Test calculating checksum of a binary stream."""
    test_content = b"Hello, World! This is a test stream."
    stream = io.BytesIO(test_content)
    
    checksum = calculate_stream_checksum(stream)
    
    expected_checksum = hashlib.sha256(test_content).hexdigest()
    assert checksum == expected_checksum
    assert len(checksum) == 64
    assert all(c in '0123456789abcdef' for c in checksum)


def test_calculate_stream_checksum_large():
    """Test calculating checksum of a large stream."""
    # Create a 1MB stream
    test_content = b"B" * (1024 * 1024)
    stream = io.BytesIO(test_content)
    
    checksum = calculate_stream_checksum(stream)
    
    expected_checksum = hashlib.sha256(test_content).hexdigest()
    assert checksum == expected_checksum


def test_calculate_stream_checksum_empty():
    """Test calculating checksum of an empty stream."""
    stream = io.BytesIO(b"")
    
    checksum = calculate_stream_checksum(stream)
    
    expected = hashlib.sha256(b"").hexdigest()
    assert checksum == expected


def test_calculate_stream_checksum_position():
    """Test that stream position is at end after checksum calculation."""
    test_content = b"Test content"
    stream = io.BytesIO(test_content)
    
    calculate_stream_checksum(stream)
    
    # Stream should be at end
    assert stream.tell() == len(test_content)


@pytest.mark.asyncio
async def test_verify_checksum_valid(temp_file):
    """Test verifying a valid checksum."""
    test_file, expected_checksum = temp_file
    
    is_valid = await verify_checksum(test_file, expected_checksum)
    
    assert is_valid is True


@pytest.mark.asyncio
async def test_verify_checksum_invalid(temp_file):
    """Test verifying an invalid checksum."""
    test_file, _ = temp_file
    
    # Use a different checksum
    wrong_checksum = "a" * 64
    
    is_valid = await verify_checksum(test_file, wrong_checksum)
    
    assert is_valid is False


@pytest.mark.asyncio
async def test_verify_checksum_case_insensitive(temp_file):
    """Test that checksum verification is case-insensitive."""
    test_file, expected_checksum = temp_file
    
    # Test with uppercase
    is_valid = await verify_checksum(test_file, expected_checksum.upper())
    
    assert is_valid is True


@pytest.mark.asyncio
async def test_verify_checksum_invalid_format(temp_file):
    """Test verifying with invalid checksum format."""
    test_file, _ = temp_file
    
    # Test with invalid length
    with pytest.raises(ValueError, match="Invalid SHA256 checksum format"):
        await verify_checksum(test_file, "abc123")
    
    # Test with invalid characters
    with pytest.raises(ValueError, match="Invalid SHA256 checksum format"):
        await verify_checksum(test_file, "g" * 64)


@pytest.mark.asyncio
async def test_verify_checksum_nonexistent_file(tmp_path):
    """Test verifying checksum of non-existent file."""
    nonexistent_file = tmp_path / "does_not_exist.txt"
    
    with pytest.raises(FileNotFoundError):
        await verify_checksum(nonexistent_file, "a" * 64)


@pytest.mark.asyncio
async def test_calculate_file_checksum_with_path_object(temp_file):
    """Test that Path objects are handled correctly."""
    test_file, expected_checksum = temp_file
    
    # Ensure test_file is a Path object
    assert isinstance(test_file, Path)
    
    checksum = await calculate_file_checksum(test_file)
    
    assert checksum == expected_checksum


@pytest.mark.asyncio
async def test_calculate_file_checksum_with_string_path(temp_file):
    """Test that string paths are handled correctly."""
    test_file, expected_checksum = temp_file
    
    # Convert to string
    test_file_str = str(test_file)
    
    checksum = await calculate_file_checksum(test_file_str)
    
    assert checksum == expected_checksum


def test_calculate_stream_checksum_file_object(temp_file):
    """Test calculating checksum from a file object."""
    test_file, expected_checksum = temp_file
    
    with open(test_file, 'rb') as f:
        checksum = calculate_stream_checksum(f)
    
    assert checksum == expected_checksum


@pytest.mark.asyncio
async def test_multiple_files_same_content(tmp_path):
    """Test that files with same content have same checksum."""
    content = b"Same content"
    
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    
    file1.write_bytes(content)
    file2.write_bytes(content)
    
    checksum1 = await calculate_file_checksum(file1)
    checksum2 = await calculate_file_checksum(file2)
    
    assert checksum1 == checksum2


@pytest.mark.asyncio
async def test_different_content_different_checksum(tmp_path):
    """Test that files with different content have different checksums."""
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    
    file1.write_bytes(b"Content 1")
    file2.write_bytes(b"Content 2")
    
    checksum1 = await calculate_file_checksum(file1)
    checksum2 = await calculate_file_checksum(file2)
    
    assert checksum1 != checksum2
