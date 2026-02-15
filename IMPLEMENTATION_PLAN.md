# Tumblr Media Downloader - Implementation Plan

## 1. Project File Structure

```
tumblr-archive/
├── pyproject.toml                 # Modern Python packaging configuration
├── setup.py                       # Fallback setup for older pip versions
├── README.md                      # User documentation
├── .gitignore                     # Git ignore patterns
├── requirements.txt               # Production dependencies
├── requirements-dev.txt           # Development dependencies
├── src/
│   └── tumblr_downloader/
│       ├── __init__.py           # Package initialization, version
│       ├── __main__.py           # CLI entry point (python -m tumblr_downloader)
│       ├── cli.py                # Argument parsing and main orchestration
│       ├── api_client.py         # Tumblr v1 API interaction
│       ├── media_selector.py     # Resolution selection logic
│       ├── downloader.py         # Parallel download manager
│       ├── manifest.py           # Manifest generation and management
│       ├── utils.py              # Shared utilities (filename sanitization, etc.)
│       └── rate_limiter.py       # Rate limiting and backoff logic
├── tests/
│   ├── __init__.py
│   ├── conftest.py               # Pytest fixtures
│   ├── test_api_client.py        # API client unit tests
│   ├── test_media_selector.py    # Media selection unit tests
│   ├── test_downloader.py        # Downloader unit tests
│   ├── test_manifest.py          # Manifest unit tests
│   ├── test_utils.py             # Utilities unit tests
│   ├── test_cli.py               # CLI integration tests
│   └── fixtures/                 # Test data (sample API responses)
│       ├── sample_post_photo.json
│       ├── sample_post_photoset.json
│       ├── sample_post_video.json
│       └── sample_post_audio.json
└── examples/
    └── sample_manifest.json      # Example output for documentation
```

---

## 2. Core Modules and Responsibilities

### 2.1 `cli.py` - Command-Line Interface
**Responsibilities:**
- Parse command-line arguments using `argparse`
- Validate required arguments (`--blog`, `--out`)
- Set up logging based on `--verbose` flag
- Orchestrate the entire download workflow
- Handle top-level error reporting

**Key Functions:**
- `parse_args() -> argparse.Namespace`: Parse CLI arguments
- `main() -> int`: Main entry point, returns exit code
- `setup_logging(verbose: bool) -> None`: Configure logging

---

### 2.2 `api_client.py` - Tumblr API Client
**Responsibilities:**
- Interact with Tumblr v1 public API endpoints
- Paginate through all posts of a blog
- Handle HTTP errors and retries
- Parse API responses into structured data

**Key Classes/Functions:**
- `class TumblrAPIClient`:
  - `__init__(blog_name: str, rate_limiter: RateLimiter)`
  - `get_all_posts(max_posts: Optional[int] = None) -> Iterator[Dict]`: Generator yielding posts
  - `_fetch_posts_page(offset: int, limit: int = 50) -> Dict`: Fetch single page
  - `_parse_post(post_data: Dict) -> Dict`: Extract relevant fields from raw post

**API Endpoint:**
- `https://{blog}.tumblr.com/api/read/json?start={offset}&num={limit}`
- No authentication required for public blogs

---

### 2.3 `media_selector.py` - Media Selection Logic
**Responsibilities:**
- Extract all media URLs from a post
- Select highest-resolution variant for images
- Handle different media types (photo, photoset, video, audio)
- Apply tie-breaking rules for resolution selection

**Key Classes/Functions:**
- `class MediaAsset`:
  - `url: str`
  - `width: Optional[int]`
  - `height: Optional[int]`
  - `file_size: Optional[int]`
  - `media_type: str` (photo, video, audio, gif)
  - `quality_hint: str` (original, high, medium, etc.)
  
- `def extract_media_from_post(post: Dict) -> List[MediaAsset]`: Extract all media
- `def select_best_resolution(candidates: List[MediaAsset]) -> MediaAsset`: Apply selection logic
- `def calculate_resolution_score(asset: MediaAsset) -> Tuple[int, int, str]`: Tie-breaking tuple

