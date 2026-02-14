#!/bin/bash

################################################################################
# Tumblr Archiver - Basic Usage Examples
#
# This script demonstrates common usage patterns for the Tumblr archiver tool.
# Each example is self-contained and includes explanations.
#
# Usage: bash basic_usage.sh
# Or run individual examples by copying the commands
################################################################################

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper function to print section headers
print_section() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"
}

# Helper function to print info
print_info() {
    echo -e "${YELLOW}→${NC} $1"
}

################################################################################
# Example 1: Most Basic Usage
################################################################################
example_1() {
    print_section "Example 1: Most Basic Usage"
    
    print_info "Archive a blog with all default settings"
    echo "Command:"
    echo "  tumblr-archiver myblog"
    echo ""
    echo "What this does:"
    echo "  • Downloads all media from myblog.tumblr.com"
    echo "  • Saves to ./downloads/myblog/"
    echo "  • Uses 2 concurrent workers"
    echo "  • Rate limited to 1 request/second"
    echo "  • Resume capability enabled"
    echo "  • Includes reblogged posts"
    echo ""
    
    # Uncomment to run:
    # tumblr-archiver myblog
}

################################################################################
# Example 2: Specify Output Directory
################################################################################
example_2() {
    print_section "Example 2: Specify Output Directory"
    
    print_info "Save downloads to a custom location"
    echo "Command:"
    echo "  tumblr-archiver myblog --output ~/tumblr-archives"
    echo ""
    echo "Result:"
    echo "  Files saved to: ~/tumblr-archives/myblog/"
    echo ""
    echo "Tip: Use absolute paths for clarity"
    echo ""
    
    # Uncomment to run:
    # tumblr-archiver myblog --output ~/tumblr-archives
}

################################################################################
# Example 3: Dry Run (Test Without Downloading)
################################################################################
example_3() {
    print_section "Example 3: Dry Run (Test Without Downloading)"
    
    print_info "Preview what would be downloaded without actually downloading"
    echo "Command:"
    echo "  tumblr-archiver myblog --dry-run"
    echo ""
    echo "Useful for:"
    echo "  • Checking if blog exists and is accessible"
    echo "  • Estimating download size"
    echo "  • Previewing number of media items"
    echo "  • Testing configuration"
    echo ""
    echo "Example output:"
    echo "  Found 150 posts"
    echo "  Found 423 media items"
    echo "  Estimated download size: 1.2 GB"
    echo ""
    
    # Uncomment to run:
    # tumblr-archiver myblog --dry-run
}

################################################################################
# Example 4: Verbose Mode (Detailed Logging)
################################################################################
example_4() {
    print_section "Example 4: Verbose Mode (Detailed Logging)"
    
    print_info "Enable detailed logging to see what's happening"
    echo "Command:"
    echo "  tumblr-archiver myblog --verbose"
    echo ""
    echo "Shows:"
    echo "  • HTTP requests and responses"
    echo "  • Parsing progress"
    echo "  • Download progress for each file"
    echo "  • Error details"
    echo ""
    echo "Tip: Save logs to a file:"
    echo "  tumblr-archiver myblog --verbose 2>&1 | tee archive.log"
    echo ""
    
    # Uncomment to run:
    # tumblr-archiver myblog --verbose
}

################################################################################
# Example 5: Resume Interrupted Download
################################################################################
example_5() {
    print_section "Example 5: Resume Interrupted Download"
    
    print_info "Continue a download that was interrupted"
    echo "Scenario:"
    echo "  You ran: tumblr-archiver myblog"
    echo "  It was interrupted (Ctrl+C, connection lost, computer crashed)"
    echo ""
    echo "To resume, simply run the same command again:"
    echo "  tumblr-archiver myblog"
    echo ""
    echo "The tool will:"
    echo "  • Load the manifest file"
    echo "  • Skip already downloaded files"
    echo "  • Retry failed downloads"
    echo "  • Continue from where it left off"
    echo ""
    echo "Note: Resume is enabled by default"
    echo ""
}

