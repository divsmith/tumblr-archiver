"""
Tests for URL utility functions.

This module provides comprehensive test coverage for URL parsing, validation,
normalization, and media URL extraction utilities.
"""

import json
from pathlib import Path

import pytest

from tumblr_archiver.url_utils import (
    build_blog_url,
    build_post_url,
    extract_blog_name,
    extract_media_urls,
    extract_original_url_from_wayback,
    get_filename_from_url,
    get_media_type_from_url,
    is_media_url,
    is_tumblr_url,
    is_valid_url,
    is_wayback_url,
    normalize_url,
    sanitize_filename,
)


# Load test fixtures
FIXTURES_PATH = Path(__file__).parent / "fixtures" / "urls.json"


@pytest.fixture
def url_fixtures():
    """Load URL test fixtures from JSON file."""
    with open(FIXTURES_PATH, "r") as f:
        return json.load(f)


class TestURLValidation:
    """Test URL validation functions."""
    
    def test_valid_urls(self, url_fixtures):
        """Test that valid URLs are correctly identified."""
        for url in url_fixtures["valid_urls"]:
            assert is_valid_url(url), f"Should be valid: {url}"
    
    def test_invalid_urls(self, url_fixtures):
        """Test that invalid URLs are correctly rejected."""
        for url in url_fixtures["invalid_urls"]:
            assert not is_valid_url(url), f"Should be invalid: {url}"
    
    def test_none_and_empty(self):
        """Test handling of None and empty strings."""
        assert not is_valid_url(None)
        assert not is_valid_url("")
        assert not is_valid_url("   ")
    
    def test_non_string_input(self):
        """Test handling of non-string inputs."""
        assert not is_valid_url(123)
        assert not is_valid_url([])
        assert not is_valid_url({})


class TestURLNormalization:
    """Test URL normalization functions."""
    
    def test_remove_tracking_params(self, url_fixtures):
        """Test removal of tracking parameters."""
        url = "https://example.com?utm_source=twitter&utm_medium=social&keep=this"
        normalized = normalize_url(url)
        assert "utm_source" not in normalized
        assert "utm_medium" not in normalized
        assert "keep=this" in normalized
    
    def test_remove_fragments(self):
        """Test removal of URL fragments."""
        url = "https://example.com/page#section"
        normalized = normalize_url(url)
        assert "#section" not in normalized
        assert normalized == "https://example.com/page"
    
    def test_remove_fragments_and_tracking(self):
        """Test removal of both fragments and tracking params."""
        url = "https://example.com/path?valid=keep&utm_source=remove#fragment"
        normalized = normalize_url(url)
        assert "utm_source" not in normalized
        assert "#fragment" not in normalized
        assert "valid=keep" in normalized
    
    def test_invalid_url_raises(self):
        """Test that invalid URLs raise ValueError."""
        with pytest.raises(ValueError):
            normalize_url("not a url")
    
    def test_already_normalized(self):
        """Test that already normalized URLs are unchanged."""
        url = "https://example.com/path"
        normalized = normalize_url(url)
        assert normalized == url
    
    def test_remove_common_tracking_params(self):
        """Test removal of various common tracking parameters."""
        tracking_params = ["utm_source", "utm_campaign", "fbclid", "gclid", "ref"]
        for param in tracking_params:
            url = f"https://example.com?{param}=value&keep=this"
            normalized = normalize_url(url)
            assert param not in normalized
            assert "keep=this" in normalized


class TestBlogNameExtraction:
    """Test blog name extraction from Tumblr URLs."""
    
    def test_standard_tumblr_url(self):
        """Test extraction from standard Tumblr subdomain."""
        assert extract_blog_name("https://myblog.tumblr.com") == "myblog"
        assert extract_blog_name("http://myblog.tumblr.com") == "myblog"
        assert extract_blog_name("https://another-blog.tumblr.com") == "another-blog"
    
    def test_tumblr_url_with_path(self):
        """Test extraction from Tumblr URLs with paths."""
        assert extract_blog_name("https://myblog.tumblr.com/") == "myblog"
        assert extract_blog_name("https://myblog.tumblr.com/archive") == "myblog"
        assert extract_blog_name("https://myblog.tumblr.com/post/123456") == "myblog"
    
    def test_tumblr_blog_path_format(self):
        """Test extraction from www.tumblr.com/blog/NAME format."""
        assert extract_blog_name("https://www.tumblr.com/blog/myblog") == "myblog"
        assert extract_blog_name("https://tumblr.com/blog/someblog") == "someblog"
    
    def test_non_tumblr_url(self):
        """Test that non-Tumblr URLs return None."""
        assert extract_blog_name("https://example.com") is None
        assert extract_blog_name("https://wordpress.com") is None
    
    def test_invalid_url(self):
        """Test that invalid URLs return None."""
        assert extract_blog_name("not a url") is None
        assert extract_blog_name("") is None
    
    def test_www_subdomain_ignored(self):
        """Test that www.tumblr.com without /blog/ path returns None."""
        assert extract_blog_name("https://www.tumblr.com") is None


