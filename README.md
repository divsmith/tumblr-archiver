# Tumblr Media Archiver

A production-ready command-line tool for archiving all media content from Tumblr blogs with automatic recovery of removed content via the Internet Archive.

## Overview

Tumblr Media Archiver is a robust CLI tool that downloads **all** images, animated GIFs, and videos from any Tumblr blog. When media files have been removed from Tumblr, the tool automatically queries the Internet Archive (Wayback Machine) to recover the highest-resolution archived versions available.

### Key Features

- **Complete Media Archive**: Downloads all images (JPG/PNG/WebP), animated GIFs, and videos from Tumblr blogs
- **Internet Archive Recovery**: Automatically recovers removed media via Wayback Machine with intelligent snapshot selection
- **Resume Support**: Intelligent resume functionality allows interrupting and continuing downloads without re-downloading
- **Manifest System**: Generates detailed `manifest.json` with complete provenance tracking (source, checksums, timestamps)
- **Polite Operation**: Configurable rate limiting, exponential backoff, jitter, and retry logic to respect service limits
- **Concurrent Downloads**: Configurable concurrent download workers for efficient bulk archiving
- **Reblog Support**: Includes reblogged posts and external embeds (optional)
- **Dry Run Mode**: Preview operations without downloading anything
- **Progress Tracking**: Real-time progress updates with detailed logging

## Installation

### Requirements

- Python 3.8 or higher
- Tumblr API key (free, read-only access)

### From Source

```bash
# Clone the repository
git clone https://github.com/parker/tumblr-archiver.git
cd tumblr-archiver

# Install with pip
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

### Dependencies

The tool automatically installs the following dependencies:

- `requests` — HTTP requests to Tumblr API
- `aiohttp` — Async HTTP for concurrent downloads
- `click` — CLI interface
- `python-dotenv` — Environment variable management
- `aiofiles` — Async file I/O
- `beautifulsoup4` — HTML parsing for Wayback recovery

## Quick Start

### 1. Get a Tumblr API Key

1. Visit [https://www.tumblr.com/oauth/apps](https://www.tumblr.com/oauth/apps)
2. Click "Register application"
3. Fill in application details:
   - **Application name**: Your choice (e.g., "Personal Media Archiver")
   - **Application website**: Can be any URL (e.g., `http://localhost`)
   - **Application description**: Brief description
   - **Default callback URL**: `http://localhost`
4. Click "Register"
5. Copy the **OAuth Consumer Key** (this tool uses it as your API key)

Note: Tumblr also shows an **OAuth Consumer Secret**. That secret is only needed for fully signed OAuth 1.0a requests (user-authenticated/private endpoints). This archiver currently uses Tumblr's public-read API key mode (adds `api_key=...` to requests) and does not require or use the secret.

### 2. Set Your API Key

Set the API key as an environment variable:

```bash
# On macOS/Linux
export TUMBLR_API_KEY=your_api_key_here

# On Windows (PowerShell)
$env:TUMBLR_API_KEY="your_api_key_here"

# Or create a .env file in your working directory
echo "TUMBLR_API_KEY=your_api_key_here" > .env
```

### 3. Archive a Blog

```bash
# Basic usage
tumblr-archiver archive --url example.tumblr.com

# Or just the blog name
tumblr-archiver archive --url example
```

The tool will:
1. Fetch all posts from the blog using the Tumblr API
2. Download all media files to `./downloads/example/`
3. Automatically recover removed media via Internet Archive
4. Generate a detailed `manifest.json` file

## Usage

### Command Reference

#### Archive Command

```bash
tumblr-archiver archive --url <blog-url> [OPTIONS]
```

**Required:**
- `--url TEXT` — Tumblr blog URL or username (e.g., `example.tumblr.com` or `example`)

**Output Options:**
- `--out, --output PATH` — Output directory for downloads (default: `./downloads`)

**Resume & Recovery:**
- `--resume / --no-resume` — Resume from previous download (default: enabled)
- `--recover-removed-media / --no-recover-removed-media` — Recover removed media via Internet Archive (default: enabled)
- `--wayback / --no-wayback` — Enable/disable Internet Archive fallback (default: enabled)
- `--wayback-max-snapshots INTEGER` — Max Wayback snapshots to check per URL (default: 5)

**Content Selection:**
- `--include-reblogs / --exclude-reblogs` — Include reblogged posts (default: include)
- `--download-embeds` — Download embedded media from external sources (optional)

**Performance & Rate Limiting:**
- `--concurrency INTEGER` — Number of concurrent download tasks (default: 2)
- `--rate FLOAT` — Maximum requests per second to Tumblr API (default: 1.0)

