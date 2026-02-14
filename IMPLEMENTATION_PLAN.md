# Tumblr Media Archiver - Implementation Plan

## Overview
This plan breaks down the implementation into phases with parallelizable steps. Each step specifies what to build, which files to create/modify, and dependencies.

---

## Phase 1: Project Setup & Structure
**Goal:** Establish project foundation, dependencies, and folder structure.

### Step 1.1: Initialize Python Project Structure
**Parallelizable:** No (must be first)
**Dependencies:** None

**Tasks:**
- Create project directory structure
- Set up package management with pyproject.toml
- Configure development tools (linting, formatting, type checking)

**Files to Create:**
```
tumblr_archiver/
├── pyproject.toml           # Project metadata, dependencies, build config
├── setup.py                 # Legacy setup for editable installs
├── .gitignore              # Python, IDE, output folders
├── .env.example            # Example environment variables
├── README.md               # Project documentation
├── LICENSE                 # License file
├── Dockerfile              # Optional containerization
├── .github/
│   └── workflows/
│       └── test.yml        # CI/CD pipeline
├── tumblr_archiver/
│   ├── __init__.py         # Package init
│   ├── __main__.py         # Entry point for `python -m tumblr_archiver`
│   └── version.py          # Version string
├── tests/
│   ├── __init__.py
│   ├── conftest.py         # Pytest fixtures
│   └── fixtures/           # Test data
└── scripts/
    └── dev_setup.sh        # Development environment setup
```

**Dependencies to Define:**
- Core: `requests>=2.31.0`, `aiohttp>=3.9.0`, `click>=8.1.0`
- Utilities: `python-dotenv>=1.0.0`, `tqdm>=4.66.0`
- Testing: `pytest>=7.4.0`, `pytest-asyncio>=0.21.0`, `pytest-mock>=3.11.0`, `responses>=0.23.0`
- Quality: `black`, `ruff`, `mypy`

---

## Phase 2: Core Components (Parallelizable)
**Goal:** Build independent modules that can be developed simultaneously.

### Step 2.1: Configuration Management Module
**Parallelizable:** Yes
**Dependencies:** Step 1.1

**Tasks:**
- Parse CLI arguments using Click
- Load environment variables (.env support)
- Validate and merge configuration from multiple sources
- Define configuration dataclasses/models

**Files to Create:**
```
tumblr_archiver/
├── config.py               # Configuration models and validation
└── cli.py                  # Click CLI interface
```

**Key Functionality:**
- `Config` dataclass with all CLI options
- Priority: CLI args > ENV vars > defaults
- Validation: URL formats, rate limits, concurrency bounds
- API key handling (TUMBLR_API_KEY)

---

### Step 2.2: Tumblr API Client
**Parallelizable:** Yes (with Step 2.1, 2.3)
**Dependencies:** Step 1.1

**Tasks:**
- Implement Tumblr v2 API wrapper
- Handle authentication (API key + OAuth support)
- Paginate through all blog posts
- Extract media metadata from post responses
- Parse different post types (photo, video, link)

**Files to Create:**
```
tumblr_archiver/
├── clients/
│   ├── __init__.py
│   ├── tumblr_client.py    # Tumblr v2 API client
│   └── tumblr_models.py    # Data models for API responses
```

**Key Functionality:**
- `TumblrClient` class with methods:
  - `get_blog_info(blog_url)` → blog metadata, total_posts
  - `get_posts(blog_name, offset=0, limit=20)` → list of posts
  - `paginate_all_posts(blog_name)` → async generator
  - `extract_media_urls(post)` → list of media URLs with metadata
- Handle API errors, rate limits (429), network failures
- Support for different post types: photo, video, audio, link
- Extract all alt_sizes for images, video sources
- Detect external embeds (YouTube, Vimeo, etc.)

---

### Step 2.3: Internet Archive (Wayback) Client
**Parallelizable:** Yes (with Step 2.1, 2.2)
**Dependencies:** Step 1.1

