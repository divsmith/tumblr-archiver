# Manifest Manager Usage Examples

This document demonstrates how to use the `ManifestManager` class for tracking downloaded media.

## Basic Usage

```python
from tumblr_archiver.manifest import ManifestManager, create_media_entry

# Initialize the manager
manager = ManifestManager("archive/manifest.json")

# Load existing manifest or create new
manager.load()

# Set blog information
manager.set_blog_info(
    blog_url="https://example.tumblr.com",
    blog_name="example",
    total_posts=150
)

# Add a media entry
media = create_media_entry(
    post_id="12345",
    post_url="https://example.tumblr.com/post/12345",
    timestamp="2023-05-15T14:20:00Z",
    media_type="image",
    filename="tumblr_xyz123_1280.jpg",
    original_url="https://64.media.tumblr.com/xyz123/tumblr_xyz123_1280.jpg",
    api_media_urls=["https://64.media.tumblr.com/xyz123/tumblr_xyz123_1280.jpg"],
    byte_size=245678,
    checksum="abc123def456...",
    status="pending"
)

manager.add_media(media)

# Save to disk (atomic write)
manager.save()
```

## Resume Support

```python
from pathlib import Path

# Check if media is already downloaded
post_id = "12345"
filename = "tumblr_xyz123_1280.jpg"
file_path = Path("archive/media") / filename

if manager.is_downloaded(post_id, filename, file_path, verify_checksum=True):
    print("Media already downloaded and verified, skipping...")
else:
    # Download the file
    # ... download logic ...
    
    # Update status after successful download
    manager.mark_status(post_id, filename, "downloaded")
    manager.save()
```

## Updating Media Entries

```python
# Update media entry with checksum after download
from tumblr_archiver.manifest import calculate_checksum

file_path = Path("archive/media/tumblr_xyz123_1280.jpg")
checksum = calculate_checksum(file_path)
byte_size = file_path.stat().st_size

manager.update_media(
    post_id="12345",
    filename="tumblr_xyz123_1280.jpg",
    updates={
        "checksum": f"sha256:{checksum}",
        "byte_size": byte_size,
        "status": "downloaded"
    }
)

manager.save()
```

## Error Handling

```python
try:
    # Attempt to download media
    # ... download logic ...
    manager.mark_status(post_id, filename, "downloaded")
    
except Exception as e:
    # Mark as failed with error message
    manager.mark_status(
        post_id, 
        filename, 
        "failed", 
        notes=f"Download failed: {str(e)}"
    )
finally:
    manager.save()
```

## Statistics

```python
# Get archive statistics
stats = manager.get_stats()

print(f"Blog: {stats['blog_name']}")
print(f"Total Posts: {stats['total_posts']}")
print(f"Total Media: {stats['total_media']}")
print(f"Unique Media: {stats['unique_media']}")
print(f"Total Size: {stats['total_mb']} MB")
print(f"\nStatus Breakdown:")
for status, count in stats['status_breakdown'].items():
    print(f"  {status}: {count}")
```

## Finding Duplicates

```python
# Find duplicate media across posts
duplicates = manager.deduplicate_media()

for dup in duplicates:
    print(f"\nChecksum: {dup['checksum']}")
    print(f"Instances: {dup['total_instances']}")
    print(f"Size: {dup['byte_size']} bytes")
    print(f"Can deduplicate: {dup['can_deduplicate']}")
    print("Posts:")
    for entry in dup['entries']:
        print(f"  - {entry['post_url']}")
```

## Tracking Provenance

