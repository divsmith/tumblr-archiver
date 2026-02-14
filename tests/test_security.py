"""
Tests for security module.

Tests input validation, sanitization, and security checks.
"""

import os
import pytest
from pathlib import Path

from tumblr_archiver.security import (
    sanitize_blog_name,
    validate_url,
    is_safe_path,
    sanitize_user_input,
    validate_file_path,
    sanitize_filename,
    SecurityError,
    InvalidBlogNameError,
    InvalidURLError,
    PathTraversalError,
    InvalidInputError,
)


class TestSanitizeBlogName:
    """Tests for blog name sanitization."""
    
    def test_valid_blog_name(self):
        """Test valid blog names."""
        assert sanitize_blog_name("myblog") == "myblog"
        assert sanitize_blog_name("my-blog") == "my-blog"
        assert sanitize_blog_name("blog123") == "blog123"
        assert sanitize_blog_name("a") == "a"
        assert sanitize_blog_name("MyBlog") == "myblog"  # Lowercase conversion
    
    def test_blog_name_with_whitespace(self):
        """Test blog names with leading/trailing whitespace."""
        assert sanitize_blog_name("  myblog  ") == "myblog"
        assert sanitize_blog_name("\tmyblog\n") == "myblog"
    
    def test_empty_blog_name(self):
        """Test empty blog name raises error."""
        with pytest.raises(InvalidBlogNameError, match="non-empty string"):
            sanitize_blog_name("")
        
        with pytest.raises(InvalidBlogNameError, match="non-empty string"):
            sanitize_blog_name("   ")
    
    def test_invalid_type(self):
        """Test invalid input types."""
        with pytest.raises(InvalidBlogNameError, match="non-empty string"):
            sanitize_blog_name(None)
        
        with pytest.raises(InvalidBlogNameError):
            sanitize_blog_name(123)
    
    def test_too_long_blog_name(self):
        """Test blog names that are too long."""
        long_name = "a" * 33
        with pytest.raises(InvalidBlogNameError, match="between 1 and 32 characters"):
            sanitize_blog_name(long_name)
    
    def test_invalid_characters(self):
        """Test blog names with invalid characters."""
        with pytest.raises(InvalidBlogNameError, match="letters, numbers, and hyphens"):
            sanitize_blog_name("my_blog")  # Underscore
        
        with pytest.raises(InvalidBlogNameError):
            sanitize_blog_name("my.blog")  # Period
        
        with pytest.raises(InvalidBlogNameError):
            sanitize_blog_name("my blog")  # Space
        
        with pytest.raises(InvalidBlogNameError):
            sanitize_blog_name("my@blog")  # Special char
    
    def test_path_traversal_attempts(self):
        """Test path traversal patterns are rejected."""
        with pytest.raises(InvalidBlogNameError):
            sanitize_blog_name("../etc/passwd")
        
        with pytest.raises(InvalidBlogNameError):
            sanitize_blog_name("../../root")
    
    def test_leading_trailing_hyphens(self):
        """Test blog names with leading/trailing hyphens."""
        with pytest.raises(InvalidBlogNameError, match="cannot start or end with a hyphen"):
            sanitize_blog_name("-myblog")
        
        with pytest.raises(InvalidBlogNameError, match="cannot start or end with a hyphen"):
            sanitize_blog_name("myblog-")
    
    def test_consecutive_hyphens(self):
        """Test blog names with consecutive hyphens."""
        with pytest.raises(InvalidBlogNameError, match="consecutive hyphens"):
            sanitize_blog_name("my--blog")
        
        with pytest.raises(InvalidBlogNameError):
            sanitize_blog_name("my---blog")