**Resolution Selection Logic:**
1. Primary: largest width × height
2. Secondary: largest file_size (if available via HEAD request or URL hints)
3. Tertiary: prefer URLs with "original" or "1280" in path

---

### 2.4 `downloader.py` - Parallel Download Manager
**Responsibilities:**
- Download media files concurrently
- Skip existing files (idempotency)
- Retry failed downloads with exponential backoff
- Track download progress and statistics
- Dry-run mode support

**Key Classes/Functions:**
- `class DownloadManager`:
  - `__init__(output_dir: Path, concurrency: int, dry_run: bool, rate_limiter: RateLimiter)`
  - `download_media(media_list: List[Tuple[MediaAsset, str]]) -> List[DownloadResult]`: Download multiple files
  - `_download_single(url: str, dest_path: Path, retries: int = 3) -> DownloadResult`
  - `_file_exists(dest_path: Path) -> bool`: Check if file already downloaded
  
- `class DownloadResult`:
  - `success: bool`
  - `url: str`
  - `filename: str`
  - `bytes_downloaded: int`
  - `error: Optional[str]`

**Concurrency:**
- Use `concurrent.futures.ThreadPoolExecutor` with configurable max_workers
- Thread-safe progress tracking

---

### 2.5 `manifest.py` - Manifest Management
**Responsibilities:**
- Generate manifest.json with post metadata
- Track downloaded files per post
- Support incremental updates (append-only for idempotency)
- Validate manifest structure

**Key Classes/Functions:**
- `class ManifestManager`:
  - `__init__(output_dir: Path)`
  - `load_existing() -> Dict`: Load existing manifest if present
  - `add_post_entry(post_id: str, entry: PostEntry) -> None`: Add/update entry
  - `save() -> None`: Write manifest.json atomically
  
- `class PostEntry(TypedDict)`:
  - `post_id: str`
  - `post_url: str`
  - `timestamp: str` (ISO 8601)
  - `tags: List[str]`
  - `media: List[MediaEntry]`
  
- `class MediaEntry(TypedDict)`:
  - `media_sources: List[str]` (all candidate URLs)
  - `chosen_url: str`
  - `downloaded_filename: str`
  - `width: Optional[int]`
  - `height: Optional[int]`
  - `bytes: Optional[int]`
  - `media_type: str`

**Manifest Format:**
```json
{
  "version": "1.0",
  "blog": "example-blog",
  "generated_at": "2026-02-15T10:30:00Z",
  "posts": {
    "123456789": {
      "post_id": "123456789",
      "post_url": "https://example-blog.tumblr.com/post/123456789",
      "timestamp": "2024-01-15T12:00:00Z",
      "tags": ["art", "photography"],
      "media": [
        {
          "media_sources": [
            "https://.../_1280.jpg",
            "https://.../_500.jpg"
          ],
          "chosen_url": "https://.../_1280.jpg",
          "downloaded_filename": "123456789_image.jpg",
          "width": 1280,
          "height": 1920,
          "bytes": 524288,
          "media_type": "photo"
        }
      ]
    }
  }
}
```

---

### 2.6 `rate_limiter.py` - Rate Limiting and Backoff
**Responsibilities:**
- Implement token bucket or sliding window rate limiting
- Exponential backoff for HTTP 429 and 5xx errors
- Respectful default rate limits (configurable)

**Key Classes/Functions:**
- `class RateLimiter`:
  - `__init__(requests_per_second: float = 2.0)`
  - `acquire() -> None`: Block until request is allowed
  - `handle_retry_after(retry_after_seconds: int) -> None`: Pause for HTTP 429
  
- `def exponential_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float`

**Rate Limiting Strategy:**
- Default: 2 requests/second for API calls
- Downloads: respect 429 headers, default 5 concurrent connections
- Exponential backoff: 1s, 2s, 4s, 8s, 16s, 32s, 60s (max)

---

### 2.7 `utils.py` - Shared Utilities
**Responsibilities:**
- Filename sanitization and generation
- URL parsing and validation
- Path handling utilities
- Common helpers

