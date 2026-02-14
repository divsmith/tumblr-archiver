# Tumblr Archiver Module

## Overview

The `archiver.py` module is the central orchestrator for the Tumblr Media Archiver project. It coordinates all components to archive a Tumblr blog's media content with comprehensive error handling, recovery capabilities, and progress tracking.

## Architecture

The `TumblrArchiver` class integrates the following modules:

- **tumblr_api.py** - Fetches blog info and posts from Tumblr API
- **downloader.py** - Manages concurrent file downloads with verification
- **manifest.py** - Tracks download state and metadata
- **wayback_client.py** - Recovers missing media from Internet Archive
- **rate_limiter.py** - Enforces API rate limits
- **retry.py** - Handles transient failures with exponential backoff
- **config.py** - Configuration management

## Key Features

### 1. Complete Blog Archival
- Fetches ALL posts from a blog using pagination
- Extracts media from all post types (photos, videos, etc.)
- Handles both legacy and NPF (Neue Post Format) posts

### 2. Resume Support
- Tracks downloaded files in a manifest
- Skips already-downloaded media on restart
- Verifies checksums to ensure integrity

### 3. Wayback Machine Recovery
- Automatically attempts recovery for missing media
- Selects best quality snapshot available
- Falls back to most recent if quality unavailable

### 4. Progress Tracking
- Reports progress through callback mechanism
- Tracks detailed statistics (downloaded, failed, recovered, etc.)
- Provides comprehensive result summary

### 5. Error Handling
- Gracefully handles API errors, rate limits, network issues
- Logs errors for troubleshooting
- Continues processing remaining media after failures

### 6. Performance
- Concurrent downloads with configurable limits
- Rate limiting to respect API quotas
- Efficient checksum computation

## Classes

### TumblrArchiver

Main orchestrator class.

#### Constructor

```python
TumblrArchiver(config: ArchiverConfig)
```

**Parameters:**
- `config` (ArchiverConfig): Configuration object with all settings

**Raises:**
- `ArchiverError`: If configuration is invalid or clients can't be initialized

#### Key Methods

##### `async archive_blog() -> ArchiveResult`

Main entry point that orchestrates the entire archiving process.

**Returns:**
- `ArchiveResult`: Comprehensive results with statistics

**Process:**
1. Fetch blog information
2. Load or initialize manifest
3. Fetch all posts from the blog
4. Extract and download media from each post
5. Handle missing media with Wayback Machine recovery
6. Update manifest with results
7. Return comprehensive results

**Example:**
```python
async def archive():
    config = ArchiverConfig(
        blog_url="staff.tumblr.com",
        output_dir=Path("./archives"),
        tumblr_api_key="YOUR_API_KEY"
    )
    
    archiver = TumblrArchiver(config)
    result = await archiver.archive_blog()
    
    print(result)  # Prints formatted summary
    print(f"Downloaded: {result.statistics.media_downloaded}")
    
    archiver.close()

asyncio.run(archive())
```

##### `set_progress_callback(callback: Callable)`

Set a callback function to receive progress updates.

**Parameters:**
- `callback`: Function that receives a dict with progress information

**Callback Events:**
- `start` - Archiving started
- `fetch_blog_info` - Fetching blog information
- `fetch_posts` - Fetching posts (includes current/total)
- `process_post` - Processing a post (includes post details)
- `complete` - Archiving completed
- `error` - An error occurred

**Example:**
```python
def progress_handler(data):
    event = data['event']
    if event == 'fetch_posts':
        print(f"Fetching: {data['current']}/{data['total']}")
    elif event == 'process_post':
        print(f"Post {data['post_index']}: {data['media_count']} media")

archiver.set_progress_callback(progress_handler)
```

##### `close()`

Clean up resources (closes API client).

**Example:**
```python
archiver.close()
```

### ArchiveResult

Result object containing outcome and statistics.

#### Attributes

- `blog_name` (str): Name of the archived blog
- `blog_url` (str): URL of the blog
- `success` (bool): Whether archiving succeeded
- `statistics` (ArchiveStatistics): Detailed statistics
- `manifest_path` (Path): Path to the manifest file
- `output_dir` (Path): Output directory
- `start_time` (datetime): When archiving started
- `end_time` (datetime): When archiving completed
- `error_message` (Optional[str]): Error message if failed

#### Properties

