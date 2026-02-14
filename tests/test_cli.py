"""
Comprehensive unit tests for CLI module.
"""

import os
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch, MagicMock

import pytest
from click.testing import CliRunner

from tumblr_archiver.cli import main
from tumblr_archiver.archiver import ArchiveResult, ArchiveStatistics
from tumblr_archiver.config import ConfigurationError


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_archive_result():
    """Create a mock archive result."""
    from datetime import datetime, timezone
    
    stats = ArchiveStatistics(
        total_posts=100,
        total_media=250,
        media_downloaded=240,
        media_skipped=5,
        media_failed=5,
        media_recovered=10,
        bytes_downloaded=1024000
    )
    
    return ArchiveResult(
        blog_name='test-blog',
        blog_url='https://test-blog.tumblr.com',
        success=True,
        statistics=stats,
        manifest_path=Path('/tmp/manifest.json'),
        output_dir=Path('/tmp/output'),
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc)
    )


@pytest.fixture
def mock_archiver():
    """Create a mock archiver."""
    archiver = MagicMock()
    archiver.set_progress_callback = Mock()
    return archiver


class TestMainCommand:
    """Tests for main CLI command."""
    
    def test_main_help(self, runner):
        """Test that the main command shows help."""
        result = runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert 'Tumblr Media Archiver' in result.output
        assert 'archive' in result.output
        assert 'config' in result.output
    
    def test_version(self, runner):
        """Test that version command works."""
        result = runner.invoke(main, ['--version'])
        assert result.exit_code == 0
        assert 'tumblr-archiver' in result.output


