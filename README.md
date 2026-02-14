# Tumblr Archiver

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A powerful command-line tool for archiving media content from Tumblr blogs with automatic Internet Archive fallback support.

## ✨ Features

- 🚀 **Async/await architecture** for efficient parallel downloads
- 🔄 **Resume capability** - automatically continue interrupted downloads
- ⏱️ **Smart rate limiting** to respect server resources
- 📦 **Internet Archive fallback** for unavailable content
- 🎯 **Web scraping approach** - no API keys required
- 📊 **Real-time progress tracking** with detailed logging
- 🎨 **Embedded media support** - download from YouTube, Vimeo, and more
- 🔍 **Manifest-based tracking** - never lose your progress
- 🛡️ **Robust error handling** - automatic retries with exponential backoff
- 🧪 **Dry run mode** - test before downloading

## 📋 Requirements

- Python 3.10 or higher
- Internet connection
- Sufficient disk space for downloads

## 🚀 Quick Start

### Installation

#### From Source

```bash
# Clone the repository
git clone https://github.com/parker/tumblr-archiver.git
cd tumblr-archiver

# Install using pip
pip install -e .

# Or with development dependencies
pip install -e ".[dev]"
```

#### Using Docker

```bash
docker build -t tumblr-archiver .
docker run --rm -v $(pwd)/downloads:/downloads tumblr-archiver myblog
```

### Basic Usage

```bash
# Archive a blog with default settings
tumblr-archiver myblog

# Specify output directory
tumblr-archiver myblog --output ~/tumblr-archives

# Test before downloading
tumblr-archiver myblog --dry-run

# Faster downloads (use carefully)
tumblr-archiver myblog --concurrency 4 --rate 2.0

# Original content only (no reblogs)
tumblr-archiver myblog --exclude-reblogs

# Enable verbose logging
tumblr-archiver myblog --verbose
```

## 🎯 Common Use Cases

### Archive Your Blog
```bash
tumblr-archiver your-blog --output ~/backups
```

### Archive Multiple Blogs
```bash
for blog in blog1 blog2 blog3; do
  tumblr-archiver "$blog" --output ./archives
  sleep 60  # Be respectful between blogs
done
```

### Resume Interrupted Download
```bash
# Simply run the same command again
tumblr-archiver myblog
# Automatically picks up where it left off
```

### Fast Archive (Good Connection)
```bash
tumblr-archiver myblog --concurrency 5 --rate 2.0
```

### Conservative Archive (Respectful)
```bash
tumblr-archiver myblog --concurrency 1 --rate 0.5
```

## 📚 Documentation

- **[Usage Guide](docs/usage.md)** - Comprehensive usage instructions and workflows
- **[Configuration Reference](docs/configuration.md)** - Detailed configuration options
- **[Architecture Overview](docs/architecture.md)** - System design and components
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues and solutions
- **[Contributing Guide](CONTRIBUTING.md)** - How to contribute to the project

### Example Scripts

- **[Basic Usage Examples](examples/basic_usage.sh)** - Shell script with common use cases
- **[Advanced Configuration](examples/advanced_config.sh)** - Performance tuning and batch processing

## 🎛️ Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `--output`, `-o` | Output directory for downloads | `./downloads` |
| `--concurrency`, `-c` | Number of concurrent workers (1-10) | `2` |
| `--rate`, `-r` | Maximum requests per second | `1.0` |
| `--resume` / `--no-resume` | Enable/disable resume capability | Enabled |
| `--include-reblogs` / `--exclude-reblogs` | Include/exclude reblogs | Include |
| `--download-embeds` | Download embedded media | Disabled |
| `--dry-run` | Simulate without downloading | Disabled |
| `--verbose`, `-v` | Enable detailed logging | Disabled |
| `--max-retries` | Maximum retry attempts (0-10) | `3` |
| `--timeout` | HTTP request timeout (seconds) | `30.0` |

Run `tumblr-archiver --help` for full options.

## 🔧 Development

### Setup Development Environment

```bash
# Clone and install with dev dependencies
git clone https://github.com/parker/tumblr-archiver.git
cd tumblr-archiver
pip install -e ".[dev]"
```

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=tumblr_archiver --cov-report=html

# Run specific test file
pytest tests/test_scraper.py
```

### Code Quality

```bash
# Format code
black src/ tests/

# Type checking
mypy src/

# Linting
ruff check src/ tests/

# Fix auto-fixable issues
ruff check --fix src/ tests/
```

## Legal & Terms of Service

**⚠️ Important Notice:**

This tool is provided for personal archival purposes only. Users must:

- Respect Tumblr's Terms of Service and robots.txt
- Comply with all applicable copyright laws
- Only archive content you have rights to download
- Use reasonable rate limiting to avoid server strain
- Not use this tool for commercial purposes without proper authorization

The authors are not responsible for misuse of this tool. By using this software, you agree to use it responsibly and in compliance with all applicable laws and terms of service.

## 📊 Project Status

✅ **Complete and Production-Ready**

- [x] Project structure and setup
- [x] Configuration management
- [x] Core scraping engine
- [x] Media download logic with deduplication
- [x] Internet Archive integration
- [x] Full-featured CLI interface
- [x] Comprehensive testing suite
- [x] Manifest-based progress tracking
- [x] Resume capability
- [x] Rate limiting and retry logic
- [x] Embedded media support
- [x] Dry run mode
- [x] Complete documentation
- [x] Example scripts and workflows

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details on:

- Setting up your development environment
- Code style guidelines
- Running tests
- Submitting pull requests

## 🐛 Troubleshooting

Having issues? Check out our [Troubleshooting Guide](docs/troubleshooting.md) for solutions to common problems:

- Connection timeouts
- Rate limiting
- Manifest corruption
- Performance issues
- And more...

## 📖 Examples

### Archive with Custom Settings
```bash
tumblr-archiver photography-blog \
  --output ~/archives \
  --concurrency 3 \
  --rate 1.5 \
  --exclude-reblogs \
  --verbose
```

### Scheduled Backup (Cron)
```bash
# Add to crontab: crontab -e
0 2 * * * /usr/local/bin/tumblr-archiver myblog --output /backups >/dev/null 2>&1
```

### Batch Processing
```bash
#!/bin/bash
for blog in art-blog photo-blog travel-blog; do
  tumblr-archiver "$blog" --output ./archives
  sleep 120  # Wait 2 minutes between blogs
done
```

See [examples/](examples/) directory for more scripts and workflows.

## 🙏 Acknowledgments

- Built with [aiohttp](https://docs.aiohttp.org/) for async HTTP
- Uses [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) for HTML parsing
- CLI powered by [Click](https://click.palletsprojects.com/)
- Validation with [Pydantic](https://docs.pydantic.dev/)

## 📄 License

MIT License - See [LICENSE](LICENSE) file for details.

---

**Made with ❤️ for digital preservation and archival purposes**
