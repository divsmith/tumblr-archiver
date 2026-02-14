#!/bin/bash
# Quick examples of the CLI usage

echo "=== Basic Usage ==="
echo "tumblr-archiver myblog"
echo ""

echo "=== With Output Directory ==="
echo "tumblr-archiver myblog --output ./archive"
echo ""

echo "=== High Performance ==="
echo "tumblr-archiver myblog -c 5 -r 2.0 --verbose"
echo ""

echo "=== Safe Mode (Slow but careful) ==="
echo "tumblr-archiver myblog -c 1 -r 0.5 --max-retries 5"
echo ""

echo "=== Dry Run (Test without downloading) ==="
echo "tumblr-archiver myblog --dry-run --verbose"
echo ""

echo "=== Full URL Support ==="
echo "tumblr-archiver https://myblog.tumblr.com"
echo ""

echo "=== Exclude Reblogs ==="
echo "tumblr-archiver myblog --exclude-reblogs"
echo ""

echo "=== Download Embedded Media (YouTube, etc.) ==="
echo "tumblr-archiver myblog --download-embeds"
echo ""

echo "=== Fresh Download (No Resume) ==="
echo "tumblr-archiver myblog --no-resume"
echo ""

echo "=== Check Version ==="
echo "tumblr-archiver --version"
echo ""

echo "=== Get Help ==="
echo "tumblr-archiver --help"
