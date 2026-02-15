#!/usr/bin/env python3
"""
Comprehensive validation tests for Tumblr Media Downloader.
Tests utils.py, media_selector.py, and rate_limiter.py functionality.

NOTE: this module is a standalone validation script (keeps its own test harness) —
it is intentionally excluded from pytest collection.
"""

# prevent pytest from auto-collecting the functions inside this module
__test__ = False

import sys
import time
import asyncio
from pathlib import Path

# Test results tracking
test_results = {
    'passed': 0,
    'failed': 0,
    'details': []
}


def test_pass(test_name, details=""):
    """Record a passing test."""
    test_results['passed'] += 1
    test_results['details'].append({
        'status': '✅ PASS',
        'test': test_name,
        'details': details
    })
    print(f"✅ PASS: {test_name}")
    if details:
        print(f"  Details: {details}")


def test_fail(test_name, error, suggestion=""):
    """Record a failing test."""
    test_results['failed'] += 1
    test_results['details'].append({
        'status': '❌ FAIL',
        'test': test_name,
        'error': str(error),
        'suggestion': suggestion
    })
    print(f"❌ FAIL: {test_name}")
    print(f"  Error: {error}")
    if suggestion:
        print(f"  Suggestion: {suggestion}")


def test_utils():
    """Test functions in utils.py"""
    from tumblr_downloader.utils import (
        sanitize_filename, parse_blog_name, extract_post_id, format_bytes
    )
    
    print("\n" + "="*70)
    print("TESTING: utils.py")
    print("="*70)
    
    # Test sanitize_filename
    try:
        # Valid filename
        result = sanitize_filename("test_file.jpg")
        assert result == "test_file.jpg"
        test_pass("sanitize_filename: Basic filename", f"'test_file.jpg' → '{result}'")
    except Exception as e:
        test_fail("sanitize_filename: Basic filename", e)
    
    try:
        # Filename with invalid characters
        result = sanitize_filename('file<>:"|?*.txt')
        assert '<' not in result and '>' not in result
        test_pass("sanitize_filename: Invalid characters", f"'file<>:\"|?*.txt' → '{result}'")
    except Exception as e:
        test_fail("sanitize_filename: Invalid characters", e)
    
    try:
        # Reserved Windows names
        result = sanitize_filename("CON.txt")
        assert result == "_CON.txt"
        test_pass("sanitize_filename: Reserved name", f"'CON.txt' → '{result}'")
    except Exception as e:
        test_fail("sanitize_filename: Reserved name", e)
    
    try:
        # Empty filename should raise ValueError
        sanitize_filename("")
        test_fail("sanitize_filename: Empty string", "Should raise ValueError but didn't")
    except ValueError as e:
        test_pass("sanitize_filename: Empty string validation", f"Correctly raised: {e}")
    except Exception as e:
        test_fail("sanitize_filename: Empty string validation", e)
    
    # Test parse_blog_name
    try:
        result = parse_blog_name("https://myblog.tumblr.com")
        assert result == "myblog"
        test_pass("parse_blog_name: Full URL", f"'https://myblog.tumblr.com' → '{result}'")
    except Exception as e:
        test_fail("parse_blog_name: Full URL", e)
    
    try:
        result = parse_blog_name("myblog.tumblr.com")
        assert result == "myblog"
        test_pass("parse_blog_name: Domain only", f"'myblog.tumblr.com' → '{result}'")
    except Exception as e:
        test_fail("parse_blog_name: Domain only", e)
    
    try:
        result = parse_blog_name("myblog")
        assert result == "myblog"
        test_pass("parse_blog_name: Plain name", f"'myblog' → '{result}'")
    except Exception as e:
        test_fail("parse_blog_name: Plain name", e)
    
    try:
        parse_blog_name("")
        test_fail("parse_blog_name: Empty input", "Should raise ValueError but didn't")
    except ValueError as e:
        test_pass("parse_blog_name: Empty input validation", f"Correctly raised: {e}")
    except Exception as e:
        test_fail("parse_blog_name: Empty input validation", e)
    
    # Test extract_post_id
    try:
        result = extract_post_id("123456789")
        assert result == "123456789"
        test_pass("extract_post_id: Direct ID string", f"'123456789' → '{result}'")
    except Exception as e:
        test_fail("extract_post_id: Direct ID string", e)
    
    try:
        result = extract_post_id(123456789)
        assert result == "123456789"
        test_pass("extract_post_id: Integer ID", f"123456789 → '{result}'")
    except Exception as e:
        test_fail("extract_post_id: Integer ID", e)
    
    try:
        result = extract_post_id("https://blog.tumblr.com/post/123456789/some-slug")
        assert result == "123456789"
        test_pass("extract_post_id: Full URL", f"URL → '{result}'")
    except Exception as e:
        test_fail("extract_post_id: Full URL", e)
    
    try:
        result = extract_post_id({'id': 123456789})
        assert result == "123456789"
        test_pass("extract_post_id: Dict with id", f"Dict → '{result}'")
    except Exception as e:
        test_fail("extract_post_id: Dict with id", e)
    
    # Test format_bytes
    try:
        result = format_bytes(0)
        assert result == "0 B"
        test_pass("format_bytes: Zero bytes", f"0 → '{result}'")
    except Exception as e:
        test_fail("format_bytes: Zero bytes", e)
    
    try:
        result = format_bytes(1024)
        assert result == "1.00 KB"
        test_pass("format_bytes: 1 KB", f"1024 → '{result}'")
    except Exception as e:
        test_fail("format_bytes: 1 KB", e)
    
    try:
        result = format_bytes(1048576)
        assert result == "1.00 MB"
        test_pass("format_bytes: 1 MB", f"1048576 → '{result}'")
    except Exception as e:
        test_fail("format_bytes: 1 MB", e)
    
    try:
        format_bytes(-1)
        test_fail("format_bytes: Negative value", "Should raise ValueError but didn't")
    except ValueError as e:
        test_pass("format_bytes: Negative validation", f"Correctly raised: {e}")
    except Exception as e:
        test_fail("format_bytes: Negative validation", e)