**Tasks:**
- Implement Wayback Machine CDX API client
- Query for archived snapshots of URLs
- Parse CDX responses and select best snapshot
- Handle Availability API for capture status

**Files to Create:**
```
tumblr_archiver/
├── clients/
│   ├── wayback_client.py   # Internet Archive API client
│   └── wayback_models.py   # Data models for CDX responses
```

**Key Functionality:**
- `WaybackClient` class with methods:
  - `search_snapshots(url, limit=5)` → list of snapshots
  - `get_best_snapshot(url, prefer='highest_resolution')` → snapshot URL + timestamp
  - `download_snapshot(snapshot_url)` → bytes
  - `check_availability(url)` → availability status
- CDX API query with filters (mimetype, status codes)
- Prefer highest resolution captures
- Handle missing captures gracefully

---

### Step 2.4: Manifest Manager
**Parallelizable:** Yes (with Steps 2.1, 2.2, 2.3)
**Dependencies:** Step 1.1

**Tasks:**
- Define manifest JSON schema
- Load/save manifest.json
- Track download status per media item
- Support incremental updates (resume capability)
- Deduplication logic

**Files to Create:**
```
tumblr_archiver/
├── manifest.py             # Manifest management
└── models.py               # Media item data models
```

**Key Functionality:**
- `ManifestManager` class with methods:
  - `load(path)` → existing manifest or empty
  - `save(path)` → write manifest.json
  - `add_media_item(item)` → add/update item
  - `is_downloaded(media_id)` → check if already downloaded
  - `get_pending_items()` → items to download
  - `mark_completed(media_id, metadata)` → update status
- `MediaItem` model matching manifest schema:
  - post_id, post_url, timestamp
  - media_type, filename, byte_size, checksum
  - original_url, api_media_urls
  - media_missing_on_tumblr, retrieved_from
  - archive_snapshot_url, archive_snapshot_timestamp
  - status, notes
- SHA256 checksum calculation
- Deduplication by checksum

---

### Step 2.5: Rate Limiter & Retry Logic
**Parallelizable:** Yes (with all Step 2.x)
**Dependencies:** Step 1.1

**Tasks:**
- Token bucket or sliding window rate limiter
- Exponential backoff with jitter
- Retry logic for transient failures
- Respect Retry-After headers

**Files to Create:**
```
tumblr_archiver/
├── rate_limiter.py         # Rate limiting implementation
└── retry.py                # Retry logic with backoff
```

**Key Functionality:**
- `RateLimiter` class:
  - `async acquire(n=1)` → wait if needed before proceeding
  - Configurable: requests/second, burst size
- `RetryHandler` class:
  - `async retry_with_backoff(func, max_retries, base_backoff, max_backoff)`
  - Exponential backoff: 1s, 2s, 4s, 8s, 16s, 32s
  - Random jitter to avoid thundering herd
  - Handle 429 (rate limit), 5xx (server error)
  - Respect Retry-After header
- Logging: log each retry attempt with reason

---

### Step 2.6: Download Manager
**Parallelizable:** Yes (with all Step 2.x)
**Dependencies:** Step 1.1

**Tasks:**
- Download media files from URLs
- Verify downloads (checksums)
- Handle concurrent downloads with semaphore
- Track progress with progress bars

**Files to Create:**
```
tumblr_archiver/
├── downloader.py           # Core download logic
└── progress.py             # Progress tracking/display
```

**Key Functionality:**
- `MediaDownloader` class:
  - `async download_file(url, dest_path, expected_checksum=None)` → bool
  - Stream large files efficiently
  - Verify checksums after download
  - Handle partial downloads/resume (Range headers)
  - Return file metadata (size, checksum)
- `ProgressTracker` class:
  - Integration with tqdm or rich
  - Multiple concurrent progress bars
  - ETA estimation
  - Rate limit warnings

---

## Phase 3: Integration & Core Logic
**Goal:** Wire components together into the main application flow.

