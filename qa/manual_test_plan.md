# Manual Test Plan - Tumblr Archiver

Version: 1.0  
Date: February 13, 2026  
Status: Phase 10 - Final Testing & Validation

## Overview

This document provides a comprehensive manual testing checklist for the Tumblr Archiver tool. Use this to validate functionality that requires human inspection or cannot be easily automated.

## Test Environment Setup

### Prerequisites
- [ ] Python 3.10+ installed
- [ ] Internet connection available
- [ ] At least 1GB free disk space
- [ ] Access to a test Tumblr blog (preferably your own or a small public one)

### Installation Test

1. **Clean Installation from Source**
   ```bash
   # Clone repository
   git clone https://github.com/parker/tumblr-archiver.git
   cd tumblr-archiver
   
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install
   pip install -e .
   ```
   - [ ] Installation completes without errors
   - [ ] Command `tumblr-archiver --help` works
   - [ ] Version is displayed: `tumblr-archiver --version`

2. **Installation with Development Dependencies**
   ```bash
   pip install -e ".[dev]"
   ```
   - [ ] All dev dependencies install successfully
   - [ ] pytest command is available

3. **Docker Installation Test**
   ```bash
   docker build -t tumblr-archiver .
   ```
   - [ ] Docker image builds successfully
   - [ ] No errors in build output

## Functional Testing

### Test 1: Basic Archive Operation

**Objective:** Verify basic archiving works end-to-end

**Steps:**
1. Choose a small test blog (e.g., `staff` or create a test blog with 5-10 posts)
2. Run command:
   ```bash
   tumblr-archiver testblog --output ./test-output --verbose
   ```
3. Monitor output

**Expected Results:**
- [ ] Progress messages are displayed
- [ ] No Python exceptions or crashes
- [ ] Directory `./test-output/testblog` is created
- [ ] Media files are downloaded
- [ ] `manifest.json` file is created
- [ ] Final statistics are displayed
- [ ] Process completes successfully

**Manual Validation:**
- [ ] Open `manifest.json` - valid JSON structure
- [ ] Check media files exist and are not corrupted
- [ ] Verify at least one post is in manifest
- [ ] Check file sizes are reasonable (not 0 bytes)

### Test 2: Dry Run Mode

**Objective:** Verify dry run doesn't download files

**Steps:**
1. Run command:
   ```bash
   tumblr-archiver testblog --output ./dry-run-test --dry-run --verbose
   ```

**Expected Results:**
- [ ] Process completes
- [ ] Log shows "DRY RUN" indicators
- [ ] No media files are downloaded (directory may exist but no .jpg/.png/.mp4)
- [ ] Statistics show what _would_ be downloaded
- [ ] No manifest.json created (or empty manifest)

### Test 3: Resume Capability

**Objective:** Verify interrupted downloads can resume

**Steps:**
1. Start archiving a blog:
   ```bash
   tumblr-archiver testblog --output ./resume-test
   ```
2. Let it download 2-3 files, then interrupt with Ctrl+C
3. Check `manifest.json` exists and has some posts
4. Re-run the exact same command:
   ```bash
   tumblr-archiver testblog --output ./resume-test
   ```

**Expected Results:**
- [ ] Second run detects existing manifest
- [ ] Already downloaded files are skipped (check logs)
- [ ] Statistics show "skipped" count
- [ ] New files are downloaded
- [ ] No duplicate files created
- [ ] Manifest is updated with new posts

### Test 4: Internet Archive Fallback

**Objective:** Verify fallback to Archive.org works

**Steps:**
1. Find or create a blog with old/deleted content
2. Run archiver with fallback enabled (default):
   ```bash
   tumblr-archiver oldblog --output ./archive-test --verbose
   ```
3. Monitor logs for Archive.org queries

**Expected Results:**
- [ ] When Tumblr returns 404, Archive.org is queried
- [ ] Log shows "Searching for snapshots of..."
- [ ] If snapshots found, they are downloaded
- [ ] Manifest shows `retrieved_from: "internet_archive"`
- [ ] Manifest includes `archive_snapshot_url`

**Manual Validation:**
- [ ] Open `manifest.json`
- [ ] Find media with `"retrieved_from": "internet_archive"`
- [ ] Verify `archive_snapshot_url` is present and valid
- [ ] Check that snapshot URL contains `web.archive.org`

### Test 5: Rate Limiting

**Objective:** Verify rate limiting prevents server overload

**Steps:**
1. Run with default rate limit:
   ```bash
   tumblr-archiver testblog --output ./rate-test
   ```
2. Observe timing between requests in logs

**Expected Results:**
- [ ] Requests are spaced out (not instant)
- [ ] No 429 "Too Many Requests" errors
- [ ] Log shows reasonable delays
- [ ] Process doesn't overwhelm server

**Manual Validation:**
- [ ] Check logs for timestamps
- [ ] Verify gaps of ~1-2 seconds between requests
- [ ] No error messages about rate limiting

