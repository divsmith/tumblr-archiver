"""
Tests for configuration management module.
"""

import os
import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory, NamedTemporaryFile
from unittest.mock import patch

from tumblr_archiver.config import (
    ArchiverConfig,
    ConfigLoader,
    ConfigurationError,
    parse_blog_url,
    get_default_output_dir,
    save_config,
    load_config,
)


class TestArchiverConfig:
    """Test ArchiverConfig dataclass."""
    
    def test_minimal_config(self):
        """Test creating config with minimal required fields."""
        config = ArchiverConfig(
            blog_url="example",
            output_dir=Path("/tmp/output")
        )
        assert config.blog_url == "example"
        assert config.output_dir == Path("/tmp/output")
        assert config.resume is True
        assert config.rate_limit == 1.0
        assert config.concurrency == 2
    
    def test_full_config(self):
        """Test creating config with all fields."""
        config = ArchiverConfig(
            blog_url="test-blog",
            output_dir=Path("/output"),
            tumblr_api_key="test-key",
            oauth_consumer_key="consumer",
            oauth_token="token",
            resume=False,
            include_reblogs=False,
            download_embeds=True,
            recover_removed_media=False,
            wayback_enabled=False,
            wayback_max_snapshots=10,
            rate_limit=2.0,
            concurrency=4,
            max_retries=5,
            base_backoff=2.0,
            max_backoff=64.0,
            verbose=True,
            dry_run=True,
            log_file=Path("/var/log/tumblr.log")
        )
        assert config.tumblr_api_key == "test-key"
        assert config.verbose is True
        assert config.concurrency == 4
    
    def test_path_conversion(self):
        """Test that string paths are converted to Path objects."""
        config = ArchiverConfig(
            blog_url="test",
            output_dir="/tmp/test"  # String path
        )
        assert isinstance(config.output_dir, Path)
        assert config.output_dir == Path("/tmp/test")


class TestParseBlogUrl:
    """Test parse_blog_url function."""
    
    def test_parse_simple_username(self):
        """Test parsing a simple username."""
        assert parse_blog_url("example") == "example"
        assert parse_blog_url("my-blog-123") == "my-blog-123"
    
    def test_parse_tumblr_subdomain(self):
        """Test parsing username.tumblr.com format."""
        assert parse_blog_url("example.tumblr.com") == "example"
        assert parse_blog_url("my-blog.tumblr.com") == "my-blog"
        assert parse_blog_url("test123.tumblr.com/") == "test123"
    
    def test_parse_https_url(self):
        """Test parsing full HTTPS URLs."""
        assert parse_blog_url("https://example.tumblr.com") == "example"
        assert parse_blog_url("https://my-blog.tumblr.com/") == "my-blog"
    
    def test_parse_http_url(self):
        """Test parsing HTTP URLs."""
        assert parse_blog_url("http://example.tumblr.com") == "example"
    
    def test_parse_tumblr_com_path(self):
        """Test parsing tumblr.com/username format."""
        assert parse_blog_url("https://www.tumblr.com/example") == "example"
        assert parse_blog_url("https://tumblr.com/my-blog/") == "my-blog"
    
    def test_parse_with_whitespace(self):
        """Test that whitespace is stripped."""
        assert parse_blog_url("  example  ") == "example"
        assert parse_blog_url("\texample\n") == "example"
    
    def test_parse_empty_url(self):
        """Test that empty URL raises error."""
        with pytest.raises(ConfigurationError, match="cannot be empty"):
            parse_blog_url("")
    
    def test_parse_invalid_url(self):
        """Test that invalid URLs raise errors."""
        with pytest.raises(ConfigurationError, match="Invalid blog URL format"):
            parse_blog_url("https://example.com")
        
        with pytest.raises(ConfigurationError, match="Invalid blog URL format"):
            parse_blog_url("not a valid url!")


class TestGetDefaultOutputDir:
    """Test get_default_output_dir function."""
    
    def test_simple_blog_name(self):
        """Test default directory for simple blog name."""
        result = get_default_output_dir("example")
        assert result.name == "example_archive"
        assert result.parent == Path.cwd()
    
    def test_blog_name_with_special_chars(self):
        """Test that special characters are replaced."""
        result = get_default_output_dir("my@blog#name!")
        assert result.name == "my_blog_name__archive"


