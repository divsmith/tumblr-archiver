#!/usr/bin/env bash
#
# Publish script for tumblr-archiver package
#
# Usage:
#   ./scripts/publish.sh [--dry-run] [--test-pypi]
#
# Options:
#   --dry-run     Test package upload without actually publishing
#   --test-pypi   Publish to Test PyPI instead of production PyPI
#
# Requirements:
#   - Valid PyPI API token set in ~/.pypirc or PYPI_API_TOKEN env var
#   - Clean working directory (no uncommitted changes)
#   - Git tag matching package version

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Tumblr Archiver Publishing Script    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Parse arguments
DRY_RUN=false
TEST_PYPI=false

for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --test-pypi)
            TEST_PYPI=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown argument: $arg${NC}"
            echo "Usage: $0 [--dry-run] [--test-pypi]"
            exit 1
            ;;
    esac
done

# Check if twine is installed
if ! command -v twine &> /dev/null; then
    echo -e "${YELLOW}Installing twine...${NC}"
    pip install twine
fi

# Extract version from pyproject.toml
VERSION=$(grep -m1 '^version' pyproject.toml | cut -d'"' -f2)
echo -e "${GREEN}Package version: ${VERSION}${NC}"
echo ""

# Pre-flight checks
echo -e "${YELLOW}Running pre-flight checks...${NC}"
echo ""

# Check if git repo is clean
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    echo -e "${RED}✗ Git working directory is not clean${NC}"
    echo "  Please commit or stash your changes before publishing"
    git status --short
    exit 1
fi
echo -e "${GREEN}✓ Git working directory clean${NC}"

# Check if version tag exists
if git rev-parse "v${VERSION}" >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Git tag v${VERSION} exists${NC}"
else
    echo -e "${YELLOW}⚠ Git tag v${VERSION} does not exist${NC}"
    read -p "Create tag now? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git tag -a "v${VERSION}" -m "Release version ${VERSION}"
        echo -e "${GREEN}✓ Created tag v${VERSION}${NC}"
        echo -e "${YELLOW}  Don't forget to push the tag: git push --tags${NC}"
    else
        echo -e "${RED}✗ Cannot publish without version tag${NC}"
        exit 1
    fi
fi

# Check if CHANGELOG is updated
if ! grep -q "\[${VERSION}\]" CHANGELOG.md; then
    echo -e "${YELLOW}⚠ Version ${VERSION} not found in CHANGELOG.md${NC}"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo -e "${GREEN}✓ CHANGELOG.md updated${NC}"
fi

echo ""

# Build the package
echo -e "${YELLOW}Building package...${NC}"
"${SCRIPT_DIR}/build.sh" --clean || {
    echo -e "${RED}✗ Build failed${NC}"
    exit 1
}
echo ""

# Check if distributions exist
if [ ! -d "dist" ] || [ -z "$(ls -A dist/*.tar.gz 2>/dev/null)" ]; then
    echo -e "${RED}✗ No distributions found in dist/${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Distributions ready${NC}"
echo ""

# List what will be uploaded
echo -e "${YELLOW}Files to upload:${NC}"
ls -lh dist/
echo ""

# Validate package
echo -e "${YELLOW}Validating package...${NC}"
twine check dist/* || {
    echo -e "${RED}✗ Package validation failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Package validation passed${NC}"
echo ""

# Determine repository
if [ "$TEST_PYPI" = true ]; then
    REPO="testpypi"
    REPO_URL="https://test.pypi.org/legacy/"
    REPO_NAME="Test PyPI"
else
    REPO="pypi"
    REPO_URL="https://upload.pypi.org/legacy/"
    REPO_NAME="PyPI"
fi

# Final confirmation
if [ "$DRY_RUN" = false ]; then
    echo -e "${YELLOW}════════════════════════════════════════${NC}"
    echo -e "${YELLOW}Ready to publish to ${REPO_NAME}${NC}"
    echo -e "${YELLOW}════════════════════════════════════════${NC}"
    echo "Version: ${VERSION}"
    echo "Repository: ${REPO_URL}"
    echo ""
    read -p "Continue with upload? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Aborted by user${NC}"
        exit 0
    fi
fi

# Publish
echo ""
echo -e "${YELLOW}Publishing to ${REPO_NAME}...${NC}"
echo ""

if [ "$DRY_RUN" = true ]; then
    # Dry run - just check
    echo -e "${BLUE}DRY RUN MODE - No actual upload${NC}"
    twine upload --repository testpypi dist/* --verbose --skip-existing || true
else
    # Actual upload
    if [ "$TEST_PYPI" = true ]; then
        twine upload --repository testpypi dist/* --verbose
    else
        twine upload dist/* --verbose
    fi
    
    # Check status
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}════════════════════════════════════════${NC}"
        echo -e "${GREEN}✓ Successfully published v${VERSION}!${NC}"
        echo -e "${GREEN}════════════════════════════════════════${NC}"
        echo ""
        
        if [ "$TEST_PYPI" = true ]; then
            echo "View package: https://test.pypi.org/project/tumblr-archiver/${VERSION}/"
            echo "Install: pip install -i https://test.pypi.org/simple/ tumblr-archiver"
        else
            echo "View package: https://pypi.org/project/tumblr-archiver/${VERSION}/"
            echo "Install: pip install tumblr-archiver"
        fi
        
        echo ""
        echo "Don't forget to:"
        echo "  1. Push git tag: git push --tags"
        echo "  2. Create GitHub release"
        echo "  3. Update documentation"
        echo ""
    else
        echo -e "${RED}✗ Upload failed${NC}"
        exit 1
    fi
fi