def test_media_selector():
    """Test functions in media_selector.py"""
    from tumblr_downloader.media_selector import select_best_image, extract_media_from_post
    
    print("\n" + "="*70)
    print("TESTING: media_selector.py")
    print("="*70)
    
    # Test select_best_image
    try:
        variants = [
            {'url': 'image_500.jpg', 'width': 500, 'height': 400},
            {'url': 'image_1280.jpg', 'width': 1280, 'height': 1024}
        ]
        result = select_best_image(variants)
        assert result['width'] == 1280
        test_pass("select_best_image: Choose highest resolution", 
                  f"Selected {result['width']}x{result['height']} from 2 variants")
    except Exception as e:
        test_fail("select_best_image: Choose highest resolution", e)
    
    try:
        variants = [
            {'url': 'image_original.jpg', 'width': 800, 'height': 600},
            {'url': 'image_1280.jpg', 'width': 1280, 'height': 1024}
        ]
        result = select_best_image(variants)
        assert result['width'] == 1280  # Pixel area wins over 'original' keyword
        test_pass("select_best_image: Pixel area priority", 
                  f"Selected {result['width']}x{result['height']} (larger area)")
    except Exception as e:
        test_fail("select_best_image: Pixel area priority", e)
    
    try:
        result = select_best_image([{'url': 'single.jpg', 'width': 100, 'height': 100}])
        assert result['url'] == 'single.jpg'
        test_pass("select_best_image: Single variant", "Correctly returned single variant")
    except Exception as e:
        test_fail("select_best_image: Single variant", e)
    
    try:
        select_best_image([])
        test_fail("select_best_image: Empty list", "Should raise ValueError but didn't")
    except ValueError as e:
        test_pass("select_best_image: Empty list validation", f"Correctly raised: {e}")
    except Exception as e:
        test_fail("select_best_image: Empty list validation", e)
    
    # Test extract_media_from_post with photo post
    try:
        photo_post = {
            'id': '123456',
            'type': 'photo',
            'photos': [
                {
                    'original_size': {
                        'url': 'https://example.com/photo_original.jpg',
                        'width': 1280,
                        'height': 1024
                    },
                    'alt_sizes': [
                        {'url': 'https://example.com/photo_500.jpg', 'width': 500, 'height': 400}
                    ]
                }
            ]
        }
        media = extract_media_from_post(photo_post)
        assert len(media) == 1
        assert media[0]['type'] == 'photo'
        assert media[0]['width'] == 1280
        test_pass("extract_media_from_post: Photo post", 
                  f"Extracted {len(media)} photo(s), selected highest res")
    except Exception as e:
        test_fail("extract_media_from_post: Photo post", e)
    
    # Test with invalid post
    try:
        media = extract_media_from_post({'id': '999', 'type': 'text'})
        assert media == []
        test_pass("extract_media_from_post: Text post", "Correctly returned empty list")
    except Exception as e:
        test_fail("extract_media_from_post: Text post", e)
    
    try:
        media = extract_media_from_post("not a dict")
        assert media == []
        test_pass("extract_media_from_post: Invalid input", "Handled gracefully")
    except Exception as e:
        test_fail("extract_media_from_post: Invalid input", e)