################################################################################
# Example 6: Archive Only Original Content
################################################################################
example_6() {
    print_section "Example 6: Archive Only Original Content"
    
    print_info "Exclude reblogged posts, download only original content"
    echo "Command:"
    echo "  tumblr-archiver myblog --exclude-reblogs"
    echo ""
    echo "Useful when:"
    echo "  • You want only the blog's original posts"
    echo "  • Reducing archive size"
    echo "  • Focusing on creator's own content"
    echo ""
    
    # Uncomment to run:
    # tumblr-archiver myblog --exclude-reblogs
}

################################################################################
# Example 7: Adjust Download Speed
################################################################################
example_7() {
    print_section "Example 7: Adjust Download Speed"
    
    print_info "Increase concurrency and rate for faster downloads"
    echo "Command:"
    echo "  tumblr-archiver myblog --concurrency 4 --rate 2.0"
    echo ""
    echo "Parameters:"
    echo "  --concurrency 4  : 4 parallel download workers"
    echo "  --rate 2.0       : 2 requests per second per worker"
    echo "  Effective rate   : ~8 requests/second total"
    echo ""
    echo "⚠️  Warning:"
    echo "  • Higher rates increase chance of rate limiting"
    echo "  • Start conservative, increase gradually"
    echo "  • Monitor for 429 errors"
    echo ""
    
    # Uncomment to run:
    # tumblr-archiver myblog --concurrency 4 --rate 2.0
}

################################################################################
# Example 8: Conservative Settings (Slow but Safe)
################################################################################
example_8() {
    print_section "Example 8: Conservative Settings (Slow but Safe)"
    
    print_info "Use very conservative settings to minimize server impact"
    echo "Command:"
    echo "  tumblr-archiver myblog --concurrency 1 --rate 0.5"
    echo ""
    echo "Parameters:"
    echo "  --concurrency 1  : Only 1 download worker"
    echo "  --rate 0.5       : 1 request per 2 seconds"
    echo ""
    echo "Use when:"
    echo "  • Being maximally respectful"
    echo "  • Avoiding rate limits"
    echo "  • Working with slow connection"
    echo "  • Not in a hurry"
    echo ""
    
    # Uncomment to run:
    # tumblr-archiver myblog --concurrency 1 --rate 0.5
}

################################################################################
# Example 9: Multiple Format Inputs
################################################################################
example_9() {
    print_section "Example 9: Multiple Format Inputs"
    
    print_info "Different ways to specify the blog"
    echo "All of these work and are equivalent:"
    echo ""
    echo "  tumblr-archiver myblog"
    echo "  tumblr-archiver myblog.tumblr.com"
    echo "  tumblr-archiver https://myblog.tumblr.com"
    echo ""
    echo "The tool automatically normalizes the input to the blog name."
    echo ""
}

################################################################################
# Example 10: Combine Multiple Options
################################################################################
example_10() {
    print_section "Example 10: Combine Multiple Options"
    
    print_info "Realistic example combining several options"
    echo "Command:"
    echo "  tumblr-archiver photography-blog \\"
    echo "    --output ~/Backups/tumblr \\"
    echo "    --concurrency 3 \\"
    echo "    --rate 1.5 \\"
    echo "    --exclude-reblogs \\"
    echo "    --verbose"
    echo ""
    echo "This will:"
    echo "  • Archive 'photography-blog'"
    echo "  • Save to ~/Backups/tumblr/photography-blog/"
    echo "  • Use 3 concurrent workers"
    echo "  • Rate limit to 1.5 requests/second"
    echo "  • Skip reblogged posts"
    echo "  • Show detailed progress"
    echo ""
    
    # Uncomment to run:
    # tumblr-archiver photography-blog \
    #   --output ~/Backups/tumblr \
    #   --concurrency 3 \
    #   --rate 1.5 \
    #   --exclude-reblogs \
    #   --verbose
}

################################################################################
# Example 11: Check Version and Help
################################################################################
example_11() {
    print_section "Example 11: Check Version and Help"
    
    print_info "Get version information and help"
    echo "Version:"
    echo "  tumblr-archiver --version"
    echo ""
    echo "Help:"
    echo "  tumblr-archiver --help"
    echo ""
    
    print_info "Running these now..."
    tumblr-archiver --version
    echo ""
    echo "For full help text, run: tumblr-archiver --help"
    echo ""
}

