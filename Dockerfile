# Tumblr Media Archiver - Production Dockerfile
# Multi-stage build for minimal image size

# Stage 1: Builder
FROM python:3.12-slim as builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy dependency files
WORKDIR /build
COPY pyproject.toml ./
COPY src/ ./src/

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install .


# Stage 2: Runtime
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    TUMBLR_API_KEY=""

# Add labels
LABEL maintainer="parker@example.com" \
      description="Tumblr Media Archiver - CLI tool for archiving Tumblr media content" \
      version="0.1.0" \
      org.opencontainers.image.title="Tumblr Media Archiver" \
      org.opencontainers.image.description="CLI tool for archiving Tumblr media content" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.authors="Parker <parker@example.com>" \
      org.opencontainers.image.url="https://github.com/parker/tumblr-archiver" \
      org.opencontainers.image.source="https://github.com/parker/tumblr-archiver" \
      org.opencontainers.image.licenses="MIT"

# Create non-root user
RUN groupadd -r archiver && \
    useradd -r -g archiver -u 1001 -m -s /bin/bash archiver

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
WORKDIR /app
COPY --chown=archiver:archiver src/ ./src/
COPY --chown=archiver:archiver README.md LICENSE ./

# Create directories for output and archives
RUN mkdir -p /archives /downloads && \
    chown -R archiver:archiver /archives /downloads

# Switch to non-root user
USER archiver

# Set working directory for archives
WORKDIR /archives

# Volume mount point for persistent storage
VOLUME ["/archives"]

# Health check (optional - checks if the CLI is responsive)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD tumblr-archiver --help > /dev/null || exit 1

# Entry point
ENTRYPOINT ["tumblr-archiver"]

# Default command (shows help)
CMD ["--help"]

# Usage examples:
# 
# Build the image:
#   docker build -t tumblr-archiver .
#
# Run with API key from environment:
#   docker run -e TUMBLR_API_KEY=your_api_key_here \
#       -v ${PWD}/archives:/archives \
#       tumblr-archiver archive myblog
#
# Run with interactive mode:
#   docker run -it -e TUMBLR_API_KEY=your_api_key_here \
#       -v ${PWD}/archives:/archives \
#       tumblr-archiver archive myblog --post-type photo --limit 100
#
# Run with config file:
#   docker run -e TUMBLR_API_KEY=your_api_key_here \
#       -v ${PWD}/config.json:/app/config.json:ro \
#       -v ${PWD}/archives:/archives \
#       tumblr-archiver archive myblog --config /app/config.json
#
# Override entry point for shell access:
#   docker run -it --entrypoint /bin/bash tumblr-archiver
