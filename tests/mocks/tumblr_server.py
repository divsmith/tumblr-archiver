"""
Mock Tumblr server for integration testing.

Provides a mock server that simulates Tumblr's HTML pages and media responses
for testing the complete archival workflow.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

from aioresponses import aioresponses


class MockContextManager:
    """
    Context manager wrapper for mock servers.
    
    Properly sets up aioresponses context with server responses.
    """
    
    def __init__(self, server):
        """Initialize with a mock server instance."""
        self.server = server
        self.mocker = None
    
    def __enter__(self):
        """Enter context and set up responses."""
        self.mocker = aioresponses()
        self.mocker.__enter__()
        self.server._setup_responses(self.mocker)
        return self.mocker
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and clean up."""
        if self.mocker:
            return self.mocker.__exit__(exc_type, exc_val, exc_tb)


class MockTumblrServer:
    """
    Mock server for simulating Tumblr blog pages and media downloads.
    
    Provides configurable responses for:
    - Blog HTML pages with pagination
    - Media file downloads
    - 404 errors for testing fallback behavior
    
    Example:
        ```python
        server = MockTumblrServer("testblog")
        server.add_post("123", "https://media.url/image.jpg", b"image data")
        
        with server.mock():
            # Make requests that will be intercepted
            response = await client.get("https://testblog.tumblr.com")
        ```
    """
    
    def __init__(self, blog_name: str):
        """
        Initialize mock server for a blog.
        
        Args:
            blog_name: Name of the blog to mock
        """
        self.blog_name = blog_name
        self.posts: List[Dict] = []
        self.media_urls: Dict[str, bytes] = {}
        self.failing_urls: Set[str] = set()
        self._mocker: Optional[aioresponses] = None
    
    def add_post(
        self,
        post_id: str,
        media_url: str,
        media_content: bytes,
        timestamp: Optional[datetime] = None,
        is_reblog: bool = False,
        media_type: str = "image"
    ) -> None:
        """
        Add a post to the mock blog.
        
        Args:
            post_id: Unique post identifier
            media_url: URL where the media is hosted
            media_content: Binary content of the media file
            timestamp: Post timestamp (defaults to now)
            is_reblog: Whether this is a reblogged post
            media_type: Type of media (image, gif, video)
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        self.posts.append({
            "post_id": post_id,
            "media_url": media_url,
            "timestamp": timestamp,
            "is_reblog": is_reblog,
            "media_type": media_type,
        })
        self.media_urls[media_url] = media_content
    
    def mark_url_as_failing(self, url: str) -> None:
        """
        Mark a URL as failing (will return 404).
        
        Args:
            url: URL that should fail
        """
        self.failing_urls.add(url)
    
    def mock(self) -> aioresponses:
        """
        Get aioresponses mock context manager.
        
        Returns:
            aioresponses instance configured with blog responses
        """
        # Create the mocker but don't set up responses yet
        # They'll be set up when the context manager is entered
        return MockContextManager(self)
    
    def _setup_responses(self, mocker: aioresponses) -> None:
        """Set up all mock responses on the given mocker."""
        # Mock blog pages with pagination
        for page in range(1, 10):  # Support up to 10 pages
            url = f"https://{self.blog_name}.tumblr.com"
            if page > 1:
                url += f"/page/{page}"
            
            # Generate HTML for this page
            html = self._generate_page_html(page)
            
            if html:
                mocker.get(url, status=200, body=html, content_type='text/html')
            else:
                # No more posts, return empty page
                mocker.get(url, status=200, body=self._generate_empty_page(), content_type='text/html')
        
        # Mock media URLs
        for media_url, content in self.media_urls.items():
            if media_url in self.failing_urls:
                mocker.get(media_url, status=404)
            else:
                mocker.get(
                    media_url,
                    status=200,
                    body=content,
                    headers={"Content-Length": str(len(content))},
                    content_type='application/octet-stream'
                )
    
    def _generate_page_html(self, page: int, posts_per_page: int = 10) -> str:
        """
        Generate HTML for a blog page.
        
        Args:
            page: Page number (1-indexed)
            posts_per_page: Number of posts per page
            
        Returns:
            HTML string for the page
        """
        start_idx = (page - 1) * posts_per_page
        end_idx = start_idx + posts_per_page
        page_posts = self.posts[start_idx:end_idx]
        
        if not page_posts:
            return ""
        
        posts_html = []
        for post in page_posts:
            post_html = self._generate_post_html(post)
            posts_html.append(post_html)
        
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{self.blog_name} - Tumblr</title>
</head>
<body>
    <div id="content">
        {''.join(posts_html)}
    </div>
</body>
</html>"""
    
    def _generate_post_html(self, post: Dict) -> str:
        """
        Generate HTML for a single post.
        
        Args:
            post: Post dictionary with metadata
            
        Returns:
            HTML string for the post
        """
        post_id = post["post_id"]
        media_url = post["media_url"]
        timestamp = post["timestamp"]
        is_reblog = post["is_reblog"]
        media_type = post["media_type"]
        
        reblog_class = " is-reblog" if is_reblog else ""
        reblog_info = ""
        if is_reblog:
            reblog_info = '''
                <div class="reblogged-from">
                    Reblogged from <a href="https://otherblog.tumblr.com">otherblog</a>
                </div>'''
        
        # Format timestamp
        iso_time = timestamp.isoformat()
        readable_time = timestamp.strftime("%B %d, %Y")
        
        # Create appropriate media tag
        if media_type == "video":
            media_tag = f'<video src="{media_url}" controls></video>'
        elif media_type == "gif":
            media_tag = f'<img src="{media_url}" data-type="gif" alt="GIF">'
        else:
            media_tag = f'<img src="{media_url}" alt="Image">'
        
        return f'''
        <article class="post{reblog_class}" data-post-id="{post_id}" id="post-{post_id}">
            <div class="post-header">
                <time datetime="{iso_time}">{readable_time}</time>
                <a href="/post/{post_id}" class="permalink">Permalink</a>
                {reblog_info}
            </div>
            <div class="post-content">
                <p>Post {post_id}</p>
                {media_tag}
            </div>
        </article>'''
    
    def _generate_empty_page(self) -> str:
        """Generate HTML for an empty page (end of pagination)."""
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{self.blog_name} - Tumblr</title>
</head>
<body>
    <div id="content">
        <!-- No posts -->
    </div>
