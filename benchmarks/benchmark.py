#!/usr/bin/env python3
"""Benchmark script for Tumblr archiver performance testing.

Tests download performance, parsing performance, and caching effectiveness.
Run standalone to measure performance characteristics.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tumblr_archiver.cache import ResponseCache
from tumblr_archiver.http_client import AsyncHTTPClient
from tumblr_archiver.parser import TumblrParser
from tumblr_archiver.performance import PerformanceMonitor

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(message)s"
)


class Benchmark:
    """Benchmark runner for performance testing."""
    
    def __init__(self):
        """Initialize benchmark."""
        self.monitor = PerformanceMonitor()
        self.results: dict[str, Any] = {}
    
    async def benchmark_http_client(self, url: str = "https://httpbin.org/delay/0") -> dict[str, Any]:
        """Benchmark HTTP client performance.
        
        Args:
            url: URL to fetch (default: httpbin delay endpoint)
            
        Returns:
            Benchmark results
        """
        print("\n=== HTTP Client Benchmark ===")
        print(f"Testing with URL: {url}")
        
        iterations = 5
        
        async with AsyncHTTPClient(rate_limit=10.0) as client:
            # Warmup
            with self.monitor.timer("http_warmup"):
                await client.get(url)
            
            # Benchmark
            for i in range(iterations):
                with self.monitor.timer("http_request"):
                    response = await client.get(url)
                    await response.text()
        
        stats = self.monitor.get_stats("http_request")["http_request"]
        
        result = {
            "test": "HTTP Client",
            "iterations": iterations,
            "total_time": stats.total_time,
            "avg_time": stats.avg_time,
            "min_time": stats.min_time,
            "max_time": stats.max_time,
            "requests_per_sec": iterations / stats.total_time,
        }
        
        self._print_result(result)
        return result
    
    def benchmark_cache(self) -> dict[str, Any]:
        """Benchmark cache performance.
        
        Returns:
            Benchmark results
        """
        print("\n=== Cache Benchmark ===")
        
        cache = ResponseCache(max_size=1000, default_ttl=60)
        iterations = 10000
        
        # Benchmark writes
        with self.monitor.timer("cache_write"):
            for i in range(iterations):
                cache.set(f"key_{i}", f"value_{i}")
        
        # Benchmark reads (hits)
        with self.monitor.timer("cache_read_hit"):
            for i in range(iterations):
                _ = cache.get(f"key_{i}")
        
        # Benchmark reads (misses)
        with self.monitor.timer("cache_read_miss"):
            for i in range(iterations):
                _ = cache.get(f"missing_key_{i}")
        
        write_stats = self.monitor.get_stats("cache_write")["cache_write"]
        read_hit_stats = self.monitor.get_stats("cache_read_hit")["cache_read_hit"]
        read_miss_stats = self.monitor.get_stats("cache_read_miss")["cache_read_miss"]
        cache_stats = cache.get_stats()
        
        result = {
            "test": "Cache",
            "iterations": iterations,
            "write_time": write_stats.total_time,
            "write_ops_per_sec": iterations / write_stats.total_time,
            "read_hit_time": read_hit_stats.total_time,
            "read_hit_ops_per_sec": iterations / read_hit_stats.total_time,
            "read_miss_time": read_miss_stats.total_time,
            "read_miss_ops_per_sec": iterations / read_miss_stats.total_time,
            "hit_rate": cache_stats["hit_rate"],
        }
        
        self._print_result(result)
        return result
    
    def benchmark_parser(self) -> dict[str, Any]:
        """Benchmark HTML parsing performance.
        
        Returns:
            Benchmark results
        """
        print("\n=== Parser Benchmark ===")
        
        # Create sample HTML with realistic Tumblr structure
        sample_html = """
        <html>
        <body>
            <article class="post" id="post-12345" data-post-id="12345">
                <div class="post-content">
                    <img src="https://example.com/image1.jpg">
                    <img src="https://example.com/image2.jpg">
                    <video src="https://example.com/video1.mp4"></video>
                </div>
                <div class="post-footer">
                    <time datetime="2024-01-01T12:00:00Z">Jan 1, 2024</time>
                </div>
            </article>
        </body>
        </html>
        """ * 10  # Repeat to make it realistic
        
        parser = TumblrParser()
        iterations = 100
        
        # Benchmark parsing
        with self.monitor.timer("parse"):
            for _ in range(iterations):
                _ = parser.parse_page(sample_html, "https://example.tumblr.com")
        
        stats = self.monitor.get_stats("parse")["parse"]
        
        result = {
            "test": "HTML Parser",
            "iterations": iterations,
            "total_time": stats.total_time,
            "avg_time": stats.avg_time,
            "parses_per_sec": iterations / stats.total_time,
        }
        
        self._print_result(result)
        return result
    
    def benchmark_performance_monitor(self) -> dict[str, Any]:
        """Benchmark performance monitor overhead.
        
        Returns:
            Benchmark results
        """
        print("\n=== Performance Monitor Overhead ===")
        
        iterations = 100000
        
        # Baseline: no monitoring
        start = time.perf_counter()
        for _ in range(iterations):
            pass  # Empty loop
        baseline_time = time.perf_counter() - start
        
        # With monitoring
        monitor = PerformanceMonitor()
        start = time.perf_counter()
        for _ in range(iterations):
            with monitor.timer("test_op"):
                pass  # Empty operation
        monitored_time = time.perf_counter() - start
        
        overhead = monitored_time - baseline_time
        overhead_per_op = overhead / iterations
        
        result = {
            "test": "Performance Monitor",
            "iterations": iterations,
            "baseline_time": baseline_time,
            "monitored_time": monitored_time,
            "overhead": overhead,
            "overhead_per_op_us": overhead_per_op * 1_000_000,  # microseconds
        }
        
        print(f"Iterations:        {iterations:,}")
        print(f"Baseline time:     {baseline_time:.6f}s")
        print(f"Monitored time:    {monitored_time:.6f}s")
        print(f"Overhead:          {overhead:.6f}s")
        print(f"Overhead per op:   {overhead_per_op * 1_000_000:.3f}µs")
        
        return result
    
    def _print_result(self, result: dict[str, Any]) -> None:
        """Print benchmark result.
        
        Args:
            result: Benchmark result dictionary
        """
        for key, value in result.items():
            if key == "test":
                continue
            if isinstance(value, float):
                if "per_sec" in key:
                    print(f"{key:25s}: {value:,.2f}")
                elif "rate" in key:
                    print(f"{key:25s}: {value:.2%}")
                else:
                    print(f"{key:25s}: {value:.6f}s")
            else:
                print(f"{key:25s}: {value:,}")
    
    async def run_all(self) -> dict[str, Any]:
        """Run all benchmarks.
        
        Returns:
            All benchmark results
        """
        print("=" * 60)
        print("Tumblr Archiver Performance Benchmarks")
        print("=" * 60)
        
        results = {}
        
        # Run benchmarks
        try:
            results["cache"] = self.benchmark_cache()
        except Exception as e:
            print(f"Cache benchmark failed: {e}")
        
        try:
            results["parser"] = self.benchmark_parser()
        except Exception as e:
            print(f"Parser benchmark failed: {e}")
        
        try:
            results["monitor"] = self.benchmark_performance_monitor()
        except Exception as e:
            print(f"Monitor benchmark failed: {e}")
        
        # HTTP client benchmark (requires network)
        try:
            results["http"] = await self.benchmark_http_client()
        except Exception as e:
            print(f"\nHTTP benchmark skipped (network error): {e}")
        
        # Summary
        print("\n" + "=" * 60)
        print("Summary")
        print("=" * 60)
        print(f"Total benchmarks:  {len(results)}")
        print("All benchmarks completed successfully!")
        
        return results


def main():
    """Run benchmarks."""
    benchmark = Benchmark()
    
    try:
        results = asyncio.run(benchmark.run_all())
        return 0
    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\nBenchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