### Test 6: Configuration Options

**Objective:** Test various CLI options work correctly

**Test 6a: Concurrency**
```bash
tumblr-archiver testblog --output ./test --concurrency 1
tumblr-archiver testblog --output ./test --concurrency 4
```
- [ ] Higher concurrency completes faster (for blogs with many posts)
- [ ] No race conditions or corrupted files

**Test 6b: Exclude Reblogs**
```bash
tumblr-archiver testblog --output ./test --exclude-reblogs
```
- [ ] Only original posts are archived
- [ ] Manifest shows `is_reblog: false` for all posts

**Test 6c: Custom Rate Limit**
```bash
tumblr-archiver testblog --output ./test --rate 0.5
```
- [ ] Slower rate limit is respected
- [ ] Requests take longer

**Test 6d: Timeout Setting**
```bash
tumblr-archiver testblog --output ./test --timeout 5
```
- [ ] Timeout is enforced
- [ ] Slow requests may fail (expected)

### Test 7: URL Formats

**Objective:** Verify different blog URL formats work

**Test different inputs:**
```bash
# Just blog name
tumblr-archiver myblog --output ./test1

# Full URL
tumblr-archiver https://myblog.tumblr.com --output ./test2

# Domain only
tumblr-archiver myblog.tumblr.com --output ./test3
```

**Expected Results:**
- [ ] All three formats work identically
- [ ] Same blog is archived in all cases
- [ ] No errors about invalid blog name

### Test 8: Error Handling

**Objective:** Verify graceful error handling

**Test 8a: Non-existent Blog**
```bash
tumblr-archiver nonexistentblog123456789 --output ./test
```
- [ ] Clear error message displayed
- [ ] No Python traceback (unless --verbose)
- [ ] Exits with non-zero code

**Test 8b: Invalid Output Directory**
```bash
tumblr-archiver testblog --output /root/nopermission
```
- [ ] Permission error is caught and reported
- [ ] Clear error message (not just exception)

**Test 8c: Network Interruption**
- [ ] Disconnect network during download
- [ ] Reconnect and resume
- [ ] Process recovers or exits gracefully

### Test 9: Manifest Validation

**Objective:** Verify manifest.json correctness

**Steps:**
1. Archive a small blog completely
2. Open `manifest.json` in text editor

**Manual Checks:**
- [ ] Valid JSON (no syntax errors)
- [ ] Has `blog_name` field
- [ ] Has `archive_date` timestamp
- [ ] Has `total_posts` and `total_media` counts
- [ ] Has `posts` array
- [ ] Each post has required fields:
  - [ ] `post_id`
  - [ ] `post_url`
  - [ ] `timestamp`
  - [ ] `is_reblog`
  - [ ] `media_items` array
- [ ] Each media item has:
  - [ ] `filename`
  - [ ] `media_type` (image/gif/video)
  - [ ] `original_url`
  - [ ] `retrieved_from` (tumblr or internet_archive)
  - [ ] `status` (downloaded/archived/missing/error)
  - [ ] `checksum` (if downloaded)
  - [ ] `byte_size` (if downloaded)

**Checksum Validation:**
```bash
# On macOS/Linux
shasum -a 256 test-output/testblog/*.jpg

# Compare with checksums in manifest.json
```
- [ ] Checksums match actual files

### Test 10: Media File Validation

**Objective:** Verify downloaded files are valid

**Steps:**
1. Navigate to output directory
2. Inspect downloaded media

**Manual Checks:**
- [ ] Image files (.jpg, .png, .gif) open correctly
- [ ] Videos (.mp4) play correctly
- [ ] File sizes are reasonable (not 0 bytes or suspiciously small)
- [ ] Filenames follow pattern: `{post_id}_{number}.{ext}`
- [ ] No duplicate files
- [ ] No corrupted files

**File Organization:**
- [ ] All media in `{output}/{blog_name}/` directory
- [ ] `manifest.json` in same directory
- [ ] No stray files in unexpected locations

## Performance Testing

### Test 11: Performance with Small Blog

**Objective:** Baseline performance metrics

**Steps:**
1. Archive a blog with ~10 posts, ~20 media items
2. Measure time and resources

**Metrics to Record:**
- [ ] Total time: ________ seconds
- [ ] Download speed: ________ MB/s
- [ ] Memory usage: < 500 MB
- [ ] CPU usage: Moderate (not 100% sustained)

### Test 12: Performance with Medium Blog

**Objective:** Validate performance at scale

**Steps:**
1. Archive a blog with ~50 posts, ~100 media items
2. Monitor system resources

**Expected:**
- [ ] Completes in reasonable time (< 30 minutes with default settings)
- [ ] Memory usage stable (no memory leaks)
- [ ] Progress updates are regular
- [ ] No performance degradation over time

## Integration Testing

### Test 13: Python API Usage

**Objective:** Verify Python API works for integration

