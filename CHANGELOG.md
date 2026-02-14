# Changelog

All notable changes to the Tumblr Archiver project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-02-13

### Added

#### Core Features
- **Async/await architecture** for efficient parallel downloads
- **Resume capability** - automatically continue interrupted downloads from manifest
- **Manifest-based tracking** - comprehensive JSON manifest for all downloads
- **Wayback Machine fallback** - automatic Internet Archive lookup for unavailable media
- **Dry run mode** - test archival without downloading files (`--dry-run`)
- **Flexible configuration** - YAML config file support and CLI overrides

#### Media Support
- Download images (JPG, PNG, GIF)
- Download video files (MP4, MOV)
- Download audio files (MP3, M4A)
- Extract and download embedded media:
  - YouTube videos
  - Vimeo videos
  - SoundCloud audio
  - Spotify embeds
  - Instagram embeds

#### Performance & Reliability
- **Smart rate limiting** - configurable delays to respect server resources
- **Automatic retries** with exponential backoff
- **Connection pooling** - reusable HTTP client sessions
- **Progress tracking** - real-time statistics and ETA
- **Comprehensive logging** - detailed logs with rotation support
- **Deduplication** - skip already downloaded files based on checksums
- **Cache system** - file-based caching for improved performance

#### Command-Line Interface
- Main `archive` command for blog archiving
- Post counter utility (`count-posts`)
- Wayback checker utility (`check-wayback`)
- Configurable concurrency, rate limits, and retry behavior
- Support for date range filtering

#### Testing & Quality
- Comprehensive test suite with 500+ tests
- Integration tests for end-to-end workflows
- Mock Tumblr server for testing
- 95%+ code coverage
- Type hints throughout (mypy compatible)
- Code formatting with Black
- Linting with Ruff

#### Documentation
- Detailed README with quick start guide
- Architecture documentation
- Configuration guide
- Usage examples
- Troubleshooting guide
- API documentation

### Known Limitations

- **No API support** - relies on web scraping (may break if Tumblr changes HTML structure)
- **Rate limiting** - aggressive downloading may trigger rate limits
- **Wayback availability** - not all media is archived in Internet Archive
- **Embedded media** - some platforms may require additional authentication
- **NSFW content** - may require authentication for certain blogs
- **Large blogs** - very large blogs (>10,000 posts) may take significant time

### Technical Details

- **Python version**: 3.10+
- **Key dependencies**: aiohttp, click, beautifulsoup4, pydantic
- **License**: MIT
- **Build system**: Hatchling

### Breaking Changes

None (initial release)

### Security

- Input validation for URLs and file paths
- Path traversal protection
- Rate limiting to prevent abuse
- No storage of credentials

### Performance

- Concurrent downloads (default: 5 workers)
- Async I/O for network and disk operations
- Connection pooling and keep-alive
- Efficient memory usage with streaming downloads

---

## [Unreleased]

### Planned Features
- GUI interface
- Better progress visualization
- Archive export formats (ZIP, TAR)
- Advanced filtering (by post type, tags, date ranges)
- Parallel blog archiving
- Database backend option
- Better Wayback integration with snapshot selection

---

## Release Guidelines

### Version Numbering
- **MAJOR.MINOR.PATCH** (e.g., 1.0.0)
- MAJOR: Breaking API changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes (backward compatible)

### Release Process
1. Update version in `pyproject.toml`
2. Update CHANGELOG.md with release notes
3. Commit changes: `git commit -m "Release v0.X.Y"`
4. Create tag: `git tag v0.X.Y`
5. Push: `git push && git push --tags`
6. GitHub Actions will automatically build and publish to PyPI

---

[0.1.0]: https://github.com/parker/tumblr-archiver/releases/tag/v0.1.0
