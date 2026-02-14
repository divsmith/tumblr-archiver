"""Tests for file deduplicator."""

import json
from pathlib import Path

import pytest

from tumblr_archiver.deduplicator import FileDeduplicator


@pytest.fixture
def deduplicator():
    """Create a deduplicator instance."""
    return FileDeduplicator()


@pytest.fixture
def deduplicator_with_persistence(tmp_path):
    """Create a deduplicator instance with persistence."""
    persistence_file = tmp_path / "checksums.json"
    return FileDeduplicator(persistence_file=persistence_file), persistence_file


def test_initialization():
    """Test deduplicator initialization."""
    dedup = FileDeduplicator()
    
    assert len(dedup) == 0
    assert not dedup.is_duplicate("a" * 64)


def test_add_file(deduplicator):
    """Test adding a file to the tracker."""
    checksum = "a" * 64
    filepath = "/path/to/file.jpg"
    
    deduplicator.add_file(checksum, filepath)
    
    assert deduplicator.is_duplicate(checksum)
    assert deduplicator.get_existing_file(checksum) == filepath
    assert len(deduplicator) == 1


def test_add_file_invalid_checksum(deduplicator):
    """Test that invalid checksums are rejected."""
    # Too short
    with pytest.raises(ValueError, match="Invalid SHA256 checksum format"):
        deduplicator.add_file("abc123", "/path/to/file.jpg")
    
    # Invalid characters
    with pytest.raises(ValueError, match="Invalid SHA256 checksum format"):
        deduplicator.add_file("g" * 64, "/path/to/file.jpg")


def test_is_duplicate(deduplicator):
    """Test checking for duplicates."""
    checksum = "b" * 64
    
    # Not a duplicate initially
    assert not deduplicator.is_duplicate(checksum)
    
    # Add file
    deduplicator.add_file(checksum, "/path/to/file.jpg")
    
    # Now it's a duplicate
    assert deduplicator.is_duplicate(checksum)


def test_is_duplicate_case_insensitive(deduplicator):
    """Test that duplicate checking is case-insensitive."""
    checksum_lower = "c" * 64
    checksum_upper = "C" * 64
    
    deduplicator.add_file(checksum_lower, "/path/to/file.jpg")
    
    # Should be detected as duplicate regardless of case
    assert deduplicator.is_duplicate(checksum_upper)
    assert deduplicator.is_duplicate(checksum_lower)


def test_get_existing_file(deduplicator):
    """Test getting path to existing file."""
    checksum = "d" * 64
    filepath = "/path/to/image.jpg"
    
    # Not found initially
    assert deduplicator.get_existing_file(checksum) is None
    
    # Add file
    deduplicator.add_file(checksum, filepath)
    
    # Now found
    assert deduplicator.get_existing_file(checksum) == filepath


def test_get_existing_file_case_insensitive(deduplicator):
    """Test that file lookup is case-insensitive."""
    checksum_lower = "e" * 64
    checksum_upper = "E" * 64
    filepath = "/path/to/file.jpg"
    
    deduplicator.add_file(checksum_lower, filepath)
    
    # Should work with different case
    assert deduplicator.get_existing_file(checksum_upper) == filepath


def test_remove_file(deduplicator):
    """Test removing a file from the tracker."""
    checksum = "f" * 64
    filepath = "/path/to/file.jpg"
    
    # Add file
    deduplicator.add_file(checksum, filepath)
    assert deduplicator.is_duplicate(checksum)
    
    # Remove file
    result = deduplicator.remove_file(checksum)
    
    assert result is True
    assert not deduplicator.is_duplicate(checksum)
    assert deduplicator.get_existing_file(checksum) is None
    assert len(deduplicator) == 0


def test_remove_file_not_found(deduplicator):
    """Test removing a file that doesn't exist."""
    checksum = "0" * 64
    
    result = deduplicator.remove_file(checksum)
    
    assert result is False


def test_get_all_checksums(deduplicator):
    """Test getting all checksums."""
    checksums = {
        "a" * 64: "/path/to/file1.jpg",
        "b" * 64: "/path/to/file2.jpg",
        "c" * 64: "/path/to/file3.jpg",
    }
    
    for checksum, filepath in checksums.items():
        deduplicator.add_file(checksum, filepath)
    
    all_checksums = deduplicator.get_all_checksums()
    
    assert len(all_checksums) == 3
    assert all_checksums == checksums


def test_get_all_checksums_returns_copy(deduplicator):
    """Test that get_all_checksums returns a copy, not the internal dict."""
    checksum = "a" * 64
    deduplicator.add_file(checksum, "/path/to/file.jpg")
    
    all_checksums = deduplicator.get_all_checksums()
    
    # Modify the returned dict
    all_checksums[checksum] = "/different/path.jpg"
    
    # Original should be unchanged
    assert deduplicator.get_existing_file(checksum) == "/path/to/file.jpg"


def test_clear(deduplicator):
    """Test clearing all checksums."""
    # Add some files
    for i in range(5):
        checksum = str(i) * 64
        deduplicator.add_file(checksum, f"/path/to/file{i}.jpg")
    
    assert len(deduplicator) == 5
    
    # Clear
    deduplicator.clear()
    
    assert len(deduplicator) == 0
    assert not deduplicator.is_duplicate("0" * 64)


