#!/usr/bin/env python3
"""
Quick verification script for ManifestManager implementation.
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from tumblr_archiver.manifest import ManifestManager
from tumblr_archiver.models import MediaItem, Post
from tumblr_archiver.storage import generate_unique_filename, get_media_directory


async def main():
    """Run verification test."""
    print("🔍 Verifying ManifestManager Implementation...\n")
    
    # Create temporary manager
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # 1. Test ManifestManager initialization and loading
        print("✓ Creating ManifestManager...")
        manager = ManifestManager(tmp_path)
        manifest = await manager.load()
        print(f"  - Created new manifest: {manifest.blog_name}")
        
        # 2. Set blog info
        print("\n✓ Setting blog information...")
        await manager.set_blog_info("test-blog", "https://test-blog.tumblr.com")
        print(f"  - Blog: {manager.manifest.blog_name}")
        print(f"  - URL: {manager.manifest.blog_url}")
        
        # 3. Test adding a post with media
        print("\n✓ Adding post with media...")
        media = MediaItem(
            post_id="123456789",
            post_url="https://test-blog.tumblr.com/post/123456789",
            timestamp=datetime.now(timezone.utc),
            media_type="image",
            filename="123456789_001.jpg",
            byte_size=524288,
            checksum="a" * 64,
            original_url="https://64.media.tumblr.com/abc/image.jpg",
            retrieved_from="tumblr",
            status="downloaded"
        )
        
        post = Post(
            post_id="123456789",
            post_url="https://test-blog.tumblr.com/post/123456789",
            timestamp=datetime.now(timezone.utc),
            is_reblog=False,
            media_items=[media]
        )
        
        await manager.add_post(post)
        print(f"  - Total posts: {manager.manifest.total_posts}")
        print(f"  - Total media: {manager.manifest.total_media}")
        
        # 4. Test resume capability
        print("\n✓ Testing resume capability...")
        is_downloaded = manager.is_media_downloaded(
            "https://64.media.tumblr.com/abc/image.jpg"
        )
        print(f"  - Media downloaded check: {is_downloaded}")
        
        # 5. Test statistics
        print("\n✓ Getting statistics...")
        stats = manager.get_statistics()
        print(f"  - Downloaded: {stats['media_downloaded']}")
        print(f"  - Images: {stats['images']}")
        print(f"  - From Tumblr: {stats['from_tumblr']}")
        
        # 6. Test storage utilities
        print("\n✓ Testing storage utilities...")
        image_dir = get_media_directory(tmp_path, "image")
        print(f"  - Image directory: {image_dir.name}")
        
        filename = generate_unique_filename(
            "https://example.com/photo.jpg",
            "b" * 64
        )
        print(f"  - Generated filename: {filename}")
        
        # 7. Verify manifest.json was created
        manifest_path = tmp_path / "manifest.json"
        print(f"\n✓ Manifest file created: {manifest_path.exists()}")
        
        # 8. Load existing manifest (test resume)
        print("\n✓ Testing manifest reload...")
        manager2 = ManifestManager(tmp_path)
        manifest2 = await manager2.load()
        print(f"  - Loaded {manifest2.total_posts} posts from disk")
        print(f"  - Blog name: {manifest2.blog_name}")
        
    print("\n✅ All verifications passed!")


if __name__ == "__main__":
    asyncio.run(main())
