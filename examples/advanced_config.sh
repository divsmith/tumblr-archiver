#!/bin/bash

################################################################################
# Tumblr Archiver - Advanced Configuration Examples
#
# This script demonstrates advanced usage patterns including:
# - Performance tuning
# - Batch processing
# - Error handling
# - Custom workflows
# - Production configurations
#
# Usage: bash advanced_config.sh
################################################################################

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Helper functions
print_section() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"
}

print_info() {
    echo -e "${YELLOW}→${NC} $1"
}

print_warning() {
    echo -e "${RED}⚠${NC}  $1"
}

################################################################################
# Example 1: Maximum Performance Configuration
################################################################################
example_max_performance() {
    print_section "Example 1: Maximum Performance Configuration"
    
    print_info "Aggressive settings for fast downloads"
    print_warning "Use only with good connection and monitoring!"
    
    echo "Command:"
    cat << 'EOF'
tumblr-archiver myblog \
  --output ./archives \
  --concurrency 8 \
  --rate 3.0 \
  --timeout 30.0 \
  --max-retries 2 \
  --verbose
EOF
    
    echo ""
    echo "Configuration breakdown:"
    echo "  Concurrency: 8 workers (high)"
    echo "  Rate: 3.0 req/s per worker"
    echo "  Effective rate: ~24 req/s total"
    echo "  Timeout: 30s (assume fast downloads)"
    echo "  Retries: 2 (fail fast)"
    echo ""
    echo "Monitor for:"
    echo "  • Rate limiting (429 errors)"
    echo "  • Failed downloads"
    echo "  • System resource usage"
    echo ""
    
    # Uncomment to run:
    # tumblr-archiver myblog \
    #   --output ./archives \
    #   --concurrency 8 \
    #   --rate 3.0 \
    #   --timeout 30.0 \
    #   --max-retries 2 \
    #   --verbose
}

################################################################################
# Example 2: Conservative Production Configuration
################################################################################
example_conservative_prod() {
    print_section "Example 2: Conservative Production Configuration"
    
    print_info "Reliable settings for unattended archiving"
    
    echo "Command:"
    cat << 'EOF'
tumblr-archiver myblog \
  --output /mnt/archives/tumblr \
  --concurrency 2 \
  --rate 0.5 \
  --timeout 120.0 \
  --max-retries 7 \
  --verbose 2>&1 | tee -a /var/log/tumblr-archiver.log
EOF
    
    echo ""
    echo "Configuration breakdown:"
    echo "  Concurrency: 2 workers (stable)"
    echo "  Rate: 0.5 req/s (very respectful)"
    echo "  Timeout: 120s (handle large files)"
    echo "  Retries: 7 (maximize success)"
    echo "  Logging: Verbose output saved to file"
    echo ""
    echo "Best for:"
    echo "  • Scheduled/cron jobs"
    echo "  • Unattended operation"
    echo "  • Maximizing success rate"
    echo "  • Long-running archives"
    echo ""
}

################################################################################
# Example 3: Batch Processing Multiple Blogs
################################################################################
example_batch_processing() {
    print_section "Example 3: Batch Processing Multiple Blogs"
    
    print_info "Archive multiple blogs with error handling"
    
    echo "Script:"
    cat << 'EOF'
#!/bin/bash

# Configuration
BLOGS=(
  "photography-blog"
  "art-gallery"
  "travel-journal"
  "food-diary"
)

OUTPUT_DIR="$HOME/tumblr-archives"
LOG_DIR="$HOME/logs/tumblr"
CONCURRENCY=2
RATE=1.0
DELAY_BETWEEN_BLOGS=120  # 2 minutes

# Create directories
mkdir -p "$OUTPUT_DIR" "$LOG_DIR"

# Process each blog
for blog in "${BLOGS[@]}"; do
  timestamp=$(date +"%Y%m%d_%H%M%S")
  log_file="$LOG_DIR/${blog}_${timestamp}.log"
  
  echo "============================================"
  echo "Processing: $blog"
  echo "Started: $(date)"
  echo "Log: $log_file"
  echo "============================================"
  
  # Run archiver with logging
  if tumblr-archiver "$blog" \
    --output "$OUTPUT_DIR" \
    --concurrency "$CONCURRENCY" \
    --rate "$RATE" \
    --verbose 2>&1 | tee "$log_file"; then
    echo "✓ Successfully archived: $blog"
  else
    echo "✗ Failed to archive: $blog (see log: $log_file)"
    # Continue with next blog despite failure
  fi
  
  # Delay before next blog
  if [ "$blog" != "${BLOGS[-1]}" ]; then
    echo "Waiting ${DELAY_BETWEEN_BLOGS}s before next blog..."
    sleep "$DELAY_BETWEEN_BLOGS"
  fi
done

echo ""
echo "============================================"
echo "Batch processing complete!"
echo "Completed: $(date)"
echo "============================================"
EOF
    
    echo ""
    echo "Features:"
    echo "  • Processes multiple blogs sequentially"
    echo "  • Individual log files per blog"
    echo "  • Error handling (continue on failure)"
    echo "  • Delays between blogs"
    echo "  • Timestamped logs"
    echo ""
}