- `duration_seconds` (float): Duration in seconds

#### Methods

- `__str__()`: Returns human-readable summary

### ArchiveStatistics

Detailed statistics about an archive operation.

#### Attributes

- `total_posts` (int): Total posts in blog
- `total_media` (int): Total media items found
- `media_downloaded` (int): Successfully downloaded from Tumblr
- `media_skipped` (int): Skipped (already downloaded)
- `media_recovered` (int): Recovered from Wayback Machine
- `media_failed` (int): Failed to download
- `media_missing` (int): Missing and couldn't recover
- `bytes_downloaded` (int): Total bytes downloaded
- `posts_processed` (int): Number of posts processed
- `errors` (List[str]): List of error messages

#### Methods

- `to_dict()`: Convert to dictionary

## Usage Examples

### Basic Usage

```python
import asyncio
from pathlib import Path
from tumblr_archiver import TumblrArchiver
from tumblr_archiver.config import ArchiverConfig

async def main():
    config = ArchiverConfig(
        blog_url="example.tumblr.com",
        output_dir=Path("./archives"),
        tumblr_api_key="YOUR_API_KEY",
        resume=True,
        recover_removed_media=True
    )
    
    archiver = TumblrArchiver(config)
    result = await archiver.archive_blog()
    
    if result.success:
        print(f"✅ Success! Downloaded {result.statistics.media_downloaded} files")
    else:
        print(f"❌ Failed: {result.error_message}")
    
    archiver.close()

asyncio.run(main())
```

### With Progress Tracking

```python
def progress_callback(data):
    event = data.get('event')
    if event == 'start':
        print(f"🚀 Starting: {data['blog']}")
    elif event == 'fetch_posts':
        current = data['current']
        total = data['total']
        print(f"📝 Posts: {current}/{total} ({current*100//total}%)")
    elif event == 'process_post':
        print(f"🖼️  Post {data['post_index']}/{data['total_posts']}")

archiver = TumblrArchiver(config)
archiver.set_progress_callback(progress_callback)
result = await archiver.archive_blog()
```

### Dry Run Mode

Test what would be downloaded without actually downloading:

```python
config = ArchiverConfig(
    blog_url="example.tumblr.com",
    output_dir=Path("./archives"),
    tumblr_api_key="YOUR_API_KEY",
    dry_run=True  # Enable dry run
)

archiver = TumblrArchiver(config)
result = await archiver.archive_blog()

print(f"Would download {result.statistics.total_media} media items")
```

### Resume Interrupted Download

```python
config = ArchiverConfig(
    blog_url="example.tumblr.com",
    output_dir=Path("./archives/example"),
    tumblr_api_key="YOUR_API_KEY",
    resume=True  # Enable resume
)

archiver = TumblrArchiver(config)
result = await archiver.archive_blog()

print(f"Skipped {result.statistics.media_skipped} already downloaded")
print(f"Downloaded {result.statistics.media_downloaded} new files")
```

### Archive Multiple Blogs

```python
blogs = ["blog1.tumblr.com", "blog2.tumblr.com", "blog3.tumblr.com"]

for blog_url in blogs:
    config = ArchiverConfig(
        blog_url=blog_url,
        output_dir=Path("./archives"),
        tumblr_api_key="YOUR_API_KEY"
    )
    
    archiver = TumblrArchiver(config)
    
    try:
        result = await archiver.archive_blog()
        print(f"✅ {blog_url}: {result.statistics.media_downloaded} files")
    except Exception as e:
        print(f"❌ {blog_url}: {e}")
    finally:
        archiver.close()
```

### Custom Settings

```python
config = ArchiverConfig(
    blog_url="example.tumblr.com",
    output_dir=Path("./archives"),
    tumblr_api_key="YOUR_API_KEY",
    
    # Only original posts (no reblogs)
    include_reblogs=False,
    
    # Aggressive recovery
    recover_removed_media=True,
    wayback_enabled=True,
    wayback_max_snapshots=10,
    
    # Performance tuning
    rate_limit=2.0,  # 2 requests/second
    concurrency=5,   # 5 concurrent downloads
    max_retries=5,
    
    # Logging
    verbose=True,
    log_file=Path("./archive.log")
)
```

### As Context Manager

```python
async with TumblrArchiver(config) as archiver:
    archiver.set_progress_callback(progress_handler)
    result = await archiver.archive_blog()
    print(result)
# Automatically closed after context
```

