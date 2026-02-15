"""
Command-line interface for Tumblr Media Downloader.

This module provides the main CLI entry point for downloading media
from Tumblr blogs with support for progress tracking, concurrent downloads,
and comprehensive error handling.
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict

from .api_client import TumblrAPIClient, TumblrAPIError, BlogNotFoundError, RateLimitError
from .downloader import MediaDownloader
from .manifest import ManifestWriter
from .media_selector import extract_media_from_post
from .utils import setup_logging, parse_blog_name


logger = logging.getLogger('tumblr_downloader')


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Returns:
        Parsed argument namespace
    """
    parser = argparse.ArgumentParser(
        description='Download media from Tumblr blogs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download all media from a blog
  %(prog)s --blog myblog --out ./downloads

  # Limit to 100 posts with 10 concurrent downloads
  %(prog)s --blog myblog --out ./downloads --max-posts 100 --concurrency 10

  # Preview what would be downloaded without actually downloading
  %(prog)s --blog myblog --out ./downloads --dry-run

  # Enable verbose logging for debugging
  %(prog)s --blog myblog --out ./downloads --verbose
        """
    )
    
    parser.add_argument(
        '--blog',
        required=True,
        help='Blog name or URL (e.g., "myblog" or "https://myblog.tumblr.com")'
    )
    
    parser.add_argument(
        '--out',
        required=True,
        help='Output directory for downloaded media and manifest'
    )
    
    parser.add_argument(
        '--concurrency',
        type=int,
        default=5,
        help='Number of parallel downloads (default: 5)'
    )
    
    parser.add_argument(
        '--max-posts',
        type=int,
        default=None,
        help='Maximum number of posts to process (default: all posts)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview what would be downloaded without actually downloading'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose debug logging'
    )
    
    return parser.parse_args()


def print_banner(blog_name: str, output_dir: str, dry_run: bool) -> None:
    """
    Print a banner with download configuration.
    
    Args:
        blog_name: Name of the blog being downloaded
        output_dir: Output directory path
        dry_run: Whether this is a dry run
    """
    mode = "DRY RUN MODE" if dry_run else "DOWNLOAD MODE"
    print("=" * 70)
    print(f"Tumblr Media Downloader - {mode}")
    print("=" * 70)
    print(f"Blog:       {blog_name}")
    print(f"Output:     {output_dir}")
    print(f"Started:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()


def print_summary(stats: Dict[str, int], elapsed_time: float) -> None:
    """
    Print download summary statistics.
    
    Args:
        stats: Dictionary containing statistics
        elapsed_time: Total elapsed time in seconds
    """
    print()
    print("=" * 70)
    print("DOWNLOAD SUMMARY")
    print("=" * 70)
    print(f"Posts processed:        {stats.get('posts_processed', 0)}")
    print(f"Posts with media:       {stats.get('posts_with_media', 0)}")
    print(f"Total media found:      {stats.get('media_found', 0)}")
    print(f"Files downloaded:       {stats.get('files_downloaded', 0)}")
    print(f"Files skipped:          {stats.get('files_skipped', 0)}")
    print(f"Files failed:           {stats.get('files_failed', 0)}")
    print(f"Total bytes:            {stats.get('bytes_downloaded', 0):,} bytes")
    print(f"Elapsed time:           {elapsed_time:.2f} seconds")
    
    if stats.get('posts_processed', 0) > 0 and elapsed_time > 0:
        posts_per_sec = stats['posts_processed'] / elapsed_time
        print(f"Average speed:          {posts_per_sec:.2f} posts/sec")
    
    print("=" * 70)


def main() -> int:
    """
    Main entry point for the CLI.
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Parse arguments
    args = parse_arguments()
    
    # Setup logging
    setup_logging(verbose=args.verbose)
    
    # Statistics tracking
    stats = {
        'posts_processed': 0,
        'posts_with_media': 0,
        'media_found': 0,
        'files_downloaded': 0,
        'files_skipped': 0,
        'files_failed': 0,
        'bytes_downloaded': 0
    }
    
    start_time = time.time()
    
    try:
        # Parse blog name from URL or raw input
        try:
            blog_name = parse_blog_name(args.blog)
            logger.info(f"Parsed blog name: {blog_name}")
        except ValueError as e:
            logger.error(f"Invalid blog name or URL: {e}")
            return 1
        
        # Create output directory
        output_dir = Path(args.out)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Output directory ready: {output_dir}")
        except OSError as e:
            logger.error(f"Failed to create output directory: {e}")
            return 1
        
        # Print banner
        print_banner(blog_name, str(output_dir), args.dry_run)
        
        # Initialize API client
        try:
            api_client = TumblrAPIClient(blog_name)
            logger.info("API client initialized")
        except ValueError as e:
            logger.error(f"Failed to initialize API client: {e}")
            return 1
        
        # Initialize manifest writer (loads existing manifest if present)
        try:
            manifest = ManifestWriter(str(output_dir))
            existing_count = len(manifest.posts)
            if existing_count > 0:
                logger.info(f"Loaded existing manifest with {existing_count} posts")
                print(f"Found existing manifest with {existing_count} posts")
        except Exception as e:
            logger.error(f"Failed to initialize manifest: {e}")
            return 1
        
        # Initialize media downloader
        try:
            downloader = MediaDownloader(
                output_dir=str(output_dir),
                concurrency=args.concurrency,
                dry_run=args.dry_run
            )
            logger.info("Media downloader initialized")
        except Exception as e:
            logger.error(f"Failed to initialize downloader: {e}")
            return 1
        
        # Fetch and process posts
        print("Fetching posts from Tumblr...")
        print()
        
        try:
            for post in api_client.get_posts(limit=args.max_posts):
                post_id = str(post.get('id', 'unknown'))
                post_type = post.get('type', 'unknown')
                post_url = post.get('post-url', '')
                
                stats['posts_processed'] += 1
                
                # Progress indicator
                if stats['posts_processed'] % 10 == 0:
                    print(f"Processed {stats['posts_processed']} posts...", end='\r')
                
                logger.debug(f"Processing post {post_id} (type: {post_type})")
                
                # Extract media from post
                try:
                    media_items = extract_media_from_post(post)
                except Exception as e:
                    logger.warning(f"Failed to extract media from post {post_id}: {e}")
                    media_items = []
                
                if not media_items:
                    logger.debug(f"No media found in post {post_id}")
                    continue
                
                stats['posts_with_media'] += 1
                stats['media_found'] += len(media_items)
                
                logger.info(f"Found {len(media_items)} media item(s) in post {post_id}")
                
                # Download media files
                try:
                    download_results = downloader.download_media(media_items)
                except Exception as e:
                    logger.error(f"Failed to download media for post {post_id}: {e}")
                    download_results = []
                
                # Update statistics
                for result in download_results:
                    if result.get('success'):
                        if result.get('skipped'):
                            stats['files_skipped'] += 1
                        else:
                            stats['files_downloaded'] += 1
                            stats['bytes_downloaded'] += result.get('bytes_downloaded', 0)
                    else:
                        stats['files_failed'] += 1
                
                # Prepare media results for manifest
                media_results = []
                for result in download_results:
                    media_entry = {
                        'media_sources': [result.get('url', '')],
                        'chosen_url': result.get('url', ''),
                        'downloaded_filename': result.get('filename', ''),
                        'width': result.get('width', 0),
                        'height': result.get('height', 0),
                        'bytes': result.get('bytes_downloaded', 0),
                        'type': result.get('type', 'unknown'),
                        'status': 'success' if result.get('success') else 'failed'
                    }
                    media_results.append(media_entry)
                
                # Update manifest
                try:
                    post_data = {
                        'post_id': post_id,
                        'post_url': post_url,
                        'timestamp': datetime.utcnow().isoformat(),
                        'tags': post.get('tags', [])
                    }
                    manifest.add_post(post_data, media_results)
                except Exception as e:
                    logger.error(f"Failed to update manifest for post {post_id}: {e}")
        
        except BlogNotFoundError:
            logger.error(f"Blog '{blog_name}' not found")
            print(f"\nError: Blog '{blog_name}' does not exist or is not accessible")
            return 1
        
        except RateLimitError as e:
            logger.error(f"Rate limit exceeded: {e}")
            print("\nError: Rate limit exceeded. Please try again later.")
            return 1
        
        except KeyboardInterrupt:
            print("\n\nDownload interrupted by user")
            logger.info("Download interrupted by KeyboardInterrupt")
            print("Saving progress to manifest...")
        
        except TumblrAPIError as e:
            logger.error(f"Tumblr API error: {e}")
            print(f"\nError: API request failed - {e}")
            return 1
        
        # Save manifest
        print("\nSaving manifest...")
        try:
            manifest.save()
            logger.info(f"Manifest saved to {manifest.manifest_path}")
        except Exception as e:
            logger.error(f"Failed to save manifest: {e}")
            print(f"Warning: Failed to save manifest - {e}")
            return 1
        
        # Calculate elapsed time
        elapsed_time = time.time() - start_time
        
        # Print summary
        print_summary(stats, elapsed_time)
        
        # Success
        logger.info("Download completed successfully")
        return 0
    
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        print(f"\nUnexpected error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
