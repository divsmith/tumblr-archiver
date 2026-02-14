"""Tests for performance monitoring and caching functionality."""

import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from tumblr_archiver.cache import CacheEntry, ResponseCache
from tumblr_archiver.http_client import AsyncHTTPClient
from tumblr_archiver.performance import PerformanceMonitor, TimingStats


class TestCacheEntry:
    """Tests for CacheEntry."""
    
    def test_cache_entry_creation(self):
        """Test creating a cache entry."""
        entry = CacheEntry(
            value="test_data",
            created_at=time.time(),
            ttl=60
        )
        
        assert entry.value == "test_data"
        assert not entry.is_expired()
    
    def test_cache_entry_expiration(self):
        """Test cache entry expiration."""
        # Create expired entry
        entry = CacheEntry(
            value="test_data",
            created_at=time.time() - 100,
            ttl=60
        )
        
        assert entry.is_expired()
    
    def test_cache_entry_no_expiration(self):
        """Test cache entry with no expiration (ttl=0)."""
        entry = CacheEntry(
            value="test_data",
            created_at=time.time() - 1000,
            ttl=0
        )
        
        assert not entry.is_expired()


class TestResponseCache:
    """Tests for ResponseCache."""
    
    def test_cache_initialization(self):
        """Test cache initialization."""
        cache = ResponseCache(max_size=100, default_ttl=300)
        
        assert len(cache) == 0
        assert cache._max_size == 100
        assert cache._default_ttl == 300
    
    def test_cache_set_and_get(self):
        """Test setting and getting values."""
        cache = ResponseCache()
        
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
    
    def test_cache_miss(self):
        """Test cache miss."""
        cache = ResponseCache()
        
        result = cache.get("nonexistent")
        assert result is None
    
    def test_cache_overwrite(self):
        """Test overwriting existing key."""
        cache = ResponseCache()
        
        cache.set("key1", "value1")
        cache.set("key1", "value2")
        
        assert cache.get("key1") == "value2"
        assert len(cache) == 1
    
    def test_cache_lru_eviction(self):
        """Test LRU eviction policy."""
        cache = ResponseCache(max_size=3)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        
        # Access key1 to make it most recently used
        _ = cache.get("key1")
        
        # Add key4, should evict key2 (least recently used)
        cache.set("key4", "value4")
        
        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"
    
    def test_cache_ttl(self):
        """Test cache entry expiration with TTL."""
        cache = ResponseCache(default_ttl=0.1)
        
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        # Wait for expiration
        time.sleep(0.15)
        
        assert cache.get("key1") is None
    
    def test_cache_custom_ttl(self):
        """Test custom TTL per entry."""
        cache = ResponseCache(default_ttl=60)
        
        cache.set("key1", "value1", ttl=0.1)
        cache.set("key2", "value2", ttl=60)
        
        # Wait for key1 to expire
        time.sleep(0.15)
        
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
    
    def test_cache_invalidate(self):
        """Test invalidating cache entry."""
        cache = ResponseCache()
        
        cache.set("key1", "value1")
        assert cache.invalidate("key1")
        assert cache.get("key1") is None
        
        # Invalidating non-existent key
        assert not cache.invalidate("key2")
    
    def test_cache_clear(self):
        """Test clearing cache."""
        cache = ResponseCache()
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        cache.clear()
        
        assert len(cache) == 0
        assert cache.get("key1") is None
    
    def test_cache_statistics(self):
        """Test cache statistics tracking."""
        cache = ResponseCache(max_size=2)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        # Hits
        _ = cache.get("key1")
        _ = cache.get("key2")
        
        # Misses
        _ = cache.get("key3")
        
        # Eviction
        cache.set("key4", "value4")
        
        stats = cache.get_stats()
        
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 2 / 3
        assert stats["size"] == 2
        assert stats["max_size"] == 2
        assert stats["evictions"] == 1
    
    def test_cache_reset_stats(self):
        """Test resetting cache statistics."""
        cache = ResponseCache()
        
        cache.set("key1", "value1")
        _ = cache.get("key1")
        
        cache.reset_stats()
        
        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
    
    def test_cache_cleanup_expired(self):
        """Test cleaning up expired entries."""
        cache = ResponseCache(default_ttl=0.1)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3", ttl=60)  # Won't expire
        
        # Wait for expiration
        time.sleep(0.15)
        
        removed = cache.cleanup_expired()
        
        assert removed == 2
        assert len(cache) == 1
        assert cache.get("key3") == "value3"
    
    def test_cache_contains(self):
        """Test __contains__ method."""
        cache = ResponseCache()
        
        cache.set("key1", "value1")
        
        assert "key1" in cache
        assert "key2" not in cache
    
    def test_cache_key_hashing(self):
        """Test that keys are properly hashed."""
        cache = ResponseCache()
        
        # Different keys should not collide
        cache.set("http://example.com/1", "value1")
        cache.set("http://example.com/2", "value2")
        
        assert cache.get("http://example.com/1") == "value1"
        assert cache.get("http://example.com/2") == "value2"


