"""
Main application entry point for the Tumblr archiver.

This module provides the TumblrArchiver class, which serves as the high-level
interface for archiving Tumblr blogs with proper resource management.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from .config import ArchiverConfig
from .exceptions import (
    ArchiverError,
    BlogNotFoundError,
    ConfigurationError,
    NetworkError,
    OrchestratorError,
)
from .http_client import AsyncHTTPClient
from .logger import setup_logging
from .orchestrator import ArchiveStats, Orchestrator

logger = logging.getLogger(__name__)


class TumblrArchiver:
    """
    Main application class for archiving Tumblr blogs.
    
    This class provides a high-level interface for the archiving workflow,
    handling initialization, execution, and cleanup of all components.
    Supports both direct usage and async context manager pattern.
    
    Features:
    - Automatic resource management
    - Comprehensive error handling
    - Async context manager support
    - Logging configuration
    - Clean integration with all archiver components
    
    Example (direct usage):
        ```python
        config = ArchiverConfig(
            blog_name="example",
            output_dir=Path("archive"),
            concurrency=5
        )
        
        archiver = TumblrArchiver(config)
        stats = await archiver.run()
        print(f"Downloaded {stats.downloaded} items")
        await archiver.cleanup()
        ```
    
    Example (context manager):
        ```python
        config = ArchiverConfig(blog_name="example", output_dir=Path("archive"))
        
        async with TumblrArchiver(config) as archiver:
            stats = await archiver.run()
            print(stats)
        ```
    """
    
    def __init__(self, config: ArchiverConfig):
        """
        Initialize the Tumblr archiver.
        
        Args:
            config: Archiver configuration
            
        Raises:
            ConfigurationError: If configuration is invalid
        """
        self.config = config
        self._orchestrator: Optional[Orchestrator] = None
        self._http_client: Optional[AsyncHTTPClient] = None
        self._initialized = False
        self._cleaned_up = False
        
        logger.info(f"Initialized TumblrArchiver for blog '{config.blog_name}'")
    
    async def __aenter__(self) -> "TumblrArchiver":
        """
        Enter async context manager.
        
        Returns:
            Self for use in async with statement
        """
        await self._setup()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Exit async context manager and cleanup resources.
        
        Args:
            exc_type: Exception type if an error occurred
            exc_val: Exception value if an error occurred
            exc_tb: Exception traceback if an error occurred
        """
        await self.cleanup()
        return None
    
    async def _setup(self) -> None:
        """
        Set up logging and ensure output directory exists.
        
        Raises:
            ConfigurationError: If setup fails
        """
        if self._initialized:
            return
        
        try:
            # Set up logging
            log_file = None
            if not self.config.dry_run:
                log_file = self.config.output_dir / "tumblr-archiver.log"
            
            setup_logging(verbose=self.config.verbose, log_file=log_file)
            
            # Create output directory if it doesn't exist
            if not self.config.dry_run:
                self.config.output_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Output directory: {self.config.output_dir}")
            
            self._initialized = True
            logger.info("Application setup complete")
            
        except Exception as e:
            logger.error(f"Failed to set up application: {e}", exc_info=True)
            raise ConfigurationError(
                "Failed to initialize application",
                details=str(e)
            ) from e
    
    async def run(self) -> ArchiveStats:
        """
        Run the complete archiving workflow.
        
        This method:
        1. Sets up logging and directories
        2. Creates the orchestrator
        3. Runs the archiving workflow
        4. Handles errors gracefully
        5. Returns statistics
        
        Returns:
            ArchiveStats with summary of the operation
            
        Raises:
            ConfigurationError: If configuration is invalid
            BlogNotFoundError: If the blog doesn't exist
            NetworkError: If network operations fail
            OrchestratorError: If orchestration fails
            ArchiverError: For other archiving errors
            
        Example:
            ```python
            archiver = TumblrArchiver(config)
            try:
                stats = await archiver.run()
                print(f"Success! Downloaded {stats.downloaded} files")
            except BlogNotFoundError:
                print("Blog not found")
            finally:
                await archiver.cleanup()
            ```
        """
        # Ensure setup is complete
        if not self._initialized:
            await self._setup()
        
        logger.info(f"Starting archive operation for blog '{self.config.blog_name}'")
        logger.info(f"Configuration: {self.config}")
        
        try:
            # Create orchestrator
            self._orchestrator = Orchestrator(self.config)
            
            # Run the archiving workflow
            logger.info("Running orchestrator...")
            stats = await self._orchestrator.run()
            
            logger.info(f"Archive operation completed successfully")
            logger.info(f"Statistics: {stats}")
            
            return stats
        
        except BlogNotFoundError as e:
            logger.error(f"Blog not found: {e}")
            raise
        
        except OrchestratorError as e:
            logger.error(f"Orchestration failed: {e}", exc_info=True)
            raise
        
        except Exception as e:
            logger.error(f"Archive operation failed: {e}", exc_info=True)
            
            # Wrap unexpected errors in ArchiverError
            if isinstance(e, ArchiverError):
                raise
            
            raise ArchiverError(
                "Archive operation failed",
                details=str(e)
            ) from e
    
    async def cleanup(self) -> None:
        """
        Clean up resources.
        
        This method ensures all resources are properly released,
        including HTTP sessions and file handles. It's safe to call
        this method multiple times.
        
        Example:
            ```python
            archiver = TumblrArchiver(config)
            try:
                stats = await archiver.run()
            finally:
                await archiver.cleanup()
            ```
        """
        if self._cleaned_up:
            return
        
        logger.debug("Cleaning up resources...")
        
        try:
            # Orchestrator has its own cleanup via workers and components
            # The HTTP client in the orchestrator will be closed automatically
            # when workers finish, but we can ensure it here
            
            if self._http_client:
                await self._http_client.close()
                logger.debug("HTTP client closed")
            
            logger.info("Cleanup complete")
            
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}", exc_info=True)
            # Don't raise exceptions during cleanup to avoid masking original errors
        finally:
            # Always mark as cleaned up, even if there was an error
            self._cleaned_up = True


async def run_archive_app(config: ArchiverConfig) -> ArchiveStats:
    """
    Convenience function to run the archiver with automatic resource management.
    
    This is a helper function that handles the context manager pattern
    automatically, making it easier to use the archiver in simple scripts.
    
    Args:
        config: Archiver configuration
        
    Returns:
        ArchiveStats with summary of the operation
        
    Raises:
        ConfigurationError: If configuration is invalid
        BlogNotFoundError: If the blog doesn't exist
        NetworkError: If network operations fail
        ArchiverError: For other archiving errors
        
    Example:
        ```python
        from pathlib import Path
        from tumblr_archiver import ArchiverConfig, run_archive_app
        
        config = ArchiverConfig(
            blog_name="example",
            output_dir=Path("archive")
        )
        
        stats = await run_archive_app(config)
        print(f"Downloaded {stats.downloaded} items in {stats.duration_seconds}s")
        ```
    """
    async with TumblrArchiver(config) as archiver:
        return await archiver.run()


__all__ = ["TumblrArchiver", "run_archive_app"]
