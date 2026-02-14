"""
Usage example for Tumblr Archiver data models.

This demonstrates how to use the Pydantic models for tracking
media downloads from Tumblr blogs.
"""

from datetime import datetime, timezone

from tumblr_archiver.models import Manifest, MediaItem, Post
from tumblr_archiver.schemas import (
    MANIFEST_SCHEMA_VERSION,
    add_schema_version,
    validate_manifest_dict,
)


def main():
    """Demonstrate creating and managing a Tumblr archive manifest."""
    
    # Create a new manifest for a blog
    print("Creating manifest for 'example-blog'...")
    manifest = Manifest(
        blog_name="example-blog",
        blog_url="https://example-blog.tumblr.com"
    )
    print(f"✓ Manifest created at {manifest.created_at}")
    
    # Create some media items
    print("\nAdding media items...")
    media1 = MediaItem(
        post_id="123456789",
        post_url="https://example-blog.tumblr.com/post/123456789",
        timestamp=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
        media_type="image",
        filename="123456789_001.jpg",
        byte_size=524288,
        checksum="a" * 64,
        original_url="https://64.media.tumblr.com/abc/tumblr_xyz.jpg",
        retrieved_from="tumblr",
        status="downloaded",
        notes="High quality image"
    )
    
    media2 = MediaItem(
        post_id="123456789",
        post_url="https://example-blog.tumblr.com/post/123456789",
        timestamp=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
        media_type="gif",
        filename="123456789_002.gif",
        byte_size=1048576,
        checksum="b" * 64,
        original_url="https://64.media.tumblr.com/def/tumblr_abc.gif",
        retrieved_from="tumblr",
        status="downloaded"
    )
    
    # Create a post with media
    post1 = Post(
        post_id="123456789",
        post_url="https://example-blog.tumblr.com/post/123456789",
        timestamp=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
        is_reblog=False,
        media_items=[media1, media2]
    )
    
    # Add post to manifest
    manifest.add_post(post1)
    print(f"✓ Added post {post1.post_id} with {len(post1.media_items)} media items")
    
    # Create another post from Internet Archive
    media3 = MediaItem(
        post_id="987654321",
        post_url="https://example-blog.tumblr.com/post/987654321",
        timestamp=datetime(2024, 1, 10, tzinfo=timezone.utc),
        media_type="video",
        filename="987654321_001.mp4",
        byte_size=5242880,
        checksum="c" * 64,
        original_url="https://va.media.tumblr.com/video.mp4",
        retrieved_from="internet_archive",
        archive_snapshot_url="https://web.archive.org/web/20240110/example.com",
        status="archived"
    )
    
    post2 = Post(
        post_id="987654321",
        post_url="https://example-blog.tumblr.com/post/987654321",
        timestamp=datetime(2024, 1, 10, tzinfo=timezone.utc),
        is_reblog=True,
        media_items=[media3]
    )
    
    manifest.add_post(post2)
    print(f"✓ Added post {post2.post_id} (from Internet Archive)")
    
    # Display statistics
    print("\n" + "=" * 60)
    print("Archive Statistics:")
    print("=" * 60)
    stats = manifest.get_statistics()
    for key, value in stats.items():
        print(f"  {key:30s}: {value}")
    
    # Query media by status
    print("\n" + "=" * 60)
    print("Media by Status:")
    print("=" * 60)
    downloaded = manifest.get_media_by_status("downloaded")
    print(f"  Downloaded: {len(downloaded)} files")
    for media in downloaded:
        print(f"    - {media.filename} ({media.byte_size:,} bytes)")
    
    archived = manifest.get_media_by_status("archived")
    print(f"  Archived: {len(archived)} files")
    for media in archived:
        print(f"    - {media.filename} ({media.byte_size:,} bytes)")
    
    # Serialize to JSON
    print("\n" + "=" * 60)
    print("Serialization:")
    print("=" * 60)
    manifest_dict = manifest.to_dict()
    print(f"✓ Converted to dictionary with {len(manifest_dict)} top-level keys")
    
    # Add schema version
    versioned_dict = add_schema_version(manifest_dict)
    print(f"✓ Added schema version: {MANIFEST_SCHEMA_VERSION}")
    
    # Validate
    is_valid, error = validate_manifest_dict(manifest_dict)
    if is_valid:
        print("✓ Manifest validation passed")
    else:
        print(f"✗ Validation error: {error}")
    
    # Deserialize back
    restored_manifest = Manifest.from_dict(manifest_dict)
    print(f"✓ Restored manifest with {restored_manifest.total_posts} posts")
    
    # Save to JSON file (example)
    import json
    json_output = json.dumps(versioned_dict, indent=2, default=str)
    print(f"\n✓ JSON output size: {len(json_output):,} characters")
    print("\nFirst 500 characters of JSON:")
    print("-" * 60)
    print(json_output[:500] + "...")


if __name__ == "__main__":
    main()