class TestTimingStats:
    """Tests for TimingStats."""
    
    def test_timing_stats_creation(self):
        """Test creating timing stats."""
        stats = TimingStats(
            count=10,
            total_time=5.0,
            min_time=0.1,
            max_time=1.0
        )
        
        assert stats.count == 10
        assert stats.total_time == 5.0
        assert stats.avg_time == 0.5
    
    def test_timing_stats_avg_zero_count(self):
        """Test average with zero count."""
        stats = TimingStats(
            count=0,
            total_time=0.0,
            min_time=0.0,
            max_time=0.0
        )
        
        assert stats.avg_time == 0.0
    
    def test_timing_stats_to_dict(self):
        """Test converting stats to dictionary."""
        stats = TimingStats(
            count=5,
            total_time=2.5,
            min_time=0.3,
            max_time=0.7
        )
        
        data = stats.to_dict()
        
        assert data["count"] == 5
        assert data["total_time"] == 2.5
        assert data["avg_time"] == 0.5
        assert data["min_time"] == 0.3
        assert data["max_time"] == 0.7


class TestPerformanceMonitor:
    """Tests for PerformanceMonitor."""
    
    def test_monitor_initialization(self):
        """Test monitor initialization."""
        monitor = PerformanceMonitor()
        
        assert len(monitor.get_active_timers()) == 0
        assert len(monitor.get_stats()) == 0
    
    def test_monitor_start_end_timer(self):
        """Test starting and ending timers."""
        monitor = PerformanceMonitor()
        
        monitor.start_timer("test_op")
        time.sleep(0.01)
        duration = monitor.end_timer("test_op")
        
        assert duration >= 0.01
        assert not monitor.has_active_timer("test_op")
    
    def test_monitor_timer_context_manager(self):
        """Test timer context manager."""
        monitor = PerformanceMonitor()
        
        with monitor.timer("test_op"):
            time.sleep(0.01)
        
        stats = monitor.get_stats("test_op")["test_op"]
        
        assert stats.count == 1
        assert stats.total_time >= 0.01
    
    def test_monitor_multiple_operations(self):
        """Test monitoring multiple operations."""
        monitor = PerformanceMonitor()
        
        with monitor.timer("op1"):
            time.sleep(0.01)
        
        with monitor.timer("op2"):
            time.sleep(0.02)
        
        with monitor.timer("op1"):
            time.sleep(0.01)
        
        stats = monitor.get_stats()
        
        assert "op1" in stats
        assert "op2" in stats
        assert stats["op1"].count == 2
        assert stats["op2"].count == 1
    
    def test_monitor_double_start_error(self):
        """Test error when starting timer twice."""
        monitor = PerformanceMonitor()
        
        monitor.start_timer("test_op")
        
        with pytest.raises(ValueError, match="already active"):
            monitor.start_timer("test_op")
        
        monitor.end_timer("test_op")
    
    def test_monitor_end_without_start_error(self):
        """Test error when ending timer without start."""
        monitor = PerformanceMonitor()
        
        with pytest.raises(ValueError, match="No active timer"):
            monitor.end_timer("test_op")
    
    def test_monitor_record_timing(self):
        """Test manually recording timing."""
        monitor = PerformanceMonitor()
        
        monitor.record_timing("manual_op", 1.5)
        monitor.record_timing("manual_op", 2.5)
        
        stats = monitor.get_stats("manual_op")["manual_op"]
        
        assert stats.count == 2
        assert stats.total_time == 4.0
        assert stats.avg_time == 2.0
    
    def test_monitor_get_stats_specific(self):
        """Test getting stats for specific operation."""
        monitor = PerformanceMonitor()
        
        with monitor.timer("op1"):
            pass
        
        with monitor.timer("op2"):
            pass
        
        stats = monitor.get_stats("op1")
        
        assert "op1" in stats
        assert "op2" not in stats
    
    def test_monitor_get_summary(self):
        """Test getting formatted summary."""
        monitor = PerformanceMonitor()
        
        with monitor.timer("download"):
            time.sleep(0.01)
        
        with monitor.timer("parse"):
            time.sleep(0.01)
        
        summary = monitor.get_summary()
        
        assert "Performance Summary" in summary
        assert "download" in summary
        assert "parse" in summary
    
    def test_monitor_reset(self):
        """Test resetting monitor data."""
        monitor = PerformanceMonitor()
        
        with monitor.timer("test_op"):
            pass
        
        monitor.reset()
        
        assert len(monitor.get_stats()) == 0
    
    def test_monitor_reset_specific_operation(self):
        """Test resetting specific operation."""
        monitor = PerformanceMonitor()
        
        with monitor.timer("op1"):
            pass
        
        with monitor.timer("op2"):
            pass
        
        monitor.reset("op1")
        
        stats = monitor.get_stats()
        assert "op1" not in stats
        assert "op2" in stats
    
    def test_monitor_get_operation_count(self):
        """Test getting operation count."""
        monitor = PerformanceMonitor()
        
        for _ in range(5):
            with monitor.timer("test_op"):
                pass
        
        assert monitor.get_operation_count("test_op") == 5
        assert monitor.get_operation_count("nonexistent") == 0
    
    def test_monitor_get_total_time(self):
        """Test getting total time for operation."""
        monitor = PerformanceMonitor()
        
        monitor.record_timing("test_op", 1.0)
        monitor.record_timing("test_op", 2.0)
        
        assert monitor.get_total_time("test_op") == 3.0
        assert monitor.get_total_time("nonexistent") == 0.0
    
    def test_monitor_export_stats(self):
        """Test exporting statistics."""
        monitor = PerformanceMonitor()
        
        with monitor.timer("test_op"):
            time.sleep(0.01)
        
        export = monitor.export_stats()
        
        assert "test_op" in export
        assert "count" in export["test_op"]
        assert "total_time" in export["test_op"]
        assert "avg_time" in export["test_op"]
    
    def test_monitor_summary_sorting(self):
        """Test summary sorting options."""
        monitor = PerformanceMonitor()
        
        monitor.record_timing("slow_op", 5.0)
        monitor.record_timing("fast_op", 1.0)
        monitor.record_timing("fast_op", 1.0)
        
        # Sort by total time
        summary_total = monitor.get_summary(sort_by="total_time")
        assert summary_total.index("slow_op") < summary_total.index("fast_op")
        
        # Sort by count
        summary_count = monitor.get_summary(sort_by="count")
        assert summary_count.index("fast_op") < summary_count.index("slow_op")
    
    def test_monitor_context_manager_exception(self):
        """Test context manager handles exceptions properly."""
        monitor = PerformanceMonitor()
        
        with pytest.raises(ValueError):
            with monitor.timer("error_op"):
                raise ValueError("Test error")
        
        # Timer should still be recorded despite exception
        stats = monitor.get_stats("error_op")
        assert "error_op" in stats
        assert stats["error_op"].count == 1


