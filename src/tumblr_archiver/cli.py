"""
Command-line interface for the Tumblr archiver.

This module provides the CLI argument parsing using Click framework.
"""

import sys
from pathlib import Path

import click

from . import __version__
from .config import ArchiverConfig, ConfigurationError
from .constants import (
    DEFAULT_CONCURRENCY,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RATE_LIMIT,
    DEFAULT_TIMEOUT,
)


def normalize_blog_identifier(blog_identifier: str) -> str:
    """
    Normalize a blog identifier to just the blog name.
    
    Accepts:
    - Blog name: 'myblog'
    - Full URL: 'https://myblog.tumblr.com'
    - Domain: 'myblog.tumblr.com'
    
    Args:
        blog_identifier: Blog name, URL, or domain
        
    Returns:
        Normalized blog name (without .tumblr.com)
    """
    # Remove protocol if present
    identifier = blog_identifier.replace("https://", "").replace("http://", "")
    
    # Remove trailing slashes
    identifier = identifier.rstrip("/")
    
    # Remove .tumblr.com if present
    if identifier.endswith(".tumblr.com"):
        identifier = identifier.removesuffix(".tumblr.com")
    
    return identifier


@click.command()
@click.version_option(version=__version__, prog_name="tumblr-archiver")
@click.argument("blog", required=True, metavar="BLOG")
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=Path("./downloads"),
    help="Output directory for downloaded media (default: ./downloads)",
    show_default=True,
)
@click.option(
    "--concurrency",
    "-c",
    type=click.IntRange(min=1, max=10),
    default=DEFAULT_CONCURRENCY,
    help="Number of concurrent download workers (1-10)",
    show_default=True,
)
@click.option(
    "--rate",
    "-r",
    type=click.FloatRange(min=0.1),
    default=DEFAULT_RATE_LIMIT,
    help="Maximum requests per second",
    show_default=True,
)
@click.option(
    "--resume/--no-resume",
    default=True,
    help="Resume from previous downloads (default: enabled)",
    show_default=True,
)
@click.option(
    "--include-reblogs/--exclude-reblogs",
    default=True,
    help="Include or exclude reblogged posts",
    show_default=True,
)
@click.option(
    "--download-embeds",
    is_flag=True,
    default=False,
    help="Download embedded media (YouTube, Vimeo, etc.)",
    show_default=True,
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Simulate operations without downloading",
    show_default=True,
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable verbose logging",
    show_default=True,
)
@click.option(
    "--max-retries",
    type=click.IntRange(min=0, max=10),
    default=DEFAULT_MAX_RETRIES,
    help="Maximum retry attempts for failed requests",
    show_default=True,
)
@click.option(
    "--timeout",
    type=click.FloatRange(min=1.0),
    default=DEFAULT_TIMEOUT,
    help="HTTP request timeout in seconds",
    show_default=True,
)
def cli(
    blog: str,
    output: Path,
    concurrency: int,
    rate: float,
    resume: bool,
    include_reblogs: bool,
    download_embeds: bool,
    dry_run: bool,
    verbose: bool,
    max_retries: int,
    timeout: float,
) -> ArchiverConfig:
    """
    Archive media from Tumblr blogs with Internet Archive fallback.
    
    BLOG can be specified as:
    
    \b
    - Blog name: myblog
    - Full URL: https://myblog.tumblr.com
    - Domain: myblog.tumblr.com
    
    \b
    Examples:
      tumblr-archiver myblog
      tumblr-archiver myblog --output ./my-archive --concurrency 4
      tumblr-archiver https://myblog.tumblr.com --rate 0.5 --verbose
      tumblr-archiver myblog --dry-run --download-embeds
    
    \b
    Features:
      • Downloads images, videos, and audio files
      • Automatic fallback to Internet Archive for missing media
      • Resume capability with manifest tracking
      • Configurable rate limiting and concurrency
      • Optional embedded media download (YouTube, Vimeo, etc.)
      • Dry-run mode for testing
    
    For more information, visit: https://github.com/yourusername/tumblr-archive
    """
    # Normalize blog identifier
    try:
        blog_name = normalize_blog_identifier(blog)
    except Exception as e:
        click.echo(f"Error: Invalid blog identifier '{blog}': {e}", err=True)
        sys.exit(1)
    
    # Create configuration
    try:
        config = ArchiverConfig(
            blog_name=blog_name,
            output_dir=output,
            concurrency=concurrency,
            rate_limit=rate,
            max_retries=max_retries,
            include_reblogs=include_reblogs,
            download_embeds=download_embeds,
            resume=resume,
            dry_run=dry_run,
            verbose=verbose,
            timeout=timeout,
        )
    except ConfigurationError as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)
    
    return config
