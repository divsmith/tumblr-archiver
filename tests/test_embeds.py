"""
Tests for external embed detection and downloading.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.tumblr_archiver.embeds import EmbedHandler
from src.tumblr_archiver.embed_downloaders import EmbedDownloader
from src.tumblr_archiver.models import MediaItem


class TestEmbedHandler:
    """Tests for EmbedHandler class."""
    
    @pytest.fixture
    def handler(self):
        """Create an EmbedHandler instance."""
        return EmbedHandler()
    
    @pytest.fixture
    def sample_timestamp(self):
        """Sample timestamp for testing."""
        return datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    
    def test_detect_youtube_iframe_embed(self, handler, sample_timestamp):
        """Test detection of YouTube embed in iframe."""
        html = '''
        <div class="post">
            <iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe>
        </div>
        '''
        
        embeds = handler.detect_embeds(
            html,
            post_url="https://example.tumblr.com/post/123456",
            post_id="123456",
            timestamp=sample_timestamp
        )
        
        assert len(embeds) == 1
        assert embeds[0].media_type == "video"
        assert embeds[0].post_id == "123456"
        assert "youtube" in embeds[0].original_url
        assert "dQw4w9WgXcQ" in embeds[0].original_url
        assert embeds[0].status == "missing"
        assert "youtube" in embeds[0].filename.lower()
    
    def test_detect_vimeo_iframe_embed(self, handler, sample_timestamp):
        """Test detection of Vimeo embed in iframe."""
        html = '''
        <iframe src="https://player.vimeo.com/video/123456789"></iframe>
        '''
        
        embeds = handler.detect_embeds(
            html,
            post_url="https://example.tumblr.com/post/999",
            timestamp=sample_timestamp
        )
        
        assert len(embeds) == 1
        assert embeds[0].media_type == "video"
        assert "vimeo.com" in embeds[0].original_url
        assert "123456789" in embeds[0].original_url
        assert "vimeo" in embeds[0].filename.lower()
    
    def test_detect_dailymotion_embed(self, handler, sample_timestamp):
        """Test detection of Dailymotion embed."""
        html = '''
        <iframe src="https://www.dailymotion.com/embed/video/x8abcde"></iframe>
        '''
        
        embeds = handler.detect_embeds(
            html,
            post_url="https://example.tumblr.com/post/555",
            timestamp=sample_timestamp
        )
        
        assert len(embeds) == 1
        assert "dailymotion" in embeds[0].original_url
        assert "x8abcde" in embeds[0].original_url
    
    def test_detect_multiple_embeds(self, handler, sample_timestamp):
        """Test detection of multiple embeds in one post."""
        html = '''
        <div class="post">
            <iframe src="https://www.youtube.com/embed/abc123"></iframe>
            <iframe src="https://player.vimeo.com/video/987654"></iframe>
        </div>
        '''
        
        embeds = handler.detect_embeds(
            html,
            post_url="https://example.tumblr.com/post/777",
            timestamp=sample_timestamp
        )
        
        assert len(embeds) == 2
        assert any("youtube" in e.original_url for e in embeds)
        assert any("vimeo" in e.original_url for e in embeds)
    
    def test_ignore_unsupported_iframe(self, handler, sample_timestamp):
        """Test that unsupported iframes are ignored."""
        html = '''
        <iframe src="https://example.com/some-widget"></iframe>
        <iframe src="https://ads.example.com/ad"></iframe>
        '''
        
        embeds = handler.detect_embeds(
            html,
            post_url="https://example.tumblr.com/post/111",
            timestamp=sample_timestamp
        )
        
        assert len(embeds) == 0
    
    def test_detect_youtube_link(self, handler, sample_timestamp):
        """Test detection of YouTube link in anchor tag."""
        html = '''
        <div class="post">
            <a href="https://www.youtube.com/watch?v=test123">Watch on YouTube</a>
        </div>
        '''
        
        embeds = handler.detect_embeds(
            html,
            post_url="https://example.tumblr.com/post/222",
            timestamp=sample_timestamp
        )
        
        assert len(embeds) == 1
        assert "youtube.com/watch?v=test123" in embeds[0].original_url
    
    def test_detect_youtu_be_short_url(self, handler, sample_timestamp):
        """Test detection of youtu.be short URLs."""
        html = '''
        <iframe src="https://www.youtube.com/embed/shortID"></iframe>
        '''
        
        embeds = handler.detect_embeds(
            html,
            post_url="https://example.tumblr.com/post/333",
            timestamp=sample_timestamp
        )
        
        assert len(embeds) == 1
        assert "shortID" in embeds[0].original_url
    
    def test_is_supported_embed_youtube(self, handler):
        """Test is_supported_embed for YouTube URLs."""
        assert handler.is_supported_embed("https://www.youtube.com/watch?v=abc")
        assert handler.is_supported_embed("https://youtube.com/embed/abc")
        assert handler.is_supported_embed("https://youtu.be/abc")
        assert handler.is_supported_embed("https://m.youtube.com/watch?v=abc")
    
    def test_is_supported_embed_vimeo(self, handler):
        """Test is_supported_embed for Vimeo URLs."""
        assert handler.is_supported_embed("https://vimeo.com/123456")
        assert handler.is_supported_embed("https://player.vimeo.com/video/123456")
        assert handler.is_supported_embed("https://www.vimeo.com/123456")
    
    def test_is_supported_embed_dailymotion(self, handler):
        """Test is_supported_embed for Dailymotion URLs."""
        assert handler.is_supported_embed("https://www.dailymotion.com/video/abc123")
        assert handler.is_supported_embed("https://dailymotion.com/embed/video/abc123")
    
    def test_is_supported_embed_unsupported(self, handler):
        """Test is_supported_embed returns False for unsupported sites."""
        assert not handler.is_supported_embed("https://example.com/video")
        assert not handler.is_supported_embed("https://facebook.com/video/123")
        assert not handler.is_supported_embed("https://twitter.com/status/123")
    
    def test_normalize_youtube_embed_url(self, handler):
        """Test normalizing YouTube embed URLs."""
        urls = [
            "https://www.youtube.com/embed/abc123",
            "https://youtube.com/watch?v=abc123",
            "https://youtu.be/abc123",
        ]
        
        for url in urls:
            normalized = handler._normalize_embed_url(url)
            assert normalized == "https://www.youtube.com/watch?v=abc123"
    
    def test_normalize_vimeo_embed_url(self, handler):
        """Test normalizing Vimeo embed URLs."""
        urls = [
            "https://player.vimeo.com/video/123456",
            "https://vimeo.com/123456",
            "https://www.vimeo.com/video/123456",
        ]
        
        for url in urls:
            normalized = handler._normalize_embed_url(url)
            assert normalized == "https://vimeo.com/123456"
    
    def test_extract_video_id_youtube(self, handler):
        """Test extracting video ID from YouTube URL."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        video_id = handler._extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"
    
    def test_extract_video_id_vimeo(self, handler):
        """Test extracting video ID from Vimeo URL."""
        url = "https://vimeo.com/123456789"
        video_id = handler._extract_video_id(url)
        assert video_id == "123456789"
    
    def test_get_platform_name(self, handler):
        """Test getting platform name from URL."""
        assert handler._get_platform_name("https://youtube.com/watch?v=abc") == "youtube"
        assert handler._get_platform_name("https://vimeo.com/123") == "vimeo"
        assert handler._get_platform_name("https://dailymotion.com/video/abc") == "dailymotion"
        assert handler._get_platform_name("https://example.com/video") == "unknown"
    
    def test_extract_post_id_from_url(self, handler):
        """Test extracting post ID from Tumblr URL."""
        assert handler._extract_post_id("https://blog.tumblr.com/post/123456789") == "123456789"
        assert handler._extract_post_id("https://blog.tumblr.com/123456789") == "123456789"
    
    def test_empty_html(self, handler, sample_timestamp):
        """Test handling of empty HTML."""
        embeds = handler.detect_embeds(
            "",
            post_url="https://example.tumblr.com/post/999",
            timestamp=sample_timestamp
        )
        assert len(embeds) == 0
    
    def test_iframe_without_src(self, handler, sample_timestamp):
        """Test handling of iframe without src attribute."""
        html = '<iframe width="560" height="315"></iframe>'
        embeds = handler.detect_embeds(
            html,
            post_url="https://example.tumblr.com/post/999",
            timestamp=sample_timestamp
        )
        assert len(embeds) == 0


