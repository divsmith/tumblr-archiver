"""
Example usage of the Orchestrator for archiving Tumblr blogs.

This demonstrates how to use the Orchestrator class to coordinate
the complete archiving workflow with concurrent downloads.
"""

import asyncio
import logging
from pathlib import Path

from tumblr_archiver import ArchiverConfig, Orchestrator


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


async def archive_blog(blog_name: str, output_dir: Path, concurrency: int = 5) -> None:
    """
    Archive a Tumblr blog with all its media.
    
    Args:
        blog_name: Name of the blog to archive
        output_dir: Directory to save archived content
        concurrency: Number of concurrent download workers
    """
    # Create configuration
    config = ArchiverConfig(
        blog_name=blog_name,
        output_dir=output_dir,
        concurrency=concurrency,
        rate_limit=2.0,  # 2 requests per second
        max_retries=3,
        resume=True,  # Resume from previous downloads
        dry_run=False,
        verbose=False,
    )
    
    # Define progress callback
    def progress_callback(worker_id: str, media_item):
        """Track download progress."""
        print(f"[{worker_id}] Downloaded: {media_item.filename} ({media_item.status})")
    
    # Create orchestrator
    orchestrator = Orchestrator(config, progress_callback=progress_callback)
    
    # Run the archiving process
    print(f"Starting archive of '{blog_name}'...")
    print(f"Output directory: {output_dir}")
    print(f"Concurrency: {concurrency} workers")
    print("-" * 60)
    
    try:
        stats = await orchestrator.run()
        
        # Print results
        print("\n" + "=" * 60)
        print("ARCHIVE COMPLETE!")
        print("=" * 60)
        print(stats)
        
    except Exception as e:
        print(f"\n❌ Error during archiving: {e}")
        raise


async def main():
    """Main entry point."""
    # Setup logging
    setup_logging(verbose=False)
    
    # Example: Archive a blog
    # Replace 'example' with an actual blog name
    blog_name = "example"
    output_dir = Path("./archive") / blog_name
    
    # Note: This is a demo. Replace with a real blog name to test.
    print("=" * 60)
    print("Tumblr Archiver - Orchestrator Example")
    print("=" * 60)
    print("\nThis example demonstrates the orchestrator workflow.")
    print("To use with a real blog, update the 'blog_name' variable.\n")
    
    # Uncomment to run with a real blog:
    # await archive_blog(blog_name, output_dir, concurrency=5)
    
    print("✓ Orchestrator example loaded successfully")
    print("\nTo run an actual archive, uncomment the archive_blog() call")
    print("in the main() function and provide a valid blog name.")


if __name__ == "__main__":
    asyncio.run(main())
