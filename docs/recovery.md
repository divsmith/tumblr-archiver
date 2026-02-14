# Media Recovery Module

The media recovery module handles recovering media files that are missing from Tumblr by querying the Internet Archive's Wayback Machine.

## Overview

When Tumblr media files are deleted or become unavailable (404, 403, 410 errors), the recovery module attempts to find archived versions using multiple strategies to maximize recovery success.

## Features

- **Multiple Recovery Strategies**: Tries direct URL lookup, then falls back to post page extraction
- **Async/Await Support**: Efficient concurrent recovery operations
- **Quality Preference**: Prioritizes highest resolution snapshots
- **Error Handling**: Comprehensive error handling with detailed status reporting
- **Batch Operations**: Recover multiple media files concurrently
- **Statistics**: Track recovery success rates and failures

## Architecture

### Classes

#### `MediaRecovery`

Main class for handling media recovery operations.

**Methods:**

- `__init__(wayback_client, config)` - Initialize with WaybackClient and configuration
- `recover_media(media_url, post_url, output_path)` - Recover single media file
- `recover_multiple_media(media_items, max_concurrent)` - Recover multiple files concurrently
- `get_recovery_stats(results)` - Calculate recovery statistics

#### `RecoveryResult`

Dataclass containing recovery operation results.

**Attributes:**

- `media_url` - Original media URL
- `status` - RecoveryStatus enum (SUCCESS, NOT_FOUND, ERROR, SKIPPED)
- `snapshot_url` - Wayback Machine replay URL if successful
- `timestamp` - Snapshot timestamp in YYYYMMDDHHMMSS format
- `file_size` - Size of recovered file in bytes
- `local_path` - Path where file was saved locally
- `strategy` - Which recovery strategy succeeded
- `error_message` - Error details if recovery failed

#### `RecoveryStatus`

Enum defining possible recovery statuses:

- `SUCCESS` - Media successfully recovered
- `NOT_FOUND` - No archived version found
- `ERROR` - Recovery failed with error
- `SKIPPED` - Recovery skipped (e.g., disabled in config)

## Recovery Strategies

The module implements multiple strategies, trying each in sequence until one succeeds:

### 1. Direct Media URL Lookup

Queries the Wayback Machine CDX API directly for the media URL.

- Uses `WaybackClient.get_best_snapshot()` with "highest_quality" preference
- Prefers largest file size (highest resolution)
- Most common case for media that was archived directly

### 2. Post Page Extraction

If direct media URL isn't archived, attempts to find it via the post page.

- Retrieves archived version of the Tumblr post page
- Parses HTML to extract media URLs
- Matches found URLs against the target media URL
- Handles URL variants (different CDN domains, resolutions)

### 3. URL Matching Strategies

When matching media from extracted post pages, tries multiple approaches:

1. **Exact URL match** - Same URL exactly
2. **Same path match** - Same path, different domain (CDN variants)
3. **Same filename match** - Same filename, different path
4. **Base filename match** - Matches without resolution suffix (e.g., `_1280` vs `_500`)

## Usage Examples

### Basic Usage

```python
import asyncio
from pathlib import Path
from tumblr_archiver.config import ArchiverConfig
from tumblr_archiver.wayback_client import WaybackClient
from tumblr_archiver.recovery import MediaRecovery, RecoveryStatus

async def main():
    # Configure
    config = ArchiverConfig(
        blog_url="https://myblog.tumblr.com",
        output_dir=Path("./downloads"),
        wayback_enabled=True
    )
    
    # Initialize clients
    wayback_client = WaybackClient(user_agent="MyApp/1.0")
    
    # Recover media
    async with MediaRecovery(wayback_client, config) as recovery:
        result = await recovery.recover_media(
            media_url="https://64.media.tumblr.com/abc123/tumblr_abc123_1280.jpg",
            post_url="https://myblog.tumblr.com/post/123456789",
            output_path=Path("./downloads/image.jpg")
        )
        
        if result.status == RecoveryStatus.SUCCESS:
            print(f"Recovered! Saved to {result.local_path}")
            print(f"Snapshot from {result.snapshot_datetime}")
        else:
            print(f"Failed: {result.error_message}")

asyncio.run(main())
```

### Check Availability Without Downloading

```python
async with MediaRecovery(wayback_client, config) as recovery:
    # Don't specify output_path to just check availability
    result = await recovery.recover_media(
        media_url="https://64.media.tumblr.com/test.jpg",
        post_url="https://myblog.tumblr.com/post/123"
    )
    
    if result.status == RecoveryStatus.SUCCESS:
        print(f"Available in archive: {result.snapshot_url}")
        print(f"File size: {result.file_size} bytes")
```

### Batch Recovery

```python
async with MediaRecovery(wayback_client, config) as recovery:
    media_items = [
        (media_url1, post_url1, output_path1),
        (media_url2, post_url2, output_path2),
        (media_url3, post_url3, output_path3),
    ]
    
    results = await recovery.recover_multiple_media(
        media_items,
        max_concurrent=2
    )
    
    # Get statistics
    stats = recovery.get_recovery_stats(results)
    print(f"Success rate: {stats['success_rate']:.1f}%")
    print(f"Recovered: {stats['successful']}/{stats['total']}")
```

