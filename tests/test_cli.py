"""
Tests for CLI interface.

This module tests the command-line interface argument parsing,
validation, and configuration creation.
"""

from pathlib import Path

from click.testing import CliRunner

from tumblr_archiver import __version__
from tumblr_archiver.cli import cli, normalize_blog_identifier
from tumblr_archiver.config import ArchiverConfig
from tumblr_archiver.constants import (
    DEFAULT_CONCURRENCY,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RATE_LIMIT,
    DEFAULT_TIMEOUT,
)


class TestNormalizeBlogIdentifier:
    """Test blog identifier normalization."""
    
    def test_normalize_simple_name(self):
        """Test normalizing a simple blog name."""
        assert normalize_blog_identifier("myblog") == "myblog"
    
    def test_normalize_with_tumblr_domain(self):
        """Test normalizing blog name with .tumblr.com."""
        assert normalize_blog_identifier("myblog.tumblr.com") == "myblog"
    
    def test_normalize_with_https_url(self):
        """Test normalizing full HTTPS URL."""
        assert normalize_blog_identifier("https://myblog.tumblr.com") == "myblog"
    
    def test_normalize_with_http_url(self):
        """Test normalizing full HTTP URL."""
        assert normalize_blog_identifier("http://myblog.tumblr.com") == "myblog"
    
    def test_normalize_with_trailing_slash(self):
        """Test normalizing URL with trailing slash."""
        assert normalize_blog_identifier("https://myblog.tumblr.com/") == "myblog"
    
    def test_normalize_complex_url(self):
        """Test normalizing complex URL."""
        assert normalize_blog_identifier("https://myblog.tumblr.com///") == "myblog"


class TestCLIBasics:
    """Test basic CLI functionality."""
    
    def test_version_flag(self):
        """Test --version flag."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        
        assert result.exit_code == 0
        assert __version__ in result.output
        assert "tumblr-archiver" in result.output
    
    def test_help_flag(self):
        """Test --help flag."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        
        assert result.exit_code == 0
        assert "Archive media from Tumblr blogs" in result.output
        assert "BLOG" in result.output
        assert "--output" in result.output
        assert "--concurrency" in result.output
        assert "--rate" in result.output
        assert "--verbose" in result.output
    
    def test_missing_blog_argument(self):
        """Test error when blog argument is missing."""
        runner = CliRunner()
        result = runner.invoke(cli, [])
        
        assert result.exit_code != 0
        assert "Error" in result.output or "Missing argument" in result.output


