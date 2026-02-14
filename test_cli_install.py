#!/usr/bin/env python
"""Simple test of the CLI installation."""

import subprocess
import sys

def test_cli():
    """Test that the CLI is properly installed and working."""
    tests = [
        (["tumblr-archiver", "--help"], "help should work"),
        (["tumblr-archiver", "--version"], "version should work"),
        (["python", "-m", "tumblr_archiver", "--help"], "module invocation should work"),
    ]
    
    print("Testing Tumblr Archiver CLI Installation\n" + "=" * 50)
    
    failures = 0
    for cmd, description in tests:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # Check if command succeeded
            if result.returncode == 0:
                print(f"✓ {description}")
                if "--version" in cmd:
                    print(f"  Output: {result.stdout.strip()}")
            else:
                print(f"✗ {description}")
                print(f"  Error: {result.stderr[:200]}")
                failures += 1
                
        except subprocess.TimeoutExpired:
            print(f"✗ {description} (timeout)")
            failures += 1
        except FileNotFoundError:
            print(f"✗ {description} (command not found)")
            failures += 1
        except Exception as e:
            print(f"✗ {description} (error: {e})")
            failures += 1
    
    print("\n" + "=" * 50)
    if failures == 0:
        print("All tests passed! ✓")
        return 0
    else:
        print(f"{failures} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(test_cli())