### Error Handling

```python
async with MediaRecovery(wayback_client, config) as recovery:
    try:
        result = await recovery.recover_media(
            media_url=url,
            post_url=post
        )
        
        match result.status:
            case RecoveryStatus.SUCCESS:
                print(f"Downloaded to {result.local_path}")
            case RecoveryStatus.NOT_FOUND:
                print("Not archived")
            case RecoveryStatus.ERROR:
                print(f"Error: {result.error_message}")
            case RecoveryStatus.SKIPPED:
                print("Recovery disabled")
                
    except ValueError as e:
        print(f"Invalid input: {e}")
```

## Configuration

Recovery behavior is controlled through `ArchiverConfig`:

```python
config = ArchiverConfig(
    blog_url="https://myblog.tumblr.com",
    output_dir=Path("./downloads"),
    
    # Wayback/Recovery settings
    wayback_enabled=True,           # Enable/disable recovery
    wayback_max_snapshots=5,        # Max snapshots to check
    
    # Rate limiting
    rate_limit=1.0,                 # Requests per second
    concurrency=2,                  # Concurrent operations
    max_retries=3,                  # Retry attempts
)
```

## Integration with Downloader

The recovery module integrates with the existing downloader:

```python
from tumblr_archiver.downloader import MediaNotFoundError

async def download_with_recovery(url, post_url, output_path):
    try:
        # Try normal download first
        await downloader.download(url, output_path)
    except MediaNotFoundError:
        # Fall back to recovery
        async with MediaRecovery(wayback_client, config) as recovery:
            result = await recovery.recover_media(
                media_url=url,
                post_url=post_url,
                output_path=output_path
            )
            if result.status != RecoveryStatus.SUCCESS:
                raise Exception(f"Recovery failed: {result.error_message}")
```

## Performance Considerations

### Rate Limiting

- Recovery operations respect Internet Archive rate limits
- Use `max_concurrent` parameter to control concurrency
- Default concurrency matches main downloader settings

### Caching

The recovery module doesn't implement caching, but you can wrap it:

```python
cache = {}

async def cached_recovery(media_url, post_url):
    if media_url in cache:
        return cache[media_url]
    
    result = await recovery.recover_media(media_url, post_url)
    cache[media_url] = result
    return result
```

### Optimization Tips

1. **Batch Operations**: Use `recover_multiple_media()` instead of individual calls
2. **Check Before Download**: Omit `output_path` to check availability first
3. **Adjust Concurrency**: Balance between speed and API respect
4. **Monitor Stats**: Use `get_recovery_stats()` to track success rates

## Error Handling

### Common Errors

**SnapshotNotFoundError**: No archived version exists
- Common for recently posted or never-archived media
- Try querying the post page as fallback

**WaybackError**: Internet Archive API error
- Transient errors: Retry after backoff
- Rate limit errors: Reduce concurrency
- Service errors: Check archive.org status

**ValueError**: Invalid input parameters
- Ensure media_url and post_url are provided
- Validate URL formats before calling

### Recovery Status Flow

```
Input: media_url, post_url
    ↓
Check config.wayback_enabled
    ↓ No → SKIPPED
    ↓ Yes
Try direct media URL
    ↓ Success → SUCCESS
    ↓ Not found
Try post page extraction
    ↓ Success → SUCCESS
    ↓ Not found → NOT_FOUND
    ↓ Error → ERROR
```

## Testing

Run the test suite:

```bash
pytest tests/test_recovery.py -v
```

Run with coverage:

```bash
pytest tests/test_recovery.py --cov=tumblr_archiver.recovery
```

## Logging

The module uses Python's `logging` module:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Or configure specific logger
logger = logging.getLogger('tumblr_archiver.recovery')
logger.setLevel(logging.INFO)
```

Log levels:
- `DEBUG`: Detailed recovery process information
- `INFO`: Recovery attempts and results
- `WARNING`: Non-fatal issues (Wayback errors)
- `ERROR`: Fatal errors with stack traces

## Limitations

1. **Archive Coverage**: Not all media may be archived
2. **Resolution Variants**: May recover different resolution than original
3. **Rate Limits**: Internet Archive has rate limits
4. **Timestamp**: Recovered media may be from different date than original
5. **CDN Changes**: Media URLs change when Tumblr updates CDN servers

## Future Enhancements

Potential improvements:

- [ ] Parallel snapshot checking for faster lookups
- [ ] Smart caching of recovery results
- [ ] Alternative archive sources (archive.today, etc.)
- [ ] Video quality selection (resolution preference)
- [ ] Automatic retry with exponential backoff
- [ ] Recovery queue with priority
- [ ] Persistent recovery history

## See Also

- [WaybackClient Documentation](./wayback_client.md)
- [Configuration Guide](./configuration.md)
- [Downloader Documentation](./downloader.md)
- [Example Scripts](../examples/recovery_example.py)
