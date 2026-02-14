# Configuration Guide

The Tumblr Archiver uses a flexible configuration system that supports multiple sources with clear precedence rules.

## Configuration Sources

Configuration can be loaded from (in order of precedence):

1. **CLI Arguments** (highest priority)
2. **Environment Variables**
3. **Configuration File** (JSON or YAML)
4. **Default Values** (lowest priority)

## Quick Start

### Option 1: Using Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your API key:
   ```env
   TUMBLR_API_KEY=your_api_key_here
   TUMBLR_BLOG_URL=example.tumblr.com
   ```

3. Run the archiver:
   ```bash
   tumblr-archiver archive example
   ```

### Option 2: Using a Config File

1. Create a `config.json`:
   ```json
   {
     "blog_url": "example.tumblr.com",
     "tumblr_api_key": "your_api_key_here",
     "output_dir": "./my-archive",
     "verbose": true
   }
   ```

2. Run with config file:
   ```bash
   tumblr-archiver archive --config config.json
   ```

### Option 3: Using CLI Arguments Only

```bash
tumblr-archiver archive example \
  --api-key YOUR_API_KEY \
  --output ./downloads \
  --verbose
```

## Configuration Options

### Required Settings

| Option | Type | Description |
|--------|------|-------------|
| `blog_url` | string | Tumblr blog URL or username to archive |
| `tumblr_api_key` | string | Tumblr API key (or OAuth credentials) |

### Input/Output

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `output_dir` | path | `{blog}_archive` | Directory for downloaded content |

### API Credentials

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `tumblr_api_key` | string | - | Tumblr API key |
| `oauth_consumer_key` | string | - | OAuth consumer key (alternative) |
| `oauth_token` | string | - | OAuth token (alternative) |

Get your API key from: https://www.tumblr.com/oauth/apps

### Behavior Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `resume` | bool | `true` | Resume from previous download progress |
| `include_reblogs` | bool | `true` | Include reblogged posts |
| `download_embeds` | bool | `false` | Download embedded media from external sources |
| `recover_removed_media` | bool | `true` | Attempt to recover removed media via Wayback Machine |

### Wayback Machine

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `wayback_enabled` | bool | `true` | Enable Wayback Machine integration |
| `wayback_max_snapshots` | int | `5` | Max number of snapshots to check |

### Rate Limiting & Performance

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `rate_limit` | float | `1.0` | Maximum requests per second |
| `concurrency` | int | `2` | Number of concurrent downloads |
| `max_retries` | int | `3` | Maximum retry attempts for failed requests |
| `base_backoff` | float | `1.0` | Initial backoff time (seconds) |
| `max_backoff` | float | `32.0` | Maximum backoff time (seconds) |

### Logging

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `verbose` | bool | `false` | Enable verbose logging |
| `dry_run` | bool | `false` | Simulate operations without downloading |
| `log_file` | path | - | Path to log file |

## Environment Variables

All configuration options can be set via environment variables using the `TUMBLR_` prefix:

```bash
# Required
TUMBLR_API_KEY=your_api_key
TUMBLR_BLOG_URL=example

# Optional
TUMBLR_OUTPUT_DIR=./downloads
TUMBLR_RESUME=true
TUMBLR_INCLUDE_REBLOGS=true
TUMBLR_DOWNLOAD_EMBEDS=false
TUMBLR_RECOVER_REMOVED_MEDIA=true
TUMBLR_WAYBACK_ENABLED=true
TUMBLR_WAYBACK_MAX_SNAPSHOTS=5
TUMBLR_RATE_LIMIT=1.0
TUMBLR_CONCURRENCY=2
TUMBLR_MAX_RETRIES=3
TUMBLR_BASE_BACKOFF=1.0
TUMBLR_MAX_BACKOFF=32.0
TUMBLR_VERBOSE=false
TUMBLR_DRY_RUN=false
TUMBLR_LOG_FILE=./archiver.log
```

## Blog URL Formats

The archiver accepts various blog URL formats:

- `example` → Username only
- `example.tumblr.com` → Standard Tumblr subdomain
- `https://example.tumblr.com` → Full URL
- `https://www.tumblr.com/example` → Tumblr.com path format

All formats are automatically normalized to the blog identifier.

## Configuration File Formats

### JSON

```json
{
  "blog_url": "example",
  "output_dir": "./archive",
  "tumblr_api_key": "your_key",
  "rate_limit": 2.0,
  "concurrency": 4,
  "verbose": true
}
```

### YAML (requires PyYAML)

```yaml
blog_url: example
output_dir: ./archive
tumblr_api_key: your_key
rate_limit: 2.0
concurrency: 4
verbose: true
```

## Programmatic Usage

```python
from tumblr_archiver.config import load_config, ArchiverConfig
from pathlib import Path

# Load from all sources
config = load_config(
    cli_args={'blog_url': 'example', 'verbose': True},
    config_file=Path('config.json'),
    load_env=True
)

# Create config directly
config = ArchiverConfig(
    blog_url='example',
    output_dir=Path('./downloads'),
    tumblr_api_key='your_key',
    rate_limit=2.0,
    verbose=True
)

# Save config for reuse
from tumblr_archiver.config import save_config
save_config(config, Path('my-config.json'))
```

## Validation

The configuration system validates all settings:

- **Blog URL**: Must be valid format
- **API Key**: Required (unless OAuth provided)
- **Rate Limit**: Must be > 0
- **Concurrency**: Must be >= 1
- **Wayback Max Snapshots**: Must be >= 1
- **Max Retries**: Must be >= 0
- **Backoff Times**: max_backoff >= base_backoff

Validation errors provide clear messages and suggestions for fixes.

## Error Handling

### Missing API Key

```
ConfigurationError: Configuration validation failed:
  - Either tumblr_api_key or both oauth_consumer_key and oauth_token must be provided.
    Get your API key from: https://www.tumblr.com/oauth/apps
```

### Invalid Blog URL

```
ConfigurationError: Invalid blog URL format: https://example.com.
Expected formats: 'username', 'username.tumblr.com',
'https://username.tumblr.com', or 'https://www.tumblr.com/username'
```

### Invalid Rate Limit

```
ConfigurationError: Configuration validation failed:
  - rate_limit must be > 0, got: -1
```

## Best Practices

1. **Use `.env` for credentials**: Keep API keys out of version control
2. **Use config files for presets**: Create different configs for different scenarios
3. **Use CLI args for overrides**: Override specific settings without changing files
4. **Start conservative**: Begin with default rate limits and adjust based on experience
5. **Enable verbose mode**: Use `--verbose` when troubleshooting
6. **Use dry-run first**: Test with `--dry-run` before actual downloads

## Examples

### High-Speed Archive

```bash
TUMBLR_RATE_LIMIT=5.0 \
TUMBLR_CONCURRENCY=10 \
tumblr-archiver archive example --verbose
```

### Conservative Mode

```json
{
  "blog_url": "example",
  "tumblr_api_key": "your_key",
  "rate_limit": 0.5,
  "concurrency": 1,
  "max_retries": 5
}
```

### Recovery Mode (Wayback-focused)

```bash
tumblr-archiver archive example \
  --wayback-enabled \
  --wayback-max-snapshots 10 \
  --recover-removed-media
```

### Testing Mode

```bash
tumblr-archiver archive example \
  --dry-run \
  --verbose \
  --log-file test.log
```