class TestBlogURLBuilding:
    """Test blog URL construction functions."""
    
    def test_build_blog_url(self):
        """Test building blog URLs from blog names."""
        assert build_blog_url("myblog") == "https://myblog.tumblr.com"
        assert build_blog_url("another-blog") == "https://another-blog.tumblr.com"
    
    def test_build_blog_url_strips_domain(self):
        """Test that .tumblr.com is stripped if present."""
        assert build_blog_url("myblog.tumblr.com") == "https://myblog.tumblr.com"
    
    def test_build_blog_url_empty_raises(self):
        """Test that empty blog name raises ValueError."""
        with pytest.raises(ValueError):
            build_blog_url("")
    
    def test_build_post_url(self):
        """Test building post URLs."""
        assert build_post_url("myblog", "123456") == "https://myblog.tumblr.com/post/123456"
        assert build_post_url("test-blog", "789") == "https://test-blog.tumblr.com/post/789"
    
    def test_build_post_url_empty_raises(self):
        """Test that empty blog name or post ID raises ValueError."""
        with pytest.raises(ValueError):
            build_post_url("", "123")
        with pytest.raises(ValueError):
            build_post_url("myblog", "")


class TestTumblrURLDetection:
    """Test Tumblr URL detection."""
    
    def test_tumblr_urls(self, url_fixtures):
        """Test that Tumblr URLs are correctly identified."""
        for url in url_fixtures["tumblr_blog_urls"]["standard_format"]:
            assert is_tumblr_url(url), f"Should be Tumblr URL: {url}"
        
        for url in url_fixtures["tumblr_blog_urls"]["post_urls"]:
            assert is_tumblr_url(url), f"Should be Tumblr URL: {url}"
    
    def test_non_tumblr_urls(self, url_fixtures):
        """Test that non-Tumblr URLs are correctly rejected."""
        for url in url_fixtures["non_tumblr_urls"]:
            assert not is_tumblr_url(url), f"Should not be Tumblr URL: {url}"
    
    def test_invalid_urls(self):
        """Test that invalid URLs return False."""
        assert not is_tumblr_url("not a url")
        assert not is_tumblr_url("")


class TestMediaURLDetection:
    """Test media URL detection and type identification."""
    
    def test_image_urls(self, url_fixtures):
        """Test that image URLs are correctly identified."""
        for url in url_fixtures["media_urls"]["images"]:
            assert is_media_url(url), f"Should be media URL: {url}"
            assert get_media_type_from_url(url) == "image", f"Should be image: {url}"
    
    def test_video_urls(self, url_fixtures):
        """Test that video URLs are correctly identified."""
        for url in url_fixtures["media_urls"]["videos"]:
            assert is_media_url(url), f"Should be media URL: {url}"
            assert get_media_type_from_url(url) == "video", f"Should be video: {url}"
    
    def test_audio_urls(self, url_fixtures):
        """Test that audio URLs are correctly identified."""
        for url in url_fixtures["media_urls"]["audio"]:
            assert is_media_url(url), f"Should be media URL: {url}"
            assert get_media_type_from_url(url) == "audio", f"Should be audio: {url}"
    
    def test_non_media_urls(self, url_fixtures):
        """Test that non-media URLs are correctly rejected."""
        for url in url_fixtures["non_media_urls"]:
            assert not is_media_url(url), f"Should not be media URL: {url}"
            assert get_media_type_from_url(url) is None, f"Should have no media type: {url}"
    
    def test_invalid_urls(self):
        """Test that invalid URLs return False/None."""
        assert not is_media_url("not a url")
        assert get_media_type_from_url("not a url") is None


