# Usage Guide

Comprehensive guide to using Tumblr Archiver for archiving Tumblr blog media.

## Table of Contents

- [Quick Start](#quick-start)
- [Basic Usage](#basic-usage)
- [CLI Options](#cli-options)
- [Common Workflows](#common-workflows)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

## Quick Start

Archive a Tumblr blog with default settings:

```bash
tumblr-archiver myblog
```

This will:
- Download all media from `myblog.tumblr.com`
- Save files to `./downloads/myblog/`
- Use conservative rate limiting (1 req/s)
- Resume if interrupted
- Skip embedded media (YouTube, Vimeo, etc.)

## Basic Usage

### Specifying the Blog

You can specify the blog in multiple formats:

```bash
# Just the blog name
tumblr-archiver myblog

# Full URL
tumblr-archiver https://myblog.tumblr.com

# Domain format
tumblr-archiver myblog.tumblr.com
```

All formats are normalized to the blog name internally.

### Output Directory

Specify where to save downloaded media:

```bash
tumblr-archiver myblog --output /path/to/archive
```

Default: `./downloads/`

The tool creates a subdirectory for each blog:
```
downloads/
└── myblog/
    ├── manifest.json       # Download tracking
    ├── image_001.jpg
    ├── image_002.png
    └── video_001.mp4
```

## CLI Options

### Core Options

#### `BLOG` (required)
The blog to archive. Can be a name, URL, or domain.

```bash
tumblr-archiver myblog
```

#### `--output`, `-o`
Output directory for downloaded media.

```bash
tumblr-archiver myblog --output ./my-archive
```

**Default**: `./downloads`

#### `--concurrency`, `-c`
Number of concurrent download workers (1-10).

```bash
tumblr-archiver myblog --concurrency 4
```

**Default**: `2`  
**Range**: 1-10  
**Recommendation**: Start with 2-3, increase if your connection can handle it.

#### `--rate`, `-r`
Maximum requests per second.

```bash
tumblr-archiver myblog --rate 2.0
```

**Default**: `1.0`  
**Minimum**: `0.1`  
**Recommendation**: 
- Use 0.5-1.0 for respectful archiving
- Use 2.0-3.0 if you need faster downloads
- Avoid exceeding 5.0 to prevent rate limiting

#### `--resume` / `--no-resume`
Enable or disable resume capability.

```bash
# Disable resume (start fresh)
tumblr-archiver myblog --no-resume

# Enable resume (default)
tumblr-archiver myblog --resume
```

**Default**: Enabled

Resume uses a manifest file to track:
- Successfully downloaded files
- Failed downloads
- Pending downloads

#### `--include-reblogs` / `--exclude-reblogs`
Include or exclude reblogged posts.

```bash
# Exclude reblogs (only original posts)
tumblr-archiver myblog --exclude-reblogs

# Include reblogs (default)
tumblr-archiver myblog --include-reblogs
```

**Default**: Include reblogs

#### `--download-embeds`
Download embedded media from external platforms.

```bash
tumblr-archiver myblog --download-embeds
```

**Default**: Disabled

Supports:
- YouTube videos
- Vimeo videos
- SoundCloud audio
- Spotify embeds

**Note**: Requires additional dependencies and may be slower.

#### `--dry-run`
Simulate the archiving process without downloading.

```bash
tumblr-archiver myblog --dry-run
```

**Use cases**:
- Preview what would be downloaded
- Test configuration
- Estimate download size
- Verify blog accessibility

#### `--verbose`, `-v`
Enable detailed logging output.

```bash
tumblr-archiver myblog --verbose
```

**Output includes**:
- HTTP requests and responses
- Parsing details
- File operations
- Error stack traces

### Advanced Options

#### `--max-retries`
Maximum retry attempts for failed requests.

```bash
tumblr-archiver myblog --max-retries 5
```

**Default**: `3`  
**Range**: 0-10

#### `--timeout`
HTTP request timeout in seconds.

```bash
tumblr-archiver myblog --timeout 60.0
```

**Default**: `30.0`  
**Minimum**: `1.0`

Increase for slow connections or large files.

### Getting Help

```bash
# Show version
tumblr-archiver --version

# Show help
tumblr-archiver --help
```

## Common Workflows

### 1. First-Time Archive

Archive a blog for the first time with conservative settings:

```bash
tumblr-archiver myblog \
  --output ./archives \
  --rate 1.0 \
  --concurrency 2 \
  --verbose
```

**Why these settings?**
- Conservative rate limiting prevents issues
- Verbose output helps monitor progress
- Resume is enabled by default

### 2. Resume Interrupted Download

If the download was interrupted, simply run the same command again:

```bash
tumblr-archiver myblog --output ./archives
```

The tool automatically:
- Loads the manifest
- Skips already downloaded files
- Continues from where it left off

### 3. Fast Archive (Good Connection)

If you have a fast, stable connection:

```bash
tumblr-archiver myblog \
  --output ./archives \
  --rate 3.0 \
  --concurrency 5
```

**Monitor for**:
- Rate limiting errors (429 status)
- Connection timeouts
- Incomplete downloads

### 4. Archive Only Original Content

Exclude reblogged posts:

```bash
tumblr-archiver myblog \
  --exclude-reblogs \
  --output ./original-content
```

### 5. Complete Archive with Embeds

Download everything including embedded media:

```bash
tumblr-archiver myblog \
  --download-embeds \
  --output ./complete-archive \
  --rate 0.5 \
  --concurrency 2
```

**Note**: Embedded media download is slower and may require API keys for some services.

### 6. Test Run Before Downloading

Preview what would be downloaded:

```bash
tumblr-archiver myblog --dry-run --verbose
```

This shows:
- Number of posts found
- Number of media items
- Estimated download size
- No actual downloads performed

### 7. Slow and Respectful Archive

Minimize server impact:

```bash
tumblr-archiver myblog \
  --rate 0.5 \
  --concurrency 1 \
  --max-retries 5
```

### 8. Re-download Failed Items

To retry only failed downloads:

```bash
# First, check what failed
cat downloads/myblog/manifest.json | grep "failed"

# Then resume (it will retry failed items)
tumblr-archiver myblog --output ./downloads
```

### 9. Multiple Blogs

Archive multiple blogs sequentially:

```bash
#!/bin/bash
for blog in blog1 blog2 blog3; do
  echo "Archiving $blog..."
  tumblr-archiver "$blog" --output ./archives
  sleep 60  # Wait between blogs
done
```

### 10. Scheduled Archiving

Use cron for regular archiving:

```bash
# Add to crontab (crontab -e)
# Archive daily at 2 AM
0 2 * * * /path/to/venv/bin/tumblr-archiver myblog --output /archives
```

## Examples

### Example 1: Basic Archive

```bash
tumblr-archiver photography-blog
```

**Output**:
```
Starting archive of 'photography-blog'...
Found 250 posts
Found 847 media items
Downloading... [████████████████] 847/847 100%
Download complete!

Archive Statistics for 'photography-blog'
============================================================
Posts found:       250
Media items:       847
Downloaded:        847
Failed:            0
Skipped:           0
Bytes downloaded:  2,458,932,441 (2.29 GB)
Duration:          423.18 seconds
============================================================
```

### Example 2: Custom Configuration

```bash
tumblr-archiver art-blog \
  --output ~/tumblr-archives \
  --rate 2.0 \
  --concurrency 3 \
  --exclude-reblogs \
  --verbose
```

### Example 3: Dry Run

```bash
$ tumblr-archiver test-blog --dry-run

Dry run mode: No files will be downloaded
Scanning test-blog.tumblr.com...
Found 50 posts (25 original, 25 reblogs)
Found 127 media items:
  - 98 images
  - 23 videos
  - 6 audio files

Estimated download size: ~450 MB
```

### Example 4: Resume After Interruption

```bash
$ tumblr-archiver myblog --output ./archives

Loading existing manifest...
Found 500 previously downloaded items
Found 123 pending items
Resuming download...
```

## Troubleshooting

### Issue: Rate Limited (429 Error)

**Symptoms**:
```
ERROR: Rate limited by Tumblr (429)
```

**Solutions**:
- Reduce rate limit: `--rate 0.5`
- Reduce concurrency: `--concurrency 1`
- Wait 5-10 minutes before retrying

### Issue: Connection Timeouts

**Symptoms**:
```
ERROR: Timeout while downloading media
```

**Solutions**:
- Increase timeout: `--timeout 60.0`
- Check your internet connection
- Reduce concurrency: `--concurrency 2`

### Issue: Blog Not Found

**Symptoms**:
```
ERROR: Blog 'myblog' not found
```

**Solutions**:
- Verify blog exists: Visit `https://myblog.tumblr.com`
- Check for typos in blog name
- Try the full URL format

### Issue: Disk Space Full

**Symptoms**:
```
ERROR: No space left on device
```

**Solutions**:
- Free up disk space
- Choose different output directory: `--output /other/drive`
- Use dry run first to estimate size: `--dry-run`

### Issue: Manifest Corruption

**Symptoms**:
```
ERROR: Failed to load manifest
```

**Solutions**:
```bash
# Backup corrupt manifest
mv downloads/myblog/manifest.json downloads/myblog/manifest.json.backup

# Start fresh (files won't be re-downloaded if checksums match)
tumblr-archiver myblog --no-resume
```

### Issue: Slow Downloads

**Possible causes**:
- Rate limit too low
- Concurrency too low
- Network congestion
- Distant server location

**Solutions**:
```bash
# Increase speed (carefully)
tumblr-archiver myblog --rate 2.0 --concurrency 4

# Monitor for errors
tumblr-archiver myblog --rate 2.0 --concurrency 4 --verbose
```

### Issue: Missing Media

**Symptoms**:
Some expected media files aren't downloaded.

**Reasons**:
- Media deleted from Tumblr
- Internet Archive fallback failed
- Media behind authentication

**Solutions**:
```bash
# Check verbose logs
tumblr-archiver myblog --verbose

# Review manifest for failed items
cat downloads/myblog/manifest.json | grep '"status": "failed"'
```

## Best Practices

1. **Start Conservative**: Use default settings first
2. **Monitor Progress**: Use `--verbose` initially
3. **Enable Resume**: Keep `--resume` enabled
4. **Be Respectful**: Use reasonable rate limits
5. **Test First**: Use `--dry-run` for large archives
6. **Regular Backups**: Archive periodically for active blogs
7. **Check Manifests**: Review for failed downloads
8. **Stable Connection**: Use wired connection for large archives

## Next Steps

- Read [Configuration Guide](configuration.md) for detailed settings
- See [Troubleshooting Guide](troubleshooting.md) for more solutions
- Check [Architecture Guide](architecture.md) to understand internals
- Review [examples/](../examples/) for shell scripts

## Support

For issues not covered here:
- Check [troubleshooting.md](troubleshooting.md)
- Open a GitHub issue
- Review existing issues for solutions