class TestValidateURL:
    """Tests for URL validation."""
    
    def test_valid_http_url(self):
        """Test valid HTTP URLs."""
        url = "http://example.tumblr.com/post/123"
        assert validate_url(url) == url
    
    def test_valid_https_url(self):
        """Test valid HTTPS URLs."""
        url = "https://example.tumblr.com/post/123"
        assert validate_url(url) == url
    
    def test_url_with_query_params(self):
        """Test URLs with query parameters."""
        url = "https://example.com/page?param=value&other=123"
        result = validate_url(url)
        assert "example.com" in result
        assert "param=value" in result
    
    def test_url_with_fragment(self):
        """Test URLs with fragments."""
        url = "https://example.com/page#section"
        result = validate_url(url)
        assert "example.com" in result
    
    def test_empty_url(self):
        """Test empty URL raises error."""
        with pytest.raises(InvalidURLError, match="non-empty string"):
            validate_url("")
        
        with pytest.raises(InvalidURLError):
            validate_url(None)
    
    def test_url_without_scheme(self):
        """Test URL without scheme."""
        with pytest.raises(InvalidURLError, match="must have a scheme"):
            validate_url("example.com/page")
    
    def test_invalid_scheme(self):
        """Test URLs with invalid schemes."""
        with pytest.raises(InvalidURLError, match="not allowed"):
            validate_url("javascript:alert(1)")
        
        with pytest.raises(InvalidURLError, match="not allowed"):
            validate_url("file:///etc/passwd")
        
        with pytest.raises(InvalidURLError, match="not allowed"):
            validate_url("ftp://example.com")
    
    def test_custom_allowed_schemes(self):
        """Test custom allowed schemes."""
        url = "ftp://example.com/file.txt"
        result = validate_url(url, allowed_schemes=['ftp'])
        assert result == url
    
    def test_url_without_domain(self):
        """Test URL without domain."""
        with pytest.raises(InvalidURLError, match="valid domain"):
            validate_url("http://")
        
        with pytest.raises(InvalidURLError):
            validate_url("https:///path")
    
    def test_credential_injection(self):
        """Test URLs with credential injection attempts."""
        with pytest.raises(InvalidURLError, match="suspicious pattern"):
            validate_url("https://user:pass@evil.com@example.com/")
    
    def test_path_traversal_in_url(self):
        """Test URLs with path traversal patterns."""
        with pytest.raises(InvalidURLError, match="suspicious pattern"):
            validate_url("https://example.com/../../../etc/passwd")
    
    def test_control_characters(self):
        """Test URLs with control characters."""
        with pytest.raises(InvalidURLError, match="suspicious pattern"):
            validate_url("https://example.com/page\x00malicious")
        
        with pytest.raises(InvalidURLError):
            validate_url("https://example.com/page\x1fmalicious")
    
    def test_url_normalization(self):
        """Test URL normalization."""
        url = "https://example.com:443/page"
        result = validate_url(url)
        assert "example.com" in result


class TestIsSafePath:
    """Tests for path safety checks."""
    
    def test_safe_relative_path(self):
        """Test safe relative paths."""
        assert is_safe_path("downloads/blog/image.jpg") == True
        assert is_safe_path("data/archive/post.html") == True
    
    def test_safe_absolute_path(self):
        """Test safe absolute paths."""
        # This depends on the system, but should be safe if not in sensitive dirs
        home_path = str(Path.home() / "downloads" / "file.txt")
        assert is_safe_path(home_path) == True
    
    def test_path_traversal_with_dots(self):
        """Test path traversal with .. patterns."""
        assert is_safe_path("../../../etc/passwd") == False
        assert is_safe_path("downloads/../../../etc/passwd") == False
        assert is_safe_path("./../../root") == False
    
    def test_path_with_base_dir(self):
        """Test path safety with base directory restriction."""
        base = "/home/user/downloads"
        
        # Safe path within base
        safe_path = "/home/user/downloads/file.txt"
        assert is_safe_path(safe_path, base) == True
        
        # Path outside base
        unsafe_path = "/home/user/documents/file.txt"
        assert is_safe_path(unsafe_path, base) == False
        
        # Traversal attempt
        traversal_path = "/home/user/downloads/../documents/file.txt"
        assert is_safe_path(traversal_path, base) == False
    
    def test_sensitive_system_paths(self):
        """Test that sensitive system paths are rejected."""
        assert is_safe_path("/etc/passwd") == False
        assert is_safe_path("/sys/kernel") == False
        assert is_safe_path("/proc/self") == False
        assert is_safe_path("/dev/sda") == False
        assert is_safe_path("/root/.ssh/id_rsa") == False
    
    def test_empty_path(self):
        """Test empty path."""
        assert is_safe_path("") == False
        assert is_safe_path(None) == False
    
    def test_invalid_path_type(self):
        """Test invalid path types."""
        assert is_safe_path(123) == False
        assert is_safe_path([]) == False


