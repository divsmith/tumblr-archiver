"""
Tumblr blog scraper for extracting posts and media.

This module provides the TumblrScraper class which orchestrates the scraping
of Tumblr blogs, handling pagination, retries, and structured data extraction.
"""

import logging
from typing import List

from aiohttp import ClientError

from .config import ArchiverConfig
from .http_client import AsyncHTTPClient, HTTPError
from .models import Post
from .parser import TumblrParser

logger = logging.getLogger(__name__)


class ScraperError(Exception):
    """Base exception for scraper errors."""
    pass


class BlogNotFoundError(ScraperError):
    """Exception raised when a blog is not found (404)."""
    pass


class TumblrScraper:
    """
    Scraper for Tumblr blogs that extracts posts with pagination support.
    
    Features:
    - Pagination handling (page parameter and infinite scroll detection)
    - Graceful 404 handling
    - Automatic parsing of post data
    - Support for filtering reblogs
    
    Example:
        ```python
        config = ArchiverConfig(blog_name="example", output_dir=Path("output"))
        async with AsyncHTTPClient(rate_limit=1.0) as http_client:
            scraper = TumblrScraper(http_client, config)
            posts = await scraper.scrape_blog("example")
            print(f"Found {len(posts)} posts")
        ```
    """
    
    def __init__(self, http_client: AsyncHTTPClient, config: ArchiverConfig):
        """
        Initialize the Tumblr scraper.
        
        Args:
            http_client: Configured async HTTP client for making requests
            config: Archiver configuration with blog settings
        """
        self.http_client = http_client
        self.config = config
        self.parser = TumblrParser()
        
    async def scrape_blog(self, blog_name: str) -> List[Post]:
        """
        Scrape all posts from a Tumblr blog.
        
        Iterates through all pages of a blog, extracting posts until no more
        posts are found. Handles pagination automatically.
        
        Args:
            blog_name: Name of the Tumblr blog (without .tumblr.com)
            
        Returns:
            List of Post objects containing post metadata and media
            
        Raises:
            BlogNotFoundError: If the blog does not exist (404)
            ScraperError: If scraping fails for other reasons
            
        Example:
            >>> posts = await scraper.scrape_blog("example")
            >>> print(f"Found {len(posts)} posts")
        """
        all_posts: List[Post] = []
        page_num = 1
        base_url = f"https://{blog_name}.tumblr.com"
        
        logger.info(f"Starting scrape of blog: {blog_name}")
        
        try:
            while True:
                # Construct page URL
                page_url = self._build_page_url(base_url, page_num)
                logger.debug(f"Scraping page {page_num}: {page_url}")
                
                # Scrape the page
                posts = await self.scrape_page(page_url)
                
                # If no posts found, we've reached the end
                if not posts:
                    logger.info(f"No more posts found at page {page_num}. Scraping complete.")
                    break
                
                # Filter reblogs if configured
                if not self.config.include_reblogs:
                    original_count = len(posts)
                    posts = [p for p in posts if not p.is_reblog]
                    filtered = original_count - len(posts)
                    if filtered > 0:
                        logger.debug(f"Filtered {filtered} reblogs from page {page_num}")
                
                all_posts.extend(posts)
                logger.info(f"Page {page_num}: Found {len(posts)} posts (total: {len(all_posts)})")
                
                page_num += 1
                
                # Safety check to prevent infinite loops
                if page_num > 10000:
                    logger.warning("Reached maximum page limit (10,000). Stopping.")
                    break
                    
        except BlogNotFoundError:
            if page_num == 1:
                # Blog doesn't exist
                raise
            else:
                # End of pagination - this is normal
                logger.info(f"Reached end of blog at page {page_num}")
        
        logger.info(f"Scraping complete. Total posts collected: {len(all_posts)}")
        return all_posts
    
    async def scrape_page(self, page_url: str) -> List[Post]:
        """
        Fetch and parse a single Tumblr blog page.
        
        Args:
            page_url: Full URL of the page to scrape
            
        Returns:
            List of Post objects from that page
            
        Raises:
            BlogNotFoundError: If page returns 404
            ScraperError: If scraping/parsing fails
            
        Example:
            >>> posts = await scraper.scrape_page("https://example.tumblr.com/page/2")
            >>> print(f"Found {len(posts)} posts on this page")
        """
        try:
            # Fetch the page HTML
            response = await self.http_client.get(page_url)
            
            # Check for 404
            if response.status == 404:
                logger.warning(f"Page not found (404): {page_url}")
                raise BlogNotFoundError(f"Blog page not found: {page_url}")
            
            # Read response content
            html = await response.text()
            
            # Parse the HTML
            posts = self.parser.parse_page(html, page_url)
            
            return posts
            
        except BlogNotFoundError:
            # Re-raise 404s
            raise
        except HTTPError as e:
            if e.status == 404:
                raise BlogNotFoundError(f"Blog page not found: {page_url}")
            logger.error(f"HTTP error scraping {page_url}: {e}")
            raise ScraperError(f"Failed to scrape page: {e}")
        except ClientError as e:
            logger.error(f"Client error scraping {page_url}: {e}")
            raise ScraperError(f"Network error while scraping: {e}")
        except Exception as e:
            logger.error(f"Unexpected error scraping {page_url}: {e}", exc_info=True)
            raise ScraperError(f"Unexpected error: {e}")
    
    def _build_page_url(self, base_url: str, page_num: int) -> str:
        """
        Build paginated URL for a specific page number.
        
        Tumblr uses /page/N format for pagination.
        
        Args:
            base_url: Base blog URL (e.g., "https://example.tumblr.com")
            page_num: Page number (1-indexed)
            
        Returns:
            Full URL for the specified page
            
        Example:
            >>> url = scraper._build_page_url("https://example.tumblr.com", 2)
            >>> print(url)
            "https://example.tumblr.com/page/2"
        """
        if page_num == 1:
            return base_url
        return f"{base_url}/page/{page_num}"
