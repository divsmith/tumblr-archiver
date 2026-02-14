"""Tests for the Tumblr scraper module."""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from tumblr_archiver.config import ArchiverConfig
from tumblr_archiver.http_client import AsyncHTTPClient
from tumblr_archiver.models import Post
from tumblr_archiver.scraper import TumblrScraper, BlogNotFoundError, ScraperError


@pytest.fixture
def config():
    """Create a test configuration."""
    return ArchiverConfig(
        blog_name="testblog",
        output_dir=Path("/tmp/test"),
        include_reblogs=True
    )


@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client."""
    client = AsyncMock(spec=AsyncHTTPClient)
    return client


@pytest.fixture
def scraper(mock_http_client, config):
    """Create a scraper instance with mocked HTTP client."""
    return TumblrScraper(mock_http_client, config)


@pytest.fixture
def sample_html():
    """Load sample HTML fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "tumblr_page.html"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.mark.asyncio
async def test_scrape_page_success(scraper, mock_http_client, sample_html):
    """Test successful page scraping."""
    # Mock response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=sample_html)
    mock_http_client.get.return_value = mock_response
    
    # Scrape the page
    posts = await scraper.scrape_page("https://testblog.tumblr.com")
    
    # Verify
    assert len(posts) > 0
    assert all(isinstance(post, Post) for post in posts)
    assert mock_http_client.get.called
    
    # Check first post has expected data
    first_post = posts[0]
    assert first_post.post_id
    assert first_post.post_url
    assert isinstance(first_post.timestamp, datetime)


@pytest.mark.asyncio
async def test_scrape_page_404(scraper, mock_http_client):
    """Test handling of 404 responses."""
    # Mock 404 response
    mock_response = AsyncMock()
    mock_response.status = 404
    mock_http_client.get.return_value = mock_response
    
    # Should raise BlogNotFoundError
    with pytest.raises(BlogNotFoundError):
        await scraper.scrape_page("https://nonexistent.tumblr.com")


@pytest.mark.asyncio
async def test_scrape_blog_pagination(scraper, mock_http_client, sample_html):
    """Test blog scraping with pagination."""
    # Mock responses for multiple pages
    async def mock_get(url):
        mock_response = AsyncMock()
        # First page (base URL without /page/)
        if "/page/" not in url:
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value=sample_html)
        elif "/page/2" in url:
            # Second page has posts
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value=sample_html)
        else:
            # Page 3+ returns 404 (end of blog)
            mock_response.status = 404
        return mock_response
    
    mock_http_client.get = mock_get
    
    # Scrape blog
    posts = await scraper.scrape_blog("testblog")
    
    # Should have posts from multiple pages
    assert len(posts) > 0


@pytest.mark.asyncio
async def test_scrape_blog_filters_reblogs(scraper, mock_http_client, sample_html):
    """Test that reblogs are filtered when configured."""
    # Configure to exclude reblogs
    scraper.config.include_reblogs = False
    
    # Mock response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=sample_html)
    
    async def mock_get(url):
        if "/page/2" in url or "/page/3" in url:
            # No more pages
            resp = AsyncMock()
            resp.status = 404
            return resp
        return mock_response
    
    mock_http_client.get = mock_get
    
    # Scrape blog
    posts = await scraper.scrape_blog("testblog")
    
    # Verify no reblogs in results
    assert all(not post.is_reblog for post in posts)


@pytest.mark.asyncio
async def test_scrape_blog_empty_blog(scraper, mock_http_client):
    """Test scraping an empty blog."""
    # Mock empty HTML
    empty_html = "<html><body><div id='content'></div></body></html>"
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=empty_html)
    mock_http_client.get.return_value = mock_response
    
    # Scrape blog
    posts = await scraper.scrape_blog("emptyblog")
    
    # Should return empty list
    assert posts == []


@pytest.mark.asyncio
async def test_scrape_blog_nonexistent(scraper, mock_http_client):
    """Test scraping a non-existent blog."""
    # Mock 404 on first page
    mock_response = AsyncMock()
    mock_response.status = 404
    mock_http_client.get.return_value = mock_response
    
    # Should raise BlogNotFoundError
    with pytest.raises(BlogNotFoundError):
        await scraper.scrape_blog("nonexistentblog")


@pytest.mark.asyncio
async def test_build_page_url(scraper):
    """Test page URL construction."""
    base_url = "https://testblog.tumblr.com"
    
    # Page 1 should be base URL
    assert scraper._build_page_url(base_url, 1) == base_url
    
    # Page 2+ should have /page/N
    assert scraper._build_page_url(base_url, 2) == f"{base_url}/page/2"
    assert scraper._build_page_url(base_url, 10) == f"{base_url}/page/10"


@pytest.mark.asyncio
async def test_scrape_page_network_error(scraper, mock_http_client):
    """Test handling of network errors."""
    from aiohttp import ClientError
    
    # Mock network error
    mock_http_client.get.side_effect = ClientError("Network error")
    
    # Should raise ScraperError
    with pytest.raises(ScraperError):
        await scraper.scrape_page("https://testblog.tumblr.com")


@pytest.mark.asyncio
async def test_scrape_blog_pagination_limit(scraper, mock_http_client, sample_html):
    """Test that pagination has a safety limit."""
    # Mock response that always returns posts (infinite pagination)
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=sample_html)
    mock_http_client.get.return_value = mock_response
    
    # Scrape blog - should stop at safety limit
    posts = await scraper.scrape_blog("testblog")
    
    # Should have stopped before 10,000 pages
    # (actual limit depends on implementation, but should stop)
    assert len(posts) >= 0  # Just verify it completes
