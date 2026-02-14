"""Tests for the snapshot selector logic."""

import pytest

from tumblr_archiver.archive import Snapshot
from tumblr_archiver.snapshot_selector import SnapshotSelector


class TestSnapshotSelector:
    """Tests for SnapshotSelector."""
    
    def test_initialization(self):
        """Test selector initialization."""
        selector = SnapshotSelector()
        assert selector is not None
    
    def test_select_best_snapshot_empty_list(self):
        """Test selection from empty list."""
        selector = SnapshotSelector()
        result = selector.select_best_snapshot([])
        assert result is None
    
    def test_select_best_snapshot_single_valid(self):
        """Test selection with single valid snapshot."""
        snapshot = Snapshot(
            timestamp="20230615143022",
            statuscode="200",
            mimetype="image/jpeg",
            original_url="https://example.com/image.jpg",
            snapshot_url="https://web.archive.org/web/20230615143022id_/https://example.com/image.jpg"
        )
        
        selector = SnapshotSelector()
        result = selector.select_best_snapshot([snapshot])
        
        assert result == snapshot
    
    def test_select_best_snapshot_filters_404(self):
        """Test that 404 responses are filtered out."""
        snapshots = [
            Snapshot(
                timestamp="20230615143022",
                statuscode="404",
                mimetype="text/html",
                original_url="https://example.com/image.jpg",
                snapshot_url="https://web.archive.org/web/20230615143022id_/https://example.com/image.jpg"
            ),
            Snapshot(
                timestamp="20230501120000",
                statuscode="404",
                mimetype="text/html",
                original_url="https://example.com/image.jpg",
                snapshot_url="https://web.archive.org/web/20230501120000id_/https://example.com/image.jpg"
            ),
        ]
        
        selector = SnapshotSelector()
        result = selector.select_best_snapshot(snapshots)
        
        assert result is None
    
    def test_select_best_snapshot_filters_500(self):
        """Test that 500 errors are filtered out."""
        snapshots = [
            Snapshot(
                timestamp="20230615143022",
                statuscode="500",
                mimetype="text/html",
                original_url="https://example.com/image.jpg",
                snapshot_url="https://web.archive.org/web/20230615143022id_/https://example.com/image.jpg"
            ),
        ]
        
        selector = SnapshotSelector()
        result = selector.select_best_snapshot(snapshots)
        
        assert result is None
    
    def test_select_best_snapshot_filters_redirects(self):
        """Test that redirects (3xx) are filtered out."""
        snapshots = [
            Snapshot(
                timestamp="20230615143022",
                statuscode="302",
                mimetype="text/html",
                original_url="https://example.com/image.jpg",
                snapshot_url="https://web.archive.org/web/20230615143022id_/https://example.com/image.jpg"
            ),
            Snapshot(
                timestamp="20230501120000",
                statuscode="301",
                mimetype="text/html",
                original_url="https://example.com/image.jpg",
                snapshot_url="https://web.archive.org/web/20230501120000id_/https://example.com/image.jpg"
            ),
        ]
        
        selector = SnapshotSelector()
        result = selector.select_best_snapshot(snapshots)
        
        assert result is None
    
    def test_select_best_snapshot_filters_invalid_mime(self):
        """Test that invalid MIME types are filtered."""
        snapshots = [
            Snapshot(
                timestamp="20230615143022",
                statuscode="200",
                mimetype="unk",
                original_url="https://example.com/image.jpg",
                snapshot_url="https://web.archive.org/web/20230615143022id_/https://example.com/image.jpg"
            ),
            Snapshot(
                timestamp="20230501120000",
                statuscode="200",
                mimetype="warc/revisit",
                original_url="https://example.com/image.jpg",
                snapshot_url="https://web.archive.org/web/20230501120000id_/https://example.com/image.jpg"
            ),
        ]
        
        selector = SnapshotSelector()
        result = selector.select_best_snapshot(snapshots)
        
        assert result is None
    
    def test_select_best_snapshot_prefers_higher_resolution(self):
        """Test preference for higher resolution snapshots."""
        snapshots = [
            Snapshot(
                timestamp="20230615143022",
                statuscode="200",
                mimetype="image/jpeg",
                original_url="https://example.com/image_500.jpg",
                snapshot_url="https://web.archive.org/web/20230615143022id_/https://example.com/image_500.jpg"
            ),
            Snapshot(
                timestamp="20230501120000",
                statuscode="200",
                mimetype="image/jpeg",
                original_url="https://example.com/image_1280.jpg",
                snapshot_url="https://web.archive.org/web/20230501120000id_/https://example.com/image_1280.jpg"
            ),
            Snapshot(
                timestamp="20230301090000",
                statuscode="200",
                mimetype="image/jpeg",
                original_url="https://example.com/image_75.jpg",
                snapshot_url="https://web.archive.org/web/20230301090000id_/https://example.com/image_75.jpg"
            ),
        ]
        
        selector = SnapshotSelector()
        result = selector.select_best_snapshot(snapshots)
        
        # Should select the 1280 resolution
        assert result is not None
        assert "1280" in result.original_url
    
    def test_select_best_snapshot_prefers_recent_when_equal(self):
        """Test preference for more recent snapshots when quality is equal."""
        snapshots = [
            Snapshot(
                timestamp="20200615143022",
                statuscode="200",
                mimetype="image/jpeg",
                original_url="https://example.com/image.jpg",
                snapshot_url="https://web.archive.org/web/20200615143022id_/https://example.com/image.jpg"
            ),
            Snapshot(
                timestamp="20230501120000",
                statuscode="200",
                mimetype="image/jpeg",
                original_url="https://example.com/image.jpg",
                snapshot_url="https://web.archive.org/web/20230501120000id_/https://example.com/image.jpg"
            ),
        ]
        
        selector = SnapshotSelector()
        result = selector.select_best_snapshot(snapshots)
        
        # Should prefer the more recent snapshot (2023 over 2020)
        assert result is not None
        assert result.timestamp == "20230501120000"
    
    def test_select_best_snapshot_mixed_quality(self):
        """Test selection with mixed quality snapshots."""
        snapshots = [
            Snapshot(
                timestamp="20230615143022",
                statuscode="404",
                mimetype="text/html",
                original_url="https://example.com/image_1280.jpg",
                snapshot_url="https://web.archive.org/web/20230615143022id_/https://example.com/image_1280.jpg"
            ),
            Snapshot(
                timestamp="20230501120000",
                statuscode="200",
                mimetype="image/jpeg",
                original_url="https://example.com/image_500.jpg",
                snapshot_url="https://web.archive.org/web/20230501120000id_/https://example.com/image_500.jpg"
            ),
            Snapshot(
                timestamp="20230301090000",
                statuscode="302",
                mimetype="text/html",
                original_url="https://example.com/image.jpg",
                snapshot_url="https://web.archive.org/web/20230301090000id_/https://example.com/image.jpg"
            ),
        ]
        
        selector = SnapshotSelector()
        result = selector.select_best_snapshot(snapshots)
        
        # Should be the only valid one (200 status)
        assert result is not None
        assert result.timestamp == "20230501120000"
        assert result.statuscode == "200"
    
    def test_extract_resolution_tumblr_format(self):
        """Test resolution extraction from Tumblr URL format."""
        selector = SnapshotSelector()
        
        # Common Tumblr formats
        assert selector._extract_resolution("https://64.media.tumblr.com/abc/tumblr_xyz_1280.jpg") == 1280
        assert selector._extract_resolution("https://64.media.tumblr.com/abc/tumblr_xyz_500.jpg") == 500
        assert selector._extract_resolution("https://64.media.tumblr.com/abc/tumblr_xyz_75.jpg") == 75
        assert selector._extract_resolution("https://64.media.tumblr.com/abc/tumblr_xyz_250.png") == 250
    
    def test_extract_resolution_dimension_format(self):
        """Test resolution extraction from WxH format."""
        selector = SnapshotSelector()
        
        # Width x Height format
        assert selector._extract_resolution("https://example.com/image_1920x1080.jpg") == 1920
        assert selector._extract_resolution("https://example.com/image_640x480.jpg") == 640
    
    def test_extract_resolution_s_format(self):
        """Test resolution extraction from _s format."""
        selector = SnapshotSelector()
        
        # _s format (sometimes used)
        assert selector._extract_resolution("https://example.com/image_s1280.jpg") == 1280
        assert selector._extract_resolution("https://example.com/image_s640.jpg") == 640
    
    def test_extract_resolution_no_match(self):
        """Test resolution extraction when no pattern matches."""
        selector = SnapshotSelector()
        
        # No resolution in URL
        assert selector._extract_resolution("https://example.com/image.jpg") is None
        assert selector._extract_resolution("https://example.com/some_file.png") is None
    
    def test_extract_resolution_multiple_patterns(self):
        """Test resolution extraction with multiple patterns in URL."""
        selector = SnapshotSelector()
        
        # URL with multiple resolutions - should take the largest
        url = "https://example.com/thumb_100/image_1280.jpg"
        assert selector._extract_resolution(url) == 1280
    
    def test_is_valid_snapshot_invalid_status(self):
        """Test validation of snapshot with invalid status."""
        selector = SnapshotSelector()
        
        snapshot = Snapshot(
            timestamp="20230615143022",
            statuscode="-",
            mimetype="image/jpeg",
            original_url="https://example.com/image.jpg",
            snapshot_url="https://web.archive.org/web/20230615143022id_/https://example.com/image.jpg"
        )
        
        assert selector._is_valid_snapshot(snapshot) is False
    
    def test_score_snapshot_200_status(self):
        """Test scoring gives highest points to 200 OK."""
        selector = SnapshotSelector()
        
        snapshot_200 = Snapshot(
            timestamp="20230615143022",
            statuscode="200",
            mimetype="image/jpeg",
            original_url="https://example.com/image.jpg",
            snapshot_url="https://web.archive.org/web/20230615143022id_/https://example.com/image.jpg"
        )
        
        snapshot_201 = Snapshot(
            timestamp="20230615143022",
            statuscode="201",
            mimetype="image/jpeg",
            original_url="https://example.com/image.jpg",
            snapshot_url="https://web.archive.org/web/20230615143022id_/https://example.com/image.jpg"
        )
        
        score_200 = selector._score_snapshot(snapshot_200)
        score_201 = selector._score_snapshot(snapshot_201)
        
        # 200 should score higher than other 2xx codes
        assert score_200 > score_201
        assert score_200 >= 100.0
    
    def test_score_snapshot_resolution_bonus(self):
        """Test that higher resolution gets higher score."""
        selector = SnapshotSelector()
        
        snapshot_high = Snapshot(
            timestamp="20230615143022",
            statuscode="200",
            mimetype="image/jpeg",
            original_url="https://example.com/image_1280.jpg",
            snapshot_url="https://web.archive.org/web/20230615143022id_/https://example.com/image_1280.jpg"
        )
        
        snapshot_low = Snapshot(
            timestamp="20230615143022",
            statuscode="200",
            mimetype="image/jpeg",
            original_url="https://example.com/image_500.jpg",
            snapshot_url="https://web.archive.org/web/20230615143022id_/https://example.com/image_500.jpg"
        )
        
        score_high = selector._score_snapshot(snapshot_high)
        score_low = selector._score_snapshot(snapshot_low)
        
        # Higher resolution should score better
        assert score_high > score_low
    
    def test_score_snapshot_mime_type_bonus(self):
        """Test that media MIME types get bonus points."""
        selector = SnapshotSelector()
        
        snapshot_image = Snapshot(
            timestamp="20230615143022",
            statuscode="200",
            mimetype="image/jpeg",
            original_url="https://example.com/image.jpg",
            snapshot_url="https://web.archive.org/web/20230615143022id_/https://example.com/image.jpg"
        )
        
        snapshot_video = Snapshot(
            timestamp="20230615143022",
            statuscode="200",
            mimetype="video/mp4",
            original_url="https://example.com/video.mp4",
            snapshot_url="https://web.archive.org/web/20230615143022id_/https://example.com/video.mp4"
        )
        
        snapshot_text = Snapshot(
            timestamp="20230615143022",
            statuscode="200",
            mimetype="text/plain",
            original_url="https://example.com/file.txt",
            snapshot_url="https://web.archive.org/web/20230615143022id_/https://example.com/file.txt"
        )
        
        score_image = selector._score_snapshot(snapshot_image)
        score_video = selector._score_snapshot(snapshot_video)
        score_text = selector._score_snapshot(snapshot_text)
        
        # Media types should score higher than plain text
        assert score_image > score_text
        assert score_video > score_text
