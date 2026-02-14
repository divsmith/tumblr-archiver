"""
Example: How to use the TumblrArchiver class to archive a Tumblr blog.

This example demonstrates:
1. Loading configuration
2. Initializing the archiver
3. Setting up progress callbacks
4. Running the archive operation
5. Examining results
"""

import asyncio
import logging
from pathlib import Path

from tumblr_archiver import TumblrArchiver, ArchiveResult
from tumblr_archiver.config import ArchiverConfig


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def progress_callback(progress_data: dict):
    """Handle progress updates from the archiver."""
    event = progress_data.get('event')
    
    if event == 'start':
        print(f"\n🚀 Starting archive of blog: {progress_data.get('blog')}")
    
    elif event == 'fetch_blog_info':
        print(f"📡 Fetching blog information...")
    
    elif event == 'fetch_posts':
        current = progress_data.get('current', 0)
        total = progress_data.get('total', 0)
        if total > 0:
            print(f"📝 Fetching posts: {current}/{total} ({current*100//total}%)")
    
    elif event == 'process_post':
        post_index = progress_data.get('post_index', 0)
        total_posts = progress_data.get('total_posts', 0)
        post_id = progress_data.get('post_id', '')
        media_count = progress_data.get('media_count', 0)
        print(f"🖼️  Processing post {post_index}/{total_posts} (ID: {post_id}, {media_count} media)")
    
    elif event == 'complete':
        print(f"✅ Archive complete!")
    
    elif event == 'error':
        error = progress_data.get('error', 'Unknown error')
        print(f"❌ Error: {error}")


async def archive_blog_example():
    """Example: Archive a blog with basic configuration."""
    
    # Configure the archiver
    config = ArchiverConfig(
        blog_url="staff.tumblr.com",  # Change this to the blog you want to archive
        output_dir=Path("./archives"),
        tumblr_api_key="YOUR_API_KEY_HERE",  # Get from https://www.tumblr.com/oauth/apps
        
        # Behavior settings
        resume=True,  # Resume from previous download
        include_reblogs=True,
        recover_removed_media=True,  # Try Wayback Machine for missing media
        
        # Wayback Machine settings
        wayback_enabled=True,
        wayback_max_snapshots=5,
        
        # Performance settings
        rate_limit=1.0,  # 1 request per second to Tumblr API
        concurrency=3,  # 3 concurrent downloads
        max_retries=3,
        
        # Logging
        verbose=True,
        dry_run=False  # Set to True to simulate without downloading
    )
    
    # Create archiver instance
    archiver = TumblrArchiver(config)
    
    # Set up progress callback
    archiver.set_progress_callback(progress_callback)
    
    # Run the archive operation
    print(f"\n{'='*60}")
    print(f"Tumblr Archiver Example")
    print(f"{'='*60}")
    
    result: ArchiveResult = await archiver.archive_blog()
    
    # Print results
    print(result)
    
    # Access specific statistics
    stats = result.statistics
    print(f"\nDetailed Statistics:")
    print(f"  Success Rate: {stats.media_downloaded}/{stats.total_media} ({stats.media_downloaded*100//stats.total_media if stats.total_media > 0 else 0}%)")
    print(f"  Recovery Rate: {stats.media_recovered}/{stats.media_missing} from Wayback Machine")
    print(f"  Average Speed: {stats.bytes_downloaded / result.duration_seconds / 1024 / 1024:.2f} MB/s")
    
    # Clean up
    archiver.close()
    
    return result