class TestEmbedDownloader:
    """Tests for EmbedDownloader class."""
    
    @pytest.fixture
    def temp_output_dir(self, tmp_path):
        """Create a temporary output directory."""
        output_dir = tmp_path / "embeds"
        output_dir.mkdir()
        return output_dir
    
    @pytest.fixture
    def sample_media_item(self):
        """Create a sample MediaItem for testing."""
        return MediaItem(
            post_id="123456",
            post_url="https://example.tumblr.com/post/123456",
            timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            media_type="video",
            filename="123456_youtube_abc123.mp4",
            original_url="https://www.youtube.com/watch?v=abc123",
            retrieved_from="tumblr",
            status="missing"
        )
    
    def test_init_creates_output_dir(self, temp_output_dir):
        """Test that initializing creates output directory."""
        EmbedDownloader(temp_output_dir)
        assert temp_output_dir.exists()
        assert temp_output_dir.is_dir()
    
    def test_is_available_without_ytdlp(self, temp_output_dir):
        """Test is_available returns False when yt-dlp not installed."""
        with patch('src.tumblr_archiver.embed_downloaders.EmbedDownloader._check_yt_dlp', return_value=False):
            downloader = EmbedDownloader(temp_output_dir)
            assert not downloader.is_available()
    
    def test_is_available_with_ytdlp(self, temp_output_dir):
        """Test is_available returns True when yt-dlp is installed."""
        with patch('src.tumblr_archiver.embed_downloaders.EmbedDownloader._check_yt_dlp', return_value=True):
            downloader = EmbedDownloader(temp_output_dir)
            assert downloader.is_available()
    
    def test_can_download_without_ytdlp(self, temp_output_dir):
        """Test can_download returns False when yt-dlp not available."""
        with patch('src.tumblr_archiver.embed_downloaders.EmbedDownloader._check_yt_dlp', return_value=False):
            downloader = EmbedDownloader(temp_output_dir)
            assert not downloader.can_download("https://youtube.com/watch?v=abc")
    
    def test_can_download_with_ytdlp(self, temp_output_dir):
        """Test can_download returns True when yt-dlp is available."""
        with patch('src.tumblr_archiver.embed_downloaders.EmbedDownloader._check_yt_dlp', return_value=True):
            downloader = EmbedDownloader(temp_output_dir)
            assert downloader.can_download("https://youtube.com/watch?v=abc")
    
    def test_download_embed_without_ytdlp(self, temp_output_dir, sample_media_item):
        """Test download_embed fails gracefully when yt-dlp not installed."""
        with patch('src.tumblr_archiver.embed_downloaders.EmbedDownloader._check_yt_dlp', return_value=False):
            downloader = EmbedDownloader(temp_output_dir)
            result = downloader.download_embed(sample_media_item)
            
            assert result.status == "error"
            assert "yt-dlp not installed" in result.notes
    
    @patch('src.tumblr_archiver.embed_downloaders.EmbedDownloader._check_yt_dlp', return_value=True)
    def test_download_embed_success(self, mock_check, temp_output_dir, sample_media_item):
        """Test successful embed download."""
        # Mock yt_dlp module
        mock_yt_dlp = MagicMock()
        mock_ydl_instance = MagicMock()
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance
        mock_ydl_instance.extract_info.return_value = {
            'title': 'Test Video',
            'extractor': 'youtube'
        }
        
        # Create a fake downloaded file
        output_file = temp_output_dir / sample_media_item.filename
        output_file.write_text("fake video content")
        
        with patch.dict('sys.modules', {'yt_dlp': mock_yt_dlp}):
            downloader = EmbedDownloader(temp_output_dir)
            
            # Mock _find_downloaded_file to return our fake file
            with patch.object(downloader, '_find_downloaded_file', return_value=output_file):
                result = downloader.download_embed(sample_media_item)
        
        assert result.status == "downloaded"
        assert result.byte_size > 0
        assert "yt-dlp" in result.notes
    
    @patch('src.tumblr_archiver.embed_downloaders.EmbedDownloader._check_yt_dlp', return_value=True)
    def test_download_embed_with_progress_callback(self, mock_check, temp_output_dir, sample_media_item):
        """Test download with progress callback."""
        mock_yt_dlp = MagicMock()
        mock_ydl_instance = MagicMock()
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance
        mock_ydl_instance.extract_info.return_value = {'extractor': 'youtube'}
        
        output_file = temp_output_dir / sample_media_item.filename
        output_file.write_text("fake video")
        
        progress_calls = []
        
        def progress_callback(downloaded, total):
            progress_calls.append((downloaded, total))
        
        with patch.dict('sys.modules', {'yt_dlp': mock_yt_dlp}):
            downloader = EmbedDownloader(temp_output_dir)
            with patch.object(downloader, '_find_downloaded_file', return_value=output_file):
                result = downloader.download_embed(sample_media_item, progress_callback)
        
        assert result.status == "downloaded"
    
    @patch('src.tumblr_archiver.embed_downloaders.EmbedDownloader._check_yt_dlp', return_value=True)
    def test_download_embed_failure(self, mock_check, temp_output_dir, sample_media_item):
        """Test handling of download failure."""
        mock_yt_dlp = MagicMock()
        mock_ydl_instance = MagicMock()
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance
        mock_ydl_instance.extract_info.side_effect = Exception("Download failed")
        
        with patch.dict('sys.modules', {'yt_dlp': mock_yt_dlp}):
            downloader = EmbedDownloader(temp_output_dir)
            result = downloader.download_embed(sample_media_item)
        
        assert result.status == "error"
        assert "Download failed" in result.notes
    
    def test_find_downloaded_file_exact_match(self, temp_output_dir):
        """Test finding downloaded file with exact name."""
        downloader = EmbedDownloader(temp_output_dir)
        
        test_file = temp_output_dir / "video.mp4"
        test_file.write_text("content")
        
        found = downloader._find_downloaded_file(temp_output_dir / "video")
        assert found == test_file
    
    def test_find_downloaded_file_different_extension(self, temp_output_dir):
        """Test finding downloaded file with different extension."""
        downloader = EmbedDownloader(temp_output_dir)
        
        test_file = temp_output_dir / "video.webm"
        test_file.write_text("content")
        
        found = downloader._find_downloaded_file(temp_output_dir / "video")
        assert found == test_file
    
    def test_find_downloaded_file_not_found(self, temp_output_dir):
        """Test finding downloaded file when it doesn't exist."""
        downloader = EmbedDownloader(temp_output_dir)
        found = downloader._find_downloaded_file(temp_output_dir / "nonexistent")
        assert found is None
    
    @patch('src.tumblr_archiver.embed_downloaders.EmbedDownloader._check_yt_dlp', return_value=True)
    def test_get_embed_info_success(self, mock_check, temp_output_dir):
        """Test getting embed info without downloading."""
        mock_yt_dlp = MagicMock()
        mock_ydl_instance = MagicMock()
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance
        mock_ydl_instance.extract_info.return_value = {
            'title': 'Test Video',
            'duration': 180,
            'description': 'Test description',
            'uploader': 'Test Channel',
            'thumbnail': 'https://example.com/thumb.jpg',
            'extractor': 'youtube',
            'format': 'mp4'
        }
        
        with patch.dict('sys.modules', {'yt_dlp': mock_yt_dlp}):
            downloader = EmbedDownloader(temp_output_dir)
            info = downloader.get_embed_info("https://youtube.com/watch?v=abc")
        
        assert info is not None
        assert info['title'] == 'Test Video'
        assert info['duration'] == 180
        assert info['extractor'] == 'youtube'
    
    def test_get_embed_info_without_ytdlp(self, temp_output_dir):
        """Test get_embed_info returns None when yt-dlp not available."""
        with patch('src.tumblr_archiver.embed_downloaders.EmbedDownloader._check_yt_dlp', return_value=False):
            downloader = EmbedDownloader(temp_output_dir)
            info = downloader.get_embed_info("https://youtube.com/watch?v=abc")
            assert info is None
    
    @patch('src.tumblr_archiver.embed_downloaders.EmbedDownloader._check_yt_dlp', return_value=True)
    def test_get_embed_info_failure(self, mock_check, temp_output_dir):
        """Test get_embed_info handles failures gracefully."""
        mock_yt_dlp = MagicMock()
        mock_ydl_instance = MagicMock()
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance
        mock_ydl_instance.extract_info.side_effect = Exception("Failed to get info")
        
        with patch.dict('sys.modules', {'yt_dlp': mock_yt_dlp}):
            downloader = EmbedDownloader(temp_output_dir)
            info = downloader.get_embed_info("https://youtube.com/watch?v=abc")
            assert info is None
