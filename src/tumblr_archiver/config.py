"""
Configuration management for Tumblr Archiver.

This module handles loading, validation, and merging of configuration from
multiple sources (CLI args, environment variables, config files).
"""

import os
import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv


class ConfigurationError(Exception):
    """Raised when configuration validation fails or is invalid."""
    pass


@dataclass
class ArchiverConfig:
    """
    Configuration settings for the Tumblr archiver.
    
    Attributes:
        blog_url: The Tumblr blog URL or username to archive
        output_dir: Directory where archived content will be saved
        tumblr_api_key: Tumblr API key for authentication
        oauth_consumer_key: OAuth consumer key for authentication
        oauth_token: OAuth token for authentication
        resume: Whether to resume from previous download progress
        include_reblogs: Whether to include reblogged posts
        download_embeds: Whether to download embedded media from external sources
        recover_removed_media: Whether to attempt recovery of removed media via Wayback Machine
        wayback_enabled: Whether to use Wayback Machine for media recovery
        wayback_max_snapshots: Maximum number of Wayback Machine snapshots to check
        rate_limit: Maximum requests per second to Tumblr API
        concurrency: Number of concurrent download tasks
        max_retries: Maximum number of retry attempts for failed requests
        base_backoff: Initial backoff time in seconds for exponential backoff
        max_backoff: Maximum backoff time in seconds
        verbose: Enable verbose logging output
        dry_run: Simulate operations without actually downloading
        log_file: Path to log file for persistent logging
    """
    
    # Input/Output
    blog_url: str
    output_dir: Path
    
    # API Credentials
    tumblr_api_key: Optional[str] = None
    oauth_consumer_key: Optional[str] = None
    oauth_token: Optional[str] = None
    
    # Behavior
    resume: bool = True
    include_reblogs: bool = True
    download_embeds: bool = False
    recover_removed_media: bool = True
    
    # Wayback/Archive
    wayback_enabled: bool = True
    wayback_max_snapshots: int = 5
    
    # Rate Limiting
    rate_limit: float = 1.0  # requests per second
    concurrency: int = 2
    max_retries: int = 3
    base_backoff: float = 1.0
    max_backoff: float = 32.0
    
    # Logging
    verbose: bool = False
    dry_run: bool = False
    log_file: Optional[Path] = None
    
    def __post_init__(self):
        """Convert string paths to Path objects."""
        if isinstance(self.output_dir, str):
            self.output_dir = Path(self.output_dir)
        if self.log_file and isinstance(self.log_file, str):
            self.log_file = Path(self.log_file)


