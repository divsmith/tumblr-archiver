"""
Tests for the Wayback Machine client module.
"""

import pytest
import requests
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from tumblr_archiver.wayback_client import (
    WaybackClient,
    WaybackError,
    SnapshotNotFoundError,
    RateLimitError,
    Snapshot,
)


class TestSnapshot:
    """Tests for Snapshot dataclass."""
    
    def test_snapshot_creation(self, sample_snapshot):
        """Test creating a Snapshot object."""
        assert sample_snapshot.urlkey == "com,tumblr,media)/tumblr_abc123_1280.jpg"
        assert sample_snapshot.timestamp == "20250101120000"
        assert sample_snapshot.status_code == "200"
    
    def test_snapshot_datetime_property(self, sample_snapshot):
        """Test datetime property parsing."""
        dt = sample_snapshot.datetime
        
        assert isinstance(dt, datetime)
        assert dt.year == 2025
        assert dt.month == 1
        assert dt.day == 1
    
    def test_snapshot_replay_url(self, sample_snapshot):
        """Test replay URL construction."""
        replay_url = sample_snapshot.replay_url
        
        assert 'web.archive.org/web' in replay_url
        assert sample_snapshot.timestamp in replay_url
        assert sample_snapshot.original_url in replay_url
        assert 'id_' in replay_url  # Identity flag
    
    def test_snapshot_file_size(self, sample_snapshot):
        """Test file_size property."""
        assert sample_snapshot.file_size == 524288
    
    def test_snapshot_file_size_invalid(self):
        """Test file_size with invalid length."""
        snapshot = Snapshot(
            urlkey="test",
            timestamp="20250101120000",
            original_url="https://example.com/image.jpg",
            mimetype="image/jpeg",
            status_code="200",
            digest="ABC123",
            length="-"  # Invalid length
        )
        
        assert snapshot.file_size == 0


