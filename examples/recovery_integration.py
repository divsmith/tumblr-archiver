"""
Integration example: Using Media Recovery with the Downloader.

This example shows how to integrate the MediaRecovery module with the
existing download pipeline to automatically fall back to Internet Archive
when media is missing from Tumblr.
"""

import asyncio
import logging
from pathlib import Path

from tumblr_archiver.config import ArchiverConfig
from tumblr_archiver.downloader import MediaNotFoundError
from tumblr_archiver.wayback_client import WaybackClient
from tumblr_archiver.recovery import MediaRecovery, RecoveryStatus


logger = logging.getLogger(__name__)


class DownloadWithRecovery:
    """Download manager with automatic recovery fallback."""
    
    def __init__(self, config: ArchiverConfig):
        """Initialize with configuration.
        
        Args:
            config: Archiver configuration
        """
        self.config = config
        self.wayback_client = WaybackClient(
            user_agent="TumblrArchiver/1.0",
            timeout=30
        )
        
        # Statistics
        self.stats = {
            "downloaded": 0,
            "recovered": 0,
            "failed": 0,
        }
    
    async def download_media(
        self,
        media_url: str,
        post_url: str,
        output_path: Path
    ) -> dict:
        """Download media with automatic recovery fallback.
        
        Args:
            media_url: URL of media to download
            post_url: URL of the post containing the media
            output_path: Where to save the downloaded file
            
        Returns:
            Dictionary with download result and metadata
        """
        # First, try normal download from Tumblr
        try:
            logger.info(f"Attempting direct download: {media_url}")
            
            # Here you would call the actual downloader
            # For demo purposes, we'll simulate a 404 error
            # await self.downloader.download(media_url, output_path)
            
            # Simulate that media is missing on Tumblr
            raise MediaNotFoundError(f"Media not found: {media_url}")
            
        except MediaNotFoundError as e:
            # Media missing on Tumblr - try recovery
            logger.warning(f"Media not found on Tumblr: {media_url}")
            
            if not self.config.recover_removed_media:
                logger.info("Recovery disabled, skipping")
                self.stats["failed"] += 1
                return {
                    "status": "failed",
                    "source": "tumblr",
                    "error": str(e)
                }
            
            logger.info("Attempting recovery from Internet Archive...")
            
            async with MediaRecovery(self.wayback_client, self.config) as recovery:
                result = await recovery.recover_media(
                    media_url=media_url,
                    post_url=post_url,
                    output_path=output_path
                )
                
                if result.status == RecoveryStatus.SUCCESS:
                    logger.info(
                        f"Successfully recovered via {result.strategy}: "
                        f"{media_url}"
                    )
                    self.stats["recovered"] += 1
                    return {
                        "status": "success",
                        "source": "internet_archive",
                        "snapshot_url": result.snapshot_url,
                        "timestamp": result.timestamp,
                        "file_size": result.file_size,
                        "strategy": result.strategy
                    }
                else:
                    logger.error(
                        f"Recovery failed for {media_url}: "
                        f"{result.error_message}"
                    )
                    self.stats["failed"] += 1
                    return {
                        "status": "failed",
                        "source": "recovery_failed",
                        "error": result.error_message
                    }
    
    async def download_post_media(
        self,
        post: dict,
        output_dir: Path
    ) -> list[dict]:
        """Download all media from a post.
        
        Args:
            post: Post data with media URLs
            output_dir: Directory to save media
            
        Returns:
            List of download results
        """
        post_url = post["post_url"]
        media_urls = post.get("media_urls", [])
        
        if not media_urls:
            logger.debug(f"No media in post: {post_url}")
            return []
        
        logger.info(f"Downloading {len(media_urls)} media files from {post_url}")
        
        results = []
        for i, media_url in enumerate(media_urls):
            # Generate output filename
            filename = f"{post['id']}_{i}_{Path(media_url).name}"
            output_path = output_dir / filename
            
            # Download with recovery
            result = await self.download_media(
                media_url=media_url,
                post_url=post_url,
                output_path=output_path
            )
            
            results.append({
                "media_url": media_url,
                "output_path": output_path,
                **result
            })
        
        return results
    
    async def download_blog_media(
        self,
        posts: list[dict],
        output_dir: Path
    ) -> dict:
        """Download media from multiple posts.
        
        Args:
            posts: List of post data
            output_dir: Base output directory
            
        Returns:
            Summary of download operations
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        all_results = []
        
        for post in posts:
            results = await self.download_post_media(post, output_dir)
            all_results.extend(results)
            
            # Respect rate limits
            await asyncio.sleep(1.0 / self.config.rate_limit)
        
        # Calculate summary
        total = len(all_results)
        successful = sum(1 for r in all_results if r["status"] == "success")
        recovered = sum(
            1 for r in all_results 
            if r.get("source") == "internet_archive"
        )
        failed = sum(1 for r in all_results if r["status"] == "failed")
        
        return {
            "total": total,
            "successful": successful,
            "recovered": recovered,
            "failed": failed,
            "success_rate": (successful / total * 100) if total > 0 else 0.0,
            "recovery_rate": (recovered / total * 100) if total > 0 else 0.0,
            "results": all_results
        }


async def main():
    """Example usage of integrated download with recovery."""
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Configuration
    config = ArchiverConfig(
        blog_url="https://example.tumblr.com",
        output_dir=Path("./downloads"),
        recover_removed_media=True,  # Enable recovery
        wayback_enabled=True,
        rate_limit=1.0,  # 1 request per second
        concurrency=2
    )
    
    # Initialize download manager
    manager = DownloadWithRecovery(config)
    
    # Example posts (would come from Tumblr API)
    posts = [
        {
            "id": "123456789",
            "post_url": "https://example.tumblr.com/post/123456789",
            "media_urls": [
                "https://64.media.tumblr.com/abc123/tumblr_abc123_1280.jpg",
                "https://64.media.tumblr.com/def456/tumblr_def456_500.jpg",
            ]
        },
        {
            "id": "987654321",
            "post_url": "https://example.tumblr.com/post/987654321",
            "media_urls": [
                "https://va.media.tumblr.com/tumblr_ghi789.mp4",
            ]
        },
    ]
    
    # Download all media
    print("Starting download with automatic recovery...\n")
    
    summary = await manager.download_blog_media(
        posts=posts,
        output_dir=config.output_dir
    )
    
    # Display results
    print("\n" + "="*60)
    print("Download Summary")
    print("="*60)
    print(f"Total media files: {summary['total']}")
    print(f"Successfully downloaded: {summary['successful']}")
    print(f"Recovered from archive: {summary['recovered']}")
    print(f"Failed: {summary['failed']}")
    print(f"Success rate: {summary['success_rate']:.1f}%")
    print(f"Recovery rate: {summary['recovery_rate']:.1f}%")
    print("="*60)
    
    # Show individual results
    print("\nDetailed Results:")
    for result in summary['results']:
        status_symbol = "✓" if result['status'] == 'success' else "✗"
        source_info = f"[{result['source']}]" if result['status'] == 'success' else ""
        
        print(f"{status_symbol} {result['media_url']} {source_info}")
        
        if result['status'] == 'success' and result['source'] == 'internet_archive':
            print(f"   → Recovered via {result.get('strategy')}")
            print(f"   → Snapshot: {result.get('timestamp')}")


async def example_batch_recovery():
    """Example: Batch recovery of known missing media."""
    
    print("\n" + "="*60)
    print("Batch Recovery Example")
    print("="*60 + "\n")
    
    config = ArchiverConfig(
        blog_url="https://example.tumblr.com",
        output_dir=Path("./downloads"),
        wayback_enabled=True
    )
    
    wayback_client = WaybackClient()
    
    # List of known missing media (from manifest or previous attempts)
    missing_media = [
        {
            "media_url": "https://64.media.tumblr.com/missing1.jpg",
            "post_url": "https://example.tumblr.com/post/111",
            "output_path": Path("./downloads/missing1.jpg")
        },
        {
            "media_url": "https://64.media.tumblr.com/missing2.jpg",
            "post_url": "https://example.tumblr.com/post/222",
            "output_path": Path("./downloads/missing2.jpg")
        },
        {
            "media_url": "https://64.media.tumblr.com/missing3.jpg",
            "post_url": "https://example.tumblr.com/post/333",
            "output_path": Path("./downloads/missing3.jpg")
        },
    ]
    
    print(f"Attempting to recover {len(missing_media)} missing files...\n")
    
    async with MediaRecovery(wayback_client, config) as recovery:
        # Prepare batch items
        media_items = [
            (item["media_url"], item["post_url"], item["output_path"])
            for item in missing_media
        ]
        
        # Recover all concurrently
        results = await recovery.recover_multiple_media(
            media_items,
            max_concurrent=2
        )
        
        # Display results
        for i, (item, result) in enumerate(zip(missing_media, results), 1):
            print(f"\n{i}. {item['media_url']}")
            
            if result.status == RecoveryStatus.SUCCESS:
                print(f"   ✓ Recovered successfully")
                print(f"   Strategy: {result.strategy}")
                print(f"   Timestamp: {result.snapshot_datetime}")
                print(f"   Size: {result.file_size:,} bytes")
            elif result.status == RecoveryStatus.NOT_FOUND:
                print(f"   ✗ Not found in archive")
            else:
                print(f"   ✗ Error: {result.error_message}")
        
        # Show statistics
        stats = recovery.get_recovery_stats(results)
        print(f"\n{'='*60}")
        print(f"Recovery Statistics:")
        print(f"  Success rate: {stats['success_rate']:.1f}%")
        print(f"  Recovered: {stats['successful']}/{stats['total']}")
        print(f"  Not found: {stats['not_found']}")
        print(f"  Errors: {stats['errors']}")
        print(f"{'='*60}")


if __name__ == "__main__":
    print("Media Recovery Integration Examples")
    print("="*60)
    
    # Run examples
    asyncio.run(main())
    asyncio.run(example_batch_recovery())
