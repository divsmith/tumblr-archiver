"""
Example usage of the Media Recovery module.

This script demonstrates how to use the MediaRecovery class to recover
missing media files from the Internet Archive.
"""

import asyncio
import logging
from pathlib import Path

from tumblr_archiver.config import ArchiverConfig
from tumblr_archiver.wayback_client import WaybackClient
from tumblr_archiver.recovery import MediaRecovery, RecoveryStatus


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def example_single_recovery():
    """Example: Recover a single media file."""
    print("\n=== Example 1: Single Media Recovery ===\n")
    
    # Set up configuration
    config = ArchiverConfig(
        blog_url="https://example.tumblr.com",
        output_dir=Path("./downloads"),
        wayback_enabled=True,
        wayback_max_snapshots=5
    )
    
    # Initialize Wayback client
    wayback_client = WaybackClient(
        user_agent="TumblrArchiver/1.0 Example",
        timeout=30
    )
    
    # Initialize recovery handler
    async with MediaRecovery(wayback_client, config) as recovery:
        # Try to recover a missing media file
        media_url = "https://64.media.tumblr.com/abc123/tumblr_abc123_1280.jpg"
        post_url = "https://example.tumblr.com/post/123456789"
        output_path = Path("./downloads/recovered_image.jpg")
        
        print(f"Attempting to recover: {media_url}")
        print(f"From post: {post_url}")
        print(f"Output path: {output_path}\n")
        
        result = await recovery.recover_media(
            media_url=media_url,
            post_url=post_url,
            output_path=output_path
        )
        
        # Display results
        print(f"Status: {result.status.value}")
        
        if result.status == RecoveryStatus.SUCCESS:
            print(f"✓ Successfully recovered!")
            print(f"  Strategy: {result.strategy}")
            print(f"  Snapshot URL: {result.snapshot_url}")
            print(f"  Timestamp: {result.timestamp}")
            print(f"  File size: {result.file_size:,} bytes")
            print(f"  Saved to: {result.local_path}")
        elif result.status == RecoveryStatus.NOT_FOUND:
            print(f"✗ Media not found in Internet Archive")
            print(f"  {result.error_message}")
        else:
            print(f"✗ Recovery failed")
            print(f"  Error: {result.error_message}")


async def example_multiple_recovery():
    """Example: Recover multiple media files concurrently."""
    print("\n=== Example 2: Multiple Media Recovery ===\n")
    
    # Set up configuration
    config = ArchiverConfig(
        blog_url="https://example.tumblr.com",
        output_dir=Path("./downloads"),
        wayback_enabled=True
    )
    
    # Initialize Wayback client
    wayback_client = WaybackClient(
        user_agent="TumblrArchiver/1.0 Example"
    )
    
    # Media files to recover
    media_items = [
        (
            "https://64.media.tumblr.com/abc123/tumblr_abc123_1280.jpg",
            "https://example.tumblr.com/post/123",
            Path("./downloads/image1.jpg")
        ),
        (
            "https://64.media.tumblr.com/def456/tumblr_def456_500.jpg",
            "https://example.tumblr.com/post/456",
            Path("./downloads/image2.jpg")
        ),
        (
            "https://va.media.tumblr.com/tumblr_ghi789.mp4",
            "https://example.tumblr.com/post/789",
            Path("./downloads/video1.mp4")
        ),
    ]
    
    print(f"Attempting to recover {len(media_items)} media files...\n")
    
    # Recover with concurrency
    async with MediaRecovery(wayback_client, config) as recovery:
        results = await recovery.recover_multiple_media(
            media_items,
            max_concurrent=2
        )
        
        # Display individual results
        for i, result in enumerate(results, 1):
            print(f"\nMedia {i}: {result.media_url}")
            print(f"  Status: {result.status.value}")
            
            if result.status == RecoveryStatus.SUCCESS:
                print(f"  ✓ Recovered via {result.strategy}")
                print(f"  Snapshot: {result.snapshot_datetime}")
            elif result.status == RecoveryStatus.NOT_FOUND:
                print(f"  ✗ Not found in archive")
            else:
                print(f"  ✗ Error: {result.error_message}")
        
        # Display summary statistics
        stats = recovery.get_recovery_stats(results)
        print("\n--- Recovery Summary ---")
        print(f"Total: {stats['total']}")
        print(f"Successful: {stats['successful']}")
        print(f"Not found: {stats['not_found']}")
        print(f"Errors: {stats['errors']}")
        print(f"Success rate: {stats['success_rate']:.1f}%")


