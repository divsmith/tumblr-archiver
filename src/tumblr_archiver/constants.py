"""Constants for the Tumblr archiver application."""

from typing import Final

# Rate limiting and concurrency defaults
DEFAULT_RATE_LIMIT: Final[float] = 1.0  # requests per second
DEFAULT_CONCURRENCY: Final[int] = 2  # concurrent download workers
DEFAULT_TIMEOUT: Final[float] = 30.0  # HTTP request timeout in seconds
DEFAULT_MAX_RETRIES: Final[int] = 3  # maximum retry attempts
DEFAULT_BASE_BACKOFF: Final[float] = 1.0  # initial backoff in seconds
DEFAULT_MAX_BACKOFF: Final[float] = 32.0  # maximum backoff in seconds

# User agent for respectful API usage
USER_AGENT: Final[str] = (
    "TumblrArchiver/1.0 (Wayback Machine Media Retrieval Tool; "
    "https://github.com/yourusername/tumblr-archive)"
)

# Tumblr API and URL constants
TUMBLR_BASE_URL: Final[str] = "https://{blog_name}.tumblr.com"
TUMBLR_API_BASE: Final[str] = "https://api.tumblr.com/v2"

# Wayback Machine CDN and API URLs
WAYBACK_CDX_API_URL: Final[str] = "https://web.archive.org/cdx/search/cdx"
WAYBACK_SNAPSHOT_URL_TEMPLATE: Final[str] = "https://web.archive.org/web/{timestamp}id_/{url}"
WAYBACK_AVAILABILITY_API: Final[str] = "https://archive.org/wayback/available"

# Supported media types
SUPPORTED_IMAGE_TYPES: Final[frozenset[str]] = frozenset({
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp",
})

SUPPORTED_VIDEO_TYPES: Final[frozenset[str]] = frozenset({
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-msvideo",
})

SUPPORTED_AUDIO_TYPES: Final[frozenset[str]] = frozenset({
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/ogg",
})

# File extensions mapping
IMAGE_EXTENSIONS: Final[frozenset[str]] = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"
})

VIDEO_EXTENSIONS: Final[frozenset[str]] = frozenset({
    ".mp4", ".webm", ".mov", ".avi"
})

AUDIO_EXTENSIONS: Final[frozenset[str]] = frozenset({
    ".mp3", ".wav", ".ogg"
})

# HTTP status codes
HTTP_OK: Final[int] = 200
HTTP_CREATED: Final[int] = 201
HTTP_ACCEPTED: Final[int] = 202
HTTP_NO_CONTENT: Final[int] = 204
HTTP_MOVED_PERMANENTLY: Final[int] = 301
HTTP_FOUND: Final[int] = 302
HTTP_NOT_MODIFIED: Final[int] = 304
HTTP_TEMPORARY_REDIRECT: Final[int] = 307
HTTP_PERMANENT_REDIRECT: Final[int] = 308
HTTP_BAD_REQUEST: Final[int] = 400
HTTP_UNAUTHORIZED: Final[int] = 401
HTTP_FORBIDDEN: Final[int] = 403
HTTP_NOT_FOUND: Final[int] = 404
HTTP_METHOD_NOT_ALLOWED: Final[int] = 405
HTTP_REQUEST_TIMEOUT: Final[int] = 408
HTTP_CONFLICT: Final[int] = 409
HTTP_GONE: Final[int] = 410
HTTP_TOO_MANY_REQUESTS: Final[int] = 429
HTTP_INTERNAL_SERVER_ERROR: Final[int] = 500
HTTP_BAD_GATEWAY: Final[int] = 502
HTTP_SERVICE_UNAVAILABLE: Final[int] = 503
HTTP_GATEWAY_TIMEOUT: Final[int] = 504

# Retry-able status codes
RETRYABLE_STATUS_CODES: Final[frozenset[int]] = frozenset({
    HTTP_REQUEST_TIMEOUT,
    HTTP_TOO_MANY_REQUESTS,
    HTTP_INTERNAL_SERVER_ERROR,
    HTTP_BAD_GATEWAY,
    HTTP_SERVICE_UNAVAILABLE,
    HTTP_GATEWAY_TIMEOUT,
})

# Success status codes
SUCCESS_STATUS_CODES: Final[frozenset[int]] = frozenset({
    HTTP_OK,
    HTTP_CREATED,
    HTTP_ACCEPTED,
    HTTP_NO_CONTENT,
})

# Redirect status codes
REDIRECT_STATUS_CODES: Final[frozenset[int]] = frozenset({
    HTTP_MOVED_PERMANENTLY,
    HTTP_FOUND,
    HTTP_TEMPORARY_REDIRECT,
    HTTP_PERMANENT_REDIRECT,
})
