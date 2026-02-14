"""Logging configuration for the Tumblr archiver."""

import logging
import sys
from pathlib import Path
from typing import Optional


class CleanFormatter(logging.Formatter):
    """Custom formatter for clean, structured log output.
    
    Formats logs with timestamps, level, logger name, and message.
    Uses color coding for different log levels when outputting to console.
    """
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    def __init__(self, use_colors: bool = True, verbose: bool = False):
        """Initialize formatter.
        
        Args:
            use_colors: Whether to use ANSI color codes
            verbose: Whether to include logger name in output
        """
        self.use_colors = use_colors
        self.verbose = verbose
        
        if verbose:
            fmt = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        else:
            fmt = '%(asctime)s [%(levelname)s] %(message)s'
        
        super().__init__(fmt=fmt, datefmt='%Y-%m-%d %H:%M:%S')
    
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record.
        
        Args:
            record: Log record to format
            
        Returns:
            Formatted log string
        """
        # Format the base message
        formatted = super().format(record)
        
        # Add colors for console output if enabled
        if self.use_colors and record.levelname in self.COLORS:
            color = self.COLORS[record.levelname]
            reset = self.COLORS['RESET']
            # Color the level name only
            formatted = formatted.replace(
                f'[{record.levelname}]',
                f'[{color}{record.levelname}{reset}]'
            )
        
        return formatted


def setup_logging(
    verbose: bool = False,
    log_file: Optional[Path] = None,
    console: bool = True,
    level: Optional[int] = None
) -> None:
    """Configure logging for the application.
    
    Sets up both console and file handlers with appropriate formatting
    and log levels.
    
    Args:
        verbose: If True, use DEBUG level and show logger names
        log_file: Optional path to log file
        console: Whether to enable console output
        level: Override log level (if not provided, uses INFO or DEBUG based on verbose)
    
    Example:
        setup_logging(verbose=True, log_file=Path("tumblr.log"))
        logger = get_logger(__name__)
        logger.info("Starting download...")
    """
    # Determine log level
    if level is None:
        level = logging.DEBUG if verbose else logging.INFO
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all, filter at handlers
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    handlers = []
    
    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(
            CleanFormatter(use_colors=True, verbose=verbose)
        )
        handlers.append(console_handler)
    
    # File handler
    if log_file:
        # Create parent directory if it doesn't exist
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file
        file_handler.setFormatter(
            CleanFormatter(use_colors=False, verbose=True)
        )
        handlers.append(file_handler)
    
    # Add all handlers to root logger
    for handler in handlers:
        root_logger.addHandler(handler)
    
    # Silence noisy third-party loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
        
    Example:
        logger = get_logger(__name__)
        logger.info("Processing post...")
    """
    return logging.getLogger(name)


def set_log_level(level: int) -> None:
    """Change the log level for all console handlers.
    
    Args:
        level: New log level (e.g., logging.DEBUG, logging.INFO)
    """
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
            handler.setLevel(level)


def add_file_handler(log_file: Path, level: int = logging.DEBUG) -> None:
    """Add a file handler to the root logger.
    
    Args:
        log_file: Path to log file
        level: Log level for file handler
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(
        CleanFormatter(use_colors=False, verbose=True)
    )
    
    logging.getLogger().addHandler(file_handler)


def log_exception(logger: logging.Logger, message: str, exc: Exception) -> None:
    """Log an exception with traceback.
    
    Args:
        logger: Logger instance
        message: Context message
        exc: Exception to log
    """
    logger.error(f"{message}: {exc}", exc_info=True)