class TestSanitizeUserInput:
    """Tests for user input sanitization."""
    
    def test_normal_input(self):
        """Test normal user input."""
        assert sanitize_user_input("hello world") == "hello world"
        assert sanitize_user_input("test-input_123") == "test-input_123"
    
    def test_input_with_whitespace(self):
        """Test input with leading/trailing whitespace."""
        assert sanitize_user_input("  hello  ") == "hello"
        assert sanitize_user_input("\thello\n") == "hello"
    
    def test_control_characters_removed(self):
        """Test that control characters are removed."""
        result = sanitize_user_input("hello\x00world")
        assert result == "helloworld"
        
        result = sanitize_user_input("test\x1fdata")
        assert result == "testdata"
    
    def test_newlines_removed_by_default(self):
        """Test that newlines are removed by default."""
        result = sanitize_user_input("line1\nline2")
        assert result == "line1line2"
        
        result = sanitize_user_input("line1\r\nline2")
        assert result == "line1line2"
    
    def test_newlines_allowed_when_specified(self):
        """Test that newlines can be allowed."""
        result = sanitize_user_input("line1\nline2", allow_newlines=True)
        assert result == "line1\nline2"
    
    def test_max_length_enforcement(self):
        """Test maximum length enforcement."""
        long_input = "a" * 2000
        with pytest.raises(InvalidInputError, match="exceeds maximum length"):
            sanitize_user_input(long_input, max_length=1000)
    
    def test_custom_max_length(self):
        """Test custom maximum length."""
        input_str = "a" * 50
        result = sanitize_user_input(input_str, max_length=100)
        assert result == input_str
        
        with pytest.raises(InvalidInputError):
            sanitize_user_input(input_str, max_length=25)
    
    def test_invalid_input_type(self):
        """Test invalid input types."""
        with pytest.raises(InvalidInputError, match="must be a string"):
            sanitize_user_input(123)
        
        with pytest.raises(InvalidInputError):
            sanitize_user_input(None)


class TestValidateFilePath:
    """Tests for file path validation."""
    
    def test_valid_file_path(self, tmp_path):
        """Test valid file path."""
        base = str(tmp_path)
        file_path = "images/photo.jpg"
        
        result = validate_file_path(file_path, base)
        assert isinstance(result, Path)
        assert str(result).startswith(base)
    
    def test_path_traversal_rejected(self, tmp_path):
        """Test path traversal attempts are rejected."""
        base = str(tmp_path)
        
        with pytest.raises(PathTraversalError):
            validate_file_path("../../../etc/passwd", base)
    
    def test_path_outside_base_rejected(self, tmp_path):
        """Test paths outside base directory are rejected."""
        base = str(tmp_path / "subdir")
        
        with pytest.raises(PathTraversalError):
            validate_file_path("/etc/passwd", base)
    
    def test_allowed_extensions(self, tmp_path):
        """Test file extension restrictions."""
        base = str(tmp_path)
        
        # Allowed extension
        result = validate_file_path("file.jpg", base, [".jpg", ".png"])
        assert result.suffix == ".jpg"
        
        # Disallowed extension
        with pytest.raises(InvalidInputError, match="not allowed"):
            validate_file_path("file.exe", base, [".jpg", ".png"])
    
    def test_case_insensitive_extensions(self, tmp_path):
        """Test case-insensitive extension checking."""
        base = str(tmp_path)
        
        result = validate_file_path("file.JPG", base, [".jpg"])
        assert result.suffix == ".JPG"
    
    def test_empty_inputs(self, tmp_path):
        """Test empty inputs."""
        with pytest.raises(InvalidInputError):
            validate_file_path("", str(tmp_path))
        
        with pytest.raises(InvalidInputError):
            validate_file_path("file.txt", "")


