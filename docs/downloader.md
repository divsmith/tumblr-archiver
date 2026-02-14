# Download Manager

A robust, production-ready download management system for the Tumblr Media Archiver with support for checksums, resume capabilities, and data integrity verification.

## Features

- **Async Downloads**: Built with `aiohttp` and `aiofiles` for efficient async I/O
- **SHA256 Checksums**: Automatic checksum computation during download
- **Resume Support**: Continue partial downloads using HTTP Range requests
- **Rate Limiting**: Token bucket rate limiter to respect server limits
- **Retry Logic**: Exponential backoff with jitter for transient failures
- **Content Verification**: Validate content type, file size, and detect placeholders
- **Progress Tracking**: Optional progress callbacks for UI integration
- **Media-Specific Methods**: Dedicated methods for images, videos, and GIFs
- **Error Handling**: Comprehensive exception hierarchy for different error types
- **Concurrent Downloads**: Control max concurrent downloads with semaphore

## Architecture

### Core Components

#### DownloadManager
Main class for managing file downloads.

```python
from tumblr_archiver.downloader import DownloadManager

async with DownloadManager(
    output_dir="./downloads",
    rate_limiter=rate_limiter,
    retry_strategy=retry_strategy,
    max_concurrent=5,
    timeout=300
) as manager:
    result = await manager.download_image(url, post_id)
```

#### RateLimiter
Token bucket rate limiter for throttling requests.

```python
from tumblr_archiver.downloader import RateLimiter

limiter = RateLimiter(rate=5.0)  # 5 requests per second
await limiter.acquire(1)  # Acquire one token
```

#### RetryStrategy
Exponential backoff retry strategy with jitter.

```python
from tumblr_archiver.downloader import RetryStrategy

strategy = RetryStrategy(
    max_retries=3,
    base_backoff=1.0,
    max_backoff=32.0
)

result = await strategy.execute(async_function, *args)
```

#### DownloadResult
Dataclass containing download results.

```python
@dataclass
class DownloadResult:
    filename: str
    byte_size: int
    checksum: str  # SHA256
    duration: float
    source: str  # 'tumblr', 'internet_archive', 'external'
    status: str  # 'success', 'missing', 'error'
    error_message: Optional[str] = None
    media_missing_on_tumblr: bool = False
```

### Exception Hierarchy

```
DownloadError (base)
├── MediaNotFoundError (404, 403, 410)
└── IntegrityError (checksum/verification failures)
```

## Usage Examples

### Basic Download

```python
import asyncio
from tumblr_archiver.downloader import DownloadManager

async def main():
    async with DownloadManager(output_dir="./downloads") as manager:
        result = await manager.download_image(
            url="https://64.media.tumblr.com/image.jpg",
            post_id="123456789",
            metadata={"source": "tumblr"}
        )
        
        if result.status == "success":
            print(f"Downloaded: {result.filename}")
            print(f"Size: {result.byte_size} bytes")
            print(f"Checksum: {result.checksum}")

asyncio.run(main())
```

### Download with Progress Tracking

```python
def progress_callback(bytes_downloaded, total_bytes):
    if total_bytes > 0:
        percent = (bytes_downloaded / total_bytes) * 100
        print(f"\rProgress: {percent:.1f}%", end="")

result = await manager.download_file(
    url="https://example.com/large_file.jpg",
    filename="output.jpg",
    progress_callback=progress_callback
)
```

### Concurrent Downloads

```python
# Download multiple files concurrently
urls = [
    ("https://example.com/img1.jpg", "post1"),
    ("https://example.com/img2.jpg", "post2"),
    ("https://example.com/img3.jpg", "post3"),
]

tasks = [
    manager.download_image(url, post_id)
    for url, post_id in urls
]

results = await asyncio.gather(*tasks, return_exceptions=True)
```

### Resume Partial Download

```python
# Resume a partial download (uses HTTP Range requests)
result = await manager.download_with_resume(
    url="https://example.com/large_file.mp4",
    filename="video.mp4",
    metadata={"source": "tumblr"}
)
```

### Custom Configuration

```python
from tumblr_archiver.downloader import (
    DownloadManager, RateLimiter, RetryStrategy
)

# Custom rate limiting
rate_limiter = RateLimiter(rate=10.0)  # 10 req/sec

# Custom retry strategy
retry_strategy = RetryStrategy(
    max_retries=5,
    base_backoff=2.0,
    max_backoff=60.0
)

async with DownloadManager(
    output_dir="./output",
    rate_limiter=rate_limiter,
    retry_strategy=retry_strategy,
    max_concurrent=10,  # 10 concurrent downloads
    timeout=600  # 10 minute timeout
) as manager:
    # Your download code here
    pass
```

### Error Handling

```python
result = await manager.download_image(url, post_id)

if result.status == "success":
    print(f"Downloaded successfully: {result.filename}")
    
elif result.status == "missing":
    print(f"Media not found: {result.error_message}")
    if result.media_missing_on_tumblr:
        print("Media confirmed missing from Tumblr")
        # Try alternate source (e.g., Internet Archive)
        
elif result.status == "error":
    print(f"Download error: {result.error_message}")
    # Log error, retry later, etc.
```

## API Reference