def test_rate_limiter():
    """Test RateLimiter class"""
    from tumblr_downloader.rate_limiter import RateLimiter
    
    print("\n" + "="*70)
    print("TESTING: rate_limiter.py")
    print("="*70)
    
    # Test initialization
    try:
        limiter = RateLimiter(max_per_second=2.0)
        assert limiter.max_per_second == 2.0
        assert limiter.tokens == 2.0
        test_pass("RateLimiter: Initialization", f"Created with 2 ops/sec, {limiter.tokens} tokens")
    except Exception as e:
        test_fail("RateLimiter: Initialization", e)
    
    try:
        RateLimiter(max_per_second=0)
        test_fail("RateLimiter: Zero rate", "Should raise ValueError but didn't")
    except ValueError as e:
        test_pass("RateLimiter: Zero rate validation", f"Correctly raised: {e}")
    except Exception as e:
        test_fail("RateLimiter: Zero rate validation", e)
    
    try:
        RateLimiter(max_per_second=-1)
        test_fail("RateLimiter: Negative rate", "Should raise ValueError but didn't")
    except ValueError as e:
        test_pass("RateLimiter: Negative rate validation", f"Correctly raised: {e}")
    except Exception as e:
        test_fail("RateLimiter: Negative rate validation", e)
    
    # Test wait() functionality
    try:
        limiter = RateLimiter(max_per_second=10.0)  # Fast rate for testing
        start = time.time()
        limiter.wait()  # Should not block since we have tokens
        elapsed = time.time() - start
        assert elapsed < 0.1  # Should be nearly instant
        test_pass("RateLimiter: wait() with available token", f"Completed in {elapsed:.4f}s")
    except Exception as e:
        test_fail("RateLimiter: wait() with available token", e)
    
    # Test token consumption
    try:
        limiter = RateLimiter(max_per_second=2.0)
        initial_tokens = limiter.get_available_tokens()
        limiter.wait()
        remaining_tokens = limiter.get_available_tokens()
        assert remaining_tokens < initial_tokens
        test_pass("RateLimiter: Token consumption", 
                  f"Tokens: {initial_tokens:.2f} → {remaining_tokens:.2f}")
    except Exception as e:
        test_fail("RateLimiter: Token consumption", e)
    
    # Test try_acquire
    try:
        limiter = RateLimiter(max_per_second=2.0)
        result1 = limiter.try_acquire()
        result2 = limiter.try_acquire()
        result3 = limiter.try_acquire()  # Should fail, no tokens left
        assert result1 == True
        assert result2 == True
        assert result3 == False
        test_pass("RateLimiter: try_acquire()", 
                  f"Results: {result1}, {result2}, {result3} (expected True, True, False)")
    except Exception as e:
        test_fail("RateLimiter: try_acquire()", e)
    
    # Test reset
    try:
        limiter = RateLimiter(max_per_second=2.0)
        limiter.wait()
        limiter.wait()
        before_reset = limiter.get_available_tokens()
        limiter.reset()
        after_reset = limiter.get_available_tokens()
        assert after_reset == 2.0
        test_pass("RateLimiter: reset()", 
                  f"Tokens before: {before_reset:.2f}, after: {after_reset:.2f}")
    except Exception as e:
        test_fail("RateLimiter: reset()", e)
    
    # Test token refill over time
    try:
        limiter = RateLimiter(max_per_second=10.0)
        limiter.wait()
        limiter.wait()
        tokens_after = limiter.get_available_tokens()
        time.sleep(0.2)  # Wait for refill
        tokens_refilled = limiter.get_available_tokens()
        assert tokens_refilled > tokens_after
        test_pass("RateLimiter: Token refill", 
                  f"Tokens after use: {tokens_after:.2f}, after 0.2s: {tokens_refilled:.2f}")
    except Exception as e:
        test_fail("RateLimiter: Token refill", e)
    
    # Test async acquire
    try:
        async def test_async():
            limiter = RateLimiter(max_per_second=10.0)
            await limiter.acquire()
            return True
        
        result = asyncio.run(test_async())
        assert result == True
        test_pass("RateLimiter: async acquire()", "Successfully acquired token asynchronously")
    except Exception as e:
        test_fail("RateLimiter: async acquire()", e)


def print_summary():
    """Print test summary"""
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Total Tests: {test_results['passed'] + test_results['failed']}")
    print(f"✅ Passed: {test_results['passed']}")
    print(f"❌ Failed: {test_results['failed']}")
    print("="*70)
    
    if test_results['failed'] > 0:
        print("\nFailed Tests Detail:")
        for detail in test_results['details']:
            if detail['status'] == '❌ FAIL':
                print(f"\n{detail['status']} {detail['test']}")
                print(f"  Error: {detail['error']}")
                if detail.get('suggestion'):
                    print(f"  Suggestion: {detail['suggestion']}")
    
    return 0 if test_results['failed'] == 0 else 1


if __name__ == "__main__":
    print("="*70)
    print("TUMBLR MEDIA DOWNLOADER - UNIT TEST VALIDATION")
    print("="*70)
    
    test_utils()
    test_media_selector()
    test_rate_limiter()
    
    exit_code = print_summary()
    sys.exit(exit_code)