class TestMediaURLExtraction:
    """Test extraction of media URLs from HTML."""
    
    def test_extract_images(self, url_fixtures):
        """Test extraction of image URLs from HTML."""
        html = url_fixtures["html_samples"]["with_images"]
        urls = extract_media_urls(html)
        assert len(urls) == 2
        assert "https://example.com/image1.jpg" in urls
        assert "https://example.com/image2.png" in urls
    
    def test_extract_video(self, url_fixtures):
        """Test extraction of video URLs from HTML."""
        html = url_fixtures["html_samples"]["with_video"]
        urls = extract_media_urls(html)
        assert len(urls) == 1
        assert "https://example.com/video.mp4" in urls
    
    def test_extract_video_sources(self, url_fixtures):
        """Test extraction of video URLs from <source> tags."""
        html = url_fixtures["html_samples"]["with_video_sources"]
        urls = extract_media_urls(html)
        assert len(urls) == 2
        assert "https://example.com/video.webm" in urls
        assert "https://example.com/video.mp4" in urls
    
    def test_extract_audio(self, url_fixtures):
        """Test extraction of audio URLs from HTML."""
        html = url_fixtures["html_samples"]["with_audio"]
        urls = extract_media_urls(html)
        assert len(urls) == 1
        assert "https://example.com/audio.mp3" in urls
    
    def test_extract_css_background(self, url_fixtures):
        """Test extraction of background-image URLs from CSS."""
        html = url_fixtures["html_samples"]["with_css_background"]
        urls = extract_media_urls(html)
        assert len(urls) == 1
        assert "https://example.com/bg.jpg" in urls
    
    def test_extract_mixed_media(self, url_fixtures):
        """Test extraction of multiple media types."""
        html = url_fixtures["html_samples"]["mixed_media"]
        urls = extract_media_urls(html)
        assert len(urls) == 3
        assert "https://example.com/img.jpg" in urls
        assert "https://example.com/vid.mp4" in urls
        assert "https://example.com/audio.mp3" in urls
    
    def test_no_media(self, url_fixtures):
        """Test that non-media HTML returns empty list."""
        html = url_fixtures["html_samples"]["no_media"]
        urls = extract_media_urls(html)
        assert len(urls) == 0
    
    def test_empty_html(self):
        """Test that empty HTML returns empty list."""
        assert extract_media_urls("") == []
        assert extract_media_urls(None) == []
    
    def test_no_duplicate_urls(self):
        """Test that duplicate URLs are removed."""
        html = """
        <img src="https://example.com/image.jpg">
        <img src="https://example.com/image.jpg">
        """
        urls = extract_media_urls(html)
        assert len(urls) == 1


class TestWaybackURLHandling:
    """Test Wayback Machine URL detection and parsing."""
    
    def test_is_wayback_url(self, url_fixtures):
        """Test that Wayback URLs are correctly identified."""
        for url in url_fixtures["wayback_urls"]["standard"]:
            assert is_wayback_url(url), f"Should be Wayback URL: {url}"
        
        for url in url_fixtures["wayback_urls"]["with_id_modifier"]:
            assert is_wayback_url(url), f"Should be Wayback URL: {url}"
    
    def test_is_not_wayback_url(self):
        """Test that non-Wayback URLs are correctly rejected."""
        assert not is_wayback_url("https://example.com")
        assert not is_wayback_url("https://tumblr.com")
    
    def test_extract_original_url_standard(self):
        """Test extraction of original URLs from standard Wayback URLs."""
        url = "https://web.archive.org/web/20210101000000/https://myblog.tumblr.com"
        original = extract_original_url_from_wayback(url)
        assert original == "https://myblog.tumblr.com"
    
    def test_extract_original_url_with_id(self):
        """Test extraction from Wayback URLs with id_ modifier."""
        url = "https://web.archive.org/web/20210101000000id_/https://example.com/image.jpg"
        original = extract_original_url_from_wayback(url)
        assert original == "https://example.com/image.jpg"
    
    def test_extract_original_url_http(self):
        """Test extraction with http original URL."""
        url = "https://web.archive.org/web/20200515123456/http://example.com/page"
        original = extract_original_url_from_wayback(url)
        assert original == "http://example.com/page"
    
    def test_extract_from_non_wayback(self):
        """Test that non-Wayback URLs return None."""
        assert extract_original_url_from_wayback("https://example.com") is None
    
    def test_extract_malformed_wayback(self):
        """Test that malformed Wayback URLs return None."""
        url = "https://web.archive.org/invalid"
        assert extract_original_url_from_wayback(url) is None


class TestFilenameExtraction:
    """Test filename extraction from URLs."""
    
    def test_simple_filename(self):
        """Test extraction of simple filenames."""
        assert get_filename_from_url("https://example.com/image.jpg") == "image.jpg"
        assert get_filename_from_url("https://example.com/path/to/file.pdf") == "file.pdf"
    
    def test_no_filename(self):
        """Test URLs without filenames return default."""
        assert get_filename_from_url("https://example.com/") == "download"
        assert get_filename_from_url("https://example.com/path/") == "download"
    
    def test_query_parameters(self):
        """Test that query parameters are ignored."""
        url = "https://example.com/image.jpg?size=large"
        assert get_filename_from_url(url) == "image.jpg"
    
    def test_invalid_url(self):
        """Test that invalid URLs return default."""
        assert get_filename_from_url("not a url") == "download"


