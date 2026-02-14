"""Configuration management for the Tumblr archiver."""

import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from .constants import (
    DEFAULT_RATE_LIMIT,
    DEFAULT_CONCURRENCY,
    DEFAULT_TIMEOUT,
    DEFAULT_MAX_RETRIES,
    DEFAULT_BASE_BACKOFF,
    DEFAULT_MAX_BACKOFF,
)


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""
    pass


@dataclass
class ArchiverConfig:
    """Configuration for the Tumblr archiver.
    
    Attributes:
        blog_name: Name of the Tumblr blog (without .tumblr.com)
        output_dir: Directory where media files will be saved
        concurrency: Number of concurrent download workers
        rate_limit: Maximum requests per second
        max_retries: Maximum number of retry attempts for failed requests
        base_backoff: Initial backoff delay in seconds for exponential backoff
        max_backoff: Maximum backoff delay in seconds
        include_reblogs: Whether to include reblogged posts
        download_embeds: Whether to download embedded media (e.g., YouTube)
        resume: Whether to resume from previous downloads
        dry_run: If True, only simulate the operation without downloading
        verbose: Enable verbose logging
        timeout: HTTP request timeout in seconds
    """
    
    blog_name: str
    output_dir: Path
    concurrency: int = DEFAULT_CONCURRENCY
    rate_limit: float = DEFAULT_RATE_LIMIT
    max_retries: int = DEFAULT_MAX_RETRIES
    base_backoff: float = DEFAULT_BASE_BACKOFF
    max_backoff: float = DEFAULT_MAX_BACKOFF
    include_reblogs: bool = True
    download_embeds: bool = False
    resume: bool = True
    dry_run: bool = False
    verbose: bool = False
    timeout: float = DEFAULT_TIMEOUT
    
    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate_blog_name()
        self._validate_numeric_fields()
        self._validate_output_dir()
    
    @property
    def blog_url(self) -> str:
        """Generate the full Tumblr blog URL from the blog name.
        
        Returns:
            The full blog URL (e.g., "https://example.tumblr.com")
        """
        return f"https://{self.blog_name}.tumblr.com"
    
    def _validate_blog_name(self) -> None:
        """Validate the blog name format."""
        if not self.blog_name:
            raise ConfigurationError("blog_name cannot be empty")
        
        # Remove .tumblr.com suffix if present
        if self.blog_name.endswith(".tumblr.com"):
            self.blog_name = self.blog_name.removesuffix(".tumblr.com")
        
        # Validate blog name format (alphanumeric and hyphens only)
        if not re.match(r"^[a-zA-Z0-9][-a-zA-Z0-9]*[a-zA-Z0-9]$|^[a-zA-Z0-9]$", self.blog_name):
            raise ConfigurationError(
                f"Invalid blog_name format: '{self.blog_name}'. "
                "Blog names must contain only letters, numbers, and hyphens, "
                "and cannot start or end with a hyphen."
            )
    
    def _validate_numeric_fields(self) -> None:
        """Validate numeric configuration fields."""
        if self.concurrency < 1:
            raise ConfigurationError(
                f"concurrency must be at least 1, got {self.concurrency}"
            )
        
        if self.rate_limit <= 0:
            raise ConfigurationError(
                f"rate_limit must be positive, got {self.rate_limit}"
            )
        
        if self.max_retries < 0:
            raise ConfigurationError(
                f"max_retries must be non-negative, got {self.max_retries}"
            )
        
        if self.base_backoff <= 0:
            raise ConfigurationError(
                f"base_backoff must be positive, got {self.base_backoff}"
            )
        
        if self.max_backoff <= 0:
            raise ConfigurationError(
                f"max_backoff must be positive, got {self.max_backoff}"
            )
        
        if self.base_backoff > self.max_backoff:
            raise ConfigurationError(
                f"base_backoff ({self.base_backoff}) cannot exceed "
                f"max_backoff ({self.max_backoff})"
            )
        
        if self.timeout <= 0:
            raise ConfigurationError(
                f"timeout must be positive, got {self.timeout}"
            )
    
    def _validate_output_dir(self) -> None:
        """Validate and normalize the output directory."""
        if not isinstance(self.output_dir, Path):
            self.output_dir = Path(self.output_dir)
        
        # Expand user home directory and resolve to absolute path
        self.output_dir = self.output_dir.expanduser().resolve()
    
    @classmethod
    def from_cli_args(
        cls,
        blog_name: str,
        output_dir: Optional[str] = None,
        concurrency: int = DEFAULT_CONCURRENCY,
        rate_limit: float = DEFAULT_RATE_LIMIT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_backoff: float = DEFAULT_BASE_BACKOFF,
        max_backoff: float = DEFAULT_MAX_BACKOFF,
        include_reblogs: bool = True,
        download_embeds: bool = False,
        resume: bool = True,
        dry_run: bool = False,
        verbose: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> "ArchiverConfig":
        """Create configuration from CLI arguments.
        
        Args:
            blog_name: Name of the Tumblr blog
            output_dir: Output directory path (defaults to ./downloads/{blog_name})
            concurrency: Number of concurrent workers
            rate_limit: Requests per second limit
            max_retries: Maximum retry attempts
            base_backoff: Initial backoff delay
            max_backoff: Maximum backoff delay
            include_reblogs: Include reblogged posts
            download_embeds: Download embedded media
            resume: Resume previous downloads
            dry_run: Simulate without downloading
            verbose: Enable verbose output
            timeout: Request timeout in seconds
            
        Returns:
            Configured ArchiverConfig instance
        """
        # Default output directory to ./downloads/{blog_name}
        if output_dir is None:
            # Clean blog name for directory
            clean_name = blog_name.replace(".tumblr.com", "")
            output_dir = f"./downloads/{clean_name}"
        
        return cls(
            blog_name=blog_name,
            output_dir=Path(output_dir),
            concurrency=concurrency,
            rate_limit=rate_limit,
            max_retries=max_retries,
            base_backoff=base_backoff,
            max_backoff=max_backoff,
            include_reblogs=include_reblogs,
            download_embeds=download_embeds,
            resume=resume,
            dry_run=dry_run,
            verbose=verbose,
            timeout=timeout,
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to a dictionary for serialization.
        
        Returns:
            Dictionary representation of the configuration
        """
        data = asdict(self)
        # Convert Path to string for JSON serialization
        data["output_dir"] = str(self.output_dir)
        # Add computed blog_url
        data["blog_url"] = self.blog_url
        return data
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArchiverConfig":
        """Create configuration from a dictionary.
        
        Args:
            data: Dictionary containing configuration values
            
        Returns:
            Configured ArchiverConfig instance
            
        Raises:
            ConfigurationError: If required fields are missing or invalid
        """
        # Remove blog_url if present (it's computed)
        data = data.copy()
        data.pop("blog_url", None)
        
        # Convert output_dir back to Path
        if "output_dir" in data:
            data["output_dir"] = Path(data["output_dir"])
        
        try:
            return cls(**data)
        except TypeError as e:
            raise ConfigurationError(f"Invalid configuration data: {e}") from e
    
    def validate(self) -> None:
        """Explicitly validate the configuration.
        
        This is called automatically by __post_init__, but can be called
        manually if configuration is modified after creation.
        
        Raises:
            ConfigurationError: If validation fails
        """
        self._validate_blog_name()
        self._validate_numeric_fields()
        self._validate_output_dir()
    
    def __repr__(self) -> str:
        """Return a detailed string representation of the configuration."""
        return (
            f"ArchiverConfig(\n"
            f"  blog_name={self.blog_name!r},\n"
            f"  blog_url={self.blog_url!r},\n"
            f"  output_dir={self.output_dir},\n"
            f"  concurrency={self.concurrency},\n"
            f"  rate_limit={self.rate_limit},\n"
            f"  max_retries={self.max_retries},\n"
            f"  base_backoff={self.base_backoff},\n"
            f"  max_backoff={self.max_backoff},\n"
            f"  include_reblogs={self.include_reblogs},\n"
            f"  download_embeds={self.download_embeds},\n"
            f"  resume={self.resume},\n"
            f"  dry_run={self.dry_run},\n"
            f"  verbose={self.verbose},\n"
            f"  timeout={self.timeout}\n"
            f")"
        )