## Error Handling

### Common Exceptions

- **ArchiverError**: Base exception for archiver errors
  - Raised for configuration errors
  - Raised when API calls fail
  - Raised for unrecoverable errors

### Error Recovery

The archiver handles errors gracefully:

1. **API Errors**: Logged and operation continues
2. **Download Errors**: Retried with exponential backoff
3. **Missing Media**: Attempts Wayback recovery
4. **Network Issues**: Retried automatically

### Error Tracking

Errors are collected in `result.statistics.errors`:

```python
result = await archiver.archive_blog()

if result.statistics.errors:
    print(f"Encountered {len(result.statistics.errors)} errors:")
    for error in result.statistics.errors[:10]:
        print(f"  - {error}")
```

## Performance Tuning

### Configuration Options

```python
config = ArchiverConfig(
    # Rate limiting
    rate_limit=1.0,      # Tumblr API: 1 req/sec (default)
    
    # Concurrency
    concurrency=3,        # 3 concurrent downloads (default: 2)
    
    # Retry behavior
    max_retries=3,        # Max retry attempts (default: 3)
    base_backoff=1.0,     # Initial backoff (default: 1.0s)
    max_backoff=32.0,     # Max backoff (default: 32.0s)
)
```

### Recommendations

- **Small blogs (<1000 posts)**: `concurrency=2-3`, `rate_limit=1.0`
- **Medium blogs (1000-10000 posts)**: `concurrency=3-5`, `rate_limit=1.0`
- **Large blogs (>10000 posts)**: `concurrency=5-8`, `rate_limit=1.0`

⚠️ **Warning**: Don't exceed Tumblr's rate limits or your API key may be throttled.

## Output Structure

```
archives/
└── example.tumblr.com/
    ├── manifest.json           # Tracking file
    ├── 123456789_0_abc123.jpg  # Downloaded media
    ├── 123456789_1_def456.jpg
    ├── 987654321_0_ghi789.jpg
    └── ...
```

### Manifest Format

The manifest tracks all media with metadata:

```json
{
  "blog_url": "https://example.tumblr.com",
  "blog_name": "example",
  "archive_date": "2026-02-14T10:30:00Z",
  "total_posts": 100,
  "total_media": 250,
  "media": [
    {
      "post_id": "123456789",
      "post_url": "https://example.tumblr.com/post/123456789",
      "timestamp": 1609459200,
      "media_type": "photo",
      "filename": "123456789_0_abc123.jpg",
      "byte_size": 204800,
      "checksum": "sha256:abc123...",
      "original_url": "https://64.media.tumblr.com/...",
      "api_media_urls": ["https://64.media.tumblr.com/..."],
      "media_missing_on_tumblr": false,
      "retrieved_from": "tumblr",
      "archive_snapshot_url": "",
      "archive_snapshot_timestamp": "",
      "status": "downloaded",
      "notes": ""
    }
  ]
}
```

## Integration

### With CLI

The archiver integrates with the CLI module:

```python
# In cli.py
from tumblr_archiver import TumblrArchiver

async def archive_command(args):
    config = create_config_from_args(args)
    archiver = TumblrArchiver(config)
    result = await archiver.archive_blog()
    print(result)
```

### Programmatic Use

Use as a library in your own code:

```python
from tumblr_archiver import TumblrArchiver
from tumblr_archiver.config import ArchiverConfig

# Your custom integration
async def archive_with_custom_logic():
    config = ArchiverConfig(...)
    archiver = TumblrArchiver(config)
    
    # Add custom progress tracking
    archiver.set_progress_callback(my_custom_handler)
    
    # Run archive
    result = await archiver.archive_blog()
    
    # Custom post-processing
    if result.success:
        send_notification(f"Archived {result.blog_name}")
        update_database(result)
    
    return result
```

## Testing

Run the test suite:

```bash
pytest tests/test_archiver.py -v
```

Test coverage includes:
- Unit tests for all classes and methods
- Integration tests for full workflow
- Mock-based tests for external dependencies
- Error handling scenarios
- Edge cases

## See Also

- [Configuration Guide](configuration.md)
- [Download Manager](downloader.md)
- [Manifest Format](MANIFEST_USAGE.md)
- [Examples](../examples/archiver_example.py)