################################################################################
# Example 4: Incremental Backup with Cron
################################################################################
example_cron_backup() {
    print_section "Example 4: Incremental Backup with Cron"
    
    print_info "Scheduled archiving for active blogs"
    
    echo "Cron job setup:"
    cat << 'EOF'
# Add to crontab (crontab -e)

# Archive blog daily at 2 AM
0 2 * * * /path/to/tumblr-archiver myblog --output /backups/tumblr >> /var/log/tumblr-cron.log 2>&1

# Archive multiple blogs on different schedules
0 2 * * * /path/to/tumblr-archiver active-blog --output /backups >/dev/null 2>&1
0 3 * * 0 /path/to/tumblr-archiver weekly-blog --output /backups >/dev/null 2>&1
0 4 1 * * /path/to/tumblr-archiver monthly-blog --output /backups >/dev/null 2>&1
EOF
    
    echo ""
    echo "Wrapper script for cron:"
    cat << 'EOF'
#!/bin/bash
# save as: /usr/local/bin/tumblr-backup.sh

BLOG="$1"
OUTPUT="/backups/tumblr"
LOG_DIR="/var/log/tumblr-backups"
VENV="/opt/tumblr-archiver/venv"

# Activate virtualenv
source "$VENV/bin/activate"

# Create log directory
mkdir -p "$LOG_DIR"

# Run archiver
tumblr-archiver "$BLOG" \
  --output "$OUTPUT" \
  --concurrency 2 \
  --rate 0.5 \
  --verbose >> "$LOG_DIR/${BLOG}_$(date +\%Y\%m\%d).log" 2>&1

# Check exit code
if [ $? -eq 0 ]; then
  echo "Backup successful: $BLOG at $(date)"
else
  echo "Backup failed: $BLOG at $(date)" >&2
  # Could send alert email here
fi
EOF
    
    echo ""
    echo "Features:"
    echo "  • Automated daily/weekly/monthly backups"
    echo "  • Uses resume capability (only downloads new content)"
    echo "  • Logs to separate files"
    echo "  • Can trigger alerts on failure"
    echo ""
}

################################################################################
# Example 5: Parallel Processing (Advanced)
################################################################################
example_parallel_processing() {
    print_section "Example 5: Parallel Processing (Advanced)"
    
    print_info "Archive multiple blogs in parallel"
    print_warning "Multiplies network load - use carefully!"
    
    echo "Script:"
    cat << 'EOF'
#!/bin/bash

# Blogs to process
BLOGS=(
  "blog1"
  "blog2"
  "blog3"
  "blog4"
)

OUTPUT_DIR="./archives"

# Function to archive a blog
archive_blog() {
  local blog="$1"
  echo "Starting: $blog"
  
  tumblr-archiver "$blog" \
    --output "$OUTPUT_DIR" \
    --concurrency 2 \
    --rate 0.5 \
    >> "logs/${blog}.log" 2>&1
  
  echo "Completed: $blog"
}

# Export function for parallel to use
export -f archive_blog
export OUTPUT_DIR

# Create log directory
mkdir -p logs

# Process blogs in parallel (2 at a time)
# Requires GNU parallel: brew install parallel
parallel -j 2 archive_blog ::: "${BLOGS[@]}"

echo "All blogs completed!"
EOF
    
    echo ""
    echo "Note: Requires GNU parallel"
    echo "Install: brew install parallel (macOS) or apt install parallel (Linux)"
    echo ""
    echo "Alternative using background jobs:"
    cat << 'EOF'
#!/bin/bash

# Start multiple archives as background jobs
tumblr-archiver blog1 --output ./archives &
tumblr-archiver blog2 --output ./archives &
tumblr-archiver blog3 --output ./archives &

# Wait for all background jobs to complete
wait

echo "All archives complete!"
EOF
    echo ""
}

