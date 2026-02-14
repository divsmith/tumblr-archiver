"""
Example usage of the Tumblr Archiver configuration system.

This script demonstrates different ways to load and use configurations.
"""

from pathlib import Path
from tumblr_archiver.config import (
    load_config,
    ArchiverConfig,
    save_config,
    parse_blog_url,
    get_default_output_dir,
    ConfigurationError,
)


def example_1_minimal_config():
    """Example 1: Create a minimal configuration."""
    print("=" * 60)
    print("Example 1: Minimal Configuration")
    print("=" * 60)
    
    config = ArchiverConfig(
        blog_url="example",
        output_dir=Path("./downloads"),
        tumblr_api_key="demo_key_12345"
    )
    
    print(f"Blog: {config.blog_url}")
    print(f"Output: {config.output_dir}")
    print(f"Rate Limit: {config.rate_limit} req/s")
    print(f"Concurrency: {config.concurrency}")
    print()


def example_2_full_config():
    """Example 2: Create a full configuration with custom settings."""
    print("=" * 60)
    print("Example 2: Full Custom Configuration")
    print("=" * 60)
    
    config = ArchiverConfig(
        blog_url="my-awesome-blog",
        output_dir=Path("./archives/my-blog"),
        tumblr_api_key="demo_key_12345",
        resume=True,
        include_reblogs=False,
        download_embeds=True,
        recover_removed_media=True,
        wayback_enabled=True,
        wayback_max_snapshots=10,
        rate_limit=2.0,
        concurrency=5,
        max_retries=5,
        verbose=True,
        dry_run=False,
    )
    
    print(f"Blog: {config.blog_url}")
    print(f"Resume: {config.resume}")
    print(f"Include Reblogs: {config.include_reblogs}")
    print(f"Download Embeds: {config.download_embeds}")
    print(f"Wayback Enabled: {config.wayback_enabled}")
    print(f"Rate Limit: {config.rate_limit} req/s")
    print(f"Concurrency: {config.concurrency} workers")
    print(f"Verbose: {config.verbose}")
    print()


def example_3_load_from_cli_args():
    """Example 3: Load configuration from CLI arguments."""
    print("=" * 60)
    print("Example 3: Load from CLI Arguments")
    print("=" * 60)
    
    # Simulate CLI arguments
    cli_args = {
        'blog_url': 'https://example.tumblr.com',
        'tumblr_api_key': 'cli_key_67890',
        'output_dir': './my-archive',
        'rate_limit': 3.0,
        'verbose': True,
    }
    
    config = load_config(cli_args=cli_args, load_env=False)
    
    print(f"Blog: {config.blog_url}")  # Automatically parsed to 'example'
    print(f"Output: {config.output_dir}")
    print(f"Rate Limit: {config.rate_limit} req/s")
    print(f"Verbose: {config.verbose}")
    print()


def example_4_parse_blog_urls():
    """Example 4: Parse various blog URL formats."""
    print("=" * 60)
    print("Example 4: Blog URL Parsing")
    print("=" * 60)
    
    urls = [
        "example",
        "my-blog.tumblr.com",
        "https://cool-blog.tumblr.com",
        "https://www.tumblr.com/awesome-blog",
        "  spaced-url.tumblr.com  ",
    ]
    
    for url in urls:
        parsed = parse_blog_url(url)
        print(f"{url:40} → {parsed}")
    print()


def example_5_default_output_dir():
    """Example 5: Generate default output directories."""
    print("=" * 60)
    print("Example 5: Default Output Directories")
    print("=" * 60)
    
    blogs = ["example", "my-awesome-blog", "test@blog"]
    
    for blog in blogs:
        output_dir = get_default_output_dir(blog)
        print(f"{blog:20} → {output_dir}")
    print()


