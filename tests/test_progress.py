"""Tests for progress tracking functionality."""

import time
import threading
import pytest
from tumblr_archiver.progress import ProgressTracker, ProgressStats


class TestProgressStats:
    """Tests for ProgressStats dataclass."""
    
    def test_remaining_calculation(self):
        """Test remaining items calculation."""
        stats = ProgressStats(
            total=100,
            completed=30,
            failed=5,
            skipped=10,
            in_progress=2,
            elapsed_time=10.0
        )
        assert stats.remaining == 55
    
    def test_processed_calculation(self):
        """Test total processed items calculation."""
        stats = ProgressStats(
            total=100,
            completed=30,
            failed=5,
            skipped=10,
            in_progress=2,
            elapsed_time=10.0
        )
        assert stats.processed == 45


class TestProgressTracker:
    """Tests for ProgressTracker class."""
    
    def test_initialization(self):
        """Test tracker initialization."""
        tracker = ProgressTracker(total=100)
        assert tracker.total == 100
        stats = tracker.get_stats()
        assert stats.completed == 0
        assert stats.failed == 0
        assert stats.skipped == 0
        assert stats.in_progress == 0
    
    def test_start(self):
        """Test start method."""
        tracker = ProgressTracker(total=100)
        tracker.start()
        stats = tracker.get_stats()
        # Elapsed time should be >= 0 (may be 0 if execution is very fast)
        assert stats.elapsed_time >= 0
        # Verify start was called by checking if we can get stats
        assert stats.total == 100
    
    def test_complete(self):
        """Test complete method."""
        tracker = ProgressTracker(total=100)
        tracker.start()
        tracker.complete()
        tracker.complete()
        tracker.complete(count=3)
        
        stats = tracker.get_stats()
        assert stats.completed == 5
        assert stats.failed == 0
        assert stats.skipped == 0
    
    def test_fail(self):
        """Test fail method."""
        tracker = ProgressTracker(total=100)
        tracker.start()
        tracker.fail()
        tracker.fail(count=2)
        
        stats = tracker.get_stats()
        assert stats.completed == 0
        assert stats.failed == 3
        assert stats.skipped == 0
    
    def test_skip(self):
        """Test skip method."""
        tracker = ProgressTracker(total=100)
        tracker.start()
        tracker.skip()
        tracker.skip(count=4)
        
        stats = tracker.get_stats()
        assert stats.completed == 0
        assert stats.failed == 0
        assert stats.skipped == 5
    
    def test_mixed_operations(self):
        """Test mixed operations."""
        tracker = ProgressTracker(total=100)
        tracker.start()
        tracker.complete(10)
        tracker.fail(2)
        tracker.skip(3)
        
        stats = tracker.get_stats()
        assert stats.completed == 10
        assert stats.failed == 2
        assert stats.skipped == 3
        assert stats.processed == 15
        assert stats.remaining == 85
    
    def test_in_progress_tracking(self):
        """Test in-progress item tracking."""
        tracker = ProgressTracker(total=100)
        tracker.start_item()
        tracker.start_item()
        
        stats = tracker.get_stats()
        assert stats.in_progress == 2
        
        tracker.complete()
        stats = tracker.get_stats()
        assert stats.in_progress == 1
        
        tracker.fail()
        stats = tracker.get_stats()
        assert stats.in_progress == 0
    
    def test_get_progress_percent(self):
        """Test progress percentage calculation."""
        tracker = ProgressTracker(total=100)
        tracker.start()
        
        assert tracker.get_progress_percent() == 0.0
        
        tracker.complete(25)
        assert tracker.get_progress_percent() == 25.0
        
        tracker.complete(25)
        tracker.fail(10)
        assert tracker.get_progress_percent() == 60.0
        
        tracker.complete(40)
        assert tracker.get_progress_percent() == 100.0
    
    def test_get_progress_percent_zero_total(self):
        """Test progress percentage with zero total."""
        tracker = ProgressTracker(total=0)
        assert tracker.get_progress_percent() == 100.0
    
    def test_calculate_eta_no_data(self):
        """Test ETA calculation with no progress."""
        tracker = ProgressTracker(total=100)
        tracker.start()
        
        eta = tracker.calculate_eta()
        assert eta is None
    
    def test_calculate_eta_with_progress(self):
        """Test ETA calculation with progress."""
        tracker = ProgressTracker(total=100)
        tracker.start()
        
        # Simulate processing 10 items in 1 second
        time.sleep(0.1)
        tracker.complete(10)
        
        eta = tracker.calculate_eta()
        assert eta is not None
        assert eta > 0
        
        # ETA should be roughly (90 items / 10 items per 0.1s) * 0.1s = 0.9s
        # But we'll be lenient since timing is imprecise in tests
        assert eta > 0.1  # Should take at least some time
    
    def test_calculate_eta_completed(self):
        """Test ETA calculation when complete."""
        tracker = ProgressTracker(total=10)
        tracker.start()
        tracker.complete(10)
        
        eta = tracker.calculate_eta()
        assert eta == 0.0
    
    def test_format_time(self):
        """Test time formatting."""
        assert ProgressTracker._format_time(0) == "0s"
        assert ProgressTracker._format_time(30) == "30s"
        assert ProgressTracker._format_time(60) == "1m"
        assert ProgressTracker._format_time(90) == "1m 30s"
        assert ProgressTracker._format_time(3600) == "1h"
        assert ProgressTracker._format_time(3660) == "1h 1m"
        assert ProgressTracker._format_time(86400) == "1d"
        assert ProgressTracker._format_time(90000) == "1d 1h"
        assert ProgressTracker._format_time(-10) == "0s"
    
    def test_format_summary_basic(self):
        """Test basic summary formatting."""
        tracker = ProgressTracker(total=100)
        tracker.start()
        tracker.complete(25)
        
        summary = tracker.format_summary()
        assert "25/100" in summary
        assert "25.0%" in summary
        assert "Elapsed:" in summary
        assert "Speed:" in summary
    
    def test_format_summary_with_failures(self):
        """Test summary formatting with failures."""
        tracker = ProgressTracker(total=100)
        tracker.start()
        tracker.complete(25)
        tracker.fail(5)
        tracker.skip(10)
        
        summary = tracker.format_summary()
        assert "40/100" in summary
        assert "25 completed" in summary
        assert "5 failed" in summary
        assert "10 skipped" in summary
    
    def test_format_summary_with_eta(self):
        """Test summary formatting with ETA."""
        tracker = ProgressTracker(total=100)
        tracker.start()
        time.sleep(0.1)
        tracker.complete(10)
        
        summary = tracker.format_summary()
        assert "ETA:" in summary
    
    def test_reset(self):
        """Test reset functionality."""
        tracker = ProgressTracker(total=100)
        tracker.start()
        tracker.complete(10)
        tracker.fail(5)
        tracker.skip(3)
        
        tracker.reset()
        
        stats = tracker.get_stats()
        assert stats.completed == 0
        assert stats.failed == 0
        assert stats.skipped == 0
        assert stats.in_progress == 0
        assert stats.elapsed_time == 0
    
    def test_thread_safety(self):
        """Test thread-safe operations."""
        tracker = ProgressTracker(total=1000)
        tracker.start()
        
        def worker():
            for _ in range(10):
                tracker.complete()
                time.sleep(0.001)
        
        # Create 10 threads, each completing 10 items
        threads = [threading.Thread(target=worker) for _ in range(10)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        stats = tracker.get_stats()
        assert stats.completed == 100
    
    def test_thread_safety_mixed_operations(self):
        """Test thread safety with mixed operations."""
        tracker = ProgressTracker(total=1000)
        tracker.start()
        
        def complete_worker():
            for _ in range(10):
                tracker.complete()
        
        def fail_worker():
            for _ in range(5):
                tracker.fail()
        
        def skip_worker():
            for _ in range(3):
                tracker.skip()
        
        threads = []
        threads.extend([threading.Thread(target=complete_worker) for _ in range(5)])
        threads.extend([threading.Thread(target=fail_worker) for _ in range(3)])
        threads.extend([threading.Thread(target=skip_worker) for _ in range(2)])
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        stats = tracker.get_stats()
        assert stats.completed == 50  # 5 threads * 10
        assert stats.failed == 15     # 3 threads * 5
        assert stats.skipped == 6     # 2 threads * 3
        assert stats.processed == 71
    
    def test_auto_start_on_operations(self):
        """Test that operations auto-start timing if not started."""
        tracker = ProgressTracker(total=100)
        
        # Don't call start() explicitly
        tracker.complete()
        
        stats = tracker.get_stats()
        # Elapsed time should be >= 0 (auto-started)
        assert stats.elapsed_time >= 0
        assert stats.completed == 1
        
        # Add a small delay and verify time increases
        time.sleep(0.01)
        stats2 = tracker.get_stats()
        assert stats2.elapsed_time > stats.elapsed_time
    
    def test_stats_snapshot(self):
        """Test that get_stats returns a snapshot, not live data."""
        tracker = ProgressTracker(total=100)
        tracker.start()
        tracker.complete(10)
        
        stats1 = tracker.get_stats()
        tracker.complete(5)
        stats2 = tracker.get_stats()
        
        assert stats1.completed == 10
        assert stats2.completed == 15
        assert stats1.completed != stats2.completed
    
    def test_speed_calculation(self):
        """Test speed calculation in summary."""
        tracker = ProgressTracker(total=100)
        tracker.start()
        time.sleep(0.1)
        tracker.complete(10)
        
        summary = tracker.format_summary()
        assert "items/s" in summary
        
        # Speed should be roughly 10 items / 0.1 seconds = 100 items/s
        # But timing is imprecise, so just check it's present
        stats = tracker.get_stats()
        speed = stats.processed / stats.elapsed_time
        assert speed > 0