class TestConfigLoader:
    """Test ConfigLoader class methods."""
    
    def test_load_from_env(self):
        """Test loading configuration from environment variables."""
        env_vars = {
            'TUMBLR_BLOG_URL': 'test-blog',
            'TUMBLR_API_KEY': 'test-key',
            'TUMBLR_RATE_LIMIT': '2.5',
            'TUMBLR_CONCURRENCY': '4',
            'TUMBLR_VERBOSE': 'true',
            'TUMBLR_DRY_RUN': 'false',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = ConfigLoader.load_from_env(load_dotenv_file=False)
        
        assert config['blog_url'] == 'test-blog'
        assert config['tumblr_api_key'] == 'test-key'
        assert config['rate_limit'] == 2.5
        assert config['concurrency'] == 4
        assert config['verbose'] is True
        assert config['dry_run'] is False
    
    def test_load_from_env_boolean_variations(self):
        """Test different boolean value formats."""
        test_cases = [
            ('true', True), ('True', True), ('TRUE', True),
            ('1', True), ('yes', True), ('on', True),
            ('false', False), ('False', False), ('0', False),
            ('no', False), ('off', False),
        ]
        
        for env_value, expected in test_cases:
            with patch.dict(os.environ, {'TUMBLR_VERBOSE': env_value}, clear=True):
                config = ConfigLoader.load_from_env(load_dotenv_file=False)
                assert config.get('verbose') == expected
    
    def test_load_from_env_invalid_int(self):
        """Test that invalid integer raises error."""
        with patch.dict(os.environ, {'TUMBLR_CONCURRENCY': 'not-a-number'}, clear=True):
            with pytest.raises(ConfigurationError, match="Invalid integer"):
                ConfigLoader.load_from_env(load_dotenv_file=False)
    
    def test_load_from_env_invalid_float(self):
        """Test that invalid float raises error."""
        with patch.dict(os.environ, {'TUMBLR_RATE_LIMIT': 'invalid'}, clear=True):
            with pytest.raises(ConfigurationError, match="Invalid float"):
                ConfigLoader.load_from_env(load_dotenv_file=False)
    
    def test_load_from_file_json(self):
        """Test loading configuration from JSON file."""
        config_data = {
            'blog_url': 'example',
            'output_dir': '/tmp/output',
            'tumblr_api_key': 'test-key',
            'rate_limit': 2.0,
            'concurrency': 3,
            'verbose': True
        }
        
        with NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = Path(f.name)
        
        try:
            config = ConfigLoader.load_from_file(temp_path)
            assert config['blog_url'] == 'example'
            assert config['tumblr_api_key'] == 'test-key'
            assert config['rate_limit'] == 2.0
            assert isinstance(config['output_dir'], Path)
        finally:
            temp_path.unlink()
    
    def test_load_from_file_not_found(self):
        """Test that missing file raises error."""
        with pytest.raises(ConfigurationError, match="not found"):
            ConfigLoader.load_from_file(Path("/nonexistent/config.json"))
    
    def test_load_from_file_invalid_json(self):
        """Test that invalid JSON raises error."""
        with NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(ConfigurationError, match="Invalid JSON"):
                ConfigLoader.load_from_file(temp_path)
        finally:
            temp_path.unlink()
    
    def test_load_from_file_unsupported_format(self):
        """Test that unsupported file format raises error."""
        with NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("config")
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(ConfigurationError, match="Unsupported config file format"):
                ConfigLoader.load_from_file(temp_path)
        finally:
            temp_path.unlink()
    
    def test_load_from_cli_args(self):
        """Test loading configuration from CLI arguments."""
        cli_args = {
            'blog_url': 'test-blog',
            'output_dir': '/tmp/output',
            'tumblr_api_key': 'key123',
            'rate_limit': 3.0,
            'verbose': True,
            'some_none_value': None,  # Should be filtered out
        }
        
        config = ConfigLoader.load_from_cli_args(cli_args)
        
        assert config['blog_url'] == 'test-blog'
        assert config['tumblr_api_key'] == 'key123'
        assert config['rate_limit'] == 3.0
        assert 'some_none_value' not in config
    
    def test_load_from_cli_args_hyphen_conversion(self):
        """Test that hyphens in CLI args are converted to underscores."""
        cli_args = {'blog-url': 'test', 'output-dir': '/tmp'}
        config = ConfigLoader.load_from_cli_args(cli_args)
        assert 'blog_url' in config
        assert 'output_dir' in config
    
    def test_merge_configs(self):
        """Test merging multiple configuration dictionaries."""
        config1 = {'blog_url': 'first', 'rate_limit': 1.0}
        config2 = {'rate_limit': 2.0, 'concurrency': 3}
        config3 = {'concurrency': 5, 'verbose': True}
        
        merged = ConfigLoader.merge_configs(config1, config2, config3)
        
        assert merged['blog_url'] == 'first'
        assert merged['rate_limit'] == 2.0  # Overridden by config2
        assert merged['concurrency'] == 5  # Overridden by config3
        assert merged['verbose'] is True
    
    def test_merge_configs_none_values(self):
        """Test that None values don't override existing values."""
        config1 = {'blog_url': 'test', 'rate_limit': 1.0}
        config2 = {'blog_url': None, 'verbose': True}
        
        merged = ConfigLoader.merge_configs(config1, config2)
        
        assert merged['blog_url'] == 'test'  # Not overridden by None
        assert merged['verbose'] is True


class TestValidation:
    """Test configuration validation."""
    
    def test_validate_valid_config(self):
        """Test that valid config passes validation."""
        config = ArchiverConfig(
            blog_url="example",
            output_dir=Path("/tmp/test"),
            tumblr_api_key="test-key"
        )
        # Should not raise
        ConfigLoader.validate(config)
    
    def test_validate_missing_blog_url(self):
        """Test that missing blog_url fails validation."""
        config = ArchiverConfig(
            blog_url="",
            output_dir=Path("/tmp/test"),
            tumblr_api_key="test-key"
        )
        with pytest.raises(ConfigurationError, match="blog_url is required"):
            ConfigLoader.validate(config)
    
    def test_validate_missing_api_key(self):
        """Test that missing API key fails validation."""
        config = ArchiverConfig(
            blog_url="example",
            output_dir=Path("/tmp/test")
        )
        with pytest.raises(ConfigurationError, match="tumblr_api_key"):
            ConfigLoader.validate(config)
    
    def test_validate_oauth_credentials(self):
        """Test that OAuth credentials do NOT replace the API key."""
        config = ArchiverConfig(
            blog_url="example",
            output_dir=Path("/tmp/test"),
            oauth_consumer_key="consumer",
            oauth_token="token"
        )
        with pytest.raises(ConfigurationError, match="tumblr_api_key is required"):
            ConfigLoader.validate(config)
    
    def test_validate_invalid_rate_limit(self):
        """Test that rate_limit <= 0 fails validation."""
        config = ArchiverConfig(
            blog_url="example",
            output_dir=Path("/tmp/test"),
            tumblr_api_key="key",
            rate_limit=0
        )
        with pytest.raises(ConfigurationError, match="rate_limit must be > 0"):
            ConfigLoader.validate(config)
    
    def test_validate_invalid_concurrency(self):
        """Test that concurrency < 1 fails validation."""
        config = ArchiverConfig(
            blog_url="example",
            output_dir=Path("/tmp/test"),
            tumblr_api_key="key",
            concurrency=0
        )
        with pytest.raises(ConfigurationError, match="concurrency must be >= 1"):
            ConfigLoader.validate(config)
    
    def test_validate_invalid_wayback_snapshots(self):
        """Test that wayback_max_snapshots < 1 fails validation."""
        config = ArchiverConfig(
            blog_url="example",
            output_dir=Path("/tmp/test"),
            tumblr_api_key="key",
            wayback_max_snapshots=0
        )
        with pytest.raises(ConfigurationError, match="wayback_max_snapshots"):
            ConfigLoader.validate(config)
    
    def test_validate_invalid_max_retries(self):
        """Test that max_retries < 0 fails validation."""
        config = ArchiverConfig(
            blog_url="example",
            output_dir=Path("/tmp/test"),
            tumblr_api_key="key",
            max_retries=-1
        )
        with pytest.raises(ConfigurationError, match="max_retries must be >= 0"):
            ConfigLoader.validate(config)
    
    def test_validate_invalid_backoff(self):
        """Test that max_backoff < base_backoff fails validation."""
        config = ArchiverConfig(
            blog_url="example",
            output_dir=Path("/tmp/test"),
            tumblr_api_key="key",
            base_backoff=10.0,
            max_backoff=5.0
        )
        with pytest.raises(ConfigurationError, match="max_backoff.*must be >= base_backoff"):
            ConfigLoader.validate(config)
    
    def test_validate_multiple_errors(self):
        """Test that multiple validation errors are reported together."""
        config = ArchiverConfig(
            blog_url="",
            output_dir=Path("/tmp/test"),
            rate_limit=-1,
            concurrency=0
        )
        with pytest.raises(ConfigurationError) as exc_info:
            ConfigLoader.validate(config)
        
        error_msg = str(exc_info.value)
        assert "blog_url is required" in error_msg
        assert "rate_limit" in error_msg
        assert "concurrency" in error_msg


class TestSaveConfig:
    """Test save_config function."""
    
    def test_save_config_json(self):
        """Test saving configuration to JSON file."""
        config = ArchiverConfig(
            blog_url="example",
            output_dir=Path("/tmp/test"),
            tumblr_api_key="test-key",
            rate_limit=2.0,
            verbose=True
        )
        
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            save_config(config, config_path)
            
            assert config_path.exists()
            
            with open(config_path) as f:
                loaded = json.load(f)
            
            assert loaded['blog_url'] == 'example'
            assert loaded['tumblr_api_key'] == 'test-key'
            assert loaded['rate_limit'] == 2.0
            assert loaded['verbose'] is True
    
    def test_save_config_creates_parent_dir(self):
        """Test that parent directories are created."""
        config = ArchiverConfig(
            blog_url="example",
            output_dir=Path("/tmp/test"),
            tumblr_api_key="key"
        )
        
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "subdir" / "config.json"
            save_config(config, config_path)
            
            assert config_path.exists()
    
    def test_save_config_unsupported_format(self):
        """Test that unsupported format raises error."""
        config = ArchiverConfig(
            blog_url="example",
            output_dir=Path("/tmp/test"),
            tumblr_api_key="key"
        )
        
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.txt"
            with pytest.raises(ConfigurationError, match="Unsupported config file format"):
                save_config(config, config_path)


class TestLoadConfig:
    """Test load_config integration function."""
    
    def test_load_config_from_cli_args(self):
        """Test loading config from CLI arguments only."""
        cli_args = {
            'blog_url': 'test-blog',
            'output_dir': '/tmp/output',
            'tumblr_api_key': 'test-key',
            'rate_limit': 2.0,
            'verbose': True
        }
        
        config = load_config(cli_args=cli_args, load_env=False)
        
        assert config.blog_url == 'test-blog'
        assert config.tumblr_api_key == 'test-key'
        assert config.rate_limit == 2.0
        assert config.verbose is True
    
    def test_load_config_parses_blog_url(self):
        """Test that blog URL is automatically parsed."""
        cli_args = {
            'blog_url': 'https://example.tumblr.com',
            'tumblr_api_key': 'key'
        }
        
        config = load_config(cli_args=cli_args, load_env=False)
        assert config.blog_url == 'example'  # Parsed to just username
    
    def test_load_config_sets_default_output_dir(self):
        """Test that default output directory is set."""
        cli_args = {
            'blog_url': 'example',
            'tumblr_api_key': 'key'
        }
        
        config = load_config(cli_args=cli_args, load_env=False)
        assert 'example_archive' in str(config.output_dir)
    
    def test_load_config_precedence(self):
        """Test that CLI args override environment variables."""
        env_vars = {
            'TUMBLR_BLOG_URL': 'env-blog',
            'TUMBLR_API_KEY': 'env-key',
            'TUMBLR_RATE_LIMIT': '1.0'
        }
        
        cli_args = {
            'blog_url': 'cli-blog',
            'rate_limit': 3.0
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = load_config(cli_args=cli_args, load_env=True)
        
        assert config.blog_url == 'cli-blog'  # CLI overrides env
        assert config.tumblr_api_key == 'env-key'  # From env
        assert config.rate_limit == 3.0  # CLI overrides env
    
    def test_load_config_no_config_provided(self):
        """Test that error is raised when no config is provided."""
        with pytest.raises(ConfigurationError, match="No configuration provided"):
            load_config(load_env=False)
    
    def test_load_config_validation_failure(self):
        """Test that validation errors are raised."""
        cli_args = {
            'blog_url': 'example',
            'rate_limit': -1  # Invalid
        }
        
        with pytest.raises(ConfigurationError, match="rate_limit"):
            load_config(cli_args=cli_args, load_env=False)