################################################################################
# Example 6: Resume with Manual Verification
################################################################################
example_resume_verification() {
    print_section "Example 6: Resume with Manual Verification"
    
    print_info "Resume and verify downloaded files"
    
    echo "Script:"
    cat << 'EOF'
#!/bin/bash

BLOG="$1"
OUTPUT="./archives"

if [ -z "$BLOG" ]; then
  echo "Usage: $0 <blog-name>"
  exit 1
fi

# Check if manifest exists
manifest_path="$OUTPUT/$BLOG/manifest.json"

if [ -f "$manifest_path" ]; then
  echo "Found existing manifest for $BLOG"
  
  # Show statistics
  echo "Statistics:"
  completed=$(grep -c '"status": "completed"' "$manifest_path" || echo "0")
  failed=$(grep -c '"status": "failed"' "$manifest_path" || echo "0")
  pending=$(grep -c '"status": "pending"' "$manifest_path" || echo "0")
  
  echo "  Completed: $completed"
  echo "  Failed: $failed"
  echo "  Pending: $pending"
  echo ""
  
  # Ask to continue
  read -p "Resume download? (y/n) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 0
  fi
fi

# Run archiver
tumblr-archiver "$BLOG" \
  --output "$OUTPUT" \
  --verbose

# Verify results
echo ""
echo "Download complete. Verification:"
echo "  Files: $(find "$OUTPUT/$BLOG" -type f ! -name "manifest.json" | wc -l)"
echo "  Size: $(du -sh "$OUTPUT/$BLOG" | cut -f1)"
EOF
    
    echo ""
    echo "Features:"
    echo "  • Checks for existing progress"
    echo "  • Shows statistics before resuming"
    echo "  • Prompts for confirmation"
    echo "  • Verifies results after completion"
    echo ""
}

################################################################################
# Example 7: Filtering and Selective Archiving
################################################################################
example_filtering() {
    print_section "Example 7: Filtering and Selective Archiving"
    
    print_info "Archive with filters and conditions"
    
    echo "Original content only (no reblogs):"
    echo "  tumblr-archiver myblog --exclude-reblogs"
    echo ""
    
    echo "Test before downloading:"
    cat << 'EOF'
#!/bin/bash

BLOG="$1"

# Dry run to check content
echo "Checking blog content..."
if tumblr-archiver "$BLOG" --dry-run > /tmp/dryrun.txt 2>&1; then
  # Parse dry run output
  posts=$(grep "Found.*posts" /tmp/dryrun.txt | awk '{print $2}')
  media=$(grep "Found.*media" /tmp/dryrun.txt | awk '{print $2}')
  size=$(grep "Estimated download size" /tmp/dryrun.txt | awk '{print $4, $5}')
  
  echo "Blog: $BLOG"
  echo "Posts: $posts"
  echo "Media: $media"
  echo "Size: $size"
  
  # Decision logic
  if [ "$posts" -gt 1000 ]; then
    echo "Large blog detected. Using conservative settings..."
    tumblr-archiver "$BLOG" --concurrency 1 --rate 0.5
  else
    echo "Regular download..."
    tumblr-archiver "$BLOG"
  fi
else
  echo "Failed to access blog: $BLOG"
  exit 1
fi
EOF
    
    echo ""
    echo "This demonstrates:"
    echo "  • Pre-flight checks with dry run"
    echo "  • Adaptive configuration based on blog size"
    echo "  • Error handling"
    echo ""
}