### DownloadManager

#### Constructor

```python
DownloadManager(
    output_dir: str,
    rate_limiter: Optional[RateLimiter] = None,
    retry_strategy: Optional[RetryStrategy] = None,
    max_concurrent: int = 5,
    timeout: int = 300
)
```

#### Methods

##### download_file()

```python
async def download_file(
    url: str,
    filename: str,
    metadata: Optional[Dict[str, Any]] = None,
    verify_size: bool = True,
    verify_content_type: bool = True,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    expected_checksum: Optional[str] = None
) -> DownloadResult
```

Download a file with full verification.

**Parameters:**
- `url`: URL to download from
- `filename`: Target filename (relative to output_dir)
- `metadata`: Optional metadata dictionary
- `verify_size`: Verify file size is reasonable
- `verify_content_type`: Verify Content-Type header
- `progress_callback`: Progress callback function
- `expected_checksum`: Expected SHA256 checksum

**Returns:** `DownloadResult` object

##### download_image()

```python
async def download_image(
    url: str,
    post_id: str,
    metadata: Optional[Dict[str, Any]] = None,
    index: int = 0,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> DownloadResult
```

Download an image file with validation.

##### download_video()

```python
async def download_video(
    url: str,
    post_id: str,
    metadata: Optional[Dict[str, Any]] = None,
    index: int = 0,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> DownloadResult
```

Download a video file with validation.

##### download_gif()

```python
async def download_gif(
    url: str,
    post_id: str,
    metadata: Optional[Dict[str, Any]] = None,
    index: int = 0,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> DownloadResult
```

Download an animated GIF file.

##### download_with_resume()

```python
async def download_with_resume(
    url: str,
    filename: str,
    metadata: Optional[Dict[str, Any]] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> DownloadResult
```

Download with resume support using HTTP Range requests.

##### generate_filename()

```python
def generate_filename(
    url: str,
    post_id: str,
    media_type: str,
    index: int = 0
) -> str
```

Generate a unique filename for downloaded media.

Pattern: `{post_id}_{index}_{hash_prefix}.{ext}`

### RateLimiter

Token bucket rate limiter.

```python
RateLimiter(rate: float)

async def acquire(n: int = 1)
```

### RetryStrategy

Exponential backoff retry strategy.

```python
RetryStrategy(
    max_retries: int = 3,
    base_backoff: float = 1.0,
    max_backoff: float = 32.0
)

async def execute(func: Callable, *args, **kwargs) -> Any
```

## Implementation Details

### Filename Generation

Files are named using the pattern: `{post_id}_{index}_{hash_prefix}.{ext}`

- `post_id`: Tumblr post ID
- `index`: Index for multiple media in same post
- `hash_prefix`: 8-character MD5 hash of URL (for uniqueness)
- `ext`: Original file extension from URL

Collisions are handled by appending an incremental suffix.

### Checksum Computation

SHA256 checksums are computed during download (streaming) to avoid reading the file twice:

```python
checksum_hash = hashlib.sha256()
async for chunk in response.content.iter_chunked(8192):
    await f.write(chunk)
    checksum_hash.update(chunk)
checksum = checksum_hash.hexdigest()
```

### Placeholder Detection

The downloader detects Tumblr placeholder images:
- Empty files (0 bytes)
- Files with known placeholder checksums
- Files smaller than 43 bytes (minimum valid image)
- Images smaller than 100 bytes
- Videos smaller than 1 KB

### Resume Support

Resume is implemented using HTTP Range requests:

1. Check if partial file exists
2. Send Range header: `Range: bytes={existing_size}-`
3. If server returns 206 (Partial Content), continue download
4. Re-hash existing content and append new content
5. If resume fails, fall back to regular download

### Rate Limiting

Token bucket algorithm:
- Tokens replenish at constant rate
- Each request consumes 1 token
- Blocks if no tokens available
- Thread-safe with asyncio.Lock

### Retry Logic

Exponential backoff with jitter:
- Base backoff increases exponentially: 1s, 2s, 4s, 8s...
- Capped at max_backoff
- Random jitter (0-10% of backoff) prevents thundering herd
- Retries on `aiohttp.ClientError` and `asyncio.TimeoutError`

## Testing

Comprehensive test suite with 30 tests covering:

- Rate limiting behavior
- Retry strategies
- Filename generation
- Checksum computation
- Placeholder detection
- Content verification
- Error handling
- Context manager
- Integration scenarios

Run tests:

```bash
pytest tests/test_downloader.py -v
```

## Dependencies

- `aiohttp>=3.9.0` - Async HTTP client
- `aiofiles>=23.0.0` - Async file I/O
- Python 3.8+

## Performance Considerations

- **Concurrent Downloads**: Use `max_concurrent` to control parallelism
- **Memory Usage**: Files are streamed in 8KB chunks
- **Rate Limiting**: Adjust `rate` parameter to respect server limits
- **Timeout**: Set appropriate timeout for large files

## Future Enhancements

- [ ] HTTP/2 support for multiplexing
- [ ] Bandwidth throttling
- [ ] Download queue with priority
- [ ] Persistent checksum cache
- [ ] Mirror/CDN fallback support
- [ ] Progress persistence for resume across restarts