### Step 3.1: Media Recovery Engine
**Parallelizable:** No
**Dependencies:** Steps 2.2, 2.3, 2.4, 2.5, 2.6

**Tasks:**
- Implement fallback logic: Tumblr → Wayback → Missing
- Detect when Tumblr media is missing (4xx, placeholder images)
- Query Wayback for removed media
- Handle both direct media URLs and post page archives

**Files to Create:**
```
tumblr_archiver/
└── recovery.py             # Media recovery orchestration
```

**Key Functionality:**
- `MediaRecoveryEngine` class:
  - `async recover_media(media_item)` → recovery result
  - Try primary URL from Tumblr API
  - If 404/403/410: try alt_sizes URLs
  - If still missing: query Wayback for media URL
  - If no direct snapshot: fetch archived post page, parse media URLs
  - Download from best available source
  - Update manifest with provenance
- Placeholder image detection (common Tumblr placeholder hashes)

---

### Step 3.2: Main Orchestrator
**Parallelizable:** No
**Dependencies:** All Phase 2 steps + Step 3.1

**Tasks:**
- Main application entry point
- Coordinate all components
- Implement the full workflow
- Handle graceful shutdown and errors

**Files to Create:**
```
tumblr_archiver/
└── archiver.py             # Main orchestration logic
```

**Key Functionality:**
- `TumblrArchiver` class:
  - `async run(config)` → execution results
  - Workflow:
    1. Initialize clients (Tumblr, Wayback, downloader)
    2. Load existing manifest (if resume enabled)
    3. Fetch blog metadata (total_posts)
    4. Paginate through all posts
    5. Extract media from each post
    6. Check manifest: skip if already downloaded
    7. Attempt download with recovery fallback
    8. Update manifest after each successful download
    9. Save manifest periodically (every N items)
    10. Report statistics
- Concurrency control with asyncio.Semaphore
- Progress reporting
- Error collection and summary
- Graceful shutdown on Ctrl+C

---

### Step 3.3: CLI Integration
**Parallelizable:** No
**Dependencies:** Step 3.2

**Tasks:**
- Wire CLI to main orchestrator
- Add all command-line flags
- Implement dry-run mode
- Configure logging and verbosity

**Files to Modify:**
```
tumblr_archiver/
├── cli.py                  # Add all CLI commands and options
└── __main__.py             # Entry point wiring
```

**Key Functionality:**
- Click command with all flags from spec:
  - --url, --out, --resume
  - --concurrency, --rate
  - --include-reblogs, --exclude-reblogs
  - --download-embeds
  - --recover-removed-media
  - --wayback, --no-wayback, --wayback-max-snapshots
  - --tumblr-api-key
  - --oauth-consumer-key, --oauth-token
  - --dry-run, --verbose
- Configure logging based on verbosity
- Validate inputs before execution
- Display summary statistics after completion

---

## Phase 4: Testing
**Goal:** Comprehensive test coverage for all components.

### Step 4.1: Unit Tests for Core Components
**Parallelizable:** Yes (independent test suites)
**Dependencies:** Corresponding Phase 2 steps

**Tasks:**
- Test each module in isolation
- Mock external API calls
- Test edge cases and error handling

**Files to Create:**
```
tests/
├── unit/
│   ├── __init__.py
│   ├── test_config.py           # Config parsing and validation
│   ├── test_tumblr_client.py    # Tumblr API client
│   ├── test_wayback_client.py   # Wayback API client
│   ├── test_manifest.py         # Manifest management
│   ├── test_rate_limiter.py     # Rate limiting logic
│   ├── test_retry.py            # Retry and backoff
│   ├── test_downloader.py       # Download manager
│   └── test_recovery.py         # Recovery engine
```

