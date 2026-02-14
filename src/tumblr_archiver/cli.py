"""
Command-line interface for Tumblr Media Archiver.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

import click

from tumblr_archiver import __version__
from tumblr_archiver.archiver import TumblrArchiver, ArchiverError
from tumblr_archiver.config import ArchiverConfig, ConfigurationError, ConfigLoader


@click.group()
@click.version_option(version=__version__, prog_name="tumblr-archiver")
@click.pass_context
def main(ctx):
    """
    Tumblr Media Archiver - Download and archive media from Tumblr blogs.
    
    A CLI tool to archive photos, videos, animated GIFs, and other media content
    from Tumblr blogs with automatic recovery of removed media via Internet Archive.
    """
    ctx.ensure_object(dict)


@main.command()
@click.option('--url', required=True,
              help='Tumblr blog URL or username (e.g., example.tumblr.com or example)')
@click.option('--out', '--output', default='./downloads',
              type=click.Path(),
              help='Output directory for downloaded media')
@click.option('--resume/--no-resume', default=True,
              help='Resume from previous download progress')
@click.option('--concurrency', type=int, default=2,
              help='Number of concurrent download tasks')
@click.option('--rate', type=float, default=1.0,
              help='Maximum requests per second to Tumblr API')
@click.option('--include-reblogs/--exclude-reblogs', default=True,
              help='Include or exclude reblogged posts')
@click.option('--download-embeds', is_flag=True, default=False,
              help='Download embedded media from external sources')
@click.option('--recover-removed-media/--no-recover-removed-media', default=True,
              help='Attempt recovery of removed media via Internet Archive')
@click.option('--wayback/--no-wayback', default=True,
              help='Enable or disable Internet Archive fallback')
@click.option('--wayback-max-snapshots', type=int, default=5,
              help='Maximum number of Wayback snapshots to check per URL')
@click.option('--tumblr-api-key',
              envvar='TUMBLR_API_KEY',
              help='Tumblr API key (or set TUMBLR_API_KEY environment variable)')
@click.option('--oauth-consumer-key',
              envvar='TUMBLR_OAUTH_CONSUMER_KEY',
              help='Reserved for future OAuth support (currently unused)')
@click.option('--oauth-token',
              envvar='TUMBLR_OAUTH_TOKEN',
              help='Reserved for future OAuth support (currently unused)')
@click.option('--dry-run', is_flag=True, default=False,
              help='Simulate operations without actually downloading')
@click.option('--verbose', '-v', is_flag=True, default=False,
              help='Enable verbose logging output')
@click.option('--log-file',
              type=click.Path(),
              help='Path to log file for persistent logging')
def archive(url, out, resume, concurrency, rate, include_reblogs, download_embeds,
            recover_removed_media, wayback, wayback_max_snapshots, tumblr_api_key,
            oauth_consumer_key, oauth_token, dry_run, verbose, log_file):
    """
    Archive media from a Tumblr blog.
    
    Downloads all images, animated GIFs, and videos from the specified blog.
    Automatically attempts recovery of removed media via Internet Archive.
    """
    
    # Configure logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
        ] + ([logging.FileHandler(log_file)] if log_file else [])
    )
    
    # Suppress verbose logging from external libraries unless in verbose mode
    if not verbose:
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('asyncio').setLevel(logging.WARNING)
    
    try:
        # Validate API key
        if not tumblr_api_key:
            click.echo("❌ Error: Tumblr API key is required", err=True)
            click.echo("\nYou can provide it via:", err=True)
            click.echo("  1. --tumblr-api-key flag", err=True)
            click.echo("  2. TUMBLR_API_KEY environment variable", err=True)
            click.echo("\nTo obtain an API key:", err=True)
            click.echo("  Visit: https://www.tumblr.com/oauth/apps", err=True)
            sys.exit(1)
        
        # Create configuration
        config = ArchiverConfig(
            blog_url=url,
            output_dir=Path(out),
            tumblr_api_key=tumblr_api_key,
            oauth_consumer_key=oauth_consumer_key,
            oauth_token=oauth_token,
            resume=resume,
            include_reblogs=include_reblogs,
            download_embeds=download_embeds,
            recover_removed_media=recover_removed_media,
            wayback_enabled=wayback,
            wayback_max_snapshots=wayback_max_snapshots,
            rate_limit=rate,
            concurrency=concurrency,
            verbose=verbose,
            dry_run=dry_run,
            log_file=Path(log_file) if log_file else None
        )
        
        # Show configuration summary
        click.echo(f"\n{'='*60}")
        click.echo("Tumblr Media Archiver")
        click.echo(f"{'='*60}")
        click.echo(f"Blog: {url}")
        click.echo(f"Output: {out}")
        click.echo(f"Mode: {'DRY RUN' if dry_run else 'DOWNLOAD'}")
        click.echo(f"Resume: {'Yes' if resume else 'No'}")
        click.echo(f"Concurrency: {concurrency}")
        click.echo(f"Rate Limit: {rate} req/s")
        click.echo(f"Include Reblogs: {'Yes' if include_reblogs else 'No'}")
        click.echo(f"Download Embeds: {'Yes' if download_embeds else 'No'}")
        click.echo(f"Recover Removed Media: {'Yes' if recover_removed_media else 'No'}")
        click.echo(f"Wayback Enabled: {'Yes' if wayback else 'No'}")
        if wayback:
            click.echo(f"Wayback Max Snapshots: {wayback_max_snapshots}")
        click.echo(f"{'='*60}\n")
        
        # Create progress callback
        def progress_callback(progress_data):
            """Handle progress updates from the archiver."""
            event = progress_data.get('event')
            
            if event == 'start':
                click.echo(f"🚀 Starting archive of blog: {progress_data.get('blog')}")
            
            elif event == 'fetch_blog_info':
                click.echo("📡 Fetching blog information...")
            
            elif event == 'fetch_posts':
                current = progress_data.get('current', 0)
                total = progress_data.get('total', 0)
                if total > 0:
                    percentage = current * 100 // total
                    click.echo(f"📝 Fetching posts: {current}/{total} ({percentage}%)")
            
            elif event == 'process_post':
                post_index = progress_data.get('post_index', 0)
                total_posts = progress_data.get('total_posts', 0)
                post_id = progress_data.get('post_id', '')
                media_count = progress_data.get('media_count', 0)
                click.echo(f"🖼️  Processing post {post_index}/{total_posts} "
                          f"(ID: {post_id}, {media_count} media)")
            
            elif event == 'download':
                filename = progress_data.get('filename', '')
                click.echo(f"   ⬇️  Downloading: {filename}")
            
            elif event == 'wayback_recovery':
                url = progress_data.get('url', '')
                click.echo(f"   🔍 Attempting Wayback recovery: {url}")
            
            elif event == 'complete':
                click.echo("✅ Archive completed!")
        
        # Initialize archiver
        archiver = TumblrArchiver(config)
        archiver.set_progress_callback(progress_callback)
        
        # Run the archiver
        result = asyncio.run(archiver.archive_blog())
        
        # Display results
        click.echo(str(result))
        
        # Exit with appropriate code
        sys.exit(0 if result.success else 1)
        
    except ConfigurationError as e:
        click.echo(f"❌ Configuration Error: {e}", err=True)
        sys.exit(1)
    
    except ArchiverError as e:
        click.echo(f"❌ Archiver Error: {e}", err=True)
        sys.exit(1)
    
    except KeyboardInterrupt:
        click.echo("\n\n⚠️  Archive interrupted by user", err=True)
        sys.exit(130)
    
    except Exception as e:
        click.echo(f"❌ Unexpected Error: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@main.command()
@click.option('--verbose', '-v', is_flag=True, default=False,
              help='Show detailed configuration information')
def config(verbose):
    """
    Show current configuration.
    
    Displays configuration from environment variables and default values.
    Does not show actual API keys for security reasons.
    """
    click.echo(f"\n{'='*60}")
    click.echo("Tumblr Archiver Configuration")
    click.echo(f"{'='*60}\n")
    
    # Load environment variables
    env_config = ConfigLoader.load_from_env(load_dotenv_file=True)
    
    # API Key Status
    click.echo("API Credentials:")
    tumblr_api_key = os.getenv('TUMBLR_API_KEY')
    oauth_consumer_key = os.getenv('TUMBLR_OAUTH_CONSUMER_KEY')
    oauth_token = os.getenv('TUMBLR_OAUTH_TOKEN')
    
    if tumblr_api_key:
        click.echo(f"  Tumblr API Key: ✅ Present (masked: {tumblr_api_key[:8]}...)")
        click.echo(f"    Source: TUMBLR_API_KEY environment variable")
    else:
        click.echo("  Tumblr API Key: ❌ Not set")
        click.echo("    Set via: TUMBLR_API_KEY env var or --tumblr-api-key flag")
    
    if oauth_consumer_key:
        click.echo(f"  OAuth Consumer Key: ✅ Present (masked: {oauth_consumer_key[:8]}...)")
    else:
        click.echo("  OAuth Consumer Key: ❌ Not set (optional)")
    
    if oauth_token:
        click.echo(f"  OAuth Token: ✅ Present (masked: {oauth_token[:8]}...)")
    else:
        click.echo("  OAuth Token: ❌ Not set (optional)")
    
    click.echo("\nDefault Settings:")
    
    # Create default config to show defaults
    defaults = {
        'output_dir': './downloads',
        'resume': True,
        'include_reblogs': True,
        'download_embeds': False,
        'recover_removed_media': True,
        'wayback_enabled': True,
        'wayback_max_snapshots': 5,
        'rate_limit': 1.0,
        'concurrency': 2,
        'max_retries': 3,
        'verbose': False,
        'dry_run': False,
    }
    
    for key, default_value in defaults.items():
        env_value = env_config.get(key)
        if env_value is not None:
            click.echo(f"  {key}: {env_value} (from environment)")
        else:
            click.echo(f"  {key}: {default_value} (default)")
    
    if verbose:
        click.echo("\nEnvironment Variables Checked:")
        for env_var in sorted(ConfigLoader.ENV_VAR_MAPPING.keys()):
            value = os.getenv(env_var)
            if value:
                # Mask sensitive values
                if 'KEY' in env_var or 'TOKEN' in env_var:
                    value = f"{value[:8]}..." if len(value) > 8 else "***"
                click.echo(f"  {env_var}: {value}")
            else:
                click.echo(f"  {env_var}: (not set)")
    
    click.echo("\nUsage:")
    click.echo("  Set environment variables in your shell or .env file")
    click.echo("  Example: export TUMBLR_API_KEY=your-api-key-here")
    click.echo("\nTo obtain a Tumblr API key:")
    click.echo("  Visit: https://www.tumblr.com/oauth/apps")
    click.echo(f"\n{'='*60}\n")


if __name__ == '__main__':
    main()