**Steps:**
1. Create test script:
```python
import asyncio
from tumblr_archiver import archive_blog

async def main():
    stats = await archive_blog(
        blog_name="testblog",
        output_dir="./api-test",
    )
    print(f"Downloaded {stats.downloaded} files")

asyncio.run(main())
```
2. Run script: `python test_api.py`

**Expected Results:**
- [ ] Script runs without errors
- [ ] Stats object is returned
- [ ] Files are downloaded
- [ ] API is usable from Python code

### Test 14: CI/CD Integration

**Objective:** Verify tool works in automated environments

**Steps:**
1. Run in CI-like environment:
```bash
# Non-interactive, no TTY
tumblr-archiver testblog --output ./ci-test --verbose 2>&1 | tee log.txt
```

**Expected Results:**
- [ ] Runs without user input
- [ ] Progress works without TTY
- [ ] Logs are captured
- [ ] Exit code indicates success/failure

## Edge Cases & Special Scenarios

### Test 15: Empty Blog

```bash
tumblr-archiver emptyblog --output ./empty-test
```
- [ ] Handles gracefully
- [ ] Creates empty manifest
- [ ] No errors

### Test 16: Blog with Only Reblogs

```bash
tumblr-archiver reblogblog --exclude-reblogs --output ./reblog-test
```
- [ ] Completes without errors
- [ ] Empty or minimal archive
- [ ] Clear message about no original content

### Test 17: Blog with Embedded Content

**Test blog with YouTube/Vimeo embeds**
- [ ] Embedded URLs are extracted
- [ ] Manifest includes embed information
- [ ] No crashes on complex embed markup

### Test 18: Special Characters in Filenames

**Test blog with posts containing special characters**
- [ ] Filenames are sanitized
- [ ] No invalid characters in filenames
- [ ] Files can be created on all OSes

### Test 19: Very Large Media Files

**Test with blog containing large videos (>50MB)**
- [ ] Large files download completely
- [ ] Progress indicators work
- [ ] Checksums are correct
- [ ] No memory issues

### Test 20: Concurrent Runs

**Run two instances simultaneously** (different blogs):
```bash
tumblr-archiver blog1 --output ./test1 &
tumblr-archiver blog2 --output ./test2 &
```
- [ ] Both complete successfully
- [ ] No file conflicts
- [ ] No race conditions

## Cross-Platform Testing

### Test 21: macOS
- [ ] Installation works
- [ ] All features functional
- [ ] File paths work correctly

### Test 22: Linux
- [ ] Installation works
- [ ] All features functional
- [ ] Permissions handled correctly

### Test 23: Windows
- [ ] Installation works (PowerShell & CMD)
- [ ] Path handling works (backslashes)
- [ ] All features functional
- [ ] File locking works correctly

## Documentation Testing

### Test 24: README Accuracy

**Validate README.md instructions:**
- [ ] Installation steps work as written
- [ ] Example commands run successfully
- [ ] Screenshots/examples are current
- [ ] Links are valid

### Test 25: Help Documentation

```bash
tumblr-archiver --help
```
- [ ] Help text is clear and accurate
- [ ] All options are documented
- [ ] Examples are provided
- [ ] No typos or errors

### Test 26: Error Messages

**Throughout testing, verify error messages are:**
- [ ] Clear and understandable
- [ ] Point to solution or next steps
- [ ] Not just raw exceptions (unless --verbose)
- [ ] Helpful for debugging

## Security & Safety

### Test 27: Rate Limiting Safety

- [ ] Default settings don't overwhelm servers
- [ ] Respectful timeout values
- [ ] User-Agent is set appropriately
- [ ] No aggressive behavior

### Test 28: Data Integrity

- [ ] Checksums prevent corrupted files
- [ ] Atomic writes prevent partial files
- [ ] Manifest updates are consistent
- [ ] No data loss on interruption

### Test 29: Privacy Considerations

- [ ] No credentials stored
- [ ] No sensitive data logged
- [ ] Respects robots.txt (if applicable)
- [ ] Public content only

## Final Validation Checklist

### Acceptance Criteria

- [ ] **Requirement 1:** All media retrieved locally OR from Internet Archive
- [ ] **Requirement 2:** manifest.json correctly reflects provenance
- [ ] **Requirement 3:** Resume capability works
- [ ] **Requirement 4:** Rate limiting prevents 429s

### Quality Metrics

- [ ] Test coverage > 80%
- [ ] No critical bugs
- [ ] Performance is acceptable
- [ ] Documentation is complete
- [ ] User experience is smooth

### Sign-off

**Tester:** ______________________  
**Date:** ______________________  
**Overall Result:** ☐ PASS  ☐ FAIL  ☐ PASS WITH ISSUES

**Issues Found:**
```
1.
2.
3.
```

**Recommendations:**
```
1.
2.
3.
```

---

## Notes

- Mark each checkbox as completed during testing
- Document any failures or unexpected behavior
- Include screenshots or logs for issues
- Update this document if new test cases are needed
- Version control this document with the codebase