class TestWaybackClient:
    """Tests for WaybackClient class."""
    
    def test_client_initialization(self):
        """Test client initialization."""
        client = WaybackClient()
        
        assert client.timeout == 30
        assert client.max_retries == 3
        assert client.session is not None
    
    def test_client_custom_initialization(self):
        """Test client with custom parameters."""
        client = WaybackClient(
            user_agent="CustomAgent/1.0",
            timeout=60,
            max_retries=5
        )
        
        assert client.timeout == 60
        assert client.max_retries == 5
        assert "CustomAgent" in client.session.headers['User-Agent']
    
    @patch('requests.Session')
    def test_check_availability_found(self, mock_session_class):
        """Test check_availability when snapshots exist."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'archived_snapshots': {
                'closest': {
                    'available': True,
                    'url': 'https://web.archive.org/web/20250101/example.com',
                    'timestamp': '20250101'
                }
            }
        }
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = WaybackClient()
        client.session = mock_session
        
        result = client.check_availability('https://example.com/image.jpg')
        
        assert result is True
        mock_session.get.assert_called_once()
    
    @patch('requests.Session')
    def test_check_availability_not_found(self, mock_session_class):
        """Test check_availability when no snapshots exist."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'archived_snapshots': {}
        }
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = WaybackClient()
        client.session = mock_session
        
        result = client.check_availability('https://example.com/missing.jpg')
        
        assert result is False
    
    @patch('requests.Session')
    def test_check_availability_error(self, mock_session_class):
        """Test check_availability with network error."""
        mock_session = Mock()
        mock_session.get.side_effect = requests.RequestException("Network error")
        mock_session_class.return_value = mock_session
        
        client = WaybackClient()
        client.session = mock_session
        
        with pytest.raises(WaybackError):
            client.check_availability('https://example.com/image.jpg')
    
    @patch('requests.Session')
    def test_get_snapshots_success(self, mock_session_class):
        """Test successful snapshot retrieval."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            ['urlkey', 'timestamp', 'original', 'mimetype', 'statuscode', 'digest', 'length'],
            ['com,example)/image.jpg', '20250101120000', 'https://example.com/image.jpg',
             'image/jpeg', '200', 'ABC123', '524288'],
            ['com,example)/image.jpg', '20241201120000', 'https://example.com/image.jpg',
             'image/jpeg', '200', 'DEF456', '524288'],
        ]
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = WaybackClient()
        client.session = mock_session
        
        snapshots = client.get_snapshots('https://example.com/image.jpg', limit=5)
        
        assert len(snapshots) == 2
        assert isinstance(snapshots[0], Snapshot)
        # Should be sorted newest first
        assert snapshots[0].timestamp > snapshots[1].timestamp
    
    @patch('requests.Session')
    def test_get_snapshots_not_found(self, mock_session_class):
        """Test get_snapshots when no snapshots exist."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            ['urlkey', 'timestamp', 'original', 'mimetype', 'statuscode', 'digest', 'length']
        ]
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = WaybackClient()
        client.session = mock_session
        
        with pytest.raises(SnapshotNotFoundError):
            client.get_snapshots('https://example.com/missing.jpg')
    
    @patch('requests.Session')
    def test_get_snapshots_network_error(self, mock_session_class):
        """Test get_snapshots with network error."""
        mock_session = Mock()
        mock_session.get.side_effect = requests.RequestException("Network error")
        mock_session_class.return_value = mock_session
        
        client = WaybackClient()
        client.session = mock_session
        
        with pytest.raises(WaybackError):
            client.get_snapshots('https://example.com/image.jpg')
    
    @patch('requests.Session')
    def test_get_snapshots_malformed_response(self, mock_session_class):
        """Test get_snapshots with malformed API response."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            ['urlkey', 'timestamp'],  # Missing fields
            ['com,example)/image.jpg', '20250101120000']  # Incomplete row
        ]
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = WaybackClient()
        client.session = mock_session
        
        with pytest.raises(WaybackError):
            client.get_snapshots('https://example.com/image.jpg')
    
    @patch('requests.Session')
    def test_get_best_snapshot_success(self, mock_session_class):
        """Test getting the best snapshot."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            ['urlkey', 'timestamp', 'original', 'mimetype', 'statuscode', 'digest', 'length'],
            ['com,example)/image.jpg', '20250101120000', 'https://example.com/image.jpg',
             'image/jpeg', '200', 'ABC123', '1048576'],  # Larger file
            ['com,example)/image.jpg', '20241201120000', 'https://example.com/image.jpg',
             'image/jpeg', '200', 'DEF456', '524288'],
        ]
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = WaybackClient()
        client.session = mock_session
        
        snapshot = client.get_best_snapshot('https://example.com/image.jpg')
        
        assert snapshot is not None
        assert isinstance(snapshot, Snapshot)
        # Should prefer the larger file
        assert snapshot.file_size == 1048576
    
    @patch('requests.Session')
    def test_download_snapshot_success(self, mock_session_class, temp_dir):
        """Test successful snapshot download."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'fake image data'
        mock_response.headers = {'Content-Type': 'image/jpeg'}
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = WaybackClient()
        client.session = mock_session
        
        snapshot = Snapshot(
            urlkey="com,example)/image.jpg",
            timestamp="20250101120000",
            original_url="https://example.com/image.jpg",
            mimetype="image/jpeg",
            status_code="200",
            digest="ABC123",
            length="524288"
        )
        
        output_path = temp_dir / "image.jpg"
        result_path = client.download_snapshot(snapshot, output_path)
        
        assert result_path == output_path
        assert output_path.exists()
        assert output_path.read_bytes() == b'fake image data'
    
    @patch('requests.Session')
    def test_download_snapshot_404(self, mock_session_class, temp_dir):
        """Test snapshot download with 404 error."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 404
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = WaybackClient()
        client.session = mock_session
        
        snapshot = Snapshot(
            urlkey="com,example)/missing.jpg",
            timestamp="20250101120000",
            original_url="https://example.com/missing.jpg",
            mimetype="image/jpeg",
            status_code="200",
            digest="ABC123",
            length="524288"
        )
        
        output_path = temp_dir / "missing.jpg"
        
        with pytest.raises(WaybackError):
            client.download_snapshot(snapshot, output_path)
    
    def test_client_context_manager(self):
        """Test client as context manager."""
        with WaybackClient() as client:
            assert client.session is not None
        
        # Session should be closed
        # Can't easily verify without additional mocking
    
    @patch('requests.Session')
    def test_rate_limit_handling(self, mock_session_class):
        """Test rate limit error handling."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {'Retry-After': '60'}
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = WaybackClient()
        client.session = mock_session
        
        # Should raise WaybackError for rate limiting
        with pytest.raises(WaybackError):
            client.check_availability('https://example.com/image.jpg')
