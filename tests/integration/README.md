# Integration Tests for Tumblr Archiver

This directory contains end-to-end integration tests that verify the complete archival workflow.

## Structure

```
tests/integration/
├── __init__.py                    # Package marker
├── conftest.py                    # Shared fixtures and helpers
├── test_end_to_end.py            # Complete workflow tests
├── test_resume.py                # Resume capability tests
└── test_archive_fallback.py      # Internet Archive fallback tests

tests/mocks/
├── __init__.py                    # Package marker
└── tumblr_server.py              # Mock Tumblr and Wayback servers
```

## Test Categories

### End-to-End Tests (`test_end_to_end.py`)
Tests the complete scrape → download → manifest workflow:
- Basic workflow with simple blog
- Multiple media types (images, GIFs, videos)
- Pagination handling
- Reblog detection
- Empty blog handling
- Failed download scenarios
- Manifest structure validation

### Resume Tests (`test_resume.py`)
Tests the resume and incremental download capability:
- Resume after interruption
- Skip already downloaded files
- Detect new posts added since last run  
- Re-download deleted/corrupted files
- Checksum verification
- Manifest updates during resume

### Fallback Tests (`test_archive_fallback.py`)
Tests Internet Archive Wayback Machine fallback:
- Automatic fallback on 404
- Mixed working/failing URLs
- Handling missing archive snapshots
- Using old archived snapshots
- Correct source attribution in manifest
- Priority (Tumblr first, then Archive)

## Running Tests

### All Integration Tests
```bash
pytest tests/integration/ -v
```

### Specific Test File
```bash
pytest tests/integration/test_end_to_end.py -v
```

### Single Test Case
```bash
pytest tests/integration/test_end_to_end.py::test_end_to_end_basic_workflow -v
```

### With Coverage
```bash
pytest tests/integration/ --cov=tumblr_archiver --cov-report=html
```

### Parallel Execution
```bash
pytest tests/integration/ -n auto  # Requires pytest-xdist
```

## Fixtures

### From `conftest.py`

#### Configuration
- `sample_blog_name` - Test blog name ("testblog")
- `integration_output_dir` - Temporary output directory (auto-cleaned)
- `sample_config` - Pre-configured ArchiverConfig

#### Test Data
- `sample_media_items` - List of MediaItem instances
- `sample_posts` - List of Post instances  
- `sample_image_data` - Minimal PNG (1x1 pixel)
- `sample_gif_data` - Minimal GIF
- `sample_video_data` - Minimal MP4 header

#### Helper Functions
- `create_test_media_content(type)` - Generate content by media type
- `verify_manifest_file(dir, posts, media)` - Validate manifest
- `verify_downloaded_files(dir, filenames)` - Check files exist
- `count_manifest_items(dir, status)` - Count items by status
- `get_media_item_from_manifest(dir, filename)` - Get specific item

## Mock Servers

### MockTumblrServer
Simulates Tumblr blog responses:

```python
server = MockTumblrServer("testblog")
server.add_post(
    post_id="123",
    media_url="https://64.media.tumblr.com/image.jpg",
    media_content=b"image data",
    timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
    is_reblog=False,
    media_type="image"
)

# Mark URL as failing (returns 404)
server.mark_url_as_failing("https://64.media.tumblr.com/missing.jpg")

# Use in tests
with server.mock():
    # Make HTTP requests - they'll be intercepted
    stats = await orchestrator.run()
```

### MockWaybackServer
Simulates Internet Archive:

```python
wayback = MockWaybackServer()
wayback.add_snapshot(
    original_url="https://64.media.tumblr.com/image.jpg",
    snapshot_url="https://web.archive.org/web/20240115120000/...",
    content=b"archived image data",
    timestamp=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
)

# Use in tests  
with wayback.mock():
    # Wayback requests will be intercepted
    pass
```

### Combining Mocks
```python
with tumblr.mock(), wayback.mock():
    # Both Tumblr and Wayback requests mocked
    stats = await orchestrator.run()
```

## Test Patterns

### Basic Test Structure
```python
@pytest.mark.asyncio
async def test_something(
    sample_blog_name: str,
    integration_output_dir: Path,
    sample_image_data: bytes
):
    """Test description."""
    # Arrange: Set up mock server
    server = MockTumblrServer(sample_blog_name)
    server.add_post(...)
    
    # Act: Run archiver
    config = ArchiverConfig(
        blog_name=sample_blog_name,
        output_dir=integration_output_dir
    )
    orchestrator = Orchestrator(config)
    
    with server.mock():
        stats = await orchestrator.run()
    
    # Assert: Verify results
    assert stats.downloaded == expected_count
    assert file_path.exists()
```

### Verifying Manifests
```python
# Check manifest exists and has correct structure
manifest_path = integration_output_dir / "manifest.json"
assert manifest_path.exists()

with open(manifest_path) as f:
    manifest = json.load(f)

assert manifest["total_posts"] == 2
assert manifest["total_media"] == 2

# Check specific media item
media = await get_media_item_from_manifest(
    integration_output_dir, 
    "123_001.jpg"
)
assert media["status"] == "downloaded"
assert media["checksum"] is not None
```

### Checking Downloaded Files
```python
# Verify file exists
file_path = integration_output_dir / "123_001.jpg"
assert file_path.exists()
assert file_path.stat().st_size > 0

# Verify content
with open(file_path, "rb") as f:
    content = f.read()
assert content == expected_binary_data

# Multiple files
filenames = ["123_001.jpg", "456_001.gif", "789_001.mp4"]
assert await verify_downloaded_files(integration_output_dir, filenames)
```

## Writing New Tests

1. **Add to appropriate test file**:
   - `test_end_to_end.py` - Complete workflow scenarios
   - `test_resume.py` - Resume/incremental behavior
   - `test_archive_fallback.py` - Fallback mechanisms

2. **Use fixtures for common setup**:
   ```python
   def test_new_feature(
       sample_blog_name,
       integration_output_dir,
       sample_config
   ):
       ...
   ```

3. **Follow AAA pattern**: Arrange, Act, Assert

4. **Use descriptive names**: `test_resume_with_deleted_files`

5. **Add docstrings** explaining what is tested

6. **Verify multiple aspects**:
   - Return values/statistics  
   - File system state
   - Manifest content
   - Side effects

## Debugging Tests

### Verbose Output
```bash
pytest tests/integration/ -vv -s
```

### Stop on First Failure
```bash
pytest tests/integration/ -x
```

### Run Only Failed Tests
```bash
pytest tests/integration/ --lf
```

### Show Local Variables on Failure
```bash
pytest tests/integration/ -l
```

### PDB Debugging
```bash
pytest tests/integration/ --pdb
```

## Notes

- Tests use `tmp_path` fixture for isolated file operations
- Each test is independent and can run in any order
- Mock servers intercept HTTP requests via `aioresponses`
- Binary test data is minimal but valid for checksums
- Tests verify actual file I/O, not just mocks

## Requirements

From `requirements-dev.txt`:
- pytest >= 7.4.4
- pytest-asyncio >= 0.21.1
- aioresponses >= 0.7.6
- pytest-mock >= 3.12.0

## Contributing

When adding new tests:
1. Ensure test is properly isolated
2. Clean up resources (automatic with tmp_path)
3. Test both success and failure cases
4. Update this README if adding new patterns
5. Run full test suite before committing