class TestCLIArgumentParsing:
    """Test CLI argument parsing and configuration creation."""
    
    def test_minimal_arguments(self):
        """Test CLI with only required arguments."""
        runner = CliRunner()
        result = runner.invoke(cli, ["myblog"], standalone_mode=False, catch_exceptions=False)
        
        assert result.exit_code == 0
        
        config = result.return_value
        assert isinstance(config, ArchiverConfig)
        assert config.blog_name == "myblog"
        assert config.output_dir.name == "downloads"
        assert config.concurrency == DEFAULT_CONCURRENCY
        assert config.rate_limit == DEFAULT_RATE_LIMIT
        assert config.resume is True
        assert config.include_reblogs is True
        assert config.download_embeds is False
        assert config.dry_run is False
        assert config.verbose is False
    
    def test_custom_output_directory(self):
        """Test --output option."""
        runner = CliRunner()
        result = runner.invoke(
            cli, 
            ["myblog", "--output", "/tmp/archive"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        assert config.output_dir.resolve() == Path("/tmp/archive").resolve()
    
    def test_short_output_option(self):
        """Test -o short option."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["myblog", "-o", "./myarchive"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        assert config.output_dir.name == "myarchive"
    
    def test_custom_concurrency(self):
        """Test --concurrency option."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["myblog", "--concurrency", "5"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        assert config.concurrency == 5
    
    def test_short_concurrency_option(self):
        """Test -c short option."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["myblog", "-c", "3"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        assert config.concurrency == 3
    
    def test_custom_rate_limit(self):
        """Test --rate option."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["myblog", "--rate", "0.5"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        assert config.rate_limit == 0.5
    
    def test_short_rate_option(self):
        """Test -r short option."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["myblog", "-r", "2.5"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        assert config.rate_limit == 2.5
    
    def test_verbose_flag(self):
        """Test --verbose flag."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["myblog", "--verbose"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        assert config.verbose is True
    
    def test_short_verbose_flag(self):
        """Test -v short flag."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["myblog", "-v"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        assert config.verbose is True
    
    def test_dry_run_flag(self):
        """Test --dry-run flag."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["myblog", "--dry-run"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        assert config.dry_run is True
    
    def test_download_embeds_flag(self):
        """Test --download-embeds flag."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["myblog", "--download-embeds"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        assert config.download_embeds is True
    
    def test_max_retries_option(self):
        """Test --max-retries option."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["myblog", "--max-retries", "5"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        assert config.max_retries == 5
    
    def test_timeout_option(self):
        """Test --timeout option."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["myblog", "--timeout", "60.0"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        assert config.timeout == 60.0


class TestCLIBooleanFlags:
    """Test boolean flag combinations."""
    
    def test_resume_enabled_by_default(self):
        """Test that resume is enabled by default."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["myblog"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        assert config.resume is True
    
    def test_no_resume_flag(self):
        """Test --no-resume flag."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["myblog", "--no-resume"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        assert config.resume is False
    
    def test_resume_flag_explicit(self):
        """Test explicit --resume flag."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["myblog", "--resume"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        assert config.resume is True
    
    def test_include_reblogs_by_default(self):
        """Test that reblogs are included by default."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["myblog"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        assert config.include_reblogs is True
    
    def test_exclude_reblogs_flag(self):
        """Test --exclude-reblogs flag."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["myblog", "--exclude-reblogs"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        assert config.include_reblogs is False
    
    def test_include_reblogs_flag_explicit(self):
        """Test explicit --include-reblogs flag."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["myblog", "--include-reblogs"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        assert config.include_reblogs is True


class TestCLIBlogNameFormats:
    """Test different blog name formats."""
    
    def test_simple_blog_name(self):
        """Test simple blog name."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["myblog"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        assert config.blog_name == "myblog"
    
    def test_blog_with_tumblr_domain(self):
        """Test blog name with .tumblr.com."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["myblog.tumblr.com"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        assert config.blog_name == "myblog"
    
    def test_full_url_https(self):
        """Test full HTTPS URL."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["https://myblog.tumblr.com"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        assert config.blog_name == "myblog"
    
    def test_full_url_http(self):
        """Test full HTTP URL."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["http://myblog.tumblr.com"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        assert config.blog_name == "myblog"


class TestCLIValidation:
    """Test CLI validation."""
    
    def test_invalid_concurrency_too_low(self):
        """Test concurrency value too low."""
        runner = CliRunner()
        result = runner.invoke(cli, ["myblog", "--concurrency", "0"])
        
        assert result.exit_code != 0
        assert "Invalid value" in result.output or "out of range" in result.output
    
    def test_invalid_concurrency_too_high(self):
        """Test concurrency value too high."""
        runner = CliRunner()
        result = runner.invoke(cli, ["myblog", "--concurrency", "20"])
        
        assert result.exit_code != 0
        assert "Invalid value" in result.output or "out of range" in result.output
    
    def test_invalid_rate_negative(self):
        """Test negative rate value."""
        runner = CliRunner()
        result = runner.invoke(cli, ["myblog", "--rate", "-1"])
        
        assert result.exit_code != 0
        assert "Invalid value" in result.output or "out of range" in result.output
    
    def test_invalid_max_retries_negative(self):
        """Test negative max-retries value."""
        runner = CliRunner()
        result = runner.invoke(cli, ["myblog", "--max-retries", "-1"])
        
        assert result.exit_code != 0
        assert "Invalid value" in result.output or "out of range" in result.output
    
    def test_invalid_timeout_too_low(self):
        """Test timeout value too low."""
        runner = CliRunner()
        result = runner.invoke(cli, ["myblog", "--timeout", "0.5"])
        
        assert result.exit_code != 0
        assert "Invalid value" in result.output or "out of range" in result.output


class TestCLICombinations:
    """Test combinations of CLI arguments."""
    
    def test_all_options(self):
        """Test CLI with all options specified."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "myblog",
                "--output", "/tmp/archive",
                "--concurrency", "4",
                "--rate", "2.0",
                "--no-resume",
                "--exclude-reblogs",
                "--download-embeds",
                "--dry-run",
                "--verbose",
                "--max-retries", "5",
                "--timeout", "60.0",
            ],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        
        assert config.blog_name == "myblog"
        assert config.output_dir.resolve() == Path("/tmp/archive").resolve()
        assert config.concurrency == 4
        assert config.rate_limit == 2.0
        assert config.resume is False
        assert config.include_reblogs is False
        assert config.download_embeds is True
        assert config.dry_run is True
        assert config.verbose is True
        assert config.max_retries == 5
        assert config.timeout == 60.0
    
    def test_short_options(self):
        """Test CLI with short option combinations."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["myblog", "-o", "/tmp/test", "-c", "3", "-r", "1.5", "-v"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        
        assert config.output_dir.resolve() == Path("/tmp/test").resolve()
        assert config.concurrency == 3
        assert config.rate_limit == 1.5
        assert config.verbose is True
    
    def test_blog_url_with_options(self):
        """Test full blog URL with additional options."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["https://myblog.tumblr.com", "-o", "./archive", "--dry-run"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        
        assert config.blog_name == "myblog"
        assert config.output_dir.name == "archive"
        assert config.dry_run is True


class TestCLIDefaults:
    """Test CLI default values."""
    
    def test_default_values(self):
        """Test that all default values are correctly set."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["myblog"],
            standalone_mode=False,
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        config = result.return_value
        
        # Check all defaults
        assert config.output_dir.name == "downloads"
        assert config.concurrency == DEFAULT_CONCURRENCY
        assert config.rate_limit == DEFAULT_RATE_LIMIT
        assert config.max_retries == DEFAULT_MAX_RETRIES
        assert config.timeout == DEFAULT_TIMEOUT
        assert config.resume is True
        assert config.include_reblogs is True
        assert config.download_embeds is False
        assert config.dry_run is False
        assert config.verbose is False