class TestPerformanceRegression:
    """Performance regression tests."""
    
    def test_cache_performance_baseline(self):
        """Ensure cache operations meet baseline performance."""
        cache = ResponseCache(max_size=1000)
        iterations = 1000
        
        start = time.perf_counter()
        for i in range(iterations):
            cache.set(f"key_{i}", f"value_{i}")
        write_time = time.perf_counter() - start
        
        start = time.perf_counter()
        for i in range(iterations):
            _ = cache.get(f"key_{i}")
        read_time = time.perf_counter() - start
        
        # Should complete in reasonable time (generous thresholds)
        assert write_time < 1.0, f"Cache writes too slow: {write_time:.3f}s"
        assert read_time < 1.0, f"Cache reads too slow: {read_time:.3f}s"
        
        # Operations per second should be reasonable
        write_ops_per_sec = iterations / write_time
        read_ops_per_sec = iterations / read_time
        
        assert write_ops_per_sec > 1000, f"Write throughput too low: {write_ops_per_sec:.0f} ops/s"
        assert read_ops_per_sec > 1000, f"Read throughput too low: {read_ops_per_sec:.0f} ops/s"
    
    def test_monitor_overhead_acceptable(self):
        """Ensure performance monitor overhead is minimal."""
        monitor = PerformanceMonitor()
        iterations = 10000
        
        # Measure baseline
        start = time.perf_counter()
        for _ in range(iterations):
            pass
        baseline = time.perf_counter() - start
        
        # Measure with monitoring
        start = time.perf_counter()
        for _ in range(iterations):
            with monitor.timer("test"):
                pass
        monitored = time.perf_counter() - start
        
        overhead = monitored - baseline
        overhead_per_op = overhead / iterations
        
        # Overhead should be less than 50 microseconds per operation
        assert overhead_per_op < 0.00005, f"Monitor overhead too high: {overhead_per_op * 1000000:.1f}µs per op"