**Key Functions:**
- `def sanitize_filename(filename: str) -> str`: Remove invalid chars, limit length
- `def generate_output_filename(post_id: str, original_url: str) -> str`: Create `postID_filename`
- `def extract_blog_name(blog_arg: str) -> str`: Parse blog name from URL or name
- `def format_bytes(bytes: int) -> str`: Human-readable file size
- `def parse_tumblr_image_url(url: str) -> Dict[str, Any]`: Extract resolution hints from URL

---

## 3. Implementation Steps (In Order)

### Phase 1: Project Scaffolding
**Step 1.1: Initialize Project Structure**
- **Files Created:**
  - `pyproject.toml`
  - `setup.py`
  - `README.md`
  - `.gitignore`
  - `requirements.txt`
  - `requirements-dev.txt`
  - `src/tumblr_downloader/__init__.py`

**Step 1.2: Set Up Version and Package Metadata**
- **Files Modified:**
  - `src/tumblr_downloader/__init__.py` - Add `__version__`
  - `pyproject.toml` - Configure package metadata, entry points

---

### Phase 2: Core Utilities (Foundation Layer)
**Step 2.1: Implement Utilities Module**
- **Files Created:**
  - `src/tumblr_downloader/utils.py`
- **Files Modified:** None
- **Tests Created:**
  - `tests/test_utils.py`

**Step 2.2: Implement Rate Limiter**
- **Files Created:**
  - `src/tumblr_downloader/rate_limiter.py`
- **Files Modified:** None
- **Tests Created:**
  - `tests/test_rate_limiter.py` (implicit in conftest)

---

### Phase 3: API Client Layer
**Step 3.1: Implement Tumblr API Client**
- **Files Created:**
  - `src/tumblr_downloader/api_client.py`
- **Files Modified:** None
- **Tests Created:**
  - `tests/test_api_client.py`
  - `tests/fixtures/sample_post_photo.json`
  - `tests/fixtures/sample_post_photoset.json`
  - `tests/fixtures/sample_post_video.json`

**Step 3.2: Handle API Edge Cases**
- **Files Modified:**
  - `src/tumblr_downloader/api_client.py` - Add error handling, pagination logic
- **Tests Modified:**
  - `tests/test_api_client.py` - Add edge case tests

---

### Phase 4: Media Selection Logic
**Step 4.1: Implement Media Asset Model**
- **Files Created:**
  - `src/tumblr_downloader/media_selector.py` - Add MediaAsset dataclass
- **Files Modified:** None
- **Tests Created:**
  - `tests/test_media_selector.py` - Basic structure

**Step 4.2: Implement Media Extraction**
- **Files Modified:**
  - `src/tumblr_downloader/media_selector.py` - Add extraction functions
- **Tests Modified:**
  - `tests/test_media_selector.py` - Add extraction tests

**Step 4.3: Implement Resolution Selection Algorithm**
- **Files Modified:**
  - `src/tumblr_downloader/media_selector.py` - Add selection logic
- **Tests Modified:**
  - `tests/test_media_selector.py` - Add comprehensive selection tests

---

### Phase 5: Download Manager
**Step 5.1: Implement Basic Download Logic**
- **Files Created:**
  - `src/tumblr_downloader/downloader.py` - Basic single-file download
- **Files Modified:** None
- **Tests Created:**
  - `tests/test_downloader.py` - Mock download tests

**Step 5.2: Add Parallel Download Support**
- **Files Modified:**
  - `src/tumblr_downloader/downloader.py` - Add ThreadPoolExecutor
- **Tests Modified:**
  - `tests/test_downloader.py` - Add concurrency tests

**Step 5.3: Add Retry Logic and Idempotency**
- **Files Modified:**
  - `src/tumblr_downloader/downloader.py` - Add retry, skip existing files
- **Tests Modified:**
  - `tests/test_downloader.py` - Add retry and idempotency tests

---

