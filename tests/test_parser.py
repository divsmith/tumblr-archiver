"""Tests for the Tumblr HTML parser module."""

import pytest
from datetime import datetime, timezone
from pathlib import Path

from tumblr_archiver.models import Post
from tumblr_archiver.parser import TumblrParser, ParserError


@pytest.fixture
def parser():
    """Create a parser instance."""
    return TumblrParser()


@pytest.fixture
def sample_html():
    """Load sample HTML fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "tumblr_page.html"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return f.read()


def test_parse_page_basic(parser, sample_html):
    """Test basic page parsing."""
    posts = parser.parse_page(sample_html, "https://testblog.tumblr.com")
    
    # Should find multiple posts
    assert len(posts) > 0
    
    # All should be Post objects
    assert all(isinstance(post, Post) for post in posts)
    
    # All should have required fields
    for post in posts:
        assert post.post_id
        assert post.post_url
        assert isinstance(post.timestamp, datetime)
        assert isinstance(post.is_reblog, bool)


def test_parse_post_ids(parser, sample_html):
    """Test extraction of post IDs."""
    posts = parser.parse_page(sample_html, "https://testblog.tumblr.com")
    
    # Check that specific post IDs are found
    post_ids = [post.post_id for post in posts]
    assert "123456789" in post_ids
    assert "987654321" in post_ids
    assert "555666777" in post_ids


def test_parse_timestamps(parser, sample_html):
    """Test extraction and parsing of timestamps."""
    posts = parser.parse_page(sample_html, "https://testblog.tumblr.com")
    
    # Find specific post
    post = next((p for p in posts if p.post_id == "123456789"), None)
    assert post is not None
    
    # Check timestamp
    assert post.timestamp.year == 2024
    assert post.timestamp.month == 1
    assert post.timestamp.day == 15
    # Should be in UTC
    assert post.timestamp.tzinfo == timezone.utc


def test_detect_reblogs(parser, sample_html):
    """Test reblog detection."""
    posts = parser.parse_page(sample_html, "https://testblog.tumblr.com")
    
    # Post 123456789 should NOT be a reblog
    original_post = next((p for p in posts if p.post_id == "123456789"), None)
    assert original_post is not None
    assert original_post.is_reblog is False
    
    # Post 987654321 should BE a reblog (has 'is-reblog' class and reblog attribution)
    reblog_post = next((p for p in posts if p.post_id == "987654321"), None)
    assert reblog_post is not None
    assert reblog_post.is_reblog is True


def test_extract_media_from_posts(parser, sample_html):
    """Test that media items are extracted from posts."""
    posts = parser.parse_page(sample_html, "https://testblog.tumblr.com")
    
    # Post 123456789 has an image
    post_with_image = next((p for p in posts if p.post_id == "123456789"), None)
    assert post_with_image is not None
    assert len(post_with_image.media_items) > 0
    
    # Check media item properties
    media = post_with_image.media_items[0]
    assert media.post_id == "123456789"
    assert media.media_type in ["image", "gif", "video"]
    assert media.original_url
    assert media.filename


def test_parse_photoset(parser, sample_html):
    """Test parsing of photoset posts with multiple images."""
    posts = parser.parse_page(sample_html, "https://testblog.tumblr.com")
    
    # Post 555666777 is a photoset with multiple images
    photoset_post = next((p for p in posts if p.post_id == "555666777"), None)
    assert photoset_post is not None
    
    # Should have multiple media items
    assert len(photoset_post.media_items) >= 3


def test_parse_video_post(parser, sample_html):
    """Test parsing of video posts."""
    posts = parser.parse_page(sample_html, "https://testblog.tumblr.com")
    
    # Post 111222333 has a video
    video_post = next((p for p in posts if p.post_id == "111222333"), None)
    assert video_post is not None
    
    # Should have video media items
    videos = [m for m in video_post.media_items if m.media_type == "video"]
    assert len(videos) > 0


def test_parse_gif_post(parser, sample_html):
    """Test parsing of animated GIF posts."""
    posts = parser.parse_page(sample_html, "https://testblog.tumblr.com")
    
    # Post 444555666 has a GIF
    gif_post = next((p for p in posts if p.post_id == "444555666"), None)
    assert gif_post is not None
    
    # Should have GIF media items
    gifs = [m for m in gif_post.media_items if m.media_type == "gif"]
    assert len(gifs) > 0


def test_parse_text_only_post(parser, sample_html):
    """Test parsing of text-only posts (no media)."""
    posts = parser.parse_page(sample_html, "https://testblog.tumblr.com")
    
    # Post 777888999 is text only
    text_post = next((p for p in posts if p.post_id == "777888999"), None)
    assert text_post is not None
    
    # Should have no media items
    assert len(text_post.media_items) == 0


def test_parse_post_urls(parser, sample_html):
    """Test extraction/construction of post URLs."""
    posts = parser.parse_page(sample_html, "https://testblog.tumblr.com")
    
    for post in posts:
        # All posts should have valid URLs
        assert post.post_url.startswith("http")
        assert "tumblr.com" in post.post_url
        assert f"/post/{post.post_id}" in post.post_url


def test_parse_empty_html(parser):
    """Test parsing of empty/minimal HTML."""
    empty_html = "<html><body></body></html>"
    posts = parser.parse_page(empty_html, "https://testblog.tumblr.com")
    
    # Should return empty list, not error
    assert posts == []


def test_parse_malformed_html(parser):
    """Test parsing of malformed HTML."""
    malformed_html = "<html><body><div><article"  # Incomplete
    
    # Should handle gracefully
    posts = parser.parse_page(malformed_html, "https://testblog.tumblr.com")
    
    # May return empty list or partial results
    assert isinstance(posts, list)


def test_parse_datetime_formats(parser):
    """Test parsing of various datetime formats."""
    # ISO format
    dt1 = parser._parse_datetime("2024-01-15T10:30:00+00:00")
    assert dt1 is not None
    assert dt1.year == 2024
    
    # ISO with Z
    dt2 = parser._parse_datetime("2024-01-15T10:30:00Z")
    assert dt2 is not None
    
    # Simple format
    dt3 = parser._parse_datetime("2024-01-15 10:30:00")
    assert dt3 is not None


def test_extract_post_id_from_various_formats(parser):
    """Test post ID extraction from different HTML formats."""
    from bs4 import BeautifulSoup
    
    # Test data-post-id attribute
    html1 = '<article data-post-id="123456789"></article>'
    soup1 = BeautifulSoup(html1, 'html.parser')
    post_id1 = parser._extract_post_id(soup1.find('article'))
    assert post_id1 == "123456789"
    
    # Test id attribute
    html2 = '<article id="post-987654321"></article>'
    soup2 = BeautifulSoup(html2, 'html.parser')
    post_id2 = parser._extract_post_id(soup2.find('article'))
    assert post_id2 == "987654321"
    
    # Test permalink
    html3 = '<article><a class="permalink" href="/post/555666777/title">Link</a></article>'
    soup3 = BeautifulSoup(html3, 'html.parser')
    post_id3 = parser._extract_post_id(soup3.find('article'))
    assert post_id3 == "555666777"


def test_is_reblog_detection(parser):
    """Test various reblog detection methods."""
    from bs4 import BeautifulSoup
    
    # Test class-based detection
    html1 = '<article class="post is-reblog"></article>'
    soup1 = BeautifulSoup(html1, 'html.parser')
    assert parser._is_reblog(soup1.find('article')) is True
    
    # Test reblog attribution
    html2 = '<article><div class="reblogged-from">Reblogged from someone</div></article>'
    soup2 = BeautifulSoup(html2, 'html.parser')
    assert parser._is_reblog(soup2.find('article')) is True
    
    # Test original post
    html3 = '<article class="post"></article>'
    soup3 = BeautifulSoup(html3, 'html.parser')
    assert parser._is_reblog(soup3.find('article')) is False
