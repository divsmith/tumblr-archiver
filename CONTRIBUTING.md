# Contributing to Tumblr Archiver

Thank you for your interest in contributing to Tumblr Archiver! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Environment Setup](#development-environment-setup)
- [Development Workflow](#development-workflow)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Reporting Issues](#reporting-issues)

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on what is best for the community
- Show empathy towards other community members

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/tumblr-archiver.git
   cd tumblr-archiver
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/parker/tumblr-archiver.git
   ```

## Development Environment Setup

### Prerequisites

- Python 3.10 or higher
- Git
- pip

### Installation Steps

1. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install development dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```

3. **Verify installation**:
   ```bash
   pytest
   tumblr-archiver --version
   ```

### Development Dependencies

The development environment includes:

- **pytest**: Testing framework
- **pytest-asyncio**: Async test support
- **pytest-cov**: Code coverage reporting
- **black**: Code formatting
- **mypy**: Static type checking
- **ruff**: Fast Python linter

## Development Workflow

### Creating a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

Use descriptive branch names:
- `feature/` - New features
- `bugfix/` - Bug fixes
- `docs/` - Documentation changes
- `refactor/` - Code refactoring

### Making Changes

1. **Write tests first** (TDD approach recommended)
2. **Implement your changes**
3. **Run tests** to ensure they pass
4. **Format code** using black
5. **Check types** with mypy
6. **Lint code** with ruff

### Keeping Your Fork Updated

```bash
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
```

## Code Style Guidelines

### General Principles

- Follow [PEP 8](https://pep8.org/) style guide
- Write clear, self-documenting code
- Add docstrings to all public functions, classes, and modules
- Keep functions small and focused
- Use type hints for all function signatures

### Python Style

```python
"""Module docstring explaining purpose."""

from typing import Optional

def process_media(url: str, timeout: Optional[float] = None) -> dict:
    """
    Process media from a given URL.
    
    Args:
        url: The URL to process
        timeout: Optional timeout in seconds
        
    Returns:
        Dictionary containing processing results
        
    Raises:
        ValueError: If URL is invalid
    """
    # Implementation
    pass
```

### Formatting

Run black to automatically format code:

```bash
black src/ tests/
```

Configuration is in `pyproject.toml`.

### Type Checking

Ensure type hints are correct:

```bash
mypy src/
```

### Linting

Check for code issues:

```bash
ruff check src/ tests/
```

Fix auto-fixable issues:

```bash
ruff check --fix src/ tests/
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=tumblr_archiver --cov-report=html

# Run specific test file
pytest tests/test_scraper.py

# Run specific test
pytest tests/test_scraper.py::test_parse_blog_posts

# Run with verbose output
pytest -v
```

### Writing Tests

- Place tests in the `tests/` directory
- Name test files `test_*.py`
- Name test functions `test_*`
- Use fixtures for common setup
- Test both success and failure cases
- Mock external dependencies (HTTP calls, file I/O)

Example test structure:

```python
"""Tests for the scraper module."""

import pytest
from tumblr_archiver.scraper import TumblrScraper

@pytest.mark.asyncio
async def test_scraper_basic_functionality():
    """Test basic scraping functionality."""
    scraper = TumblrScraper(config)
    posts = await scraper.scrape_posts()
    assert len(posts) > 0

@pytest.mark.asyncio
async def test_scraper_handles_errors():
    """Test error handling in scraper."""
    scraper = TumblrScraper(invalid_config)
    with pytest.raises(ScraperError):
        await scraper.scrape_posts()
```

### Test Coverage Goals

- Aim for >80% code coverage
- Focus on critical paths and error handling
- Don't sacrifice test quality for coverage numbers

## Pull Request Process

### Before Submitting

1. **Update your branch** with latest main:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run the full test suite**:
   ```bash
   pytest
   ```

3. **Check code quality**:
   ```bash
   black src/ tests/
   mypy src/
   ruff check src/ tests/
   ```

4. **Update documentation** if needed

### Submitting a Pull Request

1. **Push your branch** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create a pull request** on GitHub

3. **Fill out the PR template** completely:
   - Clear description of changes
   - Reference any related issues
   - List any breaking changes
   - Add screenshots if UI-related

### Pull Request Guidelines

- **Keep PRs focused** - One feature/fix per PR
- **Write clear commit messages**:
  ```
  Add YouTube embed download support
  
  - Implement YouTubeDownloader class
  - Add tests for video extraction
  - Update documentation
  
  Fixes #123
  ```

- **Respond to feedback** promptly
- **Keep commits clean** - Consider squashing if requested
- **Ensure CI passes** before requesting review

### Review Process

1. Automated checks must pass (tests, linting, type checking)
2. At least one maintainer approval required
3. Address all review comments or discuss them
4. Final approval merges the PR

## Reporting Issues

### Bug Reports

Include:
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs or error messages
- Minimal code example if applicable

### Feature Requests

Include:
- Clear description of the feature
- Use cases and motivation
- Proposed implementation approach (optional)
- Potential drawbacks or concerns

### Questions

- Check existing documentation first
- Search existing issues
- Provide context about what you're trying to achieve

## Development Tips

### Useful Commands

```bash
# Install in editable mode
pip install -e .

# Run with verbose logging
tumblr-archiver myblog --verbose

# Dry run for testing
tumblr-archiver myblog --dry-run

# Watch for file changes and run tests
pytest-watch

# Generate coverage report
pytest --cov=tumblr_archiver --cov-report=html
open htmlcov/index.html
```

### Debugging

- Use `--verbose` flag for detailed logging
- Use `--dry-run` to test without downloading
- Check `manifest.json` for download state
- Enable async debugging in your IDE

### Project Structure

```
tumblr-archiver/
├── src/tumblr_archiver/    # Main package
│   ├── __init__.py         # Package initialization
│   ├── cli.py              # CLI interface
│   ├── config.py           # Configuration management
│   ├── orchestrator.py     # Main orchestration logic
│   ├── scraper.py          # Web scraping
│   ├── downloader.py       # Media downloading
│   ├── manifest.py         # Progress tracking
│   └── ...                 # Other modules
├── tests/                  # Test suite
├── docs/                   # Documentation
├── examples/               # Usage examples
└── pyproject.toml          # Project configuration
```

## Questions?

If you have questions not covered here:
- Open a GitHub issue
- Check the [documentation](docs/)
- Review existing issues and PRs

Thank you for contributing! 🎉
