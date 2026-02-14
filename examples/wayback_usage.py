"""Example demonstrating Internet Archive / Wayback Machine integration usage."""

import asyncio

from tumblr_archiver.archive import WaybackClient
from tumblr_archiver.http_client import AsyncHTTPClient


async def main():
    """Demonstrate Wayback Machine client usage."""
    
    # Example Tumblr media URL (this is just an example)
    media_url = "https://64.media.tumblr.com/abc123xyz/tumblr_example_1280.jpg"
    
    # Create HTTP client and Wayback client
    async with AsyncHTTPClient(rate_limit=1.0) as http_client:
        wayback = WaybackClient(http_client)
        
        print(f"Searching for archived snapshots of: {media_url}\n")
        
        # Find all snapshots
        snapshots = await wayback.find_snapshots(
            media_url,
            from_date="20200101",  # From January 1, 2020
            to_date="20231231"     # To December 31, 2023
        )
        
        if not snapshots:
            print("No snapshots found in the Internet Archive.")
            return
        
        print(f"Found {len(snapshots)} snapshots:")
        for i, snapshot in enumerate(snapshots[:5], 1):  # Show first 5
            print(f"  {i}. {snapshot.timestamp} - Status: {snapshot.statuscode} - {snapshot.mimetype}")
        
        if len(snapshots) > 5:
            print(f"  ... and {len(snapshots) - 5} more")
        
        print("\nFinding best snapshot...")
        
        # Get the best snapshot
        best_snapshot = await wayback.get_best_snapshot(media_url)
        
        if best_snapshot:
            print(f"\nBest snapshot selected:")
            print(f"  Timestamp: {best_snapshot.datetime}")
            print(f"  Status: {best_snapshot.statuscode}")
            print(f"  MIME type: {best_snapshot.mimetype}")
            print(f"  URL: {best_snapshot.snapshot_url}")
            
            # Optionally download the content
            print("\nDownloading snapshot content...")
            content = await wayback.download_from_snapshot(best_snapshot.snapshot_url)
            print(f"Downloaded {len(content)} bytes")
        else:
            print("No suitable snapshot found (all were errors or redirects)")


if __name__ == "__main__":
    asyncio.run(main())
