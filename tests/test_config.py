"""Tests for configuration management."""

import json
import pytest
from pathlib import Path

from tumblr_archiver.config import ArchiverConfig, ConfigurationError
from tumblr_archiver.constants import (
    DEFAULT_RATE_LIMIT,
    DEFAULT_CONCURRENCY,
    DEFAULT_TIMEOUT,
    DEFAULT_MAX_RETRIES,
    DEFAULT_BASE_BACKOFF,
    DEFAULT_MAX_BACKOFF,
)


class TestArchiverConfigCreation:
    """Tests for creating ArchiverConfig instances."""
    
    def test_config_with_minimal_args(self):
        """Test creating config with only required arguments."""
        config = ArchiverConfig(
            blog_name="example-blog",
            output_dir=Path("/tmp/downloads")
        )
        
        assert config.blog_name == "example-blog"
        assert config.output_dir == Path("/tmp/downloads").resolve()
        assert config.concurrency == DEFAULT_CONCURRENCY
        assert config.rate_limit == DEFAULT_RATE_LIMIT
        assert config.max_retries == DEFAULT_MAX_RETRIES
        assert config.timeout == DEFAULT_TIMEOUT
    
    def test_config_with_all_args(self):
        """Test creating config with all arguments specified."""
        config = ArchiverConfig(
            blog_name="test-blog",
            output_dir=Path("/tmp/output"),
            concurrency=5,
            rate_limit=2.5,
            max_retries=5,
            base_backoff=2.0,
            max_backoff=64.0,
            include_reblogs=False,
            download_embeds=True,
            resume=False,
            dry_run=True,
            verbose=True,
            timeout=60.0,
        )
        
        assert config.blog_name == "test-blog"
        assert config.output_dir == Path("/tmp/output").resolve()
        assert config.concurrency == 5
        assert config.rate_limit == 2.5
        assert config.max_retries == 5
        assert config.base_backoff == 2.0
        assert config.max_backoff == 64.0
        assert config.include_reblogs is False
        assert config.download_embeds is True
        assert config.resume is False
        assert config.dry_run is True
        assert config.verbose is True
        assert config.timeout == 60.0
    
    def test_config_strips_tumblr_suffix(self):
        """Test that .tumblr.com suffix is automatically stripped."""
        config = ArchiverConfig(
            blog_name="example-blog.tumblr.com",
            output_dir=Path("/tmp/downloads")
        )
        
        assert config.blog_name == "example-blog"
    
    def test_config_expands_user_path(self):
        """Test that ~ in paths is expanded to user home directory."""
        config = ArchiverConfig(
            blog_name="test",
            output_dir=Path("~/downloads")
        )
        
        assert "~" not in str(config.output_dir)
        assert config.output_dir.is_absolute()
    
    def test_config_converts_relative_to_absolute_path(self):
        """Test that relative paths are converted to absolute."""
        config = ArchiverConfig(
            blog_name="test",
            output_dir=Path("./downloads")
        )
        
        assert config.output_dir.is_absolute()


class TestBlogUrlGeneration:
    """Tests for blog URL generation."""
    
    def test_blog_url_generation(self):
        """Test that blog_url is correctly generated from blog_name."""
        config = ArchiverConfig(
            blog_name="example-blog",
            output_dir=Path("/tmp")
        )
        
        assert config.blog_url == "https://example-blog.tumblr.com"
    
    def test_blog_url_with_stripped_suffix(self):
        """Test blog_url generation when .tumblr.com is in input."""
        config = ArchiverConfig(
            blog_name="my-blog.tumblr.com",
            output_dir=Path("/tmp")
        )
        
        assert config.blog_url == "https://my-blog.tumblr.com"
    
    def test_blog_url_special_characters(self):
        """Test blog_url with hyphens and numbers."""
        config = ArchiverConfig(
            blog_name="test-blog-123",
            output_dir=Path("/tmp")
        )
        
        assert config.blog_url == "https://test-blog-123.tumblr.com"