**Authentication:**
- `--tumblr-api-key TEXT` — Tumblr API key (or set `TUMBLR_API_KEY` env var)

OAuth 1.0a (consumer secret / access tokens) is not currently used by this tool.

**Logging & Debugging:**
- `--dry-run` — Simulate operations without downloading
- `--verbose, -v` — Enable verbose logging output
- `--log-file PATH` — Write logs to specified file

#### Config Command

```bash
tumblr-archiver config [--verbose]
```

Display current configuration and check API key status.

### Usage Examples

#### Basic Archive

```bash
# Archive all media from a blog
tumblr-archiver archive --url example-blog
```

#### Archive with Custom Options

```bash
# Archive with specific settings
tumblr-archiver archive \
  --url example-blog \
  --out ./my-archive \
  --concurrency 4 \
  --rate 2.0 \
  --verbose
```

#### Resume Interrupted Download

```bash
# Resume will happen automatically by default
tumblr-archiver archive --url example-blog --out ./my-archive
```

The tool automatically detects existing downloads and skips them.

#### Dry Run (Preview)

```bash
# See what would be downloaded without actually downloading
tumblr-archiver archive --url example-blog --dry-run --verbose
```

#### Archive Without Reblogs

```bash
# Only download original posts
tumblr-archiver archive --url example-blog --exclude-reblogs
```

#### Archive with Internet Archive Disabled

```bash
# Skip Wayback recovery (faster, but misses removed media)
tumblr-archiver archive --url example-blog --no-wayback
```

#### Check Configuration

```bash
# View current config and API key status
tumblr-archiver config

# View with detailed environment variables
tumblr-archiver config --verbose
```

### Environment Variables

The tool recognizes the following environment variables:

- `TUMBLR_API_KEY` — Tumblr API key (required)

Tumblr labels `TUMBLR_API_KEY` as the "OAuth Consumer Key" on the app registration page.

You can set these in your shell, or create a `.env` file in your working directory:

```bash
# .env file example
TUMBLR_API_KEY=your_api_key_here
```

## Features Explained

### Resume Functionality

The archiver maintains a `manifest.json` file that tracks all downloaded media and their status. When you run the tool again:

1. It loads the existing manifest
2. Checks which files have already been downloaded
3. Skips completed downloads and only processes new or failed items
4. Updates the manifest as new media is downloaded

This allows you to:
- Interrupt downloads with `Ctrl+C` and resume later
- Incrementally archive active blogs over time
- Retry failed downloads without re-downloading successful ones

### Internet Archive Recovery

When a media file is no longer available on Tumblr:

1. The tool detects the missing media (4xx errors, placeholder images)
2. Queries the Internet Archive Wayback Machine's CDX API
3. Evaluates available snapshots and selects the highest quality version
4. Downloads the archived media file
5. Records full provenance in the manifest

**Wayback Recovery Process:**
- Queries up to `--wayback-max-snapshots` historical captures
- Prefers highest-resolution versions
- Falls back to post page archives if direct media URLs aren't archived
- Records snapshot URL and timestamp in manifest

**Privacy Note:** Wayback queries are made to public APIs. Disable with `--no-wayback` if preferred.

### Manifest System

Every archive includes a `manifest.json` file that serves as:

- **Complete inventory** of all archived media
- **Provenance record** showing source (Tumblr vs. Internet Archive)
- **Resume database** for incremental downloads
- **Verification tool** with SHA256 checksums

The manifest enables:
- Verifying download integrity
- Understanding archive completeness
- Processing archived media programmatically
- Auditing recovery sources

### Rate Limiting & Politeness

The tool is designed to be respectful of service limits:

**Default Settings (Recommended):**
- 1 request/second to Tumblr API
- 2 concurrent downloads
- 3 retry attempts with exponential backoff (1s → 2s → 4s → ...)
- Maximum 32-second backoff
- Randomized jitter on retries

**Customization:**
```bash
# More aggressive (use cautiously)
tumblr-archiver archive --url example --rate 2.0 --concurrency 4

# More conservative (recommended for large archives)
tumblr-archiver archive --url example --rate 0.5 --concurrency 1
```

**Automatic Backoff:**
- Detects 429 (Too Many Requests) responses
- Respects `Retry-After` headers
- Implements exponential backoff with jitter
- Logs rate limit events to console

### Concurrent Downloads

The tool uses asynchronous I/O to download multiple files simultaneously:

- Downloads run in parallel worker tasks
- Rate limiting applies across all workers
- Failed downloads are automatically retried
- Progress is tracked per-file

**Recommendations:**
- **Small blogs (<1000 posts):** `--concurrency 2-4`
- **Large blogs (>1000 posts):** `--concurrency 2-3` (be respectful)
- **Slow connections:** `--concurrency 1-2`

