# Architecture Overview

Technical architecture documentation for Tumblr Archiver.

## Table of Contents

- [System Overview](#system-overview)
- [Architecture Diagram](#architecture-diagram)
- [Core Components](#core-components)
- [Data Flow](#data-flow)
- [Key Classes](#key-classes)
- [Design Patterns](#design-patterns)
- [Extension Points](#extension-points)
- [Async Architecture](#async-architecture)

## System Overview

Tumblr Archiver is an asynchronous Python application that orchestrates multiple components to efficiently download media content from Tumblr blogs with automatic fallback to the Internet Archive.

### High-Level Architecture

```
┌─────────────┐
│     CLI     │  User interaction
└──────┬──────┘
       │
┌──────▼──────┐
│   Config    │  Configuration management
└──────┬──────┘
       │
┌──────▼──────┐
│ Orchestrator│  Workflow coordination
└──┬───┬───┬──┘
   │   │   │
   │   │   └────────────┐
   │   │                │
   ▼   ▼                ▼
┌────┐ ┌────┐      ┌────────┐
│HTTP│ │ Web│      │Manifest│  State management
│    │ │Scr-│      │Manager │
└──┬─┘ │ape│      └────────┘
   │   └─┬──┘
   │     │
   │     ▼
   │  ┌────────┐
   │  │ Parser │       Media extraction
   │  └───┬────┘
   │      │
   │      ▼
   │  ┌────────┐
   └─►│Download│       Concurrent downloads
      │Workers │
      └────┬───┘
           │
           ▼
      ┌────────┐
      │Internet│       Fallback mechanism
      │Archive │
      └────────┘
```

### Key Characteristics

- **Asynchronous**: Built on `asyncio` for efficient I/O
- **Concurrent**: Multiple parallel download workers
- **Resilient**: Automatic retries with exponential backoff
- **Stateful**: Manifest-based progress tracking
- **Modular**: Clear separation of concerns

## Architecture Diagram

### Component Interaction

```
                          ┌──────────────┐
                          │  User / CLI  │
                          └──────┬───────┘
                                 │
                          ┌──────▼───────┐
                          │    Config    │
                          │  Validation  │
                          └──────┬───────┘
                                 │
                    ┌────────────▼────────────┐
                    │     Orchestrator        │
                    │  (Coordination Layer)   │
                    └────┬──────────┬─────────┘
                         │          │
        ┌────────────────┘          └──────────────┐
        │                                          │
  ┌─────▼─────┐                            ┌──────▼──────┐
  │  Scraper  │                            │  Manifest   │
  │  Component│                            │   Manager   │
  └─────┬─────┘                            └──────┬──────┘
        │                                         │
  ┌─────▼─────┐                                  │
  │ HTTP      │                                  │
  │ Client    │◄─────────────────────────────────┤
  └─────┬─────┘                                  │
        │                                        │
  ┌─────▼─────┐                                  │
  │  Parser   │                                  │
  │  (BS4)    │                                  │
  └─────┬─────┘                                  │
        │                                        │
  ┌─────▼─────┐                                  │
  │MediaQueue │                                  │
  │  (asyncio)│                                  │
  └─────┬─────┘                                  │
        │                                        │
  ┌─────▼─────┐                                  │
  │  Worker   │                                  │
  │   Pool    │◄─────────────────────────────────┘
  └─────┬─────┘
        │
  ┌─────▼─────┐
  │ Downloader│
  └─────┬─────┘
        │
     ┌──┴──┐
     │     │
┌────▼──┐ ┌▼─────────┐
│Tumblr │ │ Internet │
│ CDN   │ │ Archive  │
└───────┘ └──────────┘
```

## Core Components

### 1. CLI Module (`cli.py`)

**Purpose**: Command-line interface and argument parsing

**Responsibilities**:
- Parse command-line arguments using Click
- Validate user input
- Normalize blog identifiers
- Create configuration object
- Display help and version information

**Key Functions**:
- `cli()`: Main CLI entry point
- `normalize_blog_identifier()`: Normalize blog names/URLs

**Dependencies**:
- `click`: CLI framework
- `config`: Configuration management

### 2. Configuration Module (`config.py`)

**Purpose**: Configuration management and validation

**Responsibilities**:
- Store application settings
- Validate configuration values
- Provide defaults
- Generate blog URLs

**Key Classes**:
- `ArchiverConfig`: Main configuration dataclass
- `ConfigurationError`: Configuration validation errors

**Validation**:
- Blog name format
- Numeric field ranges
- Output directory permissions
- Backoff parameters

### 3. Orchestrator Module (`orchestrator.py`)

**Purpose**: Coordinate the entire archiving workflow

**Responsibilities**:
- Initialize all components
- Coordinate scraping and downloading
- Manage worker pool
- Collect and report statistics
- Handle high-level errors

**Key Classes**:
- `Orchestrator`: Main orchestration class
- `ArchiveStats`: Statistics collection
- `OrchestratorError`: Orchestration errors

**Workflow**:
1. Initialize HTTP client
2. Start scraper
3. Extract media items
4. Populate download queue
5. Start workers
6. Wait for completion
7. Generate statistics

### 4. Scraper Module (`scraper.py`)

**Purpose**: Scrape posts from Tumblr blogs

**Responsibilities**:
- Fetch blog pages
- Parse HTML content
- Extract post data
- Handle pagination
- Detect blog availability

**Key Classes**:
- `TumblrScraper`: Main scraping class
- `BlogNotFoundError`: Blog not found exception

**Strategy**:
- Scrapes public pages (no API key needed)
- Handles pagination automatically
- Respects rate limits
- Filters reblogs if configured

### 5. Parser Module (`parser.py`)

**Purpose**: Parse HTML and extract media URLs

**Responsibilities**:
- Parse Tumblr HTML structure
- Extract image URLs
- Extract video URLs
- Extract audio URLs
- Handle various post types

**Key Classes**:
- `TumblrParser`: HTML parsing class

**Technology**:
- BeautifulSoup4 for HTML parsing
- lxml for fast parsing
- Regular expressions for URL extraction

### 6. Downloader Module (`downloader.py`)

**Purpose**: Download media files

**Responsibilities**:
- Download individual files
- Verify downloads (checksums)
- Handle Tumblr CDN
- Fallback to Internet Archive
- Resume partial downloads

**Key Classes**:
- `MediaDownloader`: Main download class
- `DownloadError`: Download failures

**Features**:
- Streaming downloads for large files
- Checksum verification (SHA-256)
- Automatic retry on failure
- Progress reporting

### 7. Worker Module (`worker.py`)

**Purpose**: Concurrent download workers

**Responsibilities**:
- Process download queue
- Execute downloads concurrently
- Handle errors gracefully
- Update manifest
- Report progress

**Key Classes**:
- `DownloadWorker`: Worker implementation

**Concurrency Model**:
- Asyncio-based concurrency
- Semaphore for limiting parallelism
- Queue for work distribution
- Event-driven progress updates

### 8. Manifest Module (`manifest.py`)

**Purpose**: Track download progress and state

**Responsibilities**:
- Persist download state
- Track file status
- Enable resume capability
- Prevent duplicate downloads
- Store metadata

**Key Classes**:
- `ManifestManager`: Manifest operations
- `ManifestEntry`: Individual item tracking

**Storage Format**:
- JSON file format
- Atomic writes
- Corruption detection
- Schema versioning

### 9. HTTP Client Module (`http_client.py`)

**Purpose**: HTTP requests with rate limiting and retries

**Responsibilities**:
- Make HTTP requests
- Enforce rate limits
- Retry on failures
- Handle timeouts
- Manage session pooling

**Key Classes**:
- `AsyncHTTPClient`: Async HTTP client

**Features**:
- aiohttp-based async requests
- Automatic rate limiting
- Exponential backoff retries
- Connection pooling
- Timeout management

### 10. Internet Archive Module (`archive.py`)

**Purpose**: Fallback to Wayback Machine

**Responsibilities**:
- Check Archive availability
- Select best snapshot
- Retrieve archived media
- Handle Archive-specific URLs

**Key Classes**:
- `WaybackClient`: Archive API client
- `SnapshotSelector`: Choose best snapshot

**Strategy**:
- CDX API for snapshot lookup
- Timestamp-based selection
- Fallback chain: Latest → Closest → Any

### 11. Queue Module (`queue.py`)

**Purpose**: Work queue for distributing downloads

**Responsibilities**:
- Queue media items
- Priority handling
- Thread-safe operations
- Queue statistics

**Key Classes**:
- `MediaQueue`: Custom async queue

### 12. Models Module (`models.py`)

**Purpose**: Data models and types

**Key Classes**:
- `Post`: Tumblr post representation
- `MediaItem`: Individual media file
- `DownloadResult`: Download outcome

**Technology**:
- Pydantic for validation
- Type hints for safety
- Immutable where possible

## Data Flow

### 1. Initialization Phase

```
User Input → CLI → Config → Orchestrator
                              ↓
                   Init HTTP Client, Manifest,
                   Scraper, Downloader, Workers
```

### 2. Scraping Phase

```
Orchestrator → Scraper → HTTP Client → Tumblr
                  ↓
            Parse HTML → Extract Posts
                  ↓
            Parser → Extract Media URLs
                  ↓
            Media Queue ← Media Items
```

### 3. Download Phase

```
Media Queue → Workers (concurrent)
                ↓
         Check Manifest
                ↓
         Skip if Downloaded
                ↓
         Downloader → HTTP Client
                ↓
         Try Tumblr CDN
                ↓
         If Fails → Internet Archive
                ↓
         Save File → Update Manifest
```

### 4. Completion Phase

```
All Workers Complete
        ↓
Collect Statistics
        ↓
Generate Report
        ↓
Display to User
```

## Key Classes

### ArchiverConfig

```python
@dataclass
class ArchiverConfig:
    blog_name: str
    output_dir: Path
    concurrency: int = 2
    rate_limit: float = 1.0
    max_retries: int = 3
    # ... more fields
    
    def validate(self) -> None:
        """Validate configuration."""
    
    @property
    def blog_url(self) -> str:
        """Generate blog URL."""
```

**Role**: Central configuration storage and validation

### Orchestrator

```python
class Orchestrator:
    def __init__(self, config: ArchiverConfig):
        """Initialize with configuration."""
    
    async def run(self) -> ArchiveStats:
        """Execute archiving workflow."""
    
    async def _scrape_posts(self) -> List[Post]:
        """Scrape all posts from blog."""
    
    async def _download_media(self, items: List[MediaItem]) -> None:
        """Download all media items."""
```

**Role**: Coordinate all archiving operations

### TumblrScraper

```python
class TumblrScraper:
    def __init__(self, config: ArchiverConfig, client: AsyncHTTPClient):
        """Initialize scraper."""
    
    async def scrape_blog(self) -> List[Post]:
        """Scrape entire blog."""
    
    async def scrape_page(self, page_num: int) -> List[Post]:
        """Scrape single page."""
```

**Role**: Extract posts from Tumblr blog

### MediaDownloader

```python
class MediaDownloader:
    async def download(self, item: MediaItem) -> DownloadResult:
        """Download single media item."""
    
    async def _download_from_tumblr(self, url: str) -> bytes:
        """Download from Tumblr CDN."""
    
    async def _download_from_archive(self, url: str) -> bytes:
        """Download from Internet Archive."""
```

**Role**: Download and verify media files

### ManifestManager

```python
class ManifestManager:
    async def load(self) -> Manifest:
        """Load existing manifest."""
    
    async def save(self) -> None:
        """Save manifest to disk."""
    
    async def mark_completed(self, item: MediaItem, checksum: str) -> None:
        """Mark item as completed."""
    
    async def mark_failed(self, item: MediaItem, error: str) -> None:
        """Mark item as failed."""
```

**Role**: Persistent state management

### AsyncHTTPClient

```python
class AsyncHTTPClient:
    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make GET request with rate limiting."""
    
    async def download_stream(self, url: str, dest: Path) -> None:
        """Stream download to file."""
```

**Role**: HTTP operations with rate limiting

## Design Patterns

### 1. Orchestrator Pattern

**Implementation**: `Orchestrator` class coordinates all components

**Benefits**:
- Clear workflow control
- Centralized error handling
- Easy to test and modify

### 2. Worker Pool Pattern

**Implementation**: Multiple `DownloadWorker` instances process queue

**Benefits**:
- Concurrent downloads
- Resource control
- Fault isolation

### 3. Strategy Pattern

**Implementation**: Different download strategies (Tumblr, Archive)

**Benefits**:
- Flexible fallback
- Easy to add new sources
- Testable strategies

### 4. Repository Pattern

**Implementation**: `ManifestManager` abstracts persistence

**Benefits**:
- Decoupled storage
- Easy to change format
- Testable without I/O

### 5. Builder Pattern

**Implementation**: Configuration construction and validation

**Benefits**:
- Validated configuration
- Clear defaults
- Reusable configs

### 6. Async Context Manager

**Implementation**: Resource cleanup in HTTP client, workers

**Benefits**:
- Guaranteed cleanup
- Exception safety
- Resource management

## Extension Points

### 1. Custom Storage Backends

Implement `Storage` interface:

```python
from tumblr_archiver.storage import StorageBackend

class S3Storage(StorageBackend):
    async def save(self, data: bytes, path: Path) -> None:
        """Save to S3."""
    
    async def exists(self, path: Path) -> bool:
        """Check if file exists in S3."""
```

### 2. Custom Embed Downloaders

Implement `EmbedDownloader` interface:

```python
from tumblr_archiver.embed_downloaders import EmbedDownloader

class TikTokDownloader(EmbedDownloader):
    async def can_handle(self, url: str) -> bool:
        """Check if URL is TikTok."""
    
    async def download(self, url: str) -> bytes:
        """Download TikTok video."""
```

### 3. Custom Progress Reporters

Implement `ProgressReporter` interface:

```python
from tumblr_archiver.progress import ProgressReporter

class WebhookReporter(ProgressReporter):
    async def report(self, stats: DownloadStats) -> None:
        """Send progress to webhook."""
```

### 4. Custom Parsers

Extend `Parser` for custom post types:

```python
from tumblr_archiver.parser import TumblrParser

class CustomParser(TumblrParser):
    def extract_custom_media(self, post: Tag) -> List[str]:
        """Extract custom media types."""
```

### 5. Custom Rate Limiters

Implement `RateLimiter` interface:

```python
from tumblr_archiver.rate_limiter import RateLimiter

class AdaptiveRateLimiter(RateLimiter):
    async def acquire(self) -> None:
        """Adaptive rate limiting based on responses."""
```

## Async Architecture

### Event Loop

```python
# Main entry point
def main():
    config = parse_config()
    orchestrator = Orchestrator(config)
    
    # Run async workflow
    stats = asyncio.run(orchestrator.run())
    
    print(stats)
```

### Concurrency Model

```python
# Workers processing queue concurrently
async def download_all(queue: MediaQueue, workers: int):
    tasks = [
        asyncio.create_task(worker.run())
        for _ in range(workers)
    ]
    await asyncio.gather(*tasks)
```

### Rate Limiting

```python
# Token bucket algorithm
class RateLimiter:
    async def acquire(self):
        async with self._lock:
            await self._wait_for_token()
            self._consume_token()
```

### Resource Management

```python
# Context managers for cleanup
async with AsyncHTTPClient(config) as client:
    async with Orchestrator(config, client) as orch:
        stats = await orch.run()
# Automatic cleanup on exit
```

## Performance Considerations

### 1. Memory Management

- Stream downloads (no full file in memory)
- Limited queue size
- Garbage collection of completed items

### 2. Network Efficiency

- Connection pooling (aiohttp)
- HTTP/2 support
- Keep-alive connections
- DNS caching

### 3. I/O Optimization

- Async file I/O (aiofiles)
- Buffered writes
- Atomic operations

### 4. CPU Optimization

- Minimal parsing
- Efficient checksums
- Lazy evaluation

## Testing Architecture

### Unit Tests

- Test individual components
- Mock external dependencies
- Fast execution

### Integration Tests

- Test component interaction
- Use test fixtures
- Controlled environment

### End-to-End Tests

- Test full workflow
- Use test blogs
- Verify outputs

## Future Extension Ideas

1. **Plugin System**: Load custom components dynamically
2. **Database Storage**: Replace JSON manifest with SQLite
3. **Distributed Processing**: Support multiple machines
4. **Real-time Sync**: Monitor and archive new posts
5. **Web UI**: Browser-based interface
6. **API Server**: RESTful API for remote control
7. **Cloud Storage**: Direct upload to S3, GCS, etc.
8. **Advanced Filtering**: Complex post filtering rules

## Related Documentation

- [Configuration Reference](configuration.md)
- [Usage Guide](usage.md)
- [Contributing Guide](../CONTRIBUTING.md)
- [API Documentation](https://docs.example.com/api)

## Glossary

- **Async/Await**: Python's asynchronous programming model
- **Worker**: Task that processes queue items concurrently
- **Manifest**: JSON file tracking download state  
- **Orchestrator**: Central coordinator of workflow
- **Rate Limiter**: Controls request frequency
- **Fallback**: Alternative source when primary fails
- **Checksum**: Hash for verifying file integrity