### Phase 6: Manifest Generation
**Step 6.1: Implement Manifest Data Models**
- **Files Created:**
  - `src/tumblr_downloader/manifest.py` - TypedDict models
- **Files Modified:** None
- **Tests Created:**
  - `tests/test_manifest.py` - Basic structure

**Step 6.2: Implement Manifest Manager**
- **Files Modified:**
  - `src/tumblr_downloader/manifest.py` - Add ManifestManager class
- **Tests Modified:**
  - `tests/test_manifest.py` - Add save/load tests

**Step 6.3: Add Incremental Update Support**
- **Files Modified:**
  - `src/tumblr_downloader/manifest.py` - Support existing manifest merging
- **Tests Modified:**
  - `tests/test_manifest.py` - Add incremental update tests

---

### Phase 7: CLI and Orchestration
**Step 7.1: Implement Argument Parsing**
- **Files Created:**
  - `src/tumblr_downloader/cli.py` - Argument parser
  - `src/tumblr_downloader/__main__.py` - Entry point
- **Files Modified:** None
- **Tests Created:**
  - `tests/test_cli.py` - Argument parsing tests

**Step 7.2: Implement Main Workflow Orchestration**
- **Files Modified:**
  - `src/tumblr_downloader/cli.py` - Connect all components
- **Tests Modified:**
  - `tests/test_cli.py` - Integration tests

**Step 7.3: Add Logging and Progress Reporting**
- **Files Modified:**
  - `src/tumblr_downloader/cli.py` - Add logging, progress bars (optional)
  - `src/tumblr_downloader/downloader.py` - Add progress callbacks
- **Tests Modified:** None (manual testing)

---

### Phase 8: Polish and Documentation
**Step 8.1: Add Dry-Run Mode**
- **Files Modified:**
  - `src/tumblr_downloader/cli.py` - Add --dry-run flag handling
  - `src/tumblr_downloader/downloader.py` - Skip actual downloads in dry-run
- **Tests Modified:**
  - `tests/test_cli.py` - Add dry-run tests

**Step 8.2: Complete README Documentation**
- **Files Modified:**
  - `README.md` - Add installation, usage, examples
- **Files Created:**
  - `examples/sample_manifest.json`

**Step 8.3: Add Error Handling and Edge Cases**
- **Files Modified:**
  - All modules - Comprehensive error handling
  - `src/tumblr_downloader/cli.py` - User-friendly error messages

---

### Phase 9: Testing and Validation
**Step 9.1: End-to-End Manual Testing**
- Test against real Tumblr blogs (multi-resolution images, videos, etc.)
- Verify idempotency by re-running
- Test --max-posts, --concurrency flags

**Step 9.2: Add Integration Tests**
- **Tests Created:**
  - `tests/test_integration.py` - Full workflow tests with mocked API

**Step 9.3: Performance Testing**
- Test memory usage with large blogs (10k+ posts)
- Profile bottlenecks

---

## 4. Dependencies

### 4.1 Production Dependencies (requirements.txt)
```
# HTTP client - requests is ubiquitous and reliable
requests>=2.31.0,<3.0.0

# No additional heavy dependencies needed
# Standard library provides: argparse, json, concurrent.futures, pathlib, logging
```

### 4.2 Development Dependencies (requirements-dev.txt)
```
# Testing
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-mock>=3.11.0
responses>=0.23.0  # Mock HTTP responses

# Code quality
black>=23.7.0
flake8>=6.1.0
mypy>=1.5.0
isort>=5.12.0

# Optional: Progress bars (can be made optional with try/except)
# tqdm>=4.66.0
```

### 4.3 Rationale for Minimal Dependencies
- **requests**: Industry-standard HTTP library, stable and well-maintained
- **Standard library only**: argparse, json, concurrent.futures, pathlib, logging, typing
- **No heavy frameworks**: Avoid aiohttp, scrapy, etc. to keep footprint small
- **No optional dependencies required**: Progress bars can use standard output

---

## 5. Testing Strategy

### 5.1 Unit Testing Approach
**Coverage Goals:** >85% line coverage

**Per-Module Tests:**

