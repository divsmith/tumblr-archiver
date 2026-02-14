"""Progress tracking for download operations."""

import threading
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProgressStats:
    """Statistics about download progress."""

    total: int
    completed: int
    failed: int
    skipped: int
    in_progress: int
    elapsed_time: float
    
    @property
    def remaining(self) -> int:
        """Calculate remaining items."""
        return self.total - (self.completed + self.failed + self.skipped)
    
    @property
    def processed(self) -> int:
        """Total processed items (completed + failed + skipped)."""
        return self.completed + self.failed + self.skipped


class ProgressTracker:
    """Thread-safe progress tracker for download operations.
    
    Tracks completed, failed, and skipped items with ETA calculation
    and human-readable progress reporting.
    
    Example:
        tracker = ProgressTracker(total=100)
        tracker.start()
        tracker.complete()
        tracker.complete()
        tracker.fail()
        stats = tracker.get_stats()
        print(tracker.format_summary())
    """
    
    def __init__(self, total: int):
        """Initialize progress tracker.
        
        Args:
            total: Total number of items to process
        """
        self.total = total
        self._completed = 0
        self._failed = 0
        self._skipped = 0
        self._in_progress = 0
        self._start_time: Optional[float] = None
        self._lock = threading.Lock()
    
    def start(self) -> None:
        """Mark the start of progress tracking."""
        with self._lock:
            if self._start_time is None:
                self._start_time = time.time()
    
    def start_item(self) -> None:
        """Mark an item as started."""
        with self._lock:
            if self._start_time is None:
                self._start_time = time.time()
            self._in_progress += 1
    
    def complete(self, count: int = 1) -> None:
        """Mark items as completed.
        
        Args:
            count: Number of items completed (default: 1)
        """
        with self._lock:
            if self._start_time is None:
                self._start_time = time.time()
            self._completed += count
            if self._in_progress > 0:
                self._in_progress -= min(count, self._in_progress)
    
    def fail(self, count: int = 1) -> None:
        """Mark items as failed.
        
        Args:
            count: Number of items failed (default: 1)
        """
        with self._lock:
            if self._start_time is None:
                self._start_time = time.time()
            self._failed += count
            if self._in_progress > 0:
                self._in_progress -= min(count, self._in_progress)
    
    def skip(self, count: int = 1) -> None:
        """Mark items as skipped.
        
        Args:
            count: Number of items skipped (default: 1)
        """
        with self._lock:
            if self._start_time is None:
                self._start_time = time.time()
            self._skipped += count
            if self._in_progress > 0:
                self._in_progress -= min(count, self._in_progress)
    
    def get_stats(self) -> ProgressStats:
        """Get current progress statistics.
        
        Returns:
            ProgressStats object with current state
        """
        with self._lock:
            elapsed = 0.0
            if self._start_time is not None:
                elapsed = time.time() - self._start_time
            
            return ProgressStats(
                total=self.total,
                completed=self._completed,
                failed=self._failed,
                skipped=self._skipped,
                in_progress=self._in_progress,
                elapsed_time=elapsed
            )
    
    def get_progress_percent(self) -> float:
        """Calculate progress percentage.
        
        Returns:
            Progress as percentage (0-100)
        """
        if self.total == 0:
            return 100.0
        
        stats = self.get_stats()
        return (stats.processed / self.total) * 100.0
    
    def calculate_eta(self) -> Optional[float]:
        """Calculate estimated time remaining in seconds.
        
        Returns:
            Estimated seconds remaining, or None if not enough data
        """
        stats = self.get_stats()
        
        # If nothing remaining, ETA is 0
        if stats.remaining <= 0:
            return 0.0
        
        # If nothing processed yet or no time elapsed, can't calculate
        if stats.processed == 0 or stats.elapsed_time == 0:
            return None
        
        # Calculate average speed (items per second)
        speed = stats.processed / stats.elapsed_time
        
        # Calculate ETA based on remaining items
        eta = stats.remaining / speed
        return eta
    
    def format_summary(self) -> str:
        """Format a human-readable progress summary.
        
        Returns:
            Formatted summary string
        """
        stats = self.get_stats()
        percent = self.get_progress_percent()
        
        parts = [
            f"Progress: {stats.processed}/{self.total} ({percent:.1f}%)"
        ]
        
        # Add breakdown if there are failures or skips
        if stats.failed > 0 or stats.skipped > 0:
            breakdown = []
            if stats.completed > 0:
                breakdown.append(f"{stats.completed} completed")
            if stats.failed > 0:
                breakdown.append(f"{stats.failed} failed")
            if stats.skipped > 0:
                breakdown.append(f"{stats.skipped} skipped")
            parts.append(f" ({', '.join(breakdown)})")
        
        # Add elapsed time
        elapsed_str = self._format_time(stats.elapsed_time)
        parts.append(f" | Elapsed: {elapsed_str}")
        
        # Add ETA if available
        eta_seconds = self.calculate_eta()
        if eta_seconds is not None and stats.remaining > 0:
            eta_str = self._format_time(eta_seconds)
            parts.append(f" | ETA: {eta_str}")
        
        # Add speed if available
        if stats.elapsed_time > 0 and stats.processed > 0:
            speed = stats.processed / stats.elapsed_time
            parts.append(f" | Speed: {speed:.2f} items/s")
        
        return "".join(parts)
    
    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds into human-readable time string.
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Formatted time string (e.g., "5m 30s", "2h 15m")
        """
        if seconds < 0:
            return "0s"
        
        seconds = int(seconds)
        
        if seconds < 60:
            return f"{seconds}s"
        
        minutes = seconds // 60
        seconds = seconds % 60
        
        if minutes < 60:
            if seconds > 0:
                return f"{minutes}m {seconds}s"
            return f"{minutes}m"
        
        hours = minutes // 60
        minutes = minutes % 60
        
        if hours < 24:
            if minutes > 0:
                return f"{hours}h {minutes}m"
            return f"{hours}h"
        
        days = hours // 24
        hours = hours % 24
        
        if hours > 0:
            return f"{days}d {hours}h"
        return f"{days}d"
    
    def reset(self) -> None:
        """Reset all counters and start time."""
        with self._lock:
            self._completed = 0
            self._failed = 0
            self._skipped = 0
            self._in_progress = 0
            self._start_time = None