class TestSanitizeFilename:
    """Tests for filename sanitization."""
    
    def test_valid_filename(self):
        """Test valid filenames."""
        assert sanitize_filename("photo.jpg") == "photo.jpg"
        assert sanitize_filename("my-file_123.txt") == "my-file_123.txt"
    
    def test_remove_path_separators(self):
        """Test that path separators are removed."""
        assert sanitize_filename("some/path/file.txt") == "somepathfile.txt"
        assert sanitize_filename("some\\path\\file.txt") == "somepathfile.txt"
    
    def test_remove_dangerous_characters(self):
        """Test that dangerous characters are removed."""
        assert sanitize_filename("file:name.txt") == "filename.txt"
        assert sanitize_filename("file<name>.txt") == "filename.txt"
        assert sanitize_filename("file|name.txt") == "filename.txt"
    
    def test_path_traversal_removed(self):
        """Test that path traversal is neutralized."""
        result = sanitize_filename("../../../etc/passwd")
        assert ".." not in result
        assert "/" not in result
        assert result == "etcpasswd"
    
    def test_remove_leading_trailing_periods(self):
        """Test that leading/trailing periods are removed."""
        assert sanitize_filename(".hidden") == "hidden"
        assert sanitize_filename("file.") == "file"
        assert sanitize_filename("...file...") == "file"
    
    def test_normalize_spaces(self):
        """Test space normalization."""
        assert sanitize_filename("my    file.txt") == "my file.txt"
        assert sanitize_filename("  file  .txt  ") == "file .txt"  # Multiple spaces normalized
    
    def test_truncate_long_filename(self):
        """Test long filename truncation."""
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name, max_length=255)
        assert len(result) <= 255
        assert result.endswith(".txt")  # Extension preserved
    
    def test_preserve_extension_when_truncating(self):
        """Test that extension is preserved when truncating."""
        long_name = "a" * 300 + ".jpeg"
        result = sanitize_filename(long_name, max_length=100)
        assert len(result) <= 100
        assert result.endswith(".jpeg")
    
    def test_empty_after_sanitization(self):
        """Test error when filename is empty after sanitization."""
        with pytest.raises(InvalidInputError, match="empty after sanitization"):
            sanitize_filename("///")
        
        with pytest.raises(InvalidInputError):
            sanitize_filename("...")
    
    def test_invalid_input(self):
        """Test invalid input types."""
        with pytest.raises(InvalidInputError):
            sanitize_filename("")
        
        with pytest.raises(InvalidInputError):
            sanitize_filename(None)


class TestSecurityExceptions:
    """Tests for security exception classes."""
    
    def test_exception_hierarchy(self):
        """Test that all security exceptions inherit from SecurityError."""
        assert issubclass(InvalidBlogNameError, SecurityError)
        assert issubclass(InvalidURLError, SecurityError)
        assert issubclass(PathTraversalError, SecurityError)
        assert issubclass(InvalidInputError, SecurityError)
    
    def test_exceptions_are_exceptions(self):
        """Test that security exceptions are proper exceptions."""
        assert issubclass(SecurityError, Exception)
    
    def test_raise_and_catch(self):
        """Test raising and catching security exceptions."""
        with pytest.raises(SecurityError):
            raise InvalidBlogNameError("test")
        
        with pytest.raises(InvalidURLError):
            raise InvalidURLError("test")


class TestMaliciousInputs:
    """Tests for handling malicious inputs."""
    
    def test_sql_injection_patterns(self):
        """Test SQL injection patterns are sanitized."""
        malicious = "'; DROP TABLE users; --"
        result = sanitize_user_input(malicious)
        # Should be sanitized (control chars removed, but SQL syntax remains as text)
        assert len(result) > 0
    
    def test_xss_patterns(self):
        """Test XSS patterns in various contexts."""
        xss = "<script>alert('xss')</script>"
        result = sanitize_user_input(xss)
        assert len(result) > 0
        
        # Blog names should reject special chars
        with pytest.raises(InvalidBlogNameError):
            sanitize_blog_name("<script>")
    
    def test_command_injection(self):
        """Test command injection patterns."""
        malicious = "; rm -rf /"
        result = sanitize_user_input(malicious)
        assert len(result) > 0
        
        # Should fail blog name validation
        with pytest.raises(InvalidBlogNameError):
            sanitize_blog_name(malicious)
    
    def test_null_byte_injection(self):
        """Test null byte injection."""
        malicious = "file.txt\x00.exe"
        result = sanitize_user_input(malicious)
        assert "\x00" not in result
    
    def test_unicode_attacks(self):
        """Test various Unicode-based attacks."""
        # Right-to-left override
        rtlo = "file\u202etxt.exe"
        result = sanitize_filename(rtlo)
        assert len(result) > 0
        
        # Zero-width characters
        zero_width = "file\u200bname.txt"
        result = sanitize_filename(zero_width)
        assert len(result) > 0
    
    def test_extremely_long_inputs(self):
        """Test extremely long inputs."""
        huge_input = "a" * 100000
        
        with pytest.raises(InvalidInputError):
            sanitize_user_input(huge_input, max_length=10000)
        
        with pytest.raises(InvalidBlogNameError):
            sanitize_blog_name(huge_input)
    
    def test_mixed_attacks(self):
        """Test mixed attack patterns."""
        mixed = "../<script>../../etc/passwd\x00.txt"
        
        # Should fail blog name validation
        with pytest.raises(InvalidBlogNameError):
            sanitize_blog_name(mixed)
        
        # Should be sanitized for general input
        result = sanitize_user_input(mixed)
        assert "\x00" not in result