################################################################################
# Example 8: Network-Constrained Configuration
################################################################################
example_network_constrained() {
    print_section "Example 8: Network-Constrained Configuration"
    
    print_info "Optimized for slow or unreliable networks"
    
    echo "Command:"
    cat << 'EOF'
tumblr-archiver myblog \
  --output ./archives \
  --concurrency 1 \
  --rate 0.3 \
  --timeout 180.0 \
  --max-retries 10 \
  --verbose
EOF
    
    echo ""
    echo "Configuration breakdown:"
    echo "  Concurrency: 1 (minimize parallel connections)"
    echo "  Rate: 0.3 req/s (very slow, very safe)"
    echo "  Timeout: 180s (3 minutes for slow downloads)"
    echo "  Retries: 10 (maximize success on unreliable network)"
    echo ""
    echo "Best for:"
    echo "  • Slow internet (< 5 Mbps)"
    echo "  • Unstable connections"
    echo "  • Mobile/cellular connections"
    echo "  • High-latency networks"
    echo ""
}

################################################################################
# Example 9: Monitoring and Alerting
################################################################################
example_monitoring() {
    print_section "Example 9: Monitoring and Alerting"
    
    print_info "Monitor progress and send alerts"
    
    echo "Script with email alerts:"
    cat << 'EOF'
#!/bin/bash

BLOG="$1"
EMAIL="admin@example.com"
LOG_FILE="/tmp/tumblr-${BLOG}.log"

# Send email function
send_email() {
  local subject="$1"
  local body="$2"
  echo "$body" | mail -s "$subject" "$EMAIL"
}

# Start archiving
echo "Starting archive of $BLOG at $(date)"
send_email "Tumblr Archive Started" "Blog: $BLOG\nStarted: $(date)"

if tumblr-archiver "$BLOG" \
  --output ./archives \
  --verbose > "$LOG_FILE" 2>&1; then
  
  # Success
  stats=$(tail -20 "$LOG_FILE")
  send_email "Tumblr Archive Success" "Blog: $BLOG\n\n$stats"
  echo "Archive successful!"
else
  # Failure
  errors=$(grep -i "error" "$LOG_FILE" | tail -10)
  send_email "Tumblr Archive Failed" "Blog: $BLOG\n\nErrors:\n$errors"
  echo "Archive failed. Check log: $LOG_FILE"
  exit 1
fi
EOF
    
    echo ""
    echo "With Slack webhook:"
    cat << 'EOF'
#!/bin/bash

WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

send_slack() {
  local message="$1"
  curl -X POST -H 'Content-type: application/json' \
    --data "{\"text\":\"$message\"}" \
    "$WEBHOOK_URL"
}

send_slack "📥 Starting archive: myblog"

if tumblr-archiver myblog --output ./archives; then
  send_slack "✅ Archive complete: myblog"
else
  send_slack "❌ Archive failed: myblog"
fi
EOF
    
    echo ""
    echo "Features:"
    echo "  • Start/completion notifications"
    echo "  • Failure alerts"
    echo "  • Integration with email/Slack"
    echo "  • Log preservation"
    echo ""
}

################################################################################
# Example 10: Docker-based Archiving
################################################################################
example_docker() {
    print_section "Example 10: Docker-based Archiving"
    
    print_info "Run using Docker for isolation"
    
    echo "Basic Docker usage:"
    cat << 'EOF'
# Build image (if not using pre-built)
docker build -t tumblr-archiver .

# Run archiver
docker run --rm \
  -v "$(pwd)/downloads:/downloads" \
  tumblr-archiver myblog

# With custom options
docker run --rm \
  -v "$(pwd)/downloads:/downloads" \
  tumblr-archiver myblog \
  --concurrency 4 \
  --rate 2.0 \
  --verbose
EOF
    
    echo ""
    echo "Docker Compose configuration:"
    cat << 'EOF'
# docker-compose.yml
version: '3.8'

services:
  archiver:
    image: tumblr-archiver
    volumes:
      - ./downloads:/downloads
      - ./logs:/logs
    environment:
      - BLOG_NAME=myblog
      - CONCURRENCY=2
      - RATE=1.0
    command: >
      sh -c "tumblr-archiver \$$BLOG_NAME
      --output /downloads
      --concurrency \$$CONCURRENCY
      --rate \$$RATE
      --verbose"
EOF
    
    echo ""
    echo "Run with Docker Compose:"
    echo "  docker-compose run archiver"
    echo ""
}