def test_persistence_save_and_load(tmp_path):
    """Test saving and loading checksums from disk."""
    persistence_file = tmp_path / "checksums.json"
    
    # Create deduplicator and add files
    dedup1 = FileDeduplicator(persistence_file=persistence_file)
    checksums = {
        "a" * 64: "/path/to/file1.jpg",
        "b" * 64: "/path/to/file2.jpg",
    }
    
    for checksum, filepath in checksums.items():
        dedup1.add_file(checksum, filepath)
    
    # Verify persistence file was created
    assert persistence_file.exists()
    
    # Create new deduplicator and load from disk
    dedup2 = FileDeduplicator(persistence_file=persistence_file)
    
    # Verify data was loaded
    assert len(dedup2) == 2
    for checksum, filepath in checksums.items():
        assert dedup2.is_duplicate(checksum)
        assert dedup2.get_existing_file(checksum) == filepath


def test_persistence_load_nonexistent_file(tmp_path):
    """Test loading from non-existent persistence file."""
    persistence_file = tmp_path / "does_not_exist.json"
    
    # Should initialize with empty dict
    dedup = FileDeduplicator(persistence_file=persistence_file)
    
    assert len(dedup) == 0


def test_persistence_corrupted_file(tmp_path):
    """Test loading from corrupted persistence file."""
    persistence_file = tmp_path / "corrupted.json"
    
    # Create corrupted JSON file
    persistence_file.write_text("not valid json{{{")
    
    # Should initialize with empty dict
    dedup = FileDeduplicator(persistence_file=persistence_file)
    
    assert len(dedup) == 0


def test_persistence_save_on_add(tmp_path):
    """Test that persistence file is updated when adding files."""
    persistence_file = tmp_path / "checksums.json"
    dedup = FileDeduplicator(persistence_file=persistence_file)
    
    checksum = "a" * 64
    filepath = "/path/to/file.jpg"
    
    dedup.add_file(checksum, filepath)
    
    # Verify file was saved
    assert persistence_file.exists()
    
    # Verify content
    with open(persistence_file, 'r') as f:
        data = json.load(f)
    
    assert data[checksum] == filepath


def test_persistence_save_on_remove(tmp_path):
    """Test that persistence file is updated when removing files."""
    persistence_file = tmp_path / "checksums.json"
    dedup = FileDeduplicator(persistence_file=persistence_file)
    
    # Add files
    checksum1 = "a" * 64
    checksum2 = "b" * 64
    dedup.add_file(checksum1, "/path/to/file1.jpg")
    dedup.add_file(checksum2, "/path/to/file2.jpg")
    
    # Remove one
    dedup.remove_file(checksum1)
    
    # Verify persistence file was updated
    with open(persistence_file, 'r') as f:
        data = json.load(f)
    
    assert checksum1 not in data
    assert checksum2 in data


def test_persistence_save_on_clear(tmp_path):
    """Test that persistence file is updated when clearing."""
    persistence_file = tmp_path / "checksums.json"
    dedup = FileDeduplicator(persistence_file=persistence_file)
    
    # Add files
    dedup.add_file("a" * 64, "/path/to/file1.jpg")
    dedup.add_file("b" * 64, "/path/to/file2.jpg")
    
    # Clear
    dedup.clear()
    
    # Verify persistence file was updated
    with open(persistence_file, 'r') as f:
        data = json.load(f)
    
    assert len(data) == 0


def test_persistence_directory_creation(tmp_path):
    """Test that parent directories are created for persistence file."""
    persistence_file = tmp_path / "nested" / "dir" / "checksums.json"
    
    dedup = FileDeduplicator(persistence_file=persistence_file)
    dedup.add_file("a" * 64, "/path/to/file.jpg")
    
    # Verify directory was created
    assert persistence_file.parent.exists()
    assert persistence_file.exists()


def test_len(deduplicator):
    """Test __len__ method."""
    assert len(deduplicator) == 0
    
    deduplicator.add_file("a" * 64, "/path/to/file1.jpg")
    assert len(deduplicator) == 1
    
    deduplicator.add_file("b" * 64, "/path/to/file2.jpg")
    assert len(deduplicator) == 2
    
    deduplicator.remove_file("a" * 64)
    assert len(deduplicator) == 1


def test_repr(deduplicator):
    """Test __repr__ method."""
    repr_str = repr(deduplicator)
    
    assert "FileDeduplicator" in repr_str
    assert "tracked=0" in repr_str
    assert "persistence=disabled" in repr_str


def test_repr_with_persistence(tmp_path):
    """Test __repr__ with persistence enabled."""
    persistence_file = tmp_path / "checksums.json"
    dedup = FileDeduplicator(persistence_file=persistence_file)
    
    dedup.add_file("a" * 64, "/path/to/file.jpg")
    
    repr_str = repr(dedup)
    
    assert "FileDeduplicator" in repr_str
    assert "tracked=1" in repr_str
    assert "persistence=enabled" in repr_str


def test_multiple_files_same_checksum_updates_path(deduplicator):
    """Test that adding a file with existing checksum updates the path."""
    checksum = "a" * 64
    filepath1 = "/path/to/file1.jpg"
    filepath2 = "/path/to/file2.jpg"
    
    deduplicator.add_file(checksum, filepath1)
    assert deduplicator.get_existing_file(checksum) == filepath1
    
    # Add again with different path - should update
    deduplicator.add_file(checksum, filepath2)
    assert deduplicator.get_existing_file(checksum) == filepath2
    
    # Still only one entry
    assert len(deduplicator) == 1


def test_add_multiple_files(deduplicator):
    """Test adding multiple files."""
    files = {
        "a" * 64: "/path/to/file1.jpg",
        "b" * 64: "/path/to/file2.png",
        "c" * 64: "/path/to/file3.gif",
        "d" * 64: "/path/to/file4.mp4",
    }
    
    for checksum, filepath in files.items():
        deduplicator.add_file(checksum, filepath)
    
    assert len(deduplicator) == len(files)
    
    for checksum, filepath in files.items():
        assert deduplicator.is_duplicate(checksum)
        assert deduplicator.get_existing_file(checksum) == filepath