async def example_without_download():
    """Example: Check availability without downloading."""
    print("\n=== Example 3: Check Availability Only ===\n")
    
    config = ArchiverConfig(
        blog_url="https://example.tumblr.com",
        output_dir=Path("./downloads"),
        wayback_enabled=True
    )
    
    wayback_client = WaybackClient()
    
    async with MediaRecovery(wayback_client, config) as recovery:
        media_url = "https://64.media.tumblr.com/abc123/tumblr_abc123_1280.jpg"
        post_url = "https://example.tumblr.com/post/123"
        
        print(f"Checking availability: {media_url}\n")
        
        # Don't specify output_path to just check availability
        result = await recovery.recover_media(
            media_url=media_url,
            post_url=post_url
        )
        
        if result.status == RecoveryStatus.SUCCESS:
            print("✓ Media is available in Internet Archive!")
            print(f"  Snapshot URL: {result.snapshot_url}")
            print(f"  Timestamp: {result.snapshot_datetime}")
            print(f"  File size: {result.file_size:,} bytes")
            print("\nYou can download it by specifying an output_path.")
        else:
            print(f"✗ Media not available: {result.error_message}")


async def example_with_error_handling():
    """Example: Proper error handling."""
    print("\n=== Example 4: Error Handling ===\n")
    
    config = ArchiverConfig(
        blog_url="https://example.tumblr.com",
        output_dir=Path("./downloads"),
        wayback_enabled=True
    )
    
    wayback_client = WaybackClient()
    
    try:
        async with MediaRecovery(wayback_client, config) as recovery:
            # Try with invalid URLs
            try:
                result = await recovery.recover_media("", "")
            except ValueError as e:
                print(f"✓ Caught expected error: {e}")
            
            # Try normal recovery
            result = await recovery.recover_media(
                media_url="https://64.media.tumblr.com/missing.jpg",
                post_url="https://example.tumblr.com/post/999"
            )
            
            # Always check status
            if result.status == RecoveryStatus.SUCCESS:
                print("Media recovered successfully")
            elif result.status == RecoveryStatus.NOT_FOUND:
                print(f"Media not in archive: {result.error_message}")
            elif result.status == RecoveryStatus.ERROR:
                print(f"Recovery error occurred: {result.error_message}")
            elif result.status == RecoveryStatus.SKIPPED:
                print(f"Recovery skipped: {result.error_message}")
                
    except Exception as e:
        print(f"✗ Unexpected error: {e}")


async def example_disabled_recovery():
    """Example: When recovery is disabled."""
    print("\n=== Example 5: Disabled Recovery ===\n")
    
    # Set wayback_enabled to False
    config = ArchiverConfig(
        blog_url="https://example.tumblr.com",
        output_dir=Path("./downloads"),
        wayback_enabled=False  # Disabled
    )
    
    wayback_client = WaybackClient()
    
    async with MediaRecovery(wayback_client, config) as recovery:
        result = await recovery.recover_media(
            media_url="https://64.media.tumblr.com/test.jpg",
            post_url="https://example.tumblr.com/post/123"
        )
        
        print(f"Status: {result.status.value}")
        print(f"Message: {result.error_message}")


async def main():
    """Run all examples."""
    print("="*60)
    print("Media Recovery Module - Usage Examples")
    print("="*60)
    
    # Note: These examples use hypothetical URLs
    # In real usage, replace with actual Tumblr media URLs
    
    print("\nNote: Examples use hypothetical URLs for demonstration.")
    print("Replace with actual Tumblr URLs to test real recovery.\n")
    
    # Run examples
    await example_single_recovery()
    await example_multiple_recovery()
    await example_without_download()
    await example_with_error_handling()
    await example_disabled_recovery()
    
    print("\n" + "="*60)
    print("Examples completed!")
    print("="*60)


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
