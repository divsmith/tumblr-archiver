# Tumblr Media Downloader

A command-line tool to download all media (images, videos, GIFs) from Tumblr blogs.

## Features

- Download all media from any public Tumblr blog
- Support for images, videos, and GIFs
- Efficient downloading with progress tracking
- Organized output with customizable directory structure
- Resume capability for interrupted downloads

## Requirements

- Python 3.8 or higher
- Active internet connection
- Tumblr API key (optional, for authenticated access)

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/tumblr-media-downloader.git
cd tumblr-media-downloader

# Install in development mode
pip install -e .
```

### From PyPI (when published)

```bash
pip install tumblr-media-downloader
```

## Usage

### Basic Usage

Download all media from a Tumblr blog:

```bash
tumblr-media-downloader <blog-name>
```

### Examples

```bash
# Download from a specific blog
tumblr-media-downloader example-blog

# Specify output directory
tumblr-media-downloader example-blog --output ./downloads

# Limit number of posts
tumblr-media-downloader example-blog --limit 100

# Download only specific media types
tumblr-media-downloader example-blog --type image
```

### Command-Line Options

```
Usage: tumblr-media-downloader [OPTIONS] BLOG_NAME

Options:
  --output, -o PATH       Output directory (default: ./tumblr_downloads/<blog-name>)
  --limit, -l INTEGER     Limit number of posts to process
  --type, -t TEXT         Media type to download (image, video, all)
  --api-key TEXT          Tumblr API key for authenticated access
  --verbose, -v           Enable verbose output
  --help                  Show this message and exit
```

## Configuration

You can optionally provide a Tumblr API key for better rate limits and access to authenticated content:

1. Register your application at https://www.tumblr.com/oauth/apps
2. Use the Consumer Key (API Key) with the `--api-key` option

## Development

### Setup Development Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install package in development mode
pip install -e .
```

### Running Tests

```bash
pytest tests/
```

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Disclaimer

This tool is for personal use only. Please respect Tumblr's Terms of Service and content creators' rights. Do not use this tool to violate copyright or download content without permission.