## Manifest Schema

### Structure

The `manifest.json` file has the following structure:

```json
{
  "blog_url": "https://example.tumblr.com",
  "blog_name": "example",
  "archive_date": "2026-02-14T10:30:00Z",
  "total_posts": 1523,
  "total_media": 4891,
  "media": [
    {
      "post_id": "123456789",
      "post_url": "https://example.tumblr.com/post/123456789",
      "timestamp": "2023-05-15T14:30:00Z",
      "media_type": "image",
      "filename": "tumblr_abc123_1280.jpg",
      "byte_size": 245678,
      "checksum": "sha256:a1b2c3d4...",
      "original_url": "https://64.media.tumblr.com/abc123/tumblr_abc123_1280.jpg",
      "api_media_urls": [
        "https://64.media.tumblr.com/abc123/tumblr_abc123_1280.jpg",
        "https://64.media.tumblr.com/abc123/tumblr_abc123_500.jpg"
      ],
      "media_missing_on_tumblr": false,
      "retrieved_from": "tumblr",
      "archive_snapshot_url": null,
      "archive_snapshot_timestamp": null,
      "status": "downloaded",
      "notes": ""
    },
    {
      "post_id": "987654321",
      "post_url": "https://example.tumblr.com/post/987654321",
      "timestamp": "2020-08-20T09:15:00Z",
      "media_type": "video",
      "filename": "tumblr_xyz789.mp4",
      "byte_size": 8456231,
      "checksum": "sha256:e5f6g7h8...",
      "original_url": "https://va.media.tumblr.com/xyz789.mp4",
      "api_media_urls": [
        "https://va.media.tumblr.com/xyz789.mp4"
      ],
      "media_missing_on_tumblr": true,
      "retrieved_from": "internet_archive",
      "archive_snapshot_url": "https://web.archive.org/web/20201015201030/https://va.media.tumblr.com/xyz789.mp4",
      "archive_snapshot_timestamp": "2020-10-15T20:10:30Z",
      "status": "downloaded",
      "notes": "Recovered from Internet Archive"
    }
  ]
}
```

### Field Descriptions

#### Root Level

- `blog_url` — The Tumblr blog URL being archived
- `blog_name` — The blog's username
- `archive_date` — ISO 8601 timestamp when archiving started
- `total_posts` — Total number of posts processed from the blog
- `total_media` — Total number of media files in the archive
- `media` — Array of media entry objects

#### Media Entry

- `post_id` — Tumblr post ID (unique identifier)
- `post_url` — Full URL to the original post
- `timestamp` — ISO 8601 timestamp when the post was created
- `media_type` — Type of media: `image`, `gif`, or `video`
- `filename` — Filename used in the local archive
- `byte_size` — File size in bytes
- `checksum` — SHA256 hash of the file (format: `sha256:...`)
- `original_url` — Original Tumblr URL where the media was hosted
- `api_media_urls` — Array of all media URLs provided by Tumblr API (different resolutions)
- `media_missing_on_tumblr` — Boolean indicating if media was unavailable on Tumblr
- `retrieved_from` — Source of the media:
  - `tumblr` — Downloaded directly from Tumblr
  - `internet_archive` — Recovered from Wayback Machine
  - `external` — Downloaded from external embed
  - `cached` — Already existed locally
- `archive_snapshot_url` — Full Wayback Machine URL (if recovered from archive), otherwise `null`
- `archive_snapshot_timestamp` — ISO 8601 timestamp of the archive snapshot (if applicable), otherwise `null`
- `status` — Download status:
  - `downloaded` — Successfully downloaded and verified
  - `pending` — Queued for download
  - `downloading` — Currently downloading
  - `failed` — Download failed after retries
  - `missing` — Not available from any source
  - `skipped` — Skipped based on filters
- `notes` — Optional notes or error messages

## Configuration

### CLI Options Explained

#### Rate Limiting

**`--rate FLOAT`** (default: 1.0)

Maximum requests per second to the Tumblr API. This controls API request rate, not download speed.

- **Recommended:** 1.0 (default) for most use cases
- **Conservative:** 0.5 for large archives or shared IP addresses
- **Aggressive:** 2.0 (use cautiously, may trigger rate limits)

#### Concurrency

**`--concurrency INTEGER`** (default: 2)

Number of simultaneous download tasks. More workers = faster downloads but higher resource usage.

- **Recommended:** 2-3 for most use cases
- **Low bandwidth:** 1-2 to avoid congestion
- **High bandwidth:** 4-6 (monitor for rate limits)

#### Resume

**`--resume / --no-resume`** (default: enabled)

Controls whether to resume from previous downloads. When enabled:
- Checks manifest for existing downloads
- Skips files that already exist locally
- Only downloads new or failed items