################################################################################
# Example 12: Archive Multiple Blogs
################################################################################
example_12() {
    print_section "Example 12: Archive Multiple Blogs"
    
    print_info "Archive several blogs in sequence"
    echo "Script:"
    cat << 'EOF'
  #!/bin/bash
  
  BLOGS=("blog1" "blog2" "blog3")
  OUTPUT_DIR="./archives"
  
  for blog in "${BLOGS[@]}"; do
    echo "Archiving $blog..."
    tumblr-archiver "$blog" --output "$OUTPUT_DIR"
    
    echo "Waiting 60 seconds before next blog..."
    sleep 60
  done
  
  echo "All blogs archived!"
EOF
    echo ""
    echo "Tip: Add delays between blogs to be respectful"
    echo ""
}

################################################################################
# Example 13: Start Fresh (Ignore Existing Progress)
################################################################################
example_13() {
    print_section "Example 13: Start Fresh (Ignore Existing Progress)"
    
    print_info "Start a new download ignoring existing manifest"
    echo "Command:"
    echo "  tumblr-archiver myblog --no-resume"
    echo ""
    echo "When to use:"
    echo "  • Manifest is corrupted"
    echo "  • Want to verify all downloads"
    echo "  • Testing configuration changes"
    echo ""
    echo "Note:"
    echo "  • Existing files won't be re-downloaded (checksum verification)"
    echo "  • Only downloads files that don't exist or are incomplete"
    echo ""
    
    # Uncomment to run:
    # tumblr-archiver myblog --no-resume
}

################################################################################
# Example 14: Increase Timeout for Large Files
################################################################################
example_14() {
    print_section "Example 14: Increase Timeout for Large Files"
    
    print_info "Adjust timeout for slow connections or large files"
    echo "Command:"
    echo "  tumblr-archiver myblog --timeout 60.0"
    echo ""
    echo "Default timeout: 30 seconds"
    echo "This sets it to: 60 seconds"
    echo ""
    echo "Use when:"
    echo "  • Downloading large video files"
    echo "  • Slow internet connection"
    echo "  • Getting timeout errors"
    echo ""
    
    # Uncomment to run:
    # tumblr-archiver myblog --timeout 60.0
}

################################################################################
# Example 15: Full Featured Command
################################################################################
example_15() {
    print_section "Example 15: Full Featured Command"
    
    print_info "A comprehensive example with many options"
    echo "Command:"
    echo "  tumblr-archiver art-gallery \\"
    echo "    --output ~/Archives/tumblr \\"
    echo "    --concurrency 3 \\"
    echo "    --rate 1.5 \\"
    echo "    --max-retries 5 \\"
    echo "    --timeout 45.0 \\"
    echo "    --exclude-reblogs \\"
    echo "    --verbose"
    echo ""
    echo "This demonstrates:"
    echo "  • Custom output location"
    echo "  • Moderate concurrency (3 workers)"
    echo "  • Moderate rate (1.5 req/s)"
    echo "  • Extra retries for reliability"
    echo "  • Longer timeout for large files"
    echo "  • Original content only"
    echo "  • Detailed logging"
    echo ""
}

################################################################################
# Main execution
################################################################################
main() {
    print_section "Tumblr Archiver - Basic Usage Examples"
    
    echo "This script demonstrates common usage patterns."
    echo "Each example is explained but not executed by default."
    echo ""
    echo "To run an example, uncomment the command in the script."
    echo ""
    
    # Run all examples (just showing, not executing)
    example_1
    example_2
    example_3
    example_4
    example_5
    example_6
    example_7
    example_8
    example_9
    example_10
    example_11  # This one actually runs --version
    example_12
    example_13
    example_14
    example_15
    
    print_section "Examples complete!"
    echo "To run any example, copy the command and execute it."
    echo ""
    echo "For more information:"
    echo "  • Documentation: docs/"
    echo "  • Help: tumblr-archiver --help"
    echo "  • GitHub: https://github.com/parker/tumblr-archiver"
    echo ""
}

# Run main function
main