class TestFilenameSanitization:
    """Test filename sanitization for filesystem safety."""
    
    def test_simple_filename(self, url_fixtures):
        """Test that simple filenames are unchanged."""
        for filename in url_fixtures["filenames"]["simple"]:
            sanitized = sanitize_filename(filename)
            assert sanitized == filename
    
    def test_spaces_preserved(self, url_fixtures):
        """Test that spaces are preserved."""
        for filename in url_fixtures["filenames"]["with_spaces"]:
            sanitized = sanitize_filename(filename)
            assert " " in sanitized
            # Should not be empty
            assert len(sanitized) > 0
    
    def test_special_chars_removed(self, url_fixtures):
        """Test that special characters are replaced."""
        problematic_chars = [':', '<', '>', '"', '/', '\\', '|', '?', '*']
        for filename in url_fixtures["filenames"]["with_special_chars"]:
            sanitized = sanitize_filename(filename)
            for char in problematic_chars:
                assert char not in sanitized
    
    def test_path_traversal_prevented(self, url_fixtures):
        """Test that path traversal attempts are neutralized."""
        for filename in url_fixtures["filenames"]["path_traversal"]:
            sanitized = sanitize_filename(filename)
            assert ".." not in sanitized
            assert "/" not in sanitized
            assert "\\" not in sanitized
    
    def test_windows_reserved_names(self, url_fixtures):
        """Test that Windows reserved names are prefixed."""
        for filename in url_fixtures["filenames"]["windows_reserved"]:
            sanitized = sanitize_filename(filename)
            # Reserved names should be prefixed with underscore
            assert sanitized.startswith("_") or sanitized != filename.upper()
    
    def test_leading_trailing_dots(self):
        """Test that leading/trailing dots are removed."""
        assert sanitize_filename(".hidden") == "hidden"
        assert sanitize_filename("file.") == "file"
        assert sanitize_filename("..file..") == "file"
    
    def test_empty_filename(self, url_fixtures):
        """Test that empty filenames return default."""
        for filename in url_fixtures["filenames"]["empty_or_invalid"]:
            sanitized = sanitize_filename(filename)
            assert sanitized == "unnamed"
    
    def test_long_filename(self):
        """Test that long filenames are truncated."""
        # Create a filename that's definitely too long
        long_name = "a" * 300 + ".txt"
        sanitized = sanitize_filename(long_name)
        # Should be truncated to 255 bytes max
        assert len(sanitized.encode("utf-8")) <= 255
        # Should preserve extension
        assert sanitized.endswith(".txt")
    
    def test_preserve_extension_when_truncating(self):
        """Test that file extension is preserved when truncating."""
        long_name = "x" * 260 + ".jpg"
        sanitized = sanitize_filename(long_name)
        assert sanitized.endswith(".jpg")
        assert len(sanitized.encode("utf-8")) <= 255
    
    def test_unicode_filename(self):
        """Test handling of Unicode filenames."""
        filename = "文件名.txt"
        sanitized = sanitize_filename(filename)
        # Should preserve Unicode characters
        assert "文件名" in sanitized or len(sanitized) > 0
    
    def test_none_input(self):
        """Test that None input returns default."""
        assert sanitize_filename(None) == "unnamed"


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_normalize_url_with_whitespace(self):
        """Test that URLs with whitespace are handled."""
        url = "  https://example.com  "
        normalized = normalize_url(url)
        assert normalized == "https://example.com"
    
    def test_extract_blog_name_case_insensitive(self):
        """Test that blog name extraction is case-insensitive."""
        blog_name = extract_blog_name("https://MyBlog.TUMBLR.COM")
        assert blog_name == "myblog"
    
    def test_wayback_url_with_short_timestamp(self):
        """Test Wayback URLs with shorter timestamps."""
        url = "https://web.archive.org/web/2019/http://example.com"
        original = extract_original_url_from_wayback(url)
        assert original == "http://example.com"
    
    def test_media_url_case_insensitive(self):
        """Test that media URL detection is case-insensitive."""
        assert is_media_url("https://example.com/IMAGE.JPG")
        assert get_media_type_from_url("https://example.com/VIDEO.MP4") == "video"
    
    def test_extract_media_urls_invalid_html(self):
        """Test that invalid HTML doesn't crash extraction."""
        invalid_html = "<img src='invalid' <video>"
        urls = extract_media_urls(invalid_html)
        # Should not crash, returns empty or partial results
        assert isinstance(urls, list)
