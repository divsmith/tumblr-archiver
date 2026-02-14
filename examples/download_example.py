"""
Example usage of the Download Manager.

This script demonstrates how to use the DownloadManager class for downloading
media files from Tumblr.
"""

import asyncio
from pathlib import Path

from tumblr_archiver.downloader import DownloadManager, RateLimiter, RetryStrategy


async def download_example():
    """Example of downloading files with the DownloadManager."""
    
    # Configure rate limiter and retry strategy
    rate_limiter = RateLimiter(rate=5.0)  # 5 requests per second
    retry_strategy = RetryStrategy(
        max_retries=3,
        base_backoff=1.0,
        max_backoff=32.0
    )
    
    # Create download manager
    output_dir = Path("./downloads")
    output_dir.mkdir(exist_ok=True)
    
    async with DownloadManager(
        output_dir=str(output_dir),
        rate_limiter=rate_limiter,
        retry_strategy=retry_strategy,
        max_concurrent=5
    ) as manager:
        
        # Example 1: Download an image
        print("Downloading image...")
        result = await manager.download_image(
            url="https://64.media.tumblr.com/example_image.jpg",
            post_id="123456789",
            metadata={"source": "tumblr", "post_type": "photo"},
            index=0
        )
        
        print(f"Image download status: {result.status}")
        if result.status == "success":
            print(f"  Filename: {result.filename}")
            print(f"  Size: {result.byte_size} bytes")
            print(f"  Checksum: {result.checksum}")
            print(f"  Duration: {result.duration:.2f}s")
        
        # Example 2: Download a video
        print("\nDownloading video...")
        result = await manager.download_video(
            url="https://va.media.tumblr.com/example_video.mp4",
            post_id="987654321",
            metadata={"source": "tumblr", "post_type": "video"},
            index=0
        )
        
        print(f"Video download status: {result.status}")
        
        # Example 3: Download with progress callback
        def progress_callback(bytes_downloaded, total_bytes):
            if total_bytes > 0:
                percent = (bytes_downloaded / total_bytes) * 100
                print(f"\rProgress: {percent:.1f}%", end="", flush=True)
        
        print("\nDownloading with progress tracking...")
        result = await manager.download_file(
            url="https://example.com/large_file.jpg",
            filename="large_image.jpg",
            metadata={"source": "tumblr"},
            progress_callback=progress_callback
        )
        print()  # New line after progress
        
        # Example 4: Download multiple files concurrently
        print("\nDownloading multiple files...")
        urls_and_ids = [
            ("https://example.com/image1.jpg", "100"),
            ("https://example.com/image2.jpg", "101"),
            ("https://example.com/image3.jpg", "102"),
        ]
        
        tasks = [
            manager.download_image(url, post_id, index=0)
            for url, post_id in urls_and_ids
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful = sum(1 for r in results if not isinstance(r, Exception) and r.status == "success")
        print(f"Downloaded {successful}/{len(results)} files successfully")
        
        # Example 5: Resume a partial download
        print("\nResume download example...")
        result = await manager.download_with_resume(
            url="https://example.com/image.jpg",
            filename="resumed_image.jpg",
            metadata={"source": "tumblr"}
        )
        
        print(f"Resume download status: {result.status}")


async def error_handling_example():
    """Example of error handling with the DownloadManager."""
    
    async with DownloadManager(output_dir="./downloads") as manager:
        
        # Example 1: Handle missing media
        print("Attempting to download missing media...")
        result = await manager.download_image(
            url="https://example.com/nonexistent.jpg",
            post_id="404_post"
        )
        
        if result.status == "missing":
            print(f"Media not found: {result.error_message}")
            if result.media_missing_on_tumblr:
                print("  -> This media is confirmed missing from Tumblr")
        
        # Example 2: Handle download errors
        print("\nAttempting download with error...")
        result = await manager.download_image(
            url="https://invalid-domain-example-123456.com/image.jpg",
            post_id="error_post"
        )
        
        if result.status == "error":
            print(f"Download error: {result.error_message}")


def main():
    """Main entry point."""
    print("=== Download Manager Example ===\n")
    
    # Note: These examples use placeholder URLs
    # Replace with actual URLs for real usage
    print("Note: Update URLs with actual media URLs before running\n")
    
    # Run the async examples
    # asyncio.run(download_example())
    # asyncio.run(error_handling_example())
    
    print("\nUncomment the asyncio.run() calls above to execute the examples")


if __name__ == "__main__":
    main()
