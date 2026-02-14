#!/usr/bin/env python3
"""Demonstration of performance features for Task 9.1."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from tumblr_archiver.cache import ResponseCache
from tumblr_archiver.performance import PerformanceMonitor


def demo_cache():
    """Demonstrate cache functionality."""
    print("=" * 60)
    print("Cache Demonstration")
    print("=" * 60)
    
    cache = ResponseCache(max_size=100, default_ttl=300)
    
    # Store some values
    print("\n1. Storing values in cache...")
    cache.set("https://example.com/page1", {"data": "response1"})
    cache.set("https://example.com/page2", {"data": "response2"})
    cache.set("https://example.com/page3", {"data": "response3"})
    print(f"   Cached {len(cache)} items")
    
    # Retrieve values
    print("\n2. Retrieving cached values...")
    result1 = cache.get("https://example.com/page1")
    print(f"   page1: {result1}")
    
    result2 = cache.get("https://example.com/page2")
    print(f"   page2: {result2}")
    
    # Cache miss
    print("\n3. Testing cache miss...")
    result_miss = cache.get("https://example.com/missing")
    print(f"   missing page: {result_miss}")
    
    # Statistics
    print("\n4. Cache Statistics:")
    stats = cache.get_stats()
    print(f"   Hits:      {stats['hits']}")
    print(f"   Misses:    {stats['misses']}")
    print(f"   Hit Rate:  {stats['hit_rate']:.1%}")
    print(f"   Size:      {stats['size']}/{stats['max_size']}")
    
    print("\n✓ Cache demonstration complete!\n")


def demo_performance_monitor():
    """Demonstrate performance monitoring.""" 
    print("=" * 60)
    print("Performance Monitor Demonstration")
    print("=" * 60)
    
    monitor = PerformanceMonitor()
    
    # Manual timing
    print("\n1. Manual timing...")
    import time
    
    monitor.start_timer("task1")
    time.sleep(0.1)
    duration = monitor.end_timer("task1")
    print(f"   task1 took {duration:.3f}s")
    
    # Context manager timing
    print("\n2. Context manager timing...")
    with monitor.timer("task2"):
        time.sleep(0.05)
    print(f"   task2 completed")
    
    # Multiple operations
    print("\n3. Multiple timed operations...")
    for i in range(3):
        with monitor.timer("loop_operation"):
            time.sleep(0.02)
    print(f"   loop_operation executed 3 times")
    
    # Get statistics
    print("\n4. Performance Statistics:")
    stats = monitor.get_stats()
    
    for op_name, op_stats in stats.items():
        print(f"\n   {op_name}:")
        print(f"     Count:    {op_stats.count}")
        print(f"     Total:    {op_stats.total_time:.3f}s")
        print(f"     Average:  {op_stats.avg_time:.3f}s")
        print(f"     Min:      {op_stats.min_time:.3f}s")
        print(f"     Max:      {op_stats.max_time:.3f}s")
    
    # Summary table
    print("\n5. Summary Table:")
    print(monitor.get_summary())
    
    print("\n✓ Performance monitor demonstration complete!\n")


async def demo_integration():
    """Demonstrate cache and HTTP client integration."""
    print("=" * 60)
    print("HTTP Client + Cache Integration")
    print("=" * 60)
    
    from tumblr_archiver.http_client import AsyncHTTPClient
    
    # Create cache
    cache = ResponseCache(max_size=50, default_ttl=60)
    
    # Create client with cache
    print("\n1. Creating HTTP client with cache...")
    async with AsyncHTTPClient(cache=cache, rate_limit=10.0) as client:
        print(f"   Cache enabled: {client._cache is not None}")
        print(f"   Max cache size: {cache._max_size}")
        print(f"   Default TTL: {cache._default_ttl}s")
    
    print("\n✓ Integration demonstration complete!\n")


def main():
    """Run all demonstrations."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 9 + "Task 9.1: Performance Optimization" + " " * 15 + "║")
    print("║" + " " * 23 + "Demonstration" + " " * 22 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    try:
        # Demo cache
        demo_cache()
        
        # Demo performance monitor
        demo_performance_monitor()
        
        # Demo integration
        asyncio.run(demo_integration())
        
        print("=" * 60)
        print("All demonstrations completed successfully! ✓")
        print("=" * 60)
        print()
        print("Summary of implemented features:")
        print("  ✓ ResponseCache with LRU eviction")
        print("  ✓ PerformanceMonitor with timing statistics")
        print("  ✓ HTTP client cache integration")
        print("  ✓ Benchmark script (benchmarks/benchmark.py)")
        print("  ✓ Comprehensive test suite (tests/test_performance.py)")
        print()
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