1. **test_utils.py**
   - Test filename sanitization (special chars, length limits)
   - Test blog name extraction (URL vs name)
   - Test URL parsing for resolution hints

2. **test_api_client.py**
   - Mock HTTP responses using `responses` library
   - Test pagination logic (multiple pages, empty results)
   - Test error handling (404, 429, 500, network errors)
   - Test post parsing from JSON fixtures

3. **test_media_selector.py** (Critical)
   - Test extraction from different post types (photo, photoset, video, audio)
   - Test resolution selection with various scenarios:
     - Clearly different resolutions (_1280 vs _500)
     - Same resolution, different file sizes
     - Same metrics, prefer "original" in URL
   - Test edge cases (no dimensions, missing URLs)

4. **test_downloader.py**
   - Mock file I/O and HTTP responses
   - Test parallel download coordination
   - Test retry logic (exponential backoff)
   - Test idempotency (skip existing files)
   - Test dry-run mode

5. **test_manifest.py**
   - Test manifest creation and serialization
   - Test loading existing manifest
   - Test incremental updates (merging new posts)
   - Test manifest validation

6. **test_cli.py**
   - Test argument parsing (required/optional args)
   - Test validation (invalid blog names, missing output dir)
   - Integration tests with mocked API client

### 5.2 Integration Testing
**test_integration.py:**
- Full workflow test: API → selection → download → manifest
- Use fixtures for API responses
- Mock file system operations
- Verify manifest.json correctness

### 5.3 Manual Acceptance Tests
**Test Cases:**

1. **Multi-Resolution Image Test**
   - Blog: Find blog with `_1280`, `_500`, `_250` variants
   - Expected: Only `_1280` downloaded
   - Verify: Check files and manifest.json

2. **Video Resolution Test**
   - Blog: Posts with video content
   - Expected: Highest bitrate/resolution video downloaded
   - Verify: File size and manifest entry

3. **Idempotency Test**
   - Run CLI twice on same blog
   - Expected: Second run skips all files, completes quickly
   - Verify: No duplicate downloads, manifest unchanged

4. **Large Blog Test**
   - Blog: 1000+ posts
   - Expected: Completes without memory issues
   - Verify: Memory usage <500MB throughout

5. **Error Recovery Test**
   - Simulate network interruption mid-download
   - Expected: Partial downloads, clean error messages
   - Re-run: Resumes from last successful post

