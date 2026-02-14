# Configuration Reference

Comprehensive reference for configuring Tumblr Archiver.

## Table of Contents

- [Overview](#overview)
- [Configuration Methods](#configuration-methods)
- [Configuration Options](#configuration-options)
- [Rate Limiting](#rate-limiting)
- [Concurrency Tuning](#concurrency-tuning)
- [Resume Capability](#resume-capability)
- [Dry Run Mode](#dry-run-mode)
- [Advanced Configuration](#advanced-configuration)
- [Best Practices](#best-practices)

## Overview

Tumblr Archiver can be configured through:
- Command-line arguments (primary method)
- Environment variables (planned)
- Configuration files (planned)

Currently, all configuration is done via CLI options.

## Configuration Methods

### Command-Line Arguments

The primary configuration method:

```bash
tumblr-archiver myblog \
  --output ./archives \
  --rate 2.0 \
  --concurrency 3 \
  --max-retries 5
```

Use `--help` to see all available options:

```bash
tumblr-archiver --help
```

## Configuration Options

### Required Arguments

#### `BLOG`
**Type**: String (positional argument)  
**Required**: Yes  
**Description**: The Tumblr blog to archive

**Formats**:
- Blog name: `myblog`
- Full URL: `https://myblog.tumblr.com`
- Domain: `myblog.tumblr.com`

**Examples**:
```bash
tumblr-archiver myblog
tumblr-archiver https://photography-blog.tumblr.com
tumblr-archiver art-blog.tumblr.com
```

**Validation**:
- Must contain only letters, numbers, and hyphens
- Cannot start or end with a hyphen
- Automatically strips `.tumblr.com` suffix

### Output Configuration

#### `--output`, `-o`
**Type**: Path  
**Default**: `./downloads`  
**Description**: Directory where media files will be saved

**Behavior**:
- Creates directory if it doesn't exist
- Creates subdirectory for each blog
- Stores manifest in blog subdirectory

**Structure**:
```
<output>/
└── <blog-name>/
    ├── manifest.json
    ├── media files...
```

**Examples**:
```bash
# Relative path
tumblr-archiver myblog --output ./archives

# Absolute path
tumblr-archiver myblog --output /mnt/storage/tumblr

# Home directory
tumblr-archiver myblog --output ~/tumblr-archives
```

**Permissions**: Requires write access to the directory

### Concurrency Configuration

#### `--concurrency`, `-c`
**Type**: Integer  
**Range**: 1-10  
**Default**: `2`  
**Description**: Number of concurrent download workers

**How it works**:
- Each worker downloads one file at a time
- More workers = faster downloads
- More workers = more network/CPU usage

**Tuning Guidelines**:

| Connection | Recommended | Notes |
|------------|-------------|-------|
| Slow (<10 Mbps) | 1-2 | Avoid overwhelming connection |
| Medium (10-50 Mbps) | 2-4 | Balanced performance |
| Fast (>50 Mbps) | 4-6 | Maximum throughput |
| Very Fast (>100 Mbps) | 6-8 | Diminishing returns >8 |

**Examples**:
```bash
# Conservative (default)
tumblr-archiver myblog --concurrency 2

# Balanced
tumblr-archiver myblog --concurrency 4

# Aggressive
tumblr-archiver myblog --concurrency 8
```

**Trade-offs**:
- **Higher**: Faster downloads, more resource usage, higher chance of rate limiting
- **Lower**: Slower downloads, less resource usage, more respectful

### Rate Limiting Configuration

#### `--rate`, `-r`
**Type**: Float  
**Minimum**: `0.1`  
**Default**: `1.0`  
**Description**: Maximum requests per second

See [Rate Limiting](#rate-limiting) section for detailed guidance.

**Examples**:
```bash
# Very conservative
tumblr-archiver myblog --rate 0.5

# Default (recommended)
tumblr-archiver myblog --rate 1.0

# Faster (use carefully)
tumblr-archiver myblog --rate 3.0
```

### Resume Configuration

#### `--resume` / `--no-resume`
**Type**: Boolean flag  
**Default**: `--resume` (enabled)  
**Description**: Enable or disable resume capability

**Enabled behavior** (default):
- Loads manifest on startup
- Skips already downloaded files
- Retries failed downloads
- Continues from last position

**Disabled behavior**:
- Ignores existing manifest
- Starts fresh download
- May re-download existing files (but uses checksums to avoid duplicates)

**Examples**:
```bash
# Resume (default)
tumblr-archiver myblog --resume

# Start fresh
tumblr-archiver myblog --no-resume
```

**When to disable resume**:
- Manifest is corrupted
- Want to re-verify all downloads
- Testing configuration changes

See [Resume Capability](#resume-capability) section for details.

### Content Filtering

#### `--include-reblogs` / `--exclude-reblogs`
**Type**: Boolean flag  
**Default**: `--include-reblogs` (enabled)  
**Description**: Include or exclude reblogged posts

**Examples**:
```bash
# Include reblogs (default)
tumblr-archiver myblog --include-reblogs

# Only original content
tumblr-archiver myblog --exclude-reblogs
```

**Use cases**:
- `--exclude-reblogs`: Archive only original content
- `--include-reblogs`: Complete archive including reblogs

**Impact**: Can significantly reduce archive size for blogs with many reblogs

### Embedded Media

#### `--download-embeds`
**Type**: Boolean flag  
**Default**: Disabled  
**Description**: Download embedded media from external platforms

**Supported platforms**:
- YouTube
- Vimeo
- SoundCloud
- Spotify

**Examples**:
```bash
# Enable embed downloads
tumblr-archiver myblog --download-embeds
```

**Considerations**:
- Slower download process
- Requires additional API calls
- May need platform API keys
- Larger storage requirements

**Recommendation**: Enable only if you need embedded content

### Testing Configuration

#### `--dry-run`
**Type**: Boolean flag  
**Default**: Disabled  
**Description**: Simulate operations without downloading

See [Dry Run Mode](#dry-run-mode) section for details.

**Examples**:
```bash
tumblr-archiver myblog --dry-run
```

### Logging Configuration

#### `--verbose`, `-v`
**Type**: Boolean flag  
**Default**: Disabled  
**Description**: Enable detailed logging output

**Normal output**:
```
Starting archive of 'myblog'...
Downloading... [████████] 100/100 100%
Complete!
```

**Verbose output**:
```
[DEBUG] Loading configuration...
[DEBUG] Initializing HTTP client
[DEBUG] GET https://myblog.tumblr.com/page/1
[DEBUG] Response: 200 OK
[DEBUG] Found 25 posts on page 1
[DEBUG] Extracting media from post #12345
[DEBUG] Downloading: https://...image.jpg
[INFO] Downloaded: image_001.jpg (234 KB)
...
```

**Examples**:
```bash
# Verbose logging
tumblr-archiver myblog --verbose

# Short form
tumblr-archiver myblog -v
```

**When to use**:
- Debugging issues
- Monitoring progress
- Understanding behavior
- Performance analysis

### Network Configuration

#### `--timeout`
**Type**: Float  
**Minimum**: `1.0`  
**Default**: `30.0`  
**Description**: HTTP request timeout in seconds

**Examples**:
```bash
# Short timeout (fast connection)
tumblr-archiver myblog --timeout 15.0

# Long timeout (slow connection or large files)
tumblr-archiver myblog --timeout 120.0
```

**When to increase**:
- Slow internet connection
- Downloading large video files
- Experiencing timeout errors
- Using VPN/proxy

**When to decrease**:
- Fast connection
- Want to fail fast on issues
- Downloading small files only

#### `--max-retries`
**Type**: Integer  
**Range**: 0-10  
**Default**: `3`  
**Description**: Maximum retry attempts for failed requests

**Retry behavior**:
- Exponential backoff between retries
- Retries on temporary failures (5xx, timeouts)
- No retry on permanent failures (404, 403)

**Examples**:
```bash
# No retries
tumblr-archiver myblog --max-retries 0

# More retries (unstable connection)
tumblr-archiver myblog --max-retries 7
```

**Recommended values**:
- **0-1**: Fast failure, stable connection
- **3**: Default, balanced approach
- **5-7**: Unstable connection, maximize success
- **10**: Maximum persistence

## Rate Limiting

### Understanding Rate Limiting

Rate limiting controls how many requests are made per second to avoid:
- Overloading Tumblr servers
- Getting blocked (429 errors)
- Consuming excessive bandwidth
- Being flagged as abusive

### Configuration

The `--rate` option sets requests per second:

```bash
tumblr-archiver myblog --rate 2.0  # 2 requests/second
```

### Guidelines

#### Conservative (Recommended)
```bash
--rate 0.5  # 1 request every 2 seconds
--rate 1.0  # 1 request per second (default)
```

**Use for**:
- Personal archiving
- Respectful scraping
- Avoiding issues
- Long-running archives

#### Moderate
```bash
--rate 2.0  # 2 requests per second
--rate 3.0  # 3 requests per second
```

**Use for**:
- Faster archiving
- Good internet connection
- Time-sensitive archiving
- Testing with monitoring

#### Aggressive (Use Carefully)
```bash
--rate 5.0   # 5 requests per second
--rate 10.0  # 10 requests per second
```

**⚠️ Warning**: High risk of rate limiting

**Use only if**:
- You have explicit permission
- Time-critical archiving
- Continuously monitor for errors

### Rate Limiting Interaction

Rate limiting interacts with concurrency:

```bash
# 4 workers, 2 req/s = ~8 req/s total
tumblr-archiver myblog --concurrency 4 --rate 2.0
```

**Effective rate** = `concurrency × rate`

**Example combinations**:

| Concurrency | Rate | Effective Rate | Profile |
|-------------|------|----------------|---------|
| 1 | 0.5 | 0.5 req/s | Very conservative |
| 2 | 1.0 | 2 req/s | Conservative (default) |
| 3 | 2.0 | 6 req/s | Moderate |
| 4 | 2.0 | 8 req/s | Aggressive |
| 6 | 3.0 | 18 req/s | Very aggressive |

### Handling Rate Limit Errors

If you get rate limited (429 errors):

1. **Immediately stop** the current run
2. **Wait 5-10 minutes**
3. **Reduce rate**: `--rate 0.5`
4. **Reduce concurrency**: `--concurrency 1`
5. **Resume**: Tool will retry failed items

```bash
# After rate limiting, use conservative settings
tumblr-archiver myblog --rate 0.5 --concurrency 1
```

## Concurrency Tuning

### Understanding Concurrency

Concurrency determines how many files download simultaneously.

### Performance Impact

**Higher concurrency**:
- ✅ Faster total download time
- ✅ Better bandwidth utilization
- ❌ More CPU/memory usage
- ❌ Higher rate limit risk
- ❌ More complex error handling

**Lower concurrency**:
- ✅ Lower resource usage
- ✅ More stable
- ✅ Easier to debug
- ❌ Slower downloads
- ❌ Underutilized bandwidth

### Tuning Process

1. **Start with default** (2 workers):
   ```bash
   tumblr-archiver myblog --concurrency 2
   ```

2. **Monitor performance**:
   - Watch download speed
   - Check CPU usage
   - Monitor memory
   - Look for errors

3. **Increase gradually**:
   ```bash
   tumblr-archiver myblog --concurrency 4
   ```

4. **Find sweet spot** where:
   - Downloads are fast
   - No rate limiting
   - Stable operation
   - Acceptable resource usage

### System-Specific Recommendations

#### Low-End System (Raspberry Pi, old laptop)
```bash
--concurrency 1
--rate 0.5
```

#### Mid-Range System (typical laptop/desktop)
```bash
--concurrency 2-4
--rate 1.0-2.0
```

#### High-End System (powerful desktop/server)
```bash
--concurrency 4-8
--rate 2.0-3.0
```

#### Cloud Instance
```bash
--concurrency 6-10
--rate 3.0-5.0
# Monitor costs and respect rate limits
```

## Resume Capability

### How Resume Works

1. **Manifest tracking**: `manifest.json` tracks all downloads
2. **State persistence**: Each file's status is saved
3. **Automatic resume**: Tool detects existing manifest
4. **Smart skipping**: Already downloaded files are skipped

### Manifest Structure

Located at: `<output>/<blog>/manifest.json`

```json
{
  "blog_name": "myblog",
  "created_at": "2026-02-13T10:30:00Z",
  "updated_at": "2026-02-13T11:45:00Z",
  "media_items": [
    {
      "url": "https://...",
      "filename": "image_001.jpg",
      "status": "completed",
      "checksum": "abc123...",
      "size_bytes": 234567
    },
    {
      "url": "https://...",
      "filename": "video_001.mp4",
      "status": "failed",
      "error": "Connection timeout"
    },
    {
      "url": "https://...",
      "filename": "image_002.jpg",
      "status": "pending"
    }
  ]
}
```

### Status Values

- **`completed`**: Successfully downloaded and verified
- **`failed`**: Download failed (will retry on next run)
- **`pending`**: Not yet attempted
- **`skipped`**: Intentionally skipped (duplicate, filtered, etc.)

### Using Resume

#### Normal Operation (Resume Enabled)

```bash
# First run
tumblr-archiver myblog --output ./archives

# If interrupted, run again
tumblr-archiver myblog --output ./archives
# Automatically resumes from where it left off
```

#### Starting Fresh

```bash
# Ignore existing progress
tumblr-archiver myblog --output ./archives --no-resume
```

#### Manual Manifest Management

```bash
# Backup manifest
cp downloads/myblog/manifest.json downloads/myblog/manifest.backup.json

# Remove manifest to start fresh
rm downloads/myblog/manifest.json

# Check manifest status
cat downloads/myblog/manifest.json | grep -c "completed"
cat downloads/myblog/manifest.json | grep -c "failed"
```

### Manifest Corruption

If manifest becomes corrupted:

```bash
# Backup corrupt manifest
mv downloads/myblog/manifest.json downloads/myblog/manifest.corrupted.json

# Start with fresh manifest (existing files won't be re-downloaded)
tumblr-archiver myblog --output ./downloads --no-resume
```

The tool uses checksums to avoid re-downloading existing files even without manifest.

## Dry Run Mode

### Purpose

Test archiving without actually downloading files.

### Usage

```bash
tumblr-archiver myblog --dry-run
```

### What Dry Run Does

✅ **Performs**:
- Blog scraping
- Post parsing
- Media extraction
- Internet Archive lookups
- Size estimation
- Progress reporting

❌ **Skips**:
- File downloads
- Manifest updates
- Disk writes

### Output Example

```bash
$ tumblr-archiver myblog --dry-run

Dry run mode: No files will be downloaded

Scanning myblog.tumblr.com...
  Found 150 posts
  Found 423 media items
    - 312 images
    - 98 videos
    - 13 audio files

Estimated download size: 1.2 GB

Checking Internet Archive availability...
  245 items available on Tumblr
  178 items available on Internet Archive

Summary:
  Total items: 423
  Available: 423 (100%)
  Would download: 423
  Estimated time: ~15 minutes (at current rate)

Dry run complete. No files were downloaded.
```

### Use Cases

1. **Preview before archiving**:
   ```bash
   tumblr-archiver unknown-blog --dry-run
   ```

2. **Estimate size and time**:
   ```bash
   tumblr-archiver large-blog --dry-run
   ```

3. **Test configuration**:
   ```bash
   tumblr-archiver myblog --dry-run --exclude-reblogs --download-embeds
   ```

4. **Verify blog accessibility**:
   ```bash
   tumblr-archiver maybe-deleted-blog --dry-run
   ```

5. **Check Archive availability**:
   ```bash
   tumblr-archiver old-blog --dry-run
   ```

### Combining with Verbose

```bash
tumblr-archiver myblog --dry-run --verbose
```

Shows detailed processing without downloads.

## Advanced Configuration

### Batch Processing

Process multiple blogs:

```bash
#!/bin/bash
BLOGS=("blog1" "blog2" "blog3")
RATE=0.5
CONCURRENCY=2

for blog in "${BLOGS[@]}"; do
  echo "Processing $blog..."
  tumblr-archiver "$blog" \
    --output ./archives \
    --rate "$RATE" \
    --concurrency "$CONCURRENCY"
  
  echo "Waiting 60 seconds before next blog..."
  sleep 60
done
```

### Custom Timeout per Blog

```bash
# Fast, stable blog
tumblr-archiver fast-blog --timeout 15.0

# Slow, large files
tumblr-archiver slow-blog --timeout 120.0
```

### Memory-Constrained Systems

```bash
tumblr-archiver myblog \
  --concurrency 1 \
  --rate 0.5 \
  --timeout 60.0
```

### Network-Constrained Systems

```bash
tumblr-archiver myblog \
  --concurrency 1 \
  --rate 0.3 \
  --timeout 120.0 \
  --max-retries 5
```

### Maximum Performance (Use Cautiously)

```bash
tumblr-archiver myblog \
  --concurrency 8 \
  --rate 3.0 \
  --timeout 30.0 \
  --max-retries 2
```

Monitor closely for:
- Rate limiting
- Network errors
- System resource usage

## Best Practices

### 1. Start Conservative

```bash
# First run: use defaults
tumblr-archiver myblog
```

### 2. Monitor and Adjust

```bash
# Add verbose to see what's happening
tumblr-archiver myblog --verbose
```

### 3. Test with Dry Run

```bash
# Always test new configurations
tumblr-archiver myblog --dry-run [other options]
```

### 4. Keep Resume Enabled

```bash
# Resume is your friend
tumblr-archiver myblog --resume  # (default)
```

### 5. Be Respectful

```bash
# Use reasonable rate limits
tumblr-archiver myblog --rate 1.0  # or lower
```

### 6. Document Your Configuration

```bash
# Save your working configuration
cat > config.sh <<EOF
BLOG="myblog"
OUTPUT="./archives"
RATE=1.0
CONCURRENCY=3
OPTS="--exclude-reblogs --verbose"

tumblr-archiver \$BLOG --output \$OUTPUT --rate \$RATE --concurrency \$CONCURRENCY \$OPTS
EOF
```

### 7. Regular Backups

```bash
# Archive active blogs regularly
# crontab -e
0 2 * * * /path/to/tumblr-archiver my-active-blog --output /backups
```

### 8. Review Manifests

```bash
# Check for failures
jq '.media_items[] | select(.status=="failed")' downloads/myblog/manifest.json

# Count statistics
jq '.media_items | group_by(.status) | map({status: .[0].status, count: length})' \
  downloads/myblog/manifest.json
```

## Next Steps

- See [Usage Guide](usage.md) for workflows
- Read [Troubleshooting](troubleshooting.md) for issue resolution
- Check [Architecture](architecture.md) for internals
- Review [examples/](../examples/) for scripts

## Configuration Checklist

Before running:
- [ ] Verified blog name/URL
- [ ] Checked available disk space
- [ ] Set appropriate output directory
- [ ] Chose suitable rate limit
- [ ] Set appropriate concurrency
- [ ] Tested with `--dry-run`
- [ ] Enabled `--verbose` for first run
- [ ] Planned for interruptions (resume enabled)

For large archives:
- [ ] Estimated total size
- [ ] Verified network stability
- [ ] Checked system resources
- [ ] Planned downtime/interruptions
- [ ] Set up monitoring