async def archive_multiple_blogs_example():
    """Example: Archive multiple blogs sequentially."""
    
    blogs = [
        "staff.tumblr.com",
        "engineering.tumblr.com",
        "another-blog.tumblr.com"
    ]
    
    results = []
    
    for blog_url in blogs:
        print(f"\n{'='*60}")
        print(f"Archiving: {blog_url}")
        print(f"{'='*60}")
        
        config = ArchiverConfig(
            blog_url=blog_url,
            output_dir=Path("./archives"),
            tumblr_api_key="YOUR_API_KEY_HERE",
            resume=True,
            recover_removed_media=True,
            rate_limit=1.0,
            concurrency=2
        )
        
        archiver = TumblrArchiver(config)
        archiver.set_progress_callback(progress_callback)
        
        try:
            result = await archiver.archive_blog()
            results.append(result)
            print(f"✅ Successfully archived: {blog_url}")
        except Exception as e:
            print(f"❌ Failed to archive {blog_url}: {e}")
        finally:
            archiver.close()
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Summary of All Archives")
    print(f"{'='*60}")
    
    for result in results:
        status = "✅ Success" if result.success else "❌ Failed"
        print(f"{status} - {result.blog_name}: {result.statistics.media_downloaded} media downloaded")


async def archive_with_custom_settings_example():
    """Example: Archive with advanced custom settings."""
    
    config = ArchiverConfig(
        blog_url="example.tumblr.com",
        output_dir=Path("./archives/custom"),
        tumblr_api_key="YOUR_API_KEY_HERE",
        
        # Only original posts (no reblogs)
        include_reblogs=False,
        
        # Aggressive recovery settings
        recover_removed_media=True,
        wayback_enabled=True,
        wayback_max_snapshots=10,
        
        # High performance
        rate_limit=2.0,  # 2 requests per second (be careful not to exceed API limits!)
        concurrency=5,
        max_retries=5,
        base_backoff=2.0,
        max_backoff=60.0,
        
        # Logging
        verbose=True,
        log_file=Path("./archives/custom/archive.log")
    )
    
    archiver = TumblrArchiver(config)
    
    # Custom progress callback with more detail
    def detailed_progress(progress_data: dict):
        import json
        print(f"Progress: {json.dumps(progress_data, indent=2)}")
    
    archiver.set_progress_callback(detailed_progress)
    
    result = await archiver.archive_blog()
    
    print(result)
    
    archiver.close()
    
    return result


async def dry_run_example():
    """Example: Dry run to see what would be downloaded without actually downloading."""
    
    config = ArchiverConfig(
        blog_url="example.tumblr.com",
        output_dir=Path("./archives/dry-run"),
        tumblr_api_key="YOUR_API_KEY_HERE",
        dry_run=True,  # Enable dry run mode
        verbose=True
    )
    
    archiver = TumblrArchiver(config)
    archiver.set_progress_callback(progress_callback)
    
    print("\n🔍 Running in DRY RUN mode - no files will be downloaded\n")
    
    result = await archiver.archive_blog()
    
    print(f"\nDry run complete! Found {result.statistics.total_media} media items.")
    
    archiver.close()


async def resume_example():
    """Example: Resume an interrupted download."""
    
    config = ArchiverConfig(
        blog_url="example.tumblr.com",
        output_dir=Path("./archives/example"),
        tumblr_api_key="YOUR_API_KEY_HERE",
        resume=True,  # Enable resume
        verbose=True
    )
    
    archiver = TumblrArchiver(config)
    archiver.set_progress_callback(progress_callback)
    
    print("\n🔄 Resuming previous download...\n")
    
    result = await archiver.archive_blog()
    
    print(f"\nResumed archive complete!")
    print(f"Skipped {result.statistics.media_skipped} already downloaded files")
    print(f"Downloaded {result.statistics.media_downloaded} new files")
    
    archiver.close()


def main():
    """Run the appropriate example."""
    
    import sys
    
    if len(sys.argv) > 1:
        example = sys.argv[1]
        
        if example == "basic":
            asyncio.run(archive_blog_example())
        elif example == "multiple":
            asyncio.run(archive_multiple_blogs_example())
        elif example == "custom":
            asyncio.run(archive_with_custom_settings_example())
        elif example == "dry-run":
            asyncio.run(dry_run_example())
        elif example == "resume":
            asyncio.run(resume_example())
        else:
            print(f"Unknown example: {example}")
            print("Available examples: basic, multiple, custom, dry-run, resume")
    else:
        # Run basic example by default
        print("Running basic example. Pass 'basic', 'multiple', 'custom', 'dry-run', or 'resume' as argument for other examples.")
        asyncio.run(archive_blog_example())


if __name__ == "__main__":
    main()