### 5.4 Test Data (Fixtures)
**tests/fixtures/**
- `sample_post_photo.json`: Single image post with multiple resolutions
- `sample_post_photoset.json`: Post with 10 images
- `sample_post_video.json`: Video post with multiple formats
- `sample_post_audio.json`: Audio post
- Create from real Tumblr API responses (anonymized)

### 5.5 Testing Commands
```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=tumblr_downloader --cov-report=html tests/

# Run specific test file
pytest tests/test_media_selector.py -v

# Run with markers (if used)
pytest -m "not slow" tests/
```

---

## 6. Implementation Timeline Estimate

**Assumptions:** Single developer, part-time work (10-15 hours/week)

```
Phase 1 (Scaffolding):          2-3 hours
Phase 2 (Utilities):            3-4 hours
Phase 3 (API Client):           5-6 hours
Phase 4 (Media Selection):      6-8 hours (critical logic)
Phase 5 (Download Manager):     6-8 hours
Phase 6 (Manifest):             4-5 hours
Phase 7 (CLI Orchestration):    5-6 hours
Phase 8 (Polish):               3-4 hours
Phase 9 (Testing/Validation):   5-7 hours
-------------------------------------------
Total:                          39-51 hours (1-1.5 weeks full-time)
```

---

## 7. Critical Implementation Notes

### 7.1 Tumblr v1 API Specifics
**API Endpoint Pattern:**
```
https://{blog}.tumblr.com/api/read/json?start={offset}&num={limit}
```
- `start`: Post offset (0, 50, 100, ...)
- `num`: Posts per page (max 50)
- Response: JSONP format (wrap in `var tumblr_api_read = {...};`)
- Must strip JSONP wrapper before parsing

**Post Types:**
- `photo`: Single image or photoset
- `video`: Embedded or native video
- `audio`: Audio file or embedded player
- Extract media URLs from `photo-url` fields (multiple resolutions)

### 7.2 Resolution Selection Algorithm Details
**Implementation Priority:**
```python
def calculate_resolution_score(asset: MediaAsset) -> tuple:
    """Return sortable tuple: (area, filesize, quality_rank)"""
    area = (asset.width or 0) * (asset.height or 0)
    filesize = asset.file_size or 0
    
    # Quality ranking: original=3, 1280=2, 500=1, else=0
    quality_rank = 3 if 'original' in asset.url.lower() \
                   else 2 if '1280' in asset.url \
                   else 1 if '500' in asset.url \
                   else 0
    
    return (area, filesize, quality_rank)

# Usage: sorted(candidates, key=calculate_resolution_score, reverse=True)[0]
```

### 7.3 Filename Generation
**Pattern:** `{post_id}_{sanitized_original_name}.{ext}`

```python
def generate_output_filename(post_id: str, original_url: str) -> str:
    """Extract filename from URL, sanitize, prefix with post_id"""
    parsed = urlparse(original_url)
    original_name = Path(parsed.path).name  # e.g., "image_1280.jpg"
    
    # Remove resolution suffix if present (_1280, _500, etc.)
    name_clean = re.sub(r'_\d+(?=\.\w+$)', '', original_name)
    
    # Sanitize (remove special chars, limit length)
    sanitized = sanitize_filename(name_clean)
    
    return f"{post_id}_{sanitized}"
```

### 7.4 Memory Optimization for Large Blogs
**Strategies:**
- Use generators/iterators for post fetching (avoid loading all posts into memory)
- Stream downloads to disk (don't buffer full files in memory)
- Process posts in batches (fetch page → download media → write manifest → repeat)
- Manifest: Build incrementally, write atomically at end

### 7.5 Error Handling Philosophy
- **Fail fast on:** Invalid blog names, inaccessible output directory
- **Continue on:** Individual media download failures (log and skip)
- **Retry with backoff:** Transient network errors, rate limits
- **Log verbosely:** All errors with context (post ID, URL, error message)

---

## 8. Verification Checklist (Post-Implementation)

- [ ] CLI runs with `--blog` and `--out` (required args)
- [ ] Downloads complete for blog with 100+ posts
- [ ] Only highest-resolution images downloaded (verified manually)
- [ ] `manifest.json` generated with correct schema
- [ ] Re-running CLI skips existing files (idempotent)
- [ ] `--dry-run` shows what would be downloaded without downloading
- [ ] `--max-posts` limits number of posts processed
- [ ] `--concurrency` controls parallel downloads
- [ ] `--verbose` provides detailed logging
- [ ] Error messages are clear and actionable
- [ ] Memory usage remains low (<500MB) for large blogs
- [ ] Unit tests pass with >85% coverage
- [ ] Manual acceptance tests pass
- [ ] README includes clear installation and usage instructions
- [ ] Package installable via `pip install .`
- [ ] Console script entry point works (`tumblr-downloader --help`)

---

## 9. Future Enhancements (Out of Scope for Initial Release)

1. **Authentication Support:** Add OAuth for private blogs
2. **Resume Capability:** Save progress state, resume interrupted downloads
3. **Incremental Updates:** Re-run to download only new posts since last run
4. **Filtering Options:** Download only certain media types (--videos-only)
5. **Output Formats:** Support for organized subdirectories (by date, type)
6. **Progress Bar:** Integrate tqdm for better UX
7. **Database Backend:** Replace manifest.json with SQLite for very large archives
8. **Docker Image:** Pre-built container for easy deployment
9. **Web UI:** Simple web interface for non-CLI users
10. **Tumblr v2 API:** Support authenticated API with better rate limits

---

**End of Implementation Plan**

*This plan is designed for systematic implementation with clear phase boundaries and file-level tracking for parallel development coordination.*
