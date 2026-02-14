"""
External embed downloader using yt-dlp.

This module provides the EmbedDownloader class for downloading external
video embeds. Uses yt-dlp if available, otherwise gracefully degrades.
"""

import logging
from pathlib import Path
from typing import Callable, Optional

from .models import MediaItem

logger = logging.getLogger(__name__)

# Type alias for progress callbacks
ProgressCallback = Callable[[int, Optional[int]], None]


class EmbedDownloadError(Exception):
    """Exception raised when embed download fails."""
    
    def __init__(self, message: str, url: Optional[str] = None):
        """Initialize embed download error.
        
        Args:
            message: Error message
            url: URL that failed to download
        """
        super().__init__(message)
        self.url = url


class EmbedDownloader:
    """
    Downloads external video embeds using yt-dlp.
    
    Features:
    - Downloads videos from YouTube, Vimeo, Dailymotion, and more
    - Optional yt-dlp dependency (gracefully handles if not installed)
    - Progress callback support
    - Configurable output format and quality
    - Returns updated MediaItem with download status
    
    Note:
        yt-dlp is an optional dependency. If not installed, downloads will
        fail gracefully with appropriate error messages.
    
    Example:
        ```python
        downloader = EmbedDownloader(output_dir=Path("downloads/embeds"))
        
        if downloader.is_available():
            media_item = MediaItem(...)
            result = await downloader.download_embed(
                media_item,
                progress_callback=lambda d, t: print(f"{d}/{t}")
            )
            print(f"Downloaded: {result.status}")
        else:
            print("yt-dlp not available")
        ```
    """
    
    def __init__(self, output_dir: Path):
        """
        Initialize the embed downloader.
        
        Args:
            output_dir: Directory where embed videos will be saved
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if yt-dlp is available
        self._yt_dlp_available = self._check_yt_dlp()
        
        if not self._yt_dlp_available:
            logger.warning(
                "yt-dlp is not installed. Embed downloads will not be available. "
                "Install with: pip install yt-dlp"
            )
    
    def _check_yt_dlp(self) -> bool:
        """
        Check if yt-dlp is available.
        
        Returns:
            True if yt-dlp can be imported, False otherwise
        """
        try:
            import yt_dlp
            return True
        except ImportError:
            return False
    
    def is_available(self) -> bool:
        """
        Check if the downloader is available (yt-dlp installed).
        
        Returns:
            True if yt-dlp is available and downloads can be performed
            
        Example:
            >>> downloader = EmbedDownloader(Path("downloads"))
            >>> if downloader.is_available():
            ...     print("Ready to download embeds")
        """
        return self._yt_dlp_available
    
    def can_download(self, url: str) -> bool:
        """
        Check if a URL can be downloaded.
        
        Args:
            url: URL to check
            
        Returns:
            True if yt-dlp is available and can likely download this URL
            
        Example:
            >>> downloader = EmbedDownloader(Path("downloads"))
            >>> downloader.can_download("https://youtube.com/watch?v=abc123")
            True
        """
        if not self._yt_dlp_available:
            return False
        
        # Could add more sophisticated checking here
        # For now, assume yt-dlp can handle any URL if it's available
        return True
    
    def download_embed(
        self,
        media_item: MediaItem,
        progress_callback: Optional[ProgressCallback] = None
    ) -> MediaItem:
        """
        Download an external video embed.
        
        Args:
            media_item: MediaItem representing the embed to download
            progress_callback: Optional callback for progress updates.
                Called with (downloaded_bytes, total_bytes).
            
        Returns:
            Updated MediaItem with download status and file information
            
        Raises:
            EmbedDownloadError: If download fails
            
        Example:
            >>> downloader = EmbedDownloader(Path("downloads"))
            >>> item = MediaItem(
            ...     post_id="123",
            ...     post_url="https://blog.tumblr.com/post/123",
            ...     timestamp=datetime.now(timezone.utc),
            ...     media_type="video",
            ...     filename="123_youtube_abc.mp4",
            ...     original_url="https://youtube.com/watch?v=abc",
            ...     retrieved_from="tumblr",
            ...     status="missing"
            ... )
            >>> result = downloader.download_embed(item)
            >>> result.status
            'downloaded'
        """
        if not self._yt_dlp_available:
            logger.error("Cannot download embed: yt-dlp not installed")
            media_item.status = "error"
            media_item.notes = "yt-dlp not installed"
            return media_item
        
        try:
            import yt_dlp
            
            output_path = self.output_dir / media_item.filename
            
            # Configure yt-dlp options
            ydl_opts = {
                'format': 'best[ext=mp4]/best',  # Prefer MP4
                'outtmpl': str(output_path.with_suffix('')),  # yt-dlp adds extension
                'quiet': True,
                'no_warnings': True,
                'noprogress': True,
            }
            
            # Add progress hook if callback provided
            if progress_callback:
                def progress_hook(d):
                    if d['status'] == 'downloading':
                        downloaded = d.get('downloaded_bytes', 0)
                        total = d.get('total_bytes') or d.get('total_bytes_estimate')
                        progress_callback(downloaded, total)
                
                ydl_opts['progress_hooks'] = [progress_hook]
            
            logger.info(f"Downloading embed from {media_item.original_url}")
            
            # Download the video
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(media_item.original_url, download=True)
                
                # Find the actual downloaded file (yt-dlp may add/change extension)
                downloaded_file = self._find_downloaded_file(output_path)
                
                if downloaded_file and downloaded_file.exists():
                    # Update media item with success info
                    media_item.filename = downloaded_file.name
                    media_item.byte_size = downloaded_file.stat().st_size
                    media_item.status = "downloaded"
                    media_item.notes = f"Downloaded via yt-dlp from {info.get('extractor', 'unknown')}"
                    
                    logger.info(
                        f"Successfully downloaded embed to {downloaded_file} "
                        f"({media_item.byte_size} bytes)"
                    )
                else:
                    raise EmbedDownloadError(
                        "Download completed but file not found",
                        url=media_item.original_url
                    )
            
            return media_item
            
        except Exception as e:
            logger.error(f"Failed to download embed {media_item.original_url}: {e}")
            media_item.status = "error"
            media_item.notes = f"Download failed: {str(e)}"
            return media_item
    
    def _find_downloaded_file(self, base_path: Path) -> Optional[Path]:
        """
        Find the downloaded file (yt-dlp may change extension).
        
        Args:
            base_path: Base path without extension
            
        Returns:
            Path to downloaded file, or None if not found
        """
        # Check common video extensions
        for ext in ['.mp4', '.webm', '.mkv', '.flv', '.avi', '.mov']:
            candidate = base_path.with_suffix(ext)
            if candidate.exists():
                return candidate
        
        # Check if file exists with original name
        if base_path.exists():
            return base_path
        
        # Look for any file with the base name
        parent = base_path.parent
        basename = base_path.stem
        
        for file in parent.glob(f"{basename}.*"):
            if file.is_file():
                return file
        
        return None
    
    def get_embed_info(self, url: str) -> Optional[dict]:
        """
        Get information about an embed without downloading it.
        
        Args:
            url: URL of the embed
            
        Returns:
            Dictionary with embed information, or None if unavailable
            
        Example:
            >>> downloader = EmbedDownloader(Path("downloads"))
            >>> info = downloader.get_embed_info("https://youtube.com/watch?v=abc")
            >>> if info:
            ...     print(f"Title: {info.get('title')}")
            ...     print(f"Duration: {info.get('duration')}s")
        """
        if not self._yt_dlp_available:
            return None
        
        try:
            import yt_dlp
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Return simplified info dict
                return {
                    'title': info.get('title'),
                    'duration': info.get('duration'),
                    'description': info.get('description'),
                    'uploader': info.get('uploader'),
                    'thumbnail': info.get('thumbnail'),
                    'extractor': info.get('extractor'),
                    'format': info.get('format'),
                }
        except Exception as e:
            logger.warning(f"Failed to get embed info for {url}: {e}")
            return None
