#!/usr/bin/env python3
"""Quick verification that Task 9.1 implementation works."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_imports():
    """Test that modules can be imported."""
    print("Testing imports...")
    
    from tumblr_archiver.cache import ResponseCache, CacheEntry
    from tumblr_archiver.performance import PerformanceMonitor, TimingStats
    from tumblr_archiver.http_client import AsyncHTTPClient
    
    print("  ✓ All imports successful")
    return True

def test_cache():
    """Test basic cache functionality."""
    print("\nTesting cache...")
    
    from tumblr_archiver.cache import ResponseCache
    
    cache = ResponseCache(max_size=10, default_ttl=60)
    cache.set("test_key", "test_value")
    value = cache.get("test_key")
    
    assert value == "test_value", f"Expected 'test_value', got {value}"
    assert len(cache) == 1
    
    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 0
    
    print("  ✓ Cache works correctly")
    return True

def test_performance_monitor():
    """Test basic performance monitor functionality."""
    print("\nTesting performance monitor...")
    
    from tumblr_archiver.performance import PerformanceMonitor
    import time
    
    monitor = PerformanceMonitor()
    
    with monitor.timer("test_op"):
        time.sleep(0.01)
    
    stats = monitor.get_stats("test_op")
    assert "test_op" in stats
    assert stats["test_op"].count == 1
    assert stats["test_op"].total_time >= 0.01
    
    print("  ✓ Performance monitor works correctly")
    return True

def test_http_client_integration():
    """Test HTTP client cache integration."""
    print("\nTesting HTTP client integration...")
    
    from tumblr_archiver.cache import ResponseCache
    from tumblr_archiver.http_client import AsyncHTTPClient
    
    cache = ResponseCache(max_size=10, default_ttl=60)
    client = AsyncHTTPClient(cache=cache)
    
    assert client._cache is cache
    
    print("  ✓ HTTP client accepts cache parameter")
    return True

def main():
    """Run all tests."""
    print("=" * 60)
    print("Task 9.1: Performance Optimization - Quick Verification")
    print("=" * 60)
    
    try:
        test_imports()
        test_cache()
        test_performance_monitor()
        test_http_client_integration()
        
        print("\n" + "=" * 60)
        print("✅ All verification tests passed!")
        print("=" * 60)
        print("\nImplemented features:")
        print("  • ResponseCache (src/tumblr_archiver/cache.py)")
        print("  • PerformanceMonitor (src/tumblr_archiver/performance.py)")
        print("  • Benchmark script (benchmarks/benchmark.py)")
        print("  • Test suite (tests/test_performance.py - 43 tests)")
        print("  • HTTP client integration")
        print()
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
