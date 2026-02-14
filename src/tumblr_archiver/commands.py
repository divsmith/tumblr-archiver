"""
Command implementations for the Tumblr archiver.

This module provides the main command execution logic.
"""

import logging
from typing import Optional

import click

from .config import ArchiverConfig
from .logger import setup_logging
from .orchestrator import ArchiveStats, Orchestrator

logger = logging.getLogger(__name__)


def print_banner(config: ArchiverConfig) -> None:
    """
    Print a banner with configuration information.
    
    Args:
        config: Archiver configuration
    """
    click.echo()
    click.echo("=" * 70)
    click.echo("  Tumblr Archiver")
    click.echo("=" * 70)
    click.echo(f"  Blog:           {config.blog_name} ({config.blog_url})")
    click.echo(f"  Output:         {config.output_dir}")
    click.echo(f"  Concurrency:    {config.concurrency} workers")
    click.echo(f"  Rate limit:     {config.rate_limit} req/s")
    click.echo(f"  Resume:         {'enabled' if config.resume else 'disabled'}")
    click.echo(f"  Reblogs:        {'included' if config.include_reblogs else 'excluded'}")
    click.echo(f"  Embeds:         {'enabled' if config.download_embeds else 'disabled'}")
    click.echo(f"  Max retries:    {config.max_retries}")
    click.echo(f"  Timeout:        {config.timeout}s")
    
    if config.dry_run:
        click.echo()
        click.echo("  ⚠️  DRY RUN MODE - No files will be downloaded")
    
    click.echo("=" * 70)
    click.echo()


def print_summary(stats: ArchiveStats, config: ArchiverConfig) -> None:
    """
    Print a final summary of the archive operation.
    
    Args:
        stats: Archive statistics
        config: Archiver configuration
    """
    click.echo()
    click.echo("=" * 70)
    click.echo("  Archive Summary")
    click.echo("=" * 70)
    click.echo(f"  Blog:           {stats.blog_name}")
    click.echo(f"  Posts found:    {stats.total_posts}")
    click.echo(f"  Media items:    {stats.total_media}")
    click.echo()
    click.echo(f"  Downloaded:     {stats.downloaded}")
    click.echo(f"  Skipped:        {stats.skipped}")
    click.echo(f"  Failed:         {stats.failed}")
    click.echo()
    click.echo(f"  Bytes:          {stats.bytes_downloaded:,} ({_format_bytes(stats.bytes_downloaded)})")
    click.echo(f"  Duration:       {stats.duration_seconds:.2f}s")
    
    # Calculate average speed
    if stats.duration_seconds > 0:
        avg_speed = stats.bytes_downloaded / stats.duration_seconds
        click.echo(f"  Avg speed:      {_format_bytes(int(avg_speed))}/s")
    
    click.echo("=" * 70)
    
    # Print status message
    if config.dry_run:
        click.echo()
        click.echo("✓ Dry run completed successfully!")
    elif stats.failed == 0:
        click.echo()
        click.echo("✓ Archive completed successfully!")
    else:
        click.echo()
        click.echo(f"⚠ Archive completed with {stats.failed} failed downloads")
        click.echo("  Check the logs for more details.")


def _format_bytes(bytes_count: int) -> str:
    """
    Format bytes as human-readable string.
    
    Args:
        bytes_count: Number of bytes
        
    Returns:
        Formatted string (e.g., "1.23 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.2f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.2f} PB"


async def run_archive(config: ArchiverConfig) -> int:
    """
    Run the archive operation.
    
    This is the main command implementation that:
    - Sets up logging
    - Creates and runs the orchestrator
    - Displays progress and results
    - Handles errors and interruptions
    
    Args:
        config: Archiver configuration
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Setup logging
    log_file = config.output_dir / "tumblr-archiver.log" if not config.dry_run else None
    setup_logging(verbose=config.verbose, log_file=log_file)
    
    # Print banner
    print_banner(config)
    
    # Create orchestrator
    try:
        orchestrator = Orchestrator(config)
    except Exception as e:
        logger.error(f"Failed to initialize orchestrator: {e}", exc_info=config.verbose)
        click.echo(f"Error: Failed to initialize: {e}", err=True)
        return 1
    
    # Run the archive operation
    stats: Optional[ArchiveStats] = None
    exit_code = 0
    
    try:
        click.echo("Starting archive operation...")
        click.echo()
        
        # Run orchestration
        stats = await orchestrator.run()
        
        # Print summary
        print_summary(stats, config)
        
        # Set exit code based on results
        if stats.failed > 0 and stats.downloaded == 0:
            exit_code = 1
        
    except KeyboardInterrupt:
        click.echo()
        click.echo()
        click.echo("⚠ Archive interrupted by user")
        
        # Try to get partial stats if available
        if hasattr(orchestrator, '_stats'):
            stats = orchestrator._stats
            if stats:
                print_summary(stats, config)
        
        exit_code = 130  # Standard exit code for SIGINT
        
    except Exception as e:
        logger.error(f"Archive operation failed: {e}", exc_info=config.verbose)
        click.echo()
        click.echo(f"Error: Archive operation failed: {e}", err=True)
        
        if config.verbose:
            click.echo()
            click.echo("Run with --verbose for more details or check the log file.")
        
        exit_code = 1
    
    return exit_code
