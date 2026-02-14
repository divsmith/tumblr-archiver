# Multi-stage Dockerfile for tumblr-archiver
# Stage 1: Builder
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /build

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir .

# Stage 2: Runtime
FROM python:3.11-slim

# Set metadata
LABEL maintainer="parker@example.com"
LABEL description="Tumblr media archiver with Internet Archive fallback"

# Create non-root user
RUN useradd -m -u 1000 archiver && \
    mkdir -p /downloads && \
    chown -R archiver:archiver /downloads

# Install runtime dependencies only
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/tumblr-archiver /usr/local/bin/tumblr-archiver

# Switch to non-root user
USER archiver

# Set working directory
WORKDIR /downloads

# Health check (basic validation that the CLI is accessible)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD tumblr-archiver --version || exit 1

# Default command shows help
ENTRYPOINT ["tumblr-archiver"]
CMD ["--help"]