Disable (`--no-resume`) to force re-download everything (rare cases).

#### Wayback Recovery

**`--recover-removed-media / --no-recover-removed-media`** (default: enabled)

Attempt to recover removed media via Internet Archive.

**`--wayback / --no-wayback`** (default: enabled)

Master switch for Internet Archive functionality.

**`--wayback-max-snapshots INTEGER`** (default: 5)

How many historical snapshots to query per missing URL. More snapshots = better chance of finding high-quality versions but slower recovery.

- **Fast:** 1-3 snapshots
- **Balanced:** 5 snapshots (default)
- **Thorough:** 10+ snapshots

### Best Practices

#### For Large Archives (>5000 posts)

```bash
tumblr-archiver archive \
  --url large-blog \
  --rate 0.5 \
  --concurrency 2 \
  --log-file archive.log \
  --verbose
```

#### For Quick Archives (Tumblr-only, no recovery)

```bash
tumblr-archiver archive \
  --url quick-blog \
  --no-wayback \
  --rate 2.0 \
  --concurrency 4
```

#### For Maximum Data Recovery

```bash
tumblr-archiver archive \
  --url complete-blog \
  --rate 0.5 \
  --concurrency 2 \
  --wayback-max-snapshots 10 \
  --download-embeds
```

## Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/parker/tumblr-archiver.git
cd tumblr-archiver

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=tumblr_archiver --cov-report=html

# Run specific test file
pytest tests/test_cli.py

# Run integration tests
pytest tests/integration/

# View coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/
```

### Project Structure

```
tumblr-archiver/
├── src/tumblr_archiver/
│   ├── __init__.py          # Package initialization
│   ├── cli.py               # Command-line interface
│   ├── config.py            # Configuration management
│   ├── archiver.py          # Main archiver logic
│   ├── downloader.py        # Download manager
│   ├── manifest.py          # Manifest management
│   ├── tumblr_api.py        # Tumblr API client
│   ├── wayback_client.py    # Internet Archive client
│   ├── recovery.py          # Media recovery logic
│   ├── rate_limiter.py      # Rate limiting implementation
│   └── retry.py             # Retry logic with backoff
├── tests/                   # Unit tests
├── examples/                # Usage examples
└── docs/                    # Documentation
```

### Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for your changes
4. Ensure all tests pass (`pytest`)
5. Format code (`black src/ tests/`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## Legal & Compliance

### Copyright Notice

This tool is provided for **personal archival and backup purposes only**. Users are responsible for complying with:

- Tumblr's Terms of Service
- Copyright laws in their jurisdiction
- Content creators' rights and wishes

### Responsible Use

**DO:**
- ✅ Archive your own content
- ✅ Backup blogs with creator permission
- ✅ Archive public domain or Creative Commons content
- ✅ Use for personal, non-commercial purposes
- ✅ Respect rate limits and service availability

**DO NOT:**
- ❌ Redistribute archived content without permission
- ❌ Use for commercial purposes without authorization
- ❌ Violate copyright or intellectual property rights
- ❌ Circumvent access controls or authentication
- ❌ Archive private or restricted content without permission
- ❌ Overload services with excessive requests

### Terms of Service

By using this tool, you agree to:

1. **Respect Tumblr's Terms of Service** — Do not violate platform rules
2. **Honor copyright** — Respect content creators' intellectual property
3. **Use responsibly** — Configure appropriate rate limits and be a good netizen
4. **No warranty** — This software is provided "as is" without warranties
5. **Your responsibility** — You are solely responsible for how you use this tool

### Privacy & Data Handling

- API keys are never logged or transmitted except to Tumblr/Wayback APIs
- Downloaded content is stored locally only
- No analytics or telemetry are collected
- Internet Archive queries are made to public APIs

### Internet Archive Usage

This tool uses the Internet Archive's publicly accessible Wayback Machine APIs. By using the `--wayback` feature, you acknowledge that:

- Queries are made to public Internet Archive APIs
- No authentication or personal data is sent to the Internet Archive
- Retrieved content comes from public web archives
- You will comply with the Internet Archive's Terms of Use

## License

MIT License - Copyright (c) 2026 Parker

See [LICENSE](LICENSE) file for full license text.

## Support

For issues, questions, or contributions:

- **Issues**: [GitHub Issues](https://github.com/parker/tumblr-archiver/issues)
- **Documentation**: See `docs/` directory for detailed guides
- **Examples**: See `examples/` directory for usage examples

## Acknowledgments

- Tumblr for providing the API
- Internet Archive for the Wayback Machine
- All contributors and users of this tool

---

**Version**: 0.1.0 | **Requires**: Python 3.8+ | **License**: MIT