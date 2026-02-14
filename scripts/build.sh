#!/usr/bin/env bash
#
# Build script for tumblr-archiver package
# 
# Usage:
#   ./scripts/build.sh [--clean] [--check]
#
# Options:
#   --clean    Remove existing build artifacts before building
#   --check    Run additional validation checks
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

echo -e "${GREEN}Building tumblr-archiver package${NC}"
echo "Project root: ${PROJECT_ROOT}"
echo ""

# Parse arguments
CLEAN=false
CHECK=false

for arg in "$@"; do
    case $arg in
        --clean)
            CLEAN=true
            shift
            ;;
        --check)
            CHECK=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown argument: $arg${NC}"
            echo "Usage: $0 [--clean] [--check]"
            exit 1
            ;;
    esac
done

# Clean existing build artifacts
if [ "$CLEAN" = true ]; then
    echo -e "${YELLOW}Cleaning build artifacts...${NC}"
    rm -rf build/ dist/ *.egg-info .eggs/
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    echo -e "${GREEN}✓ Cleaned${NC}"
    echo ""
fi

# Check if build tools are installed
echo -e "${YELLOW}Checking build dependencies...${NC}"
if ! python -c "import build" 2>/dev/null; then
    echo -e "${YELLOW}Installing build tools...${NC}"
    pip install build twine
fi
echo -e "${GREEN}✓ Build tools available${NC}"
echo ""

# Validate pyproject.toml
echo -e "${YELLOW}Validating pyproject.toml...${NC}"
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}✗ pyproject.toml not found${NC}"
    exit 1
fi

# Extract version
VERSION=$(grep -m1 '^version' pyproject.toml | cut -d'"' -f2)
echo "Version: ${VERSION}"
echo -e "${GREEN}✓ Configuration valid${NC}"
echo ""

# Run additional checks if requested
if [ "$CHECK" = true ]; then
    echo -e "${YELLOW}Running pre-build checks...${NC}"
    
    # Check if README exists
    if [ ! -f "README.md" ]; then
        echo -e "${RED}✗ README.md not found${NC}"
        exit 1
    fi
    
    # Check if LICENSE exists
    if [ ! -f "LICENSE" ]; then
        echo -e "${RED}✗ LICENSE not found${NC}"
        exit 1
    fi
    
    # Run tests (if pytest is available)
    if command -v pytest &> /dev/null; then
        echo -e "${YELLOW}Running tests...${NC}"
        pytest tests/ -q || {
            echo -e "${RED}✗ Tests failed${NC}"
            exit 1
        }
        echo -e "${GREEN}✓ Tests passed${NC}"
    fi
    
    # Run type checking (if mypy is available)
    if command -v mypy &> /dev/null; then
        echo -e "${YELLOW}Running type checks...${NC}"
        mypy src/tumblr_archiver/ || {
            echo -e "${YELLOW}⚠ Type check warnings (non-blocking)${NC}"
        }
    fi
    
    # Run linting (if ruff is available)
    if command -v ruff &> /dev/null; then
        echo -e "${YELLOW}Running linter...${NC}"
        ruff check src/ || {
            echo -e "${YELLOW}⚠ Linting warnings (non-blocking)${NC}"
        }
    fi
    
    echo -e "${GREEN}✓ Pre-build checks complete${NC}"
    echo ""
fi

# Build the package
echo -e "${YELLOW}Building distributions...${NC}"
python -m build || {
    echo -e "${RED}✗ Build failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Build complete${NC}"
echo ""

# Check the built package
echo -e "${YELLOW}Validating distributions...${NC}"
twine check dist/* || {
    echo -e "${RED}✗ Package validation failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Distributions valid${NC}"
echo ""

# List package contents
echo -e "${YELLOW}Package contents:${NC}"
echo ""

# Show wheel contents
WHEEL_FILE=$(ls -t dist/*.whl | head -1)
if [ -f "$WHEEL_FILE" ]; then
    echo -e "${GREEN}Wheel: $(basename "$WHEEL_FILE")${NC}"
    unzip -l "$WHEEL_FILE" | head -20
    echo "..."
    echo ""
fi

# Show sdist contents
SDIST_FILE=$(ls -t dist/*.tar.gz | head -1)
if [ -f "$SDIST_FILE" ]; then
    echo -e "${GREEN}Source dist: $(basename "$SDIST_FILE")${NC}"
    tar -tzf "$SDIST_FILE" | head -20
    echo "..."
    echo ""
fi

# Summary
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Build successful!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Version: ${VERSION}"
echo "Distributions:"
ls -lh dist/
echo ""
echo "To install locally:"
echo "  pip install dist/${WHEEL_FILE##*/}"
echo ""
echo "To publish to PyPI:"
echo "  ./scripts/publish.sh"
echo ""