################################################################################
# Example 11: Error Recovery Strategies
################################################################################
example_error_recovery() {
    print_section "Example 11: Error Recovery Strategies"
    
    print_info "Robust error handling and recovery"
    
    echo "Script with retry logic:"
    cat << 'EOF'
#!/bin/bash

BLOG="$1"
MAX_ATTEMPTS=3
ATTEMPT=1

while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
  echo "Attempt $ATTEMPT of $MAX_ATTEMPTS"
  
  if tumblr-archiver "$BLOG" \
    --output ./archives \
    --verbose; then
    echo "Success!"
    exit 0
  else
    echo "Attempt $ATTEMPT failed."
    
    if [ $ATTEMPT -lt $MAX_ATTEMPTS ]; then
      # Exponential backoff
      wait_time=$((2 ** ATTEMPT * 60))
      echo "Waiting ${wait_time}s before retry..."
      sleep $wait_time
      
      # On retry, use more conservative settings
      if [ $ATTEMPT -eq 2 ]; then
        echo "Using more conservative settings..."
        tumblr-archiver "$BLOG" \
          --output ./archives \
          --concurrency 1 \
          --rate 0.5 \
          --verbose
      fi
    fi
  fi
  
  ATTEMPT=$((ATTEMPT + 1))
done

echo "All attempts failed."
exit 1
EOF
    
    echo ""
    echo "Features:"
    echo "  • Multiple retry attempts"
    echo "  • Exponential backoff"
    echo "  • Progressively more conservative settings"
    echo "  • Clear failure reporting"
    echo ""
}

################################################################################
# Example 12: Performance Benchmarking
################################################################################
example_benchmarking() {
    print_section "Example 12: Performance Benchmarking"
    
    print_info "Compare different configurations"
    
    echo "Benchmarking script:"
    cat << 'EOF'
#!/bin/bash

BLOG="test-blog"
OUTPUT="./benchmark"

configs=(
  "1:0.5"    # 1 worker, 0.5 req/s
  "2:1.0"    # 2 workers, 1.0 req/s (default)
  "3:1.5"    # 3 workers, 1.5 req/s
  "4:2.0"    # 4 workers, 2.0 req/s
)

rm -rf "$OUTPUT"  # Start fresh

for config in "${configs[@]}"; do
  IFS=':' read -r concurrency rate <<< "$config"
  
  echo "Testing: concurrency=$concurrency, rate=$rate"
  
  start_time=$(date +%s)
  
  tumblr-archiver "$BLOG" \
    --output "$OUTPUT" \
    --concurrency "$concurrency" \
    --rate "$rate" \
    --no-resume \
    > /dev/null 2>&1
  
  end_time=$(date +%s)
  duration=$((end_time - start_time))
  
  echo "Duration: ${duration}s"
  
  # Clean for next test
  rm -rf "$OUTPUT/$BLOG"
done
EOF
    
    echo ""
    echo "This helps determine optimal settings for your setup."
    echo ""
}

################################################################################
# Main execution
################################################################################
main() {
    print_section "Tumblr Archiver - Advanced Configuration Examples"
    
    echo "This script demonstrates advanced usage patterns."
    echo "Examples are explained but not executed by default."
    echo ""
    
    # Show all examples
    example_max_performance
    example_conservative_prod
    example_batch_processing
    example_cron_backup
    example_parallel_processing
    example_resume_verification
    example_filtering
    example_network_constrained
    example_monitoring
    example_docker
    example_error_recovery
    example_benchmarking
    
    print_section "Advanced Examples Complete!"
    
    echo "Remember:"
    echo "  • Test configurations with --dry-run first"
    echo "  • Monitor resource usage"
    echo "  • Be respectful with rate limits"
    echo "  • Keep logs for troubleshooting"
    echo ""
    echo "For more information:"
    echo "  • Documentation: docs/"
    echo "  • Configuration guide: docs/configuration.md"
    echo "  • Troubleshooting: docs/troubleshooting.md"
    echo ""
}

# Run main
main
