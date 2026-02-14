# Troubleshooting Guide

Solutions to common issues encountered while using Tumblr Archiver.

## Table of Contents

- [Quick Diagnostic](#quick-diagnostic)
- [Common Errors](#common-errors)
- [Network Issues](#network-issues)
- [Rate Limiting](#rate-limiting)
- [Manifest Issues](#manifest-issues)
- [Performance Problems](#performance-problems)
- [Installation Issues](#installation-issues)
- [Data Issues](#data-issues)
- [Advanced Troubleshooting](#advanced-troubleshooting)

## Quick Diagnostic

Run this diagnostic command to check common issues:

```bash
# Check version
tumblr-archiver --version

# Test with dry run and verbose
tumblr-archiver myblog --dry-run --verbose

# Check Python version
python --version  # Should be 3.10+

# Check dependencies
pip list | grep -E "aiohttp|click|beautifulsoup4"
```

## Common Errors

### Error: Blog Not Found

**Symptoms**:
```
ERROR: Blog 'myblog' not found (404)
BlogNotFoundError: The blog may have been deleted or is private
```

**Causes**:
1. Blog has been deleted
2. Blog is private/password-protected
3. Typo in blog name
4. Blog uses custom domain

**Solutions**:

1. **Verify blog exists**:
   ```bash
   # Try visiting in browser
   open https://myblog.tumblr.com
   ```

2. **Check blog name**:
   ```bash
   # Try different formats
   tumblr-archiver myblog
   tumblr-archiver my-blog  # Check for hyphens
   tumblr-archiver myblog.tumblr.com
   ```

3. **Check if private**:
   - Private blogs cannot be archived without authentication
   - Currently not supported

4. **Custom domains**:
   - Custom domain blogs not currently supported
   - Use official tumblr.com subdomain if available

### Error: Rate Limited (429)

**Symptoms**:
```
ERROR: Rate limited by server (429 Too Many Requests)
Backing off for 32.0 seconds...
```

**Immediate action**:
```bash
# Stop the current run
Ctrl+C

# Wait 5-10 minutes

# Resume with conservative settings
tumblr-archiver myblog --rate 0.5 --concurrency 1
```

**Prevention**:
```bash
# Use conservative settings from start
tumblr-archiver myblog --rate 1.0 --concurrency 2
```

**Related**: See [Rate Limiting](#rate-limiting) section.

### Error: Connection Timeout

**Symptoms**:
```
ERROR: Timeout while downloading https://...
asyncio.TimeoutError: Connection timeout after 30.0 seconds
```

**Solutions**:

1. **Increase timeout**:
   ```bash
   tumblr-archiver myblog --timeout 60.0
   ```

2. **Check your connection**:
   ```bash
   # Test connectivity
   ping tumblr.com
   curl -I https://tumblr.com
   ```

3. **Reduce concurrency**:
   ```bash
   # Less concurrent = more stable
   tumblr-archiver myblog --concurrency 2
   ```

4. **Check for VPN issues**:
   - Some VPNs cause timeouts
   - Try without VPN
   - Or increase timeout significantly

### Error: Disk Space Full

**Symptoms**:
```
ERROR: No space left on device
OSError: [Errno 28] No space left on device
```

**Solutions**:

1. **Check available space**:
   ```bash
   df -h .
   ```

2. **Free up space**:
   ```bash
   # Find large files
   du -sh downloads/*
   
   # Remove unnecessary files
   rm -rf old-archives/
   ```

3. **Use different drive**:
   ```bash
   tumblr-archiver myblog --output /mnt/external-drive/downloads
   ```

4. **Estimate before downloading**:
   ```bash
   tumblr-archiver myblog --dry-run
   # Check "Estimated download size"
   ```

### Error: Permission Denied

**Symptoms**:
```
ERROR: Permission denied: '/some/path'
PermissionError: [Errno 13] Permission denied
```

**Solutions**:

1. **Check directory permissions**:
   ```bash
   ls -ld downloads/
   ```

2. **Create writable directory**:
   ```bash
   mkdir -p ~/tumblr-archives
   chmod 755 ~/tumblr-archives
   tumblr-archiver myblog --output ~/tumblr-archives
   ```

3. **Don't use system directories**:
   ```bash
   # BAD: /usr/local/downloads
   # GOOD: ~/downloads or ./downloads
   ```

4. **Check parent directory exists**:
   ```bash
   # This may fail if /nonexistent doesn't exist
   tumblr-archiver myblog --output /nonexistent/downloads
   
   # Create parent first
   mkdir -p /path/to/parent
   tumblr-archiver myblog --output /path/to/parent/downloads
   ```

### Error: Invalid Blog Name Format

**Symptoms**:
```
Configuration error: Invalid blog_name format: 'my_blog'
```

**Cause**: Blog names can only contain letters, numbers, and hyphens.

**Solutions**:
```bash
# BAD: underscores not allowed
tumblr-archiver my_blog

# GOOD: use hyphens
tumblr-archiver my-blog

# GOOD: no special characters
tumblr-archiver myblog123
```

### Error: Manifest Corruption

**Symptoms**:
```
ERROR: Failed to load manifest
json.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**Solutions**:

1. **Backup and remove corrupt manifest**:
   ```bash
   cd downloads/myblog
   
   # Backup
   cp manifest.json manifest.json.corrupt.backup
   
   # Remove
   rm manifest.json
   
   # Start fresh (existing files won't be re-downloaded)
   tumblr-archiver myblog --no-resume
   ```

2. **Try to repair manifest**:
   ```bash
   # Check if valid JSON
   python -m json.tool manifest.json
   
   # If repairable, edit manually
   nano manifest.json
   ```

3. **Restore from backup**:
   ```bash
   # If you have backups
   cp manifest.json.backup manifest.json
   ```

## Network Issues

### Slow Download Speeds

**Diagnosis**:
```bash
# Test with verbose
tumblr-archiver myblog --verbose

# Check network speed
speedtest-cli  # or visit speedtest.net
```

**Solutions**:

1. **Increase concurrency**:
   ```bash
   tumblr-archiver myblog --concurrency 4
   ```

2. **Increase rate limit**:
   ```bash
   tumblr-archiver myblog --rate 2.0
   ```

3. **Check for throttling**:
   - ISP may throttle during peak hours
   - Try different time of day
   - Use wired connection instead of WiFi

4. **Check for local congestion**:
   ```bash
   # Close other bandwidth-heavy applications
   # Pause other downloads
   # Disconnect other devices
   ```

### Intermittent Connection Drops

**Symptoms**:
- Downloads start and stop
- Many retry attempts
- Some files fail repeatedly

**Solutions**:

1. **Increase retries and timeout**:
   ```bash
   tumblr-archiver myblog \
     --max-retries 7 \
     --timeout 60.0
   ```

2. **Reduce concurrency**:
   ```bash
   tumblr-archiver myblog --concurrency 1
   ```

3. **Check network stability**:
   ```bash
   # Ping test for 60 seconds
   ping -c 60 tumblr.com
   
   # Look for packet loss or high latency
   ```

4. **Use resume capability**:
   ```bash
   # Let it fail, then resume
   tumblr-archiver myblog  # Fails with connection issues
   # ... fix network ...
   tumblr-archiver myblog  # Resumes automatically
   ```

### SSL/TLS Errors

**Symptoms**:
```
ERROR: SSL certificate verification failed
ssl.SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**Solutions**:

1. **Update certificates**:
   ```bash
   # macOS
   /Applications/Python\ 3.10/Install\ Certificates.command
   
   # Linux
   sudo apt update && sudo apt install ca-certificates
   
   # Or update certifi
   pip install --upgrade certifi
   ```

2. **Check system time**:
   ```bash
   # Incorrect system time can cause SSL errors
   date
   
   # Fix if needed (macOS/Linux)
   sudo ntpdate -s time.apple.com
   ```

3. **Update aiohttp**:
   ```bash
   pip install --upgrade aiohttp
   ```

### DNS Resolution Failures

**Symptoms**:
```
ERROR: Failed to resolve hostname
gaierror: [Errno -2] Name or service not known
```

**Solutions**:

1. **Check DNS**:
   ```bash
   # Test DNS resolution
   nslookup tumblr.com
   host tumblr.com
   ```

2. **Try different DNS**:
   ```bash
   # Edit /etc/resolv.conf or use network settings
   # Try Google DNS: 8.8.8.8, 8.8.4.4
   # Try Cloudflare DNS: 1.1.1.1
   ```

3. **Check /etc/hosts**:
   ```bash
   cat /etc/hosts | grep tumblr
   # Remove any incorrect entries
   ```

## Rate Limiting

### Identifying Rate Limits

**Signs you're rate limited**:
- HTTP 429 status codes
- Exponential backoff messages
- Downloads suddenly stop
- "Too many requests" errors

### Recovery from Rate Limiting

**Immediate steps**:
```bash
# 1. Stop the tool
Ctrl+C

# 2. Wait 5-10 minutes
sleep 600

# 3. Resume with conservative settings
tumblr-archiver myblog --rate 0.5 --concurrency 1
```

### Preventing Rate Limits

**Best practices**:

1. **Start conservative**:
   ```bash
   tumblr-archiver myblog --rate 1.0 --concurrency 2
   ```

2. **Gradually increase**:
   ```bash
   # If 1.0 works, try 1.5
   tumblr-archiver myblog --rate 1.5 --concurrency 2
   
   # If 1.5 works, try 2.0
   tumblr-archiver myblog --rate 2.0 --concurrency 3
   ```

3. **Monitor for issues**:
   ```bash
   # Use verbose to watch for 429s
   tumblr-archiver myblog --rate 2.0 --verbose
   ```

4. **Space out large archives**:
   ```bash
   # Archive multiple blogs with delays
   tumblr-archiver blog1 && sleep 300 && tumblr-archiver blog2
   ```

### Rate Limit Calculator

Effective request rate = `concurrency × rate`

**Safe combinations**:
- 1 worker × 0.5 req/s = 0.5 req/s (very safe)
- 2 workers × 1.0 req/s = 2 req/s (safe)
- 3 workers × 1.5 req/s = 4.5 req/s (moderate)
- 4 workers × 2.0 req/s = 8 req/s (aggressive)

**Risky combinations**:
- 5+ workers × 2.0+ req/s = 10+ req/s (likely to be rate limited)

## Manifest Issues

### Manifest Won't Load

**Error**:
```
ERROR: Failed to load manifest.json
```

**Solutions**:
```bash
# Check if file exists
ls -l downloads/myblog/manifest.json

# Check if valid JSON
python -m json.tool downloads/myblog/manifest.json

# If invalid, backup and start fresh
mv downloads/myblog/manifest.json downloads/myblog/manifest.json.bad
tumblr-archiver myblog --no-resume
```

### Manifest Out of Sync

**Symptom**: Files exist but manifest shows them as pending

**Solutions**:

1. **Let tool verify existing files**:
   ```bash
   # Tool checks checksums automatically
   tumblr-archiver myblog --output ./downloads
   ```

2. **Start with fresh manifest**:
   ```bash
   mv downloads/myblog/manifest.json downloads/myblog/manifest.json.old
   tumblr-archiver myblog --no-resume
   ```

### Manifest Too Large

**Symptom**: Slow manifest loading/saving for very large blogs

**Solutions**:

1. **Split large archives**:
   ```bash
   # Archive in chunks using date ranges (future feature)
   # Or archive reblogs separately
   tumblr-archiver myblog --exclude-reblogs
   ```

2. **Monitor manifest size**:
   ```bash
   ls -lh downloads/myblog/manifest.json
   du -h downloads/myblog/manifest.json
   ```

## Performance Problems

### High Memory Usage

**Diagnosis**:
```bash
# Monitor memory during download
# On Linux:
watch -n 1 'ps aux | grep tumblr-archiver'

# On macOS:
top -pid $(pgrep -f tumblr-archiver)
```

**Solutions**:

1. **Reduce concurrency**:
   ```bash
   tumblr-archiver myblog --concurrency 1
   ```

2. **Check for memory leaks**:
   ```bash
   # Update to latest version
   pip install --upgrade tumblr-archiver
   ```

3. **Split large archives**:
   ```bash
   # Archive in smaller batches
   # Process different blogs separately
   ```

### High CPU Usage

**Normal**: Some CPU usage is expected for:
- HTML parsing
- JSON processing
- Checksum calculation

**Abnormal**: 100% CPU usage constantly

**Solutions**:

1. **Reduce concurrency**:
   ```bash
   tumblr-archiver myblog --concurrency 2
   ```

2. **Check for runaway processes**:
   ```bash
   # Kill and restart
   pkill -9 tumblr-archiver
   tumblr-archiver myblog
   ```

### Slow HTML Parsing

**Symptom**: Long delays between "Found posts" messages

**Solutions**:

1. **Check lxml installation**:
   ```bash
   pip list | grep lxml
   
   # Reinstall if needed
   pip install --force-reinstall lxml
   ```

2. **Monitor with verbose**:
   ```bash
   tumblr-archiver myblog --verbose
   # Look for parsing bottlenecks
   ```

### Downloads Stall

**Symptom**: Progress bar stops moving, no errors

**Diagnosis**:
```bash
# Check if process is running
ps aux | grep tumblr-archiver

# Check network activity
# Linux: iftop
# macOS: nettop
```

**Solutions**:

1. **Kill and resume**:
   ```bash
   # Ctrl+C or kill process
   pkill tumblr-archiver
   
   # Resume
   tumblr-archiver myblog
   ```

2. **Check timeout settings**:
   ```bash
   # Increase timeout
   tumblr-archiver myblog --timeout 60.0
   ```

3. **Check for deadlock** (rare):
   ```bash
   # If persistent, report as bug
   # Include verbose logs
   ```

## Installation Issues

### Python Version Mismatch

**Error**:
```
ERROR: Python 3.10 or higher is required
```

**Solutions**:

1. **Check Python version**:
   ```bash
   python --version
   python3 --version
   python3.10 --version
   ```

2. **Install correct Python**:
   ```bash
   # macOS (using Homebrew)
   brew install python@3.11
   
   # Ubuntu/Debian
   sudo apt install python3.11
   
   # Or use pyenv
   pyenv install 3.11.0
   pyenv global 3.11.0
   ```

3. **Use specific Python version**:
   ```bash
   python3.11 -m pip install tumblr-archiver
   python3.11 -m tumblr_archiver myblog
   ```

### Dependency Installation Failures

**Error**:
```
ERROR: Failed building wheel for lxml
```

**Solutions**:

1. **Install build dependencies**:
   ```bash
   # Ubuntu/Debian
   sudo apt install python3-dev libxml2-dev libxslt1-dev
   
   # macOS
   brew install libxml2 libxslt
   
   # Then retry
   pip install tumblr-archiver
   ```

2. **Use pre-built wheels**:
   ```bash
   pip install --prefer-binary tumblr-archiver
   ```

3. **Update pip and setuptools**:
   ```bash
   pip install --upgrade pip setuptools wheel
   pip install tumblr-archiver
   ```

### Command Not Found

**Error**:
```
bash: tumblr-archiver: command not found
```

**Solutions**:

1. **Check PATH**:
   ```bash
   echo $PATH
   
   # Find where pip installs scripts
   python -m site --user-base
   ```

2. **Add to PATH**:
   ```bash
   # Add to ~/.bashrc or ~/.zshrc
   export PATH="$HOME/.local/bin:$PATH"
   
   # Reload shell
   source ~/.bashrc
   ```

3. **Run as module**:
   ```bash
   python -m tumblr_archiver myblog
   ```

4. **Use full path**:
   ```bash
   ~/.local/bin/tumblr-archiver myblog
   ```

## Data Issues

### Missing Media Files

**Symptom**: Some expected files not downloaded

**Reasons**:
1. Media deleted from Tumblr
2. Media not in Internet Archive
3. Media behind authentication
4. Parsing failed to extract URL

**Investigation**:

1. **Check manifest**:
   ```bash
   # Look for failed items
   cat downloads/myblog/manifest.json | grep '"status": "failed"'
   
   # Pretty print failed items
   jq '.media_items[] | select(.status=="failed")' downloads/myblog/manifest.json
   ```

2. **Check verbose logs**:
   ```bash
   tumblr-archiver myblog --verbose 2>&1 | tee archive.log
   grep -i "failed\|error" archive.log
   ```

3. **Verify manually**:
   ```bash
   # Visit post in browser
   # Check if media loads
   ```

### Duplicate Files

**Symptom**: Same file downloaded multiple times with different names

**Cause**: Different URLs pointing to same content

**Prevention**: Tool uses checksum deduplication

**Manual cleanup**:
```bash
# Find duplicates (requires fdupes)
fdupes -r downloads/myblog/

# Or use checksums
find downloads/myblog/ -type f -exec sha256sum {} \; | sort | uniq -w64 -D
```

### Corrupted Downloads

**Symptom**: Files exist but won't open/play

**Causes**:
1. Download interrupted
2. Disk error
3. Network corruption

**Solutions**:

1. **Re-download specific file**:
   ```bash
   # Remove corrupted file
   rm downloads/myblog/image_corrupt.jpg
   
   # Update manifest status to pending
   # Edit manifest.json or use --no-resume
   
   # Re-run
   tumblr-archiver myblog
   ```

2. **Verify checksums**:
   ```bash
   # Tool verifies checksums automatically
   # Corrupted files will be re-downloaded
   ```

3. **Check disk health**:
   ```bash
   # macOS
   diskutil verifyVolume /
   
   # Linux
   sudo fsck -n /dev/sda1
   ```

## Advanced Troubleshooting

### Enable Debug Logging

```python
# Create debug_run.py
import logging
import sys
from tumblr_archiver.orchestrator import Orchestrator
from tumblr_archiver.config import ArchiverConfig

logging.basicConfig(level=logging.DEBUG)

config = ArchiverConfig(
    blog_name="myblog",
    output_dir="./downloads",
    verbose=True
)

import asyncio
orchestrator = Orchestrator(config)
stats = asyncio.run(orchestrator.run())
print(stats)
```

### Inspect Manifest Programmatically

```python
import json

# Load manifest
with open('downloads/myblog/manifest.json') as f:
    manifest = json.load(f)

# Failed items
failed = [item for item in manifest['media_items'] if item['status'] == 'failed']
print(f"Failed: {len(failed)}")

# By status
from collections import Counter
status_counts = Counter(item['status'] for item in manifest['media_items'])
print(status_counts)
```

### Network Packet Capture

```bash
# Capture traffic (requires root)
sudo tcpdump -i any -w tumblr_capture.pcap 'host tumblr.com'

# In another terminal
tumblr-archiver myblog

# Analyze with Wireshark
wireshark tumblr_capture.pcap
```

### Profile Performance

```bash
# Time the execution
time tumblr-archiver myblog --dry-run

# Python profiling
python -m cProfile -o profile.stats -m tumblr_archiver myblog --dry-run

# Analyze
python -m pstats profile.stats
```

### Check System Resources

```bash
# Disk I/O
iostat -x 1

# Network usage
iftop  # or nettop on macOS

# CPU and memory
htop  # or top

# File descriptors
lsof -p $(pgrep -f tumblr-archiver)
```

## Getting Help

If troubleshooting doesn't resolve your issue:

1. **Gather information**:
   ```bash
   # Version
   tumblr-archiver --version
   
   # Python version
   python --version
   
   # OS info
   uname -a  # Linux/macOS
   
   # Dependencies
   pip list | grep -E "aiohttp|click|beautifulsoup4|lxml"
   
   # Run with verbose and save output
   tumblr-archiver myblog --verbose 2>&1 | tee debug.log
   ```

2. **Create minimal reproduction**:
   ```bash
   # Try dry-run first
   tumblr-archiver myblog --dry-run --verbose
   ```

3. **Open GitHub issue** with:
   - Clear description of problem
   - Steps to reproduce
   - Expected vs actual behavior
   - Debug log (sanitize private info)
   - System information

4. **Search existing issues**:
   - Check if already reported
   - Look for solutions in closed issues

## Prevention Checklist

For new archives:
- [ ] Test with `--dry-run` first
- [ ] Start with conservative settings
- [ ] Enable `--verbose` initially
- [ ] Ensure sufficient disk space
- [ ] Use stable network connection
- [ ] Keep resume enabled
- [ ] Monitor first ~100 files
- [ ] Adjust settings based on results

For troubleshooting:
- [ ] Check Python version (>=3.10)
- [ ] Verify blog exists and is public
- [ ] Check internet connection
- [ ] Look at verbose logs
- [ ] Inspect manifest for errors
- [ ] Try with minimal settings
- [ ] Test with different blog
- [ ] Update to latest version

## Related Documentation

- [Configuration Guide](configuration.md) - Detailed configuration options
- [Usage Guide](usage.md) - Common workflows
- [Architecture](architecture.md) - System internals
- [Contributing](../CONTRIBUTING.md) - Report bugs