**Test Coverage:**
- **Config:** CLI arg parsing, env var loading, validation errors
- **Tumblr Client:** Pagination, media extraction, error handling, different post types
- **Wayback Client:** CDX parsing, snapshot selection, availability checks
- **Manifest:** Load/save, deduplication, resume logic
- **Rate Limiter:** Token consumption, waiting behavior
- **Retry:** Backoff timing, max retries, jitter
- **Downloader:** File download, checksum verification, concurrent downloads
- **Recovery:** Fallback sequence, missing media detection

---

### Step 4.2: Integration Tests
**Parallelizable:** Partially (different test scenarios)
**Dependencies:** Phase 3 complete

**Tasks:**
- End-to-end tests with real or mocked Tumblr blogs
- Test full workflow from CLI to downloaded files
- Test resume capability
- Test Wayback fallback

**Files to Create:**
```
tests/
├── integration/
│   ├── __init__.py
│   ├── test_e2e_basic.py        # Basic end-to-end flow
│   ├── test_e2e_resume.py       # Resume functionality
│   ├── test_e2e_wayback.py      # Wayback fallback
│   └── test_e2e_public_blog.py  # Real public blog test
└── fixtures/
    ├── sample_blog_responses.json
    ├── sample_manifest.json
    └── sample_media/             # Small test images/videos
```

**Test Scenarios:**
1. **Basic flow:** Small blog (50 posts), all media available
2. **Resume:** Partially completed download, resume continues
3. **Wayback fallback:** Some media missing, recovered from archive
4. **Public blog:** Run against real Tumblr blog (acceptance test)
5. **Error handling:** Network failures, API errors, missing snapshots
6. **Deduplication:** Same image in multiple posts
7. **Rate limiting:** Verify rate limiter enforces limits
8. **External embeds:** YouTube/Vimeo links extracted

---

### Step 4.3: Test Infrastructure
**Parallelizable:** Yes (with Step 4.1, 4.2)
**Dependencies:** Step 1.1

**Tasks:**
- Set up pytest configuration
- Create test fixtures and helpers
- Mock HTTP responses
- Create sample test data

**Files to Create/Modify:**
```
tests/
├── conftest.py              # Pytest configuration and fixtures
└── helpers.py               # Test utilities
pytest.ini                   # Pytest settings
```

**Fixtures:**
- Mock Tumblr API responses (various post types)
- Mock Wayback CDX responses
- Sample media files (small images, GIFs, videos)
- Temporary directories for test outputs
- Mock configuration objects

---

## Phase 5: Documentation & Polish
**Goal:** User-facing documentation and final refinements.

### Step 5.1: README Documentation
**Parallelizable:** Yes (with Step 5.2, 5.3)
**Dependencies:** Phase 3 complete

**Tasks:**
- Comprehensive README with installation, usage, examples
- Document all CLI flags
- Explain Tumblr API key setup
- Describe Wayback fallback behavior
- Add troubleshooting section

**Files to Create/Modify:**
```
README.md                    # Main documentation
docs/
├── INSTALLATION.md          # Detailed setup instructions
├── USAGE.md                 # Usage examples and patterns
├── API_KEYS.md              # How to get Tumblr API keys
├── MANIFEST_SCHEMA.md       # Manifest format documentation
└── TROUBLESHOOTING.md       # Common issues and solutions
```

**Content Sections:**
- Introduction and features
- Installation (pip, pipx, Docker)
- Quick start example
- Obtaining Tumblr API key (step-by-step with screenshots)
- All CLI flags with descriptions
- Manifest schema explanation
- Wayback fallback explanation
- Rate limiting and politeness
- Resume functionality
- Example workflows
- FAQ and troubleshooting
- Security and compliance notice
- Contributing guidelines

---

### Step 5.2: Code Documentation
**Parallelizable:** Yes (with Step 5.1, 5.3)
**Dependencies:** Phase 3 complete

**Tasks:**
- Add docstrings to all public functions/classes
- Type hints throughout codebase
- Inline comments for complex logic
- Generate API documentation (Sphinx or similar)

**Files to Modify:**
- All Python files (add/improve docstrings)
- Create:
  ```
  docs/
  ├── api/
  │   └── index.rst
  └── conf.py               # Sphinx configuration
  ```

