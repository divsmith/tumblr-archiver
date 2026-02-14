"""
Example usage of the External Embed Handler.

This script demonstrates how to detect and download external video embeds
from Tumblr posts (YouTube, Vimeo, Dailymotion, etc.).
"""

from datetime import datetime, timezone
from pathlib import Path

from src.tumblr_archiver.embeds import EmbedHandler
from src.tumblr_archiver.embed_downloaders import EmbedDownloader


def example_embed_detection():
    """Example: Detect external embeds from HTML."""
    print("=" * 60)
    print("Example 1: Detecting External Embeds")
    print("=" * 60)
    
    handler = EmbedHandler()
    
    # Sample HTML with YouTube and Vimeo embeds
    html = """
    <div class="tumblr-post">
        <h2>Check out these videos!</h2>
        <iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ" width="560" height="315"></iframe>
        <p>And here's another one:</p>
        <iframe src="https://player.vimeo.com/video/123456789"></iframe>
        <a href="https://www.youtube.com/watch?v=test123">Direct YouTube link</a>
    </div>
    """
    
    # Detect embeds
    embeds = handler.detect_embeds(
        html=html,
        post_url="https://example.tumblr.com/post/987654321",
        post_id="987654321",
        timestamp=datetime.now(timezone.utc)
    )
    
    print(f"\nDetected {len(embeds)} embed(s):\n")
    for idx, embed in enumerate(embeds, 1):
        print(f"{idx}. {embed.notes}")
        print(f"   URL: {embed.original_url}")
        print(f"   Filename: {embed.filename}")
        print(f"   Status: {embed.status}")
        print()


def example_embed_downloading():
    """Example: Download external embeds (requires yt-dlp)."""
    print("=" * 60)
    print("Example 2: Downloading External Embeds")
    print("=" * 60)
    
    # Create output directory
    output_dir = Path("downloads/embeds")
    downloader = EmbedDownloader(output_dir)
    
    # Check if yt-dlp is available
    if not downloader.is_available():
        print("\n⚠️  yt-dlp is not installed.")
        print("Install it with: pip install yt-dlp")
        print("\nWithout yt-dlp, embeds will be detected but not downloaded.")
        return
    
    print(f"\n✓ yt-dlp is available. Ready to download embeds.")
    print(f"✓ Output directory: {output_dir}")
    
    # Example: Get info about a video without downloading
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    print(f"\nGetting info for: {url}")
    
    info = downloader.get_embed_info(url)
    if info:
        print(f"  Title: {info.get('title')}")
        print(f"  Duration: {info.get('duration')}s")
        print(f"  Uploader: {info.get('uploader')}")
    else:
        print("  Could not retrieve info")


def example_supported_platforms():
    """Example: Check which platforms are supported."""
    print("=" * 60)
    print("Example 3: Checking Supported Platforms")
    print("=" * 60)
    
    handler = EmbedHandler()
    
    test_urls = [
        "https://www.youtube.com/watch?v=abc123",
        "https://youtu.be/abc123",
        "https://vimeo.com/123456789",
        "https://www.dailymotion.com/video/x8abcde",
        "https://facebook.com/video/123",  # Not supported
        "https://twitter.com/status/123",  # Not supported
    ]
    
    print("\nTesting URL support:\n")
    for url in test_urls:
        supported = handler.is_supported_embed(url)
        status = "✓ Supported" if supported else "✗ Not supported"
        print(f"{status}: {url}")


def example_integration():
    """Example: Full integration with existing archiver."""
    print("\n" + "=" * 60)
    print("Example 4: Integration with Tumblr Archiver")
    print("=" * 60)
    
    print("""
To integrate embed detection into your archiver:

1. Parse Tumblr posts with TumblrParser (existing)
2. Extract embeds with EmbedHandler (new):
   
   handler = EmbedHandler()
   embeds = handler.detect_embeds(
       html=post_html,
       post_url=post.post_url,
       post_id=post.post_id,
       timestamp=post.timestamp
   )

3. Add embeds to the post's media_items:
   
   post.media_items.extend(embeds)

4. Optionally download with EmbedDownloader (new):
   
   downloader = EmbedDownloader(output_dir)
   if downloader.is_available():
       for embed in embeds:
           result = downloader.download_embed(embed)
           # Update manifest with result
   else:
       # Store URLs only, mark as not downloaded

5. The rest of your archiver workflow remains the same!
   - Checksum calculation
   - Deduplication
   - Manifest updates
   - etc.
    """)


if __name__ == "__main__":
    print("\n🎬 External Embed Handler Examples\n")
    
    # Run examples
    example_embed_detection()
    print("\n")
    
    example_supported_platforms()
    print("\n")
    
    example_embed_downloading()
    print("\n")
    
    example_integration()
    
    print("\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60)
