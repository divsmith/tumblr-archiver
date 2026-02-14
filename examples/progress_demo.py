"""Demonstration of progress tracking and logging features."""

import time
from pathlib import Path
from tumblr_archiver.progress import ProgressTracker
from tumblr_archiver.logger import setup_logging, get_logger


def demo_basic_progress():
    """Demonstrate basic progress tracking."""
    print("\n=== Basic Progress Tracking ===\n")
    
    tracker = ProgressTracker(total=50)
    tracker.start()
    
    for i in range(50):
        time.sleep(0.05)  # Simulate work
        
        if i % 3 == 0:
            tracker.skip()  # Skip every 3rd item
        elif i % 7 == 0:
            tracker.fail()  # Fail every 7th item
        else:
            tracker.complete()  # Complete the rest
        
        # Print progress every 10 items
        if (i + 1) % 10 == 0:
            print(tracker.format_summary())
    
    print("\n" + tracker.format_summary())
    print(f"\nFinal stats: {tracker.get_stats()}")


def demo_logging():
    """Demonstrate logging functionality."""
    print("\n\n=== Logging Demo ===\n")
    
    # Setup logging with console output
    setup_logging(verbose=True)
    logger = get_logger(__name__)
    
    logger.debug("This is a debug message")
    logger.info("Starting download process...")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    
    # Simulate some work with logging
    logger.info("Processing 10 items...")
    for i in range(10):
        time.sleep(0.1)
        logger.debug(f"Processed item {i + 1}/10")
    
    logger.info("Download complete!")


def demo_combined():
    """Demonstrate progress tracking with logging."""
    print("\n\n=== Combined Progress + Logging ===\n")
    
    # Setup logging
    setup_logging(verbose=False)  # Non-verbose for cleaner output
    logger = get_logger(__name__)
    
    # Create tracker
    tracker = ProgressTracker(total=30)
    tracker.start()
    
    logger.info("Starting batch download...")
    
    for i in range(30):
        time.sleep(0.08)
        
        if i % 5 == 0:
            logger.info(f"Checkpoint: {tracker.format_summary()}")
        
        # Randomly complete, skip, or fail
        if i % 10 == 0 and i > 0:
            tracker.fail()
            logger.warning(f"Failed to download item {i}")
        elif i % 7 == 0:
            tracker.skip()
            logger.debug(f"Skipped item {i}")
        else:
            tracker.complete()
    
    logger.info(f"Batch complete: {tracker.format_summary()}")
    
    stats = tracker.get_stats()
    logger.info(f"Summary: {stats.completed} completed, {stats.failed} failed, {stats.skipped} skipped")


def demo_file_logging():
    """Demonstrate logging to file."""
    print("\n\n=== File Logging Demo ===\n")
    
    log_file = Path("demo_log.txt")
    setup_logging(verbose=True, log_file=log_file)
    logger = get_logger(__name__)
    
    logger.info("This message will be logged to both console and file")
    logger.debug("Debug information for troubleshooting")
    logger.warning("Warning: This is a test warning")
    
    print(f"\nLog file created at: {log_file.absolute()}")
    print(f"Log file size: {log_file.stat().st_size} bytes")


if __name__ == "__main__":
    print("Progress Tracking and Logging Demo")
    print("=" * 50)
    
    try:
        demo_basic_progress()
        demo_logging()
        demo_combined()
        demo_file_logging()
        
        print("\n" + "=" * 50)
        print("Demo complete!")
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