---

### Step 5.3: Logging & User Feedback
**Parallelizable:** Yes (with Step 5.1, 5.2)
**Dependencies:** Phase 3 complete

**Tasks:**
- Implement comprehensive logging
- Add progress indicators
- User-friendly error messages
- Summary statistics after completion

**Files to Modify:**
```
tumblr_archiver/
├── logging_config.py        # Logging setup
└── all relevant modules     # Add logging statements
```

**Logging Levels:**
- INFO: Major workflow steps, progress updates
- WARNING: Rate limit hits, retries, missing media
- ERROR: Failures, API errors
- DEBUG: Detailed request/response info (verbose mode)

**User Feedback:**
- Progress bars for downloads
- ETA estimation
- Rate limit notifications
- Summary: total posts, media found, downloaded, missing, errors
- Manifest location
- Next steps advice

---

### Step 5.4: Dockerfile & CI/CD
**Parallelizable:** Yes (with Step 5.1, 5.2, 5.3)
**Dependencies:** Phase 3 complete

**Tasks:**
- Create production-ready Dockerfile
- Set up GitHub Actions for testing
- Add pre-commit hooks

**Files to Create:**
```
Dockerfile                   # Container image
.dockerignore               # Docker build exclusions
.github/
└── workflows/
    ├── test.yml            # Run tests on PR
    ├── release.yml         # Build/publish releases
    └── lint.yml            # Code quality checks
.pre-commit-config.yaml     # Pre-commit hooks
```

**Docker Image:**
- Multi-stage build (builder + runtime)
- Minimal Python base image
- Non-root user
- Volume mount for output directory
- Environment variable support

**CI/CD:**
- Run tests on every PR
- Lint and type checking
- Coverage reports
- Automated releases on tags

---

## Phase 6: Optional Enhancements
**Goal:** Nice-to-have features for improved functionality.

### Step 6.1: Enhanced Media Detection
**Tasks:**
- Better placeholder image detection
- Support more external embed types
- Extract media from post HTML/markdown

**Files to Modify:**
```
tumblr_archiver/
├── clients/tumblr_client.py
└── recovery.py
```

---

### Step 6.2: Performance Optimizations
**Tasks:**
- Connection pooling
- Persistent HTTP sessions
- Async/await throughout
- Batch operations where possible

**Files to Modify:**
- All client files
- downloader.py
- archiver.py

---

### Step 6.3: Advanced CLI Features
**Tasks:**
- Interactive mode with prompts
- Configuration file support (YAML/TOML)
- Multiple blogs in one run
- Filtering by date range, post type

**Files to Create/Modify:**
```
tumblr_archiver/
├── cli.py
└── config_file.py           # Config file parsing
```

---

## Implementation Order Summary

### Recommended Execution Path:

**Phase 1 (Sequential):**
1. Step 1.1 → Complete project setup first

**Phase 2 (Parallel Execution):**
Execute all Step 2.x simultaneously:
- Step 2.1 (Config)
- Step 2.2 (Tumblr Client)
- Step 2.3 (Wayback Client)
- Step 2.4 (Manifest)
- Step 2.5 (Rate Limiter)
- Step 2.6 (Downloader)

**Phase 3 (Sequential):**
1. Step 3.1 (Recovery Engine) - depends on Phase 2
2. Step 3.2 (Main Orchestrator) - depends on Step 3.1
3. Step 3.3 (CLI Integration) - depends on Step 3.2

**Phase 4 (Mostly Parallel):**
- Step 4.3 (Test Infrastructure) first
- Then parallel: Step 4.1 (Unit Tests) + Step 4.2 (Integration Tests)

**Phase 5 (Fully Parallel):**
Execute all Step 5.x simultaneously:
- Step 5.1 (README)
- Step 5.2 (Code Docs)
- Step 5.3 (Logging)
- Step 5.4 (Docker/CI)