class ConfigLoader:
    """
    Utility class for loading and merging configuration from multiple sources.
    
    Configuration precedence (highest to lowest):
    1. CLI arguments
    2. Environment variables
    3. Configuration file
    4. Default values
    """
    
    # Environment variable mapping
    ENV_VAR_MAPPING = {
        'TUMBLR_BLOG_URL': 'blog_url',
        'TUMBLR_OUTPUT_DIR': 'output_dir',
        'TUMBLR_API_KEY': 'tumblr_api_key',
        'TUMBLR_OAUTH_CONSUMER_KEY': 'oauth_consumer_key',
        'TUMBLR_OAUTH_TOKEN': 'oauth_token',
        'TUMBLR_RESUME': 'resume',
        'TUMBLR_INCLUDE_REBLOGS': 'include_reblogs',
        'TUMBLR_DOWNLOAD_EMBEDS': 'download_embeds',
        'TUMBLR_RECOVER_REMOVED_MEDIA': 'recover_removed_media',
        'TUMBLR_WAYBACK_ENABLED': 'wayback_enabled',
        'TUMBLR_WAYBACK_MAX_SNAPSHOTS': 'wayback_max_snapshots',
        'TUMBLR_RATE_LIMIT': 'rate_limit',
        'TUMBLR_CONCURRENCY': 'concurrency',
        'TUMBLR_MAX_RETRIES': 'max_retries',
        'TUMBLR_BASE_BACKOFF': 'base_backoff',
        'TUMBLR_MAX_BACKOFF': 'max_backoff',
        'TUMBLR_VERBOSE': 'verbose',
        'TUMBLR_DRY_RUN': 'dry_run',
        'TUMBLR_LOG_FILE': 'log_file',
    }
    
    @staticmethod
    def load_from_env(load_dotenv_file: bool = True) -> Dict[str, Any]:
        """
        Load configuration from environment variables.
        
        Args:
            load_dotenv_file: Whether to load .env file before reading environment
            
        Returns:
            Dictionary of configuration values found in environment
        """
        if load_dotenv_file:
            load_dotenv()
        
        config = {}
        
        for env_var, config_key in ConfigLoader.ENV_VAR_MAPPING.items():
            value = os.getenv(env_var)
            if value is not None:
                # Type conversion
                if config_key in ('resume', 'include_reblogs', 'download_embeds', 
                                  'recover_removed_media', 'wayback_enabled', 
                                  'verbose', 'dry_run'):
                    # Boolean conversion
                    config[config_key] = value.lower() in ('true', '1', 'yes', 'on')
                elif config_key in ('wayback_max_snapshots', 'concurrency', 'max_retries'):
                    # Integer conversion
                    try:
                        config[config_key] = int(value)
                    except ValueError:
                        raise ConfigurationError(
                            f"Invalid integer value for {env_var}: {value}"
                        )
                elif config_key in ('rate_limit', 'base_backoff', 'max_backoff'):
                    # Float conversion
                    try:
                        config[config_key] = float(value)
                    except ValueError:
                        raise ConfigurationError(
                            f"Invalid float value for {env_var}: {value}"
                        )
                elif config_key in ('output_dir', 'log_file'):
                    # Path conversion
                    config[config_key] = Path(value)
                else:
                    # String value
                    config[config_key] = value
        
        return config
    
    @staticmethod
    def load_from_file(path: Path) -> Dict[str, Any]:
        """
        Load configuration from a JSON or YAML file.
        
        Args:
            path: Path to configuration file
            
        Returns:
            Dictionary of configuration values from file
            
        Raises:
            ConfigurationError: If file doesn't exist or is invalid format
        """
        path = Path(path)
        
        if not path.exists():
            raise ConfigurationError(f"Configuration file not found: {path}")
        
        try:
            with open(path, 'r') as f:
                if path.suffix == '.json':
                    config = json.load(f)
                elif path.suffix in ('.yaml', '.yml'):
                    try:
                        import yaml
                        config = yaml.safe_load(f)
                    except ImportError:
                        raise ConfigurationError(
                            "PyYAML is required for YAML config files. "
                            "Install it with: pip install pyyaml"
                        )
                else:
                    raise ConfigurationError(
                        f"Unsupported config file format: {path.suffix}. "
                        "Use .json or .yaml/.yml"
                    )
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in config file: {e}")
        except Exception as e:
            raise ConfigurationError(f"Error reading config file: {e}")
        
        # Convert paths
        if 'output_dir' in config:
            config['output_dir'] = Path(config['output_dir'])
        if 'log_file' in config and config['log_file']:
            config['log_file'] = Path(config['log_file'])
        
        return config
    
    @staticmethod
    def load_from_cli_args(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse configuration from CLI arguments.
        
        Args:
            args: Dictionary of CLI arguments (typically from argparse or click)
            
        Returns:
            Dictionary of configuration values from CLI
        """
        config = {}
        
        # Filter out None values and convert to config keys
        for key, value in args.items():
            if value is not None:
                # Convert CLI arg names (e.g., 'blog-url' -> 'blog_url')
                config_key = key.replace('-', '_')
                
                # Handle path conversion
                if config_key in ('output_dir', 'log_file'):
                    config[config_key] = Path(value)
                else:
                    config[config_key] = value
        
        return config
    
    @staticmethod
    def merge_configs(*configs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge multiple configuration dictionaries.
        
        Later configurations override earlier ones. Typically used to merge
        in order: defaults, file config, env vars, CLI args.
        
        Args:
            *configs: Variable number of configuration dictionaries to merge
            
        Returns:
            Merged configuration dictionary
        """
        merged = {}
        
        for config in configs:
            for key, value in config.items():
                # Only override if value is not None
                if value is not None:
                    merged[key] = value
        
        return merged
    
    @staticmethod
    def validate(config: ArchiverConfig) -> None:
        """
        Validate configuration values.
        
        Args:
            config: Configuration object to validate
            
        Raises:
            ConfigurationError: If any validation rule fails
        """
        errors = []
        
        # Validate blog_url
        if not config.blog_url:
            errors.append("blog_url is required")
        
        # Validate API credentials
        if not config.tumblr_api_key:
            if not (config.oauth_consumer_key and config.oauth_token):
                errors.append(
                    "Either tumblr_api_key or both oauth_consumer_key and "
                    "oauth_token must be provided. "
                    "Get your API key from: https://www.tumblr.com/oauth/apps"
                )
        
        # Validate numeric ranges
        if config.rate_limit <= 0:
            errors.append(f"rate_limit must be > 0, got: {config.rate_limit}")
        
        if config.concurrency < 1:
            errors.append(f"concurrency must be >= 1, got: {config.concurrency}")
        
        if config.wayback_max_snapshots < 1:
            errors.append(
                f"wayback_max_snapshots must be >= 1, got: {config.wayback_max_snapshots}"
            )
        
        if config.max_retries < 0:
            errors.append(f"max_retries must be >= 0, got: {config.max_retries}")
        
        if config.base_backoff < 0:
            errors.append(f"base_backoff must be >= 0, got: {config.base_backoff}")
        
        if config.max_backoff < config.base_backoff:
            errors.append(
                f"max_backoff ({config.max_backoff}) must be >= "
                f"base_backoff ({config.base_backoff})"
            )
        
        # Validate output directory
        try:
            # Check if parent directory exists or can be created
            if not config.output_dir.parent.exists():
                errors.append(
                    f"Parent directory does not exist: {config.output_dir.parent}"
                )
        except Exception as e:
            errors.append(f"Invalid output_dir path: {e}")
        
        # If there are errors, raise with all messages
        if errors:
            error_msg = "Configuration validation failed:\n  - " + "\n  - ".join(errors)
            raise ConfigurationError(error_msg)


def parse_blog_url(url: str) -> str:
    """
    Extract blog identifier from various URL formats.
    
    Handles:
    - "username.tumblr.com"
    - "https://username.tumblr.com"
    - "http://username.tumblr.com/"
    - "username"
    - "https://www.tumblr.com/username"
    
    Args:
        url: Blog URL or username
        
    Returns:
        Clean blog identifier (username)
        
    Raises:
        ConfigurationError: If URL format is invalid
    """
    if not url:
        raise ConfigurationError("Blog URL cannot be empty")
    
    # Remove whitespace
    url = url.strip()
    
    # Pattern 1: https://username.tumblr.com or http://username.tumblr.com
    match = re.match(r'^https?://([a-zA-Z0-9-]+)\.tumblr\.com/?$', url)
    if match:
        return match.group(1)
    
    # Pattern 2: username.tumblr.com
    match = re.match(r'^([a-zA-Z0-9-]+)\.tumblr\.com/?$', url)
    if match:
        return match.group(1)
    
    # Pattern 3: https://www.tumblr.com/username or https://tumblr.com/username
    match = re.match(r'^https?://(?:www\.)?tumblr\.com/([a-zA-Z0-9-]+)/?$', url)
    if match:
        return match.group(1)
    
    # Pattern 4: Just the username (validate it's alphanumeric with hyphens)
    if re.match(r'^[a-zA-Z0-9-]+$', url):
        return url
    
    raise ConfigurationError(
        f"Invalid blog URL format: {url}. "
        "Expected formats: 'username', 'username.tumblr.com', "
        "'https://username.tumblr.com', or 'https://www.tumblr.com/username'"
    )


def get_default_output_dir(blog_name: str) -> Path:
    """
    Generate default output directory for a blog.
    
    Creates a directory named after the blog in the current working directory.
    
    Args:
        blog_name: The blog identifier
        
    Returns:
        Path object for the default output directory
    """
    # Clean blog name for filesystem use
    clean_name = re.sub(r'[^\w\-]', '_', blog_name)
    return Path.cwd() / f"{clean_name}_archive"


def save_config(config: ArchiverConfig, path: Path) -> None:
    """
    Export configuration to a file for reuse.
    
    Args:
        config: Configuration object to save
        path: Path where config file will be saved (must be .json or .yaml/.yml)
        
    Raises:
        ConfigurationError: If file format is unsupported or write fails
    """
    path = Path(path)
    
    # Convert config to dictionary
    config_dict = asdict(config)
    
    # Convert Path objects to strings for serialization
    config_dict['output_dir'] = str(config_dict['output_dir'])
    if config_dict.get('log_file'):
        config_dict['log_file'] = str(config_dict['log_file'])
    
    try:
        # Create parent directory if it doesn't exist
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            if path.suffix == '.json':
                json.dump(config_dict, f, indent=2)
            elif path.suffix in ('.yaml', '.yml'):
                try:
                    import yaml
                    yaml.safe_dump(config_dict, f, default_flow_style=False)
                except ImportError:
                    raise ConfigurationError(
                        "PyYAML is required for YAML config files. "
                        "Install it with: pip install pyyaml"
                    )
            else:
                raise ConfigurationError(
                    f"Unsupported config file format: {path.suffix}. "
                    "Use .json or .yaml/.yml"
                )
    except Exception as e:
        raise ConfigurationError(f"Error saving config file: {e}")


def load_config(
    cli_args: Optional[Dict[str, Any]] = None,
    config_file: Optional[Path] = None,
    load_env: bool = True,
) -> ArchiverConfig:
    """
    Load and validate configuration from all sources.
    
    This is the main entry point for loading configuration. It merges
    configuration from multiple sources in the correct precedence order.
    
    Args:
        cli_args: Dictionary of CLI arguments (highest precedence)
        config_file: Path to configuration file (medium precedence)
        load_env: Whether to load from environment variables (lower precedence)
        
    Returns:
        Validated ArchiverConfig object
        
    Raises:
        ConfigurationError: If configuration is invalid
        
    Example:
        >>> config = load_config(
        ...     cli_args={'blog_url': 'example', 'output_dir': './output'},
        ...     load_env=True
        ... )
    """
    configs_to_merge = []
    
    # Load from environment (lowest precedence)
    if load_env:
        try:
            env_config = ConfigLoader.load_from_env()
            if env_config:
                configs_to_merge.append(env_config)
        except ConfigurationError:
            raise
    
    # Load from file (medium precedence)
    if config_file:
        try:
            file_config = ConfigLoader.load_from_file(config_file)
            if file_config:
                configs_to_merge.append(file_config)
        except ConfigurationError:
            raise
    
    # Load from CLI args (highest precedence)
    if cli_args:
        cli_config = ConfigLoader.load_from_cli_args(cli_args)
        if cli_config:
            configs_to_merge.append(cli_config)
    
    # Merge all configs
    if not configs_to_merge:
        raise ConfigurationError(
            "No configuration provided. Please provide blog_url and other settings "
            "via CLI arguments, config file, or environment variables."
        )
    
    merged_config = ConfigLoader.merge_configs(*configs_to_merge)
    
    # Parse and clean blog URL if provided
    if 'blog_url' in merged_config:
        merged_config['blog_url'] = parse_blog_url(merged_config['blog_url'])
    
    # Set default output directory if not provided
    if 'blog_url' in merged_config and 'output_dir' not in merged_config:
        merged_config['output_dir'] = get_default_output_dir(merged_config['blog_url'])
    
    # Create config object
    try:
        config = ArchiverConfig(**merged_config)
    except TypeError as e:
        raise ConfigurationError(f"Invalid configuration parameters: {e}")
    
    # Validate configuration
    ConfigLoader.validate(config)
    
    return config