class TestArchiveCommand:
    """Tests for archive command."""
    
    def test_archive_command_help(self, runner):
        """Test that archive command shows help."""
        result = runner.invoke(main, ['archive', '--help'])
        assert result.exit_code == 0
        assert 'Archive media from a Tumblr blog' in result.output
        assert '--url' in result.output
        assert '--output' in result.output
    
    def test_archive_missing_api_key(self, runner):
        """Test archive command without API key fails."""
        result = runner.invoke(main, ['archive', '--url', 'example'])
        assert result.exit_code == 1
        assert 'API key is required' in result.output
    
    @patch('tumblr_archiver.cli.TumblrArchiver')
    @patch('tumblr_archiver.cli.asyncio.run')
    def test_archive_basic_success(self, mock_asyncio_run, mock_archiver_class, 
                                   runner, mock_archive_result, mock_archiver):
        """Test successful basic archive command."""
        mock_archiver_class.return_value = mock_archiver
        mock_asyncio_run.return_value = mock_archive_result
        
        result = runner.invoke(main, [
            'archive',
            '--url', 'test-blog',
            '--tumblr-api-key', 'test_api_key'
        ])
        
        assert result.exit_code == 0
        assert 'test-blog' in result.output
        mock_archiver_class.assert_called_once()
        mock_asyncio_run.assert_called_once()
    
    @patch('tumblr_archiver.cli.TumblrArchiver')
    @patch('tumblr_archiver.cli.asyncio.run')
    def test_archive_with_options(self, mock_asyncio_run, mock_archiver_class,
                                  runner, mock_archive_result, mock_archiver):
        """Test archive command with various options."""
        mock_archiver_class.return_value = mock_archiver
        mock_asyncio_run.return_value = mock_archive_result
        
        result = runner.invoke(main, [
            'archive',
            '--url', 'test-blog',
            '--tumblr-api-key', 'test_key',
            '--output', './test-output',
            '--concurrency', '4',
            '--rate', '2.0',
            '--exclude-reblogs',
            '--download-embeds',
            '--no-wayback'
        ])
        
        assert result.exit_code == 0
        # Check that configuration was passed correctly
        call_args = mock_archiver_class.call_args
        config = call_args[0][0]
        assert config.concurrency == 4
        assert config.rate_limit == 2.0
        assert config.include_reblogs is False
        assert config.download_embeds is True
        assert config.wayback_enabled is False
    
    @patch('tumblr_archiver.cli.TumblrArchiver')
    @patch('tumblr_archiver.cli.asyncio.run')
    def test_archive_with_oauth(self, mock_asyncio_run, mock_archiver_class,
                                runner, mock_archive_result, mock_archiver):
        """Test archive command with OAuth credentials."""
        mock_archiver_class.return_value = mock_archiver
        mock_asyncio_run.return_value = mock_archive_result
        
        result = runner.invoke(main, [
            'archive',
            '--url', 'test-blog',
            '--tumblr-api-key', 'test_key',
            '--oauth-consumer-key', 'consumer_key',
            '--oauth-token', 'oauth_token'
        ])
        
        assert result.exit_code == 0
        call_args = mock_archiver_class.call_args
        config = call_args[0][0]
        assert config.oauth_consumer_key == 'consumer_key'
        assert config.oauth_token == 'oauth_token'
    
    @patch('tumblr_archiver.cli.TumblrArchiver')
    @patch('tumblr_archiver.cli.asyncio.run')
    def test_archive_dry_run(self, mock_asyncio_run, mock_archiver_class,
                            runner, mock_archive_result, mock_archiver):
        """Test archive command with dry-run flag."""
        mock_archiver_class.return_value = mock_archiver
        mock_asyncio_run.return_value = mock_archive_result
        
        result = runner.invoke(main, [
            'archive',
            '--url', 'test-blog',
            '--tumblr-api-key', 'test_key',
            '--dry-run'
        ])
        
        assert result.exit_code == 0
        assert 'DRY RUN' in result.output
        call_args = mock_archiver_class.call_args
        config = call_args[0][0]
        assert config.dry_run is True
    
    @patch('tumblr_archiver.cli.TumblrArchiver')
    @patch('tumblr_archiver.cli.asyncio.run')
    def test_archive_verbose(self, mock_asyncio_run, mock_archiver_class,
                            runner, mock_archive_result, mock_archiver):
        """Test archive command with verbose flag."""
        mock_archiver_class.return_value = mock_archiver
        mock_asyncio_run.return_value = mock_archive_result
        
        result = runner.invoke(main, [
            'archive',
            '--url', 'test-blog',
            '--tumblr-api-key', 'test_key',
            '--verbose'
        ])
        
        assert result.exit_code == 0
        call_args = mock_archiver_class.call_args
        config = call_args[0][0]
        assert config.verbose is True
    
    @patch('tumblr_archiver.cli.TumblrArchiver')
    @patch('tumblr_archiver.cli.asyncio.run')
    def test_archive_with_log_file(self, mock_asyncio_run, mock_archiver_class,
                                   runner, mock_archive_result, mock_archiver, tmp_path):
        """Test archive command with log file."""
        mock_archiver_class.return_value = mock_archiver
        mock_asyncio_run.return_value = mock_archive_result
        
        log_file = tmp_path / "archive.log"
        
        result = runner.invoke(main, [
            'archive',
            '--url', 'test-blog',
            '--tumblr-api-key', 'test_key',
            '--log-file', str(log_file)
        ])
        
        assert result.exit_code == 0
        call_args = mock_archiver_class.call_args
        config = call_args[0][0]
        assert config.log_file == log_file
    
    @patch('tumblr_archiver.cli.TumblrArchiver')
    @patch('tumblr_archiver.cli.asyncio.run')
    def test_archive_progress_callback(self, mock_asyncio_run, mock_archiver_class,
                                       runner, mock_archive_result, mock_archiver):
        """Test that progress callback is set."""
        mock_archiver_class.return_value = mock_archiver
        mock_asyncio_run.return_value = mock_archive_result
        
        result = runner.invoke(main, [
            'archive',
            '--url', 'test-blog',
            '--tumblr-api-key', 'test_key'
        ])
        
        assert result.exit_code == 0
        # Verify progress callback was set
        mock_archiver.set_progress_callback.assert_called_once()
    
    @patch('tumblr_archiver.cli.TumblrArchiver')
    @patch('tumblr_archiver.cli.asyncio.run')
    def test_archive_failure(self, mock_asyncio_run, mock_archiver_class,
                            runner, mock_archiver):
        """Test archive command with failure result."""
        from datetime import datetime, timezone
        
        mock_archiver_class.return_value = mock_archiver
        
        failed_result = ArchiveResult(
            blog_name='test-blog',
            blog_url='https://test-blog.tumblr.com',
            success=False,
            statistics=ArchiveStatistics(),
            manifest_path=Path('/tmp/manifest.json'),
            output_dir=Path('/tmp/output'),
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            error_message='Archive failed'
        )
        mock_asyncio_run.return_value = failed_result
        
        result = runner.invoke(main, [
            'archive',
            '--url', 'test-blog',
            '--tumblr-api-key', 'test_key'
        ])
        
        assert result.exit_code == 1
    
    @patch('tumblr_archiver.cli.TumblrArchiver')
    def test_archive_configuration_error(self, mock_archiver_class, runner):
        """Test archive command with configuration error."""
        mock_archiver_class.side_effect = ConfigurationError("Invalid config")
        
        result = runner.invoke(main, [
            'archive',
            '--url', 'test-blog',
            '--tumblr-api-key', 'test_key'
        ])
        
        assert result.exit_code == 1
        assert 'Configuration Error' in result.output
    
    @patch('tumblr_archiver.cli.TumblrArchiver')
    @patch('tumblr_archiver.cli.asyncio.run')
    def test_archive_keyboard_interrupt(self, mock_asyncio_run, mock_archiver_class,
                                       runner, mock_archiver):
        """Test archive command with keyboard interrupt."""
        mock_archiver_class.return_value = mock_archiver
        mock_asyncio_run.side_effect = KeyboardInterrupt()
        
        result = runner.invoke(main, [
            'archive',
            '--url', 'test-blog',
            '--tumblr-api-key', 'test_key'
        ])
        
        assert result.exit_code == 130
        assert 'interrupted' in result.output.lower()
    
    @patch('tumblr_archiver.cli.TumblrArchiver')
    @patch('tumblr_archiver.cli.asyncio.run')
    def test_archive_unexpected_error(self, mock_asyncio_run, mock_archiver_class,
                                      runner, mock_archiver):
        """Test archive command with unexpected error."""
        mock_archiver_class.return_value = mock_archiver
        mock_asyncio_run.side_effect = Exception("Unexpected error")
        
        result = runner.invoke(main, [
            'archive',
            '--url', 'test-blog',
            '--tumblr-api-key', 'test_key'
        ])
        
        assert result.exit_code == 1
        assert 'Unexpected Error' in result.output
    
    def test_archive_api_key_from_env(self, runner, monkeypatch):
        """Test API key is read from environment variable."""
        monkeypatch.setenv('TUMBLR_API_KEY', 'env_api_key')
        
        with patch('tumblr_archiver.cli.TumblrArchiver') as mock_archiver_class, \
             patch('tumblr_archiver.cli.asyncio.run') as mock_asyncio_run:
            from datetime import datetime, timezone
            
            mock_archiver = MagicMock()
            mock_archiver_class.return_value = mock_archiver
            
            mock_result = ArchiveResult(
                blog_name='test-blog',
                blog_url='https://test-blog.tumblr.com',
                success=True,
                statistics=ArchiveStatistics(),
                manifest_path=Path('/tmp/manifest.json'),
                output_dir=Path('/tmp/output'),
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc)
            )
            mock_asyncio_run.return_value = mock_result
            
            result = runner.invoke(main, [
                'archive',
                '--url', 'test-blog'
            ])
            
            assert result.exit_code == 0
            call_args = mock_archiver_class.call_args
            config = call_args[0][0]
            assert config.tumblr_api_key == 'env_api_key'