def example_6_save_and_load_config():
    """Example 6: Save and load configuration from file."""
    print("=" * 60)
    print("Example 6: Save and Load Configuration")
    print("=" * 60)
    
    # Create a configuration
    config = ArchiverConfig(
        blog_url="example",
        output_dir=Path("./downloads"),
        tumblr_api_key="demo_key_12345",
        rate_limit=2.5,
        concurrency=3,
        verbose=True,
    )
    
    # Save to file
    config_path = Path("./example_config.json")
    save_config(config, config_path)
    print(f"✓ Configuration saved to: {config_path}")
    
    # Load from file
    loaded_config = load_config(
        config_file=config_path,
        load_env=False
    )
    
    print(f"✓ Configuration loaded from: {config_path}")
    print(f"  Blog: {loaded_config.blog_url}")
    print(f"  Rate Limit: {loaded_config.rate_limit} req/s")
    print(f"  Concurrency: {loaded_config.concurrency}")
    
    # Clean up
    config_path.unlink()
    print(f"✓ Cleaned up example file")
    print()


def example_7_config_precedence():
    """Example 7: Demonstrate configuration precedence."""
    print("=" * 60)
    print("Example 7: Configuration Precedence")
    print("=" * 60)
    
    # Simulate different sources
    import os
    from unittest.mock import patch
    
    env_vars = {
        'TUMBLR_BLOG_URL': 'env-blog',
        'TUMBLR_API_KEY': 'env-key',
        'TUMBLR_RATE_LIMIT': '1.0',
        'TUMBLR_VERBOSE': 'false'
    }
    
    cli_args = {
        'blog_url': 'cli-blog',
        'rate_limit': 5.0,
        'verbose': True
    }
    
    # Load with precedence: CLI > ENV
    with patch.dict(os.environ, env_vars, clear=True):
        config = load_config(cli_args=cli_args, load_env=True)
    
    print("Environment variables:")
    print(f"  TUMBLR_BLOG_URL=env-blog")
    print(f"  TUMBLR_RATE_LIMIT=1.0")
    print(f"  TUMBLR_VERBOSE=false")
    print()
    print("CLI arguments:")
    print(f"  blog_url=cli-blog")
    print(f"  rate_limit=5.0")
    print(f"  verbose=True")
    print()
    print("Result (CLI overrides ENV):")
    print(f"  blog_url: {config.blog_url} (from CLI)")
    print(f"  tumblr_api_key: {config.tumblr_api_key} (from ENV)")
    print(f"  rate_limit: {config.rate_limit} (from CLI)")
    print(f"  verbose: {config.verbose} (from CLI)")
    print()


def example_8_error_handling():
    """Example 8: Error handling and validation."""
    print("=" * 60)
    print("Example 8: Error Handling")
    print("=" * 60)
    
    # Example 1: Missing API key
    try:
        config = ArchiverConfig(
            blog_url="example",
            output_dir=Path("./downloads")
        )
        from tumblr_archiver.config import ConfigLoader
        ConfigLoader.validate(config)
    except ConfigurationError as e:
        print("❌ Missing API key error:")
        print(f"   {e}")
        print()
    
    # Example 2: Invalid rate limit
    try:
        config = ArchiverConfig(
            blog_url="example",
            output_dir=Path("./downloads"),
            tumblr_api_key="key",
            rate_limit=-1.0  # Invalid!
        )
        from tumblr_archiver.config import ConfigLoader
        ConfigLoader.validate(config)
    except ConfigurationError as e:
        print("❌ Invalid rate limit error:")
        print(f"   {e}")
        print()
    
    # Example 3: Invalid blog URL
    try:
        parse_blog_url("https://example.com")
    except ConfigurationError as e:
        print("❌ Invalid blog URL error:")
        print(f"   {e}")
        print()


def main():
    """Run all examples."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "Tumblr Archiver Configuration Examples" + " " * 8 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    examples = [
        example_1_minimal_config,
        example_2_full_config,
        example_3_load_from_cli_args,
        example_4_parse_blog_urls,
        example_5_default_output_dir,
        example_6_save_and_load_config,
        example_7_config_precedence,
        example_8_error_handling,
    ]
    
    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"❌ Error in {example.__name__}: {e}\n")
    
    print("=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