```python
# Media from Tumblr
media_tumblr = create_media_entry(
    post_id="12345",
    post_url="https://example.tumblr.com/post/12345",
    timestamp="2023-05-15T14:20:00Z",
    media_type="image",
    filename="photo.jpg",
    original_url="https://64.media.tumblr.com/photo.jpg",
    api_media_urls=["https://64.media.tumblr.com/photo.jpg"],
    retrieved_from="tumblr",
    status="downloaded"
)

# Media from Internet Archive (when missing from Tumblr)
media_archive = create_media_entry(
    post_id="67890",
    post_url="https://example.tumblr.com/post/67890",
    timestamp="2022-01-10T08:30:00Z",
    media_type="image",
    filename="old_photo.jpg",
    original_url="https://64.media.tumblr.com/old_photo.jpg",
    api_media_urls=["https://64.media.tumblr.com/old_photo.jpg"],
    media_missing_on_tumblr=True,
    retrieved_from="internet_archive",
    archive_snapshot_url="https://web.archive.org/web/20220110/...",
    archive_snapshot_timestamp="2022-01-10T08:30:00Z",
    status="downloaded"
)

manager.add_media(media_tumblr)
manager.add_media(media_archive)
manager.save()
```

## Schema Validation

```python
from tumblr_archiver.manifest import validate_manifest, ManifestValidationError

try:
    # Validate manifest structure
    validate_manifest(manager.data)
    print("Manifest is valid!")
    
except ManifestValidationError as e:
    print(f"Validation error: {e}")
```

## Batch Operations

```python
# Add multiple media entries efficiently
media_entries = []

for post in posts_data:
    for media_url in post['media_urls']:
        entry = create_media_entry(
            post_id=str(post['id']),
            post_url=post['url'],
            timestamp=post['timestamp'],
            media_type=post['media_type'],
            filename=extract_filename(media_url),
            original_url=media_url,
            api_media_urls=[media_url],
            status="pending"
        )
        media_entries.append(entry)

# Add all entries
for entry in media_entries:
    manager.add_media(entry)

# Save once at the end
manager.save()
```

## Manifest Recovery

```python
# The manager automatically backs up corrupted manifests
manager = ManifestManager("archive/manifest.json")

try:
    manager.load()
except Exception as e:
    print(f"Error loading manifest: {e}")
    # Check for backup files
    # archive/manifest.json.backup
    # archive/manifest.json.backup.1
    # archive/manifest.json.backup.2
```

## Complete Archive Workflow

```python
from tumblr_archiver.manifest import ManifestManager, create_media_entry, calculate_checksum
from pathlib import Path

# Initialize
output_dir = Path("archive")
media_dir = output_dir / "media"
media_dir.mkdir(parents=True, exist_ok=True)

manager = ManifestManager(output_dir / "manifest.json")
manager.load()
manager.set_blog_info(
    blog_url="https://example.tumblr.com",
    blog_name="example",
    total_posts=100
)

# Process posts
for post in fetch_posts():
    for media_url in post['media_urls']:
        filename = extract_filename(media_url)
        file_path = media_dir / filename
        
        # Check if already downloaded
        if manager.is_downloaded(str(post['id']), filename, file_path):
            print(f"Skipping {filename} (already downloaded)")
            continue
        
        # Add pending entry
        entry = create_media_entry(
            post_id=str(post['id']),
            post_url=post['url'],
            timestamp=post['timestamp'],
            media_type=post['media_type'],
            filename=filename,
            original_url=media_url,
            api_media_urls=[media_url],
            status="pending"
        )
        manager.add_media(entry)
        
        # Download
        try:
            download_file(media_url, file_path)
            
            # Calculate checksum and update
            checksum = calculate_checksum(file_path)
            byte_size = file_path.stat().st_size
            
            manager.update_media(
                str(post['id']),
                filename,
                {
                    "checksum": f"sha256:{checksum}",
                    "byte_size": byte_size,
                    "status": "downloaded"
                }
            )
            
        except Exception as e:
            manager.mark_status(
                str(post['id']),
                filename,
                "failed",
                notes=str(e)
            )
        
        # Save after each download
        manager.save()

# Print final statistics
stats = manager.get_stats()
print(f"\nArchive complete!")
print(f"Total media: {stats['total_media']}")
print(f"Downloaded: {stats['status_breakdown'].get('downloaded', 0)}")
print(f"Failed: {stats['status_breakdown'].get('failed', 0)}")
print(f"Total size: {stats['total_mb']} MB")
```