class TestConfigCommand:
    """Tests for config command."""
    
    def test_config_command_basic(self, runner):
        """Test basic config command."""
        result = runner.invoke(main, ['config'])
        assert result.exit_code == 0
        assert 'Configuration' in result.output
        assert 'API Credentials' in result.output
    
    def test_config_command_without_api_key(self, runner):
        """Test config command when API key is not set."""
        result = runner.invoke(main, ['config'])
        assert result.exit_code == 0
        assert 'Not set' in result.output
    
    def test_config_command_with_api_key(self, runner, monkeypatch):
        """Test config command with API key set."""
        monkeypatch.setenv('TUMBLR_API_KEY', 'test_api_key_12345')
        
        result = runner.invoke(main, ['config'])
        assert result.exit_code == 0
        assert 'Present' in result.output
        assert 'test_api' in result.output  # Should show masked version
        assert 'test_api_key_12345' not in result.output  # Should not show full key
    
    def test_config_command_with_oauth(self, runner, monkeypatch):
        """Test config command with OAuth credentials."""
        monkeypatch.setenv('TUMBLR_OAUTH_CONSUMER_KEY', 'consumer_key_123')
        monkeypatch.setenv('TUMBLR_OAUTH_TOKEN', 'oauth_token_456')
        
        result = runner.invoke(main, ['config'])
        assert result.exit_code == 0
        assert 'OAuth Consumer Key' in result.output
        assert 'OAuth Token' in result.output
        assert 'Present' in result.output
    
    def test_config_command_verbose(self, runner, monkeypatch):
        """Test config command with verbose flag."""
        monkeypatch.setenv('TUMBLR_API_KEY', 'test_key')
        
        result = runner.invoke(main, ['config', '--verbose'])
        assert result.exit_code == 0
        assert 'Environment Variables Checked' in result.output
        assert 'TUMBLR_API_KEY' in result.output
    
    def test_config_command_shows_defaults(self, runner):
        """Test that config command shows default settings."""
        result = runner.invoke(main, ['config'])
        assert result.exit_code == 0
        assert 'Default Settings' in result.output
        assert 'output_dir' in result.output
        assert 'rate_limit' in result.output
        assert 'concurrency' in result.output
    
    def test_config_command_shows_usage(self, runner):
        """Test that config command shows usage information."""
        result = runner.invoke(main, ['config'])
        assert result.exit_code == 0
        assert 'Usage' in result.output
        assert 'tumblr.com/oauth/apps' in result.output
