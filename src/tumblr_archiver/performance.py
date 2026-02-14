"""Performance monitoring and timing utilities."""

import logging
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Generator, Optional

logger = logging.getLogger(__name__)


@dataclass
class TimingStats:
    """Statistics for a timed operation.
    
    Attributes:
        count: Number of times operation was executed
        total_time: Total time spent in seconds
        min_time: Minimum execution time
        max_time: Maximum execution time
        avg_time: Average execution time
    """
    
    count: int
    total_time: float
    min_time: float
    max_time: float
    
    @property
    def avg_time(self) -> float:
        """Calculate average time per operation.
        
        Returns:
            Average time in seconds
        """
        return self.total_time / self.count if self.count > 0 else 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.
        
        Returns:
            Dictionary representation of stats
        """
        return {
            "count": self.count,
            "total_time": self.total_time,
            "min_time": self.min_time,
            "max_time": self.max_time,
            "avg_time": self.avg_time,
        }


class PerformanceMonitor:
    """Tracks operation timings and performance metrics.
    
    Features:
    - Start/stop timer for operations
    - Context manager for automatic timing
    - Aggregate statistics (count, total, min, max, avg)
    - Per-operation tracking
    - Lightweight overhead
    
    Example:
        ```python
        monitor = PerformanceMonitor()
        
        # Manual timing
        monitor.start_timer("download")
        # ... do work ...
        monitor.end_timer("download")
        
        # Context manager (automatic timing)
        with monitor.timer("parse"):
            # ... do work ...
            pass
        
        # Get statistics
        stats = monitor.get_stats()
        print(f"Download avg: {stats['download']['avg_time']:.3f}s")
        
        # Get summary
        summary = monitor.get_summary()
        print(summary)
        ```
    """
    
    def __init__(self):
        """Initialize performance monitor."""
        self._timings: dict[str, list[float]] = defaultdict(list)
        self._active_timers: dict[str, float] = {}
        logger.debug("Initialized PerformanceMonitor")
    
    def start_timer(self, operation: str) -> None:
        """Start timing an operation.
        
        Args:
            operation: Name of the operation to time
            
        Raises:
            ValueError: If timer is already active for this operation
        """
        if operation in self._active_timers:
            raise ValueError(f"Timer already active for operation: {operation}")
        
        self._active_timers[operation] = time.perf_counter()
        logger.debug(f"Started timer: {operation}")
    
    def end_timer(self, operation: str) -> float:
        """Stop timing an operation and record duration.
        
        Args:
            operation: Name of the operation to stop timing
            
        Returns:
            Duration in seconds
            
        Raises:
            ValueError: If no active timer exists for this operation
        """
        if operation not in self._active_timers:
            raise ValueError(f"No active timer for operation: {operation}")
        
        start_time = self._active_timers.pop(operation)
        duration = time.perf_counter() - start_time
        
        self._timings[operation].append(duration)
        logger.debug(f"Ended timer: {operation} ({duration:.3f}s)")
        
        return duration
    
    @contextmanager
    def timer(self, operation: str) -> Generator[None, None, None]:
        """Context manager for automatic timing of operations.
        
        Args:
            operation: Name of the operation to time
            
        Yields:
            None
            
        Example:
            ```python
            with monitor.timer("database_query"):
                result = db.query("SELECT * FROM users")
            ```
        """
        self.start_timer(operation)
        try:
            yield
        finally:
            self.end_timer(operation)
    
    def record_timing(self, operation: str, duration: float) -> None:
        """Manually record a timing without using timers.
        
        Args:
            operation: Name of the operation
            duration: Duration in seconds
        """
        self._timings[operation].append(duration)
        logger.debug(f"Recorded timing: {operation} ({duration:.3f}s)")
    
    def get_stats(self, operation: Optional[str] = None) -> dict[str, TimingStats]:
        """Get timing statistics for operations.
        
        Args:
            operation: Specific operation to get stats for (None = all)
            
        Returns:
            Dictionary mapping operation names to TimingStats
        """
        if operation is not None:
            # Get stats for specific operation
            if operation not in self._timings:
                return {}
            
            timings = self._timings[operation]
            return {
                operation: TimingStats(
                    count=len(timings),
                    total_time=sum(timings),
                    min_time=min(timings),
                    max_time=max(timings),
                )
            }
        
        # Get stats for all operations
        stats = {}
        for op, timings in self._timings.items():
            if timings:  # Only include operations with recorded timings
                stats[op] = TimingStats(
                    count=len(timings),
                    total_time=sum(timings),
                    min_time=min(timings),
                    max_time=max(timings),
                )
        
        return stats
    
    def get_summary(self, sort_by: str = "total_time") -> str:
        """Get formatted summary of all timing statistics.
        
        Args:
            sort_by: Field to sort by ('total_time', 'count', 'avg_time')
            
        Returns:
            Formatted string with timing table
        """
        stats = self.get_stats()
        
        if not stats:
            return "No timing data recorded."
        
        # Sort operations
        if sort_by == "total_time":
            sorted_ops = sorted(
                stats.items(),
                key=lambda x: x[1].total_time,
                reverse=True
            )
        elif sort_by == "count":
            sorted_ops = sorted(
                stats.items(),
                key=lambda x: x[1].count,
                reverse=True
            )
        elif sort_by == "avg_time":
            sorted_ops = sorted(
                stats.items(),
                key=lambda x: x[1].avg_time,
                reverse=True
            )
        else:
            sorted_ops = list(stats.items())
        
        # Build table
        lines = [
            "Performance Summary",
            "=" * 80,
            f"{'Operation':<30} {'Count':>8} {'Total':>10} {'Avg':>10} {'Min':>10} {'Max':>10}",
            "-" * 80,
        ]
        
        for operation, timing_stats in sorted_ops:
            lines.append(
                f"{operation:<30} "
                f"{timing_stats.count:>8} "
                f"{timing_stats.total_time:>10.3f}s "
                f"{timing_stats.avg_time:>10.3f}s "
                f"{timing_stats.min_time:>10.3f}s "
                f"{timing_stats.max_time:>10.3f}s"
            )
        
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def reset(self, operation: Optional[str] = None) -> None:
        """Reset timing data.
        
        Args:
            operation: Specific operation to reset (None = all)
        """
        if operation is not None:
            if operation in self._timings:
                del self._timings[operation]
                logger.debug(f"Reset timings for: {operation}")
        else:
            self._timings.clear()
            self._active_timers.clear()
            logger.debug("Reset all timings")
    
    def get_active_timers(self) -> list[str]:
        """Get list of currently active timers.
        
        Returns:
            List of operation names with active timers
        """
        return list(self._active_timers.keys())
    
    def has_active_timer(self, operation: str) -> bool:
        """Check if operation has an active timer.
        
        Args:
            operation: Operation name to check
            
        Returns:
            True if timer is active
        """
        return operation in self._active_timers
    
    def get_operation_count(self, operation: str) -> int:
        """Get number of times operation has been timed.
        
        Args:
            operation: Operation name
            
        Returns:
            Number of recorded timings
        """
        return len(self._timings.get(operation, []))
    
    def get_total_time(self, operation: str) -> float:
        """Get total time spent on operation.
        
        Args:
            operation: Operation name
            
        Returns:
            Total time in seconds (0 if operation not found)
        """
        timings = self._timings.get(operation, [])
        return sum(timings)
    
    def export_stats(self) -> dict[str, dict[str, Any]]:
        """Export all statistics as a dictionary.
        
        Returns:
            Dictionary mapping operation names to their stats
        """
        stats = self.get_stats()
        return {
            operation: timing_stats.to_dict()
            for operation, timing_stats in stats.items()
        }