class TestConfigValidation:
    """Tests for configuration validation."""
    
    def test_empty_blog_name_raises_error(self):
        """Test that empty blog_name raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="cannot be empty"):
            ArchiverConfig(blog_name="", output_dir=Path("/tmp"))
    
    def test_invalid_blog_name_format_raises_error(self):
        """Test that invalid blog name format raises error."""
        invalid_names = [
            "-starts-with-hyphen",
            "ends-with-hyphen-",
            "has spaces",
            "has@special",
            "has.dots",
        ]
        
        for name in invalid_names:
            with pytest.raises(ConfigurationError, match="Invalid blog_name format"):
                ArchiverConfig(blog_name=name, output_dir=Path("/tmp"))
    
    def test_valid_blog_name_formats(self):
        """Test that valid blog names are accepted."""
        valid_names = [
            "simple",
            "with-hyphens",
            "with123numbers",
            "a",  # single character
            "test-blog-2024",
        ]
        
        for name in valid_names:
            config = ArchiverConfig(blog_name=name, output_dir=Path("/tmp"))
            assert config.blog_name == name
    
    def test_negative_concurrency_raises_error(self):
        """Test that negative concurrency raises error."""
        with pytest.raises(ConfigurationError, match="concurrency must be at least 1"):
            ArchiverConfig(
                blog_name="test",
                output_dir=Path("/tmp"),
                concurrency=0
            )
    
    def test_negative_rate_limit_raises_error(self):
        """Test that negative rate_limit raises error."""
        with pytest.raises(ConfigurationError, match="rate_limit must be positive"):
            ArchiverConfig(
                blog_name="test",
                output_dir=Path("/tmp"),
                rate_limit=-1.0
            )
    
    def test_negative_max_retries_raises_error(self):
        """Test that negative max_retries raises error."""
        with pytest.raises(ConfigurationError, match="max_retries must be non-negative"):
            ArchiverConfig(
                blog_name="test",
                output_dir=Path("/tmp"),
                max_retries=-1
            )
    
    def test_zero_max_retries_is_valid(self):
        """Test that zero max_retries is valid (no retries)."""
        config = ArchiverConfig(
            blog_name="test",
            output_dir=Path("/tmp"),
            max_retries=0
        )
        assert config.max_retries == 0
    
    def test_negative_timeout_raises_error(self):
        """Test that negative timeout raises error."""
        with pytest.raises(ConfigurationError, match="timeout must be positive"):
            ArchiverConfig(
                blog_name="test",
                output_dir=Path("/tmp"),
                timeout=-5.0
            )
    
    def test_base_backoff_exceeds_max_backoff_raises_error(self):
        """Test that base_backoff > max_backoff raises error."""
        with pytest.raises(ConfigurationError, match="cannot exceed"):
            ArchiverConfig(
                blog_name="test",
                output_dir=Path("/tmp"),
                base_backoff=10.0,
                max_backoff=5.0
            )
    
    def test_negative_backoff_raises_error(self):
        """Test that negative backoff values raise error."""
        with pytest.raises(ConfigurationError, match="base_backoff must be positive"):
            ArchiverConfig(
                blog_name="test",
                output_dir=Path("/tmp"),
                base_backoff=-1.0
            )
        
        with pytest.raises(ConfigurationError, match="max_backoff must be positive"):
            ArchiverConfig(
                blog_name="test",
                output_dir=Path("/tmp"),
                max_backoff=-1.0
            )
    
    def test_explicit_validate_method(self):
        """Test that validate() method can be called explicitly."""
        config = ArchiverConfig(blog_name="test", output_dir=Path("/tmp"))
        # Should not raise
        config.validate()


class TestFromCliArgs:
    """Tests for from_cli_args class method."""
    
    def test_from_cli_args_with_defaults(self):
        """Test from_cli_args with minimal arguments."""
        config = ArchiverConfig.from_cli_args(blog_name="example")
        
        assert config.blog_name == "example"
        assert "downloads/example" in str(config.output_dir)
        assert config.concurrency == DEFAULT_CONCURRENCY
        assert config.rate_limit == DEFAULT_RATE_LIMIT
    
    def test_from_cli_args_with_custom_output_dir(self):
        """Test from_cli_args with custom output directory."""
        config = ArchiverConfig.from_cli_args(
            blog_name="test",
            output_dir="/custom/path"
        )
        
        assert "/custom/path" in str(config.output_dir)
    
    def test_from_cli_args_strips_tumblr_suffix_in_output(self):
        """Test that output directory uses clean blog name."""
        config = ArchiverConfig.from_cli_args(
            blog_name="myblog.tumblr.com"
        )
        
        assert "downloads/myblog" in str(config.output_dir)
        assert ".tumblr.com" not in str(config.output_dir)
    
    def test_from_cli_args_with_all_parameters(self):
        """Test from_cli_args with all parameters specified."""
        config = ArchiverConfig.from_cli_args(
            blog_name="test",
            output_dir="/tmp/test",
            concurrency=10,
            rate_limit=5.0,
            max_retries=10,
            base_backoff=0.5,
            max_backoff=16.0,
            include_reblogs=False,
            download_embeds=True,
            resume=False,
            dry_run=True,
            verbose=True,
            timeout=120.0,
        )
        
        assert config.blog_name == "test"
        assert config.concurrency == 10
        assert config.rate_limit == 5.0
        assert config.max_retries == 10
        assert config.base_backoff == 0.5
        assert config.max_backoff == 16.0
        assert config.include_reblogs is False
        assert config.download_embeds is True
        assert config.resume is False
        assert config.dry_run is True
        assert config.verbose is True
        assert config.timeout == 120.0


class TestSerialization:
    """Tests for to_dict and from_dict methods."""
    
    def test_to_dict_includes_all_fields(self):
        """Test that to_dict includes all configuration fields."""
        config = ArchiverConfig(
            blog_name="test",
            output_dir=Path("/tmp/test"),
            concurrency=5,
            verbose=True
        )
        
        data = config.to_dict()
        
        assert data["blog_name"] == "test"
        assert data["output_dir"] == str(Path("/tmp/test").resolve())
        assert data["concurrency"] == 5
        assert data["verbose"] is True
        assert "blog_url" in data
        assert data["blog_url"] == "https://test.tumblr.com"
    
    def test_to_dict_converts_path_to_string(self):
        """Test that Path objects are converted to strings."""
        config = ArchiverConfig(
            blog_name="test",
            output_dir=Path("~/downloads")
        )
        
        data = config.to_dict()
        assert isinstance(data["output_dir"], str)
    
    def test_from_dict_restores_config(self):
        """Test that from_dict correctly restores configuration."""
        original = ArchiverConfig(
            blog_name="test",
            output_dir=Path("/tmp/test"),
            concurrency=7,
            rate_limit=3.5,
            dry_run=True,
        )
        
        data = original.to_dict()
        restored = ArchiverConfig.from_dict(data)
        
        assert restored.blog_name == original.blog_name
        assert restored.output_dir == original.output_dir
        assert restored.concurrency == original.concurrency
        assert restored.rate_limit == original.rate_limit
        assert restored.dry_run == original.dry_run
    
    def test_round_trip_serialization(self):
        """Test that config survives round-trip serialization."""
        original = ArchiverConfig(
            blog_name="roundtrip-test",
            output_dir=Path("/tmp/roundtrip"),
            concurrency=3,
            rate_limit=2.0,
            max_retries=5,
            include_reblogs=False,
            verbose=True,
        )
        
        # Simulate JSON serialization
        data = original.to_dict()
        json_str = json.dumps(data)
        restored_data = json.loads(json_str)
        restored = ArchiverConfig.from_dict(restored_data)
        
        assert restored.blog_name == original.blog_name
        assert restored.concurrency == original.concurrency
        assert restored.rate_limit == original.rate_limit
        assert restored.max_retries == original.max_retries
        assert restored.include_reblogs == original.include_reblogs
        assert restored.verbose == original.verbose
    
    def test_from_dict_ignores_blog_url(self):
        """Test that from_dict ignores blog_url (computed property)."""
        data = {
            "blog_name": "test",
            "output_dir": "/tmp/test",
            "blog_url": "https://wrong.tumblr.com",  # Should be ignored
        }
        
        config = ArchiverConfig.from_dict(data)
        assert config.blog_url == "https://test.tumblr.com"
    
    def test_from_dict_with_missing_fields_raises_error(self):
        """Test that from_dict raises error for missing required fields."""
        data = {"output_dir": "/tmp/test"}  # Missing blog_name
        
        with pytest.raises(ConfigurationError, match="Invalid configuration data"):
            ArchiverConfig.from_dict(data)
    
    def test_from_dict_validates_config(self):
        """Test that from_dict validates the configuration."""
        data = {
            "blog_name": "test",
            "output_dir": "/tmp/test",
            "concurrency": -1,  # Invalid
        }
        
        with pytest.raises(ConfigurationError, match="concurrency must be at least 1"):
            ArchiverConfig.from_dict(data)


class TestConfigRepresentation:
    """Tests for string representation of config."""
    
    def test_repr_includes_key_info(self):
        """Test that repr includes key configuration information."""
        config = ArchiverConfig(
            blog_name="test",
            output_dir=Path("/tmp/test")
        )
        
        repr_str = repr(config)
        assert "blog_name='test'" in repr_str
        assert "blog_url='https://test.tumblr.com'" in repr_str
        assert "concurrency=" in repr_str
        assert "rate_limit=" in repr_str
    
    def test_repr_is_readable(self):
        """Test that repr produces readable multi-line output."""
        config = ArchiverConfig(
            blog_name="test",
            output_dir=Path("/tmp/test")
        )
        
        repr_str = repr(config)
        assert "ArchiverConfig(" in repr_str
        assert "\n" in repr_str  # Multi-line format
