#!/usr/bin/env python3
"""
Example usage of the TumblrArchiver main application class.

This demonstrates different ways to use the TumblrArchiver:
1. Direct usage with manual cleanup
2. Async context manager (recommended)
3. Convenience function
"""

import asyncio
from pathlib import Path

from tumblr_archiver import (
    ArchiverConfig,
    TumblrArchiver,
    run_archive_app,
    BlogNotFoundError,
    ArchiverError,
)


async def example_manual_cleanup():
    """Example: Manual initialization and cleanup."""
    print("=" * 60)
    print("Example 1: Manual cleanup")
    print("=" * 60)
    
    config = ArchiverConfig(
        blog_name="example",
        output_dir=Path("archive"),
        concurrency=3,
        verbose=True,
        dry_run=True  # Safe for testing
    )
    
    archiver = TumblrArchiver(config)
    
    try:
        stats = await archiver.run()
        print(f"\n✓ Success! Downloaded {stats.downloaded} items")
        print(f"  Total posts: {stats.total_posts}")
        print(f"  Total media: {stats.total_media}")
    except BlogNotFoundError:
        print("✗ Blog not found")
    except ArchiverError as e:
        print(f"✗ Archive failed: {e}")
    finally:
        await archiver.cleanup()
    
    print()


async def example_context_manager():
    """Example: Using async context manager (recommended)."""
    print("=" * 60)
    print("Example 2: Async context manager (recommended)")
    print("=" * 60)
    
    config = ArchiverConfig(
        blog_name="example",
        output_dir=Path("archive"),
        concurrency=5,
        rate_limit=2.0,
        include_reblogs=True,
        download_embeds=False,
        dry_run=True
    )
    
    try:
        async with TumblrArchiver(config) as archiver:
            stats = await archiver.run()
            print(f"\n✓ Success! Downloaded {stats.downloaded} items")
            print(f"  Duration: {stats.duration_seconds:.2f}s")
            print(f"  Bytes: {stats.bytes_downloaded:,}")
        # Cleanup happens automatically here
    except BlogNotFoundError:
        print("✗ Blog not found")
    except ArchiverError as e:
        print(f"✗ Archive failed: {e}")
    
    print()


async def example_convenience_function():
    """Example: Using the convenience function."""
    print("=" * 60)
    print("Example 3: Convenience function")
    print("=" * 60)
    
    config = ArchiverConfig(
        blog_name="example",
        output_dir=Path("archive"),
        dry_run=True
    )
    
    try:
        # This handles context management automatically
        stats = await run_archive_app(config)
        print(f"\n✓ Success! Downloaded {stats.downloaded} items")
    except BlogNotFoundError:
        print("✗ Blog not found")
    except ArchiverError as e:
        print(f"✗ Archive failed: {e}")
    
    print()


async def example_error_handling():
    """Example: Comprehensive error handling."""
    print("=" * 60)
    print("Example 4: Error handling")
    print("=" * 60)
    
    config = ArchiverConfig(
        blog_name="nonexistent-blog-12345",  # This blog doesn't exist
        output_dir=Path("archive"),
        dry_run=True
    )
    
    try:
        async with TumblrArchiver(config) as archiver:
            stats = await archiver.run()
            print(f"Downloaded: {stats.downloaded}")
    except BlogNotFoundError as e:
        print(f"✗ Blog not found: {e}")
    except ArchiverError as e:
        print(f"✗ Archive error: {e}")
        if e.details:
            print(f"  Details: {e.details}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
    
    print()


async def example_production_usage():
    """Example: Production-ready usage with full configuration."""
    print("=" * 60)
    print("Example 5: Production configuration")
    print("=" * 60)
    
    config = ArchiverConfig(
        blog_name="example",
        output_dir=Path("archive/example"),
        
        # Performance settings
        concurrency=10,
        rate_limit=2.0,
        
        # Retry settings
        max_retries=5,
        base_backoff=2.0,
        max_backoff=60.0,
        
        # Feature flags
        include_reblogs=True,
        download_embeds=True,
        resume=True,
        
        # Operational settings
        verbose=True,
        dry_run=False,  # Set to False for actual downloads
        timeout=30.0
    )
    
    print(f"Blog: {config.blog_name}")
    print(f"Output: {config.output_dir}")
    print(f"Workers: {config.concurrency}")
    print(f"Rate limit: {config.rate_limit} req/s")
    
    # In production, you'd actually run this
    # async with TumblrArchiver(config) as archiver:
    #     stats = await archiver.run()
    #     print(stats)
    
    print("\n(Skipped actual run in demo)\n")


async def main():
    """Run all examples."""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 12 + "TumblrArchiver Usage Examples" + " " * 17 + "║")
    print("╚" + "═" * 58 + "╝")
    print()
    
    # Run examples (commented out to avoid actual network calls)
    # await example_manual_cleanup()
    # await example_context_manager()
    # await example_convenience_function()
    # await example_error_handling()
    await example_production_usage()
    
    print("All examples completed!")


if __name__ == "__main__":
    asyncio.run(main())