</body>
</html>"""


class MockWaybackServer:
    """
    Mock server for simulating Internet Archive Wayback Machine.
    
    Provides responses for CDX API and snapshot retrieval.
    """
    
    def __init__(self):
        """Initialize mock Wayback server."""
        self.snapshots: Dict[str, List[Dict]] = {}
        self.snapshot_content: Dict[str, bytes] = {}
        self._mocker: Optional[aioresponses] = None
    
    def add_snapshot(
        self,
        original_url: str,
        snapshot_url: str,
        content: bytes,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Add a snapshot for a URL.
        
        Args:
            original_url: Original URL that was archived
            snapshot_url: Wayback Machine snapshot URL
            content: Binary content of the archived file
            timestamp: Snapshot timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        if original_url not in self.snapshots:
            self.snapshots[original_url] = []
        
        self.snapshots[original_url].append({
            "timestamp": timestamp,
            "snapshot_url": snapshot_url,
        })
        self.snapshot_content[snapshot_url] = content
    
    def mock(self) -> aioresponses:
        """
        Get aioresponses mock context manager.
        
        Returns:
            aioresponses instance configured with Wayback responses
        """
        return MockContextManager(self)
    
    def _setup_responses(self, mocker: aioresponses) -> None:
        """Set up all mock responses on the given mocker."""
        # Mock CDX API responses
        for original_url, snapshots in self.snapshots.items():
            cdx_url = f"https://web.archive.org/cdx/search/cdx?url={original_url}&output=json&limit=1"
            
            if snapshots:
                # Return the most recent snapshot
                snapshot = snapshots[-1]
                timestamp_str = snapshot["timestamp"].strftime("%Y%m%d%H%M%S")
                cdx_response = [
                    ["urlkey", "timestamp", "original", "mimetype", "statuscode", "digest", "length"],
                    [
                        original_url.replace("://", ",").replace("/", ","),
                        timestamp_str,
                        original_url,
                        "image/jpeg",
                        "200",
                        "ABC123",
                        str(len(self.snapshot_content[snapshot["snapshot_url"]]))
                    ]
                ]
                mocker.get(cdx_url, status=200, payload=cdx_response)
            else:
                # No snapshots available
                mocker.get(cdx_url, status=200, payload=[])
        
        # Mock snapshot content
        for snapshot_url, content in self.snapshot_content.items():
            mocker.get(
                snapshot_url,
                status=200,
                body=content,
                headers={"Content-Length": str(len(content))},
                content_type='application/octet-stream'
            )