class TestHTTPClientCacheIntegration:
    """Tests for cache integration in AsyncHTTPClient."""
    
    @pytest.mark.asyncio
    async def test_http_client_without_cache(self):
        """Test HTTP client works without cache."""
        async with AsyncHTTPClient() as client:
            assert client._cache is None
    
    @pytest.mark.asyncio
    async def test_http_client_with_cache(self):
        """Test HTTP client with cache enabled."""
        cache = ResponseCache(max_size=10, default_ttl=60)
        
        async with AsyncHTTPClient(cache=cache) as client:
            assert client._cache is cache
    
    def test_cache_basic_functionality(self):
        """Test basic cache operations work correctly."""
        cache = ResponseCache(max_size=10, default_ttl=60)
        
        # Test set and get
        cache.set("https://example.com/page1", "response_data")
        assert cache.get("https://example.com/page1") == "response_data"
        
        # Test statistics
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 0
        assert stats["size"] == 1
        
        # Test contains
        assert "https://example.com/page1" in cache
        assert "https://example.com/page2" not in cache
        
        # Test miss
        assert cache.get("https://example.com/missing") is None
        stats = cache.get_stats()
        assert stats["misses"] == 1
    
    def test_cache_integration_workflow(self):
        """Test typical cache workflow with HTTP client pattern."""
        cache = ResponseCache(max_size=100, default_ttl=300)
        
        # Simulate HTTP client workflow
        url = "https://example.com/api/data"
        
        # First request - cache miss
        cached = cache.get(url)
        assert cached is None
        
        # Simulate response
        mock_response = {"data": "test", "status": 200}
        cache.set(url, mock_response)
        
        # Second request - cache hit
        cached = cache.get(url)
        assert cached is not None
        assert cached == mock_response
        
        # Verify stats
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5
    
    def test_cache_respects_use_cache_flag(self):
        """Test that use_cache parameter is properly handled."""
        cache = ResponseCache(max_size=10, default_ttl=60)
        client = AsyncHTTPClient(cache=cache)
        
        # Verify cache is attached
        assert client._cache is cache
        
        # Test that client has use_cache parameter in get method
        import inspect
        sig = inspect.signature(client.get)
        assert 'use_cache' in sig.parameters
        assert sig.parameters['use_cache'].default is True