**Phase 6 (Optional):**
- Implement as needed or time permits

---

## Key Dependencies Graph

```
1.1 (Setup)
  ├─→ 2.1 (Config)
  ├─→ 2.2 (Tumblr) ─┐
  ├─→ 2.3 (Wayback) ├─→ 3.1 (Recovery) ─→ 3.2 (Orchestrator) ─→ 3.3 (CLI)
  ├─→ 2.4 (Manifest)┤
  ├─→ 2.5 (Limiter) ─┤
  └─→ 2.6 (Download)─┘

1.1 ─→ 4.3 (Test Infra) ─┬─→ 4.1 (Unit Tests)
                         └─→ 4.2 (Integration Tests)

3.3 (CLI) ─┬─→ 5.1 (README)
           ├─→ 5.2 (Docs)
           ├─→ 5.3 (Logging)
           └─→ 5.4 (Docker/CI)
```

---

## Success Criteria Checklist

- [ ] CLI accepts all required flags and environment variables
- [ ] Tumblr API client paginates through all posts (verified against `total_posts`)
- [ ] Media extraction works for photo, video, and link post types
- [ ] Wayback fallback successfully recovers removed media
- [ ] Manifest.json matches specified schema
- [ ] Resume functionality skips already-downloaded items
- [ ] Rate limiting enforced (default 1 req/sec)
- [ ] Exponential backoff with jitter on failures
- [ ] Deduplication works across posts
- [ ] Unit tests achieve >80% coverage
- [ ] Integration test runs against real public blog (>50 posts)
- [ ] README includes API key setup instructions
- [ ] Docker image builds and runs successfully
- [ ] Security/compliance notice displayed to users

---

## Estimated Timeline

**Assuming 1 developer:**
- Phase 1: 4-6 hours
- Phase 2: 16-24 hours (parallelizable to ~8-12 dev hours with multiple contributors)
- Phase 3: 12-16 hours
- Phase 4: 12-16 hours (parallelizable to ~6-8 dev hours)
- Phase 5: 8-12 hours (parallelizable to ~3-4 dev hours)
- **Total: 52-74 hours** (~7-10 working days)

**With 3 developers (parallel execution):**
- Phase 1: 4-6 hours
- Phase 2: 8-12 hours
- Phase 3: 12-16 hours
- Phase 4: 6-8 hours
- Phase 5: 3-4 hours
- **Total: 33-46 hours** (~4-6 working days)

---

## Critical Path Items

1. **Tumblr API pagination** (Step 2.2) - Must correctly handle all pagination schemes
2. **Media URL extraction** (Step 2.2) - Must capture all variants (alt_sizes, video sources)
3. **Wayback CDX query** (Step 2.3) - Must correctly parse and select best snapshots
4. **Recovery fallback logic** (Step 3.1) - Core differentiator of the tool
5. **Manifest persistence** (Step 2.4) - Critical for resume functionality
6. **Integration test** (Step 4.2) - Acceptance criteria validation

---

## Risk Mitigation

**Risk:** Tumblr API changes or rate limits block development
- **Mitigation:** Build comprehensive mocks early; use cached responses for testing

**Risk:** Wayback API is slow or unreliable
- **Mitigation:** Implement aggressive timeouts; make Wayback optional (--no-wayback)

**Risk:** Complex async concurrency causes race conditions
- **Mitigation:** Extensive unit tests for concurrent scenarios; use proper locking for manifest writes

**Risk:** Large blogs (100k+ posts) cause memory issues
- **Mitigation:** Stream processing; don't load all posts into memory; save manifest frequently

**Risk:** Media files are huge (multi-GB videos)
- **Mitigation:** Stream downloads; chunked transfer; progress tracking; allow resume of partial files

---

This plan provides a clear roadmap from project initialization to production-ready tool with comprehensive testing and documentation. The parallelization opportunities in Phase 2 and Phase 5 allow for efficient team collaboration or faster solo development when focusing on independent components.
